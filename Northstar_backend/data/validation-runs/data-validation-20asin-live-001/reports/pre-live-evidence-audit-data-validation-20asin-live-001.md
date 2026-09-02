# Pre-Live Evidence Audit — data-validation-20asin-live-001

- **Audit date:** 2026-08-20 (local)
- **Audit type:** OFFLINE — zero provider calls; file and code inspection only
- **Run:** `data-validation-20asin-live-001` (mode `standard_queue`, hard_cap 100 cents, 20 ASINs, providers DATAFORSEO + BRIGHTDATA)
- **Primary finding:** All 10 `task_post` submissions were **rejected by DataForSEO at the task level** — HTTP 200 envelope, `status_code=40402`, `status_message="Invalid Path."`, `cost=0`, `result=null`, `tasks_error=1`. The `remote_task_id` values in the ledger reference **rejected responses, not created tasks**. This fully explains the retrieval HTTP 404: the tasks never existed provider-side. **Confirmed provider spend: $0.00** for this run.

---

## Phase 1 — Artifact inventory

### Benchmark / reference evidence
| Artifact | Path | Key facts |
|---|---|---|
| Benchmark reference (canonical) | `data/benchmarks/asin_benchmark_reference.json` | 87,764 B; generated 2026-08-18T04:59:34Z; 67 observations / 47 ASINs; schema_v1; `kind`=reference; 3 `conflicts` (see below) |
| Benchmark manifest | `data/benchmarks/manifest.json` | provenance `user_provided_reference`; capture_time `unknown` |
| Raw source CSV (BSR/proxy-rank) | `data/benchmarks/raw/BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv` | 3,406 B |
| Raw source CSV (rank) | `data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv` | 2,338 B |
| Source preflight | `data/batch/proof-batch-preflight-20260818T060549Z.json` | 20 ASINs, per-ASIN benchmark fields, local_cache info |

**Benchmark conflicts (title cross-file, all 3 = `manual_review_only` ASINs):**
- `B00N54AJZE` — "Stool Softener 100mg (400ct, alt listing)" vs "Stool Softener 100mg (alt)"
- `B01H40O42I` — "Aller-Flo (Pack of 5)" vs "Aller-Flo Fluticasone (Pack of 5)"
- `B08R2SRN88` — "Aller-Flo (5 Bottles/600 sprays)" vs "Aller-Flo Fluticasone (5 Bottles/600 sprays)"

### Run artifacts (data-validation-20asin-live-001)
| Artifact | Path | Facts |
|---|---|---|
| Run manifest | `manifest.json` | hard_cap_cents=100, 20 ASINs, providers DATAFORSEO+BRIGHTDATA |
| Authorization | `authorization.json` | created 2026-08-20T02:27:19Z |
| Preflight plan | `preflight-plan.json` | eligible_to_submit=10, manual_review_only=3, blocked=7, total_reserved=100, within_budget=true |
| Budget ledger | `budget-ledger.jsonl` | 30 rows: submitted=10, planned=10, manual_review_required=3, budget_rejected=7; all provider=DATAFORSEO |
| Plan report | `reports/plan-report.md` | per-ASIN plan status |
| Raw envelopes | `raw/dataforseo/*.json` | 10 files × 837 B, stored 2026-08-20T03:07:45–52Z |
| Normalized | `normalized/{dataforseo,brightdata}/` | **EMPTY** (0 records) |
| Comparisons | `comparisons/` | **EMPTY** (0 records) |
| Logs | `logs/` | **EMPTY** |

### Supporting local data
| Artifact | Path | Facts |
|---|---|---|
| Scanner search cache | `data/scanner-search-cache.json` | 230 products; fetched_at 2026-08-18T01:43:46Z; source=brightdata; search_terms=[kirkland]; per-product: asin, name, amazon_price, product_url, brand, sales_volume, monthly_sales_estimate(+estimated), rating, reviews_count |
| Costco cost files | `data/costco-items.csv`, `costco-invoice-confirmed.json`, `costco-amazon-mapping.json`, `costco-api-catalog.json`, `costco-discovery-catalog.json`, `costco-product-detail.json` | **ALL ABSENT** — no cost basis exists locally for any ASIN |

---

## Phase 2 — Reconciliation matrix (10 submitted ASINs)

Legend: benchmark = user-provided reference; cache = scanner-search-cache (2026-08-18, Bright Data source).

| ASIN | Bench price | Cache price | Price verdict | Reviews | Prime/FBA (bench) | Cache monthly sales est. | DataForSEO task state |
|---|---|---|---|---|---|---|---|
| B0CP6LXPLK | 33.12 | — (cache miss) | MISS | 1,434 | yes | — | submitted → provider_rejected 40402 |
| B00BISGJXA | 12.75 | 11.49 | CONFLICT (−1.26) | 18,629 | yes | — | submitted → provider_rejected 40402 |
| B00BH3HPZW | 17.84 | 17.84 | MATCH | 4,799 | yes | 5,000 | submitted → provider_rejected 40402 |
| B00GYZWNY6 | 29.25 | 28.95 | CONFLICT (−0.30) | 5,183 | yes | 5,000 | submitted → provider_rejected 40402 |
| B0045XGE9E | 13.84 | 12.39 | CONFLICT (−1.45) | 4,966 | yes | — | submitted → provider_rejected 40402 |
| B002L4M4M0 | 7.93 | — (cache miss) | MISS | 6,270 | yes | — | submitted → provider_rejected 40402 |
| B081THWMDK | 28.79 | 26.98 | CONFLICT (−1.81) | 967 | yes | 1,000 | submitted → provider_rejected 40402 |
| B085F1QCB9 | 28.07 | 28.07 | MATCH | 588 | no* | 2,000 | submitted → provider_rejected 40402 |
| B00QGMOJ4Y | 23.99 | 23.99 | MATCH | 2,358 | no | 1,000 | submitted → provider_rejected 40402 |
| B01LY71217 | 35.99 | 35.99 | MATCH | 4,319 | no | 2,000 | submitted → provider_rejected 40402 |

\* B085F1QCB9: "Amazon-shipped, non-Prime badge" per benchmark note.

**All 10 envelopes** (`raw/dataforseo/*.json`) are structurally identical submission responses: HTTP 200, `status_code=40402`, `status_message="Invalid Path."`, `cost=0`, `result=null`, `data=null`, `tasks_error=1`, single `tasks[0].id` recorded.

**Ledger bookkeeping note:** ledger rows show `state=submitted`, `reserved_cost_cents=5`, `actual_cost_cents=5`, `retrieval_attempt_count=0`, `updated_at=2026-08-20T03:07:45Z`. The `actual_cost_cents` is **local estimate only** — provider returned `cost=0` on every envelope. The pre-fix retrieval attempt (task_get → HTTP 404 → uncaught GuardError, run aborted) never updated the ledger attempt counters; with the `DataForSeoGuardError` fix landed, per-row GuardErrors are now caught and bookkept.

### Other 10 ASINs (for completeness)

| ASIN | Plan status | Bench price | Cache price | Verdict |
|---|---|---|---|---|
| B01H40O42I | manual_review (title conflict) | 26.74 | 15.49 | CONFLICT |
| B08R2SRN88 | manual_review (title conflict) | 26.80 | 15.49 | CONFLICT |
| B00N54AJZE | manual_review (title conflict) | 12.69 | — | MISS |
| B07BZW88NY | budget_rejected | 14.25 | 12.44 | CONFLICT |
| B078B5N4DD | budget_rejected | 13.97 | — | MISS |
| B007MWNFBA | budget_rejected | 19.99 | 14.99 | CONFLICT |
| B00OPQZJA6 | budget_rejected | 20.99 | 20.98 | CONFLICT (Δ0.01) |
| B0C54GXFQ8 | budget_rejected | 43.99 | 43.99 | MATCH |
| B0F7GTX962 | budget_rejected | 15.49 | 14.99 | CONFLICT |
| B00BI33NU2 | budget_rejected | 13.65 | — | MISS |

---

## Phase 3 — Missing-data register (summary; full 20-row register in CSV)

