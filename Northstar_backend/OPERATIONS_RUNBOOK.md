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
| `COSTCO_CATALOG_SOURCE` | `OFF` (default, local CSV only, zero network) \| `OPENWEBNINJA` \| `UNWRANGLE` |
| `COSTCO_CATALOG_MAX_PAGES` | Cap on pages fetched per query |
| `COSTCO_CATALOG_REQUEST_DELAY_SECONDS` | Rate-limit sleep between requests (default 2.0) |
| `COSTCO_DELIVERY_ZIP` | Delivery ZIP for catalog lookup (default 75201) |
| `COSTCO_BUSINESS_CENTER` | Business center label (default "Dallas Business Center") |
| `COSTCO_CATALOG_DETAIL_ENABLED` | `1` to enable layer-2 detail refresh (gated) |
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
| **Costco/Unwrangle** | `COSTCO_CATALOG_SOURCE=UNWRANGLE`, `COSTCO_CATALOG_MAX_PAGES`, `COSTCO_CATALOG_REQUEST_DELAY_SECONDS`, `COSTCO_DELIVERY_ZIP`, `COSTCO_BUSINESS_CENTER` | `COSTCO_CATALOG_SOURCE=UNWRANGLE` enables | 401/403 blocked, 429 rate-limited, search-page credit 10 | Y (`test_costco_api_client.py`, 66 tests) |
| **Costco/OpenWebNinja** | `COSTCO_CATALOG_SOURCE=OPENWEBNINJA`, `OPENWEBNINJA_API_KEY` | `COSTCO_CATALOG_SOURCE=OPENWEBNINJA` enables | 401/403 blocked, 429 rate-limited, 100 req/mo free tier | Y (same file, 66 tests) |
| **Costco/Local CSV** | `COSTCO_CATALOG_SOURCE=OFF` (default) | `OFF` always | none (zero network) | Y |
| **Easyparser (RapidAPI)** | `SCANNER_OFFER_ENRICHMENT=EASYPARSER`, `SCANNER_OFFER_CACHE_PATH`, `SCANNER_OFFER_CACHE_TTL_HOURS` | `SCANNER_OFFER_ENRICHMENT=EASYPARSER` enables | API key not configured, invalid ASIN, HTTP 5xx | Y (`test_easyparser_client.py`, `test_offer_enrichment.py`, `test_enrich_cached_asins.py`) |
| **DataForSEO** | `DATAFORSEO_TRANSPORT_ENABLED`, `DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `SCANNER_LIVE_ALLOWED` | `DATAFORSEO_TRANSPORT_ENABLED=true` AND `SCANNER_LIVE_ALLOWED=true` both required | 40402 invalid path, 401 auth, 402 budget, 40400 invalid params | N (15 missing symbols, 67 errors in `test_dataforseo_adapter.py`; documented in `00_STATE.json` known_issues) |
| **Bright Data** | `SCANNER_OFFER_ENRICHMENT=BRIGHTDATA`, `BRIGHTDATA_UNLOCKER_API_KEY`, `BRIGHTDATA_UNLOCKER_ZONE` (default `northstaros`) | `SCANNER_OFFER_ENRICHMENT=BRIGHTDATA` enables | credits exhausted (1 credit/request, 5k/mo free tier), HTTP 5xx, network timeout | Y (`test_bright_data_client.py`, `test_offer_enrichment.py`) |
| **Chocodata** | `SCANNER_OFFER_ENRICHMENT=CHOCODATA`, `CHOCODATA_API_KEY` | `SCANNER_OFFER_ENRICHMENT=CHOCODATA` enables | credits exhausted (5 credits/ASIN), 1k free on signup, no card | Y (`test_offer_enrichment.py`, `test_provider_switch.py`) |
| **Scavio** | (uses internal client; gated by `SCANNER_LIVE_ALLOWED`) | integrated | transport_error classification (bare print-and-swallow removed in Batch 02) | Y (`test_scavio_client.py`, `test_offer_enrichment.py`) |
| **Canopy** | (uses internal client) | integrated | network-level failure, invalid response | Y (`test_canopy_route.py`) |

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