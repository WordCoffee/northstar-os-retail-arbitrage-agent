# Proof Batch — Easyparser Live Adapter Plan (Phase 1: design; outcome in §12)

Status: **DESIGN + IMPLEMENTATION + OFFLINE VERIFICATION COMPLETE — LIVE
PULL NOT EXECUTED.** No provider/network/HTTP call was made to produce this
plan or its implementation; the actual data pull is a separate, explicitly
approved step (approval runbook §7).

Scope: make the fixed 20-ASIN Proof Batch workflow production-ready for a
future real Easyparser `market_offers` pull. Build + offline verification
only; the actual data pull is a separate, explicitly approved step.

---

## 1. Existing Easyparser client — methods, parameters, shapes, error modes

### 1.1 The single public method

`easyparser_client.get_easyparser_offers(asin)` is the project's only
Easyparser entry point. It:

- Builds one GET to `https://realtime.easyparser.com/v1/request` with params
  `api_key` (module env, loaded at import via `load_dotenv()` — the new
  adapter must NEVER touch env or keys itself), `platform=AMZ`,
  `operation=OFFER`, `domain=.com`, `asin=<asin>`; timeout 60 s.
- **Never raises.** Every outcome returns the documented normalized dict.
- Validates the ASIN client-side (`ASIN_PATTERN`); no request is made for an
  invalid/missing ASIN or when `EASYPARSER_API_KEY` is unset (gap recorded).

### 1.2 Returned normalized shape (top level)

`source="easyparser"`, `asin` (product asin or requested asin — see §1.4),
`title`, `offer_count` (claimed), `offers_returned_count`,
`buy_box_price`/`buy_box_price_raw`/`buy_box_seller`/`buy_box_seller_id`/
`buy_box_is_fba`/`buy_box_is_fbm`/`buy_box_is_prime`/`buy_box_condition`,
`observed_fba_offer_count`/`observed_fbm_offer_count`/
`observed_amazon_offer_count`, `offers[]`, `request_zip_code`, `observed_at`,
`credits_used`, `credits_remaining`, `data_gaps[]`.

Offer entries (`_safe_offer`): `position`, `buybox_winner` (explicit flag —
winner is never inferred), `price` (provider dict `{value, raw, currency}`,
preserved verbatim), `condition`, `seller_id`, `seller_name`, `seller_rating`,
`seller_positive_percentage`, `seller_ratings_total`, `is_prime`, `is_fba`,
`is_fbm`, `is_sba`, `fulfilled_by_amazon`, `shipping_text`, `shipping_is_free`,
`ships_from`, `minimum_order_quantity`, `maximum_order_quantity`.

### 1.3 Error modes (all folded into `data_gaps`, never raised, no raw bodies)

| Mode | Gap text prefix |
|---|---|
| API key unset | "Easyparser API key is not configured." |
| Invalid ASIN | "Invalid ASIN. Expected exactly 10 alphanumeric characters." |
| Timeout | "Easyparser request timed out." |
| Network | "Easyparser request failed at the network level." |
| HTTP status | "Easyparser API returned HTTP <code>." |
| Non-JSON | "Easyparser response was not valid JSON." |
| Unexpected structure | "Easyparser response had an unexpected structure." |
| `request_info.success is False` | "…request_info.success is false…" |
| Missing `result` / `result.product` / `offer_results` | "…missing result data…" / "…missing result.product…" / "…missing result.offer.offer_results…" |

`credits_used`/`credits_remaining` are read from `request_info` (null when
absent). `observed_at` from `request_metadata.processed_at`/`created_at`.

### 1.4 Gaps found (documented, additive fixes planned)

1. **No request ID exposed.** `request_info` may carry an id but the client
   never reads it. Plan: additive key `request_id = request_info.get("request_id")`
   (None when absent). No existing behavior changes.
2. **Returned-ASIN evidence is blurred.** The client does
   `result["asin"] = product.get("asin") or asin` — when the provider omits
   `product.asin` the client reports the REQUESTED asin, so the runner could
   never distinguish "provider returned the right ASIN" from "provider
   returned no ASIN" (a hard-abort condition per §8). Plan: additive key
   `provider_asin = product.get("asin")` so the adapter can detect
   "requested/returned ASIN relationship cannot be established". The existing
   `asin` key keeps its fallback for current consumers.
3. Both additions are additive keys only; `test_easyparser_client.py` asserts
   key-level values, not full-dict equality, so no test break is expected.

