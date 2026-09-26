# Staging Handoff Checklist (1C-LC / Workstream F)

**Classification: STAGING_READY** — documentation reached. NOT
`STAGING_VALIDATED`, NOT `PRODUCTION_READY`, NOT `PRODUCTION_DEPLOYED`, NOT
`GO_LIVE_APPROVED`. No staging system was contacted.

## F01 — Migration package

Machine-readable package: `docs/northstar-phase1c/staging-migration-package.json`.

- Ordered migrations: `001_foundation.sql` → `002_jobs_durable.sql` →
  `003_keyword_intel.sql` (additive, reapply-safe, SHA-256 checksums embedded).
- Rollback (compensating, reverse order): `003_rollback_keyword_intel.sql` →
  `002_rollback_jobs_durable.sql`.
- PostgreSQL ≥ 15 (verified on 15.19); no extensions required.
- Lock risks: index/constraint DDL takes ACCESS EXCLUSIVE on the target table —
  run in a maintenance window or under low write load.
- Abort conditions: identity validation failure, checksum mismatch, unverified
  backup, denylisted identifier.
- Staging-identity validation: `migrate.assert_staging_identity` refuses unless
  `environment=staging`, the explicit allow flag is set, and no
  prod/production/live/primary token appears in host/db.
- Production denylist: `prod, production, live, primary`.

## F02 — Backup and rollback

- **Backup requirement:** full `pg_dump` (or equivalent point-in-time-capable
  backup) of the staging database immediately before the first migration.
- **Backup verification:** restore the backup into a scratch database and run a
  row-count / schema sanity check BEFORE applying migrations.
- **Restore-test requirement:** the backup must restore successfully before any
  migration step.
- **Rollback commands:** apply `003_rollback_keyword_intel.sql` then
  `002_rollback_jobs_durable.sql` in a single transaction each, in a controlled
  step.
- **Data-preservation warnings:** rollback DROPS foundation tables and destroys
  data written by the new system; legacy tables are never touched. Backup first.
- **Reapply procedure:** after rollback, re-apply `002` then `003` (idempotent);
  verify fingerprints match `staging-migration-package.json`.
- **Escalation triggers:** any failed statement, any unexpected data change, or
  any abort condition → stop, restore the verified backup, escalate.

## F03 — Staging smoke plan

After the migrations are applied to staging (separate authorization required):

1. Startup posture — backend/worker/scheduler start; `/ui` serves; auth-posture
   reports JWT-active.
2. Authentication — valid JWT succeeds; missing/wrong-issuer/wrong-audience/
   revoked/suspended all fail closed.
3. Organization resolution — server-side memberships; cross-org denied.
4. Revocation — a revoked session is rejected.
5. Preview — banner appears; entry/exit audited.
6. Economics — `/economics/contract` reports `economics-1.0.0`; missing
   cost/fees/pack ambiguity remain incomplete; scanner includes formula version.
7. Job submission → worker → success; transient retries; permanent dead-letters.
8. Scheduler — enqueues once per occurrence; no duplicates.
9. Keyword import — job-driven import; reimport idempotent; rejected rows kept.
10. Frontend — deep links; route refresh; 401/403/404/500 states.
11. Accessibility smoke — keyboard flow on Hub/Jobs/Keywords; visible focus.
12. Security smoke — CSP headers; no bundle secrets; GET creates no jobs.
13. Audit — consequential actions present.
14. Usage — reservations settle; no double debit.
15. No-provider-on-load — page loads make zero provider calls.

## F04 — Secret delivery (variable NAMES only; values never documented here)

| Variable | Required | Consuming component | Rotation |
|---|---|---|---|
| `FOUNDATION_DB_URL` | required | backend | rotate with DB credentials |
| `NORTHSTAR_JWT_SECRET` | required | backend (auth) | rotate on compromise |
| `NORTHSTAR_JWT_ISSUER` | required | backend (auth) | rare |
| `NORTHSTAR_JWT_AUDIENCE` | required | backend (auth) | rare |
| `NORTHSTAR_JWT_ALGORITHMS` | required | backend (auth) | rare |
| `NORTHSTAR_JWT_KEY_ID` | optional | backend (auth) | rare |
| `NORTHSTAR_ALLOW_STAGING_MIGRATION` | migration-time | migrate guard | per migration |

Secret-manager expectations: inject at process start; never in logs; redaction
rules per `docs/northstar-phase1c/01-auth-final-hardening.md`. No secret values
are included in any Phase 1C artifact.

## F05 — Monitoring and incident plan

Signals to monitor: authentication failures, authorization failures, proxy
anomalies, queue depth, job age, worker heartbeat, scheduler heartbeat, retries,
dead letters, lease expirations, usage anomalies, budget blocks, provider
blocks, import failures, frontend failures, database health.

Incident thresholds (proposed; owner-tunable): queue depth sustained > N for
> M minutes; dead-letter growth without review; idle-in-transaction connections;
auth 401/403 spikes. Rollback triggers per F02; escalation: on-call owner +
staging operator, never auto-retry a failed live migration.

## F06 — STAGING_READY — requirements met

- [x] LOCAL_PRODUCTION_CANDIDATE passed (1C-03R/04/05/06, PG validation,
  backend suites, worker concurrency, keyword imports, React build, browser/e2e,
  security, accessibility baseline, restart recovery, no unresolved critical/high
  local-security issue, fake/local providers only).
- [x] Migration + checksum package exists (`staging-migration-package.json`).
- [x] Backup requirements exist (F02).
- [x] Abort and rollback conditions exist (F01/F02).
- [x] Staging smoke plan exists (F03).
- [x] Secret-delivery requirements exist (F04, names only).
- [x] Monitoring and incident plan exists (F05).
- [x] Required owner inputs are explicit (below).

## Required owner inputs (external boundary)

1. A designated staging PostgreSQL (host/database names, approved identity).
2. Staging credentials via the approved secret-delivery mechanism (never chat/docs).
3. Explicit backup authorization and a verified pre-migration backup.
4. Explicit migration authorization (allow flag + named checksum).
5. Confirmation of the smoke-plan owner and incident escalation path.

Until those are provided, the only remaining work is staging execution, which
is outside this phase's authorization.