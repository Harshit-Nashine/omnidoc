## Component: FastAPI Gateway Skeleton
**Completed:** Phase 1

**What it does:**
Entry point for all API requests. On startup connects to all 4
databases and confirms they are reachable. Exposes two endpoints.

**Endpoints:**
- GET /        → returns API name, version, status
- GET /health  → pings PostgreSQL, MongoDB, Redis and returns status

**Inputs:** None (no auth yet — added in next step)

**Outputs:** JSON responses

**Dependencies:**
- PostgreSQL running on localhost:5432
- MongoDB running on localhost:27017
- Redis running on localhost:6379
- packages: fastapi, uvicorn, asyncpg, motor, redis, pydantic-settings

**Files:**
- services/api/app/main.py     — app instance, routes, lifespan
- services/api/app/config.py   — reads .env, typed settings object
- services/api/app/database.py — connection pools, ping functions

**Known limitations:**
- No authentication yet
- Runs locally only — not containerized yet
- .env uses localhost hosts — will change to service names when dockerized

---

## Component: PostgreSQL Schema
**Completed:** Phase 1

**What it does:**
Defines all database tables, indexes, row-level security policies,
and auto-update triggers for the OmniDoc platform.

**Tables created:**
- tenants        — one row per company/team using the platform
- users          — one row per user, scoped to a tenant
- refresh_tokens — JWT refresh tokens for session management

**Key design decisions:**
- UUID primary keys — unguessable, safe to expose in URLs
- tenant_id on every table from day one — never added retroactively
- Composite unique index on users(tenant_id, email) — same email
  allowed across different tenants, unique within one tenant
- RLS forced on all tables — DB blocks cross-tenant access even
  if application code has a bug
- updated_at trigger — automatically updated on every row change
- Soft deletes via is_active — never hard delete users or tenants

**Files:**
- infra/postgres/schema.sql  — full schema definition
- infra/postgres/init.sql    — extensions (uuid-ossp, pgcrypto)

**Known limitations:**
- Schema applied manually for now
- Phase 2 will add: documents, ingestion_jobs, query_cost_log tables

---

## Component: Auth System
**Completed:** Phase 2

**What it does:**
Complete authentication system with JWT tokens, bcrypt password
hashing, and tenant-scoped row level security.

**Endpoints:**
- POST /auth/register — creates tenant + first admin user atomically
- POST /auth/login    — returns access token (30min) + refresh token (7d)
- GET  /auth/me       — returns current user, requires valid token

**Files:**
- services/api/app/security.py      — password hashing + JWT utils
- services/api/app/schemas.py       — request/response Pydantic models
- services/api/app/auth_queries.py  — all auth SQL queries
- services/api/app/auth_routes.py   — HTTP route handlers
- services/api/app/middleware.py    — RLS tenant isolation middleware

**Security properties:**
- Passwords hashed with bcrypt (intentionally slow, brute-force resistant)
- JWTs signed with HS256 + SECRET_KEY
- Access tokens expire in 30 minutes
- Generic error messages (never reveal if email or password was wrong)
- RLS enforced at DB layer — not just application layer

**Known limitations:**
- Login finds user by email only — no tenant slug required yet
- Refresh token stored in JWT only — not yet persisted to DB
- Refresh token rotation endpoint not yet built


---

## Component: Document Parsing Pipeline
**Completed:** Phase 3

**What it does:**
Async pipeline that processes uploaded documents in the background.
Extracts text from PDFs and images, stores results in MinIO,
updates document status in PostgreSQL.

**Flow:**
POST /documents/upload → MinIO (raw file) → PostgreSQL (status: uploaded)
→ Celery task queued → worker downloads file → parser extracts text
→ extracted text saved to MinIO as .extracted.txt
→ PostgreSQL updated (status: processed)

**Parsers:**
- pdf_parser.py    — pdfplumber, handles multi-column + tables
- image_parser.py  — Tesseract OCR, English + Hindi
- router.py        — dispatches to correct parser by file_type

**Files:**
- services/api/app/parsers/pdf_parser.py
- services/api/app/parsers/image_parser.py
- services/api/app/parsers/router.py
- services/api/app/celery_app.py
- services/api/app/tasks.py

**Known limitations:**
- Audio (Whisper), Word, Excel, PowerPoint not yet implemented
- Scanned multi-page PDFs use image parser on first page only
- Celery uses --pool=solo on Windows (single worker process)

---

## Component: PII Scanner + Compliance Pipeline
**Completed:** Phase 3 Part 2

