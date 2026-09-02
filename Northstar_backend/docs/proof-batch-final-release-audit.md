# Proof Batch — Final Release Audit

Local Northstar_backend project, T2 Holdings LLC.
Scope: fixed 20-ASIN Easyparser provider-data-contract validation.
Status of this document: READINESS AUDIT ONLY. No live run was executed.

This audit was produced during the final offline-completion task. It reflects
the codebase state after the shared-contracts refactor (`proof_batch_contracts.py`)
and the default-disabled live adapter. Every claim below is verifiable by the
tests in `test_proof_batch_run.py`, `test_proof_batch_easyparser_adapter.py`,
and the full offline suite (959 passed / 3 skipped).

---

## 1. Current adapter state and exact live-enable mechanism

- The only real-capable adapter is
  `proof_batch_easyparser_adapter.EasyparserLiveAdapter`.
- It is **disabled by default** via a second external, non-secret, read-only
  runtime gate `PROOF_BATCH_LIVE_ARMED=1` in `proof_batch_easyparser_adapter.py`
  (module constant `PROOF_BATCH_LIVE_ARMED_ENV`; `proof_batch_armed()` reads the
  env var and only the exact value `"1"` enables it).
- `EasyparserLiveAdapter.__init__` raises `GuardError` unless **all** of:
  - `allow_live=True` (only ever set inside the guarded runner path
    `_arm_live_adapter`, never from CLI/env/UI/GET);
  - `proof_batch_armed()` is `True` (the external gate; absent in this build);
  - an explicitly injected callable `client` is supplied (never defaults to
    the real transport — fail closed);
  - `run_id` and `preflight_fingerprint` are present.
- The real client is reached only through
  `proof_batch_easyparser_adapter.real_easyparser_client()`, which lazily
  imports `easyparser_client.get_easyparser_offers` **inside** the function,
  and is only invoked after every production gate passes **and** the
  `PROOF_BATCH_LIVE_ARMED` gate is on. In this build the gate is absent, so the
  real client is never constructed or called.
- A test-only injection hook `proof_batch_run.LIVE_CLIENT_FACTORY` (default
  `None`, set only by tests) supplies a fake client for offline coverage.

The arming control is OFF by default and cannot be activated by CLI, UI, GET
route, report path, or dry-run. It is only enabled by the operator setting
`PROOF_BATCH_LIVE_ARMED=1` (a separate, non-secret runtime opt-in distinct from
`SCANNER_LIVE_ALLOWED`), and the code never mutates or prints it. This satisfies
the requirement that the arming control cannot be activated by CLI, UI, GET
route, report path, or environment variable (other than the explicit, separate,
approved gate).

## 2. Exact guard chain required before a future adapter dispatch

Future `run --live` requires, in order, every gate below. Any missing/inconsistent
gate refuses with a scrubbed `GuardError` (nothing written):

1. Explicit `--live` flag on the CLI (or `live=True` from an API caller).
2. External gate `live_gate.live_enabled()` → `SCANNER_LIVE_ALLOWED` must be an
   explicit opt-in (e.g. `1`). Off by default.
3. External Proof Batch arm gate `proof_batch_armed()` → `PROOF_BATCH_LIVE_ARMED`
   must be the exact value `"1"`. Off by default (absent/blank/`false`/`0`/`no`
   all stay disabled).
4. Preflight binding valid: `kind == "proof-batch-preflight"`,
   `purpose == "provider_data_contract_validation"`, non-empty `run_id`,
   exact `human_confirmation` line, EASYPARSER provider `status == "planned"`,
   `requests_per_asin == 1`, `credit_estimate_per_asin == 5`,
   `requested_fields_per_asin == ["market_offers"]`,
   `request_count_per_asin == 1`, `request_count_total == 20`,
   `hard_caps.max_asins == 20`, `hard_caps.max_requests == 20`.
5. Canonical ASIN list resolves to exactly 20 unique valid ASINs.
6. `_arm_live_adapter` constructs the adapter with `allow_live=True`; this
   internally requires `proof_batch_armed()` is `True` (absent in this build →
   refuses before any client contact).
6. `run_guarded` re-checks `isinstance(adapter, ProviderAdapter)`, that the
   preflight plan total is 20, that `max_requests` is finite ≥1 and ≤20, and
   `allowed = min(max_requests, plan_total, 20) ≥ 1`.
7. Arbitrary-ASIN options (`--asin`, `--asins`, `--input-file`, `--discover`)
   are rejected before adapter construction.
8. Per request, stop-before budget validation: `budget.can_request()` (request
   AND estimated-credit cap) is checked before each `adapter.fetch`; the adapter
   also re-validates request index, ASIN, and remaining budgets in
   `_guard_fetch`.

## 3. Fixed preflight, canonical 20 ASINs, provider scope, field contract, cap, review ASINs

- Authoritative preflight:
  `data/batch/proof-batch-preflight-20260818T060549Z.json`
