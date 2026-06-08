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