# 1C-04 Financial-Integrity Vertical Slice — Mandatory Gate Report (owner-prioritized)

**Date:** 2026-09-24
**Owner priority:** build the 1C-04 vertical slice with financial integrity first.
**Acceptance gate:** idempotent submission + exactly-once settlement (PostgreSQL evidence).

## What was implemented

### 1. Idempotent submission (account + request type scope)
- The job-submission idempotency key is now unique at the database level scoped to
  **(organization_id, job_type, idempotency_key)** — migration
  `004_financial_integrity.sql` (`uq_job_requests_org_type_idem`). The same key
  with a DIFFERENT request type creates a NEW job (never a wrong replay).
- Submission is **race-safe**: `find`-then-insert is wrapped so a concurrent
  duplicate that loses the unique-index race is caught and the ORIGINAL
  job/result (with its runs and output reference) is returned — never a second
  payable execution, never a 500.

### 2. Exactly-once settlement (DB-level unique + transaction)
- Settlement now happens **only on success**. The ledger entry key
  `settle:{run_id}:{attempt}` is UNIQUE at the database level
  (`usage_events.idempotency_key`), and the whole settle is **one transaction**:
  org-balance release + ledger insert + reserved-event release commit or roll
  back together. A concurrent/second double-settlement attempt rolls back and
  returns the existing entry.
- **Failed, cancelled, blocked, and unknown-result jobs never settle.** They
  RELEASE their reservation (no debit, no ledger entry). Unknown-outcome
  recovery (lease expired while running / worker died after reserving) releases
  outstanding reservations without debiting; re-execution reserves fresh and
  settles once.
- Reservations use nonce-keyed events (`reserve:{run}:{attempt}:{nonce}`) so a
  re-executed attempt after a crash can never collide with the prior
  reservation's unique key.

### 3. Append-only audit correlation
- `audit_events` gains a `correlation_id` column (migration 004). Every
  transition writes an append-only record correlated by **request ID
  (correlation_id), job ID (resource_id), actor ID (actor_user_id), and
  timestamp (occurred_at)** — in addition to the existing `job_state_history`
  transition ledger.

## Required proofs (all executed, RUNTIME_CONFIRMED)

| Proof | Where | Result |
|---|---|---|
| Concurrent duplicate submissions (6 callers) → ONE job, all receive the original job/result | `test_financial_integrity_postgres.py::test_concurrent_duplicate_submission_single_job` | PASS (1 job, 1 run, 1 settlement) |
| Retry-after-timeout → exactly one ledger settlement | `test_financial_integrity.py::test_retry_after_timeout_single_settlement` + PG variant | PASS (1 finalized) |
| Double-settlement attempt → exactly one ledger entry | `test_financial_integrity.py::test_double_settlement_attempt_single_entry` + PG variant | PASS (1 finalized, no double debit) |
| Failed-handler → no settlement | `test_financial_integrity.py::test_failed_handler_never_settles` + PG variant | PASS (0 finalized, reservation released) |
| Staging smoke report linking request → job → execution → ledger → audit | `staging-smoke-report.json` item 27 (`financial_chain`) | PASS (see below) |

Additional financial-integrity coverage: cancelled-never-settles,
unknown-result-crash release + single re-settle, idempotent-replay returns the
original job with result, idempotency scoped per request type, audit-chain
correlation (every transition present + correlated).

## Staging evidence (PostgreSQL)

- Migration **004 applied to staging** with a **verified pre-migration backup**
  (`staging-pre-004-20260925T134217Z.sql`, 94,789 bytes; backup never skipped) →
  `staging-004-apply-report.json`. Post-apply: 41 tables / 425 columns; the
  idempotency unique + audit correlation_id verified present.
- Staging smoke: **27/27 PASS** → `staging-smoke-report.json`.
- **Financial chain (single request → audit):**
  - request: correlation_id `staging-req-chain-1`, idempotency_key `staging-fin-chain`
  - job: `ece8ac3a-1061-486c-a849-7574c872926d`
  - execution: `succeeded`
  - ledger: **exactly 1** finalized entry `settle:189021bf-e92f-456e-933d-577fb90e6ae2:1`
  - audit chain: 7 events, all correlated by `staging-req-chain-1`, job id,
    actor `818d3840…`, timestamps (job.submit, queued, leased, running,
    succeeded + idempotent-replay submits).

## Suite totals (all executed)

- Foundation SQLite: **582 passed / 32 skipped** (32 = PG-only modules).
- Disposable PostgreSQL (financial + durable + integration + concurrency): **32 passed**.
- Migration harness (001–004): **9/9 PASS** (apply/inspect/rollback/reapply/
  fingerprint/clean-room).
- e2e matrix + 1C-04 gate + financial gates: 52 passed.

## Safety confirmations

No live provider calls, no production access, no public exposure. Rollback of
004 was **NOT executed** — Tyrone is the sole rollback authority. The staging
box remains running on loopback `127.0.0.1:55433` for inspection.

## Files (financial-integrity work)

Added: `foundation/tests/test_financial_integrity.py`,
`test_financial_integrity_postgres.py`, `migrations_foundation/004_financial_integrity.sql`,
`004_rollback_financial_integrity.sql`, `tools/staging_apply_004.py`,
`reports/northstar_phase1c_financial_integrity_20260924.md`.
Modified: `foundation/{db.py, models.py, audit.py, db_postgres.py, jobs_durable.py,
jobs_handlers.py}`, `001_foundation.sql` (regenerated), migration harness,
`tools/staging_smoke.py`, `docs/northstar-phase1c/*` (evidence), `staging-migration-package.json`.