## 2. What the client can expose (vs. the mission field list)

| Requirement | Client capability |
|---|---|
| provider status | Partial: success/failure folded into `data_gaps`; adapter derives `provider_status` from gap classification (success | provider_error | parse_error | unavailable) |
| request ID | **Missing today** — additive fix §1.4.1 |
| returned ASIN | `asin` (blurred when absent) + planned additive `provider_asin` |
| capture timestamp | `observed_at` (request_metadata) |
| offer/seller data | `offers[]` with explicit `buybox_winner`, seller id/name/rating/counts |
| price/currency | offer `price` dict preserved (`value/raw/currency`); Buy Box price float |
| shipping | `shipping_text`, `shipping_is_free`, `fulfilled_by_amazon`, `ships_from` |
| fulfillment | `is_fba`, `is_fbm`, `is_sba` (seller_type) |
| Buy Box data | `buy_box_*` block, only when a `buybox_winner` offer exists; winner never inferred |
| provider-reported credits | `credits_used`, `credits_remaining` from `request_info` (null when absent) |

Never fabricated anywhere: BSR, category, reviews, Prime/FBA (absent =
null), seller totals (observed counts only), fees, sales, cost, demand,
profitability.

## 3. Narrow adapter design (and why no scanner-wide fallback)

New module `proof_batch_easyparser_adapter.py`:

- Implements the runner's narrow interface (one ASIN per invocation):
  `fetch(asin, request_index) -> dict` (client-shaped result + scrubbed
  `adapter_request_meta`).
- Constructed with `adapter_config`: `run_id`, `preflight_fingerprint`,
  `request_budget` (remaining), `credit_budget` (remaining),
  `estimated_credits_per_request` (5.0, documented), **`client` (EXPLICITLY
  REQUIRED — the adapter never defaults to the real easyparser transport;
  construction fails closed without an injected client, so tests that forget
  their fake cannot accidentally reach the network)**,
  `allow_live` (default **False**).
- Construction refuses unless `allow_live=True` AND a callable `client` is
  injected; the future real build passes
  `easyparser_client.get_easyparser_offers` explicitly (a visible, reviewed
  change).
- **No fallback is possible**: no scanner cache, no `enrich_cached_asins.py`,
  no candidate discovery, no `--asin`/`--asins`/`--input-file` options, no
  batch expansion, no automatic retry. The runner's preflight binding is the
  only ASIN source. `enrich_cached_asins.py` is explicitly NOT an execution
  path: it is cache-driven and writes protected snapshot storage.
- `allow_live=False` (this build): `fetch()` raises
  `GuardError("live adapter execution not enabled in this build…")` before
  any client interaction. The CLI never sets `allow_live=True`; enabling a
  real pull is a separate human-approved build step.
- Tests exercise the full path with `allow_live=True` + injected mock client
  (zero network).

## 4. Preflight fingerprint — exact algorithm

`proof_batch_run.preflight_fingerprint(preflight)`:

```
subset = {
  purpose, run_id,
  asins: sorted(canonical uppercase ASINs),
  providers: [{provider, status, fields_owned, requests_per_asin,
               credit_estimate_per_asin} for each plan provider],
  requested_fields_per_asin, request_count_per_asin, request_count_total,
  max_asins (hard_caps), max_requests_plan (hard_caps),
}
sha256( json.dumps(subset, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode("utf-8") )
```

Runtime `max_credits` is intentionally NOT fingerprinted (human-entered per
run). ASIN order is not fingerprinted (sorted set; per-request mapping checks
validate every returned ASIN). Any change to purpose/run_id/ASIN set/
provider plan/field contract/counts/hard caps changes the fingerprint.
Authoritative preflight: `data/batch/proof-batch-preflight-20260818T060549Z.json`.

## 5. Runtime guard stack (all required; no fallback; fail closed)

1. Explicit `--live` argument.
2. `live_gate.live_enabled()` (`SCANNER_LIVE_ALLOWED` strict opt-in, set
   outside the program).
3. Valid preflight file path (exists, JSON, no secret-like keys).
4. Purpose exactly `provider_data_contract_validation`.
5. Canonical fingerprint recomputed == preflight fingerprint (binding).
6. Exactly 20 unique valid ASINs.
7. Runtime provider exactly EASYPARSER (only planned provider in plan).
8. Requested fields exactly `["market_offers"]`.
9. Explicit finite `--max-requests` (int ≥ 1, ≤ 20).
10. Explicit finite `--max-credits` (int ≥ 1; no default cap).
11. Effective allowance = min(runtime max_requests, plan 20, hard 20).
12. Plan/caps consistency (plan request_count_total == 20 == hard max).
13. Request cap not exhausted before each request (stop-before).
14. Estimated or provider-reported credit budget not exhausted before each
    request (stop-before); unbounded/unknown cost ⇒ fail closed.
