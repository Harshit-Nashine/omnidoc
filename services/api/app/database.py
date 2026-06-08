# ================================================================
# services/api/app/database.py
# ================================================================
# Manages connections to all 4 databases.
#
# WHY CONNECTION POOLS:
# Opening a new database connection for every HTTP request is slow
# (~50-100ms per connection). Connection pools keep a set of
# connections open and reuse them. A request grabs one, uses it,
# and returns it to the pool. This is standard production practice.
#
# WHY ASYNC DRIVERS (asyncpg, motor, redis async):
# FastAPI is async. If we used sync database drivers, every database
# call would block the entire server — no other requests could be
# handled while waiting for DB. Async drivers let FastAPI handle
# thousands of requests concurrently while DB calls are in flight.
# ================================================================

import asyncpg
import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
from services.api.app.config import settings


# ── PostgreSQL connection pool ──────────────────────────────────
# asyncpg Pool: maintains 2-10 open connections to PostgreSQL.
# min_size=2: always keep 2 connections warm and ready.
# max_size=10: never open more than 10 simultaneous connections.
# These numbers are appropriate for a single-developer local setup.
# In production with many users, max_size would be higher.
_postgresql_pool: asyncpg.Pool | None = None


async def get_postgresql_pool() -> asyncpg.Pool:
    """
    Returns the shared PostgreSQL connection pool.
    Raises RuntimeError if called before init_databases().
    """
    if _postgresql_pool is None:
        raise RuntimeError(
            "PostgreSQL pool not initialized. "
            "init_databases() must be called on app startup."
        )
    return _postgresql_pool


# ── MongoDB client ──────────────────────────────────────────────
# Motor (async MongoDB driver) manages its own connection pool
# internally — we just keep one client instance and reuse it.
_mongodb_client: AsyncIOMotorClient | None = None


def get_mongodb_client() -> AsyncIOMotorClient:
    """Returns the shared MongoDB client."""
    if _mongodb_client is None:
        raise RuntimeError(
            "MongoDB client not initialized. "
            "init_databases() must be called on app startup."
        )
    return _mongodb_client


def get_mongodb_database():
    """
    Returns the specific database we use for quarantine storage.
    Separating get_client from get_database lets us switch
    databases in tests without changing application code.
    """
    client = get_mongodb_client()
    return client[settings.mongo_db]


# ── Redis client ────────────────────────────────────────────────
# Single async Redis client — thread-safe and reusable.
_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Returns the shared Redis client."""
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialized. "
            "init_databases() must be called on app startup."
        )
    return _redis_client


# ── Lifecycle functions ─────────────────────────────────────────
# These are called when FastAPI starts up and shuts down.
# init_databases() opens all connections.
# close_databases() closes them cleanly so no connections leak.

async def init_databases() -> None:
    """
    Opens connections to all 4 databases on application startup.
    Called once when FastAPI starts — not on every request.
    If any connection fails here, the app refuses to start.
    This is intentional: better to fail at startup with a clear
    error than to start successfully and crash on the first request.
    """
    global _postgresql_pool, _mongodb_client, _redis_client

    # PostgreSQL — create connection pool
    # command_timeout=60: if a query takes more than 60 seconds,
    # something is seriously wrong — fail rather than hang forever
    _postgresql_pool = await asyncpg.create_pool(
        dsn=settings.postgres_url,
        min_size=2,
        max_size=10,
        command_timeout=60,
    )

    # MongoDB — create async client
    # serverSelectionTimeoutMS=5000: fail after 5 seconds if
    # MongoDB is not reachable, instead of hanging forever
    _mongodb_client = AsyncIOMotorClient(
        settings.mongo_url,
        serverSelectionTimeoutMS=5000,
    )

    # Redis — create async client
    # decode_responses=True: return strings not bytes — much easier
    # to work with in Python (no need for b"key".decode() everywhere)
    _redis_client = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )


async def close_databases() -> None:
    """
    Closes all database connections on application shutdown.
    FastAPI calls this when the server stops (Ctrl+C or container stop).
    Not closing connections causes resource leaks — the DB thinks
    connections are still open and wastes resources managing them.
    """
    global _postgresql_pool, _mongodb_client, _redis_client

    if _postgresql_pool is not None:
        await _postgresql_pool.close()
        _postgresql_pool = None

    if _mongodb_client is not None:
        _mongodb_client.close()
        _mongodb_client = None

    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


async def ping_all_databases() -> dict:
    """
    Pings all 4 databases and returns their status.
    Used by the /health endpoint to report which services are up.
    Returns a dict so the health endpoint can serialize it to JSON.
    """
    status = {
        "postgresql": "unreachable",
        "mongodb": "unreachable",
        "redis": "unreachable",
        "minio": "unchecked",
    }

    # PostgreSQL ping — acquire a connection and run a trivial query
    try:
        pool = await get_postgresql_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        status["postgresql"] = "healthy"
    except Exception as e:
        status["postgresql"] = f"error: {str(e)}"

    # MongoDB ping — run adminCommand ping
    try:
        client = get_mongodb_client()
        await client.admin.command("ping")
        status["mongodb"] = "healthy"
    except Exception as e:
        status["mongodb"] = f"error: {str(e)}"

    # Redis ping — standard PING command returns PONG
    try:
        client = get_redis_client()
        response = await client.ping()
        status["redis"] = "healthy" if response else "no response"
    except Exception as e:
        status["redis"] = f"error: {str(e)}"

    return status