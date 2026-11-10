-- Northstar OS Foundation — 1C P2-T5a owner password credentials (additive delta)
-- Additive ONLY: creates a new table; never drops, renames, or alters existing
-- objects. Reapply-safe (CREATE TABLE IF NOT EXISTS). Forward-only.
-- Passwords are stored ONLY as bcrypt hashes (never plaintext).

BEGIN;

CREATE TABLE IF NOT EXISTS owner_credentials (
    user_id       TEXT PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_owner_credentials_email
    ON owner_credentials (lower(email));

COMMIT;
