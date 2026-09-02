# Northstar Kirkland Backend

> **DataForSEO provider integration: DISABLED / out-of-scope for launch.** Do not re-enable without new source code and a verified endpoint contract from DataForSEO support (provider contract mismatch `40402 Invalid Path` unresolved as of 2026-08-28).

Run with:

    uvicorn main:app --reload

Then open http://127.0.0.1:8000/ to use the Kirkland Product Scout, or
http://127.0.0.1:8000/docs for the API.

## API

> **Live-call containment (read first):** the server is **offline/cache-only
> by default**. `SCANNER_LIVE_ALLOWED` must be an explicit opt-in
> (`1`/`true`/`yes`/`on`) before ANY outbound provider call can happen.
> With it unset, `GET /`, `GET /health`, `GET /api/kirkland/scanner`, static
> assets, imports, and startup hooks make **zero** provider calls — page
> loads can never trigger Bright Data/Chocodata/Scavio/Easyparser/Canopy
> traffic. See "Safe commands" below.

- `GET /health` — service liveness (no dependencies, no secrets, no providers).
- `GET /api/kirkland/live` — scanner analysis. Cache-only while
  `SCANNER_LIVE_ALLOWED` is unset (zero provider calls); live results only
  after an explicit refresh with the gate enabled.
- `GET /api/kirkland/scanner` — Scout data used by the UI. Returns
  `{ "generated_at": <UTC ISO>, "status": "ok" | "no_candidates" |
  "upstream_unavailable", "summary": { "candidates_returned", "tier_found",
  "costco_catalog", "costco_discovery", "search_source", "enrichment_source",
  "scanner_mode" ("cache_only" | "live"), "live_allowed", "cache_status",
  "cache_fetched_at", "cache_source", "upstream_hint" }, "products": [...] }`.
  This endpoint is read-only and never triggers a live search itself: with
  `SCANNER_LIVE_ALLOWED` unset it serves the local search cache only; the
  live search backend (chosen by `SCANNER_SEARCH_SOURCE`, default
  `BRIGHTDATA` — Web Unlocker via `bright_data_client.py`; billing = free
  tier, 5,000 credits/month shared pool, 1 credit per request, renews on the
  1st, no rollover; `CHOCODATA` = free 1,000 credits on signup, no card — set
  `CHOCODATA_API_KEY`; `/amazon/search` costs 5 credits per call, so a full
  scan of 3 keywords × 2 pages costs 30 credits; `SCAVIO` = default fallback)
  only runs inside an explicit refresh with the gate enabled. When the active
  provider is out of credits or otherwise fails, the scanner reports
  `upstream_unavailable` with a human-readable `upstream_hint` naming the
  provider; setting `SCANNER_SEARCH_FALLBACK=CHOCODATA|SCAVIO` auto-falls
  back after a Bright Data failure. Products
  carry only allowlisted Scout fields (`verdict` is `Pass | Hold | Reject |
  Needs Fee Verification | null`, plus `offer_data_provider` /
  `enrichment_status` / `enriched_at` provenance); fields like
  `projected_net_profit`, `landed_cost`, fee breakdowns, and supplier or
  invoice metadata are calculator/internal fields and never appear here.
- `POST /api/kirkland/refresh` — **explicit live refresh, the only route
  that may trigger live provider searches.** Returns `403` unless
  `SCANNER_LIVE_ALLOWED=1`; with the gate on it runs one live scan
  (search + cost basis + economics) and returns
  `{ "status": "ok", "live_allowed": true, "generated_at", "candidates_returned" }`.
  Never called by the UI on page load.
- `POST /api/kirkland/scan`, `/api/kirkland/canopy` — pipeline stage
  endpoints.
- `GET /api/products/{asin}/offers` — on-demand per-ASIN seller roster and
  Buy Box detail (Easyparser OFFER op; 1 provider request per cache miss,
  5 credits/ASIN). Validates the ASIN (400 otherwise), serves the cached
  roster from `data/seller-offer-cache.json` when fresh
  (`SCANNER_SELLER_CACHE_TTL_HOURS`, default 24; `<=0` disables), and is
  only ever triggered by an explicit user click in the Scout detail row.
  While `SCANNER_LIVE_ALLOWED` is unset it returns the honest
  `offer_data_status: "unavailable"` note without any provider call.
  The response carries `offer_data_status` (`available | partial |
  provider_error | unavailable`), `offer_data_source`, `offer_data_fetched_at`,
  `offer_data_cached`, `buy_box{...}` (winner never inferred), the `offers[]`
  roster, `offers_returned`/`offers_complete`, and legacy keys
  (`buy_box_price`, `offer_count`, `request_zip_code`, `observed_at`,
  `credits_used`, `credits_remaining`, `data_gaps`). Unknown values stay
  null in the payload and render Unavailable/Unknown in the UI — never 0.
- `GET /api/products/{asin}/canopy` — on-demand Canopy product detail
  (explicit click only). Cache-only/offline while `SCANNER_LIVE_ALLOWED` is
  unset (`data_gaps` notes the disabled gate).

## Safe commands (live-call containment)

### Start the UI in offline/cache-only mode (the default — zero network)

```powershell
python -m uvicorn main:app --reload
# then open http://127.0.0.1:8000/ or http://127.0.0.1:8000/?ui_debug=1
```

No `SCANNER_LIVE_ALLOWED` needed and none should be set: page loads serve
the cached scan (`data/scanner-search-cache.json`) and Costco data only.
Verify with the scanner summary: `scanner_mode: "cache_only"` and
`live_allowed: false`.

### Intentionally run a live refresh (explicit opt-in)

