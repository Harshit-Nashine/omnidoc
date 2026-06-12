# ================================================================
# services/api/app/llm_service.py
# ================================================================
# LLM answer synthesis from retrieved chunks.
#
# WHY A SEPARATE FILE:
# Every LLM call must be timed and token-counted for cost tracking
# (MLOps requirement). Wrapping this in one place means every
# caller automatically gets metrics — no caller can forget to
# measure a model call.
#
# GRACEFUL DEGRADATION:
# If ANTHROPIC_API_KEY is empty, synthesize_answer() returns None
# instead of raising. The query endpoint falls back to returning
# raw chunks only. This lets the system work without an API key
# during development.
# ================================================================

import time
from dataclasses import dataclass
from anthropic import Anthropic
from services.api.app.config import settings


@dataclass
class LLMResult:
    """Result of an LLM call — always includes timing + token data."""
    answer: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


_client: Anthropic | None = None


def _get_client() -> Anthropic | None:
    """
    Returns a cached Anthropic client, or None if no API key set.
    Lazily initialized — avoids error at import time if key missing.
    """
    global _client

    if not settings.anthropic_api_key:
        return None

    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)

    return _client


def synthesize_answer(
    question: str,
    chunks: list[dict],
) -> LLMResult | None:
    """
    Synthesizes a natural language answer from retrieved chunks.

    WHY THIS WRAPPER MEASURES EVERYTHING:
    MLOps requirement — every LLM call must log token count and
    latency. By centralizing the call here, the query endpoint
    doesn't need to know about timing or token counting at all.

    Args:
        question: the user's natural language question
        chunks:   list of {text, document_id, page, score} dicts
                  from vector_store.query_vector_store()

    Returns:
        LLMResult with answer + metrics, or None if no API key
        configured (caller falls back to raw chunks).
    """
    client = _get_client()

    if client is None:
        return None

    # Build context from chunks — numbered so the model can cite sources
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[Source {i} — Document {chunk['document_id'][:8]}, "
            f"Page {chunk['page']}]\n{chunk['text']}"
        )
    context = "\n\n".join(context_parts)

    system_prompt = (
        "You are OmniDoc's document assistant. Answer the user's "
        "question using ONLY the provided sources below. "
        "Cite sources using [Source N] notation. "
        "If the sources don't contain enough information to answer, "
        "say so clearly — do not make up information."
    )

    user_message = (
        f"Sources:\n\n{context}\n\n"
        f"Question: {question}"
    )

    # ── Timing starts here ───────────────────────────────────────
    start_time = time.perf_counter()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
    except Exception as e:
        # API errors (bad key, rate limit, network) should not
        # crash the query — fall back to chunks-only response.
        # Latency is still recorded for the failed attempt.
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        print(f"LLM call failed: {e}")
        return LLMResult(
            answer=f"(LLM synthesis unavailable: {type(e).__name__})",
            input_tokens=0,
            output_tokens=0,
            latency_ms=latency_ms,
        )

    latency_ms = int((time.perf_counter() - start_time) * 1000)
    # ── Timing ends here ─────────────────────────────────────────

    answer_text = "".join(
        block.text for block in response.content
        if block.type == "text"
    )

    return LLMResult(
        answer=answer_text,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
        latency_ms=latency_ms,
    )