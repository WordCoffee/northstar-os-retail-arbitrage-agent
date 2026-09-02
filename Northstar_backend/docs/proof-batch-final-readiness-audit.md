# Proof Batch Final Readiness Audit

Audit of the fixed 20-ASIN Proof Batch data-validation system (T2 Holdings
LLC, `Northstar_backend`) before the final offline readiness phase. Written
BEFORE this phase's implementation edits; Phase 2 changes are listed in
§12 and their outcome is recorded at the bottom of this document.

- Preflight: `data/batch/proof-batch-preflight-20260818T060549Z.json`
  (20 unique ASINs, purpose `provider_data_contract_validation`).
- References: `docs/proof-batch-guarded-execution-design.md`,
  `docs/proof-batch-easyparser-live-adapter-plan.md`,
  `docs/proof-batch-live-validation-approval.md`.
- Zero network / zero live execution: this audit and all Phase 2-5 work is
  offline. No provider call, no credits, no server, no `.env`, no secrets.

## 1. Existing guarded runner and adapter architecture

`proof_batch_run.py` (module + CLI):

- Commands: `dry-run`, `fixture-run`, `run --live`, `report`.
- `run_guarded()` — the single guarded execution function. Requires
  `live=True` and a passed-in `live_enabled` value (CLI passes
  `live_gate.live_enabled()`); refuses with `GuardError` and writes NOTHING
  when any guard is missing.
- Guard stack in `run_guarded`: explicit `--live`; `SCANNER_LIVE_ALLOWED`
  strict opt-in (`live_gate.live_enabled()`); preflight binding
  (`validate_preflight_binding` — purpose, run_id, exactly 20 unique valid
  ASINs, `human_confirmation` line verbatim, Easyparser-only plan, sole
  field contract `["market_offers"]`, request_count 1/ASIN total 20, hard
  caps 20/20); `--max-requests`/`--max-credits` mandatory and finite
  (`_require_caps`); effective allowance
  `min(runtime, plan_total 20, hard 20)`; adapter type check; retries 0.
- Per-ASIN loop: stop-before budget check → `adapter.refresh_guard_state`
  → `adapter.fetch(asin, request_index)` → secret scan of raw result →
  provider/parse-error abort checks (from `adapter_request_meta`) →
  `market_snapshot_store.build_snapshot` normalization → secret scan of
  snapshot → returned-ASIN relationship check (`provider_asin` present but
  null = hard abort) → `classify_mapping` → envelope build →
  `proof_batch.validate_envelope` (incl. `intel_schema.validate_snapshot`).
- Aborts write ONLY a scrubbed `failure-manifest.json` (run_id,
  fingerprint, stage, ASIN index only, budget state, category, timestamp);
  never raw bodies/results/secrets. Finalization of
  `validated-result-envelopes.json` happens ONLY when all 20 ASINs hold
  final non-aborting statuses.
- `_finalize_success`: temp write → fsync → read-back validation
  (fingerprint + envelope validity) → atomic `os.replace`; then writes
  `run-manifest.json` with counts, budget, honesty block (actual credit
  total null unless provider-reported), persistence proof.
- `_run_run` rejects `--asin/--asins/--input-file/--discover`, lazily
  imports `proof_batch_easyparser_adapter`, and constructs
  `EasyparserLiveAdapter` with `allow_live=False` — which ALWAYS raises
  `GuardError` (exit 2, no provider call) in this build.
- Shared-contract class identity: `ProviderAdapter`, `GuardError`,
  `BindingError`, and `RunAbort` are defined once in
  `proof_batch_contracts.py` (stdlib only) and imported by BOTH
  `proof_batch_run.py` and `proof_batch_easyparser_adapter.py`. The runner's
  strict `isinstance(adapter, ProviderAdapter)` guard therefore resolves
  against a single class under every import path — direct script
  (`python proof_batch_run.py`), module (`python -m proof_batch_run`),
  ordinary import, and `importlib.reload`. The `sys.modules.setdefault(
  "proof_batch_run", sys.modules["__main__"])` alias at the bottom of the
  runner remains as belt-and-suspenders but is no longer the identity
  solution.

Adapters (narrow contract `fetch(asin, request_index) -> dict`):

- `FixtureAdapter` — deterministic synthetic data, labeled
  `synthetic_fixture` in every artifact; zero network by construction.
- `EasyparserLiveAdapter` (`proof_batch_easyparser_adapter.py`) —
  real-data-ready; construction refuses unless `allow_live=True` AND an
  explicitly injected callable `client` (never defaults to
  `easyparser_client.get_easyparser_offers`). Returns client-shaped dict +
  scrubbed `adapter_request_meta` (request_index, requested_asin, provider,
  fields, estimated/actual credits, `credit_accounting_status`,
  request_id, provider_status, provider_asin, captured_at, retries_used 0,
  run_id, fingerprint). Stop-before re-checks in `_guard_fetch`.

## 2. Exact preflight binding and fingerprint rules

`canonical_preflight_asins` — uppercase/dedupe in preflight order; rejects
invalid ASIN strings, duplicates, and any count != 20 (hard
`HARD_PROOF_BATCH_LIMIT = 20`).

`preflight_fingerprint` — sha256 over a stable subset:
`{purpose, run_id, sorted canonical ASIN set, providers[{provider,status,
fields_owned,requests_per_asin,credit_estimate_per_asin}],
requested_fields_per_asin, request_count_per_asin, request_count_total,
hard_caps.max_asins, hard_caps.max_requests}`. Runtime caps
(`--max-credits`) are intentionally NOT fingerprinted (human-entered per
run). Altering/substituting/adding/missing/reordering the list changes the
fingerprint; only the sorted-set order inside the fingerprint JSON is
canonicalized (the fingerprint itself permits harmless ordering
differences while the ASIN set, counts, and binding are fixed).

`validate_preflight_binding` additionally enforces: kind
`proof-batch-preflight`; purpose `provider_data_contract_validation`;
non-empty run_id; verbatim `human_confirmation` line; Easyparser entry
status `planned`, requests_per_asin 1, credit_estimate_per_asin 5; NO other
planned/approved/enabled provider; fields exactly `["market_offers"]`;
request_count_per_asin 1; request_count_total 20; hard caps 20/20.

The real preflight carries `title_conflict: true` on exactly
`B01H40O42I`, `B08R2SRN88`, `B00N54AJZE` (verified).

## 3. Every live gate required for eventual execution

1. CLI `--live` flag (absent → exit 2, nothing written).
2. `SCANNER_LIVE_ALLOWED=1` strict opt-in via `live_gate.live_enabled()`
   (off by default; nothing written).
3. `--preflight <path>` required; must exist and parse; secret-scan of the
   payload (`load_preflight`).
4. Purpose `provider_data_contract_validation` (binding).
5. Canonical ASIN set/fingerprint valid (binding + fingerprint).
6. Exactly 20 unique ASINs (binding).
7. Easyparser-only provider plan (binding).
8. Sole field contract `market_offers` (binding).
9. Finite `--max-requests >= 1` (required, no default).
10. Finite `--max-credits >= 1` (required, no default).
11. Runtime request cap <= 20 (BudgetTracker raises if > 20; effective
    allowance = min(runtime, plan 20, hard 20)).
12. Runtime caps compatible with the preflight plan (plan total must be 20).
13. Adapter constructed in production-capable mode ONLY inside this guarded
    path — the future build passes `allow_live=True` + the real client
    here; this build passes `allow_live=False` and refuses. The adapter is
    never constructed elsewhere (no other module imports it).
14. Zero retries (fixed 0; every attempt counts toward caps).
15. Stop-before budget checks: `BudgetTracker.can_request()` before each
    fetch AND `adapter._guard_fetch` re-verifies refreshed remaining
    budgets before dispatch.

Fail-closed: absence/inconsistency of any of the above → `GuardError`,
exit 2, no writes (except CLI-level binding-error prints), no provider
call.

## 4. Actual Easyparser client boundary and supported `market_offers` fields

