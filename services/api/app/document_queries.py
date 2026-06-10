# ================================================================
# services/api/app/document_queries.py
# ================================================================
# Database operations for documents.
# Only SQL here — no business logic, no HTTP.
# ================================================================

import uuid
from asyncpg import Pool


async def create_document_record(
    pool: Pool,
    tenant_id: uuid.UUID,
    uploaded_by: uuid.UUID,
    original_filename: str,
    file_type: str,
    file_size_bytes: int,
    storage_path: str,
) -> dict:
    """
    Creates a document record in PostgreSQL after file is
    stored in MinIO.

    Called AFTER successful MinIO upload — if this fails,
    the file exists in MinIO but has no DB record.
    The upload route handles this by deleting the MinIO file
    if the DB insert fails (cleanup on failure).

    Returns the created document as a dict.
    """
    document_id = uuid.uuid4()

    row = await pool.fetchrow(
        """
        INSERT INTO documents (
            id,
            tenant_id,
            uploaded_by,
            original_filename,
            file_type,
            file_size_bytes,
            storage_path,
            compliance_status,
            processing_status
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending', 'uploaded')
        RETURNING
            id, tenant_id, uploaded_by, original_filename,
            file_type, file_size_bytes, storage_path,
            compliance_status, processing_status, created_at
        """,
        document_id,
        tenant_id,
        uploaded_by,
        original_filename,
        file_type,
        file_size_bytes,
        storage_path,
    )

    return dict(row)


async def get_documents_by_tenant(
    pool: Pool,
    tenant_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[dict]:
    """
    Returns all documents for a tenant, newest first.
    Paginated — limit/offset controls how many to return.
    RLS ensures tenant_id filter is redundant but we include
    it explicitly for clarity and defense in depth.
    """
    rows = await pool.fetch(
        """
        SELECT
            id, tenant_id, uploaded_by, original_filename,
            file_type, file_size_bytes, storage_path,
            compliance_status, processing_status, created_at
        FROM documents
        WHERE tenant_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        tenant_id,
        limit,
        offset,
    )

    return [dict(row) for row in rows]


async def get_document_by_id(
    pool: Pool,
    document_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict | None:
    """
    Fetches a single document by ID.
    tenant_id included for RLS defense in depth.
    Returns None if not found or belongs to different tenant.
    """
    row = await pool.fetchrow(
        """
        SELECT
            id, tenant_id, uploaded_by, original_filename,
            file_type, file_size_bytes, storage_path,
            compliance_status, processing_status,
            error_message, chunk_count, created_at
        FROM documents
        WHERE id = $1 AND tenant_id = $2
        """,
        document_id,
        tenant_id,
    )

    return dict(row) if row else None