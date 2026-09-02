# Proof-Batch Guarded Execution — Design (Phase 1)

Status: DESIGN (written before implementation edits). Implementation: Phase 2.
This document researches the existing execution pathways and fixes the design
for the guarded 20-ASIN provider-data validation run. No live call is made by
anything in this design; all future live commands are marked NOT EXECUTED.

Authoritative preflight: `data/batch/proof-batch-preflight-20260818T060549Z.json`
(run_id `proof-batch-preflight-20260818T060549Z`, purpose
`provider_data_contract_validation`, 20 ASINs, Easyparser-only plan,
`market_offers` sole requested field contract).

---

## 1. Current execution pathways (audit)

### Live gates and providers
| Component | Role | Offline? |
|---|---|---|
| `live_gate.py` | Default-off gate: `SCANNER_LIVE_ALLOWED` must be an explicit opt-in (`env_flags.env_flag`, strict 1/true/yes/on). `live_enabled()` checked at every app-facing provider entry point. | Yes (imports env_flags only) |
| `env_flags.py` | Strict boolean flag parser; anything but 1/true/yes/on ⇒ disabled. | Yes |
| `easyparser_client.py` | One GET per call (`get_easyparser_offers`); returns normalized dict, never raises; exposes `credits_used`/`credits_remaining` (None when unknown), `observed_at`, `asin`, `title`, `offers`, `buy_box_*`, `offer_count`, counts, `data_gaps`. No request ID, no capture timestamp except `observed_at`. | Network-capable; import-safe |
| `bright_data_client.py` / `brightdata_client.py` / `scavio_client.py` / `canopy_client.py` / `costco_api_client.py` / `amazon_search.py` | Search/detail/canopy/costco providers. Not needed for the proof-batch offer contract. | Network-capable |
| `offer_enrichment.py` | Enrichment orchestration + `map_seller_offer_contract`; gated by live_gate. Not reused by the runner (it pulls provider clients in). | Network-capable |

### Existing CLI execution paths
| CLI | ASIN source | Caps | Writes | Verdict for this flow |
|---|---|---|---|---|
| `enrich_cached_asins.py` (status/dry-run/preflight/batch) | **Candidate cache** (`amazon_search.load_cached_candidates()`) — implicit scanner-wide discovery; `--limit` truncates, never a fixed list | `--live` + `--limit` + `--max-requests` + `--max-credits` (all required for live modes); budget stop per request; retries opt-in (default 0) | **Market snapshot store + run report = PROTECTED artifacts** | **NOT reused for ASIN sourcing or persistence.** Its budget pattern (`_fetch_once`, stop-before-request, ~5 credits/ASIN estimate) is the reference pattern for the runner. |
| `proof_batch.py` (fixture-run / report / preflight) | Preflight file (fixed 20) / fixture canonical rows | fixture-run: none beyond explicit `--out`; preflight: none | Explicit `--out` paths only; production files never | **REUSED**: envelope build/validate, preflight, compare, batch report. |
| `costco_api_client.py refresh` etc. | Costco catalog | pages cap | Costco files | Not involved. |
| `npm run pipeline` / `run-agent.bat` | Search keywords | — | data/snapshots… | Not involved. |

### Routes (main.py)
`GET /` (static), `GET /api/kirkland/scanner|live`, `GET /api/products/{asin}/canopy|offers`, `POST /api/kirkland/refresh` (403 without gate), `/health`. All GET paths are cache-only by construction (gate off). **No route change in this task; no route may trigger a provider call from a page load or GET.**

### Risks found
1. `enrich_cached_asins.py` would accept ANY cached ASIN (scanner-wide fallback) — exactly what the fixed-20 flow must never do.
2. Its persistence target is the protected snapshot store; the proof-batch flow must keep its own output namespace.
3. `easyparser_client` provides no request ID — the runner assigns a local request index.
4. Actual credit usage is only known when the provider returns `credits_used`; otherwise only the documented ~5-credit estimate exists — the runner must track both and label actual usage as unavailable without provider evidence.
5. No existing module binds a preflight artifact; no envelope carries a preflight fingerprint; no atomic multi-file finalize exists outside `market_snapshot_store._atomic_write_json` (temp + os.replace + cleanup — reused as the pattern).
6. `benchmark_validation.compare_identity` already provides title/pack compatibility signals (`title_status` match/likely_match/mismatch, `pack_mismatch_block`) with constants `TITLE_MATCH_SIMILARITY=0.90`, `TITLE_LIKELY_SIMILARITY=0.55` — reused for mapping classification.

