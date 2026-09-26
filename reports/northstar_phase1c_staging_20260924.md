# Staging Provisioning & Smoke — Evidence Report for Tyrone (owner)

**Date:** 2026-09-24
**Authorization:** Staging provisioning authorization (Tyrone, sole operator /
sole rollback / sole approval authority).

## Step 1 — Verify no staging PostgreSQL exists (read-only, no assumption)

Command: `docker ps -a` + env-var NAME check + readiness-record check.
Result: only the stopped disposable ephemeral container
(`northstar-phase1c04-ephemeral | postgres:15 | Exited`); no staging-named
container; no staging/db-related environment variable names; prior readiness
record `postgres-staging-readiness.json` documented `do_not_execute` /
`not_executed`. **Conclusion: NO_STAGING_INSTANCE_EXISTS** (RUNTIME_CONFIRMED).

## Step 2 — Provision staging PostgreSQL

**Choice:** local Docker-based staging box (`postgres:15`) on loopback,
consistent with the repository convention (Docker-based disposable PostgreSQL
throughout) and budget-conscious (cost **$0**; existing Docker engine).
**Rationale:** single-operator + ~50-user staging needs one Postgres instance;
a managed instance adds cost/accounts with no benefit at this stage. The
upgrade path to a small managed Postgres is a **connection-string change** —
no rebuild — so crossing the ~50-subscriber threshold requires only capacity,
exactly per the service-tier requirement.

| Item | Value |
|---|---|
| Container | `northstar-staging` (named volume `northstar-staging-data`) |
| Host / port | `127.0.0.1:55433` (loopback only) |
| Database / user | `northstar_staging` / `northstar_staging_owner` |
| Version | PostgreSQL 15.19 (Debian) |
| Cost | $0 (local Docker) |

## Step 3 — Secret management

**Choice:** local encrypted AES-256-GCM vault (`Northstar_backend/foundation/secrets.py`),
master key held in an OS-permissioned file **outside the repository**
(`%LOCALAPPDATA%\northstar\secrets.masterkey`). The staging DB password is
generated at provisioning and stored **only** in the vault (name
`staging_db_password`); it is never echoed, never logged, never committed.
Git status shows no vault/key files; the vault + key are outside the repo
(verified). The `get_secret`/`set_secret` interface is stable so the backend
can later be swapped for a hosted secret manager (Vault/cloud KMS) without a
breaking migration.

## Step 4 — Preflight, backup, migration (rollback prepared, NOT executed)

| Step | Command (conceptual) | Result |
|---|---|---|
| Preflight | `migrate.preflight(environment=staging, host, db, allow_flag)` | identity + production-denylist + checksum validated offline |
| Backup | `pg_dump -d northstar_staging` → `Northstar_backend/data/staging/staging-pre-migration-20260925T124526Z.sql` (695 bytes) | verified non-empty + pg_restore parse |
| Apply 001 | `001_foundation.sql` | ok (313 ms) |
| Apply 002 | `002_jobs_durable.sql` | ok (15 ms) |
| Apply 003 | `003_keyword_intel.sql` | ok (18 ms) |
| Post-apply | schema fingerprint | **41 tables / 424 columns** (hash `84725eb8…`) |

The backup step was **not skipped** (owner requirement). Rollback scripts
(`002_rollback_jobs_durable.sql`, `003_rollback_keyword_intel.sql`) are
prepared and validated on the disposable instance, but **were NOT executed**.
Per the rollback-authority clause, no rollback will be run autonomously; if a
rollback ever appears necessary, I will stop and wait for your explicit
real-time confirmation.

## Step 5 — Staging smoke suite (F03 plan)

Command: `python -m Northstar_backend.tools.staging_smoke`
Result: **26/26 PASS** → `docs/northstar-phase1c/staging-smoke-report.json`.

Coverage: auth posture, environment, missing/valid JWT, org resolution,
cross-org denial, session revocation, preview + audit, canonical economics
(contract version + incomplete-on-missing-cost), fake job success, transient
retry, scheduler dedup, keyword import + idempotent reimport + rejected rows,
keyword search, search-term performance, frontend served + deep links,
security headers, GET-creates-no-jobs, no-provider-on-load, audit, usage
settlement.

One product defect was found and fixed during smoke: PostgreSQL boolean-column
rejection of raw `=0`/`=1` SQL in `preview_end` and `schedule archive`
(bound booleans now; SQLite suite re-verified 574 passed / 28 skipped).

## Redacted connection details (for your records)

- Staging URL shape: `postgresql://northstar_staging_owner:*****@127.0.0.1:55433/northstar_staging`
  (password in the encrypted vault, never printed).

## Cost

$0 (local Docker). No managed infrastructure provisioned.

## Data written to staging by smoke

One smoke organization ("Staging Smoke"), the owner membership, test jobs/
schedules/keywords/imports/audit/usage events. These are expected smoke data
for validation; nothing production-like.

## Status & next actions

- Staging: **APPLIED_AND_SMOKED** (26/26).
- Not executed / out of scope: rollback (yours), production provisioning,
  subscriber provisioning, public exposure.
- Ready for your real-time observation: the staging box is running on loopback
  `127.0.0.1:55433`; I will leave it running for your inspection and stop it on
  your instruction.

**No staging write is considered "complete" until you acknowledge this report.**