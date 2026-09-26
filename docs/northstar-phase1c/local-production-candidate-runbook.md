# Local Production Candidate — Operational Runbook (1C-LC / Workstream E)

**Classification: LOCAL_PRODUCTION_CANDIDATE** — RUNTIME_CONFIRMED (SQLite 574
passed / 28 skipped; disposable PostgreSQL 28 passed; migration harness 9/9;
live loopback stack exercised in a real browser).

## What this is

A loopback-only integration of: PostgreSQL 15 (disposable), production-mode
authentication (temporary local signing material, local issuer/audience), a
real local organization + owner membership, the FastAPI backend, the durable
worker, the persisted scheduler, the canonical React/Vite build (served at
`/ui`), and fake/local handlers. No external provider is contacted.

## Startup

```bash
# 1. Disposable PostgreSQL (loopback only)
docker run -d --name northstar-phase1c04-ephemeral \
  -e POSTGRES_USER=northstar_phase1c02_test \
  -e POSTGRES_PASSWORD=<disposable> \
  -e POSTGRES_DB=northstar_phase1c02_ephemeral \
  -p 127.0.0.1:55432:5432 postgres:15

# 2. Set FOUNDATION_DB_URL (disposable credentials only)
export FOUNDATION_DB_URL=postgresql://northstar_phase1c02_test:<disposable>@127.0.0.1:55432/northstar_phase1c02_ephemeral

# 3. Migrate (optional for a fresh container; migrations validate cleanly)
python -m Northstar_backend.tools.foundation_pg_validate_durable

# 4. Start the stack (generates temp signing material, bootstraps the owner,
#    issues a local token, starts backend + worker + scheduler)
python -m Northstar_backend.tools.local_production_stack start --port 8001

# 5. Open http://127.0.0.1:8001/ui  (loopback only)
```

## Shutdown

```bash
python -m Northstar_backend.tools.local_production_stack stop
```

Temporary JWT secret and token file are removed on shutdown. The disposable PG
may be stopped with `docker stop northstar-phase1c04-ephemeral` (data is
disposable; never point this stack at staging/production).

## Migration & rollback

- Migrations: `001_foundation.sql` (canonical full schema), `002_jobs_durable.sql`,
  `003_keyword_intel.sql` (additive deltas), each with compensating rollback.
- Validation: `foundation_pg_validate_durable` applies / inspects / rolls back /
  reapplies / fingerprints / clean-room checks (9/9).
- Rollback: apply the rollback files in reverse order (`003` then `002`) in a
  controlled step; backups first. See `11-rollback-runbook.md`.

## Worker

- Org-scoped; atomically claims queued runs (`FOR UPDATE SKIP LOCKED` on PG).
- Re-runs every runtime recheck before executing; executes ONLY registered
  fake/local handlers; heartbeats; settles usage; audits.
- Inspect: `GET /api/v1/foundation/jobs-durable/queue-posture`.

## Scheduler

- Enqueue-only; never executes jobs or calls providers.
- Occurrence idempotency prevents duplicate enqueues across instances.
- Inspect: `GET /api/v1/foundation/schedules/posture`.

## Queue inspection / dead letter / session revocation / preview audit

- Queue: `jobs-durable` list + `queue-posture`.
- Dead letter: `jobs-durable?state=dead_letter`; retry via
  `POST /jobs-durable/{id}/retry` (operator; new-run linkage).
- Session revocation: `POST /session/revoke?jti=...` (admin).
- Preview audit: `audit?limit=...` filtered on `preview.start` / `preview.end`.

## Imports

- Dry run: `POST /keywords/imports/dry-run` (no writes).
- Submit: `POST /keywords/imports` (creates a `keyword_import` job executed by
  the worker). Rejected rows preserved; reimports idempotent; overlaps flagged.

## Health routes

- `/api/v1/foundation/environment`, `/auth-posture`, `/jobs-durable/queue-posture`,
  `/schedules/posture`, `/ui` (canonical UI).

## Incident indicators

- Idle-in-transaction connections on PostgreSQL block DDL — terminate them
  (`pg_terminate_backend`) and fix the leaking path (seed() commits; reads
  roll back on error).
- Dead-letter growth → review failures via job detail + audit timeline.
- Usage anomalies → `org_balances` counters vs `usage_events` settlement.
- Auth failures → 401/403 codes in `/audit`.

## Security / accessibility / performance notes

- Security matrix (E06) and accessibility baseline (D12) pass; dynamic a11y
  scan and dependency audit run in the local stack.
- Performance smoke (E08): 40-job drain < 30 s, keyword list < 1 s (SQLite
  local; not a capacity claim).
- The built shell references Google Fonts (external CDN) — CSP scoped to
  fonts.googleapis.com / fonts.gstatic.com; loopback otherwise makes zero
  network calls.

## Test totals (this run)

| Suite | Result |
|---|---|
| Foundation (SQLite) | 574 passed, 28 skipped |
| PostgreSQL integration | 28 passed |
| Migration harness | 9/9 PASS |
| e2e matrix | 37 passed |
| Frontend gates | 30 passed |
| Local production (security/perf) | 13 passed |