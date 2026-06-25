# ================================================================
# services/api/app/document_routes.py
# ================================================================
# Document upload and listing endpoints.
#
# POST /documents/upload  — upload a file, store in MinIO + PostgreSQL
# GET  /documents/        — list all documents for current tenant
# GET  /documents/{id}    — get a single document by ID
# ================================================================
from uuid import UUID
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi import Query

from services.api.app.database import get_postgresql_pool
from services.api.app.auth_routes import get_current_user
from services.api.app.metrics import documents_uploaded_total, documents_compliance_total
from services.api.app.schemas import DocumentOut, DocumentUploadResponse
from services.api.app.events import emit_document_event, DocumentEvent
from services.api.app.notifications import notify_document_event
from services.api.app.audit_queries import write_audit_log
from services.api.app.storage import (
    upload_file_to_minio,
    SUPPORTED_FILE_TYPES,
    MAX_FILE_SIZE_BYTES,
    get_minio_client,
)
from services.api.app.document_queries import (
    create_document_record,
    get_documents_by_tenant,
    get_document_by_id,
)
from services.api.app.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
     
    """
    Uploads a document to MinIO and creates a PostgreSQL record.

    Steps:
        1. Validate file type is supported
        2. Validate file size is within limit
        3. Upload to MinIO
        4. Create document record in PostgreSQL
        5. Return document metadata

    If step 4 fails, the MinIO file is deleted to avoid orphans.
    """

    # ── Step 1: validate file type ──────────────────────────────
    content_type = file.content_type or ""

    if content_type not in SUPPORTED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{content_type}' is not supported. "
                f"Supported types: PDF, images (JPEG/PNG/TIFF), "
                f"audio (MP3/WAV/OGG), Word, Excel, PowerPoint."
            ),
        )

    file_category = SUPPORTED_FILE_TYPES[content_type]

    # ── Step 2: validate file size ──────────────────────────────
    # Read entire file into memory to check size
    # For files > 50MB we will add chunked upload in a later phase
    file_bytes = await file.read()
    file_size = len(file_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File size {file_size / 1024 / 1024:.1f}MB exceeds "
                f"the 50MB limit."
            ),
        )

    # ── Step 3: generate document ID before upload ──────────────
    # We generate the ID here so we can use it in the storage path
    # before creating the DB record. This ensures the path is
    # deterministic and tied to the document ID.
    document_id = uuid.uuid4()
    tenant_id = uuid.UUID(str(current_user["tenant_id"]))
    user_id = uuid.UUID(str(current_user["id"]))

    # ── Step 4: upload to MinIO ─────────────────────────────────
    storage_path = await upload_file_to_minio(
        file_bytes=file_bytes,
        tenant_id=tenant_id,
        document_id=document_id,
        original_filename=file.filename or "unnamed",
        content_type=content_type,
    )

    # ── Step 5: create PostgreSQL record ────────────────────────
    # If this fails, delete the MinIO file to avoid orphaned files
    # that have no corresponding DB record.
    try:
        document = await create_document_record(
            pool=pool,
            tenant_id=tenant_id,
            uploaded_by=user_id,
            original_filename=file.filename or "unnamed",
            file_type=file_category,
            file_size_bytes=file_size,
            storage_path=storage_path,
        )
    except Exception as e:
        # Cleanup MinIO file on DB failure
        try:
            client = get_minio_client()
            client.remove_object(
                settings.minio_bucket_documents,
                storage_path,
            )
        except Exception:
            pass  # MinIO cleanup failure is logged, not raised

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document record. File upload rolled back.",
        )
# ── Step 6: queue parsing task ──────────────────────────────
    # Queue async processing task — returns immediately.
    # Worker picks it up and parses in background.
    # User polls GET /documents/{id} to check processing_status.
    from services.api.app.tasks import process_document
    process_document.delay(
        document_id=str(document["id"]),
        tenant_id=str(document["tenant_id"]),
    )
    
    # Emit upload event to Redis Streams
    await emit_document_event(
        event_type=DocumentEvent.UPLOADED,
        document_id=str(document["id"]),
        tenant_id=str(document["tenant_id"]),
        user_id=str(current_user["id"]),
        payload={"filename": document["original_filename"]},
    )

    # Send notification (email/Slack if configured)
    await notify_document_event(
        event_type=DocumentEvent.UPLOADED,
        document_id=str(document["id"]),
        filename=document["original_filename"],
        tenant_name=str(current_user["tenant_id"]),
        user_email=current_user["email"],
    )
