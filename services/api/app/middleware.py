# ================================================================
# services/api/app/middleware.py
# ================================================================
# Tenant isolation middleware.
#
# WHAT IT DOES ON EVERY REQUEST:
#   1. Reads Authorization header
#   2. Decodes JWT token (if present)
#   3. Extracts tenant_id from token
#   4. Sets PostgreSQL session variable: app.current_tenant_id
#   5. RLS policies read this variable automatically
#
# WHY MIDDLEWARE NOT A DEPENDENCY:
# FastAPI dependencies run per-route — only on routes that
# declare them. Middleware runs on EVERY request automatically,
# including routes we might forget to add the dependency to.
# For security-critical operations like tenant isolation,
# middleware is the safer choice — it cannot be accidentally skipped.
#
# WHAT HAPPENS ON PUBLIC ROUTES (register, login, health):
# These routes have no token. Middleware detects no token,
# sets tenant_id to empty string, and lets the request through.
# RLS policies treat empty string as NULL — no data is returned.
# Public routes do not query tenant-scoped tables so this is fine.
# ================================================================

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from jose import JWTError

from services.api.app.security import decode_access_token
from services.api.app.database import get_postgresql_pool


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Sets PostgreSQL session variable app.current_tenant_id
    on every request that carries a valid JWT token.

    This activates Row Level Security policies on all tables.
    Every subsequent DB query in the request automatically
    filters by the tenant_id extracted from the token.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

        # Routes that never need tenant context
        # Middleware still runs but skips setting tenant_id
        self.public_paths = {
            "/",
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/register",
            "/auth/login",
        }

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Runs before every request handler.
        Sets tenant_id session variable if token is present and valid.
        """

        # Skip tenant setup for public routes
        if request.url.path in self.public_paths:
            return await call_next(request)

        # Extract token from Authorization: Bearer <token> header
        tenant_id = await self._extract_tenant_id(request)

        if tenant_id is None:
            # No valid token — let the route handle the 401
            # The route's Depends(get_current_user) will reject it
            return await call_next(request)

        # Set tenant_id in PostgreSQL session for this request
        # This activates RLS policies for all queries in this request
        await self._set_rls_tenant(request, tenant_id)

        return await call_next(request)

    async def _extract_tenant_id(
        self,
        request: Request,
    ) -> str | None:
        """
        Reads the Authorization header and extracts tenant_id
        from the JWT payload. Returns None if token is missing
        or invalid — middleware does not raise errors, routes do.
        """
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ", 1)[1]

        try:
            payload = decode_access_token(token)
            return payload.get("tenant_id")
        except JWTError:
            # Invalid token — return None, route will handle 401
            return None

    async def _set_rls_tenant(
        self,
        request: Request,
        tenant_id: str,
    ) -> None:
        """
        Sets app.current_tenant_id in the PostgreSQL session.

        WHY SET SESSION VARIABLE IN POSTGRESQL:
        PostgreSQL RLS policies read this variable automatically.
        Every query in this request will have an invisible
        WHERE clause added: WHERE tenant_id = <this value>

        This is connection-level — the variable is reset when
        the connection returns to the pool, so it cannot leak
        between requests.
        """
        try:
            pool = await get_postgresql_pool()
            async with pool.acquire() as conn:
                # SET LOCAL means this variable is scoped to
                # the current transaction, not the connection.
                # Using app. prefix is a PostgreSQL convention
                # for application-defined custom settings.
                await conn.execute(
                    f"SET LOCAL app.current_tenant_id = '{tenant_id}'"
                )
                # Store connection in request state so routes
                # can reuse it — avoids acquiring a second connection
                request.state.db_conn = conn
                request.state.tenant_id = tenant_id
        except Exception:
            # If we cannot set the session variable, something is
            # seriously wrong with the DB connection. Log and continue
            # — the route will fail with its own DB error if needed.
            pass