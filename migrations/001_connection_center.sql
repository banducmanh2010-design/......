-- DUCMANH AI Connection Center — PostgreSQL schema v1
-- Apply only after DATABASE_URL and the credential-encryption key are configured.
-- All timestamps are UTC. Never store raw provider keys or extension bearer tokens.

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY,
    external_subject TEXT UNIQUE,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'owner' CHECK (role IN ('owner','admin','member')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS connections (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_connected'
      CHECK (status IN ('not_connected','pending_authorization','connected','degraded','expired','revocation_pending','disconnected')),
    auth_type TEXT NOT NULL CHECK (auth_type IN ('api_key','oauth','personal_access_token','device_pairing')),
    granted_scopes TEXT[] NOT NULL DEFAULT '{}',
    capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_health_check TIMESTAMPTZ,
    last_error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, provider_id)
);

CREATE TABLE IF NOT EXISTS encrypted_credentials (
    connection_id UUID PRIMARY KEY REFERENCES connections(id) ON DELETE CASCADE,
    ciphertext BYTEA NOT NULL,
    nonce BYTEA NOT NULL,
    key_version TEXT NOT NULL,
    credential_type TEXT NOT NULL,
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS plugin_catalog (
    plugin_id TEXT NOT NULL,
    version TEXT NOT NULL,
    manifest JSONB NOT NULL,
    publisher_status TEXT NOT NULL DEFAULT 'unverified'
      CHECK (publisher_status IN ('unverified','verified','blocked')),
    published_at TIMESTAMPTZ,
    PRIMARY KEY(plugin_id, version)
);

CREATE TABLE IF NOT EXISTS plugin_installs (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plugin_id TEXT NOT NULL,
    version TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    granted_scopes TEXT[] NOT NULL DEFAULT '{}',
    installed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY(plugin_id, version) REFERENCES plugin_catalog(plugin_id, version),
    UNIQUE(user_id, plugin_id)
);

CREATE TABLE IF NOT EXISTS extension_sessions (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL,
    token_hash BYTEA NOT NULL UNIQUE,
    scopes TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    provider_id TEXT,
    plugin_id TEXT,
    outcome TEXT NOT NULL CHECK (outcome IN ('success','failure','denied')),
    safe_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_connections_user_status ON connections(user_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON audit_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_events_actor_created ON audit_events(actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_extension_sessions_user_expiry ON extension_sessions(user_id, expires_at)
  WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_plugin_installs_user ON plugin_installs(user_id, enabled);

-- Defence in depth: application queries must always scope records by user_id.
-- Credentials are encrypted by the application with AES-256-GCM before insertion.
