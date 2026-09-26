# 07 — Cross-Phase Validation (Phase 1C, as at 1C-02R)

Evidence states: RUNTIME_CONFIRMED_EPHEMERAL / STATICALLY_CONFIRMED / UNVERIFIED_STAGING.

## SQLite (offline) validation

- Command: `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider`
- Result: **172 passed, 13 skipped, 0 failed** (the 13 skipped are the PG integration
  suite, skipped when `FOUNDATION_DB_URL` is unset).

## PostgreSQL (ephemeral) validation

- Command: `FOUNDATION_DB_URL=postgresql://northstar_phase1c02_test:***@127.0.0.1:55432/northstar_phase1c02_ephemeral pytest Northstar_backend/foundation/tests/test_postgres_integration.py -q -p no:cacheprovider`
- Result: **13 passed, 0 failed** (run at Stage E and again at Stage I clean-room).
- Covered: dialect = PostgreSQL (no SQLite fallback), server = PostgreSQL 15, disposable
  DB name, repositories round-trip, audit insert, UI preference, usage shadow, provider
  guard, JSONB observation round-trip, auth `/me` role resolution, cross-org denial,
  suspended membership denial, session revocation, owner bootstrap.

## Migration lifecycle validation (PG)

| Check | Result |
|---|---|
| apply | PASS |
| reapply (no rollback) | PASS (safe no-op) |
| rollback | PASS (0 tables after) |
| reapply after rollback | PASS (fingerprint match) |
| clean-room apply | PASS (fingerprint match) |
| schema fingerprint (columns/constraints/indexes) | identical across clean-room apply and reapply |

## Not validated (honest)

- **Staging compatibility: UNVERIFIED_STAGING** — no staging contact.
- **Production compatibility: UNVERIFIED_PRODUCTION.**
- **Full foundation suite on PostgreSQL: NOT RUN** (SQLite-oriented); only the focused PG
  integration subset ran on PostgreSQL.
- **Concurrency races** (true parallel duplicate-membership inserts): partially covered
  (UNIQUE constraint + advisory lock); not stress-tested.
- **Decimal/NUMERIC in the foundation store**: P0 has no money columns; NUMERIC semantics
  were proven separately (Stage D) and money lands in 1C-03.

## Gate state

1C-01F PASSED · 1C-02A PASSED · 1C-02B PASSED (ephemeral) · 1C-02C/D/E NOT STARTED ·
1C-03..1C-06 NOT STARTED.