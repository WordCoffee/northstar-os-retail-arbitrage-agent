# 03 — Product Identity and Migration Plan

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). This is a SPECIFICATION — migration is NOT executed.

## 1. Source inventory (Phase 0 evidence)

| Source | Kind | Records | Location | Owner | Freshness field |
|---|---|---|---|---|---|
| `products` table | SQLite | 1,024 | `Northstar_backend/data/northstar.db` | live_catalog/seed/migration | fetched_at/fresh_until |
| `scanner-search-cache*.json` | JSON | 0..234 | `Northstar_backend/data/` | amazon_search/kirkland_discovery | fetched_at |
| `sourcescout_manifest.json` | JSON | 470 | `Northstar_backend/data/catalog/` | build_sourcescout_manifest tool | generated_at (2026-09-13) |
| `goose_scan_*.json` | JSON | ~300 files | `Northstar_backend/data/golden-goose-reports/` | GG pipeline | meta.generated_at |
| `enriched-offer-cache.json` | JSON | 263 | root `data/` | offer_enrichment | cached_at |
| `seller-offer-cache.json` | JSON | 247 | root `data/` | seller_cache | cached_at |
| `costco-discovery-catalog.json` | JSON | 800 | root `data/` | costco_api_client | updated_at |
| `kirkland-discovery.json` | JSON | 138 | `Northstar_backend/data/` | kirkland_discovery | generated_at |
| `us_suppliers.csv` | CSV | ~30 | `Northstar_backend/data/` | find_us_suppliers | — |

## 2. Target mapping (→ canonical entities)

| Source field | Canonical target |
|---|---|
| products.asin → catalog_product.asin + product_identifier(ASIN) | marketplace = `amazon.com` default (owner Q1) |
| products.title → catalog_product.canonical_title | source title preserved separately |
| products.amazon_price / buy_box_price → amazon_offer_snapshot.price | captured_at = fetched_at |
| products.costco_cost → supplier_offer_snapshot(supplier=Costco) | invoice status separate |
| products.fba_fee_estimate / referral_fee_pct → fee_snapshot | fee_rule_version captured |
| products.net_profit / roi_pct → product_economics_snapshot | cost_basis recorded |
| products.bsr_rank → rank_snapshot | source provider noted |
| products.rating / review_count → amazon_offer_snapshot / market_snapshot | — |
| sourcescout_manifest items → catalog_product + amazon_offer_snapshot + supplier match | quantity_match → pack_config |
| goose_scan opportunities → catalog_product + opportunity_assessment | report meta → provenance |
| enriched/seller offer caches → seller_offer_snapshot + amazon_offer_snapshot | cached_at → captured_at |

## 3. Normalization pipeline (order)

1. **Marketplace assignment** — default `amazon.com` (id from marketplace table); owner Q1 governs additional marketplaces.
2. **ASIN validation** — normalize (uppercase, strip), validate format `[0-9A-Z]{10}`; invalid → quarantine row.
3. **Identifier normalization** — UPC/EAN/GTIN digit normalization; MPN raw.
4. **Duplicate detection** — across sources by `(marketplace_id, asin)` for Amazon identity; by normalized UPC/EAN/GTIN for cross-source identity.
5. **Pack/variation separation** — parse pack_config; ambiguous → `pending`; variation family grouping from parent-child fields.
6. **Conflict handling** — per-field conflict resolution table: newest `captured_at` wins for snapshots; canonical identity fields require explicit resolution (never silent).
7. **Provenance preservation** — every mapped value carries source, source_identifier, captured_at, confidence, verification_state, raw_source_ref, transformation_version.

## 4. Migration jobs (non-destructive)

| Job | Behavior |
|---|---|
| M1 import `products` table | COPY to staging; map to canonical; no deletes |
| M2 import sourcescout manifest | COPY to staging; pack parse; supplier match attempt |
| M3 import GG reports (latest preferred) | COPY; opportunity assessment rows |
| M4 import offer/seller caches | COPY into snapshots |
| M5 identity reconciliation | dedupe by (marketplace,asin) + UPC/EAN; merge records; conflict report |
| M6 rebuild read projections | canonical reads only; legacy reads continue via compat views |

## 5. Dry run + reconciliation

- Every migration job has a `--dry-run` that writes a **reconciliation report**: counts by source, mapped counts, quarantined counts, conflict list, unmapped fields.
- Acceptance thresholds (owner to confirm): e.g., ≥ 99% ASIN validity, 0 unmapped critical fields, all conflicts reviewed, provenance completeness ≥ 95%.

## 6. Rollback

- Migration writes only to staging tables first (canonical `_staging` schema); promotion to live tables is a separate flag.
- Rollback = drop promoted views/tables; sources are never modified (non-destructive).
- `ROLLBACK_DRILL.md` pattern retained; data rollback documented.

## 7. Legacy read compatibility

- Compatibility views (`v_products_legacy`, `v_sourcescout_manifest`) preserve Phase 0 response shapes for `/api/kirkland/scanner`, `/api/sourcescout/*`, `/api/golden-goose/opportunities` so existing clients keep working during cutover.

## 8. Cutover sequence

1. Build canonical schema + staging (Phase 1B foundation).
2. M1–M4 imports to staging (dry-run → promoted).
3. M5 identity reconciliation (dry-run → promoted).
4. Switch canonical endpoints to read canonical DB; legacy views active.
5. Deprecate legacy endpoints only after owner-verified equivalence.

## 9. What this resolves

- Phase 0 R1 (four stores) and R19 (GG vs scanner universes): single canonical `catalog_product` + `opportunity_assessment`.
- Preserves all non-negotiable data rules (null-not-zero, provenance, no fabrication).
