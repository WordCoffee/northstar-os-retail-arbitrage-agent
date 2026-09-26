# 02 — PostgreSQL Staging Application (1C-02 / 1C-02R)

**Status:** 1C-02B **PASSED (ephemeral)** · 1C-02C/D/E **NOT STARTED** (staging).
Evidence state: **RUNTIME_CONFIRMED_EPHEMERAL**.

## Summary

The foundation migration was applied, rolled back, reapplied, and clean-room re-applied
on a **disposable local PostgreSQL 15.19** instance, following RA1 authorization. Staging
was **not** contacted; production was **not** contacted; no production data was used.

## PostgreSQL instance

| Item | Value |
|---|---|
| Image | `docker.io/library/postgres:15` (official; Supabase image is 3rd-party → not used) |
| Digest | `sha256:dfbbb0ad8cab91d41e99123664e37a9b25d0413426d4fb3154e4d668e5d35246` |
| Server | PostgreSQL 15.19 (Debian), `server_version_num` 150019 |
| Rationale | `docker-compose.yml:81` pins `supabase/postgres:15.1.1.78` → documented major **15** |
| Driver | psycopg 3.2.13 (installed in `venv-phase1c02`, system-site-packages) |
| Bind | `127.0.0.1:55432` (loopback only) |
| DB/User | `northstar_phase1c02_ephemeral` / `northstar_phase1c02_test` (disposable) |

## Applied migration

- File: `Northstar_backend/migrations_foundation/001_foundation.sql`
- Apply checksum: `20562cac6223dee6d242aafeb4b00b89ce09d2a1ad826dd57ed878f7c76b5500`
- Rollback checksum: `0fcbba99d8b2e949c0314723dac395232740319b4c13c9864f68f9a26526181a`
- Injection: none — schema is generated from `foundation/db.py:SCHEMA`; drift check `in_sync: true`.

## Stage results

| Stage | Result |
|---|---|
| A — empty baseline | PASS (0 tables; plpgsql; Etc/UTC; read committed) |
| B — first apply | PASS (exit 0, 320 ms, 25 tables) |
| C — schema validation | PASS (25 tables, 234 column rows, 30 PK/UNIQUE constraints) |
| D — PG semantics | PASS (JSONB, BOOLEAN, TIMESTAMPTZ, NUMERIC, constraints, savepoint, advisory lock) |
| E — repository tests (PG) | PASS (13/13 in `test_postgres_integration.py`; dialect asserted = PostgreSQL) |
| F — reapply (no rollback) | PASS (safe no-op) |
| G — rollback | PASS (25 drops; 0 tables) |
| H — reapply after rollback | PASS (fingerprint match) |
| I — clean-room | PASS (fingerprint match; smoke 13/13) |

## Schema fingerprints (db-side, deterministic)

- columns `64d08db3ff66fb9af246a674aa99e6f5`
- constraints `a1596ce1a63ef6261ff1cbaec3b8e13b` (30)
- indexes `8b3d4ecd2a67ab8a61873883198bfc8b`
- clean-room apply **==** reapply after rollback (all three match).

## SQLite vs PostgreSQL (behaviour differences)

See `postgres-behavior-differences.md`. Runtime-confirmed on PG: JSONB (nested/array/
unicode), BOOLEAN (t/f/NULL), TIMESTAMPTZ (offset→UTC), NUMERIC exactness + overflow
rejection, UNIQUE/NOT NULL violations, transaction+savepoint, advisory lock. The
repository layer normalizes JSONB→JSON-string and TIMESTAMPTZ→ISO so repositories observe
SQLite-equivalent Python types.

## Repository-on-PostgreSQL (Stage E scope note)

The foundation store is SQLite by default; a PostgreSQL backend
(`foundation/db_postgres.py`) was added additively and selected via `FOUNDATION_DB_URL`.
Stage E ran a **focused** repository + authentication integration suite (13 tests) against
PG. The **full 172-test suite was NOT run on PostgreSQL** — it is SQLite-oriented; this is
reported honestly, not hidden.

## Staging (NOT executed)

Staging backup/identity (1C-02C), staging migration (1C-02D), and staging rollback (1C-02E)
are **NOT STARTED**. See `postgres-staging-readiness.json` for the prepared plan and the
exact owner authorization required.

## Environment blocker resolution

The earlier block (`BLOCKED_NO_POSTGRES`) is resolved for the **ephemeral** sub-gate via a
disposable Docker PostgreSQL instance. Staging remains unverified.