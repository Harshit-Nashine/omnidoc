# ================================================================
# services/api/app/metrics.py
# ================================================================
# Prometheus metrics definitions.
#
# WHY PROMETHEUS:
# Industry standard for metrics collection. Pull-based —
# Prometheus scrapes /metrics every 15s, no code needs to push.
# Grafana then visualizes these metrics over time.
#
# METRIC TYPES USED:
# Counter   — only increases (total requests, total queries)
# Histogram — distribution of values (latency buckets)
# Gauge     — can go up or down (active connections)
# ================================================================

from prometheus_client import Counter, Histogram, Gauge

# ── HTTP request metrics ─────────────────────────────────────────
http_requests_total = Counter(
    "omnidoc_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "omnidoc_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
)

# ── Document pipeline metrics ────────────────────────────────────
documents_uploaded_total = Counter(
    "omnidoc_documents_uploaded_total",
    "Total documents uploaded",
    ["tenant_id", "file_type"],
)

documents_processed_total = Counter(
    "omnidoc_documents_processed_total",
    "Total documents processed",
    ["tenant_id", "status"],  # status: processed/failed
)

documents_compliance_total = Counter(
    "omnidoc_documents_compliance_total",
    "Documents by compliance status",
    ["tenant_id", "compliance_status"],
)

# ── RAG query metrics ────────────────────────────────────────────
rag_queries_total = Counter(
    "omnidoc_rag_queries_total",
    "Total RAG queries",
    ["tenant_id"],
)

rag_retrieval_duration_seconds = Histogram(
    "omnidoc_rag_retrieval_duration_seconds",
    "Vector retrieval latency in seconds",
    ["tenant_id"],
)

rag_llm_duration_seconds = Histogram(
    "omnidoc_rag_llm_duration_seconds",
    "LLM synthesis latency in seconds",
    ["tenant_id"],
)

rag_tokens_total = Counter(
    "omnidoc_rag_tokens_total",
    "Total tokens used in LLM calls",
    ["tenant_id", "token_type"],  # token_type: input/output
)

# ── Active resources gauge ───────────────────────────────────────
documents_in_knowledge_base = Gauge(
    "omnidoc_documents_in_knowledge_base",
    "Number of completed/approved documents per tenant",
    ["tenant_id"],
)