`easyparser_client.get_easyparser_offers(asin)` — single public method;
one GET (`realtime.easyparser.com/v1/request`, timeout 60 s); NEVER raises;
every outcome returns a normalized dict. Returns (where available):
`source, asin (fallback to requested when absent), provider_asin (additive
key, product.get("asin"), added in the previous phase), request_id
(additive key from request_info), title, offer_count, offers_returned_count,
buy_box_price(+raw), buy_box_seller(+id), buy_box_is_fba/fbm/prime,
buy_box_condition, observed_fba/fbm/amazon_offer_count, offers[]
(position, buybox_winner, price{value,currency}, condition, seller_id,
seller_name, seller_rating, seller_ratings_total, is_prime, is_fba, is_fbm,
is_sba, fulfilled_by_amazon, shipping_text, shipping_is_free, ships_from,
minimum/maximum_order_quantity), request_zip_code, observed_at,
credits_used, credits_remaining, data_gaps (informational + failure
substrings), request_metadata/request_info.` Error modes fold into
`data_gaps` (timeout/network/HTTP/`success:false`/missing
`result.product`/`result.offer.offer_results`/bad JSON).

The adapter's `_gap_classification` maps those to `provider_status`:
`success | provider_error | parse_error` via substring matching
(`_PROVIDER_ERROR_GAPS`, `_PARSE_ERROR_GAPS`); unknown fields stay absent
(null), never fabricated. `market_snapshot_store.build_snapshot` (pure,
offline) normalizes offers; `_intel_offer` maps to the intel_schema offer
shape.

## 5. Actual credit-accounting limitations

- Easyparser does not expose a per-request credit meter in the client
  response shape beyond `credits_used` (when present) — no authoritative
  per-call cost, no remaining-balance guarantee; `credits_remaining` is
  informational and not used for budgeting.
- `CREDIT_ESTIMATES["EASYPARSER"] = 5` (enrichment_preflight) and
  `ESTIMATED_CREDITS_PER_REQUEST = 5.0` (runner) are DOCUMENTED ESTIMATES,
  not bills. Preflight binding enforces `credit_estimate_per_asin == 5`.
- Budget honesty: `BudgetTracker` records `credits_estimated_used`
  (estimate per attempt unless the provider reported a usable positive int)
  and `credits_reported_used` (provider-reported only). `snapshot_state`
  exposes `credits_actual_status: reported_by_provider |
  unavailable_estimated_only`. Run manifest `honesty.actual_credit_total`
  is null unless provider-reported (never the estimate).
- Gap found by this audit: `BudgetTracker.__init__` does not validate
  `estimated_credits_per_request` (default 5.0) — an injected 0/None/negative
  would make the stop-before credit check meaningless (a `None` would
  TypeError at runtime). Must fail closed (Phase 2). The adapter already
  validates its own estimate (positive numeric).

## 6. Current adapter capability state

`EasyparserLiveAdapter` is **production-ready but externally gated**:
- The code is complete for a real one-ASIN `market_offers` pull (injected
  client, guard re-checks, meta accounting, secret scans).
- `allow_live` is FALSE in this build's CLI wiring → every `run --live`
  invocation refuses with exit 2 and "no provider call was made".
- Construction additionally requires an explicitly injected client — the
  adapter cannot reach the real transport without a visible, reviewed
  code change (the future approval step passes
  `easyparser_client.get_easyparser_offers`).
- Every test injects `FakeClient`; all transport paths are module-level
  patched to raise.

## 7. Every possible provider-call path in the project and whether it is blocked

Network-capable modules (single shared `requests` transport):

| Module | Call | Blocked by default? |
|---|---|---|
| `easyparser_client.py` | GET `realtime.easyparser.com/v1/request` | Yes — only called by `offer_enrichment` (credit-gated, on-demand, `SCANNER_OFFER_ENRICHMENT`), `enrich_cached_asins.py` (operator CLI), or the proof-batch adapter (never: allow_live=False). |
| `bright_data_client.py` | POST/GET dataset + Web Unlocker | Yes — scanner search path / offer enrichment; credit-gated, explicit CLI/scan only. |
| `amazon_search.py` | Bright Data search pages | Yes — explicit `npm run search` / CLI only. |
| `scavio_client.py` | POST Amazon search | Yes — only when `SCANNER_SEARCH_SOURCE=SCAVIO` (off by default). |
| `canopy_client.py` | GET Canopy product | Yes — on-demand route `get_canopy_product` use only, live-gated. |
| `offer_enrichment.py` | Easyparser/Bright Data per-ASIN offers | Yes — `SCANNER_OFFER_ENRICHMENT` gated, credit-gated, never during scans; offline placeholder otherwise. |
| `costco_api_client.py` | OpenWebNinja / Unwrangle | Yes — `COSTCO_CATALOG_SOURCE` OFF default (local CSV only); refresh is a scheduled/CLI-only action. |
| `proof_batch_easyparser_adapter.py` | (via injected client only) | Yes — allow_live=False + explicit client required; nothing else can construct it. |

