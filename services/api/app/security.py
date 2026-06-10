# ================================================================
# services/api/app/security.py
# ================================================================
# Two responsibilities:
#   1. Password hashing and verification (bcrypt via passlib)
#   2. JWT token creation and verification (python-jose)
#
# WHY THIS IS A SEPARATE FILE:
# Both auth routes and middleware need these functions.
# Putting them here avoids circular imports — routes import
# from security.py, not from each other.
# ================================================================

from datetime import datetime, timedelta, timezone
from typing import Optional

# python-jose handles JWT creation and verification
# We use HS256 — HMAC with SHA256, standard for single-server apps
from jose import JWTError, jwt

# passlib wraps bcrypt — cleaner API than using bcrypt directly
# CryptContext lets us define which algorithm to use and handles
# future algorithm migrations (e.g. upgrading from bcrypt to argon2)
from passlib.context import CryptContext

from services.api.app.config import settings


# ── Password hashing ────────────────────────────────────────────
# bcrypt is the industry standard for password hashing.
# It is intentionally slow — takes ~100ms per hash.
# This is a feature, not a bug: it makes brute-force attacks
# take years instead of seconds.
# deprecated="auto" means if we change algorithms later,
# passlib automatically rehashes old passwords on next login.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """
    Hashes a plain text password using bcrypt.
    Returns a 60-character hash string.
    The hash includes the salt — no need to store salt separately.

    Usage:
        hashed = hash_password("mysecretpassword")
        # Store hashed in DB, never plain_password
    """
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a stored bcrypt hash.
    Returns True if they match, False otherwise.

    WHY NOT COMPARE STRINGS DIRECTLY:
    bcrypt hashes include a random salt — the same password
    hashes to a different string every time. You cannot compare
    hash strings directly. passlib handles this correctly.

    Usage:
        is_valid = verify_password("mysecretpassword", stored_hash)
    """
    return pwd_context.verify(plain_password, hashed_password)


# ── JWT tokens ──────────────────────────────────────────────────
# JWT = JSON Web Token
# Structure: header.payload.signature
# Payload contains: user_id, tenant_id, role, expiry time
# Signature is created with SECRET_KEY — only our server can
# create valid signatures, so we know tokens are not forged.
#
# TWO TOKEN TYPES:
# Access token  — short-lived (30 min), sent with every request
# Refresh token — long-lived (7 days), used only to get new access tokens
# If access token is stolen, it expires in 30 min max.
# If refresh token is stolen, user can revoke it by logging out.

def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Creates a signed JWT access token.

    Payload contains:
        sub       — subject (user_id) — standard JWT field
        tenant_id — which tenant this user belongs to
        role      — admin / editor / viewer
        type      — 'access' so we can distinguish from refresh tokens
        exp       — expiry timestamp — jose validates this automatically

    Returns the token as a string to send to the client.
    """
    # timezone.utc ensures we always work in UTC, never local time
    # Local time causes bugs when servers are in different timezones
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=settings.access_token_expire_minutes
        )

    payload = {
        "sub": str(user_id),           # standard JWT subject field
        "tenant_id": str(tenant_id),
        "role": role,
        "type": "access",
        "iat": now,                     # issued at
        "exp": now + expires_delta,     # expiry
    }

    # jwt.encode signs the payload with our SECRET_KEY
    # Anyone can decode the payload (it's base64) but they cannot
    # forge the signature without knowing SECRET_KEY
    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def create_refresh_token(
    user_id: str,
    tenant_id: str,
) -> str:
    """
    Creates a signed JWT refresh token.
    Longer expiry than access token.
    Does NOT include role — role is always fetched fresh from DB
    when a new access token is issued (in case role changed).
    """
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "type": "refresh",              # MUST be different from access
        "iat": now,
        "exp": now + timedelta(days=7),
    }

    return jwt.encode(
        payload,
        settings.secret_key,
        algorithm=settings.algorithm,
    )


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.

    Validates:
        1. Signature — was this token created by our server?
        2. Expiry    — has this token expired?
        3. Type      — is this an access token, not a refresh token?

    Returns the payload dict if valid.
    Raises JWTError if invalid — caller must handle this.

    WHY WE CHECK token TYPE:
    Without the type check, someone could use a refresh token
    as an access token. They are both valid JWTs signed by us,
    so signature check alone would pass.
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )

        # Reject refresh tokens used as access tokens
        if payload.get("type") != "access":
            raise JWTError("Invalid token type")

        return payload

    except JWTError:
        # Re-raise so the caller (middleware/route) can return 401
        raise