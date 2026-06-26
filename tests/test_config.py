# ================================================================
# tests/test_config.py
# ================================================================
# Tests for the settings/config module.
# These run without any database connections.
# ================================================================

import os
import pytest


def test_settings_load():
    """Settings object loads without error."""
    from services.api.app.config import get_settings
    settings = get_settings()
    assert settings.postgres_port == 5432
    assert settings.redis_port == 6379
    assert settings.minio_port == 9000
    assert settings.algorithm == "HS256"


def test_postgres_url_format():
    """PostgreSQL URL uses correct format for asyncpg."""
    from services.api.app.config import get_settings
    settings = get_settings()
    url = settings.postgres_url
    assert url.startswith("postgresql://")
    assert settings.postgres_host in url
    assert str(settings.postgres_port) in url


def test_redis_url_format():
    """Redis URL uses correct format."""
    from services.api.app.config import get_settings
    settings = get_settings()
    url = settings.redis_url
    assert url.startswith("redis://")


def test_secret_key_not_empty():
    """Secret key must be set — empty key is a security risk."""
    from services.api.app.config import get_settings
    settings = get_settings()
    assert len(settings.secret_key) > 0


def test_access_token_expiry():
    """Access token expiry must be positive."""
    from services.api.app.config import get_settings
    settings = get_settings()
    assert settings.access_token_expire_minutes > 0