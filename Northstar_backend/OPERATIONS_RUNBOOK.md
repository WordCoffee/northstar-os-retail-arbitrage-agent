# OPERATIONS_RUNBOOK.md

Operator-facing runbook for Northstar OS Retail Arbitrage Agent (Northstar_backend/).
For universal agent rules see `AGENTS.md`; for universal Master Brain rules see
`../shared/master-brain/constitution.json`. This runbook covers only operator
procedures, not the agent's decision-making logic.

---

## 1. Run the app locally

### Prerequisites
- Python 3.10+ with venv at `Northstar_backend/venv/`
- Node.js (for UI test harness only)
- Cloudflare Wrangler (for production deploy only)
- `.env` at project root with required keys (see AGENTS.md `.env` section)

### Local development server
```powershell
cd "Northstar OS Retail Arbitrage Agent\Northstar_backend"
.\venv\Scripts\Activate.ps1
# Run the FastAPI/Flask server (see main.py for the actual entrypoint)
python main.py
```

### Production deploy
```powershell
# Wrangler reads Northstar_backend/wrangler.toml
npx wrangler deploy
```

---

## 2. Run the full offline test suite

```powershell
cd "Northstar OS Retail Arbitrage Agent\Northstar_backend"
.\venv\Scripts\Activate.ps1

# Python tests (no network, no LLM)
python -m unittest discover -s . -p "test_*.py"

# Node UI test harness (sandboxed VM, never-resolving fetch)
node test_ui_display.cjs
```

Expected at the time of writing: **1272 tests ran / 1 failure / 67 errors / 3 skipped**
(modal, deterministic across multiple runs). The 1 failure and 67 errors are
**pre-existing**, all confined to `test_dataforseo_adapter.py`:
- 1 FAIL: `test_disabled_post_returns_403` (import-time env-capture of
  `DATAFORSEO_ENABLED=true` at `dataforseo_adapter.py:108`)
- 67 ERRORS: `AttributeError: module 'dataforseo_adapter' has no attribute '...'`
  (15 named missing symbols; documented in `00_STATE.json` known_issues)

These are deliberately left OPEN per the discipline in
`docs/dataforseo-adapter-collection-blocker-report.md`.

### Individual test files
```powershell
python -m unittest test_benchmark_validation -v
python -m unittest test_intel_schema -v
python -m unittest test_normalized_snapshot -v
python -m unittest test_master_brain_gateway -v
python -m unittest test_master_brain -v  # if present
```

---

## 3. Live gates — env var NAMES (never values)

All live calls are **fail-closed**. The transport is disabled by default.
The following env vars control live behavior; the operator must set them
**locally for a single invocation** then restore.

### Provider transport arms (set BEFORE invoking, restore AFTER)
| Env var | Effect |
|---------|--------|
| `SCANNER_LIVE_ALLOWED` | Master "live allowed" switch (must be exactly `"true"`) |
| `DATAFORSEO_TRANSPORT_ENABLED` | Enables DataForSEO transport (must be exactly `"true"`) |
| `DATAFORSEO_LOGIN` | DataForSEO credential (username) |
| `DATAFORSEO_PASSWORD` | DataForSEO credential (password) |
| `BRIGHTDATA_UNLOCKER_API_KEY` | Bright Data Web Unlocker key |
| `BRIGHTDATA_UNLOCKER_ZONE` | Bright Data zone (default `northstaros`) |
| `CHOCODATA_API_KEY` | Chocodata API key |
| `OPENWEBNINJA_API_KEY` | OpenWebNinja Costco catalog key |

### Costco catalog source
| Env var | Effect |
|---------|--------|
| `COSTCO_CATALOG_SOURCE` | `OFF` (default, local CSV only, zero network) \| `OPENWEBNINJA` (legacy `UNWRANGLE` value maps to `OFF`; Unwrangle removed 2026-09 — no free tier, paid from $99/mo) |
| `COSTCO_CATALOG_MAX_PAGES` | Cap on pages fetched per query |
| `COSTCO_CATALOG_REQUEST_DELAY_SECONDS` | Rate-limit sleep between requests (default 2.0) |
| `COSTCO_DELIVERY_ZIP` | Delivery ZIP for catalog lookup (default 75201) |
| `COSTCO_BUSINESS_CENTER` | Business center label (default "Dallas Business Center") |
| `COSTCO_CATALOG_DETAIL_ENABLED` | `1` to enable layer-2 detail refresh (gated) |
| `BRIGHTDATA_COSTCO_DETAIL_ENABLED` | `1` to arm Bright Data Web Unlocker (primary) for detail pulls |
| `BRIGHTDATA_UNLOCKER_API_KEY` | Web Unlocker key (presence check only — never log the value) |
| `FIRECRAWL_COSTCO_DETAIL_ENABLED` | `1` to arm Firecrawl (fallback) for detail pulls |
| `FIRECRAWL_API_KEY` | Firecrawl API key (presence check only — never log the value) |
| `COSTCO_FRESHNESS_THRESHOLD_DAYS` | Stale threshold (default 8) |

### Enrichment modes
| Env var | Effect |
|---------|--------|
| `SCANNER_OFFER_ENRICHMENT` | `OFF` (default) \| `BRIGHTDATA` \| `AUTO` \| `EASYPARSER` \| `CHOCODATA` \| `UNWRANGLE` |
| `SCANNER_OFFER_CACHE_TTL_HOURS` | Cache freshness in hours (default 24; <= 0 disables) |
| `SCANNER_LOCAL_SNAPSHOT_MERGE` | `1` enables opt-in read-only snapshot merge (strict flag) |

### Network guard for tests
| Env var | Effect |
|---------|--------|
| `NS_ALLOW_NETWORK` | `1` escapes network_guard (NEVER in CI) |

**Pattern (one-run live probe):**
```powershell
$env:SCANNER_LIVE_ALLOWED="true"
$env:DATAFORSEO_TRANSPORT_ENABLED="true"
$env:DATAFORSEO_LOGIN="login@example.com"
$env:DATAFORSEO_PASSWORD="pw"
python validation_run.py authorize-check --run <id> --confirm <id>
python validation_run.py execute-dataforseo --run <id> --confirm <id>
python validation_run.py retrieve-dataforseo --run <id> --confirm <id>
$env:DATAFORSEO_TRANSPORT_ENABLED="false"
$env:SCANNER_LIVE_ALLOWED="false"
```

---

## 4. Authorization Gate states (operator reference)

The Authorization Gate is a **read-only, derived** field on each Scout row.
It is computed from existing payload fields only (no live calls, no inference
beyond the explicit rules below). The states and their precedence:

| State | Severity | Meaning |
|-------|----------|---------|
| **Blocked** | `blocked` | Identity/pack/required-evidence conflict. NEVER purchase-authorized. Triggers: `pack_match === "mismatch"`, `portfolio_readiness === "blocked_mismatch"` or `"insufficient_data"`. |
| **Authorized** | `ok` | Invoice-confirmed cost present. `cost_is_purchase_authorized === true` AND `costco_cost_basis === "invoice_confirmed"` AND `pack_match === "exact"`. Operator must still complete normal Amazon listing + account checks. |
| **Invoice Pending** | `warn` | Discovery/estimated cost only. `costco_cost_basis` in (`costco_online`, `estimated`, `candidate_match`, `unavailable`) OR `pack_match` in (`candidate`, `unknown`, `invoice_pending`). Verify supplier invoice, exact product identity, quantity, and pack before buying. |
| **Needs Review** | `review` | Economics/freshness incomplete. `economics_confidence` in (`provisional`, `unavailable`) OR `economics_status` in (`missing_amazon_price`, `missing_costco_cogs`, `mapping_verification_required`, `needs_fee_verification`) OR `freshness_label === "stale"`. NOT purchase-ready. |

**Default:** Empty/undefined record falls through to **Needs Review**
(conservative; never silently promoted to Invoice Pending).

**Precedence order:** Blocked > Authorized > Invoice Pending > Needs Review.

Implementation: `NS.authorizationGate(p)` in `static/index.html` (line 4779).

---

## 5. BSR / comparison evidence model

The BSR evidence contract is defined in `intel_schema.py` and is a structured
field set (never a loose string):

```
bsr_primary_rank         (int|null, never 0)
bsr_primary_category     (string|null)
bsr_secondary_rank       (int|null)
bsr_secondary_category   (string|null)
bsr_raw                  (original string, always preserved)
bsr_capture_status       (verified | missing_live | missing_csv_reference |
                          provider_not_supported | parse_error |
                          identity_conflict | unavailable)
bsr_source               (provider name)
bsr_captured_at          (ISO timestamp)
```

**Valid `bsr_capture_status` values:**
- `verified` — parsed rank+category successfully
- `missing_live` — live provider returned no BSR for a non-excluded ASIN
- `missing_csv_reference` — benchmark CSV carried no BSR for this ASIN
- `provider_not_supported` — chosen provider does not supply BSR at all
- `parse_error` — raw BSR string could not be parsed to a rank
- `identity_conflict` — BSR came back for a conflicting identity (wrong title/brand/pack)
- `unavailable` — no BSR signal at all (default)

**Rules:**
- Never infer BSR from price, reviews, or category.
- Never convert "Not listed on page" or absent value to rank 0.
- Raw BSR source text preserved separately (`bsr_raw`) from parsed numeric rank.
- Per-field capture status: `bsr_field_completeness(bsr)` returns
  `captured | unavailable | provider_not_supported | parse_error | identity_conflict | not_requested`.

**Comparison engine:** `benchmark_validation.compare_benchmark_record()` (Phase 4):
- BSR rank compared ONLY when both ranks present AND same category.
- If categories differ → `bsr_comparison_status = "mismatch"`, no numeric delta.
- Price drift within `PRICE_WITHIN_TOLERANCE` (5%) = `within_tolerance` (not failure).
- Overall disposition: `matched | normal_market_drift | provider_field_gap |
  mapping_conflict | insufficient_data | needs_manual_review`.

---

## 6. Live provider run procedure (universal pattern)

The same 6-step pattern applies to DataForSEO, Costco discovery, and any future
provider. Each step is fail-closed; never skip a step.

### Step 1: Preflight (zero network)
```powershell
python validation_run.py preflight --run <run-id>
```
Verifies: env vars resolve, manifest valid, no overlapping prior run-id,
shortlist criteria met, zero network calls, budget ceiling stated.

### Step 2: Freeze manifest
```powershell
python validation_run.py report-plan --run <run-id>
```
Locks the plan (target ASINs, provider paths, credit estimates) and
writes it to disk. Frozen for the duration of the run.

### Step 3: Authorize
```powershell
python validation_run.py authorize-check --run <run-id> [--confirm <run-id>]
```
Operator must enter a one-time approval token EQUAL to the run-id.
Without confirmation, the run remains PLANNED (not READY).
The token must equal the run-id exactly; no auto-submit, no UI toggle.

### Step 4: Execute (bounded, zero retries)
```powershell
python validation_run.py execute-dataforseo --run <run-id> --confirm <run-id>
```
Provider rejections, rate limits, timeouts, and unexpected errors are
NEVER auto-retried. A `40402` path mismatch routes to
`provider_rejected_invalid_path` and that route is permanently off-limits
for this run.

### Step 5: Retrieve
```powershell
python validation_run.py retrieve-dataforseo --run <run-id> --confirm <run-id>
```
Reads the task_get results. Re-checks for `id`/family/path match
before accepting the result. Never auto-retries on failure.

### Step 6: Report
```powershell
python validation_run.py repair-dataforseo --run <run-id>  # if rejection-classified
python validation_run.py report --run <run-id>
```
Generates the run report. Inspect it before touching the archive.
Repair is read-only against the preserved envelope store
(`data/validation-runs/<run-id>/raw/`).

---

## 7. Provider Readiness Matrix

