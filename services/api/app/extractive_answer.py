# ================================================================
# services/api/app/extractive_answer.py
# ================================================================
# Free, offline answer generation for the query endpoint.
#
# HOW IT WORKS:
# 1. Split each retrieved passage into sentences
# 2. Score each sentence by how many question words it contains
# 3. Return the best sentences, each tagged with its source number
#
# WHY NOT AN LLM HERE:
# No API key, no cost, no GPU, no model download. It also cannot
# invent facts, because every sentence is copied from an approved
# document. A generative model can be added later behind the same
# function signature.
# ================================================================

import re
import time
from dataclasses import dataclass


# Common words that carry no meaning for matching
STOPWORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "what", "when", "where", "which", "who", "how", "why", "does",
    "did", "was", "were", "has", "have", "had", "this", "that",
    "with", "from", "they", "them", "their", "there", "about",
    "into", "your", "our", "its", "will", "would", "should", "could",
    "tell", "give", "show", "many", "much", "any", "also",
}

NOT_FOUND_MESSAGE = (
    "I couldn't find a direct answer to this in your approved documents. "
    "The closest matching passages are shown below."
)


@dataclass
class ExtractiveAnswer:
    """Same field names as the LLM result, so query_routes needs no other change."""
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0


def _terms(text: str) -> set:
    """
    Lowercase words of 3+ letters, minus stopwords.
    Words are matched as whole tokens, so 'leave' does not match 'leaves'
    by accident. Trade-off: plural forms are missed, which is acceptable
    for a first version.
    """
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if len(w) >= 3 and w not in STOPWORDS}


def _sentences(text: str) -> list[str]:
    """
    Splits on sentence punctuation and line breaks. Lines from policy
    documents often have no full stop, so line breaks count as boundaries.
    Fragments under 15 characters are skipped (headings, bullet labels).
    """
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 15]


def build_extractive_answer(question: str, chunks: list[dict]) -> ExtractiveAnswer:
    """
    Builds an answer from the best-matching sentences in the chunks.

    chunks: the filtered retrieval results, in the same order as the
            source cards on screen, so [1] refers to the first source card.

    Always returns an ExtractiveAnswer. If nothing matches, the answer
    is a clear "not found" message rather than a guess.
    """
    start = time.perf_counter()

    question_terms = _terms(question)
    if not question_terms or not chunks:
        return ExtractiveAnswer(
            answer=NOT_FOUND_MESSAGE,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    # Score every sentence that shares at least one word with the question
    scored = []
    for source_no, chunk in enumerate(chunks, start=1):
        for sentence in _sentences(chunk["text"]):
            overlap = len(question_terms & _terms(sentence))
            if overlap > 0:
                # Sort key: more matched words first, then stronger source
                scored.append((overlap, chunk["score"], source_no, sentence))

    if not scored:
        return ExtractiveAnswer(
            answer=NOT_FOUND_MESSAGE,
            latency_ms=int((time.perf_counter() - start) * 1000),
        )

    scored.sort(key=lambda s: (s[0], s[1]), reverse=True)

    # Take up to 3 distinct sentences, keeping their source numbers
    picked = []
    seen = set()
    for _, _, source_no, sentence in scored:
        if sentence in seen:
            continue
        seen.add(sentence)
        picked.append(f"{sentence} [{source_no}]")
        if len(picked) == 3:
            break

    return ExtractiveAnswer(
        answer=" ".join(picked),
        latency_ms=int((time.perf_counter() - start) * 1000),
    )