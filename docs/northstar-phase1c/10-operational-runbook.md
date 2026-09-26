# 10 — Operational Runbook (Foundation, Phase 1C)

## Environments

`ENVIRONMENT ∈ {development, test, staging, production}`. Staging/production require
`NORTHSTAR_JWT_SECRET` (non-dev), `NORTHSTAR_JWT_ISSUER`, `NORTHSTAR_JWT_AUDIENCE`, and a
non-empty `NORTHSTAR_JWT_ALGORITHMS` allowlist. Startup fails closed otherwise.

## Storage backends

- **Default (development):** SQLite (`foundation/db.py`), disposable temp DB.
- **PostgreSQL:** set `FOUNDATION_DB_URL` → `foundation/db_postgres.py` is used. Validated
  against PostgreSQL 15.19 (ephemeral) in 1C-02R.

## Initial owner provisioning

```
python -m foundation.bootstrap --org-name "<name>" --email "<owner@example>" [--recover]
```
CLI-only, idempotent, audited; no secrets on the command line.

## Migrations

- File: `Northstar_backend/migrations_foundation/001_foundation.sql` (generated from
  `foundation/db.py:SCHEMA`; regenerate with `python -m Northstar_backend.tools.foundation_generate_sql`).
- Apply (PostgreSQL): `psql -v ON_ERROR_STOP=1 -1 -U <user> -d <db> -f 001_foundation.sql`.
- Reapply is a safe no-op (`CREATE TABLE IF NOT EXISTS`).
- Preflight guardrails: `foundation.migrate.assert_staging_identity` (env==staging +
  `NORTHSTAR_ALLOW_STAGING_MIGRATION=1` + production denylist + redaction).

## Health checks

- Table count `== 25`; PK/UNIQUE constraint count `== 30`; column rows `== 234`.
- Fingerprints: columns `64d08db3…`, constraints `a1596ce1…`, indexes `8b3d4ecd…`.

## Job/scheduler

Not implemented (1C-04 not started). No GET route may create jobs or trigger providers;
this invariant is enforced by the absence of such code paths and by auth on all routes.

## Provider posture

All live providers default-off. No provider was called in Phase 1C. OpenRouter routing
(constrained when implemented) must retain `provider.sort="price"` and
`provider.allow_fallbacks=true`; no `max_price` until per-model thresholds are configured.

## Incident basics

- Auth failures are fail-closed (401/403); no fallback to header or claim trust.
- Session revocation is immediate (foundation session store).
- Migration failure: stop, capture, do not patch the DB manually; fix the SCHEMA generator
  and regenerate apply+rollback together.