## 2. Data contract

### Envelope (extended from proof_batch.build_envelope)
Every run envelope keeps the existing contract (`envelope_schema_version`, `run_id`, `asin` = requested ASIN, `provider`, `requested_fields`, `provider_status`, `result_status`, `captured_at`, `snapshot`, `provenance`, `error`) and adds optional guard keys (absent in older envelopes ⇒ no contract break):
- `preflight_fingerprint` — sha256 hex of the bound preflight.
- `requested_asin` — requested ASIN (same as `asin`, explicit).
- `request_index` — 1-based request sequence number.
- `mapping_state` / `mapping_reason` — classification per §6.
- `credits_used_reported` / `credits_used_estimated` — per-ASIN budget accounting.

### Snapshot (intel_schema.validate_snapshot is the gate)
Built from the normalized Easyparser-style result via `market_snapshot_store.build_snapshot`, mapped into `facts.*`:
- `identity.name` = returned title (provenanced).
- `market.amazon_price` stays null; `market.buy_box.price` carries the observed Buy Box price (compare falls back to it with `live_price_source=buy_box`).
- `market.offers[]` mapped only from returned offers; unknown fields null; fulfillment normalized FBA/FBM/AMAZON/Unknown; `is_buy_box_winner` only when the offer is marked `buybox_winner`.
- `market.seller_counts` observed counts only (`counts_from_observed`).
- `market.coverage.offer_list_available` + `offers_complete_status` (full/partial/unknown) + `coverage_reason`.
- `cost`, `fees`, `demand` (bsr/category/reviews), `economics` all null/unavailable — Easyparser OFFER does not supply them; model-based values are NEVER merged here.
- `provenance` entries for every populated non-exempt field.

### Raw response handling
Raw provider bodies are never persisted. Only the normalized snapshot + scrubbed error shape (`proof_batch.sanitize_error`, message ≤500 chars) survive. Secret-like keys anywhere in a result ⇒ run abort.

### Relationship summary
preflight run_id + fingerprint ⇒ every envelope ⇒ run manifest ⇒ comparison report.

## 3. Exact preflight binding (tamper-resistant, local)

- Load ONLY the named preflight JSON file (`--preflight <path>`).
- `canonical_preflight_asins(preflight)`: uppercase, strip, dedupe in order; must be exactly 20 unique valid ASINs.
- Fingerprint = sha256 over a stable subset, canonicalized with `json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)`:
  `purpose`, `run_id`, canonical ASIN list (sorted), provider plan (providers in order with `status`/`fields_owned`/`requests_per_asin`/`credit_estimate_per_asin`), `requested_fields_per_asin`, `request_count_per_asin`, `request_count_total`, `hard_caps.max_asins`, `hard_caps.max_requests`.
- Binding rejection (no fallback): purpose mismatch, missing run_id, duplicates, count ≠ 20, any non-EASYPARSER provider with a planned/approved status, requested fields ≠ `["market_offers"]`, plan totals inconsistent, secret-like keys, missing `human_confirmation` line.
- Every envelope + run manifest + failure manifest carries the fingerprint.
- Threat-model limits (documented): this is an operational integrity guard against accidental drift/misconfiguration, not cryptographic authorization. A user with direct filesystem write access can alter both the preflight and its hash — outside the threat model.

## 4. Credit and request containment

- `--max-requests` (int ≥ 1) and `--max-credits` (int ≥ 1) are REQUIRED for every run command; no defaults.
- Allowed requests = `min(runtime max_requests, preflight request_count_total (20), hard proof-batch limit 20)`.
- Stop-before checks (each ASIN): requests used ≥ allowed ⇒ `budget_max_requests`; `est_credits_used + estimated_per_request > max_credits` ⇒ `budget_max_credits`.
- Accounting per request: `requests_used += 1` (attempts incl. retries; retries default 0 and count toward caps); credits: provider-reported `credits_used` (int > 0) when present else documented estimate 5.0/ASIN (`ESTIMATED_CREDITS_PER_ASIN=5.0`, mirroring `enrich_cached_asins.py`); both totals recorded; `actual credits = unknown` is stated whenever no provider evidence exists.
- No hidden retries: `retries=0` always in this build.