| Provider | Env var NAMES (not values) | Live gate flag | Known failure modes | Test coverage |
|----------|----------------------------|----------------|---------------------|----------------|
| **Costco/OpenWebNinja** | `COSTCO_CATALOG_SOURCE=OPENWEBNINJA`, `OPENWEBNINJA_API_KEY` | `COSTCO_CATALOG_SOURCE=OPENWEBNINJA` enables | 401/403 blocked, 429 rate-limited, 100 req/mo free tier | Y (`test_costco_api_client.py`, 105 tests) |
| **Costco detail / Bright Data** (primary) | `BRIGHTDATA_COSTCO_DETAIL_ENABLED`, `BRIGHTDATA_UNLOCKER_API_KEY`, `COSTCO_CATALOG_DETAIL_ENABLED=1` | detail flag + `BRIGHTDATA_COSTCO_DETAIL_ENABLED=1` + key presence | 1 credit/request, 5k/mo free tier; HTTP 401/403 auth, 429 rate-limit, 5xx http_error, timeout transport_error | Y (`test_firecrawl_costco.py`, `test_costco_live_runner.py`, `test_costco_api_client.py`) |
| **Costco detail / Firecrawl** (fallback, failover) | `FIRECRAWL_COSTCO_DETAIL_ENABLED`, `FIRECRAWL_API_KEY`, `COSTCO_CATALOG_DETAIL_ENABLED=1` | detail flag + `FIRECRAWL_COSTCO_DETAIL_ENABLED=1` + key presence | free tier 1,000 pages/mo (renews monthly, no card, 2 concurrent); HTTP 402 = credits_exhausted, 401/403 auth, 429 rate-limit, 5xx http_error, timeout transport_error | Y (same three files) |
| **Costco/Local CSV** | `COSTCO_CATALOG_SOURCE=OFF` (default) | `OFF` always | none (zero network) | Y |
| **Easyparser (RapidAPI)** | `SCANNER_OFFER_ENRICHMENT=EASYPARSER`, `SCANNER_OFFER_CACHE_PATH`, `SCANNER_OFFER_CACHE_TTL_HOURS` | `SCANNER_OFFER_ENRICHMENT=EASYPARSER` enables | API key not configured, invalid ASIN, HTTP 5xx | Y (`test_easyparser_client.py`, `test_offer_enrichment.py`, `test_enrich_cached_asins.py`) |
| **DataForSEO** | `DATAFORSEO_TRANSPORT_ENABLED`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `SCANNER_LIVE_ALLOWED` | `DATAFORSEO_TRANSPORT_ENABLED=true` AND `SCANNER_LIVE_ALLOWED=true` both required | 40402 invalid path, 401 auth, 402 budget, 40400 invalid params | N (15 missing symbols, 67 errors in `test_dataforseo_adapter.py`; documented in `00_STATE.json` known_issues) |
| **Bright Data** | `SCANNER_OFFER_ENRICHMENT=BRIGHTDATA`, `BRIGHTDATA_UNLOCKER_API_KEY`, `BRIGHTDATA_UNLOCKER_ZONE` (default `northstaros`) | `SCANNER_OFFER_ENRICHMENT=BRIGHTDATA` enables | credits exhausted (1 credit/request, 5k/mo free tier), HTTP 5xx, network timeout | Y (`test_bright_data_client.py`, `test_offer_enrichment.py`) |
| **Chocodata** | `SCANNER_OFFER_ENRICHMENT=CHOCODATA`, `CHOCODATA_API_KEY` | `SCANNER_OFFER_ENRICHMENT=CHOCODATA` enables | credits exhausted (5 credits/ASIN), 1k free on signup, no card | Y (`test_offer_enrichment.py`, `test_provider_switch.py`) |
| **Scavio** | (uses internal client; gated by `SCANNER_LIVE_ALLOWED`) | integrated | transport_error classification (bare print-and-swallow removed in Batch 02) | Y (`test_scavio_client.py`, `test_offer_enrichment.py`) |
| **Canopy** | (uses internal client) | integrated | network-level failure, invalid response | Y (`test_canopy_route.py`) |

---

## 7A. Costco item-detail pulls (single-item retry and full pull)

Two entry points for product-detail pulls; both are fail-closed and neither
executes without a fresh, named operator approval naming the exact provider,
item set, and budget quantity (Hard Stop Zone, Section 3).

### Entry point 1 — legacy path (backward compatible)
```powershell
# costco_api_client.py delegates to the unified runner; legacy gate must be on
$env:COSTCO_CATALOG_DETAIL_ENABLED="1"
python costco_api_client.py details refresh --item-ids 424976
python costco_api_client.py details refresh --item-ids 424976 `
  --provider BRIGHTDATA_WEB_UNLOCKER --provider-budget BRIGHTDATA_WEB_UNLOCKER=50
```

### Entry point 2 — unified runner (recommended)
```powershell
# 1) Status (zero network)
python costco_live_runner.py status

