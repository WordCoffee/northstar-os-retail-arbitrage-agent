# 07 — Database and Storage Map

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) — all DB inspection was READ-ONLY (`mode=ro`), no writes, no inserts, no migration execution.

## 1. SQLite database (primary)

- Path: `Northstar_backend\data\northstar.db` (716,800 B). Source: `data_layer.py:35` (`_SQLITE_PATH`).
- WAL mode + foreign_keys ON, `check_same_thread=False`, threading.RLock serialization (`data_layer.py:50-72`).
- Postgres/Supabase path exists as a stub when `DATABASE_URL`/`SUPABASE_DB_URL` set — **SQLite is the only implemented engine** (`data_layer.py:38-56`).
- **Row counts were obtained from the ACTIVE database via read-only `sqlite3.connect("file:...?mode=ro")`. No writes occurred.**

### Tables and row counts (read-only, 2026-09-23)

| Table | Rows | Purpose | Writer |
|---|---|---|---|
| products | 1,024 | canonical-ish product table, ASIN-unique | live_catalog.stock, seed_demo_data, data_migration |
| memory_entries | 22 | knowledge plane | memory_bank |
| keywords | 10 | keyword catalog | (dormant) |
| audit_log | 8 | action/entity audit | AuditDB |
| refresh_metadata | 8 | provider refresh runs | refresh logging |
| live_pulls | 3 | live pull ledger | live_catalog |
| campaigns | 4 | PPC campaigns | (dormant) |
| keyword_performance | 4 | keyword KPIs | (dormant) |
| listings | 2 | listing content | (dormant) |
| invites | 0 | invite codes | invites |
| search_query_performance | 0 | search-term metrics | (dormant) |
| social_content | 0 | social posts | (dormant) |
| suppliers | 0 | supplier directory | suppliers routes |
| supplier_products | 0 | supplier SKUs | wholesale ingest |
| supplier_cost_analysis | 0 | supplier economics | (dormant) |
| transactions | 0 | financial transactions | (dormant) |

**16 user tables** (sqlite_sequence excluded). Prior exploration reported 17 counting `sqlite_sequence`; this audit uses 16 user tables.

### products table schema (read-only PRAGMA, 31 columns)

`id, asin, title, brand, category, marketplace, amazon_price, buy_box_price, costco_cost, cost_basis_source, weight_lbs, fba_fee_estimate, referral_fee_pct, bsr_rank, bsr_category, monthly_sales_estimate, review_count, rating, seller_count, net_profit, roi_pct, risk_score, authorization_status, last_enriched_at, data_sources, created_at, updated_at, data_kind, provider_id, fetched_at, fresh_until`

Freshness columns `data_kind/provider_id/fetched_at/fresh_until` added idempotently (`data_layer.py:352-371`); read paths filter `fresh_until IS NULL OR fresh_until > now`.

## 2. JSON caches / stores (root `data/`)

| File | Kind | Records | Producer | Consumer |
|---|---|---|---|---|
| costco-discovery-catalog.json | cache | 800 | costco_api_client refresh | scanner summary |
| seller-offer-cache.json | cache | 247 ASINs | seller_cache.py (TTL 24h) | offer_enrichment, data_migration |
| seller-offer-cache.pre-v2-clean.json | cache backup | 246 | backup | — |
| enriched-offer-cache.json | cache | 263 ASINs | offer_enrichment (TTL 24h) | market_snapshot_store, data_migration |
| costco-api-catalog.json | computed | run report | costco_api_client | main.py presence check |
| costco-product-detail.json | computed | 76 | kirkland_costco_merge | — |
| costco-items.csv | imported | fixture | legacy | Node pipeline, main.py:1053 |
| costco-amazon-mapping.json | imported | 29 ASINs | manual | — |
| data/snapshots/scan-*.json | raw | 212 (one file) | src/scrapers/amazonSearch.js | legacy pipeline |
| data/normalized/ | computed | 154 rows (latest) | normalizeLatestSnapshot.js | legacy |
| data/scored/ | computed | 154 rows, 4 qualified | scoreLatestSnapshot.js | legacy + data_migration |

## 3. Backend data (`Northstar_backend/data/`)

| File | Kind | Records | Producer | Consumer |
|---|---|---|---|---|
| scanner-search-cache.json | cache | candidate_count 0 (empty at audit) | amazon_search.py | kirkland_discovery, proof_batch, autothink context |
| scanner-search-cache.enriched-candidate.json | cache | 10 | kirkland_discovery | autothink |
| scanner-search-cache.brightdata-*.json | cache backup | 234 | brightdata | tests |
| kirkland-discovery.json | cache | 138 Kirkland / 1 qualified | kirkland_discovery | /api/kirkland/discovery |
| kirkland-discovery-meta.json | meta | counts | kirkland_discovery | launcher |
| offline-scout-candidates.json | imported | 245 | populate_scout_offline | offline |
| discovery-manifest.json | manifest | — | kirkland_discovery | — |
| us_suppliers.csv | imported | ~30 | find_us_suppliers.py | supplier pipeline |
| free_tier_ledger.json | ledger | rapidapi_pool 600.0 | GG free_tier_registry | free_tier_router |
| word-coffee/ads-export.json | imported fixture | campaigns | Word Coffee | word_coffee.py |
| catalog/sourcescout_manifest.json | imported/cache | 470 | build_sourcescout_manifest | /api/sourcescout* |
| catalog/sourcescout_compliant_manifest.json | imported | 245 | run_enrichment_pipeline | — |
| catalog/asin_costco_crossref.json | imported | — | costco_sku_registry | — |
| golden-goose-reports/goose_scan_*.json | computed | ~300 files | GG pipeline | /api/golden-goose/opportunities |
| benchmarks/ | protected | reference | benchmark tooling | tests (protected) |
| batch/ | evidence | — | proof-batch | tests/review |
| enrich/, costco-discovery-runs/, costco-lookup-runs/, snapshots/, validation-runs/ | run evidence | — | live-run tooling | audits/reports |

## 4. Migrations

- `migrations/001_core_auth.sql`, `002_productivity.sql`, `003_golden_goose.sql` — PostgreSQL/Supabase; each header "NOT APPLIED. Apply with psql or Supabase SQL editor per MIGRATION_GUIDE.md". (S)
- `MIGRATION_GUIDE.md` status: PREPARED — NOT APPLIED (L3-6). Applying = gated live/deploy action.
- `ops/schema.sql` and `views.sql` — alternative/demo SQLite→PG schemas + analytics views (competing schema descriptions, see `01`).

## 5. Freshness / TTL model

| Store | Field | TTL | Enforcer |
|---|---|---|---|
| enriched/seller offer cache | cached_at | 24h default (`SCANNER_OFFER_CACHE_TTL_HOURS`, `SELLER_CACHE_TTL_HOURS`) | offer_enrichment, seller_cache |
| market snapshots | offers/sales/identity fresh_until | 7d/30d/90d | market_snapshot_store |
| products rows | fresh_until | now+ttl | data_layer read paths |
| costco discovery catalog | updated_at vs threshold | 8 days | scanner summary |
| shared data-requirements | min_freshness_hours | 24/168/0 per service | readiness.py |

## 6. Row-count provenance

- Counts obtained via a temporary read-only Python script: `sqlite3.connect("file:Northstar_backend\data\northstar.db?mode=ro", uri=True)`, `SELECT COUNT(*)` per table, plus `PRAGMA table_info(products)`. Script written to `$env:TEMP\ns_db_inspect.py` / `ns_db_schema.py` and run once; no mutation. Commands recorded in `17` §E.