15. No retries (attempts count toward both caps; retry policy is a separate
    future human-approved change).
16. Adapter `allow_live=False` in this build ⇒ `run --live` refuses at the
    adapter gate even when 1–15 pass.
17. Default mode remains zero-network dry-run.

## 6. Request/credit accounting policy

Per attempted request, preserved in `adapter_request_meta` and the envelope/
failure manifest:

- `request_index`, `request_attempted` (True for every fetch attempt, failed
  included), `requested_asin`, `provider="EASYPARSER"`,
  `estimated_credits_per_request=5.0` (documented estimate),
  `estimated_credits_consumed`, `actual_credits_used`, `credit_accounting_status`
  (`provider_reported` | `estimated_only` | `unavailable`), `request_id`
  (only if the provider returned one), `provider_status`.

Rules:
- `actual_credits_used` is null unless the provider explicitly returned
  `credits_used` (int > 0); `credit_accounting_status` follows the evidence.
- Estimates are never presented as actual; the manifest labels actual vs
  estimated explicitly.
- Stop before a request when: request cap exhausted; estimated total would
  exceed the credit cap; provider-reported running total would exceed the
  cap; or cost cannot be bounded honestly (no estimate + no provider
  evidence ⇒ refuse the run at startup: fail closed).
- Default spending cap: none — `--max-credits` must be entered by the human.
- Zero retries by default; every attempt (success or failure) consumes one
  request budget unit and its credit accounting.
- Budget state is preserved in every outcome (run manifest / failure
  manifest / per-envelope credit keys).

## 7. Response normalization contract

- Adapter returns the client-shaped normalized dict (single source of truth)
  + `adapter_request_meta`. The runner then:
  1. Secret-like scan on the client result AND the meta AND the final
     intel-shaped snapshot (reject ⇒ hard abort).
  2. `market_snapshot_store.build_snapshot(asin, result)` — pure offline
     normalizer; verified to preserve the honesty constraints (unknown stays
     null, observed counts only, claimed vs returned kept distinct,
     `offers_complete` only when claimed>0 and returned>=claimed).
  3. intel-shaped envelope snapshot via
     `proof_batch_run.build_envelope_snapshot` (identity/cost/fees/demand/
     market/economics/provenance; only provider-returned values populated;
     `amazon_price` stays null — Buy Box price lives in `market.buy_box.price`;
     economics always `unavailable` in this flow).
  4. `proof_batch.validate_envelope` ⇒ `intel_schema.validate_snapshot`
     gate before the envelope is accepted.
- Requested ASIN and returned ASIN are preserved separately
  (`requested_asin` vs snapshot `asin` + provider `provider_asin`).
- Never fabricated: BSR, category, reviews, Prime/FBA (null when absent),
  seller counts beyond observed, Buy Box winner (explicit flag only), fees,
  sales, cost, demand, profitability.

## 8. Mapping / mismatch classification

Per envelope (`classify_mapping` + adapter status merge):

- **Hard abort of the entire run** (before the next request) when:
  wrong returned ASIN (`provider_asin` present and != requested), or
  requested/returned ASIN relationship cannot be established (`provider_asin`
  absent), title/pack/product clearly incompatible (`title_status == mismatch`
  or `pack_mismatch_block`), malformed provider response (parse_error gap),
  provider-reported error, secret-like output, normalization failure,
  intel_schema validation failure, request/credit cap breach, atomic
  persistence failure.
- Mapping states: `match` | `expected_mapping_review` |
  `unexpected_mapping_mismatch` | `unavailable` | `possible_market_drift` |
  `parse_error` | `provider_error`.
  - `expected_mapping_review`: benchmark `title_conflict` + compatible
    returned title — exactly `B01H40O42I`, `B08R2SRN88`, `B00N54AJZE`.
    Preserves the conflict, allows comparison and reporting, is not a
    provider failure, and never overrides a real wrong-ASIN/incompatible
    result.
  - `possible_market_drift`: report-level classification of price/BSR/
    review differences against the unknown-timestamp benchmark (never a
    provider failure by itself).
  - `parse_error` / `provider_error`: derived from client `data_gaps`
    classification; both block final-result persistence (hard abort).
