# ================================================================
# services/api/app/cost_queries.py
# ================================================================
# Inserts rows into query_cost_log — one per RAG query.
# ================================================================

import uuid
from asyncpg import Pool


async def log_query_cost(
    pool: Pool,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    question: str,
    chunks_retrieved: int,
    retrieval_latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    llm_latency_ms: int,
    total_latency_ms: int,
) -> None:
    """
    Records cost/performance metrics for one query.
    Called at the end of every POST /query/ request — success or
    LLM-disabled fallback both log a row (llm fields = 0 if disabled).
    """
    await pool.execute(
        """
        INSERT INTO query_cost_log (
            tenant_id, user_id, question, chunks_retrieved,
            retrieval_latency_ms, input_tokens, output_tokens,
            llm_latency_ms, total_latency_ms
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        tenant_id,
        user_id,
        question,
        chunks_retrieved,
        retrieval_latency_ms,
        input_tokens,
        output_tokens,
        llm_latency_ms,
        total_latency_ms,
    )