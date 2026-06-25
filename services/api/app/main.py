# ================================================================
# services/api/app/main.py
# ================================================================
# FastAPI application entry point.
#
# This file does 3 things only:
# 1. Creates the FastAPI app instance
# 2. Registers startup and shutdown database lifecycle hooks
# 3. Defines the 2 starter endpoints: / and /health
#
# All business logic goes in separate route files (added in later steps).
# This file stays small and focused — it is the entry point, not
# the place to put actual logic.
# ================================================================

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.app.config import settings
from services.api.app.database import init_databases, close_databases, ping_all_databases
from services.api.app.auth_routes import router as auth_router
from services.api.app.middleware import TenantIsolationMiddleware
from services.api.app.document_routes import router as document_router
from services.api.app.query_routes import router as query_router
from services.api.app.audit_routes import router as audit_router
from prometheus_client import make_asgi_app, generate_latest, CONTENT_TYPE_LATEST
from services.api.app.ml_tracking import setup_mlflow
from fastapi import Response
import time

from services.api.app.metrics import (
    http_requests_total,
    http_request_duration_seconds,
)
# ── Lifespan ────────────────────────────────────────────────────
# asynccontextmanager turns this into a context manager FastAPI
# uses for startup and shutdown events.
# Everything BEFORE yield runs on startup.
# Everything AFTER yield runs on shutdown.
# This is FastAPI's modern way of handling lifecycle events —
# the older @app.on_event("startup") decorator is deprecated.

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────────
    print("Starting OmniDoc API...")
    print(f"Connecting to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}")
    print(f"Connecting to MongoDB at {settings.mongo_host}:{settings.mongo_port}")
    print(f"Connecting to Redis at {settings.redis_host}:{settings.redis_port}")

    # Open all database connections — app will not start if any fail
    await init_databases()
    print("All database connections established successfully.")
# Initialize Redis Streams consumer group for document events
    from services.api.app.events import ensure_consumer_group
    await ensure_consumer_group()
    print("Redis Streams consumer group initialized.")
    # Initialize MLflow experiment tracking
    setup_mlflow()
    
    yield  # App runs here — handling all incoming requests

    # ── SHUTDOWN ─────────────────────────────────────────────────
    print("Shutting down OmniDoc API...")
    await close_databases()
    print("All database connections closed cleanly.")


# ── FastAPI app instance ─────────────────────────────────────────
# This is the central object — everything registers on it.
app = FastAPI(
    title="OmniDoc API",
    description="Enterprise Multimodal Document Intelligence Platform",
    version="0.1.0",
    # Disable automatic docs in production later — fine for dev
    docs_url="/docs",       # Swagger UI at http://localhost:8000/docs
    redoc_url="/redoc",     # ReDoc UI at http://localhost:8000/redoc
    lifespan=lifespan,
)


# ── CORS Middleware ──────────────────────────────────────────────
# CORS = Cross-Origin Resource Sharing
# Allows a frontend running on localhost:3000 to call our API
# on localhost:8000. Without this, browsers block the request.
# In production, replace allow_origins=["*"] with your actual
# frontend domain — ["*"] is too permissive for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # any origin allowed in dev
    allow_credentials=True,
    allow_methods=["*"],        # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],
)
# ── Prometheus metrics middleware ────────────────────────────────
# Records every HTTP request's method, path, status code, and duration.
# This runs on every request — lightweight, no DB calls.
@app.middleware("http")
async def prometheus_middleware(request, call_next):
    start_time = time.perf_counter()

    response = await call_next(request)

    duration = time.perf_counter() - start_time

    # Use route path template, not raw URL, to avoid high cardinality
    # e.g. /documents/{document_id} not /documents/abc-123-def
    endpoint = request.url.path
    for route in app.routes:
        if hasattr(route, "path") and route.path_regex.match(request.url.path):
            endpoint = route.path
            break

    http_requests_total.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code,
    ).inc()

    http_request_duration_seconds.labels(
        method=request.method,
        endpoint=endpoint,
    ).observe(duration)

    return response
# Tenant isolation — sets PostgreSQL RLS session variable
# on every authenticated request. Must be added after CORS.
app.add_middleware(TenantIsolationMiddleware)
# Mount auth routes — all endpoints will be at /auth/...
app.include_router(auth_router)
app.include_router(document_router)
app.include_router(query_router)
app.include_router(audit_router)
# ── Routes ──────────────────────────────────────────────────────

@app.get("/")
async def root():
    """
    Root endpoint — returns basic API information.
    Useful for quickly checking if the API is reachable at all.
    """
    return {
        "service": "OmniDoc API",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint — pings all 4 databases and reports status.

    This endpoint is used by:
    - Docker health checks (in later phases when API is containerized)
    - Kubernetes liveness and readiness probes (Phase 5)
    - Your own eyes during development to verify everything is connected

    Returns HTTP 200 if all databases are reachable.
    Returns HTTP 503 if any database is unreachable.
    """
    db_status = await ping_all_databases()

    # Check if all databases are healthy
    all_healthy = all(
        v == "healthy"
        for k, v in db_status.items()
        if k != "minio"  # minio checked separately in later phase
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "databases": db_status,
        "api_version": "0.1.0",
    }
@app.get("/metrics")
async def metrics():
    """
    Prometheus scrape endpoint.
    Returns all metrics in Prometheus text exposition format.
    Prometheus server polls this every 15 seconds (configured
    in prometheus.yml).
    """
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )