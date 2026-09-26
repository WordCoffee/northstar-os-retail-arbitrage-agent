# 10 — Testing Audit

Evidence states: STATICALLY_CONFIRMED (S) for discovery counts. **Tests were NOT executed in this phase — runtime results are UNVERIFIED.**

## 1. Test inventory (discovered statically)

| Area | Files | `def test_` / `assert(` | Category | Network | Provider charges / prod writes |
|---|---|---|---|---|---|
| Backend pytest (Northstar_backend incl. agents/) | 124 files | 2,368 functions | unit + integration (TestClient) + contract | Offline (requests blocked; TestClient) | None expected (placeholders/gates) |
| Autothink pytest | 3 files | 25 functions | unit + API | Offline (adapter monkeypatched) | None |
| GG finder tests | (in the 124) | included above | unit + integration | Offline | None |
| test_shell.cjs (Analyst's Desk) | 1 | 296 asserts | contract (VM/DOM stub) | Offline (asserts no fetch) | None |
| test_ui_display.cjs (workbench) | 1 | 1,052 asserts | contract (VM/DOM stub) | Offline (never-resolving fetch) | None |
| test_functions_contract.cjs | 1 | 23 asserts | contract (KV stub) | Offline | None |
| test_ui_autothink.cjs | 1 | 25 asserts | contract (VM) | Offline | None |
| src/tests/navigation-test.js | 1 | broken | legacy | N/A | N/A |
| React SPA (northstar-os-ui) | 0 | 0 | — | — | Untested |

**Totals (statically discovered): 128 pytest files / 2,393 `def test_` functions (2,368 backend + 25 autothink); 1,396 JS `assert(` calls.**
- **Current runtime result: NOT EXECUTED IN THIS PHASE.**
- **Passing/failing status: UNVERIFIED.**
- **Reason: plan/read-only mode; pytest execution was not approved in this phase.**
- **Last-known result (HISTORICAL, not current):** `tests/BASELINE.json` records a prior green baseline (backend 2,425 passed / 0 failed / 3 skipped / 48 subtests; GG 511 passed; shell 307; UI display 1,122; functions 31). This is a historical artifact (UNVERIFIED for the current tree).

## 2. Test configuration

| Item | Status |
|---|---|
| pytest.ini / pyproject.toml / setup.cfg | NONE anywhere (glob) |
| jest/vitest config | NONE |
| conftest.py | `Northstar_backend/conftest.py` (env scrubbing + artifact isolation) + `agents/golden_goose_finder/tests/conftest.py` (factories) |
| package.json test scripts | root: `node src/tests/navigation-test.js` (BROKEN); northstar-os-ui: none; northstar-os-retail-arbitrage-agent: `node --test` (collects nothing) |

### Runner scripts
- `scripts/run_all_tests.ps1` (188 lines) — canonical runner; runs 5 suites, diffs against `tests/BASELINE.json`; sets `NORTHSTAR_DISABLE_RATE_LIMIT=1` + temp root. Stale header claims GG `test_single_match.py` is ignored but the command includes it.
- `scripts/run_all_tests.sh` — PowerShell wrapper.

## 3. Network-block mechanism

- `sitecustomize.py` (48 lines): blocks all real `requests` calls in test processes unless `NS_ALLOW_NETWORK=1` (never in CI per `OPERATIONS_RUNBOOK.md:112`).
- `network_guard.py` (127 lines): `install()`/`block_network()`; 34 test modules import it explicitly (unittest gap for sitecustomize).
- `conftest.py` scrubs credential-shaped env vars (name-matches `KEY|TOKEN|SECRET|PASSWORD|...`), keeps `NORTHSTAR_DISABLE_RATE_LIMIT`/`ENVIRONMENT`/GG debug vars, restores per-test.

## 4. Dangerous / risky tests (do not run casually)

| File | Risk |
|---|---|
| `tools/test_chrome.py` | Launches real Chrome to cloudflare.com; **contains hardcoded credentials (email/password literals)** in source — credential-hygiene concern (S) |
| `tools/test_endpoints.py` | Spawns real uvicorn on :8000 and hits endpoints; can write to local SQLite data layer |
| `test_scavio.py` | Live script in `__main__` calling `search_kirkland_products()` (latent live-call foot-gun if executed) |
| `test_compare.py` | Empty shell (0 tests) |
| `src/tests/navigation-test.js` | Broken (undefined `navigationService`) |

## 5. Coverage gaps

- `main.py` routes: no dedicated root `test_main.py`; coverage scattered across ~23 TestClient files.
- `data_layer.py`: no `test_data_layer.py`; indirect coverage only.
- React SPA: **completely untested** (no framework/scripts/config).
- Autothink Python tests absent from the sanctioned runner.
- Postgres path untested (SQLite only).
- No e2e, visual-regression, a11y, load, migration, or data-quality suites found.

## 6. Protected fixtures referenced by tests

- `test_proof_batch_run.py` (line 41), `test_proof_batch.py` (line 24), `test_proof_batch_easyparser_adapter.py` (56-59): reference `data/benchmarks/asin_benchmark_reference.json` + raw CSV; byte-identity guard via `fixtures/protected_hashes.json` (lines 516-523, 981).
- `fixtures/protected_hashes.json`: fingerprints 2 scanner caches, 4 benchmark files, finance.py, pricing.py, fee_engine.py, product_analysis.py.

## 7. Skipped / broken / notable

- No `@pytest.mark.skip`/`xfail` markers anywhere.
- 10 runtime conditional skips when real data files absent (test_intel_clis.py, test_mapping_review.py, test_proof_batch_run.py, GG test_free_tier_router.py).
- `run_all_tests.ps1:10-11` stale comment vs executed command.
- `test_dataforseo_adapter.py` — historically 67 errors+1 failure (00_STATE.json), now listed green in baseline (historical).

## 8. Proposed safe commands (NOT run — require separate approval)

- Backend suite: `cd Northstar_backend && python -m pytest -q -p no:cacheprovider` (offline, network-blocked, env-scrubbed) — this is the sanctioned local runner path and is expected safe; NOT executed in this phase pending approval.
- SPA: none configured (no framework exists).

## 9. Counting methods

- `def test_` counts: recursive `Select-String '^\s*def test_'` over `Northstar_backend` test_*.py (124 files / 2,368) and `autothink\tests` (3 / 25).
- JS asserts: `Select-String 'assert\('` over the 4 .cjs files (296+1052+23+25=1,396).
- Commands in `17` §E. No test executed.
