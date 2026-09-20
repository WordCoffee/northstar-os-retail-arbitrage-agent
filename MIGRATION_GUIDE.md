# Migration Guide — Postgres (Phase F/S9)

**Status:** PREPARED — **NOT APPLIED.** No Postgres/Supabase instance is
connected; local development/tests continue on the SQLite fallback
(`Northstar_backend/data/northstar.db`). Applying these migrations anywhere is
a **live/deploy action** requiring operator approval.

## Files

| Migration | Mirrors |
|---|---|
| `migrations/001_core_auth.sql` | `auth.py` `users` (incl. `role`) + `sessions` |
| `migrations/002_productivity.sql` | `invites.py`, `support.py`, `credit_ledger.py` entry schema |
| `migrations/003_golden_goose.sql` | `ops/schema.sql` (PG port) + `scan_runs` provenance |

## How to apply (operator, when approved)

```bash
# Option A: local PostgreSQL
psql "$DATABASE_URL" -f migrations/001_core_auth.sql
psql "$DATABASE_URL" -f migrations/002_productivity.sql
psql "$DATABASE_URL" -f migrations/003_golden_goose.sql

# Option B: Supabase (free tier)
# Open the SQL editor and paste each file in order (001 -> 002 -> 003).
```

After applying, point the backend at Postgres by setting **`DATABASE_URL`** (or
`SUPABASE_DB_URL`) in the runtime environment — `data_layer` auto-selects
Postgres over SQLite when the URL is present. Apply migrations once, in order;
each file is idempotent (`IF NOT EXISTS`).

## Rules

- Apply to **staging first**, verify, then production.
- Never apply while the SQLite fallback is the running data source for both
  environments (avoid split-brain writes).
- `scan_runs.report_path` is an **internal** field — ensure API responses still
  strip it (no-leak, B1 §6); the row is for operator/ops tooling only.
- Tests keep running on SQLite (see `data_layer._get_postgres_url` TODO).

## Not included

Stripe/billing schema, OAuth provider tables, and the full blueprint §2 data
model (keywords/campaigns/social) are deferred to the hosted-release phase
(HANDOFF.md F24).