# 19 — Required Amendments Before Phase 1C (owner-issued)

**Date:** 2026-09-23
**Status:** All three amendments addressed. R1 escalated to blocking and enforced in code.

---

## Amendment 1 — R1 (auth shim) escalated to BLOCKING, NON-NEGOTIABLE

The risk register entry R1 is changed from `high` to **`blocking`** (see
`phase1b-risk-register.json` → `1B-R1`, `severity: "blocking"`).

### Written confirmation

**(a) The shim is rejected outside localhost *by default* — enforced, not conventional.**

Enforced in code at `Northstar_backend/foundation/api/deps.py:enforce_local_only()`:

- It runs as the **first statement** of `get_context`, before any header is read or any
  context is built.
- Allowed client hosts: `127.0.0.1`, `::1`, `localhost`, and `testclient`
  (the in-process FastAPI TestClient harness host).
- Any other host → **HTTP 401 `auth_required_remote_blocked`**.
- A missing client (`request.client is None`) is treated as blocked.
- An explicit override `NS_FOUNDATION_ALLOW_REMOTE_DEV=1` permits remote dev access but
  logs a loud warning and does **not** enable real auth. It is documented as
  operator-only and must not be used in production.

**(b) No frontend route, API response, or preview-mode banner is reachable from
non-localhost until real JWT/org resolution replaces the shim.**

- Every foundation endpoint depends on `get_context` (which calls the guard) —
  including `/me`, `/environment`, `/roles`, `/preview/*`, `/usage/*`, `/approvals`,
  `/audit`, `/ui/preferences/*`. There is no unguarded data route.
- `/auth-posture` calls the guard directly.
- The preview-mode banner is driven by `GET /preview/active`, which is guarded; so a
  remote client cannot reach preview-mode state.
- The frontend shell calls only these paths; from a non-localhost origin every such call
  returns 401, so no shell data, no preview banner, and no context can render remotely.

**(c) The blocker sits at the TOP of Phase 1C, alone.**

Phase 1C entry order (below) makes real-auth replacement **1C-01, first and alone**.

### Enforcement evidence

- `Northstar_backend/foundation/tests/test_auth_guard.py` — 12 tests: loopback hosts
  allowed; `10.0.0.5`, `203.0.113.9`, `8.8.8.8`, `example.com` blocked with 401;
  override behavior; `client=None` blocked; `/environment` and `/auth-posture` report
  the posture.
- `GET /api/v1/foundation/auth-posture` returns `real_authentication_active: false`,
  `reachable_from: "localhost only"`, `remote_blocked_by_default: true`.

---

## Amendment 2 — R13/R14 (formula duplication) resolved BEFORE canonical economics

A full inventory now exists: **`18-formula-inventory.md`** (+ `formula-inventory.json`).

- It lists **every** fee/ROI/profit/margin/ACoS site across `fee_engine`, `fee_calculator`,
  `pricing`, `finance`, `unit_economics`, `enricher`, `product_analysis`, `scanner_data`,
  `ad_pilot`, `word_coffee`, Golden Goose `breakdown_economics`/`opportunity_scorer`, and
  the frontend `Auctioneer.jsx`, `Golden Goose.jsx`, `Prospector.jsx`.
- It records the confirmed conflicts (two margin definitions; three ACoS implementations;
  hardcoded 0.15 referral + tier FBA in the frontend).
- The canonical module (1C-04) is now explicitly gated on this inventory and must
  **reduce** the number of formula sources to one each, with regression tests.

**No formula was changed in Phase 1B** (owner rule preserved).

---

## Amendment 3 — SQLite-vs-Postgres divergence cannot mask silent differences

### Written confirmation

**(a) No SQLite-only behavior is relied upon.**

`foundation/db.py` now has a **single schema specification** (`SCHEMA`) from which
**both** the SQLite DDL and the PostgreSQL DDL are generated. Divergence is a
construction error, not a runtime surprise. Additionally:

- **JSON**: all JSON columns are written/read via explicit `json.dumps`/`json.loads`
  in the repository layer (`_ser`, `UiPreferenceRepo.set_pref`). Behavior is identical on
  SQLite `TEXT` and Postgres `JSONB`; no implicit coercion is used.
- **Booleans**: serialized explicitly (0/1 on SQLite, native `BOOLEAN` on Postgres);
  no truthiness reliance on integer coercion.
- **Timestamps**: stored as ISO-8601 `TEXT` on SQLite, `TIMESTAMPTZ` on Postgres;
  freshness/staleness is **computed in Python**, not in SQL, so comparisons are
  backend-independent.
- **Constraints**: `PRIMARY KEY` and `UNIQUE` (idempotency keys, marketplace code,
  provider key) are generated for both backends. Idempotency is additionally enforced in
  Python (repository checks) rather than relying on a database error.

**(b) The migration DDL was validated for schema-equivalence, not just "it parses".**

`foundation/db.py:schema_equivalence_report()` and `validate_sqlite_schema()`:

- Create an in-memory SQLite DB, apply the generated DDL, and compare the **actual**
  column set per table (`PRAGMA table_info`) to `SCHEMA` — 24 tables, all match.
- Verify the generated Postgres DDL text contains every table and column.
- Report `equivalent: true`, `postgres_missing_items: []`.

Verified output (run this phase):
```
{"sqlite_validated": true, "postgres_ddl_generated": true,
 "postgres_missing_items": [], "equivalent": true}
```

Tests: `foundation/tests/test_db_schema.py` (6 tests).

---

## Recommended Phase 1C entry order (adopted — blockers first, strict sequence)

| Order | Item | Dependency | Notes |
|---|---|---|---|
| **1C-01 (blocker, alone)** | Replace dev shim with real JWT/org resolution | — | Hard prerequisite. Nothing else starts until this is done and tested. |
| 1C-02 | Staging Postgres apply + rollback plan | 1C-01 | Apply `001_foundation.sql` to staging only; drill rollback. |
| 1C-03 | Canonical economics module | 1C-02, `18-formula-inventory.md` | Informed by the inventory; reduce formula sources to one each; regression tests. |
| 1C-04 | Job worker/scheduler | 1C-02 | Fixture/local execution loop; no external providers. |
| 1C-05 | Keyword module (provider-neutral) | 1C-02 | Fixture adapter + contract tests; no paid provider. |
| 1C-06 | Frontend serving + real-auth wiring | 1C-01 | Single canonical surface. |

**Rule:** 1C-02 must not be bundled with 1C-01 as a parallel task. 1C-03 must not begin
until the inventory is accepted and 1C-02 has a rollback path.