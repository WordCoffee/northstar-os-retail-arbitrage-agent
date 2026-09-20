-- Phase F/S9 — Postgres migration 003: Golden Goose store (PG port of
-- Northstar_backend/ops/schema.sql) + scan provenance.
-- NOT APPLIED (see MIGRATION_GUIDE.md).

BEGIN;

CREATE TABLE IF NOT EXISTS products (
    id            BIGSERIAL PRIMARY KEY,
    asin          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT '',
    brand         TEXT NOT NULL DEFAULT '',
    amazon_price  NUMERIC(12,2) NOT NULL DEFAULT 0,
    cogs          NUMERIC(12,2) NOT NULL DEFAULT 0,
    fba_fee       NUMERIC(12,2) NOT NULL DEFAULT 0,
    referral_fee  NUMERIC(12,2) NOT NULL DEFAULT 0,
    net_profit    NUMERIC(12,2) NOT NULL DEFAULT 0,
    roi_pct       NUMERIC(8,2)  NOT NULL DEFAULT 0,
    buybox_owned  BOOLEAN NOT NULL DEFAULT FALSE,
    tier          TEXT NOT NULL DEFAULT 'C' CHECK (tier IN ('A','B','C','Scrubbed')),
    goose         BOOLEAN NOT NULL DEFAULT FALSE,
    est_monthly   INTEGER NOT NULL DEFAULT 0,
    in_inventory  BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS suppliers (
    id            BIGSERIAL PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    channel       TEXT NOT NULL DEFAULT 'costco',
    health        TEXT NOT NULL DEFAULT 'viable' CHECK (health IN ('viable','marginal','reject','unverified')),
    invoice_path  TEXT NOT NULL DEFAULT 'clean' CHECK (invoice_path IN ('clean','needs_review','missing')),
    moq           INTEGER,
    fba_score     INTEGER,
    website       TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gate_events (
    id            BIGSERIAL PRIMARY KEY,
    actor         TEXT NOT NULL,
    gate          TEXT NOT NULL,
    action        TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS board_pins (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,
    title         TEXT NOT NULL,
    body          TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id            BIGSERIAL PRIMARY KEY,
    run_key       TEXT NOT NULL UNIQUE,           -- goose_scan_<ts>
    mode          TEXT NOT NULL,                  -- mock | live | dry-run
    scan_manifest JSONB,
    opportunities JSONB,
    report_path   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMIT;