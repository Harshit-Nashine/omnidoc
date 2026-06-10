# ================================================================
# services/api/app/schemas.py
# ================================================================
# Pydantic models for request and response validation.
#
# WHY SEPARATE SCHEMAS FROM DB MODELS:
# Database tables store everything including hashed_password.
# API responses must never include hashed_password.
# Having separate schema classes for input/output makes it
# impossible to accidentally leak sensitive fields.
#
# NAMING CONVENTION:
# UserCreate  — data needed to create a user (input)
# UserOut     — data returned to client (output, no password)
# TokenOut    — what the login endpoint returns
# ================================================================

from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from uuid import UUID
from datetime import datetime


# ── Tenant schemas ──────────────────────────────────────────────

class TenantCreate(BaseModel):
    """Input: what we need to create a new tenant."""
    name: str
    slug: str

    @field_validator("slug")
    @classmethod
    def slug_must_be_url_safe(cls, v: str) -> str:
        """
        Slug is used in URLs and logs — must be lowercase,
        letters/numbers/hyphens only. No spaces or special chars.
        Validated here so bad slugs never reach the database.
        """
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError(
                "Slug must be lowercase letters, numbers, "
                "and hyphens only. Example: acme-corp"
            )
        return v


class TenantOut(BaseModel):
    """Output: what we return to the client about a tenant."""
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime

    # model_config tells Pydantic to read values from object
    # attributes, not just dict keys.
    # Required when returning SQLAlchemy/asyncpg Row objects.
    model_config = {"from_attributes": True}


# ── User schemas ────────────────────────────────────────────────

class UserCreate(BaseModel):
    """
    Input: data needed to register a new user.
    password is plain text here — we hash it before storing.
    """
    email: EmailStr        # EmailStr validates email format automatically
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_must_be_strong(cls, v: str) -> str:
        """
        Minimum password rules enforced at schema level.
        Failing here gives a clear 422 error before any DB call.
        """
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class UserOut(BaseModel):
    """
    Output: what we return about a user.
    hashed_password is intentionally excluded — never sent to client.
    """
    id: UUID
    tenant_id: UUID
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Registration schema ─────────────────────────────────────────

class RegisterRequest(BaseModel):
    """
    Input: registering a new tenant + first admin user together.
    One request creates both atomically in a single transaction.
    If user creation fails, tenant creation is also rolled back.
    """
    tenant_name: str
    tenant_slug: str
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("tenant_slug")
    @classmethod
    def slug_format(cls, v: str) -> str:
        import re
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError(
                "Tenant slug must be lowercase letters, "
                "numbers, and hyphens only"
            )
        return v


class RegisterResponse(BaseModel):
    """Output: what we return after successful registration."""
    message: str
    tenant: TenantOut
    user: UserOut


# ── Auth / Login schemas ────────────────────────────────────────

class LoginRequest(BaseModel):
    """Input: email and password to log in."""
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    """
    Output: what the login endpoint returns.
    access_token  — short-lived, sent with every API request
    refresh_token — long-lived, used only to get new access tokens
    token_type    — always 'bearer', required by OAuth2 standard
    """
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ── Current user schema ─────────────────────────────────────────

class CurrentUser(BaseModel):
    """
    Populated by auth middleware from the JWT token.
    Injected into every protected route as a dependency.
    Routes never decode tokens themselves — they just receive this.
    """
    user_id: str
    tenant_id: str
    role: str