```powershell
$env:SCANNER_LIVE_ALLOWED = "1"
python -m uvicorn main:app --reload
# then POST once:  Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/kirkland/refresh
# (GET /api/kirkland/scanner afterwards serves the refreshed cache)
Remove-Item Env:SCANNER_LIVE_ALLOWED   # back to offline mode
```

The canonical refresh remains the pipeline: `npm run search` /
`npm run normalize` / `npm run score` (Node side), and the Costco catalog
refresh is `python costco_api_client.py refresh` (Scheduled Task
`NorthstarCostcoCatalogRefresh`, `COSTCO_CATALOG_SOURCE` default OFF). These
are explicit operator commands and are the intended live paths; the web
server must never call providers on its own.

### Guardrails (enforced in code, tested offline)

- `live_gate.live_enabled()` — single gate, default **off**
  (`SCANNER_LIVE_ALLOWED` strict boolean via `env_flags`).
- `amazon_search.search_kirkland_products` — returns `[]` before touching a
  provider when the gate is off.
- `offer_enrichment._enrichment_mode` — forced `"OFF"` (cache-only scan)
  when the gate is off, regardless of `SCANNER_OFFER_ENRICHMENT`.
- `offer_enrichment.get_seller_offer_contract` — cache hits still served;
  live Easyparser fetch refused (`unavailable`) when the gate is off.
- `canopy_client.get_canopy_product` — offline shape when the gate is off.
- `POST /api/kirkland/refresh` — 403 when the gate is off.
- `test_live_containment.py` (17 tests) proves zero provider calls from
  `GET /`, `GET /?ui_debug=1`, `GET /health`, `GET /api/kirkland/scanner`,
  `GET /api/kirkland/live`, static routes, and the on-demand GETs, with
  every provider client patched to fail loudly.

## Costco CSV contract

`data/costco-items.csv` (at the project root) must have these columns:

    item_name,costco_cost

`costco_cost` is the actual source cost of the exact sellable Amazon unit
(not the case price, no repack or bundle assumptions). Lookup matches the
item name exactly first, then falls back to a fuzzy match (>= 0.70). Ambiguous
exact matches are skipped and logged. Missing costs are never treated as $0.
Weight is not a Scout input and is never required.

## Costco catalog via OpenWebNinja (optional)

Set `COSTCO_CATALOG_SOURCE=OPENWEBNINJA` and `OPENWEBNINJA_API_KEY` in `.env`
to build the Kirkland Signature discovery catalog from Costco US/Canada
online search results (one request per query; free tier 100 requests/month,
then $0.005/request — this is a catalog-refresh workflow, never per-ASIN
enrichment):

    python costco_api_client.py status          # connector health, archive age
    python costco_api_client.py refresh         # fetch + archive + snapshot + export CSV
    python costco_api_client.py export          # re-export CSV from the archive, no network

`COSTCO_CATALOG_SOURCE` defaults to `OFF`, in which case only the local CSV
is used and the connector performs zero network calls. Refresh is always
explicit (CLI or scheduled), capped at `COSTCO_CATALOG_MAX_PAGES` (default 1
request), and never runs inside the scanner. An Unwrangle Business Delivery
source (`COSTCO_CATALOG_SOURCE=UNWRANGLE` + `UNWRANGLE_API_KEY`) is also
supported with the same workflow (10 credits per search page, up to 96
products/page) and labels its costs `business_delivery_online`.

### Discovery catalog (archive-first, append-only)

Every refresh appends new records to the append-only archive
`data/costco-discovery-catalog.json`; existing records are **never
overwritten or mutated**. Each record captures: `item_name`, `raw_title`
(verbatim), `costco_item_id`, `source_url` (derived as
`https://www.costco.com/.product.<id>.html` with `url_derived: true` when
the API sends no URL), `regular_price` / `sale_price` / `price_status`,
`pack_size` / `unit_count`, `cost_basis` (`costco_online` for OpenWebNinja,
`business_delivery_online` for Unwrangle), `cost_status: "discovery_only"`,
`source`, `location` (delivery ZIP + Business Center), `availability`,
`promo`, `brand`, `fetched_at`.

Location and rate limiting (`.env`):

    COSTCO_DELIVERY_ZIP=75201                       # defined delivery ZIP (default 75201)
    COSTCO_BUSINESS_CENTER=Dallas Business Center   # review location (default)
    COSTCO_CATALOG_REQUEST_DELAY_SECONDS=2.0        # sleep between requests
    COSTCO_FRESHNESS_THRESHOLD_DAYS=8               # Scout staleness window (default 8)

### Freshness check (Scout)

The Scout UI shows a catalog freshness line fed by
`costco_api_client.last_run_status()` (read-only, zero network) in
`GET /api/kirkland/scanner` → `summary.costco_discovery`:

- `fresh`: the latest run completed cleanly (`status: ok`, no `stop_reason`)
  within `COSTCO_FRESHNESS_THRESHOLD_DAYS` (default 8 — weekly run plus one
  day of grace). The UI shows last run time, fetched item count, delivery
  ZIP + Business Center, and status.
- `stale`: the latest run was blocked, rate-limited, failed, partial, or
  disabled, or is older than the threshold. The UI labels online discovery
  data **STALE** with the stop reason and reminds the operator to confirm
  prices at the Business Center before purchase.
- `unknown`: no run report exists yet (e.g. before the first scheduled
  run).

Every run report now carries `generated_at` so freshness can be verified.

Deduplication is conservative and conflict-safe:

- Within-run duplicate item IDs are **skipped**.
- A same-ID item with a different title, or a same-title item with a
  different pack size vs. the latest archive record, is **held for review**
  (`title_conflict` / `pack_size_conflict`) and never attached a cost.
