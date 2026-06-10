# ================================================================
# services/api/app/auth_routes.py
# ================================================================
# Three endpoints:
#   POST /auth/register  — create tenant + first admin user
#   POST /auth/login     — returns JWT tokens
#   GET  /auth/me        — returns current user info
#
# Route files handle HTTP only:
#   - Parse incoming request
#   - Call query functions
#   - Return response
# No SQL here. No hashing here. Those live in their own files.
# ================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError

from services.api.app.database import get_postgresql_pool
from services.api.app.schemas import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    TokenOut,
    UserOut,
    TenantOut,
)
from services.api.app.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
)
from services.api.app.auth_queries import (
    create_tenant,
    create_user,
    get_user_by_email,
    get_tenant_by_slug,
    get_user_by_id,
)

# fastapi dependency for reading Bearer token from Authorization header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# APIRouter groups related endpoints together
# We mount this on /auth in main.py
router = APIRouter(prefix="/auth", tags=["Authentication"])

# HTTPBearer reads the Authorization: Bearer <token> header
# auto_error=False means we return a clean 401, not a generic error
bearer_scheme = HTTPBearer(auto_error=False)


# ── Dependency: get current user from token ─────────────────────
# This function is used as a FastAPI dependency.
# Any route that needs authentication adds it as a parameter:
#   async def my_route(current_user = Depends(get_current_user)):
# FastAPI calls this function, validates the token, and injects
# the result into the route. If token is invalid, returns 401
# automatically — the route never runs.

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    pool=Depends(get_postgresql_pool),
) -> dict:
    """
    Validates JWT token and returns the current user from DB.
    Used as a dependency in protected routes.
    """
    # credentials is None if no Authorization header was sent
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Include Authorization: Bearer <token> header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch fresh user data from DB
    # We don't trust role from token alone — it could be stale
    # if an admin changed the user's role after token was issued
    user = await get_user_by_id(
        pool=pool,
        user_id=payload["sub"],
        tenant_id=payload["tenant_id"],
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists.",
        )

    return user


# ── POST /auth/register ─────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    pool=Depends(get_postgresql_pool),
):
    """
    Registers a new tenant and creates the first admin user.

    These two operations happen in a single DB transaction.
    If user creation fails (e.g. email already exists),
    the tenant creation is rolled back automatically.
    No partial state is left in the database.
    """
    # Use a transaction so both inserts succeed or both fail
    # pool.acquire() gets a connection from the pool
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Step 1: create the tenant
            try:
                tenant = await create_tenant(
                    pool=conn,
                    name=body.tenant_name,
                    slug=body.tenant_slug,
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Tenant with name '{body.tenant_name}' or "
                           f"slug '{body.tenant_slug}' already exists.",
                )

            # Step 2: create the first admin user for this tenant
            try:
                user = await create_user(
                    pool=conn,
                    tenant_id=tenant["id"],
                    email=body.email,
                    password=body.password,
                    full_name=body.full_name,
                    role="admin",   # first user is always admin
                )
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Email '{body.email}' already exists "
                           f"in this tenant.",
                )

    return RegisterResponse(
        message="Registration successful.",
        tenant=TenantOut(**tenant),
        user=UserOut(**user),
    )


# ── POST /auth/login ────────────────────────────────────────────

@router.post("/login", response_model=TokenOut)
async def login(
    body: LoginRequest,
    pool=Depends(get_postgresql_pool),
):
    """
    Logs in a user and returns JWT tokens.

    Requires tenant_slug in the email or a separate field.
    For simplicity in Phase 1, we find the user by email across
    all active tenants — this works fine for single-tenant dev.
    Multi-tenant login (by slug) is added in Phase 2 iteration.

    Returns:
        access_token  — valid for 30 minutes
        refresh_token — valid for 7 days
    """
    # Find user by email across all tenants
    # In production this would require tenant_slug too
    row = await pool.fetchrow(
        """
        SELECT u.id, u.tenant_id, u.email, u.hashed_password,
               u.full_name, u.role, u.is_active, u.created_at
        FROM users u
        WHERE u.email = $1 AND u.is_active = true
        LIMIT 1
        """,
        body.email,
    )

    # Use a generic error message — never reveal whether email
    # or password was wrong. That helps attackers enumerate emails.
    invalid_credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if row is None:
        raise invalid_credentials_error

    user = dict(row)

    # Verify password against stored bcrypt hash
    if not verify_password(body.password, user["hashed_password"]):
        raise invalid_credentials_error

    # Create tokens
    access_token = create_access_token(
        user_id=str(user["id"]),
        tenant_id=str(user["tenant_id"]),
        role=user["role"],
    )

    refresh_token = create_refresh_token(
        user_id=str(user["id"]),
        tenant_id=str(user["tenant_id"]),
    )

    return TokenOut(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=UserOut(**{k: v for k, v in user.items()
                       if k != "hashed_password"}),
    )


# ── GET /auth/me ────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    """
    Returns the currently authenticated user's profile.
    This is the first protected endpoint — requires a valid token.
    Tests that the full auth flow works end to end.
    """
    return UserOut(**current_user)