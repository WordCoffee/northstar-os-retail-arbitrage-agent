-- Northstar OS Foundation — P4-T2 identity ingest contract (additive delta)
-- Additive ONLY: new tables; reapply-safe (IF NOT EXISTS). Forward-only.
-- Pack/unit/quantity/dimension fields are kept DISTINCT.

BEGIN;

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id          TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    schema_version  TEXT NOT NULL,
    observed_at     TEXT,
    status          TEXT NOT NULL,
    rows_in         INTEGER NOT NULL DEFAULT 0,
    pairs_upserted  INTEGER NOT NULL DEFAULT 0,
    inputs_upserted INTEGER NOT NULL DEFAULT 0,
    conflicts       INTEGER NOT NULL DEFAULT 0,
    invalid         INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS identity_pairs (
    pair_id          TEXT PRIMARY KEY,
    run_id           TEXT NOT NULL,
    lane             TEXT,
    source_id        TEXT,
    asin             TEXT,
    match_state      TEXT NOT NULL,
    match_score      DOUBLE PRECISION,
    pack_match_state TEXT NOT NULL DEFAULT 'UNKNOWN',
    evidence_json    TEXT NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS resale_score_inputs (
    input_id                TEXT PRIMARY KEY,
    run_id                  TEXT NOT NULL,
    pair_id                 TEXT,
    asin                    TEXT,
    supplier_pack           INTEGER,
    marketplace_pack        INTEGER,
    unit_count              INTEGER,
    net_quantity            DOUBLE PRECISION,
    package_dimensions_json TEXT,
    raw_claims_json         TEXT NOT NULL DEFAULT '{}',
    normalized_json         TEXT NOT NULL DEFAULT '{}',
    source                  TEXT,
    observed_at             TEXT,
    freshness_state         TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_identity_pairs_run ON identity_pairs (run_id);
CREATE INDEX IF NOT EXISTS idx_resale_score_inputs_run ON resale_score_inputs (run_id);

COMMIT;
