-- ============================================================================
-- Northstar OS — Phase 3 · Golden Goose store (SQLite → Oracle PG migration)
-- Persistence for everything the analyst's desk produces:
--   · products       — the hunt's ever-growing scout pool (golden-goose flags)
--   · suppliers      — Costco/Supplier sheets + health + enrichment gates
--   · gate_events    — who-pressed-what, when (authorization ledger, fail-closed)
--   · board_pins     — bulletin-board pins that survive reloads (local-first)
--   · scan_runs      — per-run provenance for every +SourceScout pass
-- Zero network. This is the demo schema the SPA renders against.
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  asin          TEXT UNIQUE NOT NULL,
  title         TEXT NOT NULL,
  category      TEXT NOT NULL DEFAULT '',
  brand         TEXT NOT NULL DEFAULT '',
  amazon_price  REAL NOT NULL DEFAULT 0,
  cogs          REAL NOT NULL DEFAULT 0,
  fba_fee       REAL NOT NULL DEFAULT 0,
  referral_fee  REAL NOT NULL DEFAULT 0,
  net_profit    REAL NOT NULL DEFAULT 0,
  roi_pct       REAL NOT NULL DEFAULT 0,
  buybox_owned  INTEGER NOT NULL DEFAULT 0,
  tier          TEXT NOT NULL DEFAULT 'C' CHECK (tier IN ('A','B','C','Scrubbed')),
  goose         INTEGER NOT NULL DEFAULT 0,   -- 1 = Golden Goose qualified
  est_monthly   INTEGER NOT NULL DEFAULT 0,
  in_inventory  INTEGER NOT NULL DEFAULT 1,
  updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suppliers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  name          TEXT UNIQUE NOT NULL,
  channel       TEXT NOT NULL DEFAULT 'costco'  -- costco | sams | distributor
  health        TEXT NOT NULL DEFAULT 'viable'  -- viable | marginal | reject | unverified
  invoice_path  TEXT NOT NULL DEFAULT 'clean',  -- clean | needs_review | missing
  enriched      INTEGER NOT NULL DEFAULT 0,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gate_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  gate          TEXT NOT NULL,
  authorized    INTEGER NOT NULL DEFAULT 0,    -- 0 = denied (fail closed)
  route         TEXT NOT NULL DEFAULT 'hub',
  at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS board_pins (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  title         TEXT NOT NULL,
  kind          TEXT NOT NULL DEFAULT 'deal',
  pinned_by     TEXT NOT NULL DEFAULT 'demo',
  pinned_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scan_runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  mode          TEXT NOT NULL DEFAULT 'once'    -- once | daily | weekly
  pool_checked  INTEGER NOT NULL DEFAULT 0,
  goose_found   INTEGER NOT NULL DEFAULT 0,
  cursor        TEXT NOT NULL DEFAULT '',
  ran_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Hub-grade KPI views — survive a restart without JS re-render.
CREATE VIEW IF NOT EXISTS v_hub_kpis AS
  SELECT
    COALESCE(SUM(products.net_profit), 0)                          AS total_profit,
    COUNT(DISTINCT products.asin)                                  AS catalog_items,
    COUNT(DISTINCT CASE WHEN products.goose = 1 THEN products.id END) AS golden_goose,
    COUNT(DISTINCT CASE WHEN products.tier = 'A' THEN products.id END) AS tier_a_items
  FROM products;

-- Authorization ledger: the shell must always see gates OFF on first boot.
CREATE VIEW IF NOT EXISTS v_gate_health AS
  SELECT g.gate, g.authorized,
         CASE WHEN g.authorized = 1 THEN 'Authorized' ELSE 'Authorization required' END AS status
  FROM (SELECT DISTINCT gate FROM gate_events) g;