# 1a) PRE-LIVE DRESS REHEARSAL (zero network, hermetic): runs the REAL
#     runner + REAL adapters + REAL fixture HTML (transport mocked) and the
#     REAL merge through to a temp product-detail store. Proves the whole
#     pull -> evidence -> merge chain before a single live call:
python -m pytest test_full_pull_rehearsal.py -q

# 2) Build the full-pull manifest from the master price-capture CSV (zero network)
python costco_live_runner.py build-manifest `
  --from-csv data/catalog/costco_master_price_capture_20260825T142621Z.csv `
  --out data/catalog/costco_detail_manifest.json

# 2a) Dry-run the resolve-then-backfill chain (zero network) BEFORE any live call:
#       - resolve loads the manifest's pending_lookup rows (no item number)
#       - backfill folds STRONG lookups (score >= 0.50) into a NEW CSV copy
python bright_data_costco_lookup.py resolve `
  --unresolved-from data/catalog/costco_detail_manifest.json --limit 3
python bright_data_costco_backfill.py `
  --csv data/catalog/costco_master_price_capture_20260825T142621Z.csv --dry-run

# 3) Dry-run the full pull (zero network; prints plan + estimated credits)
python costco_live_runner.py full-pull `
  --manifest data/catalog/costco_detail_manifest.json --dry-run

# 3b) Rebuild the manifest from the backfilled CSV once lookups have filled
#     item numbers (rows without ids stay in pending_lookup, never fabricated)
python costco_live_runner.py build-manifest `
  --from-csv data/catalog/costco_master_price_capture_20260825T142621Z_backfilled.csv `
  --out data/catalog/costco_detail_manifest.json

# 4) Execute the full pull — LIVE AUTHORIZED, needs fresh named approval
#    Evidence goes to a NEW data/costco-discovery-runs/<ts>/ dir per pull
#    (per-pull accounting stays clean; --run-dir overrides). Then merge
#    offline: python kirkland_costco_merge.py writes/updates
#    data/costco-product-detail.json (latest evidence wins per item).
python costco_live_runner.py full-pull `
  --manifest data/catalog/costco_detail_manifest.json `
  --provider-budget BRIGHTDATA_WEB_UNLOCKER=50,FIRECRAWL=50
```

### Resolve → backfill chain (gated lookup, then offline backfill)
```powershell
# 1) LIVE (gated approval): search-lookup every title without an item number.
#    1 Web Unlocker credit per title; runs sequentially with a rate-limit delay.
python bright_data_costco_lookup.py resolve `
  --unresolved-from data/catalog/costco_detail_manifest.json
#    (chunk instead with --limit N, e.g. --limit 90, to bound each batch)

# 2) OFFLINE: fold strong matches (lookup_candidate, score >= 0.50) into a
#    NEW CSV copy. Weak/no-result/page-not-found titles are REPORTED only —
#    nothing is ever fabricated into the CSV (fail-closed).
python bright_data_costco_backfill.py `
  --csv data/catalog/costco_master_price_capture_20260825T142621Z.csv `
  --out data/catalog/costco_master_price_capture_<ts>_backfilled.csv `
  --report-json data/catalog/backfill-<ts>.json
#    (--lookup-root defaults to data/costco-lookup-runs; --dry-run previews)

# 3) Rebuild + re-plan, then pull (steps 3b / 4 above).
```

### Failover / budget semantics (tested, `test_costco_live_runner.py`)
- Auto mode starts on the first enabled + configured provider (Bright Data
  primary, Firecrawl fallback).
- A HARD failure switches to the next provider AND STAYS there (persistent
  cursor — never flip-flops back).
- A hard failure on the LAST provider halts the batch (circuit breaker):
  persist what already succeeded, record the failure in a scrubbed manifest,
  report, stop. No silent retries. Un-attempted items are never silently
  dropped: they are recorded as `skipped` (`reason: halted`,
  `items_halted_skipped` in the summary), so
  items_requested == items_fetched + items_failed + len(skipped).
- Soft per-item failures (`url_not_found` / `no_data_found`) continue and never
  switch providers.
- `--provider-budget NAME=N,...` caps items per provider; budget-exhausted items
  are `skipped` (`budget_exhausted`), never dropped.
- Store provenance: `kirkland_costco_merge.py` labels each row by the platform
  that ACTUALLY served it (`brightdata_web_unlocker` /
  `firecrawl_costco_page` for the fallback) — cost/credit accounting never
  misattributes a Firecrawl-served row to Bright Data.