Proof-batch family imports are provider-client-free: `proof_batch.py`
(→ intel_schema, benchmark_validation), `proof_batch_run.py` (→ intel_schema,
benchmark_validation, live_gate, market_snapshot_store, proof_batch),
adapter (→ proof_batch, proof_batch_run). Import-audit tests assert no
`requests`/`urllib`/`socket`/`http`/provider tokens in `proof_batch_run.py`
and `proof_batch.py`; `test_proof_batch_easyparser_adapter` patches every
`requests` verb + `easyparser_client.get_easyparser_offers` to raise.

## 8. Can GET/UI/static/report/CLI-dry-run/cache-only paths call a provider?

- `main.py` (FastAPI) imports provider modules at module level (imports
  alone make no calls), but provider calls happen only inside explicit
  handlers: scanner POST refresh (live-gated), `GET /api/products/{asin}/
  offers` (on-demand Easyparser, ~5 credits/ASIN, never during scan/
  render), Canopy helper. Normal page loads/static files/cache reads make
  no provider calls (verified by `test_scanner_cache_only`,
  `test_offers_route`, `test_live_containment`,
  `test_market_snapshot_merge`, and `test_32` in the adapter suite which
  imports `main` with all transports patched to raise).
- `static/index.html` is a pure renderer (no provider SDK; only backend
  route fetches, itself guarded).
- `proof_batch_run.py` `dry-run`/`report`/`fixture-run` and
  `proof_batch.py` `build_preflight` make no provider calls; `run --live`
  refuses at the adapter gate. Reports/cache-only paths exercise no
  provider code.
- `test_network_guard` + `test_live_containment` prove the same across the
  suite (network guard raises on any real request).

## 9. Current atomic persistence behavior and failure/rollback handling

- `_atomic_write_json`: temp write → flush → `os.fsync` → `os.replace`
  (atomic on same filesystem); leftover `.tmp` cleaned on failure.
- Finalization: results file temp-written → fsync → READ-BACK validation
  (kind, fingerprint, every envelope re-validated) → `os.replace` →
  run-manifest written atomically. No finalized artifact exists before
  read-back validation passes; a failed replace removes the `.tmp` and
  yields a scrubbed `failure-manifest.json` only.
- Failure lifecycle: hard-stop (binding/budget/wrong-ASIN/mapping/
  provider-error/parse-error/schema/secret/adapter-crash/persistence) →
  NO further request → NO completed-result artifact → scrubbed failure
  manifest only (run_id, fingerprint, stage, ASIN index, budget state,
  category, timestamp) → NO automatic resume.
- Output namespace exclusively `data/batch/live-validation-runs/<run_id>/`:
  `run-manifest.json`, `validated-result-envelopes.json`,
  `benchmark-comparison-report.json`, `benchmark-comparison-report.csv`,
  `human-review-summary.md`, `failure-manifest.json` (failure only).
  Protected artifacts are never write targets.

## 10. Mapping-review policy for the three known conflict ASINs

- Benchmark reference carries `title_conflict` for exactly
  `B01H40O42I`, `B08R2SRN88`, `B00N54AJZE`.
- `classify_mapping`: wrong returned ASIN or null provider ASIN → hard
  abort (`wrong_asin`); pack-block or `title_status == mismatch` → hard
  abort (`mapping_incompatible`); compatible title + benchmark
  `title_conflict` → `expected_mapping_review` (never silently resolved);
  otherwise `match`; no title/benchmark/ASIN → `unavailable` (final,
  non-aborting, nulls).
- Historical benchmark title disagreement alone is NOT a provider error —
  `expected_mapping_review` rows finalize normally and are listed for human
  review in the report and `human-review-summary.md`.

## 11. Remaining technical gaps (found by this audit)

1. Dry-run output contract (Phase 2 C): does not yet print the exact 20
   ASINs, the credit-accounting status, the exact future output directory,
   the three expected mapping-review ASINs, the hard-stop condition list,
   or the required wording `DRY RUN ONLY — NO PROVIDER CALLS, NO CREDITS
   USED, NO LIVE SNAPSHOT WRITTEN`.