- Items missing a name or a positive price are held for review too.

Rate limiting and stop-on-block: requests are spaced by
`COSTCO_CATALOG_REQUEST_DELAY_SECONDS`, and the run stops on the first
block/error — HTTP 401/403 = `blocked`, 429 = `rate_limited`, anything else
= `failed`. A stopped run preserves the last-good archive, snapshot, and
CSV.

Each run writes a run report (`data/costco-catalog-run-report.json`) with
`fetched` / `updated` / `skipped` / `held_for_review` / `failed` counts and
the record lists behind them. `data/costco-api-catalog.json` remains the
last-run snapshot view (items plus `skipped`, `held_for_review`, `stale_rows`,
`location`, `stop_reason`); the archive is the full audit trail.

### Scheduled refresh

Windows Task Scheduler task `NorthstarCostcoCatalogRefresh` runs
`refresh-costco-catalog.ps1` weekly on Sunday 03:00 (off-peak). Logs to
`data/costco-refresh.log`. There are **zero automatic retries**: the
connector stops on the first block/rate-limit/error (401/403 = `blocked`,
429 = `rate_limited`, anything else = `failed`) and neither the wrapper nor
the task retries — the next Sunday run is the natural next attempt.
Interactive logon, Limited run level, `StartWhenAvailable` catches missed
runs (e.g. machine asleep at 03:00). Inspect
`data/costco-catalog-run-report.json` after each run before touching the
archive.

Cost guardrails:

- API prices are Costco online prices and carry a nominal markup over
  walk-in Business Center pricing. Until verified against an actual
  Business Center invoice / confirmed walk-in price, every cost is labeled
  `cost_status: "discovery_only"` (never invoice-confirmed, never purchase
  authorization), a margin buffer is baked into the exported CSV cost
  (`COSTCO_API_COST_BUFFER_PERCENT`, default 10), and costs count only as
  discovery and preliminary ROI. Final unit economics must come from the
  invoice.
- Matching updates existing CSV rows by Costco item id (when the CSV carries
  one), then normalized exact title, then pack-size-aware fuzzy title
  (>= 0.70). Pack-size conflicts, duplicate names, and items without a price
  are preserved in the snapshot's `unmatched` list for analyst review — the
  connector never forces a fuzzy match that could attach the wrong cost.
- Stale CSV rows (no longer present in the API results) are preserved, not
  deleted.

## FBA fee and unit economics (versioned fee engine)

All unit economics are computed in the backend **before** the UI renders,
by `fee_engine.py` against versioned rules in
`amazon_us_fee_rules_2026.py` (`RULES_VERSION`; referral fee schedule,
FBA size-tier table with the 3.5% fuel/logistics surcharge, unit-cost
defaults). The UI only formats and displays these values.

