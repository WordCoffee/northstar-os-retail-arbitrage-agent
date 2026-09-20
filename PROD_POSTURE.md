# PROD POSTURE — Phase F/S6

**Date:** 2026-09-20 · **Scope:** guarantee the edge rate-limiter is never
disabled in production.

## Rule

- `NORTHSTAR_DISABLE_RATE_LIMIT=1` is a **harness-only** opt-out: the shared
  pytest process counts every TestClient call against one client id and would
  trip the anonymous 30/min edge limit.
- **It must never be set when `ENVIRONMENT=production`.**

## Enforcement (in code)

- `rate_limiter.prod_posture_ok()` → `False` only when
  `ENVIRONMENT=production` AND the disable flag is `1`.
- `rate_limiter.assert_prod_posture()` → raises `RuntimeError` on violation.
- Called at **app startup** (`main.lifespan`), so a mis-configured production
  process refuses to boot rather than silently running without the edge
  limiter.

## Operator notes

- Set `ENVIRONMENT=production` in the production runtime (CF Pages/dashboard /
  container) exactly once; never also set `NORTHSTAR_DISABLE_RATE_LIMIT`.
- The harness runner (`scripts/run_all_tests.ps1`) sets the disable flag for
  local/test runs only — it must never run inside the production environment.

## Tests

`Northstar_backend/test_rate_limit_posture.py` covers: ok when flag unset,
ok when flag set but env != production, violation raises when env=production +
flag set, and the bool helper.