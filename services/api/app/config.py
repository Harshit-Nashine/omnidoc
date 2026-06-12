# ================================================================
# services/api/app/config.py
# ================================================================
# Central configuration — reads .env file and exposes all settings
# as a typed Python object.
#
# WHY THIS FILE EXISTS:
# Every service needs database URLs, passwords, and settings.
# Instead of reading os.environ['POSTGRES_PASSWORD'] scattered
# across dozens of files (messy, error-prone, hard to change),
# every file imports from here:
#   from app.config import settings
#   settings.postgres_password
#
# If a variable is missing from .env, pydantic-settings raises
# a clear error at startup — not a confusing crash later.
# ================================================================

# pydantic-settings reads .env files and validates types automatically
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    All environment variables the API service needs.
    Pydantic validates types on startup — if POSTGRES_PORT is not
    a valid integer, the app refuses to start with a clear error.
    This is intentional — fail fast with a clear message is better
    than a confusing error 10 minutes into runtime.
    """

    # ── PostgreSQL ──────────────────────────────────────────────
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str
    postgres_port: int = 5432

    # ── MongoDB ─────────────────────────────────────────────────
    mongo_root_user: str
    mongo_root_password: str
    mongo_host: str
    mongo_port: int = 27017
    mongo_db: str

    # ── Redis ────────────────────────────────────────────────────
    redis_password: str
    redis_host: str
    redis_port: int = 6379

    # ── MinIO ────────────────────────────────────────────────────
    minio_root_user: str
    minio_root_password: str
    minio_host: str
    minio_port: int = 9000
    minio_bucket_documents: str

    # ── FastAPI ──────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # ── Anthropic ────────────────────────────────────────────────
    anthropic_api_key: str = ""   # empty = LLM synthesis disabled

    # ── Computed properties ──────────────────────────────────────
    # These build connection strings from the individual variables above.
    # We compute them here so no other file needs to know the format.

    @property
    def postgres_url(self) -> str:
        # asyncpg uses postgresql:// not postgres://
        # We build the URL here so it's consistent everywhere
        return (
            f"postgresql://{self.postgres_user}"
            f":{self.postgres_password}"
            f"@{self.postgres_host}"
            f":{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def mongo_url(self) -> str:
        return (
            f"mongodb://{self.mongo_root_user}"
            f":{self.mongo_root_password}"
            f"@{self.mongo_host}"
            f":{self.mongo_port}"
        )

    @property
    def redis_url(self) -> str:
        return (
            f"redis://:{self.redis_password}"
            f"@{self.redis_host}"
            f":{self.redis_port}"
        )

    model_config = SettingsConfigDict(
        # Look for .env file starting from current directory going up
        env_file=".env",
        # If a variable appears twice, first one wins
        env_file_encoding="utf-8",
        # Ignore extra variables in .env that this class doesn't define
        extra="ignore",
        # Variables are case-insensitive — POSTGRES_HOST = postgres_host
        case_sensitive=False,
    )


# lru_cache means this function runs only once no matter how many
# times it is called. Settings object is created once and reused.
# This is important — we don't want to re-read the .env file on
# every single HTTP request, that would be very slow.
@lru_cache
def get_settings() -> Settings:
    return Settings()


# Single shared instance — import this everywhere
# Usage in other files:
#   from app.config import settings
#   print(settings.postgres_host)
settings = get_settings()