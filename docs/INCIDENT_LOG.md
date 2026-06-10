## Incident 001 — API startup failures during Phase 1

**Date:** 2025

**ISSUE:**
Multiple errors when running uvicorn for the first time.

**ROOT CAUSE 1:** asyncpg DSN format wrong
Using `postgresql+asyncpg://` which is SQLAlchemy format.
asyncpg uses plain `postgresql://`.

**FIX 1:** Changed `postgres_url` property in config.py to use
`postgresql://` instead of `postgresql+asyncpg://`

**ROOT CAUSE 2:** @ symbol in password breaks URL parser
Password `OmniDoc@2025Secure` contains `@` which the URL parser
reads as a URL delimiter, splitting the password and hostname.

**FIX 2:** Removed `@` from all passwords in .env.
New password: `OmniDoc2025Secure`

**ROOT CAUSE 3:** motor/pymongo version mismatch
motor 3.5.1 incompatible with auto-installed pymongo version.

**FIX 3:** Pinned to motor==3.3.2 + pymongo==4.6.3

**ROOT CAUSE 4:** Import paths wrong
Files used `from app.config import settings` but the package
path from project root is `services.api.app.config`.
Also missing `__init__.py` in services/ and services/api/.

**FIX 4:** Updated all imports to full path.
Added __init__.py to services/ and services/api/.

**PREVENTION:**
- Never use special characters (@, #, %) in passwords used in URLs
- Always use plain `postgresql://` with asyncpg, never SQLAlchemy format
- Always add __init__.py when creating new Python package folders
- Pin exact versions of packages that have known compatibility issues
## Incident 002 — Document upload failures

**Date:** 2026-06-10

**ISSUE 1:** MinIO connection failed with NameResolutionError
**ROOT CAUSE:** MINIO_HOST=minio in .env — 'minio' is a Docker
service name, not resolvable from outside Docker.
**FIX:** Changed MINIO_HOST=localhost in .env for local dev.
**PREVENTION:** Any service running outside Docker must use
localhost, not Docker service names.

**ISSUE 2:**