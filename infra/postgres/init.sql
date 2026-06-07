-- ================================================================
-- OmniDoc — PostgreSQL Initialization Script
-- ================================================================
-- This file runs ONCE on first container start only.
-- After that, PostgreSQL stores this state in the named volume.
-- If you need to re-run it, delete the volume and restart.
--
-- Docker automatically runs any .sql file placed in:
-- /docker-entrypoint-initdb.d/
-- We mount this file there in docker-compose.yml
-- ================================================================


-- uuid-ossp: lets us generate UUID primary keys like
-- 'a3f8c2e1-d4b7-a9f0-e3c6-d1b2a5f8c3e6'
-- We use UUIDs instead of 1,2,3 integers because:
-- (1) UUIDs are unguessable — users can't enumerate records via URL
-- (2) UUIDs work across distributed systems without collision
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";


-- pgcrypto: provides cryptographic functions
-- Used for hashing passwords at DB level as a second layer of safety
-- Primary password hashing happens in Python (bcrypt), but having
-- pgcrypto available gives us options without a schema change later
CREATE EXTENSION IF NOT EXISTS "pgcrypto";


-- Verify both extensions installed correctly
-- This produces output visible in Docker logs on first startup
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('uuid-ossp', 'pgcrypto');