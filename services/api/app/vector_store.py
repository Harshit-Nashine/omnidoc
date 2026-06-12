# ================================================================
# services/api/app/vector_store.py
# ================================================================
# ChromaDB vector store — stores and retrieves document embeddings.
#
# WHY CHROMADB:
# Local, free, no API key needed. Perfect for development.
# Abstract retriever interface means we can swap to Pinecone
# or Qdrant in production without changing any other file.
#
# ABSTRACT INTERFACE RULE:
# Nothing outside this file imports ChromaDB directly.
# All other code calls functions defined here.
# To swap vector stores: rewrite this file only.
#
# STORAGE:
# ChromaDB persists data to disk at ./chroma_data/
# This folder is created automatically on first run.
# Add chroma_data/ to .gitignore — it is local data, not code.
# ================================================================

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from services.api.app.config import settings as app_settings


# ── Embedding model ─────────────────────────────────────────────
# paraphrase-multilingual-mpnet-base-v2:
#   - 278M parameters
#   - Supports 50+ languages including Hindi
#   - 768-dimensional embeddings
#   - Downloaded once to venv cache (~420MB)
#
# Why this model over OpenAI embeddings:
#   - Free — no API cost per document
#   - Local — no data leaves your machine
#   - Fine-tuneable — we add LoRA in Phase 5
#   - Multilingual — handles Hindi + English documents
EMBEDDING_MODEL_NAME = (
    "paraphrase-multilingual-mpnet-base-v2"
)

# Load model once at module level — loading takes ~3 seconds
# Loading per request would make every query 3 seconds slower
print(f"Loading embedding model: {EMBEDDING_MODEL_NAME}")
_embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
print("Embedding model loaded successfully.")


# ── ChromaDB client ─────────────────────────────────────────────
# PersistentClient stores data to disk — survives restarts
# Path: ./chroma_data/ inside D:\omnidoc
_chroma_client = chromadb.PersistentClient(
    path="./chroma_data",
    settings=Settings(
        # anonymized_telemetry=False: disable ChromaDB sending
        # anonymous usage stats to their servers
        anonymized_telemetry=False,
    ),
)


def get_or_create_collection(tenant_id: str):
    """
    Gets or creates a ChromaDB collection for a tenant.

    WHY ONE COLLECTION PER TENANT:
    ChromaDB collections are isolated namespaces.
    Using one collection per tenant means vector searches
    are automatically scoped — tenant A cannot retrieve
    tenant B's document chunks even without filtering.
    This is defense in depth on top of PostgreSQL RLS.

    Collection name format: tenant_{tenant_id_without_hyphens}
    ChromaDB collection names cannot contain hyphens.
    """
    # Remove hyphens — ChromaDB collection names are alphanumeric
    safe_id = tenant_id.replace("-", "")
    collection_name = f"tenant_{safe_id}"

    collection = _chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={
            "tenant_id": tenant_id,
            # cosine distance is standard for semantic similarity
            # documents with similar meaning have high cosine similarity
            "hnsw:space": "cosine",
        },
    )

    return collection


def embed_text(text: str) -> list[float]:
    """
    Converts text to a 768-dimensional embedding vector.
    Used for both indexing documents and embedding queries.
    Same model for both — consistency is critical.
    """
    embedding = _embedding_model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Batch embeds multiple texts — much faster than one at a time.
    Used during document ingestion to embed all chunks at once.
    """
    embeddings = _embedding_model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,          # process 32 chunks at a time
        show_progress_bar=False,
    )
    return embeddings.tolist()


def add_chunks_to_store(
    tenant_id: str,
    document_id: str,
    chunks: list[dict],
) -> int:
    """
    Adds document chunks to the vector store.

    Each chunk dict must have:
        text     — the chunk text to embed
        chunk_id — unique identifier within the document
        page     — page number (0 if not applicable)

    Returns number of chunks added.
    """
    collection = get_or_create_collection(tenant_id)

    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_texts(texts)

    # Build IDs and metadata for each chunk
    # IDs must be unique across the entire collection
    ids = [
        f"{document_id}_chunk_{chunk['chunk_id']}"
        for chunk in chunks
    ]

    metadatas = [
        {
            "document_id": document_id,
            "tenant_id": tenant_id,
            "chunk_id": chunk["chunk_id"],
            "page": chunk.get("page", 0),
            "text": chunk["text"][:1000],  # store preview in metadata
        }
        for chunk in chunks
    ]

    # upsert = insert or update if ID already exists
    # Safe to call multiple times — idempotent
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    return len(chunks)


def query_vector_store(
    tenant_id: str,
    query_text: str,
    n_results: int = 10,
) -> list[dict]:
    """
    Searches the vector store for chunks similar to query_text.

    Returns top n_results chunks ranked by cosine similarity.
    Only searches within the tenant's collection — cross-tenant
    search is impossible by design (separate collections).

    Returns list of dicts with:
        text        — the chunk text
        document_id — which document this came from
        page        — page number
        score       — similarity score (higher = more similar)
    """
    collection = get_or_create_collection(tenant_id)

    # Check collection has documents
    if collection.count() == 0:
        return []

    # Embed the query using the same model as document chunks
    query_embedding = embed_text(query_text)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    # Format results into clean dicts
    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        metadata = results["metadatas"][0][i]
        distance = results["distances"][0][i]

        # Convert cosine distance to similarity score
        # distance 0 = identical, distance 2 = opposite
        # similarity 1 = identical, similarity 0 = opposite
        similarity = 1 - (distance / 2)

        chunks.append({
            "text": doc,
            "document_id": metadata["document_id"],
            "page": metadata.get("page", 0),
            "score": round(similarity, 4),
        })

    # Sort by score descending — most relevant first
    chunks.sort(key=lambda x: x["score"], reverse=True)

    return chunks