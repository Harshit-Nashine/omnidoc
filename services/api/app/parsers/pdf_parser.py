# ================================================================
# services/api/app/parsers/pdf_parser.py
# ================================================================
# Extracts text from PDF files using pdfplumber.
#
# WHY PDFPLUMBER OVER PYPDF OR PYMUPDF:
# pdfplumber preserves reading order in multi-column PDFs and
# extracts tables as structured data. PyPDF loses column ordering.
# PyMuPDF is faster but pdfplumber is more accurate for complex
# layouts — accuracy matters more than speed for document intelligence.
# ================================================================

import io
from dataclasses import dataclass

# pdfplumber: extracts text with layout coordinates
# chosen over PyMuPDF because it handles multi-column PDFs
# and tables more accurately for our use case
import pdfplumber


@dataclass
class ParsedDocument:
    """
    Result of parsing any document type.
    Consistent structure regardless of input type —
    the rest of the pipeline only deals with this class.
    """
    # Full extracted text — all pages joined
    full_text: str

    # Text split by page — useful for page-level citations
    pages: list[str]

    # Total number of pages
    page_count: int

    # Metadata extracted from the document
    metadata: dict

    # Which parser produced this result
    parser_used: str


def parse_pdf(file_bytes: bytes) -> ParsedDocument:
    """
    Extracts text from a PDF file.

    Handles:
    - Single column text
    - Multi-column layouts (pdfplumber preserves reading order)
    - Tables (extracted as text rows)
    - Scanned PDFs with embedded text layer

    Note: scanned PDFs with NO text layer return empty text.
    Those are routed to OCR parser instead (handled in router).

    Args:
        file_bytes: raw PDF file bytes from MinIO

    Returns:
        ParsedDocument with extracted text and metadata
    """
    pages_text = []
    metadata = {}

    # io.BytesIO wraps bytes as a file-like object
    # pdfplumber expects a file path or file-like object
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:

        # Extract document-level metadata
        # pdfplumber reads PDF metadata headers if present
        if pdf.metadata:
            metadata = {
                k: str(v) for k, v in pdf.metadata.items()
                if v is not None
            }

        metadata["page_count"] = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = ""

            # extract_text() returns text in reading order
            # layout=True preserves column structure
            text = page.extract_text(layout=True)

            if text:
                page_text += text.strip()

            # Extract tables separately — tables often contain
            # key data that plain text extraction misses or garbles
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    for row in table:
                        # Filter None cells and join with tab separator
                        clean_row = [
                            cell.strip() if cell else ""
                            for cell in row
                        ]
                        page_text += "\n" + "\t".join(clean_row)

            pages_text.append(page_text)

    # Join all pages with clear page separator
    # The separator helps downstream chunking know page boundaries
    full_text = "\n\n--- PAGE BREAK ---\n\n".join(pages_text)

    return ParsedDocument(
        full_text=full_text,
        pages=pages_text,
        page_count=len(pages_text),
        metadata=metadata,
        parser_used="pdfplumber",
    )


def is_scanned_pdf(file_bytes: bytes) -> bool:
    """
    Detects if a PDF is scanned (image-only, no text layer).
    Scanned PDFs need OCR — text extraction returns nothing.

    Returns True if PDF has no extractable text on any page.
    """
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text and text.strip():
                # Found real text — not a scanned PDF
                return False

    # No text found on any page — it is scanned
    return True