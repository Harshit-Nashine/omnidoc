# ================================================================
# services/api/app/storage.py
# ================================================================
# MinIO client utility for storing and retrieving raw files.
#
# WHY MINIO:
# S3-compatible API — code is identical whether files are stored
# in local MinIO (dev) or real AWS S3 (production).
# Switching to S3 in production = change 3 env variables, zero code.
#
# STORAGE PATH FORMAT:
# {tenant_id}/{document_id}/{original_filename}
# tenant_id in the path = second layer of isolation beyond RLS.
# Even if RLS had a bug, files from different tenants live in
# completely separate path prefixes.
# ================================================================

import io
from uuid import UUID
from minio import Minio
from minio.error import S3Error
from services.api.app.config import settings


def get_minio_client() -> Minio:
    """
    Creates and returns a MinIO client instance.

    Called once per request — Minio client is lightweight,
    no persistent connection needed unlike DB pools.

    secure=False because we are running locally without TLS.
    In production, set secure=True and provide TLS certificates.
    """
    return Minio(
        # endpoint format: host:port (no http:// prefix)
        endpoint=f"{settings.minio_host}:{settings.minio_port}",
        access_key=settings.minio_root_user,
        secret_key=settings.minio_root_password,
        # secure=False for local dev — MinIO runs without TLS locally
        # Change to True when deploying with real TLS certificates
        secure=False,
    )


async def upload_file_to_minio(
    file_bytes: bytes,
    tenant_id: UUID,
    document_id: UUID,
    original_filename: str,
    content_type: str,
) -> str:
    """
    Uploads a file to MinIO and returns the storage path.

    Storage path format: {tenant_id}/{document_id}/{filename}
    This path is stored in PostgreSQL documents.storage_path.

    Returns:
        storage_path — the path inside the bucket
        e.g. "738137fd/60d69a91/report.pdf"

    Raises:
        S3Error if upload fails
    """
    client = get_minio_client()
    bucket = settings.minio_bucket_documents

    # Build the storage path
    # Using first 8 chars of UUID for readability in MinIO console
    storage_path = (
        f"{str(tenant_id)}/{str(document_id)}/{original_filename}"
    )

    # io.BytesIO wraps bytes in a file-like object
    # MinIO client expects a file-like object, not raw bytes
    file_stream = io.BytesIO(file_bytes)
    file_size = len(file_bytes)

    client.put_object(
        bucket_name=bucket,
        object_name=storage_path,
        data=file_stream,
        length=file_size,
        content_type=content_type,
    )

    return storage_path


def get_file_url(storage_path: str, expires_hours: int = 1) -> str:
    """
    Generates a pre-signed URL to download a file from MinIO.

    Pre-signed URL = temporary URL that lets anyone download
    the file without credentials. Expires after expires_hours.

    Used to return download links in API responses without
    exposing MinIO credentials to the client.
    """
    from datetime import timedelta

    client = get_minio_client()

    url = client.presigned_get_object(
        bucket_name=settings.minio_bucket_documents,
        object_name=storage_path,
        expires=timedelta(hours=expires_hours),
    )

    return url


# Supported file types and their MIME types
# Used to validate uploads and route to correct parser in Phase 3
SUPPORTED_FILE_TYPES = {
    # PDFs
    "application/pdf": "pdf",
    # Images — for OCR processing
    "image/jpeg": "image",
    "image/png": "image",
    "image/tiff": "image",
    "image/webp": "image",

    # Office documents
    "application/vnd.openxmlformats-officedocument"
    ".wordprocessingml.document": "word",
    "application/vnd.openxmlformats-officedocument"
    ".spreadsheetml.sheet": "excel",
    "application/vnd.openxmlformats-officedocument"
    ".presentationml.presentation": "powerpoint",
    "application/vnd.ms-excel": "excel",
    "application/msword": "word",
    #text docs
    # Plain text files — useful for testing and simple documents
    "text/plain": "text",
}

# Maximum file size: 50MB
# Large files cause memory issues and slow processing
# Phase 3 will add chunked upload for files > 50MB
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB