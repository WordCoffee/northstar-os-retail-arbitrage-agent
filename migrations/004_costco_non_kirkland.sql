-- Phase F — Postgres migration 004: Costco Non-Kirkland research pipeline.
-- NOT APPLIED. Apply with psql or Supabase SQL editor per MIGRATION_GUIDE.md.
-- SQLite parity DDL lives in Northstar_backend/costco_non_kirkland/store.py.
-- All DDL is idempotent (IF NOT EXISTS) and additive-only.

BEGIN;

CREATE TABLE IF NOT EXISTS costco_pipeline_runs (
    run_id TEXT PRIMARY KEY,
    run_name TEXT NOT NULL,
    command TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    counts_json JSONB,
    error_summary TEXT
);

CREATE TABLE IF NOT EXISTS costco_source_products (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    source_name TEXT,
    source_record_id TEXT,
    source_file_or_dataset TEXT,
    source_url TEXT,
    costco_item_number TEXT,
    title_raw TEXT,
    title_normalized TEXT,
    brand_raw TEXT,
    brand_normalized TEXT,
    upc TEXT,
    ean TEXT,
    gtin TEXT,
    manufacturer_part_number TEXT,
    costco_price NUMERIC(12,2),
    currency TEXT DEFAULT 'USD',
    costco_pack_raw TEXT,
    normalized_unit_count REAL,
    normalized_unit_kind TEXT,
    size_or_weight_raw TEXT,
    availability_status TEXT,
    warehouse_or_location TEXT,
    observed_at TIMESTAMPTZ,
    imported_at TIMESTAMPTZ,
    freshness_status TEXT,
    evidence_class TEXT,
    identity_status TEXT,
    exclusion_reason TEXT,
    manual_review_required BOOLEAN DEFAULT FALSE,
    eligible_for_costco_non_kirkland_workflow BOOLEAN DEFAULT TRUE,
    disallowed_classes TEXT,
    raw_json JSONB
);

CREATE TABLE IF NOT EXISTS amazon_match_candidates (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    costco_source_product_id TEXT REFERENCES costco_source_products(id),
    asin TEXT,
    marketplace TEXT DEFAULT 'US',
    match_method TEXT,
    match_confidence REAL,
    title_similarity REAL,
    brand_match_status TEXT,
    pack_match_status TEXT,
    size_match_status TEXT,
    variation_match_status TEXT,
    identity_status TEXT,
    match_rationale TEXT,
    manual_review_required BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ,
    amazon_title TEXT,
    amazon_brand TEXT
);

CREATE TABLE IF NOT EXISTS costco_evidence (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    candidate_id TEXT,
    source TEXT,
    source_url TEXT,
    field_name TEXT,
    field_value TEXT,
    evidence_class TEXT,
    freshness_status TEXT,
    capture_status TEXT,
    captured_at TIMESTAMPTZ,
    limitations TEXT,
    metadata_json JSONB
);

CREATE TABLE IF NOT EXISTS costco_enrichment_manifests (
    manifest_id TEXT PRIMARY KEY,
    run_id TEXT,
    provider TEXT,
    status TEXT DEFAULT 'planned',
    max_items INTEGER,
    spend_cap NUMERIC(12,2),
    approved BOOLEAN DEFAULT FALSE,
    approval_token TEXT,
    created_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    items_json JSONB,
    preflight_json JSONB
);

CREATE TABLE IF NOT EXISTS costco_gg_scores (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    costco_source_product_id TEXT,
    amazon_match_candidate_id TEXT,
    score REAL,
    score_version TEXT,
    score_components_json JSONB,
    positive_evidence_json JSONB,
    penalties_json JSONB,
    risk_flags_json JSONB,
    missing_evidence_json JSONB,
    confidence_level TEXT,
    recommendation_status TEXT,
    purchase_authorization_status TEXT NOT NULL DEFAULT 'not_authorized',
    manual_review_required BOOLEAN DEFAULT TRUE,
    evidence_summary TEXT,
    scored_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS costco_confirmations (
    confirmation_id TEXT PRIMARY KEY,
    action_key TEXT NOT NULL,
    description TEXT,
    granted_at TIMESTAMPTZ NOT NULL,
    granted_by TEXT,
    expires_at TIMESTAMPTZ,
    UNIQUE(action_key)
);

CREATE TABLE IF NOT EXISTS costco_provider_imports (
    import_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    parse_kind TEXT,
    schema_version TEXT,
    rows_total INTEGER,
    rows_imported INTEGER,
    row_status_counts_json JSONB,
    imported_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS costco_market_snapshots (
    id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    asin TEXT,
    provider_export_filename TEXT,
    provider_export_sha256 TEXT,
    provider_row_number INTEGER,
    provider_record_id TEXT,
    provider_snapshot_id TEXT,
    observed_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ,
    freshness_status TEXT,
    identity_json JSONB,
    marketplace_json JSONB,
    demand_json JSONB,
    fees_json JSONB,
    size_json JSONB,
    risk_json JSONB,
    fields_json JSONB,
    raw_source_reference TEXT
);

CREATE TABLE IF NOT EXISTS costco_candidate_decisions (
    id TEXT PRIMARY KEY,
    candidate_id TEXT,
    costco_source_product_id TEXT,
    asin TEXT,
    identity_state TEXT,
    split_pack_state TEXT,
    market_snapshot_id TEXT,
    provider TEXT,
    competition_state TEXT,
    economics_json JSONB,
    market_snapshot_json JSONB,
    mfn_score REAL,
    mfn_score_version TEXT,
    recommendation_status TEXT,
    reason_codes_json JSONB,
    risk_flags_json JSONB,
    purchase_authorization_status TEXT NOT NULL DEFAULT 'not_authorized',
    evidence_summary TEXT,
    source_name TEXT,
    source_sku TEXT,
    source_url TEXT,
    source_price REAL,
    source_price_observed_at TIMESTAMPTZ,
    source_pack_text TEXT,
    updated_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS costco_approvals (
    approval_id TEXT PRIMARY KEY,
    candidate_id TEXT,
    costco_source_product_id TEXT,
    asin TEXT,
    source_name TEXT,
    source_sku TEXT,
    source_url TEXT,
    source_price REAL,
    source_price_observed_at TIMESTAMPTZ,
    source_pack_text TEXT,
    quantity INTEGER,
    approved_by TEXT,
    state TEXT DEFAULT 'requested',
    granted_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    revoke_reason TEXT,
    invalidated_at TIMESTAMPTZ,
    invalidate_reason TEXT,
    economics_snapshot_json JSONB,
    market_snapshot_json JSONB,
    reason_codes_json JSONB,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cnk_source_run ON costco_source_products(run_id);
CREATE INDEX IF NOT EXISTS idx_cnk_source_eligible ON costco_source_products(eligible_for_costco_non_kirkland_workflow);
CREATE INDEX IF NOT EXISTS idx_cnk_match_csp ON amazon_match_candidates(costco_source_product_id);
CREATE INDEX IF NOT EXISTS idx_cnk_gg_run ON costco_gg_scores(run_id);
CREATE INDEX IF NOT EXISTS idx_cnk_snap_asin ON costco_market_snapshots(asin);
CREATE INDEX IF NOT EXISTS idx_cnk_decisions_status ON costco_candidate_decisions(recommendation_status);
CREATE INDEX IF NOT EXISTS idx_cnk_approvals_state ON costco_approvals(state);

COMMIT;