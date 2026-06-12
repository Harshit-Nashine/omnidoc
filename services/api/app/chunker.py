# ================================================================
# services/api/app/chunker.py
# ================================================================
# Splits extracted document text into chunks for embedding.
#
# WHY CHUNKING:
# Embedding models have a token limit (~512 tokens for our model).
# A 50-page PDF has ~25,000 tokens — we cannot embed it as one unit.
# We split it into overlapping windows so:
#   1. Each chunk fits in the model's context window
#   2. Overlap ensures sentences at chunk boundaries are not lost
#   3. Retrieval finds the specific relevant section, not whole doc
#
# CHUNK STRATEGY:
# Window size:  400 tokens  (leaves buffer below 512 limit)
# Overlap:      80 tokens   (~20% overlap preserves context)
# Split on:     paragraphs first, then sentences, then tokens
# ================================================================

import re
from dataclasses import dataclass


@dataclass
class DocumentChunk:
    """One chunk of a document ready for embedding."""
    chunk_id: int
    text: str
    page: int
    token_count: int


def _estimate_tokens(text: str) -> int:
    """
    Estimates token count without loading a tokenizer.
    Rule of thumb: 1 token ≈ 4 characters for English text.
    Fast and accurate enough for chunking purposes.
    For exact counts we use tiktoken in cost tracking.
    """
    return len(text) // 4


def _split_into_sentences(text: str) -> list[str]:
    """
    Splits text into sentences using punctuation patterns.
    More reliable than splitting on newlines alone.
    """
    # Split on sentence-ending punctuation followed by space/newline
    sentences = re.split(r'(?<=[.!?])\s+', text)
    # Filter empty strings
    return [s.strip() for s in sentences if s.strip()]


def chunk_document(
    full_text: str,
    pages: list[str],
    chunk_size: int = 400,
    chunk_overlap: int = 80,
) -> list[DocumentChunk]:
    """
    Splits document text into overlapping chunks.

    Strategy:
        1. Split by page first (preserves page attribution)
        2. Within each page, split by paragraph
        3. Build chunks by accumulating sentences until chunk_size
        4. Overlap by carrying last chunk_overlap tokens forward

    Args:
        full_text:     complete document text (used as fallback)
        pages:         text split by page from parser
        chunk_size:    target tokens per chunk (default 400)
        chunk_overlap: tokens to overlap between chunks (default 80)

    Returns:
        List of DocumentChunk objects ready for embedding
    """
    chunks = []
    chunk_id = 0

    # Process page by page to preserve page numbers in metadata
    for page_num, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue

        # Split page into paragraphs
        paragraphs = [
            p.strip()
            for p in page_text.split("\n\n")
            if p.strip()
        ]

        current_chunk_text = ""
        current_tokens = 0

        for paragraph in paragraphs:
            para_tokens = _estimate_tokens(paragraph)

            # If single paragraph exceeds chunk_size, split it
            if para_tokens > chunk_size:
                sentences = _split_into_sentences(paragraph)
                for sentence in sentences:
                    sent_tokens = _estimate_tokens(sentence)

                    if current_tokens + sent_tokens > chunk_size:
                        # Save current chunk if it has content
                        if current_chunk_text.strip():
                            chunks.append(DocumentChunk(
                                chunk_id=chunk_id,
                                text=current_chunk_text.strip(),
                                page=page_num,
                                token_count=current_tokens,
                            ))
                            chunk_id += 1

                            # Keep overlap from end of current chunk
                            overlap_text = _get_overlap(
                                current_chunk_text, chunk_overlap
                            )
                            current_chunk_text = overlap_text + " " + sentence
                            current_tokens = _estimate_tokens(current_chunk_text)
                        else:
                            current_chunk_text = sentence
                            current_tokens = sent_tokens
                    else:
                        current_chunk_text += " " + sentence
                        current_tokens += sent_tokens
            else:
                # Paragraph fits — check if adding it exceeds limit
                if current_tokens + para_tokens > chunk_size:
                    # Save current chunk
                    if current_chunk_text.strip():
                        chunks.append(DocumentChunk(
                            chunk_id=chunk_id,
                            text=current_chunk_text.strip(),
                            page=page_num,
                            token_count=current_tokens,
                        ))
                        chunk_id += 1

                        overlap_text = _get_overlap(
                            current_chunk_text, chunk_overlap
                        )
                        current_chunk_text = overlap_text + " " + paragraph
                        current_tokens = _estimate_tokens(current_chunk_text)
                else:
                    current_chunk_text += "\n\n" + paragraph
                    current_tokens += para_tokens

        # Save remaining text from this page
        if current_chunk_text.strip():
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                text=current_chunk_text.strip(),
                page=page_num,
                token_count=current_tokens,
            ))
            chunk_id += 1

    # Fallback: if no chunks created, chunk the full text directly
    if not chunks and full_text.strip():
        words = full_text.split()
        words_per_chunk = chunk_size * 4 // 5  # rough word estimate

        for i in range(0, len(words), words_per_chunk - chunk_overlap):
            chunk_words = words[i:i + words_per_chunk]
            if chunk_words:
                text = " ".join(chunk_words)
                chunks.append(DocumentChunk(
                    chunk_id=chunk_id,
                    text=text,
                    page=1,
                    token_count=_estimate_tokens(text),
                ))
                chunk_id += 1

    return chunks


def _get_overlap(text: str, overlap_tokens: int) -> str:
    """
    Returns the last overlap_tokens worth of text.
    Used to carry context forward between chunks.
    """
    # Approximate characters from tokens
    overlap_chars = overlap_tokens * 4
    return text[-overlap_chars:] if len(text) > overlap_chars else text