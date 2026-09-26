# 04 — Durable Worker & Scheduler (1C-04)

**Status:** ✅ **PASS** — RUNTIME_CONFIRMED (SQLite 419 passed / 28 skipped;
disposable PostgreSQL 28 passed; migration harness 9/9).

## Authoritative state machine — `foundation/jobs_state.py`

One machine, 15 canonical states:

`draft → pending_approval → queued → leased → running → {succeeded, failed,
retry_wait, cancel_requested, dead_letter, expired, blocked_budget,
blocked_provider, blocked_authorization, cancelled}`.

- Legal/illegal transitions, terminal (`succeeded`, `cancelled`, `dead_letter` —
  dead-letter also permits the authorized operator manual retry into a NEW run),
  retryable, cancellable, lease-required (`leased`, `running`), and blocked
  state sets.
- Approval-required transitions (`pending_approval → queued`).
- Per-transition required actors and required reasons.
- Immutable transition evidence (job_id, run_id, previous_state, new_state,
  actor, timestamp, reason, correlation_id, audit_event_ref).
- Illegal transitions raise structured `JobStateError` (unknown_state /
  illegal_transition / actor_not_allowed / reason_required / terminal_state).
- Tests: `foundation/tests/test_job_state_machine.py` → **99 passed**.

## Additive schema (B02/B03)

- `money` logical type (SQLite REAL ↔ PostgreSQL NUMERIC) for all monetary
  columns.
- `job_requests` + `job_runs` durable columns (job_type, payload JSONB,
  payload_schema_version, approval_id, provider_class, budget_class,
  estimated_cost, parent_job_id, correlation_id, provenance, state;
  lease_owner, lease_expiration, heartbeat_time, scheduled_time, reserved_cost,
  actual_cost, output_reference, error_code, error_summary, cancellation_state,
  …).
- New tables: `job_state_history`, `job_schedules`, `schedule_occurrences`,
  `org_balances`.
- Organization-scoped idempotency: composite unique
  `(organization_id, idempotency_key)`.
- Foreign keys (organizations/job_requests/job_schedules/schedule_occurrences)
  and query indexes (queue/claim, lease recovery, history, schedules, audit).
- Migrations: `001_foundation.sql` (regenerated canonical) +
  `002_jobs_durable.sql` (additive delta, reapply-safe) +
  `002_rollback_jobs_durable.sql` (compensating rollback).
- Validation harness `tools/foundation_pg_validate_durable.py` → **9/9 steps**
  (clean apply, schema/constraint/index inspection, repository tests,
  compensating rollback, reapply, fingerprint comparison, clean-room
  determinism, foundation regression) → evidence
  `postgres-durable-validation.json`.

## Submission & API (B04)

`foundation/jobs_durable.py` + `api/router.py`:
authenticated, organization-scoped submission; server-side membership +
permission resolution; job-type/payload-schema validation (unregistered types
fail closed); org-scoped idempotency; approval determination; provider/budget
class determination; never executes work in the request. Read-only GETs
(list/detail/run/audit timeline/queue posture/handler registry) create zero
jobs and execute zero jobs. Mutations use non-GET methods (create/cancel/
authorized retry). Approval grants promote pending jobs (`promote_approved_jobs`).

## Atomic claim & worker (B05/B06)

- PostgreSQL: `SELECT … FOR UPDATE SKIP LOCKED` inside a CTE feeding an
  `UPDATE … RETURNING` (one atomic statement). SQLite: `BEGIN IMMEDIATE` +
  conditional UPDATE (single-writer equivalence). Claim is a short transaction;
  handler execution is outside it.
- Lease owner/expiration; only the lease owner may heartbeat or finalize;
  stale workers are rejected; expired leases are recoverable.
- `foundation/jobs_worker.py` — org-scoped worker loop (poll → atomic claim →
  rechecks → execute → settle → audit). `drain()` runs an org queue to empty.

## Runtime rechecks (B07/B08)

Immediately before handler execution: organization active, membership active,
required permission, approval exists/applies/not expired/not revoked, provider
enabled (fixture class) / class permitted, budget available, not cancelled,
preview restrictions, payload schema supported. Failures move the job to the
correct blocked/cancelled state, audit the reason, and release reservations.

## Usage (B09)

`org_balances` ledger with Decimal/NUMERIC; atomic conditional reservation
(`granted - consumed - reserved >= amount`), settlement, release; per-attempt
idempotent usage events (`reserve:{run}:{attempt}` / `settle:{run}:{attempt}`);
no double reservation, no double debit, retry-safe settlement; cost-variance
guard blocks a job whose actual cost exceeds estimate + policy tolerance;
fake handlers use deterministic costs. No billing processors connected.

## Retry / cancellation / dead-letter (B10–B12)

- Retry: retryable-class classification, exponential backoff with bounded
  jitter, max attempts, attempt history, redacted errors, dead-letter on
  exhaustion. Tests cover transient→success, exhaustion, permanent, timeout,
  rate limit, malformed output, cancellation/auth-revocation during retry wait.
- Cancellation: queued/retry-wait direct; running/leased cooperative via
  CANCEL_REQUESTED; reservation release; audit history; org-scoped permission.
- Dead-letter: transition + reason, attempt history, redacted error storage,
  authorized manual retry with new-run linkage and parent linkage.

## Lease recovery & concurrency (B13/B14)

`recover_expired_leases` expires stale leases then re-queues them. Concurrency
matrix on disposable PostgreSQL (real threads, per-worker connections): two
workers/one job → single claim; many workers/jobs → exactly-once; duplicate
idempotency → single submission; stale completion rejected; concurrent
reservations cannot overspend; concurrent cancellation → single winner;
cross-org visibility zero; restart with queued + expired leases → recovery.

## Scheduler (B15)

`foundation/jobs_scheduler.py` — persisted schedules (organization, owner, job
template, timezone, cron/interval, enabled, next/last run, concurrency/misfire/
approval/budget/provider/failure policies, version). Enqueue-only: never
executes jobs, never calls providers. Atomic occurrence claiming (unique
`(schedule_id, occurrence_key)` → INSERT-ON-CONFLICT semantics); occurrence
idempotency across scheduler instances; misfire policy prevents unbounded
catch-up; suspended orgs, revoked owners, disabled schedules, and
concurrency-limit schedules are skipped; every enqueue/skip/failure is audited;
GET never ticks. Cron via `croniter` (interval supported natively).

## 1C-04 gate (B16)

`foundation/tests/test_1c04_gate.py` — full-path acceptance: approval →
claim → execute → settle → output → audit; transient retry; dead-letter →
authorized manual retry; organization isolation; GET-side-effect audit;
local-handler-only rule; blocked-job reservation release.

## Evidence

| Command | Result |
|---|---|
| `pytest foundation/tests` | 419 passed, 28 skipped |
| `pytest foundation/tests/test_1c04_gate.py` | 7 passed |
| `pytest` (disposable PG modules) | 28 passed |
| `foundation_pg_validate_durable` | 9/9 steps PASS |

## Warnings / skips

- 28 SQLite skips are the three PostgreSQL-only modules (require
  `FOUNDATION_DB_URL` pointing at the disposable loopback instance).
- 5 HMAC key-length warnings (test fixtures only; production posture rejects
  weak keys).
- The three PG modules are best run individually or in safe pairs; a single
  combined run with concurrent DDL has shown transient lock contention when
  stray connections remain (mitigated by terminating idle-in-transaction
  connections; `seed()` now always commits, so no product path leaks
  transactions).