# TEST_RESULTS — safe audit test pass

**Audit date:** 2026-10-08 · **Baseline commit:** `2482048` (audit start; a concurrent commit `f232ef8` landed during the run)
**Environment:** Windows / PowerShell · Python 3.14.5 · Node v24.15.0 · fastapi 0.140.0 · vite 5.4.21
**Constraints honoured:** no source, fixture, benchmark or protected file was edited; no git mutation; no provider API contacted by the test runs themselves (the repo's own `sitecustomize.py`/`network_guard.py` blocks `requests` during pytest runs — **0 guard violations observed**); `NORTHSTAR_DISABLE_RATE_LIMIT=1` set only for the harness runs.

> **Audit-side incident, disclosed:** the audit's *own* instrumented read-only probe (`evidence/live-call-attribution.txt`) triggered **19 live outbound provider connections** via `GET /api/kirkland/scanner`, because `Northstar_backend/.env` sets `SCANNER_LIVE_ALLOWED=1`. The probe was stopped after one attribution run; no retry was attempted; no further provider-touching endpoint was called. This is simultaneously the evidence for **P0-01** and the reason ~19 metered requests were consumed during the audit.

---

## 1. Python backend full suite

**Command (exact):**
```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\Northstar_backend"
$env:NORTHSTAR_DISABLE_RATE_LIMIT="1"
python -m pytest -q --no-header -p no:cacheprovider --tb=no -rf
```
**Result:** `9 failed, 3512 passed, 65 skipped, 14 warnings, 64 subtests passed in 512.37s (8:32)` — exit 1. **Collected: 3,586.**

A literal `-x` variant ran to first failure: `1 failed, 1085 passed, 14 skipped`.

**Command deviations:** `tail` does not exist on this box (used `Select-Object -Last`); `--timeout=300` was rejected because **pytest-timeout is not installed**; the flag was dropped.

### Failures grouped by file

| File | Failing test | Error |
|---|---|---|
| `foundation/tests/test_frontend_gate.py` | `test_v3_shell_invariants` | `assert 50 == 48` — expected 48 `<Route path=` in `App.jsx`, found more (the frozen assertion was not updated as routes were added; 51 today) |
| `foundation/tests/test_jobs_durable_lifecycle.py` | `test_cancel_leased_job_cooperative` | unhandled thread exception `JobStateError: illegal transition cancel_requested -> running` (`jobs_state.py:490`) |
| `foundation/tests/test_owner_test_mode_non_bypass.py` | `test_frozen_file_boundary_is_a_static_rule` | path double-prefixed `Northstar_backend/Northstar_backend/costco_non_kirkland/brightdata_costco_live.py`; the file is untracked in git |
| `test_env_hygiene.py` | `test_env_example_tracked_but_is_placeholder` | `.env.example` contains the literal `"Bearer "` (a documented auth-header example) → `assert (1 == 0 or 'example' in body)` |
| `test_proof_batch.py` | `PreflightTests::test_preflight_local_cache_state` | `AssertionError: 0 not greater than 0` |
| `test_proof_batch_run.py` | `KnownTitleConflictTests::test_protected_artifacts_byte_identical` | sha256 `95cfb9ee…` != fixture `faf3575d…` (`data/scanner-search-cache.json`) |
| `test_proof_batch_run.py` | `Attempt2PreflightTests::test_no_protected_artifact_changed` | same hash mismatch |
| `tests/test_reasoning_routes.py` | `test_reasoning_models_report_per_model_state` | `assert m["configured"]` → False |
| `tests/test_reasoning_routes.py` | `test_reasoning_models_returns_catalog` | `None != 'step-5-preview-free'` |

### Baseline comparison — DIVERGES (materially better)

| Metric | `00_STATE.json` recorded (2026-09-22) | Observed 2026-10-08 |
|---|---|---|
| passed | 3,410 | **3,512** |
| failed | 23 | **9** |
| skipped | 62 | 65 |

The 23 recorded failures were all `test_proof_batch.py` + `test_proof_batch_run.py` (`FileNotFoundError: data/scanner-search-cache.json missing fixture file`). Those are now only **3**, and they are hash mismatches rather than missing files. The remaining failures are in files the recorded baseline did not mention at all.

### Root cause of the 2 `test_reasoning_routes` failures (bisected)
Reproduced deterministically:
```powershell
python -m pytest "test_provider_seller_probe.py" "tests/test_reasoning_routes.py" -k "reasoning_models"
# -> 2 failed, 14 deselected
```
`test_provider_seller_probe.py:50` calls `load_dotenv(<repo-root>/.env)` at module import → the real `OPENCODE_GO_API_KEY` enters `os.environ`. `tests/test_reasoning_routes.py:21` uses `os.environ.setdefault("OPENCODE_GO_API_KEY","test-key")`, which becomes a **no-op** once the real key is present, so the provider reports "unconfigured". Standalone, the reasoning-route file passes **7/7**. **No network test — no outbound call.**

### Protected-artifact drift (three inconsistent states)
`data/scanner-search-cache.json`: **194 B on disk**, **76,668 B at git HEAD**, **38,331 B demanded by the fixture**. The 194-byte file appeared at 22:17 during this suite run — `conftest._restore_generated_artifacts` only snapshots what exists at session start, so it cannot restore committed bytes once a prior run has already shrunk the file. The other fixture-protected artifacts (both benchmark CSVs, the manifest, the ASIN reference, `brightdata_costco_live.py`, `finance.py`, `pricing.py`, `fee_engine.py`, `product_analysis.py`) **all still match their fixture hashes** — no genuine protected drift on those.

---

## 2. Golden Goose module suite — MATCHES

```powershell
cd Northstar_backend
python -m pytest agents/golden_goose_finder -q --no-header -p no:cacheprovider
```
`513 passed in 2.12s` — **0 failures**. Recorded baseline: 511. Divergence: +2 collected tests, zero failures.

---

## 3. Acceptance / noncreative subset

```powershell
python -m pytest test_noncreative_reads.py -q --no-header -p no:cacheprovider
# -> 4 passed, 16 subtests passed in 1.22s
```
`test_ui_display.py` **does not exist** (the real harness is `Northstar_backend/test_ui_display.cjs`).

Substituted the full foundation tree:
```powershell
python -m pytest Northstar_backend/foundation/tests -q --no-header -p no:cacheprovider --tb=line
# -> 1 failed, 756 passed, 59 skipped, 13 warnings in 353.90s
```
Sole failure = `test_v3_shell_invariants` (above). `docs/northstar-phase1c/07-cross-phase-validation.md` records `172 passed / 13 skipped` for this path — **stale by ~584 tests**; the tree is much larger now.

---

## 4. AutothinK suite — MATCHES

```powershell
cd autothink
python -m pytest tests -q --no-header -p no:cacheprovider
# -> 25 passed in 0.28s
```
0 failures, 0 skips. No recorded baseline for this suite in `00_STATE.json`.

---

## 5. Node UI harnesses — 5 green, 1 failure, 1 blocked

All harnesses are **read-only in the repo** (verified: no `writeFileSync`/`mkdirSync`/`rmSync`/`spawn`/`execSync`; all assertions run against a local Vite preview with stubbed `window.fetch`). **Exception:** `verify-invite-flow.cjs` writes 3 screenshots into `northstar-os-ui/screenshots/` (`59-invite-accepted-step2.png`, `59b-signin-prefilled.png`, `59c-signed-in-workspace.png`) — pre-existing tracked files overwritten in place.

Server: `npm run preview` in `northstar-os-ui` on port 8101, killed after the run. Harnesses defaulting to `:80/ui/` were pointed at it with `$env:HARNESS_BASE_URL="http://127.0.0.1:8101/ui/"`.

| Harness | Result | Recorded baseline | Verdict |
|---|---|---|---|
| `verify-smoke.cjs` | **40 passed, 1 failed** — deep `/commerce-ops/CO-01` marker "Sourcing Validation" not found | UI 1122 (aggregate) | **1 failure** |
| `verify-acceptance.cjs` | 32 passed, 0 failed | 32/0 | MATCH |
| `verify-guards.cjs` | 11 passed, 0 failed | 11/0 | MATCH |
| `verify-admin.cjs` | 33 passed, 0 failed | 34/0 | **−1 assertion** (likely one retired) |
| `verify-golden-goose.cjs` | 16 passed, 0 failed | 16/0 | MATCH |
| `verify-invite-flow.cjs` | 11 passed, 0 failed | 11/0 | MATCH (writes 3 screenshots) |
| `verify-live-signin.cjs` | **BLOCKED — exit 2, no run** | — | requires `NS_TEST_EMAIL` / `NS_TEST_PASSWORD`; unset in this env; fails closed by design |

No harness made an outbound/external network call (all `fetch` is stubbed; only loopback 127.0.0.1).

**Coverage gap:** the new hosted-reasoning panels (`ReasoningModelSelector`, AutothinK hosted lane, AdPilot/ListingForge/SpreadsheetLab proposal panels) have **no harness coverage** — precisely the panels that P0-02 breaks. `docs/NON_CREATIVE_REMAINING_WORK.md` §5 already records that new panels are not harness-covered.

---

## 6. Build / static checks

```powershell
npm run build
```
```
vite v5.4.21 building for production...
✓ 92 modules transformed.
dist/index.html                 1.14 kB │ gzip:  0.63 kB
dist/assets/index-CK8J0q2J.css 38.65 kB │ gzip:  7.16 kB
dist/assets/vendor-DAA2ywcB.js 163.69 kB │ gzip: 53.39 kB
dist/assets/index-CDq83HMt.js 416.06 kB │ gzip: 89.84 kB
✓ built in 1.66s
```
**0 errors.** (Note: `AGENTS.md` records an 88-module baseline; 92 modules today — the tree grew.)

`npm run lint` → `echo 'Linting not implemented yet'`, exits 0, performs **zero** linting. `eslint.config.js` is a real flat config but neither `eslint` nor `globals` is installed; `node_modules/.bin` is empty.

---

## 7. Live API boot probe (safe, local)

Boot verified: `python -m uvicorn main:app --host 127.0.0.1 --port 8017 --log-level info` from `Northstar_backend/` → `GET /health` returns `{"status":"ok","service":"northstar-backend","version":"1.0.0"}`.

**210 routes** in `/openapi.json`.

### GET sweep — status sweep plus outbound attribution

| Endpoint | HTTP | Outbound (non-loopback) connects |
|---|---|---|
| `/health`, `/health/detailed`, `/api/v1/status`, `/api/v1/models`, `/api/v1/reasoning/models`, `/api/autothink/models`, `/api/autothink/history`, `/api/sourcescout`, `/api/sourcescout/summary`, `/matches`, `/mismatches`, `/review`, `/api/monitoring/error-alerts`, `/api/products/finder`, `/api/golden-goose/health`, `/entitlements`, `/dry-run`, `/api/kirkland/discovery`, `/discovery/meta`, `/discovery/categories`, `/api/kirkland/live`, `/api/v1/catalog/stocked`, `/api/v1/plans`, `/openapi.json`, all 8 `/api/v1/noncreative/*` | 200 | **0** |
| `/api/invites/DOES-NOT-EXIST` | 404 (correct) | 0 |
| **`/api/kirkland/scanner`** | 200 | **19 → `3.232.71.244:443`** |

### Auth posture observed (unauthenticated)
- `/api/v1/foundation/*` → **401** (correct, server-side enforced).
- `/api/autothink/models`, `/api/autothink/history` → **200 unauthenticated** (P0-04).
- Anonymous rate limit (30/min) was hit by a rapid sweep, returning `429` with `retry_after` — the limiter is active and correct.

### Hosted reasoning posture observed
`GET /api/v1/reasoning/models` → 200, with `configured:false, enabled:false, armed:false, verified_model:"step-5-preview-free", runtime_default_model:null`, and 4 unverified models (`deepseek-v4.1-flash`, `glm-5.3-flash`, `mimo-v2.6-flash-free`, `kimi-k2.7-code`).

### UI-to-backend route probe (P0-02)
```
GET /api/v1/foundation/reasoning/models  -> 404   (what the UI calls)
GET /api/v1/reasoning/models              -> 200   (what the backend exposes)
GET /api/v1/foundation/jobs               -> 405   (only POST exists)
```

### Config-resolution probe (no live call)
Loading the repo-root `.env` into a process yields `configured: True, enabled: True, armed: True, runtime_default_model: step-5-preview-free`, while the running server (which never loads that file) reports all-false. **Config intent and runtime state disagree.** No `complete()` call was made.

---

## 8. AutothinK local-lane probe (local only, free, no credential)

```
local_available: True
installed models: ['qwen3:4b', 'northstar-qwen3:rev1', 'qwen3:14b', 'qwen2.5vl:7b']
route: {"task_class":"AUTOTHINK_RESEARCH","label":"research",
        "plan":["Classify intent","Gather available local data","Reason step-by-step","Deliver findings"],
        "gateway_backend": true}
context data_sources: [scanner-search-cache.json, scanner-search-cache.enriched-candidate.json, kirkland-discovery.json]
ok: True | model: northstar-qwen3:rev1 | content: READY | elapsed_ms: 14238.0
```
Confirms: the local lane produces a real completion; the deterministic router works; the context bundle is built — **and then discarded** (`server.py` contains 0 references to `build_system_prompt_with_context`).

---

## 9. Test-result summary

| Suite | Command | Passed | Failed | Skipped | Baseline | Verdict |
|---|---|---|---|---|---|---|
| Backend full | `pytest -q --no-header -p no:cacheprovider --tb=no -rf` | 3,512 | 9 | 65 | 3,410/23/62 | **DIVERGES (better, but not green)** |
| Golden Goose | `pytest agents/golden_goose_finder` | 513 | 0 | 0 | 511/0 | MATCH |
| Noncreative reads | `pytest test_noncreative_reads.py` | 4 (+16 sub) | 0 | 0 | — | MATCH |
| Foundation tree | `pytest foundation/tests` | 756 | 1 | 59 | 757/59s (state); 172/13s (doc) | state MATCH, **doc STALE** |
| AutothinK | `pytest tests` (in `autothink`) | 25 | 0 | 0 | — | no baseline |
| `verify-smoke.cjs` | node | 40 | 1 | — | UI 1122 | **1 failure** |
| `verify-acceptance.cjs` | node | 32 | 0 | — | 32/0 | MATCH |
| `verify-guards.cjs` | node | 11 | 0 | — | 11/0 | MATCH |
| `verify-admin.cjs` | node | 33 | 0 | — | 34/0 | −1 assertion |
| `verify-golden-goose.cjs` | node | 16 | 0 | — | 16/0 | MATCH |
| `verify-invite-flow.cjs` | node | 11 | 0 | — | 11/0 | MATCH |
| `verify-live-signin.cjs` | node | — | — | — | — | **BLOCKED** (no test credentials) |
| `npm run build` | npm | 92 modules, 0 errors | 0 | — | 88 modules | diverges (growth) |
| `npm run lint` | npm | 0 rules run | 0 | — | — | **stub, not a check** |

**Aggregate: 4,935 tests passed · 12 failed · 65 skipped · 64 subtests passed · 1 suite blocked · 1 check is a no-op.**

---

## 10. Evidence artifacts

| File | Content |
|---|---|
| `evidence/build-output.txt` | `npm run build` full output |
| `evidence/api-get-sweep.txt` | 33-endpoint GET status sweep + outbound attribution |
| `evidence/live-call-attribution.txt` | instrumented socket probe showing 19 non-loopback connects on `GET /api/kirkland/scanner` |
| `evidence/reasoning-route-probe.txt` | UI-vs-backend reasoning route probe (404 vs 200, 405) |
| `evidence/autothink-local-probe.txt` | local-lane completion probe + unwired-context evidence |
| `evidence/hosted-reasoning-config-probe.txt` | config-resolution probe (armed state from `.env`, no live call) |
| `evidence/test-suite-output.txt` | consolidated suite counts and baselines |
