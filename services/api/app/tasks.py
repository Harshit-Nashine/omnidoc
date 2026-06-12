# ================================================================
# services/api/app/tasks.py
# ================================================================
# Celery task definitions for document processing.
#
# HOW TASKS WORK:
# 1. API endpoint receives upload → stores file in MinIO
# 2. API creates PostgreSQL record (status: uploaded)
# 3. API queues this Celery task with document_id
# 4. API immediately returns 201 to user (does not wait)
# 5. Celery worker (separate process) picks up the task
# 6. Worker downloads file from MinIO
# 7. Worker runs the correct parser
# 8. Worker saves extracted text back to MinIO
# 9. Worker updates PostgreSQL status to 'processed'
# 10. User can poll GET /documents/{id} to check status
# ================================================================

import asyncio
import uuid
import io

from celery import Task
from services.api.app.celery_app import celery_app


class DocumentProcessingTask(Task):
    """
    Base task class with error handling.
    on_failure is called automatically if the task raises an exception.
    Updates document status to 'failed' with error message.
    """
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task raises an unhandled exception."""
        document_id = args[0] if args else kwargs.get("document_id")
        if document_id:
            # Run async function in sync context
            asyncio.run(
                _update_document_status(
                    document_id=document_id,
                    processing_status="failed",
                    error_message=str(exc),
                )
            )


@celery_app.task(
    base=DocumentProcessingTask,
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.process_document",
)
def process_document(self, document_id: str, tenant_id: str):
    """
    Main document processing task.
    Called after a document is uploaded via the API.

    Steps:
        1. Update status to 'processing'
        2. Download file from MinIO
        3. Parse document (PDF text extraction or OCR)
        4. Save extracted text back to MinIO
        5. Update status to 'processed'

    Args:
        document_id: UUID string of the document to process
        tenant_id:   UUID string of the owning tenant

    Retries up to 3 times on failure with 60 second delay.
    """
    try:
        # Run async operations in sync Celery context
        # asyncio.run() creates a new event loop for each task
        asyncio.run(
            _process_document_async(document_id, tenant_id)
        )
    except Exception as exc:
        # Retry on failure — handles transient errors
        raise self.retry(exc=exc)


async def _process_document_async(
    document_id: str,
    tenant_id: str,
) -> None:
    """
    Async implementation of document processing.
    Separated from the Celery task so it can be tested
    independently without Celery infrastructure.
    """
    import asyncpg
    from services.api.app.config import settings
    from services.api.app.storage import get_minio_client
    from services.api.app.parsers.router import parse_document

    # Connect directly to PostgreSQL — worker has its own connection
    # We don't use the FastAPI connection pool here because the
    # worker is a separate process from the API
    conn = await asyncpg.connect(settings.postgres_url)

    try:
        # ── Step 1: fetch document details ──────────────────────
        row = await conn.fetchrow(
            """
            SELECT id, tenant_id, storage_path, file_type,
                   original_filename, processing_status
            FROM documents
            WHERE id = $1
            """,
            uuid.UUID(document_id),
        )

        if row is None:
            raise ValueError(f"Document {document_id} not found")

        if row["processing_status"] != "uploaded":
            # Already processed or being processed — skip
            return

        document = dict(row)

        # ── Step 2: update status to processing ─────────────────
        await conn.execute(
            """
            UPDATE documents
            SET processing_status = 'processing', updated_at = NOW()
            WHERE id = $1
            """,
            uuid.UUID(document_id),
        )

        # ── Step 3: download file from MinIO ────────────────────
        minio_client = get_minio_client()
        from services.api.app.config import settings as s

        response = minio_client.get_object(
            bucket_name=s.minio_bucket_documents,
            object_name=document["storage_path"],
        )
        file_bytes = response.read()
        response.close()

        # ── Step 4: parse the document ──────────────────────────
        parsed = parse_document(
            file_bytes=file_bytes,
            file_type=document["file_type"],
            filename=document["original_filename"],
        )

        # ── Step 5: save extracted text to MinIO ────────────────
        # Store text alongside original file with .txt extension
        text_storage_path = document["storage_path"] + ".extracted.txt"

        text_bytes = parsed.full_text.encode("utf-8")
        minio_client.put_object(
            bucket_name=s.minio_bucket_documents,
            object_name=text_storage_path,
            data=io.BytesIO(text_bytes),
            length=len(text_bytes),
            content_type="text/plain",
        )

        # ── Step 6: update document record ──────────────────────
       # ── Step 6: scan for PII ─────────────────────────────────
        from services.api.app.parsers.pii_scanner import scan_for_pii
        pii_result = scan_for_pii(parsed.full_text)

        # ── Step 7: if flagged — save to MongoDB quarantine ──────
        if pii_result.compliance_status in ("flagged", "quarantined"):
            from motor.motor_asyncio import AsyncIOMotorClient
            from services.api.app.config import settings as s

            mongo_client = AsyncIOMotorClient(s.mongo_url)
            db = mongo_client[s.mongo_db]

            await db.quarantine.insert_one({
                "document_id": document_id,
                "tenant_id": tenant_id,
                "original_filename": document["original_filename"],
                "compliance_status": pii_result.compliance_status,
                "pii_types_found": pii_result.pii_types_found,
                "summary": pii_result.summary,
                "extracted_text_preview": parsed.full_text[:500],
                "storage_path": document["storage_path"],
            })

            mongo_client.close()

        # ── Step 8: update document record ──────────────────────
        await conn.execute(
            """
            UPDATE documents
            SET
                processing_status = 'processed',
                compliance_status = $1,
                extracted_text_path = $2,
                updated_at = NOW()
            WHERE id = $3
            """,
            pii_result.compliance_status,
            text_storage_path,
            uuid.UUID(document_id),
        )

    finally:
        # Always close the connection — even if something failed
        await conn.close()


async def _update_document_status(
    document_id: str,
    processing_status: str,
    error_message: str = None,
) -> None:
    """Updates document status — called by error handler."""
    import asyncpg
    from services.api.app.config import settings

    conn = await asyncpg.connect(settings.postgres_url)
    try:
        await conn.execute(
            """
            UPDATE documents
            SET processing_status = $1,
                error_message = $2,
                updated_at = NOW()
            WHERE id = $3
            """,
            processing_status,
            error_message,
            uuid.UUID(document_id),
        )
    finally:
        await conn.close()

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="tasks.embed_document",
)
def embed_document(self, document_id: str, tenant_id: str):
    """
    Embeds an approved document into the ChromaDB vector store.
    Called after a document is approved via the approval endpoint.

    Steps:
        1. Fetch extracted text from MinIO
        2. Chunk the text
        3. Embed chunks using sentence-transformers
        4. Store in ChromaDB tenant collection
        5. Update PostgreSQL status to 'completed'
    """
    try:
        asyncio.run(
            _embed_document_async(document_id, tenant_id)
        )
    except Exception as exc:
        raise self.retry(exc=exc)


async def _embed_document_async(
    document_id: str,
    tenant_id: str,
) -> None:
    """Async implementation of document embedding."""
    import asyncpg
    from services.api.app.config import settings
    from services.api.app.storage import get_minio_client
    from services.api.app.chunker import chunk_document
    from services.api.app.vector_store import add_chunks_to_store

    conn = await asyncpg.connect(settings.postgres_url)

    try:
        # ── Step 1: fetch document details ──────────────────────
        row = await conn.fetchrow(
            """
            SELECT id, tenant_id, storage_path, file_type,
                   original_filename, extracted_text_path
            FROM documents
            WHERE id = $1
            """,
            uuid.UUID(document_id),
        )

        if row is None:
            raise ValueError(f"Document {document_id} not found")

        document = dict(row)

        if not document["extracted_text_path"]:
            raise ValueError(
                f"Document {document_id} has no extracted text. "
                f"Run processing first."
            )

        # ── Step 2: download extracted text from MinIO ───────────
        minio_client = get_minio_client()
        from services.api.app.config import settings as s

        response = minio_client.get_object(
            bucket_name=s.minio_bucket_documents,
            object_name=document["extracted_text_path"],
        )
        extracted_text = response.read().decode("utf-8")
        response.close()

        # ── Step 3: chunk the text ───────────────────────────────
        chunks = chunk_document(
            full_text=extracted_text,
            pages=extracted_text.split("\n\n--- PAGE BREAK ---\n\n"),
        )

        if not chunks:
            raise ValueError(
                f"Document {document_id} produced no chunks. "
                f"Text may be empty or too short."
            )

        # ── Step 4: embed and store in ChromaDB ──────────────────
        chunk_dicts = [
            {
                "text": chunk.text,
                "chunk_id": chunk.chunk_id,
                "page": chunk.page,
            }
            for chunk in chunks
        ]

        chunks_added = add_chunks_to_store(
            tenant_id=tenant_id,
            document_id=document_id,
            chunks=chunk_dicts,
        )

        # ── Step 5: update PostgreSQL ────────────────────────────
        await conn.execute(
            """
            UPDATE documents
            SET
                processing_status = 'completed',
                chunk_count = $1,
                updated_at = NOW()
            WHERE id = $2
            """,
            chunks_added,
            uuid.UUID(document_id),
        )

    finally:
        await conn.close()