Every field below is **absent for all 20 ASINs** unless noted:
- **UPC / EAN / GTIN** — absent from benchmark, cache, and both provider adapters' observed-field vocabularies (neither DataForSEO `_OBSERVED_FIELDS` nor Bright Data clients return it). Never synthesized.
- **Weight / dimensions** — absent everywhere; no FBA fee estimate possible from evidence.
- **FBA fee** — absent everywhere (cache has no `fba_fee`; benchmark has none).
- **Seller roster / seller counts / buy box winner** — absent everywhere (no Easyparser calls were made; DataForSEO `seller_offer` rows were `planned`, never executed; Bright Data seller fields exist in clients but no detail fetch ran for this run).
- **BSR** — absent for all 20 (benchmark CSV BSR column empty for these rows; `bsr_rank_number=null`).
- **Cost basis (Costco COGS)** — absent for all 20 (all Costco data files missing locally; `resolve_costco_cost` returns empty).
- **Capture timestamps** — benchmark rows carry `capture_timestamp=null` / `capture_time_status="unknown"`; cache carries run-level `fetched_at` only.
- Present: benchmark price/title/reviews/prime_fba (all 20); cache price/name/brand/reviews/rating/monthly-sales-est (16 of 20); cache price vs benchmark price MATCH on 8 of 20, CONFLICT on 10 of 20 (cache lower in 9), MISS on 2 of 20.

---

## Phase 4 — DataForSEO readiness + retrieval-only gate

**Local implementation (verified in code):**
- Strict gate `SCANNER_LIVE_ALLOWED` (`live_gate.py:29-31`; `env_flags.py:12,22-25`) — only `1/true/yes/on` enable; default off.
- Endpoint allowlist (`dataforseo_adapter.py`): `POST .../product_info/task_post`, `GET .../product_info/task_get/{id}`; `/live/` endpoints forbidden.
- Per-ID task_get retrieval; one task ID per call; no batch `tasks_ready`/`tasks_failed` status endpoint implemented locally.
- Idempotency keys + payload fingerprints + reserved-cost budgeting + ledger bookkeeping all present and consistent (30/30 rows).
- GuardError class mismatch (uncaught traceback on provider HTTP 404) **fixed** this session (`DataForSeoGuardError`; targeted tests 99 OK, full suite 1092 OK / 3 skipped).
- Adapter observed fields (`dataforseo_adapter.py:996-1008`): asin, product_identity, title, brand, observed_price, seller_offer_count, seller_offer_details, condition, fulfillment_signal, source_timestamp, provider_task_id. Run normalizer (`validation_run.py:724-742`): asin, title, brand, product_count, pack_count, size, variation, observed_price, seller_signals. **No UPC/GTIN/BSR/reviews/Prime/FBA/fee fields exist in either map.**

**Provider-side diagnosis (evidence-based, offline):**
- `task_post` returned task-level `40402 Invalid Path.` for every submission → the endpoint path `/v3/merchant/amazon/product_info/task_post` is **rejected by the provider** (wrong path, moved endpoint, or plan/account restriction). Zero cost on every envelope.
- Retrieval HTTP 404 → consistent: the recorded task IDs belong to rejected responses; no provider task exists to fetch.
- Conclusion: **no live-verified tasks exist for this run.** The 10 `submitted` ledger states are locally-recorded submission metadata, not confirmed provider state.

---

## Phase 5 — Bright Data readiness scorecard

| Criterion | Status | Evidence |
|---|---|---|
| Zero-call-by-default on GET/browser paths | PASS | product_analysis.py:152-170; main.py routes; test_live_containment.py (all GET routes, zero calls) |
| Strict boolean gates (no truthiness) | PASS | env_flags.py:12,22-25; live_gate.py:29-31; offer_enrichment.py:100-107 |
| Fail-closed missing API key | PASS | bright_data_client.py:411-412 (`ValueError`) |
| Cache-only scans + failed-run cache preservation | PASS | product_analysis.py:160-169; test_scanner_cache_only.py |
| No auto-retry / stop-on-block | PASS | bright_data_client.py:424-434,475; amazon_search.py:200 |
| Raw HTML persisted to disk | GAP | in-memory TTL only (bright_data_client.py:53,452) |
| Monetary/credit hard cap (env-driven) | GAP | none exists; `get_bright_data_credits_remaining()` returns None (bright_data_client.py:524-532); only `PAGES_TO_SEARCH`/planning caps |
| Approval token / run manifest / idempotency | GAP | none on the Bright Data path (gates are the strict flag + 403 on POST /refresh) |
| UPC/GTIN capability | GAP | not returned by either Bright Data client (capability, not config) |
| Legacy dataset client dedicated tests | MINOR GAP | `enrich_product` covered only indirectly (AUTO mode, containment patches) |

Overall: **fail-closed containment is verified and strong; live-budget control-plane is absent** — no cost ceiling, no token, no manifest.

---

## Phase 6 — Cross-provider evidence matrix

| Field | Benchmark (user) | Bright Data cache (local) | DataForSEO (capability) | Costco (local) |
|---|---|---|---|---|
| ASIN | ✓ | ✓ | ✓ | — |
| Title | ✓ (conflicts on 3) | ✓ (16/20) | ✓ | — |
| Brand | ✗ | ✓ (14/20) | ✓ | — |
| Price | ✓ (20/20) | ✓ (16/20) | ✓ | — |
| Reviews | ✓ (20/20) | ✓ (16/20) | ✗ | — |
| Prime/FBA signal | ✓ (20/20) | ✗ | ✓ fulfillment_signal only | — |
| BSR | ✗ (20/20 null) | ✗ | ✗ | — |
| Monthly sales est. | ✗ | ✓ (5/10 submitted ASINs) | ✗ | — |
| Seller count / roster | ✗ | ✗ | ✓ count only (OFFER) | — |
| Condition | ✗ | ✗ | ✓ | — |
| UPC / EAN / GTIN | ✗ | ✗ | ✗ | — |
| Weight / dims | ✗ | ✗ | ✗ | — |
| FBA fee | ✗ | ✗ | ✗ | — |
| Cost basis (COGS) | ✗ | ✗ | ✗ | **✗ (all files absent)** |

Cross-provider conflicts to hold for review before any purchase decision: 10 of 20 price disagreements between benchmark and cache (9 of 10 cache lower), 3 benchmark title conflicts, and all unknown-value fields listed above.

---

## Phase 7 — Go/No-Go decisions

| # | Decision | Verdict | Conditions to lift |
|---|---|---|---|
| D1 | Resubmit the DataForSEO batch | **NO-GO (blocked)** | (a) correct `task_post` path confirmed with the provider; (b) single-ASIN preflight task_post returns `status_code=20000` with `cost>0`; (c) fresh explicit approval token for the corrected path. No batch submission before a 1-task validation task succeeds. |
| D2 | Retrieve existing tasks | **NO-GO** | Nothing provider-side to retrieve — recorded task IDs are from rejected responses (40402). Do not `task_get` the invalid IDs. Re-enable only after D1 succeeds; retrieval-only gate (per-ID task_get allowlist) stays the only permitted live operation. |
| D3 | Bright Data live scan / enrichment | **NO-GO (deferred)** | Containment is verified, but the live path has no monetary cap, no approval token, and no run manifest. Add an explicit credit/cost ceiling env, an approval token, and a run manifest; then re-audit before any live scan. |
| D4 | Offline reconciliation (benchmark + cache) | **GO (conditional)** | Zero provider calls; benchmark + cache support price/title/reviews/prime evidence. **Blocked only on cost basis:** Costco CSV and invoice-confirmed files are absent — import invoice rows or supply the CSV first, then reconcile per the Pack/Variant gate. |

---

## Phase 8 — Deliverables

1. This audit: `reports/pre-live-evidence-audit-data-validation-20asin-live-001.md`
2. Gap register: `reports/pre-live-data-gap-register-data-validation-20asin-live-001.csv`
3. Decision summary: `reports/pre-live-decision-summary-data-validation-20asin-live-001.json`

---

OFFLINE PRE-LIVE AUDIT COMPLETE — NO PROVIDER CALLS MADE — NO LIVE TASKS SUBMITTED, RETRIEVED, OR RETRIED.