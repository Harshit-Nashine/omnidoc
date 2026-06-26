# ================================================================
# tests/test_security.py
# ================================================================
# Tests for password hashing and JWT token functions.
# No database needed — pure unit tests.
# ================================================================

import pytest
from services.api.app.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_access_token,
)
from jose import JWTError


def test_password_hash_is_not_plaintext():
    """Hashed password must not equal the original."""
    plain = "mysecretpassword"
    hashed = hash_password(plain)
    assert hashed != plain


def test_password_hash_verifies_correctly():
    """Correct password verifies against its hash."""
    plain = "mysecretpassword"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_wrong_password_fails_verification():
    """Wrong password must not verify against hash."""
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_access_token_created_and_decoded():
    """Access token can be created and decoded correctly."""
    token = create_access_token(
        user_id="test-user-id",
        tenant_id="test-tenant-id",
        role="admin",
    )
    assert isinstance(token, str)
    assert len(token) > 0

    payload = decode_access_token(token)
    assert payload["sub"] == "test-user-id"
    assert payload["tenant_id"] == "test-tenant-id"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token_rejected_as_access_token():
    """Refresh token must not be accepted as access token."""
    refresh = create_refresh_token(
        user_id="test-user-id",
        tenant_id="test-tenant-id",
    )
    with pytest.raises(JWTError):
        decode_access_token(refresh)


def test_tampered_token_rejected():
    """Modified token signature must be rejected."""
    token = create_access_token(
        user_id="user-id",
        tenant_id="tenant-id",
        role="viewer",
    )
    tampered = token[:-5] + "XXXXX"
    with pytest.raises(JWTError):
        decode_access_token(tampered)


def test_hash_is_different_each_time():
    """
    bcrypt uses random salt — same password hashes differently each time.
    This is intentional and important for security.
    """
    plain = "samepassword"
    hash1 = hash_password(plain)
    hash2 = hash_password(plain)
    assert hash1 != hash2
    # But both should verify correctly
    assert verify_password(plain, hash1) is True
    assert verify_password(plain, hash2) is True