- `run_id`: `proof-batch-preflight-20260818T060549Z`
- Canonical preflight fingerprint:
  `eb21a9877ce5b27c2aed55fe835d2a8712fbc28a44d2082ce30b6262b6b7478d`
- Purpose: `provider_data_contract_validation`
- Provider: **EASYPARSER only** (no Keepa/Bright Data/Costco/Scavio/Canopy/Amazon
  search/browser).
- Requested field contract: **`market_offers` only**.
- Maximum ASINs: 20. Maximum provider requests: 20. Retries: 0 by default.
- Canonical 20 ASINs (fixed, in preflight order):

  ```
  B01H40O42I, B08R2SRN88, B0CP6LXPLK, B00BISGJXA, B00BH3HPZW,
  B00GYZWNY6, B0045XGE9E, B002L4M4M0, B081THWMDK, B085F1QCB9,
  B00N54AJZE, B00QGMOJ4Y, B01LY71217, B07BZW88NY, B078B5N4DD,
  B007MWNFBA, B00OPQZJA6, B0C54GXFQ8, B0F7GTX962, B00BI33NU2
  ```

- Known historical benchmark title-only conflicts (mapping-review only, never
  silently resolved, never treated as a provider failure):
  `B01H40O42I`, `B08R2SRN88`, `B00N54AJZE`.

> **Narrow title-conflict policy.** Pre-registered benchmark title-conflict ASINs are expected mapping-review cases when the returned ASIN matches and no explicit pack mismatch exists. Title difference alone does not hard-stop those three pre-registered cases. Wrong ASIN, explicit pack mismatch, incompatible product evidence, malformed response, provider error, schema failure, budget breach, secret-like data, and persistence failure remain hard stops. A BSR/category difference is **never** an execution hard stop — it is a report flag (`possible_market_drift`) when comparable; missing BSR/category is reported as unavailable.

> **Attempt 1 pack-evidence note.** No explicit `pack_mismatch_block=true` was recorded before the original title-mismatch abort. Pack compatibility was not independently confirmed by the failed Attempt 1 artifact and remains visible for human review.

## 4. Shared-contract architecture (single source of truth)

- `proof_batch_contracts.py` (stdlib only) defines and is the **single** source
  of:
  - `ProviderAdapter` (abstract adapter base),
  - `GuardError`, `BindingError`, `RunAbort` (typed exceptions),
  - `ESTIMATED_CREDITS_PER_REQUEST` (shared documented estimate, `5.0`).
- `proof_batch_run.py` imports these from `proof_batch_contracts` and
  re-exports them (so `from proof_batch_run import ProviderAdapter, GuardError,
  BindingError, RunAbort` still works).
- `proof_batch_easyparser_adapter.py` imports the **same** names from
  `proof_batch_contracts` and subclasses `proof_batch_contracts.ProviderAdapter`;
  it does **not** import `proof_batch_run` merely to inherit or raise.
- `EasyparserLiveAdapter.__mro__` ends in
  `proof_batch_contracts.ProviderAdapter → object`, and the runner's strict
  `isinstance(adapter, ProviderAdapter)` guard resolves against that one class.
- Direct-script (`python proof_batch_run.py`) and module
  (`python -m proof_batch_run`) invocations both resolve the same shared class;
  the legacy `sys.modules.setdefault("proof_batch_run", __main__)` alias is kept
  only as belt-and-suspenders and is no longer the identity solution.
- Identity is stable under ordinary import **and** after `importlib.reload` of
  the runner and adapter (verified by tests `TestSharedContractIdentity`).

## 5. Provider client boundary and field coverage

`easyparser_client.get_easyparser_offers(asin)` returns a normalized dict
(`source == "easyparser"`) that can supply:

| Field | Available from client? |
|---|---|
| returned ASIN (`provider_asin` / `asin`) | Yes |
| title | Yes |
| offer list | Yes (`offers[]`) |
| offer price / currency | Yes (`price` raw; currency not separately modeled — treated as USD) |
| shipping | Yes (`shipping_text`, `shipping_is_free`, `ships_from`) |
| fulfillment | Yes (`is_fba`, `is_fbm`, `fulfilled_by_amazon`) |
| Buy Box | Yes (`buy_box_*`) |
| provider status | Yes — derived by the adapter from `data_gaps` (`provider_reported`/`error`/`parse_error` → meta) |
| capture time | Yes (`observed_at` from `request_metadata.processed_at`/`created_at`) |
| request ID | Yes (`request_id`) |
| actual provider credit usage | Yes (`credits_used`) when the provider reports it; otherwise `null` |

The adapter wraps each result with `adapter_request_meta` carrying
`requested_asin`, `request_index`, `provider`, `requested_fields`,
`estimated_credits_per_request`, `actual_credits_used`,
`credit_accounting_status` (`provider_reported` / `estimated_only` /
`unavailable`), `provider_status`, `provider_asin`, `captured_at`, `retries_used`,
`run_id`, `preflight_fingerprint`.

## 6. Honest credit limitations