- Unknown benchmark capture time ⇒ price/BSR/review differences are possible
  market drift, not automatically provider failure. Missing values stay
  null/unavailable, never 0.

## 9. Atomic persistence state machine

Output root ONLY: `data/batch/live-validation-runs/<run_id>/`.

States:
- `running` → per-ASIN loop (budget stop-before → fetch → secret scan →
  normalize → mapping → envelope → validate). Any hard abort transitions to
  `failed` writing ONLY a scrubbed `failure-manifest.json` (no secrets, no
  raw bodies, no normalized results; budget state included). No auto-resume.
- `all 20 final non-aborting` → temp-write + fsync + read-back validation
  (fingerprint + every envelope re-validated) + atomic `os.replace` →
  `validated-result-envelopes.json`, then `run-manifest.json` (atomic).
- `report` (zero network, later command) reads ONLY the finalized
  validated-results artifact; refuses anything else; writes
  `benchmark-comparison-report.json` + `.csv` + `human-review-summary.md`
  atomically per file.
- Failure manifest only on abort; a `.tmp` leftover is cleaned; no partial
  result file can ever appear completed; protected stores are never touched.
- Fixture output in this task: same root, visibly marked
  `synthetic_fixture = true` in every artifact.

## 10. Test plan and fixture strategy

New `test_proof_batch_easyparser_adapter.py` (imports `test_network_guard` so
real network is structurally blocked; every client call is a mock; protected
files never read-write; hashes captured at module import and re-verified in
`tearDownModule`). Required coverage (mission Phase 3 list, 33 items):

1. Importing the adapter makes no provider call.
2. Dry-run makes no provider call.
3. `--live` with gate off makes no provider call.
4. Missing `--live` makes no provider call.
5. Missing preflight makes no provider call.
6. Altered preflight/fingerprint makes no provider call.
7. Non-Easyparser provider plan makes no provider call.
8. Field contract other than `market_offers` makes no provider call.
9. Arbitrary ASIN input rejected.
10. ≠20 ASINs rejected.
11. Duplicate ASINs rejected.
12. Request cap blocks next call (stop-before; manifest budget).
13. Credit cap blocks next call (stop-before; manifest budget).
14. Unknown/unbounded credit cost fails closed.
15. Retry count defaults to zero (manifest).
16. Each adapter invocation receives exactly one ASIN (mock client spy).
17. Valid fixture response normalizes correctly (envelope validates;
    coverage full; buy_box present from explicit winner).
18. Missing returned values remain null.
19. Provider-reported credits distinct from estimates (manifest).
20. Actual credits null when unavailable (`credit_accounting_status`).
21. Wrong returned ASIN hard-aborts (failure manifest only).
22. Incompatible pack/product hard-aborts.
23. Exactly the 3 known conflicts are `expected_mapping_review`.
24. Unexpected title/pack mismatch hard-aborts per mapping policy.
25. Provider error scrubbed, blocks final result persistence.
26. Malformed response scrubbed, blocks final result persistence.
27. Secret-like key rejection (input result + meta + snapshot).
28. intel_schema validation failure blocks persistence.
29. Atomic finalization for 20 valid fixtures (read-back, fingerprints).
30. Atomic write failure ⇒ scrubbed failure manifest only.
31. Fixture adapter result flows through benchmark comparison/report.
32. No provider calls from preflight generation, report generation,
    cache-only paths, UI/GET route code paths, static routes.
33. Protected artifact hashes/sizes unchanged before and after (module-level
    before/after snapshot + task-level final verification).

Fixture strategy: canonical-title-bearing synthetic client responses built
from `data/benchmarks/asin_benchmark_reference.json` (read-only), explicit
`buybox_winner`, provider-reported credits, and labeled `source: fixture`;
all labeled synthetic in artifacts. Test 32 additionally patches every
provider client to raise (mirrors `test_live_containment._provider_patches`).

## 11. Exact future commands — NOT EXECUTED

```powershell
# 1. Zero-network dry run (review resolved ASIN list, counts, credit logic,
#    output path, stop rules) — executable NOW
python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100

# 2. Offline rehearsal with the synthetic adapter (no provider) — executable NOW
python proof_batch_run.py fixture-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100 --out-dir data/batch/live-validation-runs/<run_id>

# 3. Offline comparison report on a finalized run dir — executable NOW
python proof_batch_run.py report --run-dir data/batch/live-validation-runs/<run_id>

# 4. FUTURE live run — NOT EXECUTED; requires: Easyparser-only scope
#    approved, max_requests approved, finite max_credits approved/entered,
#    SCANNER_LIVE_ALLOWED enabled outside the program, AND a separately
#    approved build that sets adapter allow_live=True.
python proof_batch_run.py run --live --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100
```

