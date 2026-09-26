# 03 — Database and Migrations

## 1. Storage model (Phase 1B)

| Layer | Choice | Notes |
|---|---|---|
| Foundation store | **stdlib `sqlite3`** | dependency-light; temp DB by default; tests use disposable temp files |
| Target production DB | PostgreSQL | DDL generated in `migrations_foundation/001_foundation.sql` |
| Cache/queue target | Redis | Phase 1C (jobs runner) |
| Legacy store | existing `northstar.db` | **read-only use only**; never written by foundation |

## 2. Foundation tables (additive)

24 tables, all `CREATE TABLE IF NOT EXISTS`:
`organizations, users, memberships, marketplaces, catalog_products,
product_identifiers, pack_configs, variation_relationships, product_aliases,
unresolved_candidates, identity_conflicts, observations, providers, job_requests,
job_runs, usage_events, pricing_policies, audit_events, approval_requests,
approval_decisions, preview_sessions, suppliers, supplier_documentation,
ui_preferences`.

Schema source of truth: `foundation/db.py:SQLITE_DDL`. Postgres translation:
`foundation/db.py:postgres_ddl()`.

## 3. Migration files

| File | Target | Status |
|---|---|---|
| `migrations_foundation/001_foundation.sql` | PostgreSQL | **CREATED, NOT APPLIED** |

Header explicitly states "ADDITIVE ONLY. NOT APPLIED." Generated from the same source
as the SQLite DDL to prevent drift.

## 4. Migrations applied

**NONE.** No `psql`, no Supabase apply, no destructive migration logic was executed.
The existing `migrations/001..003` remain unapplied. The production-like `northstar.db`
was not modified by this phase.

## 5. Isolation guarantees

- `FoundationState.build()` defaults to a **disposable temp SQLite file**; it never
  infers a path from `northstar.db`.
- Tests create and delete a temp DB per test (`foundation/tests/conftest.py`).
- `foundation_migrate_dryrun.py` opens `northstar.db` with `mode=ro` (read-only URI) and
  reports `writes_performed: 0`.

## 6. Note on the production-like DB timestamp

The `northstar.db` shown as "modified" in git predates this phase (prior-session runtime
cache writes). **Phase 1B performed zero write operations against it.** Per the owner
directive, a file timestamp alone is not treated as proof that no process touched the
DB; instead, the guarantee here is the read-only connection mode used by the only tool
that opens it (`mode=ro`), plus the absence of any foundation code path that writes to
that path.