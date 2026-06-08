-- ================================================================
-- OmniDoc — PostgreSQL Schema
-- ================================================================
-- Run order matters:
--   1. tenants       (no foreign key dependencies)
--   2. users         (references tenants)
--   3. user_roles    (references users + tenants)
--   4. documents     (references tenants + users) — added Phase 2
--
-- HOW TO RUN THIS FILE:
--   docker exec -i omnidoc_postgresql psql -U omnidoc_user -d omnidoc_db < infra\postgres\schema.sql
--
-- HOW TO VERIFY TABLES EXIST:
--   docker exec omnidoc_postgresql psql -U omnidoc_user -d omnidoc_db -c "\dt"
-- ================================================================


-- ================================================================
-- TABLE: tenants
-- ================================================================
-- A tenant = one company or team using OmniDoc.
-- Every other table has a tenant_id column pointing here.
-- This is the foundation of multi-tenancy.
--
-- WHY UUID not integer ID:
-- UUIDs are unguessable. If we used id=1,2,3 a user could try
-- changing their tenant_id to 1 and potentially see another
-- company's data. UUID makes that attack impossible.
-- ================================================================

CREATE TABLE IF NOT EXISTS tenants (
    -- uuid_generate_v4() generates a random UUID automatically
    -- we installed uuid-ossp extension in init.sql for this
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Company or team name — must be unique across all tenants
    name                VARCHAR(255) NOT NULL UNIQUE,

    -- URL-safe identifier used in API paths and logs
    -- Example: "acme-corp" not "Acme Corporation"
    slug                VARCHAR(100) NOT NULL UNIQUE,

    -- Controls whether this tenant can use the platform
    -- Soft disable: set is_active=false instead of deleting
    -- Deleting a tenant would cascade-delete all their data
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    -- Timestamps — always store in UTC, convert to local in frontend
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on slug because we look up tenants by slug in every request
-- Without index: PostgreSQL scans every row to find the slug
-- With index: lookup is O(log n) — instant even with millions of rows
CREATE INDEX IF NOT EXISTS idx_tenants_slug
    ON tenants(slug);

CREATE INDEX IF NOT EXISTS idx_tenants_is_active
    ON tenants(is_active);


-- ================================================================
-- TABLE: users
-- ================================================================
-- One user belongs to exactly one tenant.
-- tenant_id is on this table from day one — not added later.
-- Adding it later would require migrating existing data.
-- ================================================================

CREATE TABLE IF NOT EXISTS users (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Every user belongs to exactly one tenant
    -- ON DELETE CASCADE: if a tenant is deleted, all their users
    -- are automatically deleted too — no orphaned records
    tenant_id           UUID NOT NULL REFERENCES tenants(id)
                        ON DELETE CASCADE,

    email               VARCHAR(255) NOT NULL,

    -- We store the bcrypt hash, never the plain password
    -- bcrypt hashes are always 60 characters long
    -- Python code hashes before inserting — DB never sees plaintext
    hashed_password     VARCHAR(255) NOT NULL,

    full_name           VARCHAR(255),

    -- RBAC role — three levels:
    -- admin  : full access, can approve documents, manage users
    -- editor : can upload and query documents
    -- viewer : can only query, cannot upload
    -- We use VARCHAR not ENUM so we can add roles without migrations
    role                VARCHAR(20) NOT NULL DEFAULT 'viewer'
                        CHECK (role IN ('admin', 'editor', 'viewer')),

    -- Soft disable instead of delete
    -- Deleted users would break audit trails and document ownership
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,

    last_login_at       TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Email must be unique WITHIN a tenant, not globally
-- Two different companies can have the same email — that is valid
-- A composite unique index enforces this correctly
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_tenant
    ON users(tenant_id, email);

-- We query users by tenant_id constantly — index makes this fast
CREATE INDEX IF NOT EXISTS idx_users_tenant_id
    ON users(tenant_id);

CREATE INDEX IF NOT EXISTS idx_users_role
    ON users(tenant_id, role);


-- ================================================================
-- TABLE: refresh_tokens
-- ================================================================
-- Stores JWT refresh tokens so users can get new access tokens
-- without logging in again. Also lets us invalidate sessions
-- (logout, suspicious activity) by deleting the token row.
-- ================================================================

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Which user owns this token
    user_id             UUID NOT NULL REFERENCES users(id)
                        ON DELETE CASCADE,

    tenant_id           UUID NOT NULL REFERENCES tenants(id)
                        ON DELETE CASCADE,

    -- The actual token string — stored hashed for security
    token_hash          VARCHAR(255) NOT NULL UNIQUE,

    -- When this token stops being valid
    expires_at          TIMESTAMPTZ NOT NULL,

    -- Track where the token was created from — useful for
    -- detecting suspicious logins from unknown locations
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- If revoked is true, token is invalid even before expires_at
    -- Used for logout and security revocation
    is_revoked          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user_id
    ON refresh_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash
    ON refresh_tokens(token_hash);

-- Automatically clean up expired tokens
-- Tokens older than expires_at are useless — this index helps
-- a cleanup job find and delete them efficiently
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires_at
    ON refresh_tokens(expires_at);


-- ================================================================
-- ROW LEVEL SECURITY
-- ================================================================
-- RLS is PostgreSQL's built-in data isolation mechanism.
-- When RLS is enabled on a table, every query automatically
-- gets an invisible WHERE clause added based on a policy.
--
-- WHY THIS MATTERS:
-- Without RLS: if application code has a bug and forgets to
-- filter by tenant_id, it returns all tenants' data.
-- With RLS: even if application code has a bug, PostgreSQL
-- itself blocks cross-tenant data access at the DB layer.
-- Two layers of protection = defense in depth.
--
-- HOW IT WORKS:
-- We set a session variable: SET app.current_tenant_id = 'uuid'
-- The RLS policy reads this variable and adds WHERE automatically.
-- Application code sets this variable at the start of every request.
-- ================================================================

-- Enable RLS on all tables that contain tenant data
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- FORCE RLS even for the table owner (omnidoc_user)
-- Without FORCE, the DB owner bypasses RLS — dangerous
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY;


-- ── RLS Policy: tenants ─────────────────────────────────────────
-- A tenant can only see their own row
-- current_setting('app.current_tenant_id', true):
--   reads the session variable we set at request start
--   the 'true' means return NULL instead of error if not set
CREATE POLICY tenant_isolation_policy ON tenants
    USING (
        id = NULLIF(
            current_setting('app.current_tenant_id', true), ''
        )::UUID
    );


-- ── RLS Policy: users ───────────────────────────────────────────
-- Users can only see other users in their own tenant
CREATE POLICY tenant_isolation_policy ON users
    USING (
        tenant_id = NULLIF(
            current_setting('app.current_tenant_id', true), ''
        )::UUID
    );


-- ── RLS Policy: refresh_tokens ──────────────────────────────────
-- Tokens are scoped to tenant
CREATE POLICY tenant_isolation_policy ON refresh_tokens
    USING (
        tenant_id = NULLIF(
            current_setting('app.current_tenant_id', true), ''
        )::UUID
    );


-- ================================================================
-- FUNCTION: update_updated_at
-- ================================================================
-- Automatically updates the updated_at column whenever a row
-- is modified. Without this, updated_at stays at its original
-- value even after the row changes — useless for auditing.
--
-- We create one function and attach it to every table that has
-- an updated_at column via a trigger.
-- ================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    -- NEW refers to the row being inserted/updated
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to tenants table
CREATE OR REPLACE TRIGGER trigger_tenants_updated_at
    BEFORE UPDATE ON tenants
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Attach trigger to users table
CREATE OR REPLACE TRIGGER trigger_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- ================================================================
-- VERIFICATION
-- ================================================================
-- These queries run at the end and print confirmation to the
-- terminal so you can see the schema was applied correctly.
-- ================================================================

-- Show all tables created
SELECT
    tablename,
    rowsecurity AS rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;

-- Show all indexes created
SELECT
    indexname,
    tablename
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;
