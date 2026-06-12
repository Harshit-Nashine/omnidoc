# ================================================================
# services/api/app/query_routes.py
# ================================================================
# Natural language query endpoint.
# Users ask questions — we find relevant document chunks and
# return them with source citations.
#
# Phase 4 returns raw retrieved chunks (no LLM yet).
# Phase 5 adds LLM to generate a synthesized answer.
# This lets us verify retrieval quality before adding LLM cost.
# ================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
import uuid

from services.api.app.database import get_postgresql_pool
from services.api.app.auth_routes import get_current_user
from services.api.app.vector_store import query_vector_store


router = APIRouter(prefix="/query", tags=["Query"])


class QueryRequest(BaseModel):
    """Input: natural language question."""
    question: str
    n_results: int = 5   # how many chunks to return


class ChunkResult(BaseModel):
    """One retrieved document chunk with source info."""
    text: str
    document_id: str
    page: int
    score: float


class QueryResponse(BaseModel):
    """Response from the query endpoint."""
    question: str
    chunks: list[ChunkResult]
    total_chunks_searched: int


@router.post("/", response_model=QueryResponse)
async def query_documents(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
    pool=Depends(get_postgresql_pool),
):
    """
    Searches the knowledge base for chunks relevant to the question.

    Only searches documents that are:
    - Approved (compliance_status = approved)
    - Completed (processing_status = completed)
    - Owned by the current tenant

    Returns top-n chunks ranked by semantic similarity.
    Each chunk includes the source document ID and page number.
    """
    if not body.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    tenant_id = str(current_user["tenant_id"])

    # Check how many completed documents exist for this tenant
    row = await pool.fetchrow(
        """
        SELECT COUNT(*) as count
        FROM documents
        WHERE tenant_id = $1
          AND compliance_status = 'approved'
          AND processing_status = 'completed'
        """,
        uuid.UUID(tenant_id),
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

    # Search vector store
    results = query_vector_store(
        tenant_id=tenant_id,
        query_text=body.question,
        n_results=body.n_results,
    )

    chunks = [
        ChunkResult(
            text=r["text"],
            document_id=r["document_id"],
            page=r["page"],
            score=r["score"],
        )
        for r in results
    ]

    return QueryResponse(
        question=body.question,
        chunks=chunks,
        total_chunks_searched=total_docs,
    )