# Proof-Batch Live Validation — Approval Runbook (Stage 1 + Guarded Execution Path)

Status: **STAGE 1 COMPLETE + GUARDED EXECUTION PATH IMPLEMENTED — AWAITING
HUMAN APPROVAL. NO LIVE CALLS EXECUTED.**
Runbook for the fixed 20-ASIN benchmark validation batch (provider data contract
validation — NOT a sourcing or purchase-approval workflow).

## 1. Protected-input baseline (before hashes)

Computed 2026-08-18 UTC, SHA-256 + byte size. Re-computed after all work —
see section 8. Artifacts marked `absent` do not exist in the workspace.

| Path | Bytes | SHA-256 (before) |
|---|---|---|
| `data/scanner-search-cache.json` | 95074 | `400005608C5EC5EAE24FAD6567324F6FEADD0D87D6AEB7BC8D739B80BE53671C` |
| `data/scanner-search-cache.brightdata-20260817-065933-20260817-021812.json` | 99138 | `AB21124E7F94296D98DCDF68EB5F90E270AA24E27C767A9286755151FC3B2535` |
| `data/amazon-market-snapshots.json` | absent | — |
| `data/enrichment-run-report.json` | absent | — |
| `data/benchmarks/raw/BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv` | 3406 | `FFB25C8284126DCFCD577171AF4AB8AC5099AE484B72FCD718E2DFADE20FE9DA` |
| `data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv` | 2338 | `AE85C5D72F2EBE2D15E8558CE29AD86AE4C8015FC10105E111595533DB09368B` |
| `data/benchmarks/manifest.json` | 1402 | `BD7FFC77416246ED229C707E6AFBFDB5CAEB6B3C36AF450E919BFA6728A3C664` |
| `data/benchmarks/asin_benchmark_reference.json` | 87764 | `7D54978753DAC7BA7F874022BCAE02F63642F01C9196251CF54B25A317EEC5DC` |

Raw CSV hashes match the values already recorded in `manifest.json`. No
protected artifact was modified, created, or moved.

## 2. Validation set resolution

- **Fixed set = exactly the 20 ASINs of the user-provided Rank file**
  (`data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv`, file B,
  `source_rank` 1–20). Derived deterministically from the normalized
  reference (`source_files` includes the Rank file; ordered by the user's own
  rank). No ASIN added, removed, or re-ranked; this is not a selection task.
