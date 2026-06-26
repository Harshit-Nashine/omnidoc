# OmniDoc — Enterprise Multimodal Document Intelligence Platform

![CI](https://github.com/Harshit-Nashine/omnidoc/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![License](https://img.shields.io/badge/license-MIT-blue)

OmniDoc is a production-grade, multi-tenant document intelligence
platform that ingests any document type, scans for PII, embeds
content into a vector store, and answers natural language queries
using RAG — with full observability, audit trails, and MLOps.

---

## What it does

Upload a PDF, image, Word doc, or audio file. OmniDoc:

1. **Extracts text** — PDF parsing, OCR for images, Whisper for audio
2. **Scans for PII** — Aadhaar, PAN, phone, email via Microsoft Presidio
3. **Quarantines flagged docs** — stored in MongoDB, not embedded
4. **Embeds clean docs** — multilingual sentence-transformers → ChromaDB
5. **Answers questions** — semantic search + Claude LLM synthesis
6. **Tracks everything** — cost per query, audit log, Prometheus metrics

---

## Architecture
┌─────────────────────────────────────────────────────────────┐

│                        FastAPI Gateway                       │

│              JWT Auth · RBAC · Tenant Isolation (RLS)        │

└──────────┬────────────────────────────────┬─────────────────┘

│                                │

┌──────▼──────┐                  ┌──────▼──────┐

│   Document  │                  │    Query    │

│   Upload    │                  │   Engine    │

└──────┬──────┘                  └──────┬──────┘

│                                │

┌──────▼──────┐                  ┌──────▼──────┐

│   Celery    │                  │  ChromaDB   │

│   Worker    │                  │ Vector Store│

└──────┬──────┘                  └─────────────┘

│

┌──────▼──────────────────────────────┐

│         Processing Pipeline          │

│  PDF Parser → OCR → PII Scan →      │

│  Embed → ChromaDB                   │

└──────┬──────────────────────────────┘

│

┌──────▼──────┐    ┌─────────────┐    ┌─────────────┐

│ PostgreSQL  │    │   MongoDB   │    │    MinIO    │

│  Metadata   │    │  Quarantine │    │  Raw Files  │

│  Audit Log  │    │   Store     │    │  + Extracted│

│  Cost Log   │    │             │    │    Text     │

└─────────────┘    └─────────────┘    └─────────────┘
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    Redis    │    │ Prometheus  │    │   MLflow    │
│  Celery +   │    │  + Grafana  │    │  Experiment │
│  Streams    │    │  Dashboards │    │  Tracking   │
└─────────────┘    └─────────────┘    └─────────────┘

---

## Tech Stack

| Category | Technologies |
|---|---|
| API | FastAPI, Uvicorn, Pydantic |
| Auth | JWT (python-jose), bcrypt (passlib), PostgreSQL RLS |
| Async | Celery, Redis |
| Storage | PostgreSQL, MongoDB, Redis, MinIO (S3-compatible) |
| Document Processing | pdfplumber, Tesseract OCR, Presidio PII |
| Embeddings | sentence-transformers (multilingual-mpnet-base-v2) |
| Vector Store | ChromaDB |
| LLM | Anthropic Claude (graceful degradation without API key) |
| Observability | Prometheus, Grafana, query_cost_log |
| MLOps | MLflow (experiment tracking), DVC (data versioning) |
| Events | Redis Streams, SMTP, Slack webhook |
| CI/CD | GitHub Actions |

---

## Features

### Multi-Tenancy
- PostgreSQL Row Level Security — tenant isolation at DB layer
- JWT tokens carry `tenant_id` — set as session variable on every request
- One ChromaDB collection per tenant — vector search never crosses tenants

### Document Pipeline
- **Supported formats:** PDF, JPEG, PNG, TIFF, MP3, WAV, TXT, Word, Excel, PowerPoint
- **Async processing:** API returns immediately, Celery processes in background
- **Status tracking:** `uploaded → processing → processed → embedding → completed`

### PII Governance
- Presidio NLP-based detection (not just regex)
- Detects: Aadhaar, PAN, phone, email, credit card, IBAN, names, locations
- Flagged documents quarantined in MongoDB
- `compliance_status`: `pending → clean / flagged / quarantined → approved`

### RAG Pipeline
- 400-token chunks with 80-token overlap
- 768-dimensional multilingual embeddings
- Cosine similarity search
- Optional LLM synthesis with source citations

### Observability
- `/metrics` endpoint — Prometheus scrape target
- Grafana dashboard — 6 panels (request volume, latency, RAG metrics)
- `query_cost_log` — per-query token count and latency
- `audit_log` — immutable record of every document state change

---

## Quick Start

### Prerequisites
- Python 3.13
- Docker Desktop
- Git

### 1. Clone and setup

```bash
git clone https://github.com/Harshit-Nashine/omnidoc.git
cd omnidoc
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure environment

```bash
copy .env.example .env
# Edit .env with your passwords and API keys
```

### 3. Start databases

```bash
docker compose up -d
# Wait for all 4 to show (healthy)
docker compose ps
```

### 4. Apply database schema

```bash
docker exec -i omnidoc_postgresql psql -U omnidoc_user -d omnidoc_db < infra/postgres/schema.sql
```

### 5. Start the API

```bash
uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start the Celery worker (new terminal)

```bash
celery -A services.api.app.celery_app worker --loglevel=info --pool=solo
```

### 7. Open Swagger UI
http://localhost:8000/docs

---

## API Overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create tenant + first admin user |
| POST | `/auth/login` | Get JWT tokens |
| GET | `/auth/me` | Current user profile |
| POST | `/documents/upload` | Upload a document |
| GET | `/documents/` | List tenant documents |
| GET | `/documents/{id}` | Get document status |
| POST | `/documents/{id}/approve` | Approve clean document |
| POST | `/query/` | Natural language search |
| GET | `/audit/` | Audit log |
| GET | `/audit/{doc_id}` | Document audit trail |
| GET | `/health` | Database health check |
| GET | `/metrics` | Prometheus metrics |

---

## Monitoring

| Service | URL | Credentials |
|---|---|---|
| API Swagger | http://localhost:8000/docs | JWT token |
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| MinIO Console | http://localhost:9001 | .env credentials |
| MLflow UI | http://localhost:5000 | — |

---

## Running Tests

```bash
pytest tests/ -v
```

19 unit tests covering config, security, and document chunking.

---

## Project Structure
omnidoc/

├── .github/workflows/    # CI pipeline

├── services/api/app/     # FastAPI application

│   ├── parsers/          # PDF, OCR, PII scanner

│   ├── config.py         # Settings from .env

│   ├── database.py       # Connection pools

│   ├── main.py           # App entry point

│   ├── auth_routes.py    # Auth endpoints

│   ├── document_routes.py # Document endpoints

│   ├── query_routes.py   # RAG query endpoint

│   ├── audit_routes.py   # Audit log endpoints

│   ├── vector_store.py   # ChromaDB abstraction

│   ├── chunker.py        # Document chunking

│   ├── llm_service.py    # LLM synthesis

│   ├── tasks.py          # Celery tasks

│   ├── events.py         # Redis Streams

│   ├── metrics.py        # Prometheus metrics

│   └── ml_tracking.py   # MLflow tracking

├── infra/

│   ├── postgres/         # Schema + init SQL

│   └── prometheus/       # Scrape config

├── tests/                # pytest unit tests

├── docs/                 # Component docs, ADRs

├── docker-compose.yml    # Full local stack

├── dvc.yaml              # Data pipeline

└── requirements.txt      # Python dependencies
---

## Built With

This project demonstrates enterprise patterns across the full
ML engineering stack:

- **Backend:** Production FastAPI with async database access
- **Security:** JWT + bcrypt + PostgreSQL RLS (defense in depth)
- **MLOps:** DVC data versioning + MLflow experiment tracking
- **Observability:** Prometheus metrics + Grafana dashboards
- **Compliance:** PII detection + quarantine + immutable audit trail
- **Async:** Celery + Redis Streams event-driven architecture

---

## License

MIT License — see LICENSE file.