2. `BudgetTracker` does not fail closed on a missing/non-positive
   `estimated_credits_per_request` (Phase 2 D: "if no conservative
   estimate or actual provider cost can be bounded, fail closed").
3. Report fingerprint linkage (Phase 2 F): `build_run_report` reads the
   results artifact but does not verify the `run-manifest.json`
   fingerprint linkage.
4. Report outcome vocabulary (Phase 2 F): `match / expected_mapping_review
   / unexpected_mapping_mismatch / unavailable / possible_market_drift /
   parse_error / provider_error` are only implicit (mapping_state +
   result_status + price classes); `STATE_DRIFT` is defined but unused;
   no explicit per-ASIN `outcome_status` and no
   `purchase_authorization_statement` field ("Passing provider-data
   validation does not authorize a purchase.").
5. No dedicated dry-run-contract tests (Phase 3 item 2 currently only
   asserts exit code 0).

No other functional gaps found. Every other Phase 2 A-G requirement is
already implemented (guard chain, adapter isolation, budget honesty,
lifecycle, comparison rules incl. no-universal-accuracy + internal labels,
direct-script/module class identity) and regression-tested.

## 12. Files proposed for modification (Phase 2-5)

Implementation (Phase 2):
- `proof_batch_run.py` — dry-run output contract (exact ASINs, accounting
  status, output dir, review ASINs, hard stops, DRY RUN ONLY wording);
  `BudgetTracker` fail-closed estimate validation; `build_run_report`
  run-manifest fingerprint linkage; per-ASIN `outcome_status` +
  `outcome_summary` + vocabulary note + `purchase_authorization_statement`;
  `human-review-summary.md` exact purchase sentence.

Tests (Phase 3):
- `test_proof_batch_easyparser_adapter.py` — dry-run contract tests (no
  adapter construction; exact printed fields), BudgetTracker
  fail-closed test, report fingerprint-linkage test, outcome-vocabulary
  and purchase-statement assertions.

Docs (Phase 1/5):
- `docs/proof-batch-final-readiness-audit.md` (this file).
- `docs/proof-batch-live-validation-approval.md` — readiness-phase
  verification rows + approval-block wording.
- `docs/proof-batch-guarded-execution-design.md` — outcome vocabulary /
  purchase statement notes.
- `docs/proof-batch-easyparser-live-adapter-plan.md` — outcome update.
- `README.md` — command documentation only.

No protected artifacts are modified (before/after sha256 proof at the
end).

---

## Implementation outcome (after Phase 2-5)

- Dry-run contract implemented and verified (exact 20 ASINs, 20/20 count,
  provider/fields, runtime caps, estimated credits, credit accounting
  status `estimated_only`, zero retries, exact output dir, 3 expected
  mapping-review ASINs, full hard-stop list, `DRY RUN ONLY — NO PROVIDER
  CALLS, NO CREDITS USED, NO LIVE SNAPSHOT WRITTEN`). Dry-run constructs
  no adapter/client (test-patched).
- `BudgetTracker` fails closed on non-positive/unbounded estimates
  (None/0/negative/bool/non-numeric → GuardError).
- Report verifies results ↔ run-manifest ↔ preflight fingerprint linkage
  (refuses when the manifest fingerprint differs); per-ASIN
  `outcome_status` vocabulary
  (`match | expected_mapping_review | unexpected_mapping_mismatch |
  unavailable | possible_market_drift | provider_error`; `parse_error` is
  a hard abort and can never appear in a finalized report — documented in
  `outcome_vocabulary`); `purchase_authorization_statement` present in the
  report JSON, CSV (`outcome_status` column), and human-review summary;
  `_run_report` CLI prints the outcome summary and purchase statement.
- Test totals: adapter suite **53 tests OK** (45 prior + 8 new: 5 dry-run
  contract, BudgetTracker fail-closed, fingerprint linkage, outcome
  vocabulary + purchase statement); focused suites **228 OK**; full suite
  **950 OK (skipped=3)** (942 baseline + 8 new). CLI smokes: dry-run exit 0
  with the full contract on the real preflight; `run --live` refuses exit 2
  (gate off; adapter gate covered by subprocess tests); fixture-run 20/20 +
  report (17 match / 3 expected review / 0 mismatch, all prices
  within_tolerance, purchase statement printed). Protected artifact hashes
  before == after. Full details in
  `docs/proof-batch-live-validation-approval.md` §8.