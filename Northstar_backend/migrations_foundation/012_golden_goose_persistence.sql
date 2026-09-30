-- Northstar OS Foundation — P5-T3/T4 Golden Goose persistence (additive delta)
-- Additive ONLY; reapply-safe. Enables decision round-trip + snapshots.

BEGIN;

CREATE TABLE IF NOT EXISTS golden_goose_items (
    item_id                TEXT PRIMARY KEY,
    organization_id        TEXT,
    category               TEXT,
    match_state            TEXT,
    resale_score           DOUBLE PRECISION,
    net_per_unit           DOUBLE PRECISION,
    economics_complete     INTEGER,
    policy_exclusion_flag  INTEGER,
    payload_json           TEXT NOT NULL DEFAULT '{}',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS golden_goose_decisions (
    decision_id     TEXT PRIMARY KEY,
    item_id         TEXT NOT NULL,
    organization_id TEXT,
    decision_state  TEXT NOT NULL,
    purchase_ready  INTEGER NOT NULL DEFAULT 0,
    scorer_version  TEXT,
    inputs_hash     TEXT,
    payload_json    TEXT NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gg_items_org ON golden_goose_items (organization_id);
CREATE INDEX IF NOT EXISTS idx_gg_decisions_item ON golden_goose_decisions (item_id, organization_id);

COMMIT;
