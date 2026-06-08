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