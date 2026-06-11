# ================================================================
# services/api/app/parsers/router.py
# ================================================================
# Routes each document to the correct parser based on file_type.
# This is the only file that knows which parser handles what.
# All other code calls parse_document() — not individual parsers.
#
# WHY A ROUTER:
# When we add Whisper (audio) and LibreOffice (office docs) in
# Phase 4, we add them here only. No other file changes.
# ================================================================

from services.api.app.parsers.pdf_parser import (
    parse_pdf,
    is_scanned_pdf,
    ParsedDocument,
)
from services.api.app.parsers.image_parser import parse_image


def parse_document(
    file_bytes: bytes,
    file_type: str,
    filename: str = "",
) -> ParsedDocument:
    """
    Routes a document to the correct parser based on file_type.

    file_type comes from the documents table — set during upload
    by matching MIME type against SUPPORTED_FILE_TYPES.

    Supported types right now:
        pdf   → pdfplumber (or OCR if scanned)
        image → Tesseract OCR

    Types added in Phase 4:
        audio      → Whisper
        word       → LibreOffice → text
        excel      → LibreOffice → text
        powerpoint → LibreOffice → text

    Args:
        file_bytes: raw file bytes downloaded from MinIO
        file_type:  one of: pdf, image, audio, word, excel, powerpoint
        filename:   original filename for metadata

    Returns:
        ParsedDocument with extracted text

    Raises:
        ValueError if file_type is not supported yet
    """

    if file_type == "pdf":
        # Check if this is a scanned PDF (no text layer)
        # Scanned PDFs need OCR, not text extraction
        if is_scanned_pdf(file_bytes):
            # Treat as image — OCR every page
            # For now we OCR the first page as a single image
            # Full multi-page scanned PDF support added in Phase 4
            return parse_image(file_bytes, filename)
        else:
            return parse_pdf(file_bytes)

    elif file_type == "image":
        return parse_image(file_bytes, filename)
    elif file_type == "text":
        # Plain text — no parsing needed, just wrap in ParsedDocument
        text = file_bytes.decode("utf-8", errors="ignore")
        return ParsedDocument(
            full_text=text,
            pages=[text],
            page_count=1,
            metadata={"filename": filename},
            parser_used="plaintext",
        )
    else:
        # Unsupported types return a placeholder
        # Will be replaced in Phase 4 when Whisper + LibreOffice added
        raise ValueError(
            f"Parser for file_type='{file_type}' not yet implemented. "
            f"Supported: pdf, image. "
            f"Coming in Phase 4: audio, word, excel, powerpoint."
        )
        