# ================================================================
# services/api/app/query_routes.py
# ================================================================
# Natural language query endpoint.
#
# Flow:
#   1. Retrieve relevant chunks (ChromaDB)         — timed
#   2. Synthesize answer from chunks (LLM)         — timed
#   3. Log cost/performance to query_cost_log
#   4. Return answer + source chunks
#
# If ANTHROPIC_API_KEY is not set, step 2 is skipped and
# answer=None — chunks are still returned.
# ================================================================

import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from services.api.app.database import get_postgresql_pool
from services.api.app.auth_routes import get_current_user
from services.api.app.vector_store import query_vector_store
from services.api.app.llm_service import synthesize_answer
from services.api.app.cost_queries import log_query_cost
from services.api.app.metrics import (
    rag_queries_total,
    rag_retrieval_duration_seconds,
    rag_llm_duration_seconds,
    rag_tokens_total,
)


router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    question: str
    n_results: int = 5


class ChunkResult(BaseModel):
    text: str
    document_id: str
    page: int
    score: float


class QueryResponse(BaseModel):
    question: str
    answer: Optional[str] = None
    chunks: list[ChunkResult]
    total_chunks_searched: int
    retrieval_latency_ms: int
    llm_latency_ms: int


@router.post("/", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Searches the knowledge base and synthesizes an answer.

    Only searches documents that are approved + completed,
    scoped to the current tenant.
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    tenant_id = uuid.UUID(str(current_user["tenant_id"]))
    user_id = uuid.UUID(str(current_user["id"]))

    # ── Overall timing starts ────────────────────────────────────
    overall_start = time.perf_counter()

    # Check there's anything to search
    row = await pool.fetchrow(
        """
        SELECT COUNT(*) as count
        FROM documents
        WHERE tenant_id = $1
          AND compliance_status = 'approved'
          AND processing_status = 'completed'
        """,
        tenant_id,
    )
    total_docs = row["count"] if row else 0

    if total_docs == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No documents in the knowledge base yet. "
                "Upload and approve documents first."
            ),
        )

    # ── Step 1: retrieval — timed ────────────────────────────────
    retrieval_start = time.perf_counter()
    results = query_vector_store(
        tenant_id=str(tenant_id),
        query_text=body.question,
        n_results=body.n_results,
    )
    retrieval_latency_ms = int((time.perf_counter() - retrieval_start) * 1000)

    chunks = [
        ChunkResult(
            text=r["text"],
            document_id=r["document_id"],
            page=r["page"],
            score=r["score"],
        )
        for r in results
    ]
    rag_queries_total.labels(tenant_id=str(tenant_id)).inc()
    rag_retrieval_duration_seconds.labels(
        tenant_id=str(tenant_id)
    ).observe(retrieval_latency_ms / 1000)
    # ── Step 2: LLM synthesis — timed internally ─────────────────
    answer = None
    input_tokens = 0
    output_tokens = 0
    llm_latency_ms = 0

    if chunks:
        llm_result = synthesize_answer(
            question=body.question,
            chunks=results,
        )
        if llm_result is not None:
            answer = llm_result.answer
            input_tokens = llm_result.input_tokens
            output_tokens = llm_result.output_tokens
            llm_latency_ms = llm_result.latency_ms

    total_latency_ms = int((time.perf_counter() - overall_start) * 1000)
    
    if llm_latency_ms > 0:
        rag_llm_duration_seconds.labels(
            tenant_id=str(tenant_id)
        ).observe(llm_latency_ms / 1000)
        rag_tokens_total.labels(
            tenant_id=str(tenant_id), token_type="input"
        ).inc(input_tokens)
        rag_tokens_total.labels(
            tenant_id=str(tenant_id), token_type="output"
        ).inc(output_tokens)
        
    # ── Step 3: log cost/performance ─────────────────────────────
    await log_query_cost(
        pool=pool,
        tenant_id=tenant_id,
        user_id=user_id,
        question=body.question,
        chunks_retrieved=len(chunks),
        retrieval_latency_ms=retrieval_latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        llm_latency_ms=llm_latency_ms,
        total_latency_ms=total_latency_ms,
    )

    return QueryResponse(
        question=body.question,
        answer=answer,
        chunks=chunks,
        total_chunks_searched=total_docs,
        retrieval_latency_ms=retrieval_latency_ms,
        llm_latency_ms=llm_latency_ms,
    )