1. Referral fee: an Amazon browse node (from the product-page breadcrumb
   parser, zero extra requests) or a structured `amazon_category` match
   wins (`verified_category`); a breadcrumb-only category maps to the
   matching rule but stays `inferred` (confirm in Seller Central); no
   metadata → default Everything Else 15% (`default_category`, "verify in
   Seller Central" note); no price → `unavailable`. Each row carries
   `browse_node_id` + `category_resolution_source/confidence/note`.
   `CATEGORY_RESOLVER_VERSION` versions the resolver (independent of
   `RULES_VERSION`).
2. FBA fee: a listing-reported fee wins (`listing_reported`); otherwise a
   table estimate from package weight (+ dimensions), splitting base fee
   and 3.5% surcharge; oversized or unknown weight stays
   `needs_revenue_calculator_verification` / `weight_unavailable` → `None`,
   never invented.
3. Unit costs: inbound 0.35, prep 0.25, packaging 0.00, return reserve 2%
   (env-configurable).
4. `net_profit` and `roi_pct` follow from those, with an
   `economics_confidence` tier:
   - `estimated` — full fee stack included (`estimated_fee_stack`)
   - `provisional` — FBA fee missing and **excluded** from the numbers
     (`needs_fee_verification`; never final, never called profitable)
   - `unavailable` — missing sale price or Costco cost (values `null`,
     never 0)
   Missing values are always `null` (JSON null, rendered "Unavailable"),
   never `0` or `$0.00` — except an explicitly configured `0.00`
   (packaging cost).

`costco_cost_basis` (`invoice_confirmed | costco_online | estimated |
unavailable`) records the provenance of every cost basis. Profit tiering
and ROI/margin gating apply to `estimated` rows only. Run the three
mocked example rows offline with `python examples_fee_engine.py`.

### Pack/Variant Match gate (purchase-analysis policy)

Estimated economics require a hard product-equivalence fingerprint match
(`costco_client.product_equivalence()`): brand, product line/formula,
flavor, net weight, pack/count, and UPC/EAN when the catalog row carries
one. A fuzzy name match may still surface a research candidate, but it
sets `costco_cost_basis = candidate_match`,
`economics_status = mapping_verification_required`, and `pack_match`
(`exact | invoice_confirmed | candidate | mismatch | unknown`) in the UI —
with net profit, ROI, tier, and verdict all null. Nothing below `exact`
(or `invoice_confirmed`) is ever Tier/Pass/Scale eligible.

### Three-layer Costco cost catalog

The Costco side of the equation is a three-layer catalog
(`costco_api_client.py`), resolved by
`resolve_costco_cost(amazon_name)` in priority order:

1. **Layer 3 — `costco_invoice_confirmed`** (`data/costco-invoice-confirmed.json`):
   Business Center invoice/order-history rows imported with `python
   costco_api_client.py invoices import --path X` (CSV/JSON). Real paid
   unit costs with `cost_basis = invoice_confirmed`; only an
   invoice-confirmed row that fingerprint-matches exactly may authorize a
   purchase (after Amazon listing checks). Duplicate (invoice, item)
   pairs are held for review.
2. **Layer 2 — `costco_product_detail`** (`data/costco-product-detail.json`):
   per-item detail records fetched only for Costco item IDs that are
   potential Amazon matches (`details refresh --item-ids I,J`, UNWRANGLE
   `costco_business_detail`, gated by `COSTCO_CATALOG_DETAIL_ENABLED=1`;
   OPENWEBNINJA is a documented data gap) or imported offline (`details
   import --path X`). Research only — `cost_status = "detail_only"`: an
   exact fingerprint here enables net/ROI but never authorizes a buy.
3. **Layer 1 — `costco_catalog_live`**: the discovery snapshot/archive
   (search pages → `data/costco-api-catalog.json`, append-only archive).
   Every normalized record carries the structured schema (`costco_item_id`,
   `upc_or_ean`, `brand`, `product_line`, `formula_or_flavor`,
   `net_weight`, `unit_of_measure`, `pack_count`, `case_count`,
   `current_price`, `price_basis`, `warehouse_or_zip`, `product_url`,
   `last_seen_at`, `source`) — fields the provider does not return stay
   `null`, never invented. The legacy `data/costco-items.csv` remains the
   third priority exact source (`estimated` basis).

Exact matches resolve invoice_confirmed > product_detail > CSV; any
non-exact (candidate/mismatch/unknown) surfaces as `candidate_match` —
research view only, never COGS/ROI. `product_analysis.get_costco_price`
wraps the resolver, so the scanner never touches layers 2-3 directly.

Every derived value carries `confidence` / `status` / `note` provenance;
the full pre-UI field catalog and the "UI is a pure renderer" invariant
are in `docs/pre_ui_calculation_pipeline.md`.

## Per-ASIN offer enrichment (optional)

Set `SCANNER_OFFER_ENRICHMENT` in `.env` to enrich each matched ASIN with
live offer data before scoring. Unset, empty, `0`, `false`, `no`, `off`,
`OFF`, or any invalid string = **disabled (cache-only)**: the scanner
reads only the local candidate cache (`data/scanner-search-cache.json`,
written after a fully successful live search) plus local Costco data, and
makes zero outbound calls. Explicit values:

    SCANNER_OFFER_ENRICHMENT=1|true|yes|on  # enabled, default provider (Bright Data)
    SCANNER_OFFER_ENRICHMENT=BRIGHTDATA     # Web Unlocker product page per ASIN (1 credit from free pool)
    SCANNER_OFFER_ENRICHMENT=AUTO           # Easyparser first, Bright Data fallback
    SCANNER_OFFER_ENRICHMENT=EASYPARSER     # fast OFFER operation per ASIN
    SCANNER_OFFER_ENRICHMENT=CHOCODATA      # 5 credits per ASIN product page
    SCANNER_OFFER_ENRICHMENT=UNWRANGLE      # 1 credit per ASIN (US)

Bright Data (the default provider when enrichment is explicitly enabled)
fetches the product page through the Web Unlocker via
`bright_data_client.get_product_detail` — title, Buy Box price, new-offers
range, weight (drives the FBA fee estimate), sales rank, rating/reviews, and
monthly sales — and is gated to rows that can actually score: a Costco cost
exists AND the Pack/Variant fingerprint is exact or invoice-confirmed.
Candidate/mismatch/unknown rows (research view only) and `OFF` mode get the
offline placeholder at zero credit cost (1 credit per request from the
5,000/month free pool; `AUTO`/Easyparser fallbacks remain). Successful live
fetches (`complete`/`partial`) are cached per-ASIN in
`data/enriched-offer-cache.json` (`SCANNER_OFFER_CACHE_PATH`, project-root
relative; `SCANNER_OFFER_CACHE_TTL_HOURS`, default 24, `<= 0` disables the
cache) so repeat scans spend zero credits on recently-fetched ASINs; offline
placeholders and failed fetches are never cached. Weight is read from the
"Package Dimensions" row (the shippable weight — preferred over Amazon's
often per-unit "Item Weight") or "Item Weight" as fallback; pages with
neither stay Needs Fee Verification rather than guessing.
Easyparser supplies: offer count (total sellers), observed FBA/FBM counts,
Buy Box price, and the offer price range (low/high) used for the Buy Box
stability ranking factor. Values a
provider cannot supply stay `None` (never zeros) — the product stays in
Needs Fee Verification rather than guessing. Provider failures fall back
to the offline placeholder, so the Scout never breaks.

Every product carries data provenance: `offer_data_provider`
(`easyparser` | `brightdata` | `offline`), `enrichment_status`
(`complete` | `partial` | `failed` | `offline` | `invalid_asin`), and
`enriched_at` (UTC ISO when live data was obtained). The Scout UI shows a
small provider/status chip on enriched rows so every decision can trace
which source produced the values.

## Controlled Easyparser batch enrichment (manual, capped)

A separate, operator-driven tool that fills a local **market snapshot
store** (`data/amazon-market-snapshots.json`) with per-ASIN Easyparser
OFFER results — never during a scan. The scanner stays zero-network by
default; snapshots are merged read-only into cache-only rows only when the
operator opts in (see "Merge into the Scout" below).

### Candidate cache vs snapshot store

- `data/scanner-search-cache.json` (Bright Data backup kept alongside) —
  the scan candidate pool. Never written by this tool.
- `data/amazon-market-snapshots.json` (`SCANNER_MARKET_SNAPSHOT_PATH`,
  project-root relative) — per-ASIN snapshots keyed by ASIN, each saved
  atomically (tmp + rename + verify-by-reread) so an interrupted batch
  never corrupts earlier results. A corrupt store is refused, never
  overwritten.
- `data/enrichment-run-report.json` (`SCANNER_ENRICH_RUN_REPORT_PATH`) —
  last-run record: mode, planned/attempted/succeeded/partial/failed/
  skipped-fresh/skipped-cap/skipped-retry-ineligible counts, credits
  reported/estimated, stop reason, duration, and per-ASIN errors.

Neither file is touched by scans, tests, or dry runs. No credentials are
stored.

### Field honesty

A snapshot stores only what the provider returned. Easyparser OFFER never
supplies UPC/EAN/GTIN, weight/dimensions, brand, category, FBA fee, sales
rank, or monthly sales — those fields stay `null` in the snapshot and the
Scout keeps rendering them Unknown (never 0, never invented). Seller
counts distinguish observed (`offers_returned`, `fba_observed`,
`fbm_observed`, `amazon_observed`) from claimed (`offer_count` from the
provider), and `offers_complete = false` whenever the returned sample is
shorter than the claimed count. A failed request preserves the prior valid
snapshot for that ASIN.

### Modes (terminology)

- `status` — read-only summary of the store and candidate cache. Zero
  network.
- `dry-run` — plans the batch (which ASINs would be requested, projected
  credits at 5 per ASIN) without issuing a single request. Zero network.
- `preflight` — exactly **one** live Easyparser OFFER for one explicit
  ASIN. Requires `--live --asin <ASIN> --limit 1 --max-requests 1
  --max-credits N`.
- `batch` — live, cache-driven, capped. Requires `--live --limit N
  --max-requests N --max-credits N`; `--limit` never defaults to the whole
  cache. `--asin` is refused in batch mode (use preflight for a single
  ASIN).

Live commands (preflight/batch) are refused unless all three finite caps
are supplied; dry-run/status never need `--live`. Only Easyparser is ever
called — never other providers.

### Budget and resume

Budget = requests used + credits used (provider-reported `credits_used`
when returned, else the 5.0/ASIN estimate). The run stops at
`max_requests`, `max_credits`, or completion; `skipped_cap` records what
the cap left over. Resume is safe: fresh successes (available/partial,
within the offers window) are skipped (`skipped_fresh`), retry-eligible
failures (attempts < 3, no permanent gap) are re-attempted,
retry-ineligible rows are counted and left alone. `--retries N` is an
opt-in bounded re-attempt count, recorded per run; offline tests never
retry. Permanent gaps (missing API key, invalid ASIN) are never retried.

### Exact manual commands (operator-run, Easyparser credits required)

```powershell
# Plan the full 234-ASIN batch without any request (zero network)
python enrich_cached_asins.py --mode dry-run --limit 234

# Read-only store/cache summary (zero network)
python enrich_cached_asins.py --mode status

# Validate the pipeline with exactly ONE live request
python enrich_cached_asins.py --mode preflight --live --asin B0XXXXXXXXXX --limit 1 --max-requests 1 --max-credits N

# Small validation batch (10 ASINs, 10 requests, ~50 credits at 5/ASIN)
python enrich_cached_asins.py --mode batch --live --limit 10 --max-requests 10 --max-credits 60

# Full capped batch (234 ASINs, 234 requests, ~1,170 credits at 5/ASIN)
python enrich_cached_asins.py --mode batch --live --limit 234 --max-requests 234 --max-credits 1300
```

Freshness windows: offers 7 days, sales 30 days, identity 90 days
(`snapshot_freshness_status`). Interrupted batches resume on the next run
and the run report lists exactly what happened.

### Fixed 20-ASIN proof-batch validation (guarded runner)

`proof_batch_run.py` binds a run to exactly the ASINs of the named preflight
(`data/batch/proof-batch-preflight-20260818T060549Z.json`, fingerprint-bound;
see `docs/proof-batch-guarded-execution-design.md` and
`docs/proof-batch-final-readiness-audit.md`). `dry-run` (prints the exact
20 ASINs, scope/fields, caps, credit-accounting status, output dir, the 3
expected mapping-review ASINs, every hard-stop condition, and
`DRY RUN ONLY — NO PROVIDER CALLS, NO CREDITS USED, NO LIVE SNAPSHOT
WRITTEN`), `fixture-run` (synthetic adapter, labeled `synthetic_fixture`),
and `report` (verifies the results↔run-manifest↔preflight fingerprint
linkage; per-ASIN `outcome_status`; `Passing provider-data validation does
not authorize a purchase.`) are zero network. `run --live` exists and is
wired to a real-data-ready Easyparser adapter
(`proof_batch_easyparser_adapter.py`) behind the full guard stack. The
adapter is **armed-capable but disabled by default**: a second, non-secret,
read-only runtime gate `PROOF_BATCH_LIVE_ARMED=1` (exactly `"1"` enables; absent
/ blank / `false` / `"0"` / `"no"` stay disabled) makes every armed construction
refuse at the adapter gate — `run --live` always exits 2 with "easyparser-live
adapter is not armed … no provider call was made" until the operator sets
`PROOF_BATCH_LIVE_ARMED=1` in their own shell (never mutated or printed by the
code) AND `SCANNER_LIVE_ALLOWED=1` is set. Writes go ONLY under
`data/batch/live-validation-runs/<run_id>/`. A passing live data comparison does
not authorize sourcing or purchases.

```powershell
python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100
python proof_batch_run.py fixture-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100 --out-dir data/batch/live-validation-runs/<run_id>
python proof_batch_run.py report --run-dir data/batch/live-validation-runs/<run_id>
# Live run (separately approved; NOT RUN here): in your own shell,
#   $env:SCANNER_LIVE_ALLOWED="1"
#   $env:PROOF_BATCH_LIVE_ARMED="1"
# then: python proof_batch_run.py run --live --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100
# then remove both env vars.
```

### Merge into the Scout (opt-in, read-only)

Set `SCANNER_LOCAL_SNAPSHOT_MERGE=1` in `.env` **and** keep
`SCANNER_OFFER_ENRICHMENT=OFF` to have cache-only scanner rows overlay
snapshot values at read time: Buy Box price (as `amazon_price`), observed
seller counts (`snapshot_fbm_sellers`, `snapshot_amazon_sellers`), Buy Box
details, and `snapshot_*` provenance keys. Strict `env_flag` semantics —
anything but `1|true|yes|on` leaves merging off. The merge never forces or
upgrades a Costco match, never changes economics tiers, and unknowns stay
Unknown; the Scout UI renders a compact "Local market snapshot" block in
the Market & Seller Intelligence group (status badge, provenance, observed
counts, Buy Box, stale/failed/partial disclosures) with no auto-refresh
and no provider calls from the browser.

## Manual import (offline, zero network)

`manual_import.py` populates the existing candidate cache
(`data/scanner-search-cache.json` relative to this backend, via the same
`amazon_search.save_cached_candidates()` writer) from a local JSON or CSV
file, so the Scout can analyze Amazon candidates against the local
Kirkland/Costco catalog in cache-only mode (`SCANNER_OFFER_ENRICHMENT=OFF`).
The import NEVER makes a network request — no search/enrichment/offers
provider, no Amazon, no Costco API — and never consumes credits. All
downstream analysis (Costco match, cost basis, fee-engine economics,
verdicts) is the existing pipeline; only the candidate source differs.

    python manual_import.py --input path/to/file.json
    python manual_import.py --input path/to/file.csv
    python manual_import.py --input path --dry-run     # validate only, never writes
    python manual_import.py --input path --replace     # overwrite an existing valid cache
    python manual_import.py --input path --source my_label
    python manual_import.py --input path --report out.json

Exit codes: 0 success; 2 zero valid candidates or malformed file; 3
existing valid cache without `--replace`; 4 cache write/report-file
failure. JSON input is either a top-level array or an object with a
`candidates` array (decoded with a streaming parser, one candidate at a
time — memory-safe for hundreds of candidates with thousands of nested
offers); CSV uses a streaming `csv.DictReader` (first row = header).
Templates: `templates/manual-import-template.json` and
`templates/manual-import-template.csv` (fictional example rows only).

Candidate fields: `asin` (required, 10 alphanumeric), `title`/`name`
(required), `product_url`/`amazon_url`, `amazon_price`,
`amazon_shipping`, `buy_box_price`, `buy_box_shipping`,
`monthly_sales_estimate`/`estimated_monthly_sales`/`monthly_sales`,
`monthly_sales_estimated` (bool), `total_sellers`,
`fba_seller_count`/`fba_sellers`, `fbm_seller_count`/`fbm_sellers`,
`buy_box_seller_name`, `buy_box_fulfillment` (FBA|FBM|Amazon|unknown),
`referral_fee`, `fba_fee`, `weight_lbs`, `upc`, `gtin`, `ean`,
`pack_count`, `unit_count`, `weight`, `volume`, `product_form`,
`variant`, `flavor`, `scent`, `amazon_category`, `browse_node_id`,
`observed_at` (ISO-8601, normalized to UTC), and nested `offers[]`
(`seller_name`, `seller_id`, `fulfillment`, `item_price`,
`shipping_price`, `landed_price`, `condition`, `is_buy_box_winner`,
`is_prime`, `seller_rating`, `rating_count`, `observed_at`).
Unknown/missing values stay `null` (render Unknown/Unavailable in the UI)
— never 0, never fabricated; unknown input keys are ignored. Numbers must
be finite and non-negative; invalid rows are rejected with a reason, not
silently dropped.

Rules and labels:

1. Dedupe by ASIN is deterministic: the newest valid `observed_at` wins;
   ties or missing `observed_at` keep the last valid input row.
2. Provenance: `source` = the `--source` label (default `manual_import`);
   `imported_at` is always the UTC import time; `observed_at` is kept
   only when supplied and valid (`live_observed` true only then);
   `enrichment_status` stays `offline`; `enriched_at` = `observed_at` or
   `imported_at`. Imported data is never presented as live, verified, or
   provider-fetched. The cache is tagged `search_terms: ["manual_import"]`
   (provenance marker — no live search is performed).
3. Economics stay honest: missing price or missing Costco COGS → net/ROI
   `null`; missing FBA fee → the existing provisional/Needs Fee
   Verification tier; imported shipping is preserved in the cache but
   never used in economics. High-confidence manual-import rows keep
   their estimated economics and get "Verify UPC, pack size, and variant
   before buying." appended to the economics note.
4. Cache protection: a malformed or fully-invalid import never touches an
   existing cache; zero valid candidates or a failed (or swallowed) write
   preserves the prior cache — the write is verified by re-reading the
   cache afterwards (`candidate_count` + `source`); an existing valid
   cache requires `--replace`; `--dry-run` never writes.
5. Report counts (also written as JSON with `--report`): `accepted` =
   valid rows kept after dedupe; `rejected` = invalid candidate rows;
   `duplicated` = valid rows dropped by ASIN dedupe;
   `missing_market_data` = accepted rows with neither `amazon_price` nor
   `buy_box_price`; `match_ready` = accepted rows with an Amazon price
   basis AND a local Costco match tier of exact | invoice_confirmed |
   high_confidence.

## Batch audit tooling (offline — zero live calls, zero writes to source data)

Three read-only Python tools turn the locally cached candidates into an
auditable opportunity pipeline. All three never call the network, never
modify `data/scanner-search-cache.json` or its backup, and never touch
the Costco catalog/snapshot/invoice files. Force
`SCANNER_OFFER_ENRICHMENT=OFF` on every run so the scanner stays
cache-only.

    python inspect_cache.py                      # integrity + SHA-256 + field coverage
    python coverage_report.py --out report.json --csv review-queue.csv --top 20
    python costco_api_client.py mapping status   # verified-mapping ledger
    python costco_api_client.py mapping import --path verified-mappings.json

`inspect_cache.py` (read-only): exists/parseable/size/SHA-256, schema
version, source, fetched_at, freshness label, declared vs observed
candidate count, per-field presence, fields absent on every product.
Exit 0 ok, 2 not ok.

`coverage_report.py` (read-only): batch metrics with visible denominators
— match coverage (exact + invoice-confirmed + high-confidence over
eligible rows), Costco COGS coverage, economics-ready, opportunity
complete — plus per-layer counts, missing-data reasons, verification-task
and readiness counts, title-similarity histogram (unmatched rows only),
and a 24-column review queue. `--top N` exports the N best non-mismatch
rows by backend opportunity score (requires `--csv`). Output files are
written only to the explicit `--out`/`--csv` paths.

`costco_api_client.py mapping import` loads a verified ASIN → Costco
item_name ledger (`data/costco-amazon-mapping.json`, env
`COSTCO_AMAZON_MAPPING_PATH`). JSON is a flat `{"ASIN": "item name"}`
object; CSV header `asin,item_name`. Append-only: an existing ASIN with a
different name is held for review, never overwritten; invalid ASINs
(`^[A-Za-z0-9]{10}$`) and empty names are held. Ledger entries resolve as
exact identity matches (invoice cost → purchase-authorized, detail →
detail_only, CSV → estimated; mapped but no cost anywhere →
`ledger_only`, never invented).

### 9-step workflow

1. `python inspect_cache.py` — confirm the cache is intact and note the
   SHA-256 (change detection baseline).
2. `python costco_api_client.py mapping status` — ledger size; import
   any analyst-verified ASIN→item mappings first.
3. `python coverage_report.py` — print metrics; read the denominators,
   not just the numerators.
4. `python coverage_report.py --out data/batch/report.json --csv data/batch/review-queue.csv`
   — write the artifacts for the working session (explicit paths only).
5. `python coverage_report.py --csv data/batch/top.csv --top 20` — top
   ranked, non-mismatch opportunities by backend score.
6. Open the review queue; work the `verification_task` /
   `recommended_next_step` columns (verify UPC/pack/count/weight/variant
   at Costco, confirm category and FBA fee in Seller Central, invoice the
   Business Center order).
7. Import verified mappings: `python costco_api_client.py mapping import --path ...`.
8. Re-run steps 3–5; confirm coverage improved and no row regressed to
   mismatch.
9. Re-run `python inspect_cache.py` and compare SHA-256 — the cache must
   be byte-identical to step 1.

### Phase 3 intel runbook (offline — demand, competition, portfolio)

Five read-only CLIs add Phase 3 planning layers on top of the local
cache and snapshot store. Same rules: zero network, writes go only to
the explicit `--output`/`--audit` paths, and unknown stays Unknown
(never 0, never a synthesized aggregate).

    python demand_report.py --input data/scanner-search-cache.json --output data/batch/demand-report.json
    python competition_report.py --input data/amazon-market-snapshots.json --output data/batch/competition-report.json
    python portfolio_report.py --input data/scanner-search-cache.json --output data/batch/portfolio-report.json
    python opportunity_export.py --input data/scanner-search-cache.json --output data/batch/top-opportunities.csv --top 50
    python mapping_review.py --input data/scanner-search-cache.json --output data/batch/mapping-review.csv --coverage-output data/batch/mapping-coverage.json
    python mapping_review.py --validate-import data/batch/proposed-mapping.csv --validate-output data/batch/import-validation.json
    python mapping_review.py --input data/scanner-search-cache.json --output data/batch/mapping-review.csv --audit data/batch/mapping-review-audit.jsonl

- `demand_report.py` — per-candidate monthly demand estimate from
  listing/provider signals only (`monthly_sales_estimate`, BSR +
  category). Never estimates from price, title, reviews, seller counts,
  or Costco cost. Model: 6 category curves, log-log interpolation,
  confidence tiers; `monthly_sales_estimated` never None.
- `competition_report.py` — seller-competition picture from the local
  Easyparser snapshot store. **Zero seller counts appear only under
  explicit proof** (`data_status available` + `offers_complete` exactly
  True + `claimed_offer_count` exactly 0 + `offers_returned` exactly 0);
  every other empty/partial/failed/unavailable roster is Unknown with a
  roster reason. Seller-share stays Unknown here (snapshots carry no
  monthly sales estimate).
- `portfolio_report.py` — runs the exact cache-only scanner pipeline
  (forces `SCANNER_OFFER_ENRICHMENT=OFF` + `SCANNER_LOCAL_SNAPSHOT_MERGE=1`
  in-process) and aggregates readiness, next step, category, risk flags,
  completeness, and monthly revenue/profit pools. Sums are computed only
  over rows that carry the value; `rows_with_value` is reported beside
  every sum.
- `opportunity_export.py` — top-N opportunities by `opportunity_score`
  as CSV. Unknown rows (no score) sort after every scored row — they
  never rank above a complete positive. "est."-provenance columns travel
  with every modeled value.
- `mapping_review.py` — one CSV row per candidate with match quality,
  evidence, conflicts, verification task, and the suggested mapping
  action (`confirm_exact_mapping`, `verify_upc`, `verify_count_pack`,
  `verify_weight`, `verify_variant`, `verify_flavor`, `reject_mapping`,
  `no_costco_candidate`). `--coverage-output` writes action/ledger-hit/
  conflict/missing-identifier metrics. `--validate-import` classifies a
  proposed ledger import (ledger-confirmable / research / rejected /
  held-for-review) read-only — the ledger's only writer remains
  `costco_api_client.py mapping import` (append-only, conflict-held).
  `--audit` appends one JSONL record per run.

Revenue rule (portfolio layer): `estimated_monthly_revenue =
estimated_monthly_sales × observed_buy_box_landed_price` only when the
Buy Box landed price is explicitly supplied; fallback only to the
separately documented `amazon_price` in the candidate record
(`candidate_amazon_price`); never an arbitrary seller-offer price;
neither → Unknown (`monthly_revenue_basis` reports which path won).

### No-live-call runbook (PowerShell-safe)

    $env:SCANNER_OFFER_ENRICHMENT = "OFF"
    python inspect_cache.py
    python coverage_report.py --out data/batch/report.json --csv data/batch/review-queue.csv --top 20
    python costco_api_client.py mapping status
    python -m unittest discover -s . -p "test_*.py"
    node test_ui_display.cjs

Never run `npm run search`, the Uvicorn server, or `test_scavio.py` in
this mode — those are live paths.

### Definitions (display vocabulary, computed backend-side)

- Freshness: per-row label from the newest of `enriched_at`,
  `observed_at`, `imported_at`, or the cache `fetched_at`; Fresh <7 days,
  Aging 8–30 days, Stale >30 days, Unknown. `freshness_basis` names which
  timestamp won. Display only — no auto-refresh.
- Match readiness (`match_readiness`): `exact_ready` (exact /
  invoice-confirmed), `likely_verify_pack_upc` (high-confidence),
  `candidate_manual_review`, `blocked_mismatch`, `no_costco_match`.
- Opportunity readiness (`opportunity_readiness`): one honest label —
  `blocked_mismatch`, `needs_costco_match`, `needs_price`,
  `economics_provisional`, `needs_identity_verification`,
  `needs_sales_data`, `needs_seller_data`, `complete_opportunity`,
  `insufficient_data`. `recommended_next_step` mirrors it
  (`reject_mismatch`, `find_costco_match`, `await_data`,
  `get_fba_fee_preview`, `verify_upc_and_variant`,
  `enrich_sales_and_sellers`, `verify_costco_pack_and_price`,
  `review_top_opportunity`).
- Verification tasks (`verification_tasks` + primary): `none`,
  `verify_upc`, `verify_pack`, `verify_count`, `verify_weight`,
  `verify_variant`, `verify_flavor`, `verify_listing`,
  `verify_costco_price`, `verify_fba_fee`, `enrich_sales`,
  `enrich_sellers`, `blocked_mismatch`, `no_costco_candidate`.
- Data completeness (`data_completeness_score`): 0–100, one point per
  present dimension (identity, price, COGS, economics tier, FBA fee,
  sales, sellers ×2, match quality, freshness). Missing stays missing —
  no fabricated zeros.
- Opportunity score (backend): mismatch → 0 + Blocked; missing price or
  COGS → no score with reasons (never ranked 0). Components: economics
  40 pts (ROI + net profit), sales 20, competition 10, match quality
  25/15/5, × completeness factor. Display only — never the purchase gate.
- Fee labels: the referral fee shown is always labeled as referral and
  marked `(est.)` when the category is default/inferred; an unknown FBA
  fee renders "Unknown — verify before buying" and is never replaced by
  the 15% referral default.

## Ranking

Products rank first by unit-economics confidence group — estimated →
provisional → unavailable — so a verified full fee stack always outranks
a provisional number, however large. Within a group: 1. net profit per
unit desc, 2. ROI desc, 3. seller count asc, 4. FBA seller count asc,
5. monthly-sales demand desc, 6. Buy Box price stability (narrower
high-low spread) asc. Unavailable/review products sort last. The goal is
to surface the highest quality Kirkland opportunities first.

## Scout vs Margin Calculator

The Product Scout shows only allowlisted market/COGS fields and labels
estimates and unknowns honestly ("Estimated", "Unknown", "Unavailable" —
never zeros). The Margin Calculator is a manual unit-economics model: values
entered there never alter Scout source-cost data. No Scout result is a
recommendation to buy or an approval to resell.

## Tests (offline — no live API calls, no secrets)

    python -m unittest test_finance test_pricing test_live_response test_offers_route test_canopy_route test_easyparser_client test_costco_client test_costco_api_client test_scanner_endpoint test_product_analysis test_offer_enrichment test_amazon_search test_bright_data_client test_scavio_client test_fee_engine test_network_guard test_manual_import test_opportunity_analytics test_coverage_report test_inspect_cache test_demand_estimator test_competition_analytics test_portfolio_analytics test_mapping_review test_intel_clis test_market_snapshot_store test_market_snapshot_merge
    node test_ui_display.cjs

`test_scavio.py` is a live test and is never part of the offline suite.

A structural network guard (`sitecustomize.py`, imported by every test
module) blocks all real `requests` calls during test runs: no .env
fallback misconfiguration can ever trigger a live call that burns credits
or leaks secrets. Set `NS_ALLOW_NETWORK=1` to bypass (never in CI).
