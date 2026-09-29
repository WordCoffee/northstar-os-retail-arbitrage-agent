-- Northstar OS Foundation — P2-T5/T6 shared login throttle (additive delta)
-- Additive ONLY: creates a new table; reapply-safe (IF NOT EXISTS). Forward-only.
-- Backs the shared, multi-process login rate limit.

BEGIN;

CREATE TABLE IF NOT EXISTS auth_login_attempts (
    id           BIGSERIAL PRIMARY KEY,
    key          TEXT NOT NULL,
    attempted_at BIGINT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_auth_login_attempts_key
    ON auth_login_attempts (key, attempted_at);

COMMIT;