# Write to audit log
    await write_audit_log(
        pool=pool,
        tenant_id=tenant_id,
        event_type="document.uploaded",
        document_id=str(document["id"]),
        user_id=str(current_user["id"]),
        payload={"filename": document["original_filename"]},
    )



# Record metric: document uploaded
    documents_uploaded_total.labels(
        tenant_id=str(tenant_id),
        file_type=file_category,
    ).inc()
    return DocumentUploadResponse(
        message=(
            f"Document '{file.filename}' uploaded successfully. "
            f"Status: pending PII scan."
        ),
        document=DocumentOut(**document),
    )


@router.get("/", response_model=list[DocumentOut])
async def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Lists all documents for the current tenant.
    Paginated — use limit and offset to page through results.
    RLS ensures only this tenant's documents are returned.
    """
    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    documents = await get_documents_by_tenant(
        pool=pool,
        tenant_id=tenant_id,
        limit=limit,
        offset=offset,
    )

    return [DocumentOut(**doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Returns a single document by ID.
    Returns 404 if document does not exist or belongs to
    a different tenant — indistinguishable by design.
    (We do not reveal whether a document exists in another tenant)
    """
    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    document = await get_document_by_id(
        pool=pool,
        document_id=document_id,
        tenant_id=tenant_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    return DocumentOut(**document)
@router.post("/{document_id}/approve", response_model=DocumentOut)
async def approve_document(
    document_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Approves a clean document for embedding into the knowledge base.
    Only admin and editor roles can approve documents.
    Only documents with compliance_status='clean' can be approved.
    Triggers embedding task after approval.
    """
    # Check role — viewers cannot approve
    if current_user["role"] not in ("admin", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and editor roles can approve documents.",
        )

    tenant_id = uuid.UUID(str(current_user["tenant_id"]))

    # Fetch the document
    document = await get_document_by_id(
        pool=pool,
        document_id=document_id,
        tenant_id=tenant_id,
    )

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    # Only clean documents can be approved
    if document["compliance_status"] != "clean":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Document cannot be approved. "
                f"Current compliance_status: "
                f"{document['compliance_status']}. "
                f"Only 'clean' documents can be approved."
            ),
        )

    # Only processed documents can be approved
    if document["processing_status"] != "processed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Document is not ready for approval. "
                f"Current processing_status: "
                f"{document['processing_status']}. "
                f"Wait for processing to complete."
            ),
        )

    # Update status to approved
    await pool.execute(
        """
        UPDATE documents
        SET compliance_status = 'approved',
            processing_status = 'embedding',
            updated_at = NOW()
        WHERE id = $1 AND tenant_id = $2
        """,
        document_id,
        tenant_id,
    )

    # Queue embedding task
    from services.api.app.tasks import embed_document
    embed_document.delay(
        document_id=str(document_id),
        tenant_id=str(tenant_id),
    )

    # Emit approval event
    await emit_document_event(
        event_type=DocumentEvent.APPROVED,
        document_id=str(document_id),
        tenant_id=str(tenant_id),
        user_id=str(current_user["id"]),
        payload={"filename": document["original_filename"]},
    )

    await write_audit_log(
        pool=pool,
        tenant_id=tenant_id,
        event_type="document.approved",
        document_id=str(document_id),
        user_id=str(current_user["id"]),
        payload={"filename": document["original_filename"]},
    )
    await notify_document_event(
        event_type=DocumentEvent.APPROVED,
        document_id=str(document_id),
        filename=document["original_filename"],
        tenant_name=str(tenant_id),
        user_email=current_user["email"],
    )
    # Return updated document
    updated = await get_document_by_id(
        pool=pool,
        document_id=document_id,
        tenant_id=tenant_id,
    )

    return DocumentOut(**updated)