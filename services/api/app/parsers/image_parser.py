# ================================================================
# services/api/app/parsers/image_parser.py
# ================================================================
# Extracts text from images using Tesseract OCR.
#
# WHY TESSERACT AS FALLBACK:
# Tesseract is production-ready for standard documents.
# Your custom PyTorch CNN (MTP project) will replace/supplement
# this in Phase 4 for Devanagari-heavy documents.
# For now, Tesseract handles Latin + Hindi adequately.
#
# TESSERACT MUST BE INSTALLED SEPARATELY:
# It is not a Python package — it is a system executable.
# Windows path: C:\Program Files\Tesseract-OCR\tesseract.exe
# ================================================================

import io
import os
from dataclasses import dataclass

# pytesseract: Python wrapper around Tesseract executable
# chosen over easyocr because Tesseract is faster on CPU
# and more accurate for printed (non-handwritten) text
import pytesseract
from PIL import Image

from services.api.app.parsers.pdf_parser import ParsedDocument


# Tell pytesseract where Tesseract is installed on Windows
# This must match your actual installation path
# If you installed to a different location, update this path
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
else:
    # If path not found, pytesseract will try system PATH
    # This handles Linux/Mac where Tesseract is in PATH
    print(
        f"Warning: Tesseract not found at {TESSERACT_PATH}. "
        f"Make sure Tesseract is installed and in PATH."
    )


def parse_image(file_bytes: bytes, filename: str = "") -> ParsedDocument:
    """
    Extracts text from an image file using Tesseract OCR.

    Supported formats: JPEG, PNG, TIFF, WebP
    Languages: English + Hindi (--lang eng+hin)
    Add more languages by installing Tesseract language packs.

    Args:
        file_bytes: raw image bytes from MinIO
        filename: original filename (used for metadata only)

    Returns:
        ParsedDocument with OCR-extracted text
    """
    # Open image from bytes using Pillow
    image = Image.open(io.BytesIO(file_bytes))

    # Convert to RGB if needed
    # Tesseract works best with RGB — not RGBA or grayscale
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    # image_to_string runs Tesseract on the image
    # lang="eng+hin" enables both English and Hindi recognition
    # config="--psm 3" = fully automatic page segmentation
    # psm 3 works for most documents — change to psm 6 for
    # single uniform blocks of text
    extracted_text = pytesseract.image_to_string(
        image,
        lang="eng+hin",
        config="--psm 3",
    )

    clean_text = extracted_text.strip()

    # Get image metadata
    metadata = {
        "width": image.width,
        "height": image.height,
        "mode": image.mode,
        "filename": filename,
        "page_count": 1,
    }

    return ParsedDocument(
        full_text=clean_text,
        pages=[clean_text],
        page_count=1,
        metadata=metadata,
        parser_used="tesseract",
    )