**What it does:**
Scans extracted document text for personally identifiable
information using Microsoft Presidio. Routes flagged documents
to MongoDB quarantine. Updates compliance_status in PostgreSQL.

**PII entities detected:**
IN_AADHAAR, IN_PAN, PHONE_NUMBER, EMAIL_ADDRESS,
CREDIT_CARD, IBAN_CODE, PERSON, LOCATION

**Compliance status rules:**
- clean       → no PII found, ready for approval
- flagged     → PII detected, stored in MongoDB quarantine
- quarantined → text too short (< 50 chars), unreadable doc

**Files:**
- services/api/app/parsers/pii_scanner.py
- services/api/app/tasks.py (steps 6-8 added)

**Known limitations:**
- IN_AADHAAR and IN_PAN detection requires specific format
- PERSON detection has false positives on product/company names
- Hindi PII not yet detected (Presidio English model only)


---

## Component: RAG Pipeline (Embedding + Retrieval)
**Completed:** Phase 4

**What it does:**
Embeds approved documents into ChromaDB and allows natural
language search across them with similarity scoring.

**Flow:**
Document approved → chunked (400 tokens, 80 overlap) →
embedded (multilingual-mpnet-base-v2, 768-dim) →
stored in per-tenant ChromaDB collection →
query embeds question → cosine similarity search →
returns top-N chunks with source document_id, page, score

**New endpoints:**
- POST /documents/{id}/approve — clean docs only, triggers embedding
- POST /query/                 — natural language search

**Files:**
- services/api/app/vector_store.py — ChromaDB abstraction, embedding
- services/api/app/chunker.py      — document chunking logic
- services/api/app/query_routes.py — search endpoint
- services/api/app/tasks.py        — embed_document task added

**Key design decisions:**
- One ChromaDB collection per tenant — isolation beyond RLS
- paraphrase-multilingual-mpnet-base-v2 — supports Hindi + English
- Cosine similarity, normalized embeddings
- 400-token chunks with 80-token overlap

**Known limitations:**
- No LLM synthesis yet — returns raw chunks (Phase 5 adds this)
- ChromaDB local persistent storage only (./chroma_data/)
- No reranking yet (MMR/cross-encoder planned for Phase 5)
---

## Component: LLM Synthesis + Cost Tracking
**Completed:** Phase 5

**What it does:**
Synthesizes natural language answers from retrieved chunks using
Claude. Logs token usage and latency for every query to enable
per-user/per-tenant cost dashboards.

**Flow:**
Retrieve chunks (timed) → build context → call Claude with
numbered sources → return answer + chunks → log to query_cost_log

**Graceful degradation:**
If ANTHROPIC_API_KEY is empty or invalid, answer=None, chunks
still returned, llm fields = 0 in cost log. System remains fully
functional in retrieval-only mode.

**Files:**
- services/api/app/llm_service.py   — Anthropic client, timing
- services/api/app/cost_queries.py  — cost log insert
- services/api/app/query_routes.py  — updated with full pipeline
- infra/postgres/schema.sql         — query_cost_log table

**Known limitations:**
- No LLM response caching — identical questions re-call the API
- claude-haiku-4-5 hardcoded — not configurable yet
- No streaming response (full answer returned at once)
---

## Component: Observability Stack
**Completed:** Phase 6

**What it does:**
Full metrics collection and visualization. Prometheus scrapes
the API every 15 seconds. Grafana visualizes trends over time.

**Grafana Dashboard: OmniDoc Overview**
- Request Volume by Endpoint   — total HTTP requests per route
- Average Latency per Endpoint — request duration per route
- Documents Uploaded           — count by file_type
- RAG Query Volume             — total semantic queries
- RAG Retrieval Latency        — vector search duration
- Token Usage                  — LLM input/output tokens

**Metrics exposed at /metrics:**
- omnidoc_http_requests_total
- omnidoc_http_request_duration_seconds
- omnidoc_documents_uploaded_total
- omnidoc_rag_queries_total
- omnidoc_rag_retrieval_duration_seconds
- omnidoc_rag_tokens_total
- omnidoc_documents_in_knowledge_base

**Access:**
- Prometheus: http://localhost:9090
- Grafana:    http://localhost:3000 (admin/admin)
- Metrics:    http://localhost:8000/metrics

**Files:**
- services/api/app/metrics.py         — metric definitions
- services/api/app/main.py            — middleware + /metrics endpoint
- infra/prometheus/prometheus.yml     — scrape config
- docker-compose.yml                  — prometheus + grafana services