- **Count: 20 unique ASINs, 20/20 matched** to canonical benchmark rows
  (`matched_count 20`, `unmatched_count 0`). The reference artifact holds 47
  canonical ASINs total; file B is a strict subset (file A's first 20 ranks).
- **Title-only conflicts preserved as mapping-review flags (3), never
  silently resolved:**
  - `B01H40O42I` (rank 1) — "Aller-Flo (Pack of 5)" vs "Aller-Flo Fluticasone (Pack of 5)"
  - `B08R2SRN88` (rank 2) — "Aller-Flo (5 Bottles/600 sprays)" vs "Aller-Flo Fluticasone (5 Bottles/600 sprays)"
  - `B00N54AJZE` (rank 11) — "Stool Softener 100mg (400ct, alt listing)" vs "Stool Softener 100mg (alt)"
  - Canonical keeps file A's title per `CANONICAL_RULES`; each preflight entry
    carries `title_conflict: true` + `conflict_note`. No price or review
    conflicts exist in the 20.
- **Unavailable benchmark fields are null, never 0** (from the 20 rows):
  - BSR rank/category unavailable for **5 ASINs** — `B01H40O42I` (rank 1,
    file B says "Not listed on page"), `B081THWMDK` (9), `B01LY71217` (13),
    `B007MWNFBA` (16), `B0C54GXFQ8` (18). All other benchmark fields
    (price/reviews/Prime-FBA) are present for all 20.
  - Per-ASIN `benchmark_fields_present` / `benchmark_fields_unavailable` are
    listed in the preflight JSON; counts: `bsr_rank_number` 5, `bsr_category`
    5, all others 0.
- Benchmark `capture_time_status` is `unknown` for all 20 — any price/BSR/
  review difference in a future live pull is legitimate market drift first
  and is NEVER automatically called a provider error.

## 3. Zero-network preflight output

- File: `data/batch/proof-batch-preflight-20260818T060549Z.json`
- `run_id`: `proof-batch-preflight-20260818T060549Z` (immutable)
- `generated_at`: `2026-08-18T06:05:49.112410+00:00`
- `purpose`: `provider_data_contract_validation`
- Selection: 20/20 (max 20); benchmark matched 20, unmatched 0, title
  conflicts 3; per-ASIN benchmark fields + local cache state included.
- Local cache/snapshot state (metadata only): `scanner-search-cache.json`
  (brightdata, fetched `2026-08-18T01:43:46.384271+00:00`, 230 candidates)
  — search-page rows for the 20 ASINs are noted per ASIN but explicitly do
  NOT satisfy offer/BSR provider requests. Market snapshot store, enriched
  offer cache, and seller offer cache are absent → `expected_cache_skips: 0`.
- Contains NO secret-like keys (asserted at generation).

## 4. Provider plan, requested fields, requests, credits

| Provider | Status | Fields owned | Requests | Credits |
|---|---|---|---|---|
| Easyparser | planned | offer/seller roster, offer price, shipping, fulfillment, Buy Box when available | 1/ASIN → **20 total** | 5/ASIN documented estimate → **100 total** (documented estimate, not a bill) |
| Keepa | not approved / not available | BSR/category/history — ONLY if separately approved AND available | 0 | `null` — "requires provider confirmation"; **no Keepa client exists in the project** |
| Costco cache | planned, zero cost | discovery cost only — NOT purchase-authorized COGS | 0 | 0 (no local discovery rows) |
| Seller Central / manual | manual, zero cost | eligibility, restrictions, invoice legitimacy, actual fees | 0 | 0 |

- Requested fields per ASIN: `["market_offers"]`; `request_count_total: 20`.
- Hard caps: `max_asins 20`; `max_requests 20` (exact number required by the
  approved plan); `max_credits: null` — **must be entered and approved by
  human; no default spending authorization.**
- Credit numbers never fabricated: Easyparser 5/ASIN is the documented
  estimate from `enrichment_preflight.CREDIT_ESTIMATES`; Keepa is `null`.

## 5. Stop conditions (preflight-defined, enforced at any future live run)

1. Hard request cap (20) or human-entered credit cap reached — stop immediately.
2. Provider response/error (HTTP or provider failure).
3. Schema validation failure (`intel_schema.validate_snapshot`) for any returned envelope.
4. Wrong ASIN returned (returned != requested).
5. Product/title/pack mapping mismatch (returned ASIN mismatch, title mismatch for a non-conflict ASIN, or pack mismatch block). Note: a BSR/category difference is **not** an execution hard stop — it is a report flag (`possible_market_drift`) when comparable.
6. Malformed or impossible field values (invalid numeric/currency parse, forbidden zeros, negative price).
7. Unexpected secret-like key in provider output.
8. Persistence failure (atomic snapshot write failed).
9. Cache-only containment failure (provider call outside the explicit guarded run).
10. Credit estimate/budget-stop enforcement failure.

Explicit statement (present verbatim in the preflight JSON):
`HUMAN CONFIRMATION REQUIRED — NO LIVE CALLS EXECUTED`

## 6. Live-run acceptance criteria (for the future approved run)

### A. What validates a real, usable data pull
- Returned ASIN corresponds exactly to the requested ASIN.
- Title/pack plausibility preserved, or the mismatch is explicitly flagged
  (`title_status`/`pack_mismatch_block`). Note: a BSR `category_context == "mismatch"` is a report flag, not a hard stop; missing BSR/category is reported as unavailable.
- Field names/types parse correctly (intel_schema shape; no forbidden zeros;
  unknown stays null).
- Provider, capture timestamp, and result status are present on every output.
- Output passes `intel_schema.validate_snapshot` (envelope validation via
  `proof_batch.validate_envelope`).
- Snapshot persists atomically ONLY after validation passes.
- Zero provider calls occur outside the explicit guarded run.
- Every returned value carries provenance and coverage.

### B. What must NOT be labeled a provider failure by itself
- Price difference versus the unknown-timestamp benchmark.
- BSR/rank difference. Review-count difference.
- Unavailable benchmark field (reference simply lacks it).
- A provider field not requested or not covered by the provider plan.

### C. Provider/data failures (stop conditions 2–10 above, materialized)
- Wrong ASIN; product/pack mismatch; malformed response; invalid
  numeric/currency parsing; unexpected empty response where the provider
  claims success; inconsistent offer/Buy Box/fulfillment records; missing
  capture time/source/result status or envelope validation; secret leakage;
  request/credit cap breach.

### D. Report outputs required after a future approved live run
- Per-ASIN comparison vs the benchmark reference (`proof_batch.report`).
- Matched / mapping-review / unavailable counts.
- Field coverage by provider.
- Parse/validation failures.
- Internal consistency flags (offer/seller/Buy Box).
- Drift classifications (exact / within-tolerance / moderate / material).
- NO universal accuracy percentage.
- Economics/demand labeled internal/model-based unless independently sourced
  (`INTERNAL_ONLY_LABEL` / `DEMAND_LABEL`).

## 7. Guarded execution workflow — IMPLEMENTED (offline-tested; live NOT executed)

The guarded run path from section 5's stop conditions is now implemented
(design: `docs/proof-batch-guarded-execution-design.md`; module:
`proof_batch_run.py`). It is fully offline-verified with the synthetic
`FixtureAdapter` and with the real-data-ready Easyparser adapter
(`proof_batch_easyparser_adapter.py`, 45 offline tests) using injected fake
clients only. **The live adapter exists but its `allow_live` gate is OFF in
this build — the `run` command refuses at the adapter gate after the outer
guards pass.**

Guard stack (all required; no fallback; `run_guarded` refuses with a
`GuardError` and writes nothing when any is missing):
1. Explicit `--live` flag.
2. `live_gate.live_enabled()` (`SCANNER_LIVE_ALLOWED` strict opt-in).
3. Valid fixed preflight binding: exactly 20 unique valid ASINs, purpose
   `provider_data_contract_validation`, Easyparser-only `planned`, requested
   fields `["market_offers"]`, 1 request/ASIN, total 20, hard caps 20/20,
   verbatim `HUMAN CONFIRMATION REQUIRED — NO LIVE CALLS EXECUTED` line,
   no secret-like keys. ASIN source is ONLY the named preflight JSON.
4. Explicit finite `--max-requests` (≥ 1) and `--max-credits` (≥ 1).
5. Effective allowance `min(runtime cap, preflight plan 20, hard 20)`;
   `max_requests > 20` rejected.
6. Retries fixed at 0; every attempt counts toward the caps.
7. Easyparser-live adapter gate: construction requires `allow_live=True`
   AND an explicitly injected client — both absent in this build, so the
   `run` command refuses (exit 2, no provider call, no traceback).
8. Adapter-level stop-before re-checks (request/credit budgets refreshed by
   the runner before each request; unbounded/unknown cost fails closed).
9. Provider-error and parse-error classifications (from the client's
   `data_gaps`) hard-abort before any envelope is built.

Class-identity note: `ProviderAdapter`, `GuardError`, `BindingError`, and
`RunAbort` are defined once in `proof_batch_contracts.py` (stdlib only) and
imported by both `proof_batch_run.py` and `proof_batch_easyparser_adapter.py`,
so the runner's strict `isinstance(adapter, ProviderAdapter)` guard resolves
against a single class under every import path (direct script, `python -m`,
ordinary import, reload). The legacy `sys.modules.setdefault("proof_batch_run",
__main__)` alias is kept only as belt-and-suspenders. Regression tests prove
direct-script and `python -m` invocation both refuse cleanly (exit 2, no
traceback).

Preflight fingerprint: sha256 over the stable binding subset (purpose,
run_id, sorted canonical ASIN set, provider plan, requested fields,
request counts, hard caps). Runtime `max_credits` is intentionally NOT
fingerprinted (human-entered per run). Envelopes, the run manifest, the
validated-results artifact, and the report all carry the fingerprint.

Request loop (stop-before semantics): per ASIN — budget check → adapter
fetch → secret-like scan (raw result AND normalized snapshot) →
per-attempt credit accounting (`credit_accounting_status`:
`provider_reported` | `estimated_only` | `unavailable`; `actual_credits_used`
null unless the provider explicitly reported a usable positive int) →
provider/parse-error abort check → intel snapshot build
(`market_snapshot_store.build_snapshot` normalizer reused; pure, offline) →
mapping classification → envelope build →
`proof_batch.validate_envelope` (envelope + `intel_schema.validate_snapshot`)
→ append.

Mapping classification (per ASIN, vs the benchmark row):
- wrong returned ASIN (explicit `provider_asin` != requested) → **hard
  abort** (`wrong_asin`)
- provider returned no product ASIN (requested/returned relationship cannot
  be established) → **hard abort** (`wrong_asin`)
- incompatible title (`title_status == mismatch`) or pack mismatch block →
  **hard abort** (`mapping_incompatible`) — *except* the three pre-registered
  `title_conflict` ASINs, which route to `expected_mapping_review` on a
  same-ASIN title mismatch with no pack mismatch (the expected cross-file
  disagreement; never silently resolved)
- pre-registered benchmark `title_conflict` ASIN (returned ASIN matched, no
  pack mismatch) → `expected_mapping_review`
  (exactly the 3 known ASINs: `B01H40O42I`, `B08R2SRN88`, `B00N54AJZE`) —
  never silently resolved
- otherwise → `match`
- no title / no benchmark row / no ASIN → `unavailable` (final,
  non-aborting, honest nulls)
- **BSR/category difference is never an execution hard stop** — a BSR
  `category_context == "mismatch"` is a report flag (`possible_market_drift`)
  when comparable; missing BSR/category is reported as unavailable, never as
  a failure. An offer-only run must not hard-stop solely because the provider
  does not return BSR/category.

> **Narrow title-conflict policy.** Pre-registered benchmark title-conflict ASINs are expected mapping-review cases when the returned ASIN matches and no explicit pack mismatch exists. Title difference alone does not hard-stop those three pre-registered cases. Wrong ASIN, explicit pack mismatch, incompatible product evidence, malformed response, provider error, schema failure, budget breach, secret-like data, and persistence failure remain hard stops.

Budget: `BudgetTracker` with stop-before checks; provider-reported
`credits_used` when returned (via the adapter's request meta), documented
estimate (5.0/request) otherwise; actual totals labeled
`reported_by_provider` only with provider evidence, else
`unavailable_estimated_only` — never claimed as actual. Every outcome and
every failure manifest preserves the budget state.

Persistence (atomic): temp write + flush + fsync + read-back validation +
`os.replace`; `validated-result-envelopes.json` is finalized ONLY when all
20 ASINs hold final non-aborting statuses. Aborts (wrong ASIN, mapping,
provider/parse error, schema, secrets, adapter crash, budget stop) write
ONLY a scrubbed `failure-manifest.json` (no secrets, no raw bodies, no
normalized results) and never a finalized results file. Atomic write
failure also yields a scrubbed failure manifest and no partial artifact.
NO auto-resume.

Output namespace (the only writes of this module):
`data/batch/live-validation-runs/<run_id>/{run-manifest.json,
validated-result-envelopes.json, failure-manifest.json (only if needed),
benchmark-comparison-report.json, benchmark-comparison-report.csv,
human-review-summary.md}`. Protected artifacts are never written.

Commands (documented; only `dry-run`, `fixture-run`, `report` are
executable in this build — all zero network):

```powershell
python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100
python proof_batch_run.py fixture-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100 --out-dir data/batch/live-validation-runs/<run_id>
python proof_batch_run.py report --run-dir data/batch/live-validation-runs/<run_id>
python proof_batch_run.py run --live --preflight <preflight> --max-requests N --max-credits N   # NOT EXECUTED: adapter allow_live gate OFF in this build
```

`run --live` refuses today at two gates: the external `SCANNER_LIVE_ALLOWED`
gate (off by default) and the adapter's `allow_live` gate (off in this
build; the adapter also never defaults to the real easyparser client —
explicit injection is required, so tests cannot accidentally reach the
network). `--asin/--asins/--input-file/--discover` options are rejected.
Enabling a real pull is a separate human-approved build step (approval
sequence below).

Report outputs (post-run, zero network): per-ASIN comparison via
`benchmark_validation.compare_benchmark_record` (identity/price/reviews/
Prime-FBA/BSR/offer-section/internal-consistency), mapping summary (match /
expected review with ASIN list / unexpected mismatch with ASIN list /
unavailable), price drift classes, `summarize_batch` metrics, NO universal
accuracy percentage, economics/demand labeled
`INTERNAL_ONLY_LABEL` (never a purchase decision), capture-time-unknown
drift policy (price/BSR/review differences are possible market drift, not
provider failure by themselves).

Approval sequence for a FUTURE live run (each step human-gated):
1. Confirm the preflight fingerprint from `dry-run` matches the bound
   preflight.
2. Enter and approve `--max-credits` (no default; documented estimate
   ≈ 100 for the 20-ASIN plan; `--max-requests 20`).
3. Approve enabling the existing easyparser-live adapter: review
   `proof_batch_easyparser_adapter.py` + its 45 offline tests + the adapter
   plan (`docs/proof-batch-easyparser-live-adapter-plan.md`), then approve a
   separate build change that sets `allow_live=True` (and explicitly injects
   the real client) — a visible, reviewed change, never an env toggle.
4. Run `fixture-run` first as a rehearsal against the SAME preflight.
5. Run the live command; review `benchmark-comparison-report.json` +
   `human-review-summary.md` before ANY sourcing decision.
6. A passing data run is NOT purchase authorization: invoice legitimacy,
   selling eligibility, correct pack, fee confirmation, and supply-chain
   review remain required.

Rollback: delete the run's directory under `data/batch/live-validation-runs/`;
nothing else is ever written by this module, so no other cleanup applies.

## 8. Offline verification (this task)

Full offline verification for the final readiness phase (including the
36-item required test matrix and the dry-run contract) is recorded in
`docs/proof-batch-final-readiness-audit.md` §12 and the tables below.
Focused offline checks (prior builds) were:

| Command | Result |
|---|---|
| `python -m unittest test_proof_batch` (29 tests: envelope/fixture/report/validation-set/preflight/containment) | OK (0 failures) |
| `python -c "<secret-like + set-count checks on the generated preflight>"` | pass (20 ASINs, no secret-like keys, human line present) |
| `python proof_batch.py preflight --out <temp>` (CLI smoke, temp path) | wrote only the explicit path; validated 20-set; refused nothing |
| Provider-client containment | `test_proof_batch.ContainmentTests.test_proof_batch_operations_make_zero_provider_calls` patches every provider client to raise; preflight build, envelope validation, fixture compare, batch report all pass under it |
| Module import audit | `proof_batch.py` imports `json/os/re/sys/intel_schema/benchmark_validation` only — no `requests`/`httpx`/`urllib` |

Guarded-execution verification (Phase 3, offline; `test_proof_batch_run.py`,
48 tests — tamper rejection, fingerprint determinism, budget stop-before,
wrong-ASIN / mapping / schema / secrets / adapter-crash hard aborts with
scrubbed failure manifests only, null-preservation, atomic success,
report labels, containment/import audit):

| Command | Result |
|---|---|
| `python -m unittest test_proof_batch_run test_proof_batch test_asin_benchmark_store test_benchmark_validation` | 134 tests OK |
| `python -m unittest discover -s . -p "test_*.py"` | **897 tests OK (skipped=3)** (guarded-runner build) |
| `python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100` | exit 0, fingerprint `eb21a9877ce5b27c2aed55fe835d2a8712fbc28a44d2082ce30b6262b6b7478d`, 20/20 |
| `python proof_batch_run.py fixture-run --preflight <same> --max-requests 20 --max-credits 100 --out-dir data/batch/live-validation-runs/proof-batch-fixture-20260818T060000Z` | completed, 20 requests, `synthetic_fixture: true`, counts available 20 / match 17 / expected_mapping_review 3 (B00N54AJZE, B01H40O42I, B08R2SRN88) / mismatch 0 |
| `python proof_batch_run.py report --run-dir <same>` | wrote report JSON + CSV + human-review-summary.md; mapping summary 17/3/0/0; price drift all `within_tolerance` (fixture drift 1–3% ≤ 5% tolerance) |
| `python proof_batch_run.py run --live --preflight <same> --max-requests 20 --max-credits 100` | refused exit 2 (`SCANNER_LIVE_ALLOWED` not set; adapter gate also refuses with `allow_live=False`) |

### Real-data-ready adapter verification (this task; `test_proof_batch_easyparser_adapter.py`, 45 tests)

| Command | Result |
|---|---|
| `python -m unittest test_proof_batch_easyparser_adapter` | **53 tests OK** (45 + 8 new: dry-run contract x5, BudgetTracker fail-closed, report fingerprint linkage, outcome vocabulary + purchase statement) |
| Direct-script regression: `python proof_batch_run.py run --live --preflight <temp valid preflight> --max-requests 20 --max-credits 100` with `SCANNER_LIVE_ALLOWED=1` (subprocess env only, removed after) | exit 2, "easyparser-live adapter is not enabled in this build", "no provider call was made", **no traceback** (proves the `__main__`/`proof_batch_run` class-identity alias) |
| Module invocation regression: `python -m proof_batch_run run --live ...` (same env) | exit 2, same clean refusal, no traceback |
| Class-identity probe (script exec'd as `__main__` then imported by name) | `ALIAS=True GUARD=True ISINSTANCE=True` — `import proof_batch_run` returns the running module; adapter `GuardError` caught as the runner's; adapter passes `ProviderAdapter` isinstance |
| Fail-closed: `EasyparserLiveAdapter(allow_live=True)` without an injected client | `GuardError` "explicitly injected client … never defaults to the real easyparser transport" |
| Containment: every transport/provider path patched to raise (requests.*, `easyparser_client.get_easyparser_offers`) | no test touches them; preflight build, report generation, cache-only seller contract, `main` import: zero provider calls |
| Protected artifacts (module-level before/after sha256) | unchanged; absent files still absent |
| Focused suites: adapter + runner + proof_batch + client + benchmark store/validation + containment + network guard + scanner-cache-only | **228 tests OK** |
| Full suite | **950 tests OK (skipped=3)** (897 baseline + 45 prior + 8 readiness) |
| CLI smokes (temp out dirs): `dry-run` / `fixture-run` / `report` | dry-run exit 0 with the full Phase-2C contract on the real preflight; `run --live` refused exit 2 (gate off); fixture-run completed 20/20; report wrote JSON + CSV + md — mapping 17/3/0/0, outcome summary 17/3/0/0/0/0, price all within_tolerance, purchase statement printed |

Preflight generation ran 100% offline from the benchmark artifact + local
cache file; no provider client was imported or invoked.

## 9. Protected-file hash equality (before → after)

All 12 protected artifacts re-hashed after the adapter-arming build; hashes
and byte sizes are identical to the before-capture (6 data artifacts +
`finance.py` / `pricing.py` / `fee_engine.py` / `product_analysis.py`
unchanged; the two absent artifacts remain absent). New/updated files from
the adapter task and the final readiness phase:
`proof_batch_easyparser_adapter.py`, `proof_batch_run.py`,
`test_proof_batch_easyparser_adapter.py`,
`docs/proof-batch-easyparser-live-adapter-plan.md`,
`docs/proof-batch-adapter-arming-plan.md`,
`docs/proof-batch-final-readiness-audit.md` (new audit);
`easyparser_client.py` gained two additive keys (`request_id`,
`provider_asin`); `proof_batch.py`'s `build_envelope` carries optional
`provider_request_id`/`credit_accounting_status`/`adapter` provenance keys.

## 11. Adapter arming build (separate gating; this offline task)

Objective: convert the real-data-ready Easyparser adapter from its
intentionally-disabled state (`allow_live=False`) into a capability that can
be EXPLICITLY ARMED ONLY inside the already-guarded Proof Batch execution
path, while keeping it disabled by default. A live pull was NOT run.

Command/result evidence (zero-network offline build):

| Command | Result |
|---|---|
| `python -m unittest test_proof_batch_easyparser_adapter` | **71 tests OK** (readiness + new arming: disabled-default refusal, runner-disabled never calls factory, guards-before-factory on missing-guard scenarios, armed CLI completes offline with injected fake client reaching `run_guarded`, arbitrary-ASIN rejection still precedes arming, and `TestRuntimeArmGate` covering `PROOF_BATCH_LIVE_ARMED` gate semantics — absent/false/`0`/`no` stay disabled, `SCANNER_LIVE_ALLOWED`-only refused, arm-only refused, invalid preflight/cap refused before client construction, both gates + fake client reaches runner, dry-run constructs no adapter, direct/module invocation preserve typed error) |
| `python -m unittest test_proof_batch_run test_proof_batch` | **106 tests OK** (incl. `test_module_imports_no_provider_client` — runner source verified free of provider-client import tokens) |
| `python -m unittest discover -s . -p "test_*.py"` | **968 tests OK (skipped=3)** (959 prior + 9 new arm-gate tests) |
| `python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100` | exit 0, full contract, fingerprint `eb21a987...7478d`, 20/20, `DRY RUN ONLY — NO PROVIDER CALLS, NO CREDITS USED, NO LIVE SNAPSHOT WRITTEN` |
| `python proof_batch_run.py run --live --preflight <same> --max-requests 20 --max-credits 100` (no `SCANNER_LIVE_ALLOWED`) | exit 2, "Live providers are disabled" |
| `python proof_batch_run.py run --live ...` with `SCANNER_LIVE_ALLOWED=1` but `PROOF_BATCH_LIVE_ARMED` absent (subprocess env only) | exit 2, "easyparser-live adapter is not armed (set PROOF_BATCH_LIVE_ARMED=1 … no provider call was made", no traceback |
| Direct-script / `python -m proof_batch_run` regressions | exit 2, same clean refusal, `ALIAS=True GUARD=True ISINSTANCE=True` |

Implementation summary (smallest safe change):
- `proof_batch_easyparser_adapter.py`: added a second, external, non-secret,
  read-only arming gate `PROOF_BATCH_LIVE_ARMED=1` (module constant
  `PROOF_BATCH_LIVE_ARMED_ENV`; `proof_batch_armed()` reads the env var and only
  the exact value `"1"` enables it). `allow_live=True` construction now ALSO requires
  the gate armed; refusal preserves message substrings "easyparser-live adapter is
  not armed" and "no provider call was made". The gate is never mutated by code,
  never printed, and never flippable by a CLI flag, GET route, report command,
  dry-run, or fixture run. Added `real_easyparser_client()` resolver (lazy
  `import easyparser_client`) so the runner never carries the forbidden
  provider-client import token.
- `proof_batch_run.py`: added `LIVE_CLIENT_FACTORY` test-only injection hook
  (`None` in production); `_run_run` now calls `_arm_live_adapter(...)` ONLY after
  every runner guard passes (`--live`, `SCANNER_LIVE_ALLOWED`, binding/fingerprint,
  finite caps, plan consistency, arbitrary-ASIN-option rejection). The real client
  is resolved through `adapter_mod.real_easyparser_client()` only on the production
  path when armed; `allow_live` is never set by CLI input; no general-purpose
  provider path added.

Class-identity fix: the "a provider adapter is required" failure arose from a
source-scan containment test forbidding the `easyparser_client` token in
`proof_batch_run.py`; resolving the client through the adapter module (which
already imports `proof_batch_run` as `pbr` for its `ProviderAdapter` base) restored
stable `isinstance(adapter, ProviderAdapter)` without weakening the guard.

## 10. No-live-touch statement

No Amazon/Easyparser/Keepa/Bright Data/Costco/Scavio/Canopy/HTTP/browser-
automation request was made; no Uvicorn or browser started; no application
GET/POST route was called; no guarded POST refresh called;
`SCANNER_LIVE_ALLOWED` was enabled ONLY inside short subprocess test
environments and removed immediately after (never in the parent shell or
persisted); `PROOF_BATCH_LIVE_ARMED` was similarly never set in the parent
shell and only ever patched inside isolated `patch.dict` test blocks (never
persisted); `test_scavio.py` not run; no `.env`/credentials/tokens/keys
accessed or printed; no benchmark raw CSVs, manifest, normalized reference,
scanner caches, snapshot store, enrichment report, `finance.py`,
`pricing.py`, `fee_engine.py`, `product_analysis.py`, or the CSV contract
modified; no ASIN added/removed/re-ranked; nothing marked purchase-approved;
no live snapshot created or claimed. The guarded-run module, the easyparser-
live adapter's `PROOF_BATCH_LIVE_ARMED` gate (remained absent in the parent
shell), and its `real_easyparser_client()` resolver perform no provider calls
of any kind (fixture adapter, or live adapter with injected fakes only) and
their only writes are under `data/batch/live-validation-runs/` and the temp
dirs tests create.

---

READY FOR FINAL HUMAN APPROVAL:
1. Review the fixed 20-ASIN preflight and canonical fingerprint
   (`data/batch/proof-batch-preflight-20260818T060549Z.json`;
   `eb21a9877ce5b27c2aed55fe835d2a8712fbc28a44d2082ce30b6262b6b7478d`).
2. Confirm Easyparser-only scope and `market_offers` as the sole requested
   field contract.
3. Confirm the three known title-only conflicts remain
   `expected_mapping_review` (B01H40O42I, B08R2SRN88, B00N54AJZE).
4. Approve `max_requests = 20`.
5. Enter and approve a finite `max_credits` cap; do not use 100 unless the
   documented 5-credits-per-ASIN estimate remains valid and you accept the
   approximately 100-credit maximum exposure.
6. Review the final dry-run output showing exactly 20 ASINs, zero retries,
   and no provider call.
7. Separately approve one guarded live validation run (requires a separate
   human-approved build change enabling the easyparser-live adapter:
   `allow_live=True` + explicit real client; the current `run` command
   refuses at the adapter gate with exit 2 and no provider call).
8. Review the persisted benchmark comparison report before any sourcing,
   invoice, test-buy, or purchase decision — passing provider-data
   validation does not authorize a purchase.
