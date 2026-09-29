-- Northstar OS Foundation — P3-T4 labeled demo dataset (additive delta)
-- Additive ONLY: new tables; reapply-safe (IF NOT EXISTS). SAMPLE rows only.

BEGIN;

CREATE TABLE IF NOT EXISTS demo_settings (
    organization_id TEXT PRIMARY KEY,
    enabled         INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS demo_observations (
    id              TEXT PRIMARY KEY,
    organization_id TEXT NOT NULL,
    basis           TEXT NOT NULL,
    is_sample       INTEGER NOT NULL DEFAULT 1,
    payload         TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_demo_observations_org
    ON demo_observations (organization_id, is_sample);

COMMIT;