In THIS build, command 4 refuses at the adapter gate (allow_live=False) even
when all other guards pass.

---

## 12. Implementation outcome (after Phase 2/3)

Implemented as designed, with three documented refinements:

1. **Explicit client injection (fail closed).** The adapter never defaults to
   `easyparser_client.get_easyparser_offers` — construction requires an
   explicitly injected `client` (callable) alongside `allow_live=True`. A
   test that forgets its fake fails closed at construction; the future real
   build passes the real client explicitly (visible, reviewed change). The
   injected client must implement the one-ASIN contract of
   `easyparser_client.get_easyparser_offers`.
 2. **Shared-contract class identity.** `ProviderAdapter`, `GuardError`,
    `BindingError`, and `RunAbort` are defined once in
    `proof_batch_contracts.py` (stdlib only) and imported by both the runner
    and the adapter, so the adapter's base class and raised errors are the
    SAME objects the runner validates against — under direct-script,
    `python -m`, ordinary import, and `importlib.reload`. Regression tests
    prove direct-script and `python -m` invocation both refuse cleanly (exit 2,
    no traceback), an isolated identity probe reports
    `ALIAS=True GUARD=True ISINSTANCE=True`, and the reload-stability test
    proves the shared identity persists after reloading both modules.
3. **Provider/parse-error hard aborts.** The runner now aborts (scrubbed
   failure manifest) when the adapter's meta classifies a result as
   `provider_error` or `parse_error`, and atomic-write failure during
   finalization also produces a scrubbed failure manifest with no partial
   artifact.

Delivered:
- `proof_batch_easyparser_adapter.py` — `EasyparserLiveAdapter`
  (one-ASIN `fetch`, `adapter_request_meta`, stop-before re-checks,
  retries=0, secret scans, credit accounting
  `provider_reported | estimated_only | unavailable`).
- `easyparser_client.py` — two additive keys: `request_id`
  (`request_info.get("request_id")`) and `provider_asin`
  (`product.get("asin")`); existing behavior unchanged (10 client tests OK).
- `proof_batch_run.py` — adapter wiring behind the full guard stack
  (`run --live` refuses at the adapter gate in this build), request-meta
  credit accounting, provider_asin mapping evidence + relationship
  hard-abort, provider/parse-error aborts, persistence failure manifest,
  `_is_synthetic_adapter`, module-alias registration.
- `proof_batch.py` — `build_envelope` provenance now optionally carries
  `provider_request_id` / `credit_accounting_status` / `adapter`.
- `test_proof_batch_easyparser_adapter.py` — **45 tests OK** covering the
  33-requirement list + mandatory regressions (direct-script, `-m`,
  class-identity, fail-closed client injection, CLI safety model).
- Focused suites 209 OK; full suite **942 OK (skipped=3)** (897 baseline +
  45 new); CLI smokes (dry-run / fixture-run / report) pass; protected
  artifact hashes before/after identical; `SCANNER_LIVE_ALLOWED` only ever
  set inside subprocess test environments and removed immediately.
- No live/provider/HTTP call, no secrets accessed, no protected artifact
  modified, no `test_scavio.py`, no server. See
  `docs/proof-batch-live-validation-approval.md` §8/§10 for the full
  verification record and the 8-item READY FOR HUMAN APPROVAL block.

Final readiness phase (audit: `docs/proof-batch-final-readiness-audit.md`):
the dry-run now prints the full Phase-2C contract (exact 20 ASINs, credit
accounting status `estimated_only`, exact output dir, the 3 expected
mapping-review ASINs, every hard-stop condition, `DRY RUN ONLY — NO
PROVIDER CALLS, NO CREDITS USED, NO LIVE SNAPSHOT WRITTEN`) without
constructing any client; `BudgetTracker` fails closed on unbounded
estimates; the report verifies the results↔run-manifest↔preflight
fingerprint linkage and carries per-ASIN `outcome_status` +
`outcome_summary` + `purchase_authorization_statement`. Adapter suite now
**53 tests OK**; focused 228 OK; full suite **950 OK (skipped=3)**.
