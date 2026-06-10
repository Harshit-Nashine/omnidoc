# ================================================================
# services/api/app/auth_queries.py
# ================================================================
# All database operations for authentication.
# No business logic here — only SQL queries.
#
# WHY SEPARATE QUERIES FROM ROUTES:
# Routes handle HTTP (request parsing, response formatting).
# Queries handle data (SQL, DB connections).
# Separating them means we can test queries without HTTP,
# and change SQL without touching route logic.
# ================================================================

import uuid
from asyncpg import Pool, UniqueViolationError
from services.api.app.security import hash_password


async def create_tenant(
    pool: Pool,
    name: str,
    slug: str,
) -> dict:
    """
    Inserts a new tenant row.
    Returns the created tenant as a dict.
    Raises UniqueViolationError if name or slug already exists.
    """
    # We generate UUID in Python, not in SQL, so we have the ID
    # available immediately without a second SELECT query
    tenant_id = uuid.uuid4()

    row = await pool.fetchrow(
        """
        INSERT INTO tenants (id, name, slug)
        VALUES ($1, $2, $3)
        RETURNING id, name, slug, is_active, created_at
        """,
        tenant_id,
        name,
        slug,
    )

    # asyncpg returns a Record object — convert to dict for easier use
    return dict(row)


async def create_user(
    pool: Pool,
    tenant_id: uuid.UUID,
    email: str,
    password: str,
    full_name: str | None,
    role: str = "admin",
) -> dict:
    """
    Inserts a new user row.
    Hashes the password before storing — plain text never touches DB.
    Returns the created user as a dict (without hashed_password).
    Raises UniqueViolationError if email already exists in this tenant.
    """
    user_id = uuid.uuid4()
    hashed = hash_password(password)

    row = await pool.fetchrow(
        """
        INSERT INTO users (id, tenant_id, email, hashed_password, full_name, role)
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, tenant_id, email, full_name, role, is_active, created_at
        """,
        user_id,
        tenant_id,
        email,
        hashed,
        full_name,
        role,
    )

    return dict(row)


async def get_user_by_email(
    pool: Pool,
    tenant_id: uuid.UUID,
    email: str,
) -> dict | None:
    """
    Fetches a user by email within a specific tenant.
    Returns None if not found — caller handles the 404/401.

    WHY tenant_id in the query:
    Email is unique per tenant, not globally.
    Without tenant_id, user@company-a.com would match
    user@company-b.com if they have the same email.
    """
    row = await pool.fetchrow(
        """
        SELECT id, tenant_id, email, hashed_password,
               full_name, role, is_active, created_at
        FROM users
        WHERE tenant_id = $1 AND email = $2 AND is_active = true
        """,
        tenant_id,
        email,
    )

    return dict(row) if row else None


async def get_tenant_by_slug(
    pool: Pool,
    slug: str,
) -> dict | None:
    """
    Fetches a tenant by slug.
    Used during login to look up which tenant the user belongs to.
    Returns None if not found.
    """
    row = await pool.fetchrow(
        """
        SELECT id, name, slug, is_active, created_at
        FROM tenants
        WHERE slug = $1 AND is_active = true
        """,
        slug,
    )

    return dict(row) if row else None


async def get_user_by_id(
    pool: Pool,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict | None:
    """
    Fetches a user by ID.
    Used by the /auth/me endpoint to return current user info.
    tenant_id included for RLS consistency.
    """
    row = await pool.fetchrow(
        """
        SELECT id, tenant_id, email, full_name,
               role, is_active, created_at
        FROM users
        WHERE id = $1 AND tenant_id = $2 AND is_active = true
        """,
        user_id,
        tenant_id,
    )

    return dict(row) if row else None