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


## Incident 003 — Phase 4 dependency conflicts (Windows + Python 3.13)

**Date:** 2026-06-12

**ISSUE:** Chain of package conflicts installing chromadb,
langchain, sentence-transformers, tiktoken on Windows.

**ROOT CAUSES:**
1. numpy 1.26.4 has OverflowError bug on Python 3.13 (longdouble)
2. chromadb 0.5.0 incompatible with numpy 2.x (np.float_ removed)
3. chromadb 0.5.23 downgrades tokenizers, breaks transformers
4. tiktoken 0.7.0 has no Python 3.13 wheel

**FIXES:**
1. numpy 2.1.0 (skip 1.26.4 entirely)
2. chromadb 0.5.23 (numpy 2.x compatible)
3. tokenizers 0.20.3 + transformers 4.46.0 (compatible pair)
4. tiktoken 0.8.0 (first version with 3.13 wheel)

**PREVENTION:**
On Windows + Python 3.13, ML library versions from tutorials/docs
are often stale. When a version conflict loop occurs, identify
the OLDEST package's constraint and work backward — usually
chromadb or transformers is the anchor. Pin all 4 together in
requirements.txt as a tested-working set.

**FINAL WORKING VERSIONS:**
numpy==2.1.0, chromadb==0.5.23, tokenizers==0.20.3,
transformers==4.46.0, sentence-transformers==3.0.1

## Incident 004 — Anthropic SDK + LLM integration

**Date:** 2026-06-12

**ISSUE 1:** anthropic 0.34.2 raised TypeError on Client init
**ROOT CAUSE:** incompatible with newer httpx version (proxies kwarg removed)
**FIX:** Upgraded to anthropic==0.40.0

**ISSUE 2:** Invalid/missing API key crashed entire query with 500
**ROOT CAUSE:** No try/except around client.messages.create()
**FIX:** Wrapped LLM call in try/except — returns graceful fallback
message, latency still recorded, query never 500s due to LLM issues

**PREVENTION:** Any external API call (LLM, third-party) must be
wrapped in try/except with a fallback — external service failures
should never crash the core retrieval functionality.