- `actual_credits_used` is `null` unless the provider explicitly returns a usable
  positive `credits_used`.
- `estimated_credits_consumed` is always the documented estimate
  (`5.0`/request).
- `credit_accounting_status` is truthful: `provider_reported` only when the
  provider returned a positive int; `estimated_only` when absent; `unavailable`
  when the provider returned something unusable.
- An unknown/unbounded per-request cost fails closed (`BudgetTracker` rejects
  `None`/0/negative/bool/non-numeric estimates; the runner refuses to budget).
- The run report never states estimated credits as actual provider billing.

## 7. Every provider-call path and default blocking

- `proof_batch_run.py` imports **no** provider client at module level (verified
  by `ContainmentTests.test_module_imports_no_provider_client` scanning the
  source for forbidden import tokens).
- The adapter module imports `easyparser_client` **only inside**
  `real_easyparser_client()` (lazy, never at import).
- `run_guarded`/`_arm_live_adapter` reach the real client only after all gates
  AND the `PROOF_BATCH_LIVE_ARMED` runtime gate is on. Since the gate is absent
  in this build, the real client is never constructed.
- All provider transports and client entry points are patched to raise in every
  offline test (`test_network_guard` + `setUpModule` patches `requests.*` and
  `easyparser_client.get_easyparser_offers`).
- `dry-run` and `report` make zero network calls and construct no client.

## 8. Dry-run behavior (no client, no output, no spend)

`python proof_batch_run.py dry-run --preflight <p> --max-requests N --max-credits N`:
- Validates the preflight binding and prints exact scope (run ID, fingerprint,
  20 ASINs, provider, field contract, caps, estimated credits, retries,
  output dir, expected mapping-review ASINs, all hard-stop conditions).
- Constructs **no** adapter and **no** client, makes **no** call, writes **no**
  artifact, and consumes **no** credits (verified by
  `TestDryRunContract`, which asserts `EasyparserLiveAdapter` is never even
  constructed during dry-run).

## 9. Atomic persistence and failure-manifest behavior

- Output root: `data/batch/live-validation-runs/<run_id>/` only (no protected
  artifact is read-modify-written).
- Success path: temp write → JSON serialization read-back validation (fingerprint
  + per-envelope validation) → `os.replace` atomic finalize.
  Artifacts: `run-manifest.json`, `validated-result-envelopes.json`,
  `benchmark-comparison-report.json`, `benchmark-comparison-report.csv`,
  `human-review-summary.md`.
- Failure path: a **scrubbed** `failure-manifest.json` (no secrets, no raw
  response bodies, no normalized results) is written; no completed result
  artifact is produced; no automatic resume.
- `synthetic_fixture` flag marks fixture artifacts visibly.
- Protected artifacts are never touched (verified by `test_33_protected_artifacts_unchanged`).

## 10. Final technical gaps

- None blocking final offline completion. The live pull remains gated behind
  the `PROOF_BATCH_LIVE_ARMED=1` runtime opt-in (set only by the operator, never
  by code) plus `SCANNER_LIVE_ALLOWED` plus the full guard chain. Currency is
  assumed USD (Easyparser price is not returned with an explicit currency token);
  this is a known modeling note, not a blocker.
- Benchmark capture time is unknown, so price/BSR/review deltas are treated as
  possible market drift, never provider failure by themselves.

## 11. Exact files modified/created for this final offline completion

- Created: `proof_batch_contracts.py` (shared single-source identity/types).
- Edited: `proof_batch_run.py` (imports shared types from `proof_batch_contracts`;
  removed local duplicate `ProviderAdapter`/`GuardError`/`BindingError`/`RunAbort`
  and the `ESTIMATED_CREDITS_PER_REQUEST` constant; kept `__main__` alias as
  belt-and-suspenders).
- Edited: `proof_batch_easyparser_adapter.py` (imports shared types from
  `proof_batch_contracts`; no longer imports `proof_batch_run` for identity).
- Edited: `docs/proof-batch-adapter-arming-plan.md` (added "Shared contract
  module rationale").
- Edited: `test_proof_batch_easyparser_adapter.py` (added
  `TestSharedContractIdentity` — ordinary-import identity, strict isinstance,
  reload stability, arming-control-not-via-env).
- Created: `docs/proof-batch-final-release-audit.md` (this file).
- Created: `docs/proof-batch-live-run-approval-package.md`.
- Protected artifacts, finance/pricing/fee/product-analysis modules, CSV
  contracts, and all secret/configuration files: **unchanged**.

## 12. Conclusion

**READY FOR FINAL OFFLINE COMPLETION.**

All offline implementation, regression-test, documentation, safety-verification,
and dry-run items are complete. The fixed 20-ASIN Proof Batch is correctly
guarded, shares one stable `ProviderAdapter`/typed-exception identity across
every import path, and refuses every invalid/missing configuration with zero
provider contact. The only remaining action is a separately approved, bounded
live run (see the approval package) — which was **NOT EXECUTED** in this task.