### Credit math (tiers verified 2026-09)
- Bright Data Web Unlocker: 5,000 credits/mo free tier, 1 credit per request page.
- Firecrawl: 1,000 pages/mo recurring on the $0 plan (renews monthly, no card,
  2 concurrent requests).
- Budget example BrightData=50 / Firecrawl=50 → one full pull consumes ≤ 100
  credits total across the two free tiers.

### Manifest coverage note
Rows in the master capture CSV without a Costco item number (~446) land in
`pending_lookup` and are resolved by the gated lookup step, then folded back
with `bright_data_costco_backfill.py` (strong matches only) before the
manifest is rebuilt — that whole chain needs its own named live approval for
the lookup step before it runs.

---

## 8. Never do this

The following are **explicitly prohibited** by the Master Brain constitution
(`../shared/master-brain/constitution.json`) and enforced by tests/network guard:

1. **No live calls in tests.** All tests run via `python -m unittest` or
   `node test_ui_display.cjs` must be zero-network. The `network_guard.py`
   module blocks this at the import level. `NS_ALLOW_NETWORK=1` escapes the
   guard but is NEVER set in CI.

2. **No secret exposure in test output.** Never hardcode credentials in
   committed files. The credential-exposure-in-test-failure-diff
   known_issue documents a real incident where a test diff printed
   actual `.env` values — root cause is import-time env capture in
   `dataforseo_adapter.py:96-109`. Read flags at call-time, not import-time.

3. **No purchase-authorization inference.** A `matched` DataForSEO
   cross-check is a **secondary identity/offer observation only**.
   `purchase_authorized` is always `false` in the data layer.
   All purchase-eligibility decisions remain governed by existing
   shortlist, Costco cost-basis, fee engine, ASIN/pack mapping, Amazon
   listing eligibility, margin, supply, and concentration controls.

4. **No silent retries.** Provider rejections, `mapping_incompatible`,
   `schema_validation_failed`, `persistence_failure`, and
   `needs_manual_reconciliation` are NEVER auto-retried. A `40402` path
   mismatch permanently excludes that route for the run.

5. **No defaulting missing evidence to a value.** Unknown values are `null`,
   never `0`, never a fabricated aggregate. This applies to:
   - BSR (never blank-as-zero, never inferred from price/reviews)
   - Amazon price (never `$0.00`, never bare dash for missing)
   - FBA fee (never `$0`, render `Unavailable` with honest reason)
   - Monthly sales (never `0`; `null` until a real signal)
   - Costco cost (never `0.00`; CSV rows are `estimated` tier only)
   - Seller counts (zero only under explicit `available+complete` + claimed 0 + returned 0)

6. **No modifying protected artifacts** without explicit approval:
   - `data/scanner-search-cache.json` (cached scan data)
   - `data/costco-items.csv` (Costco catalog)
   - `fixtures/protected_hashes.json` (byte-identity fingerprint)
   - Benchmark CSVs (`BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv`)
   - Costco catalog archive (`data/costco-discovery-catalog.json`)
   - Amazon market snapshots (`data/amazon-market-snapshots.json`)

7. **No LLM calls in deterministic paths.** The Master Brain task
   classifier (`master_brain_gateway.classify_task`) is keyword/pattern
   based only. Provider-rejection classification uses enum lookups
   (`proof_batch_contracts.classify_dataforseo_rejection`).

8. **No committed secrets.** `.env` is gitignored. No `.env`, `.key`, or
   `.pem` files inside `Northstar_backend/`. Credential rotation is
   operator-run, never committed.

---

## 9. Reading list (in order of importance)

1. `AGENTS.md` — universal agent rules (this repo)
2. `../shared/master-brain/constitution.json` — Master Brain constitution
3. `docs/pre_ui_calculation_pipeline.md` — backend-side economics
4. `docs/dataforseo-adapter-runbook.md` — DataForSEO specific
5. `docs/proof-batch-guarded-execution-design.md` — guarded run design
6. `00_STATE.json` — current known_issues, completed_batches, next_batch
7. `static/index.html` `NS.authorizationGate` (line 4779) — gate logic
8. `intel_schema.py` `BSR_STATUSES` and `bsr_field_completeness` — BSR model