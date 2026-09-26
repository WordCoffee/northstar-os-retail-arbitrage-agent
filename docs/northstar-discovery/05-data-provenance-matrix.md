# 05 — Data Provenance Matrix

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNKNOWN (K).

## 1. Field provenance table

| Field | UI label | Type | Source | Last-updated | Provenance | Null behavior | Formula (if derived) | Misrepresents certainty? | Safe for financial/sourcing decision? |
|---|---|---|---|---|---|---|---|---|---|
| Product name/title | "Product" | str | varies by store (products.title, sourcescout_manifest.title, scanner name) | products.updated_at / cache generated_at | IMPORTED/CACHE | null allowed | — | Slight (different titles per store) | No — identity not canonical |
| ASIN | "ASIN" | str | products.asin / cache asin | same | IMPORTED | required | — | No | Identity key (but not canonical across stores) |
| Image | — | url | fixture image URLs in demo-data.js only | static | MOCKED | absent | — | N/A (frontends don't render real images) | N/A |
| Amazon price | "Price" | REAL | cache/offer provider | cached_at / fetched_at | CACHE/LIVE(gated) | null→hidden | — | Partially (cache age not surfaced in SPA) | No without freshness check |
| Supplier price (Costco) | "Costco COGS" | REAL | costco_client CSV / costco_api_client / costco_cost_reference | generated_at | IMPORTED/COMPUTED | 0.0 observed (meaning "unknown") | — | YES — 0.0 shown as if known | NO — must distinguish unknown |
| Estimated sales | "Sales/mo" | INTEGER | demand_estimator from BSR | cached | COMPUTED/ESTIMATED | null | log-log BSR→sales calibration | Labeled estimate | No |
| BSR/rank | "BSR" | INTEGER | provider (unwrangle/chocodata carry; dataforseo does NOT) | fetched_at | LIVE(gated)/CACHE | null | — | No | No |
| Seller count | "Seller" | INTEGER | offer roster providers | cached_at | CACHE | null | — | No | No |
| Buy Box | "Buy Box" | str (seller/fulfillment) | seller cache / offer providers | cached_at | CACHE | null | — | No | No |
| FBA fees | "FBA" | REAL | fee_engine table by size tier | static rules | COMPUTED | None when weight missing | size-tier table (see 04) | No | Yes (rules are deterministic) |
| Referral fees | — | REAL | fee_engine category rules | static rules | COMPUTED | None | category rule + min fee | No | Yes |
| ROI | "ROI" | REAL | fee_engine | static+input | COMPUTED | None when cogs=0 | net/cogs*100 | No | Yes if inputs fresh |
| Margin | "Margin" | REAL | scanner_data / product_analysis (2 defs exist) | computed | COMPUTED | — | net/price*100 OR net/costco_cost*100 | YES — two definitions in code | NO — ambiguous |
| Opportunity score | "Score" | INTEGER | opportunity_scorer (GG) / product_analysis | computed | COMPUTED | — | 0.35 profit+0.20 demand+0.15 comp+… | Subjective weights | No — decision aid |
| Eligibility | — | — | hard filters (GG) | computed | COMPUTED | fail-closed | profit/demand/competition/size/rating gates | No | No |
| Invoice/doc status | "invoice_verified_status" | str | suppliers table | updated_at | IMPORTED/STATIC | unverified default | — | No | Yes (fail-closed) |
| Keyword rank | — | — | schema-only (keyword_performance) | — | MISSING | — | — | N/A | No |
| Ad spend/sales/ACoS/CPC/CTR/CVR | — | — | word_coffee fixture / local calculator | — | IMPORTED (fixture) / COMPUTED (frontend) | — | see Auctioneer formula duplication | N/A (no live data) | No |
| Credits | "Balance" | INTEGER | credit_ledger (derived sum) | main.py:1717 | COMPUTED (display) | — | balance=allotment, consumed=0 | YES — shows balance as real while nothing consumes | NO |
| Model usage | — | — | usage_meter (exists, unwired) | — | MISSING | — | — | N/A | No |
| Provider status | "cloud key present" etc. | str/bool | `/api/v1/models` (key presence, live_armed) | live | RUNTIME | false | — | No | No |
| Integration status | "Authorization required" | str | gate flags/env | live | RUNTIME (env) | closed | — | No | No |

## 2. Two-margin-definition conflict (STATICALLY CONFIRMED)

- `net_margin_pct = net/price*100` — `scanner_data.py:265-267`, `fee_calculator.py:254-255`.
- `profit_margin_pct = net/costco_cost*100` — `product_analysis.py:376-380` (ROI-like over COGS).
- These are not the same number. Any UI showing "margin" must cite which.

## 3. ACoS formula duplication (STATICALLY CONFIRMED)

- `word_coffee.breakeven_acos` (word_coffee.py:47-66): `(asp − cogs − fba − asp*referral_pct)/asp*100`.
- `ad_pilot.compute_target_acos` (ad_pilot.py:327-355): `breakeven=gross/price*100; target=breakeven*(1−desired_margin/100)`.
- Frontend `Auctioneer.jsx:15-16`: `breakeven=(gross/price)*100; target=breakeven*0.7`.
- Three implementations; reconciliation required before Phase 1 (owner decision).

## 4. Provenance summary by store (see also `08`)

| Store | Contains | Provenance label mechanism | Consumers |
|---|---|---|---|
| `products` table (northstar.db) | 1,024 rows | `data_kind`, `provider_id`, `fetched_at`, `fresh_until` | dashboard_api, live_catalog, /api/products/finder, /api/v1/catalog/stocked |
| `scanner-search-cache*.json` | candidates | `fetched_at`, `source` | scanner pipeline, kirkland_discovery, GG/autothink context |
| `sourcescout_manifest.json` | 470 items | `generated_at` | /api/sourcescout* |
| `goose_scan_*.json` reports | opportunities | `meta.generated_at`, `mode` | /api/golden-goose/opportunities |
| `seller-offer-cache.json` | 247 ASIN offers | per-ASIN `cached_at` | offer_enrichment, data_migration |
| `enriched-offer-cache.json` | 263 ASIN offers | per-ASIN `cached_at` | offer_enrichment, market_snapshot_store |
| `costco-discovery-catalog.json` | 800 Costco records | `updated_at`, `price_status`, `cost_status` | scanner summary, kirkland pipeline |

## 5. Honesty rules present in code (STATICALLY CONFIRMED)

- Missing inputs stay `None`, never `0` (`fee_engine.py:17-19`).
- `costco_cost_reference: 0.0` appears in sourcescout items — a placeholder that must not be presented as a known cost.
- Unknown ROI guarded (cogs>0 required, `fee_engine.py:512`).
- `fresh_until` column filtering on read paths (`data_layer.py:363/523/535/546`, `readiness.py:96`).
- Cache TTLs: enriched/seller offer cache 24h default; market snapshot offers 7d / sales 30d / identity 90d (`market_snapshot_store.py`).

## 6. Misrepresentation risks (highest first)

1. **Costco cost = 0.0** displayed as a number (Prospector table computed `cost=0.00` when reference missing).
2. **Credits balance displayed as usable** while consumption is unwired.
3. **Two margin definitions** both labeled "margin".
4. **Cache age not surfaced** in the React SPA tables (only a footer note).
5. **"live" badges** in SPA pages (e.g., `badges={[{label:'live · scanner'}]}`) while data is cache-first — see `13` risk #R9.

## 7. Counting methods

- Row counts from read-only SQLite `mode=ro` (commands in `17` §E). Cache record counts from file peek + consumer analysis (S). No DB writes performed.
