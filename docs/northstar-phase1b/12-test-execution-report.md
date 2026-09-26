# 12 — Test Execution Report

## Executed

| Command | Result |
|---|---|
| `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider` | **74 passed, 0 failed, 0 skipped** (≈9.4s) |
| `cd northstar-os-ui && npm run build` | **success** — 67 modules, 0 errors |
| `python -m py_compile main.py foundation/app.py foundation/api/router.py tools/foundation_migrate_dryrun.py` | success |
| `python -m Northstar_backend.tools.foundation_migrate_dryrun --repo-root . --json` | success (read-only) |
| Local standalone foundation app (`uvicorn foundation.app:app`, spare port) + `curl` | success; stopped after |

### Safety preconditions confirmed before running
- Offline (no `requests`; the repo's `sitecustomize`/`network_guard` do not trigger because
  the foundation never uses `requests`).
- Temp SQLite DB per test — no production-like DB touched.
- No credential values; header-based dev context only.
- No provider adapter performs I/O (fixture only).

## Test breakdown (74)

| Module | Tests | Covers |
|---|---|---|
| `test_identity.py` | 9 | normalization, new/existing/conflict/duplicate/pack-review/no-ASIN |
| `test_permissions.py` | 10 | role matrix, sandbox guard, preview non-elevation, write blocking |
| `test_provenance.py` | 5 | null-first, envelope, staleness, non-current classes |
| `test_usage_shadow.py` | 6 | local-free, shadow charge, derived balance, idempotency, reversal |
| `test_jobs.py` | 8 | idempotency, state machine, illegal transition, retry→dead-letter, ceiling, execution, cancel |
| `test_approvals.py` | 7 | request, idempotency, approver authz, grant, no-execution, cancel, double-decide |
| `test_audit.py` | 3 | record, redaction, no-plaintext-secret |
| `test_repositories.py` | 8 | CRUD, UI-pref roundtrip, fixture adapter, provider guard, write refusal, redact, logger |
| `test_api_contracts.py` | 18 | me/roles/environment/orgs/marketplaces/identity/observations/preview/jobs/usage/approvals/audit/ui-prefs/error-envelope |

## Not run / withheld

| Suite | Reason |
|---|---|
| Full backend `pytest` (`Northstar_backend/test_*.py`, 2,368 funcs) | Broad suite; not required for changed modules this phase; withheld pending owner approval (per test authorization) |
| `.cjs` contract suites | Unaffected by foundation additions; withheld |
| Provider/sandbox live suites | Require provider access — out of scope |
| `tools/test_chrome.py` | Contains hardcoded credentials + external network — withheld (see `13`) |

No failing test was modified to pass. Where a foundation test failed initially, the
**production logic was corrected** (repository `add()` returning the persisted row;
`effective_policy()` parsing JSON columns; reversal accounting model) and the test
expectations were aligned to the corrected, documented semantics.