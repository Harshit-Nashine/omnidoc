# ================================================================
# services/api/app/ml_tracking.py
# ================================================================
# MLflow experiment tracking for embedding model evaluation.
#
# WHY MLFLOW:
# Every time we embed documents or evaluate retrieval quality,
# we want to record: which model was used, what parameters,
# what metrics (retrieval accuracy, latency). MLflow lets us
# compare runs and roll back to a better model if quality drops.
#
# WHAT WE TRACK:
# - Model name and version
# - Embedding dimensions
# - Number of documents embedded
# - Average chunks per document
# - Retrieval latency benchmarks
# - RAGAS-style quality scores (added in later iteration)
# ================================================================

import mlflow
import mlflow.sklearn
from datetime import datetime
from services.api.app.config import settings


def setup_mlflow():
    """
    Configures MLflow tracking URI and experiment.
    Called once on application startup.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)
    print(f"MLflow tracking: {settings.mlflow_tracking_uri}")
    print(f"MLflow experiment: {settings.mlflow_experiment_name}")


def log_embedding_run(
    model_name: str,
    document_count: int,
    total_chunks: int,
    avg_retrieval_latency_ms: float,
    embedding_dim: int = 768,
    notes: str = "",
) -> str:
    """
    Logs one embedding run to MLflow.

    Call this after a batch of documents is embedded to record
    the model performance at that point in time.

    Args:
        model_name:              name of the embedding model used
        document_count:          how many docs were embedded this run
        total_chunks:            total chunks across all documents
        avg_retrieval_latency_ms: average query latency in ms
        embedding_dim:           dimensionality of embeddings
        notes:                   any free-text notes for this run

    Returns:
        MLflow run ID for reference
    """
    with mlflow.start_run(
        run_name=f"embed_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ) as run:
        # Log parameters — what model and settings were used
        mlflow.log_params({
            "model_name": model_name,
            "embedding_dim": embedding_dim,
            "notes": notes or "auto-logged",
        })

        # Log metrics — how well did it perform
        mlflow.log_metrics({
            "document_count": document_count,
            "total_chunks": total_chunks,
            "avg_chunks_per_doc": (
                total_chunks / document_count
                if document_count > 0 else 0
            ),
            "avg_retrieval_latency_ms": avg_retrieval_latency_ms,
        })

        # Log a tag for easy filtering in MLflow UI
        mlflow.set_tags({
            "stage": "embedding",
            "model_type": "sentence_transformer",
        })

        return run.info.run_id


def log_query_metrics(
    question: str,
    chunks_retrieved: int,
    retrieval_latency_ms: int,
    top_score: float,
) -> str:
    """
    Logs one query evaluation to MLflow.
    Tracks retrieval quality over time — if scores drop,
    it signals the embedding model needs retraining.

    Returns MLflow run ID.
    """
    with mlflow.start_run(
        run_name=f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ) as run:
        mlflow.log_params({
            "question_length": len(question),
            "n_results_requested": chunks_retrieved,
        })

        mlflow.log_metrics({
            "chunks_retrieved": chunks_retrieved,
            "retrieval_latency_ms": retrieval_latency_ms,
            "top_similarity_score": top_score,
        })

        mlflow.set_tags({"stage": "retrieval"})

        return run.info.run_id