# ================================================================
# tests/test_chunker.py
# ================================================================
# Tests for the document chunker.
# No database or external services needed.
# ================================================================

import pytest
from services.api.app.chunker import chunk_document, _estimate_tokens


def test_estimate_tokens_basic():
    """Token estimation returns reasonable value."""
    text = "This is a test sentence with some words."
    tokens = _estimate_tokens(text)
    assert tokens > 0
    assert tokens < len(text)


def test_chunk_empty_text_returns_empty():
    """Empty text produces no chunks."""
    chunks = chunk_document(full_text="", pages=[""])
    assert len(chunks) == 0


def test_chunk_short_text_single_chunk():
    """Short text fits in one chunk."""
    text = "This is a short document."
    chunks = chunk_document(full_text=text, pages=[text])
    assert len(chunks) == 1
    assert chunks[0].text == text


def test_chunk_assigns_page_numbers():
    """Chunks have correct page numbers."""
    pages = ["Page one content.", "Page two content."]
    chunks = chunk_document(
        full_text=" ".join(pages),
        pages=pages,
    )
    assert all(chunk.page >= 1 for chunk in chunks)


def test_chunk_ids_are_sequential():
    """Chunk IDs start at 0 and are sequential."""
    text = " ".join(["word"] * 500)
    chunks = chunk_document(full_text=text, pages=[text])
    ids = [c.chunk_id for c in chunks]
    assert ids == list(range(len(ids)))


def test_chunk_long_document_creates_multiple_chunks():
    """Long document is split into multiple chunks."""
    # Use paragraphs separated by double newlines so the chunker
    # can split on paragraph boundaries correctly
    paragraphs = ["This is paragraph number {}.".format(i) * 20
                  for i in range(50)]
    long_text = "\n\n".join(paragraphs)
    chunks = chunk_document(
        full_text=long_text,
        pages=[long_text],
        chunk_size=100,
    )
    assert len(chunks) > 1


def test_chunk_text_not_empty():
    """No chunk should have empty text."""
    text = "\n\n".join([
        "First paragraph with some content here.",
        "Second paragraph with different content.",
        "Third paragraph to ensure multiple chunks.",
    ] * 10)
    chunks = chunk_document(full_text=text, pages=[text])
    assert all(len(chunk.text.strip()) > 0 for chunk in chunks)