## 5. Failure semantics and atomicity

- Storage primitive: per-file temp write (UTF-8 JSON, flush+fsync) → read-back validation → `os.replace` (atomic on Windows) — pattern proven in `market_snapshot_store._atomic_write_json`.
- Run state machine: `guard_refused` → nothing written; `binding_invalid` → nothing written; per-ASIN loop (stop-before + fetch + normalize + classify + validate); abort conditions (wrong ASIN, incompatible title/pack, schema failure, secret-like, budget stop, adapter crash, persistence failure) ⇒ write ONLY a scrubbed `failure-manifest.json` (run_id, fingerprint, stage, ASIN index only, budget state, error category, timestamp — no secrets, no raw bodies, no results).
- `validated-result-envelopes.json` is finalized ONLY when all 20 ASINs hold a final non-aborting status; temp file read-back must validate every envelope + fingerprint before `os.replace`.
- Resume policy: NO automatic resume. A later run is a new human-approved command referencing the same preflight with new explicit caps.
- Interruption: stale `.tmp` files in the run dir are cleaned on next write to the same dir; a run dir without a finalized `validated-result-envelopes.json` is never treated as completed.

## 6. Mapping review policy

Comparison states (each envelope + report row):
`match` | `expected_mapping_review` | `unexpected_mapping_mismatch` | `unavailable` | `possible_market_drift` | `parse_error` | `provider_error`.

Rules (via `benchmark_validation.compare_identity` on canonical benchmark title vs returned title):
- **Returned ASIN missing (null/absent)** ⇒ HARD abort (`STOP_WRONG_ASIN`): the requested/returned ASIN relationship cannot be established.
- **Returned ASIN ≠ requested ASIN** ⇒ HARD abort (`unexpected_mapping_mismatch`, `STOP_WRONG_ASIN`): wrong product.
- **Explicit `pack_mismatch_block` (pack-size signal conflict)** ⇒ HARD abort (`unexpected_mapping_mismatch`) for **all** ASINs, including the three pre-registered title-conflict ASINs. A pack mismatch is independent product evidence beyond title text and is never downgraded to review.
- **Benchmark row `title_conflict == true`** (pre-registered; the returned ASIN already matched in the steps above) ⇒ `expected_mapping_review` (the 3 known ASINs: B01H40O42I, B08R2SRN88, B00N54AJZE). The same-ASIN title disagreement is the expected cross-file conflict — routed to human review, never silently resolved, never hard-stopped. The conflict stays flagged in the report.
- **`title_status == mismatch` for a non-conflict ASIN** ⇒ HARD abort (`unexpected_mapping_mismatch`): unrelated/incompatible title with no pre-registered conflict.
- **Returned title missing/unavailable** ⇒ `unavailable` (never silently treated as `match`, never fabricated).
- **Compatible title/pack AND no benchmark conflict** ⇒ `match`.

> **Narrow title-conflict policy.** Pre-registered benchmark title-conflict ASINs are expected mapping-review cases when the returned ASIN matches and no explicit pack mismatch exists. Title difference alone does not hard-stop those three pre-registered cases. Wrong ASIN, explicit pack mismatch, incompatible product evidence, malformed response, provider error, schema failure, budget breach, secret-like data, and persistence failure remain hard stops.
>
> **BSR/category is never an execution hard stop.** A BSR or category difference (including a `bsr` `category_context == "mismatch"`) is a **report flag** (`possible_market_drift`) when both sides are comparable; it must not hard-stop an offer-only run solely because the provider does not return BSR/category. Missing BSR/category is reported as unavailable, never as a failure.
- `possible_market_drift` is assigned by the REPORT step for price/reviews/BSR differences (capture time unknown) — never a provider failure and never a mapping conclusion. The report's per-ASIN `outcome_status` folds the vocabulary: `match | expected_mapping_review | unexpected_mapping_mismatch | unavailable | possible_market_drift | provider_error`; `parse_error` is a hard abort (scrubbed failure manifest) and can never appear in a finalized report (documented in `outcome_vocabulary`). The report always carries `purchase_authorization_statement: "Passing provider-data validation does not authorize a purchase."`

