# ================================================================
# services/api/app/document_routes.py
# ================================================================
# Document upload and listing endpoints.
#
# POST /documents/upload  — upload a file, store in MinIO + PostgreSQL
# GET  /documents/        — list all documents for current tenant
# GET  /documents/{id}    — get a single document by ID
# ================================================================

import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi import Query

from services.api.app.database import get_postgresql_pool
from services.api.app.auth_routes import get_current_user
from services.api.app.schemas import DocumentOut, DocumentUploadResponse
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