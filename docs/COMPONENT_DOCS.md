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