## 7. Output/report contract

New output namespace ONLY (nothing protected is written):
```
data/batch/live-validation-runs/<run_id>/
  run-manifest.json                 (run_id, preflight path, fingerprint, caps,
                                     budget final state, per-ASIN statuses, stop_reason)
  validated-result-envelopes.json   (finalized only on full success; read-back
                                     validated; fingerprint in every envelope)
  failure-manifest.json             (only on abort; scrubbed)
  benchmark-comparison-report.json  (report command output)
  benchmark-comparison-report.csv   (per-ASIN rows)
  human-review-summary.md           (report command output)
```
`report` accepts only a finalized `validated-result-envelopes.json` AND a
`run-manifest.json` whose `preflight_fingerprint` equals the results
artifact's — the results↔run-manifest↔preflight fingerprint linkage is
verified before any report is produced.

## 8. Future command design (NOT EXECUTED)

```
# Human approval gate (zero network):
python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json \
    --max-requests 20 --max-credits <N>

# Future live run (after approval; requires explicit gate):
python proof_batch_run.py run --live --preflight data/batch/proof-batch-preflight-20260818T060549Z.json \
    --max-requests 20 --max-credits <N>

# Post-run comparator (zero network, fixture or finalized results):
python proof_batch_run.py report --run-dir data/batch/live-validation-runs/<run_id>
```
- `run` requires: `--live`, `SCANNER_LIVE_ALLOWED` (live_gate), valid preflight binding, finite `--max-requests`, finite `--max-credits`, caps consistent with the preflight plan. No broad scan switch; no arbitrary ASIN list; no scanner/cache fallback.
- A new dedicated module `proof_batch_run.py` is required because: (a) `enrich_cached_asins.py` is cache-driven and writes protected artifacts; (b) the fixed-preflight binding, fingerprint, envelope-finalize, and report pipeline do not exist anywhere; (c) keeping the runner isolated from scanner-wide code makes containment testable by import audit.
- The live provider adapter IS implemented (`proof_batch_easyparser_adapter.py`)
  but its `allow_live` gate is OFF in this build, and it never defaults to the
  real easyparser transport (explicit client injection required) ⇒ `run`
  refuses at the adapter gate (exit 2, no provider call) until a separate
  human-approved build enables it. All commands above are documentation;
  nothing was executed.

## 9. Test plan (Phase 3)

- Preflight canonicalization + fingerprint stability (same file ⇒ same fingerprint; stable subset order).
- Tamper rejection: purpose/run_id/ASIN list/count/duplicates/provider plan/requested fields ⇒ binding errors + different fingerprint.
- Caps mandatory and finite; lower-bound behavior (max_requests 5 ⇒ stops after 5 with failure manifest, no finalized results).
- Request cap before request; credit-estimate cap before request (max_credits 7 ⇒ 1 request only).
- Zero retry default (a failed ASIN is attempted exactly once).
- No provider call without every guard (refusals; adapter call count 0).
- Fixture adapter only in offline tests; import audit proves the runner's module top-level imports no provider modules (the gated live adapter is imported lazily only inside the refusing `run` path).
- Wrong ASIN ⇒ hard abort; incompatible title/pack ⇒ hard abort; expected_mapping_review exactly for the 3 conflicts.
- Null preservation (reviews/BSR/cost/fees null, never 0); secret-like rejection; intel_schema rejection (forbidden zero).
- Atomic persistence success (finalized file + manifest, fingerprint match); failure (no finalized output, scrubbed failure manifest, tmp cleanup).
- Report generation from fixtures: per-ASIN + batch metrics, drift classes, expected-mapping-review list, no universal accuracy score, economics/demand internal labels.
- No provider call from preflight/cache-only paths (provider-client patch containment).
- Protected-artifact hashes unchanged before/after (task-level check).
