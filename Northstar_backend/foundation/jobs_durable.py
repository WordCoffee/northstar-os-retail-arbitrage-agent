"""Durable job service (1C-04 / Workstream B).

Organization-scoped job submission, atomic claiming, lease/heartbeat ownership,
runtime authorization/approval/provider/budget rechecks, usage reservation and
settlement, retry/backoff, cancellation, dead-letter handling, lease recovery,
and audit. ONLY fake/local handlers execute; no remote system is ever contacted.

The authoritative transition model lives in ``jobs_state``; this module drives
it and persists transition evidence (``job_state_history``) + audit events.
"""
from __future__ import annotations

import json
import math
import time as _time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import uuid4

from .approvals import ApprovalService
from .audit import AuditService
from .context import RequestContext
from .enums import (
    Environment, Role, UsageEventStatus, CostKind, ApprovalState,
    CapabilitySafetyClass,
)
from .jobs_handlers import (
    HandlerRegistry, UnknownJobType, build_default_registry, is_retryable,
)
from .jobs_state import (
    JobActor, JobState, JobStateError, transition as state_transition,
    TERMINAL_STATES, is_cancellable, is_worker_terminal,
)
from .models import (
    ApprovalRequest, JobRequest, JobRun, JobStateHistory, UsageEvent,
    OrgBalance, utcnow,
)
from .permissions import PERM_REQUEST_REFRESH, evaluate
from .repositories import Repositories

DEFAULT_LEASE_SECONDS = 60
DEFAULT_BUDGET = Decimal("0.00")


def _now_iso() -> str:
    return utcnow().isoformat()


def _dec(value, default: Optional[Decimal] = None) -> Optional[Decimal]:
    if value is None:
        return default
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default
    return d


class JobValidationError(ValueError):
    """Structured submission/recheck validation failure."""

    def __init__(self, code: str, message: str = "", *, job_id: Optional[str] = None,
                 run_id: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.job_id = job_id
        self.run_id = run_id


class RecheckFailure(Exception):
    """A runtime recheck failed; carries the target state + reason."""

    def __init__(self, state: str, reason: str, *, code: str = "recheck_failed") -> None:
        super().__init__(reason)
        self.state = state
        self.reason = reason
        self.code = code


class JobStateConflict(RuntimeError):
    """A concurrent actor moved the job before the worker could finish.

    Raised when a transition or settlement guarded on ``expected_state`` loses
    the race. The worker must never overwrite the winner: a pending
    cancellation is terminal for the worker, so the caller either acknowledges
    it (CANCEL_REQUESTED -> CANCELLED) or fails closed.
    """

    def __init__(self, expected: str, actual: Optional[str], *,
                 job_id: Optional[str] = None) -> None:
        super().__init__(f"expected job state {expected!r}, found {actual!r}")
        self.expected = expected
        self.actual = actual
        self.job_id = job_id


@dataclass
class ExecutionOutcome:
    run_id: str
    job_id: str
    state: str
    failure_class: Optional[str] = None
    attempts: int = 0
    actual_cost: Optional[Decimal] = None
    reserved_cost: Optional[Decimal] = None


class DurableJobService:
    def __init__(self, repos: Repositories, *, audit: Optional[AuditService] = None,
                 approvals: Optional[ApprovalService] = None,
                 registry: Optional[HandlerRegistry] = None) -> None:
        self.repos = repos
        self.audit = audit or AuditService(repos)
        self.approvals = approvals or ApprovalService(repos, self.audit)
        self.registry = registry or build_default_registry()
        self.lease_seconds = DEFAULT_LEASE_SECONDS
        self._services: dict = {}

    def register_service(self, name: str, obj) -> None:
        """Register domain services handlers may depend on (e.g. the keyword
        importer for the ``keyword_import`` job type)."""
        self._services[name] = obj

    # ------------------------------------------------------------------
    # B04 — authenticated organization-scoped submission
    # ------------------------------------------------------------------

    def submit(self, ctx: RequestContext, *, job_type: str, payload: Optional[dict],
               payload_schema_version: str, idempotency_key: Optional[str] = None,
               priority: int = 5, reason: Optional[str] = None,
               correlation_id: Optional[str] = None,
               service: Optional[str] = None, environment: Optional[str] = None) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise JobValidationError("no_organization",
                                     "organization context required for submission")
        if not ctx.user_id:
            raise JobValidationError("no_actor", "authenticated user required")
        # server-side membership + permission
        member = self._require_active_membership(org_id, ctx.user_id)
        allowed, perm_reason = evaluate(ctx, PERM_REQUEST_REFRESH)
        if not allowed:
            raise JobValidationError("permission_denied", perm_reason)

        spec = self.registry.spec(job_type)  # raises UnknownJobType (fail closed)
        if payload_schema_version != spec.input_schema_version:
            raise JobValidationError(
                "unsupported_payload_schema",
                f"payload schema {payload_schema_version!r} not supported "
                f"(expected {spec.input_schema_version!r})")

        # Centralized entitlement check (1C-06 master slice / Phase B): over-tier
        # job creation is denied. The tier limit is enforced here AND the same
        # limit gates the worker-facing surface — never a hardcoded plan-name
        # comparison in this module.
        entsvc = self._services.get("entitlements")
        if entsvc is not None:
            try:
                entsvc.enforce_max_jobs(ctx)
            except Exception as e:  # noqa: BLE001 - centralized entitlement error
                if getattr(e, "code", None) == "entitlement_denied":
                    raise JobValidationError("entitlement_denied", str(e))
                raise

        # account + request-type scoped idempotency (owner financial gate)
        def _existing():
            if not idempotency_key:
                return None
            return self.repos.job_requests.find({
                "organization_id": org_id, "job_type": job_type,
                "idempotency_key": idempotency_key})

        existing = _existing()
        if existing:
            self.audit.record(
                action="job.submit", actor_user_id=ctx.user_id,
                actor_role=ctx.effective_role, organization_id=org_id,
                resource_type="job_request", resource_id=existing["id"],
                correlation_id=correlation_id,
                environment=environment or ctx.environment,
                result="success", after_meta={"idempotent_replay": True,
                                              "job_type": job_type})
            return self._job_view(existing, ctx)

        requires_approval = spec.approval_class != "none"
        est = spec.deterministic_cost
        req = JobRequest(
            organization_id=org_id, user_id=ctx.user_id,
            service=service or f"durable:{job_type}",
            environment=environment or ctx.environment,
            idempotency_key=idempotency_key, requires_approval=requires_approval,
            reason=reason, priority=priority, correlation_id=correlation_id,
            state=JobState.DRAFT.value, job_type=job_type, payload=payload,
            payload_schema_version=payload_schema_version,
            provider_class=spec.provider_class, budget_class=spec.budget_class,
            estimated_cost=est,
            provenance={"submitted_by": ctx.user_id, "auth_method": ctx.auth_method},
        )
        try:
            row = self.repos.job_requests.add(req)
        except Exception:  # noqa: BLE001 - concurrent duplicate won the race
            # The DB-level unique (organization_id, job_type, idempotency_key)
            # rejected a concurrent duplicate: return the ORIGINAL job/result
            # rather than surfacing an error or creating a second execution.
            won = _existing()
            if won is not None:
                self.audit.record(
                    action="job.submit", actor_user_id=ctx.user_id,
                    actor_role=ctx.effective_role, organization_id=org_id,
                    resource_type="job_request", resource_id=won["id"],
                    correlation_id=correlation_id,
                    environment=environment or ctx.environment,
                    result="success",
                    after_meta={"idempotent_replay": True, "job_type": job_type,
                                "concurrent_duplicate": True})
                return self._job_view(won, ctx)
            raise
        run = self._create_initial_run(row, spec, ctx)
        self._record_creation(row, run, correlation_id=correlation_id)

        if requires_approval:
            approval = self.approvals.request(
                organization_id=org_id, requested_by_user_id=ctx.user_id,
                capability=f"job.run:{job_type}",
                safety_class=CapabilitySafetyClass.WRITE_EXTERNAL.value
                if spec.provider_class != "local" else CapabilitySafetyClass.DRAFT.value,
                resource_type="job_request", resource_id=row["id"],
                risk_level="low", cost_estimate=float(est),
                idempotency_key=f"job-approval:{row['id']}",
                environment=ctx.environment)
            self.repos.db.conn.execute(
                "UPDATE job_requests SET approval_id=? WHERE id=?",
                (approval["id"], row["id"]))
            self.repos.db.conn.commit()
            row["approval_id"] = approval["id"]
            self._transition(job=row, run=run, new_state=JobState.PENDING_APPROVAL.value,
                             actor=JobActor.REQUESTOR.value, reason="approval required",
                             correlation_id=correlation_id,
                             approval_ref=approval["id"])
        else:
            self._transition(job=row, run=run, new_state=JobState.QUEUED.value,
                             actor=JobActor.REQUESTOR.value, reason="submitted",
                             correlation_id=correlation_id)

        self.audit.record(
            action="job.submit", actor_user_id=ctx.user_id,
            actor_role=ctx.effective_role, organization_id=org_id,
            resource_type="job_request", resource_id=row["id"],
            correlation_id=correlation_id,
            environment=environment or ctx.environment,
            approval_ref=row.get("approval_id"),
            after_meta={"job_type": job_type, "state": row["state"],
                        "requires_approval": requires_approval})
        return self._job_view(self.repos.job_requests.get(row["id"]), ctx)

    def promote_approved_jobs(self, approval_id: str) -> list[dict]:
        """Approval granted → move matching pending jobs to QUEUED."""
        pending = self.repos.job_requests.list(
            where={"approval_id": approval_id, "state": JobState.PENDING_APPROVAL.value})
        promoted = []
        for job in pending:
            run = self._current_run(job)
            self._transition(job=job, run=run, new_state=JobState.QUEUED.value,
                             actor=JobActor.APPROVER.value,
                             reason=f"approval granted ({approval_id})",
                             approval_ref=approval_id)
            promoted.append(job["id"])
        return promoted

    # ------------------------------------------------------------------
    # B04 — read-only queries (GET has zero side effects)
    # ------------------------------------------------------------------

    def get_job(self, org_id: str, job_id: str) -> Optional[dict]:
        job = self.repos.job_requests.get(job_id)
        if not job or job["organization_id"] != org_id:
            return None
        return self._job_view(job)

    def list_jobs(self, org_id: str, *, limit: int = 50, offset: int = 0,
                  state: Optional[str] = None) -> dict:
        where = {"organization_id": org_id}
        if state:
            where["state"] = state
        rows = self.repos.job_requests.list(where=where,
                                            order_by="created_at DESC",
                                            limit=limit, offset=offset)
        return {"items": [self._job_view(r) for r in rows],
                "total": len(self.repos.job_requests.list(where=where))}

    def get_run(self, org_id: str, run_id: str) -> Optional[dict]:
        run = self.repos.job_runs.find({"run_id": run_id})
        if not run:
            return None
        job = self.repos.job_requests.get(run["job_request_id"])
        if not job or job["organization_id"] != org_id:
            return None
        return self._run_view(run, job)

    def audit_timeline(self, org_id: str, job_id: str) -> list[dict]:
        job = self.repos.job_requests.get(job_id)
        if not job or job["organization_id"] != org_id:
            return []
        history = self.repos.job_state_history.for_job(job_id)
        return [self._history_view(h) for h in reversed(history)]

    def queue_posture(self, org_id: str) -> dict:
        rows = self.repos.job_requests.list(where={"organization_id": org_id})
        counts: dict[str, int] = {}
        for r in rows:
            s = r.get("state") or "unknown"
            counts[s] = counts.get(s, 0) + 1
        return {"organization_id": org_id,
                "by_state": counts,
                "queued": counts.get(JobState.QUEUED.value, 0),
                "leased": counts.get(JobState.LEASED.value, 0),
                "running": counts.get(JobState.RUNNING.value, 0),
                "retry_wait": counts.get(JobState.RETRY_WAIT.value, 0),
                "dead_letter": counts.get(JobState.DEAD_LETTER.value, 0)}

    # ------------------------------------------------------------------
    # B04/B11/B12 — cancellation, retry
    # ------------------------------------------------------------------

    def cancel(self, ctx: RequestContext, job_id: str, *, reason: str) -> dict:
        job = self._owned_job(ctx, job_id)
        run = self._current_run(job)
        # Recompute against the CURRENT state on each attempt so a concurrent
        # claim/start cannot turn a valid cancel into an illegal transition:
        # running/leased jobs get a cooperative cancel-request, anything else
        # is cancelled outright. If the worker finishes first, the cancel is
        # refused with the documented structured error.
        for _ in range(3):
            current = self._job_state(job)
            if not is_cancellable(current):
                raise JobValidationError(
                    "not_cancellable", f"job state {current} is not cancellable",
                    job_id=job_id)
            if current in (JobState.RUNNING.value, JobState.LEASED.value):
                new_state = JobState.CANCEL_REQUESTED.value
            else:
                new_state = JobState.CANCELLED.value
            try:
                self._transition(job=job, run=run, new_state=new_state,
                                 actor=JobActor.OPERATOR.value, reason=reason,
                                 expected_state=current)
                break
            except JobStateConflict:
                continue  # the state moved under us; recompute
        else:
            fresh_state = self._job_state(job)
            raise JobValidationError(
                "not_cancellable", f"job state {fresh_state} is not cancellable",
                job_id=job_id)
        self._release_reservation_if_any(job, run, reason="cancelled")
        return self._job_view(self.repos.job_requests.get(job_id), ctx)

    def request_cancel(self, ctx: RequestContext, job_id: str, *, reason: str) -> dict:
        """Alias used by the worker when it observes a cancel request."""
        return self.cancel(ctx, job_id, reason=reason)

    def retry(self, ctx: RequestContext, job_id: str, *, reason: str) -> dict:
        job = self._owned_job(ctx, job_id)
        current = job["state"]
        if current not in (JobState.FAILED.value, JobState.DEAD_LETTER.value,
                           JobState.BLOCKED_BUDGET.value,
                           JobState.BLOCKED_PROVIDER.value,
                           JobState.BLOCKED_AUTHORIZATION.value):
            raise JobValidationError("not_retryable",
                                     f"job state {current} is not retryable",
                                     job_id=job_id)
        spec = self.registry.spec(job["job_type"])
        # Authorized retry creates a NEW run (new-run linkage).
        run = JobRun(
            job_request_id=job_id, state=JobState.QUEUED.value,
            run_id=str(uuid4()), attempts=0,
            max_attempts=spec.retry_policy.get("max_attempts", 3),
            priority=job.get("priority") or 5,
            parent_job_id=self._last_run_id(job), correlation_id=job.get("correlation_id"),
            scheduled_time=utcnow(),
        )
        self.repos.job_runs.add(run)
        run_row = self.repos.job_runs.get(run.id)
        self._transition(job=job, run=run_row, new_state=JobState.QUEUED.value,
                         actor=JobActor.OPERATOR.value, reason=reason)
        self.audit.record(
            action="job.retry", actor_user_id=ctx.user_id,
            actor_role=ctx.effective_role, organization_id=job["organization_id"],
            resource_type="job_request", resource_id=job_id,
            job_run_ref=run_row["run_id"], after_meta={"reason": reason,
                                                       "parent_run": run_row.get("parent_job_id")})
        return self._job_view(self.repos.job_requests.get(job_id), ctx)

    # ------------------------------------------------------------------
    # B05 — atomic claim
    # ------------------------------------------------------------------

    def claim_next(self, worker_id: str, *, organization_id: str,
                   lease_seconds: Optional[int] = None) -> Optional[dict]:
        if not organization_id:
            raise JobValidationError("no_organization",
                                     "claiming requires an organization scope")
        lease = lease_seconds or self.lease_seconds
        claimed = self.repos.db.atomic_claim_job(
            worker_id=worker_id, organization_id=organization_id,
            lease_seconds=lease, now_iso=_now_iso(), limit=1)
        if not claimed:
            return None
        run = claimed[0]
        job = self.repos.job_requests.get(run["job_request_id"])
        if job is None:
            raise JobValidationError("orphan_run", "run references a missing job",
                                     run_id=run["id"])
        # Mirror job state to LEASED.
        self._transition(job=job, run=run, new_state=JobState.LEASED.value,
                         actor=JobActor.WORKER.value,
                         reason=f"claimed by {worker_id}",
                         correlation_id=job.get("correlation_id"))
        return self._run_view(self.repos.job_runs.get(run["id"]), job)

    def heartbeat(self, run_id: str, worker_id: str, *,
                  extension_seconds: int = 30) -> dict:
        run = self.repos.job_runs.find({"run_id": run_id})
        if not run:
            raise JobValidationError("unknown_run", f"unknown run {run_id}")
        if run.get("lease_owner") != worker_id:
            raise JobValidationError("lease_not_owned",
                                     "only the lease owner may heartbeat",
                                     run_id=run_id)
        exp = (utcnow() + timedelta(seconds=extension_seconds)).isoformat()
        self.repos.db.conn.execute(
            "UPDATE job_runs SET heartbeat_time=?, lease_expiration=? WHERE id=?",
            (_now_iso(), exp, run["id"]))
        self.repos.db.conn.commit()
        return {"run_id": run_id, "lease_owner": worker_id,
                "heartbeat_at": _now_iso(), "lease_expiration": exp}

    def recover_expired_leases(self, *, organization_id: Optional[str] = None,
                               now_iso: Optional[str] = None) -> list[str]:
        """B13 — lease recovery: expire stale leases, then re-queue them.

        Only runs whose lease expired (heartbeat missed) are reclaimed. A new
        worker may then claim them normally.
        """
        now = now_iso or _now_iso()
        stale = self.repos.job_runs.list(where={"state": JobState.LEASED.value})
        recovered = []
        for run in stale:
            job = self.repos.job_requests.get(run["job_request_id"])
            if job is None:
                continue
            if organization_id and job["organization_id"] != organization_id:
                continue
            exp = run.get("lease_expiration")
            if exp and str(exp) < now:
                # Unknown outcome (handler may or may not have completed): the
                # run's outstanding reservation must be RELEASED, never settled
                # — no debit without a known-successful settlement.
                self._release_outstanding_reservations(job, run)
                self._transition(job=job, run=run,
                                 new_state=JobState.EXPIRED.value,
                                 actor=JobActor.RECOVERY.value,
                                 reason="lease expired")
                self._transition(job=job, run=run,
                                 new_state=JobState.QUEUED.value,
                                 actor=JobActor.RECOVERY.value,
                                 reason="reclaimed after lease expiry")
                recovered.append(run["run_id"])
        return recovered

    # ------------------------------------------------------------------
    # B06 — execution of a claimed job
    # ------------------------------------------------------------------

    def execute_claimed(self, run: dict, worker_id: str) -> ExecutionOutcome:
        run_id = run["run_id"]
        job = self.repos.job_requests.get(run["job_request_id"])
        if job is None:
            raise JobValidationError("orphan_run", "run references a missing job",
                                     run_id=run_id)
        if run.get("lease_owner") != worker_id:
            raise JobValidationError("lease_not_owned",
                                     "only the lease owner may execute", run_id=run_id)
        if job["state"] != JobState.LEASED.value:
            if job["state"] in (JobState.CANCEL_REQUESTED.value,
                                JobState.CANCELLED.value):
                # A cancel request arrived between the claim and the start of
                # execution. Cancellation is terminal for the worker: it must
                # acknowledge the request, not fail the execution.
                return self._finish_cancelled(job, run,
                                              reason="cancellation acknowledged")
            raise JobValidationError("not_leased", f"job is {job['state']} not leased",
                                     job_id=job["id"], run_id=run_id)

        # 1. runtime rechecks (B07/B08)
        try:
            self._runtime_rechecks(job, run)
        except RecheckFailure as exc:
            if exc.state == JobState.CANCELLED.value:
                # A pending cancellation is terminal for the worker: acknowledge
                # it, release anything reserved, and never settle.
                return self._finish_cancelled(job, run, reason=exc.reason)
            self._transition(job=job, run=run, new_state=exc.state,
                             actor=JobActor.WORKER.value, reason=exc.reason)
            self._release_reservation_if_any(job, run, reason=exc.reason)
            self.audit.record(
                action="job.blocked", actor_user_id=job.get("user_id"),
                actor_role=Role.OPERATOR.value, organization_id=job["organization_id"],
                resource_type="job_request", resource_id=job["id"],
                job_run_ref=run_id, result="denied",
                failure_class=exc.code, after_meta={"reason": exc.reason})
            return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                    state=exc.state)

        # 2. cancellation observed before execution starts. Fresh read: the
        #    operator may have cancelled since the job was claimed. A pending
        #    cancellation is terminal for the worker.
        if is_worker_terminal(self._job_state(job)):
            return self._finish_cancelled(job, run,
                                          reason="cancellation acknowledged",
                                          attempts=int(run.get("attempts") or 0))

        # 3. reserve usage (B09)
        spec = self.registry.spec(job["job_type"])
        est = _dec(job.get("estimated_cost"), Decimal("0.00")) or Decimal("0.00")
        reserved = self.reserve_usage(job, run, est, attempt=int(run.get("attempts") or 0) + 1)

        # 4. start run — guarded on LEASED: a cancel request that landed while
        #    the reservation was being taken wins over RUNNING.
        attempt = int(run.get("attempts") or 0) + 1
        self.repos.db.conn.execute(
            "UPDATE job_runs SET attempts=? WHERE id=?",
            (attempt, run["id"]))
        self.repos.db.conn.commit()
        run["attempts"] = attempt
        try:
            self._transition(job=job, run=run, new_state=JobState.RUNNING.value,
                             actor=JobActor.WORKER.value, reason="execution started",
                             correlation_id=job.get("correlation_id"),
                             expected_state=JobState.LEASED.value)
        except JobStateConflict as conflict:
            if conflict.actual == JobState.CANCEL_REQUESTED.value:
                return self._finish_cancelled(
                    job, run, reason="cancellation acknowledged",
                    attempts=attempt, reserved_cost=reserved)
            raise

        try:
            handler = self.registry.handler(job["job_type"])
        except UnknownJobType as e:
            cancelled = self._after_run_transition(
                job=job, run=run, new_state=JobState.FAILED.value,
                actor=JobActor.WORKER.value, reason=str(e),
                correlation_id=job.get("correlation_id"), attempts=attempt,
                reserved_cost=reserved)
            if cancelled is not None:
                return cancelled
            return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                    state=JobState.FAILED.value,
                                    failure_class="unknown_job_type",
                                    reserved_cost=reserved)

        payload = _as_dict(job.get("payload"))
        run_ctx = {
            "attempt": attempt,
            "job_id": job["id"],
            "run_id": run_id,
            "organization_id": job["organization_id"],
            "worker_id": worker_id,
            "services": self._services,
            "cancellation_requested": lambda: self._cancellation_requested(job),
        }

        try:
            result = handler(payload, run_ctx)
        except Exception as e:  # noqa: BLE001 - classify generic handler failure
            result = HandlerResultFallback(e)

        # heartbeat (post-execution; slow handlers heartbeat during via run_ctx)
        self.heartbeat(run_id, worker_id, extension_seconds=self.lease_seconds)

        # 5. outcome classification (financial integrity: ONLY a successful job
        #    settles; failed/cancelled/blocked/variance jobs RELEASE the
        #    reservation and never produce a ledger/usage settlement).
        actual = _dec(result.actual_cost, Decimal("0.00")) or Decimal("0.00")
        tolerance = max(Decimal("1.00"), est * Decimal("0.10"))
        variance_exceeded = actual > est + tolerance

        # A cancellation observed at any point while the handler ran wins over
        # the handler's own outcome: release, never settle, acknowledge once.
        if is_worker_terminal(self._job_state(job)):
            return self._finish_cancelled(job, run,
                                          reason="cancellation acknowledged",
                                          attempts=attempt, actual_cost=actual,
                                          reserved_cost=reserved)

        if result.ok and not variance_exceeded:
            # EXACTLY-ONCE settlement: DB-level unique on the settle key +
            # single transaction (balance + ledger) enforce one entry. The
            # settlement is guarded on RUNNING, so a cancel request that lands
            # between the check above and the debit wins: nothing is charged
            # and the job is acknowledged as cancelled instead of succeeding.
            already_settled = self._settlement_exists(run, attempt)
            try:
                self.settle_usage(
                    job, run, reserved, actual, attempt=attempt,
                    expected_state=None if already_settled
                    else JobState.RUNNING.value)
            except JobStateConflict as conflict:
                if conflict.actual == JobState.CANCEL_REQUESTED.value:
                    return self._finish_cancelled(
                        job, run, reason="cancellation acknowledged",
                        attempts=attempt, actual_cost=actual,
                        reserved_cost=reserved)
                raise
            self._persist_output(job, run, result)
            self._transition(job=job, run=run, new_state=JobState.SUCCEEDED.value,
                             actor=JobActor.WORKER.value, reason="handler success",
                             correlation_id=job.get("correlation_id"),
                             expected_state=JobState.RUNNING.value,
                             state_applied=not already_settled)
            return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                    state=JobState.SUCCEEDED.value,
                                    attempts=attempt, actual_cost=actual,
                                    reserved_cost=reserved)

        if result.failure_class == "cancelled":
            return self._finish_cancelled(job, run, reason="cancelled during run",
                                          attempts=attempt, actual_cost=actual,
                                          reserved_cost=reserved)

        if variance_exceeded:
            self.release_usage(job, run)
            self._store_error(job, run, _VarResult(actual, est))
            cancelled = self._after_run_transition(
                job=job, run=run, new_state=JobState.BLOCKED_BUDGET.value,
                actor=JobActor.WORKER.value,
                reason="actual cost exceeds policy variance",
                correlation_id=job.get("correlation_id"), attempts=attempt,
                actual_cost=actual, reserved_cost=reserved)
            if cancelled is not None:
                return cancelled
            return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                    state=JobState.BLOCKED_BUDGET.value,
                                    failure_class="budget_variance",
                                    attempts=attempt, actual_cost=actual,
                                    reserved_cost=reserved)

        if is_retryable(result.failure_class) and \
                attempt < spec.retry_policy.get("max_attempts", 3):
            # retryable failure: release this attempt's reservation, no ledger
            self.release_usage(job, run)
            try:
                self._schedule_retry(job, run, result, attempt,
                                     expected_state=JobState.RUNNING.value)
            except JobStateConflict as conflict:
                if conflict.actual == JobState.CANCEL_REQUESTED.value:
                    return self._finish_cancelled(
                        job, run, reason="cancellation acknowledged",
                        attempts=attempt, actual_cost=actual,
                        reserved_cost=reserved)
                raise
            return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                    state=JobState.RETRY_WAIT.value,
                                    failure_class=result.failure_class,
                                    attempts=attempt, actual_cost=actual,
                                    reserved_cost=reserved)

        # permanent failure or retries exhausted: release, never settle
        self.release_usage(job, run)
        self._store_error(job, run, result)
        if attempt >= spec.retry_policy.get("max_attempts", 3) and \
                is_retryable(result.failure_class):
            new_state = JobState.DEAD_LETTER.value
            reason = "retries exhausted"
        else:
            new_state = JobState.FAILED.value
            reason = result.failure_class or "failed"
        cancelled = self._after_run_transition(
            job=job, run=run, new_state=new_state,
            actor=JobActor.WORKER.value, reason=reason,
            correlation_id=job.get("correlation_id"), attempts=attempt,
            actual_cost=actual, reserved_cost=reserved)
        if cancelled is not None:
            return cancelled
        return ExecutionOutcome(run_id=run_id, job_id=job["id"],
                                state=new_state,
                                failure_class=result.failure_class,
                                attempts=attempt, actual_cost=actual,
                                reserved_cost=reserved)

    # ------------------------------------------------------------------
    # B07/B08 — runtime rechecks
    # ------------------------------------------------------------------

    def _runtime_rechecks(self, job: dict, run: dict) -> None:
        org_id = job["organization_id"]
        org = self.repos.organizations.get(org_id)
        if org is None:
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 "organization no longer exists",
                                 code="organization_missing")
        # 1. organization active
        if not org.get("active", True):
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 "organization is suspended",
                                 code="organization_suspended")
        # 2. membership active
        user_id = job.get("user_id")
        memberships = self.repos.memberships.list(
            where={"organization_id": org_id, "user_id": user_id})
        active = [m for m in memberships if (m.get("status") or "active") == "active"]
        if not active:
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 "membership revoked or suspended",
                                 code="membership_inactive")
        # 3. required permission
        spec = self.registry.spec(job["job_type"])
        role = active[0]["role"]
        if not _role_has(role, spec.required_permission):
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 f"role {role} lacks {spec.required_permission}",
                                 code="permission_missing")
        # 4. approval when required
        if job.get("requires_approval") or job.get("approval_id"):
            approval = self.repos.approvals.get(job.get("approval_id"))
            if approval is None or approval["state"] != ApprovalState.GRANTED.value:
                raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                     "approval missing or not granted",
                                     code="approval_missing")
            if approval.get("expires_at") and str(approval["expires_at"]) < _now_iso():
                raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                     "approval expired",
                                     code="approval_expired")
            if approval.get("resource_id") and approval["resource_id"] != job["id"]:
                raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                     "approval does not apply to this exact action",
                                     code="approval_mismatch")
        # 5. preview restrictions
        if job.get("environment") == Environment.PRODUCTION.value and \
                self._is_preview_job(job):
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 "preview write restrictions apply",
                                 code="preview_restricted")
        # 6. provider enabled + environment permits (B08)
        if spec.provider_class not in ("local", "fixture"):
            raise RecheckFailure(JobState.BLOCKED_PROVIDER.value,
                                 f"provider class {spec.provider_class!r} not "
                                 "permitted in 1C-04",
                                 code="provider_class_not_permitted")
        if spec.provider_class == "fixture":
            provider_row = self.repos.providers.by_key(job.get("job_type") or "")
            if provider_row is None or not provider_row.get("enabled"):
                raise RecheckFailure(JobState.BLOCKED_PROVIDER.value,
                                     "provider disabled",
                                     code="provider_disabled")
        # 7. budget available (B08/B09)
        if not self.budget_available(job, run):
            raise RecheckFailure(JobState.BLOCKED_BUDGET.value,
                                 "insufficient available balance",
                                 code="budget_insufficient")
        # 8. cancellation not requested — read FRESH: the operator may have
        #    requested cancellation since the job was claimed.
        if self._job_state(job) == JobState.CANCEL_REQUESTED.value:
            raise RecheckFailure(JobState.CANCELLED.value, "cancellation requested",
                                 code="cancelled")
        # 9. payload schema supported
        if job.get("payload_schema_version") != spec.input_schema_version:
            raise RecheckFailure(JobState.BLOCKED_AUTHORIZATION.value,
                                 "payload schema version no longer supported",
                                 code="payload_schema_unsupported")

    # ------------------------------------------------------------------
    # B09 — usage reservation and settlement (Decimal)
    # ------------------------------------------------------------------

    def budget_available(self, job: dict, run: dict) -> bool:
        bal = self._balance(job["organization_id"])
        est = _dec(job.get("estimated_cost"), Decimal("0.00")) or Decimal("0.00")
        available = bal.available
        return est <= available

    def reserve_usage(self, job: dict, run: dict, amount: Decimal, *, attempt: int = 1) -> Decimal:
        amount = _dec(amount, Decimal("0.00")) or Decimal("0.00")
        if amount <= 0:
            return Decimal("0.00")
        org_id = job["organization_id"]
        rowcount = self.repos.db.conn.execute(
            "UPDATE org_balances SET reserved = reserved + ?, updated_at = ? "
            "WHERE organization_id = ? AND granted - consumed - reserved >= ?",
            (float(amount), _now_iso(), org_id, float(amount)))
        self.repos.db.conn.commit()
        if rowcount.rowcount == 0:
            # ensure a ledger row exists, then retry once (idempotent create)
            self._ensure_balance(org_id)
            rowcount = self.repos.db.conn.execute(
                "UPDATE org_balances SET reserved = reserved + ?, updated_at = ? "
                "WHERE organization_id = ? AND granted - consumed - reserved >= ?",
                (float(amount), _now_iso(), org_id, float(amount)))
            self.repos.db.conn.commit()
        if rowcount.rowcount == 0:
            raise RecheckFailure(JobState.BLOCKED_BUDGET.value,
                                 "insufficient balance to reserve",
                                 code="budget_insufficient")
        # Each reservation is a distinct event (nonce key), so a re-executed
        # attempt after an unknown-outcome crash can never collide with the
        # prior reservation's unique key.
        nonce = uuid4().hex
        event = UsageEvent(
            organization_id=org_id, user_id=job.get("user_id"),
            service=job.get("service"), workflow_run_id=run.get("run_id"),
            provider="local", estimated_cost=amount,
            credits_debited_shadow=amount, cost_kind=CostKind.ESTIMATED.value,
            status=UsageEventStatus.RESERVED.value,
            idempotency_key=f"reserve:{run['run_id']}:{attempt}:{nonce}",
            environment=job.get("environment"),
            provenance={"kind": "job_reservation", "job_id": job["id"],
                        "run_id": run["run_id"], "attempt": attempt})
        self.repos.usage.add(event)
        return amount

    def _release_run_reservations(self, job: dict, run: dict) -> Decimal:
        """Release ALL outstanding reservations for the run (at most one is
        outstanding at any time). Returns the released total."""
        events = self.repos.usage.list(
            where={"workflow_run_id": run.get("run_id"),
                   "status": UsageEventStatus.RESERVED.value})
        if not events:
            return Decimal("0.00")
        total = sum((_dec(e.get("credits_debited_shadow"), Decimal("0.00"))
                     or Decimal("0.00") for e in events), Decimal("0.00"))
        if total <= 0:
            return Decimal("0.00")
        conn = self.repos.db.conn
        try:
            conn.execute(
                "UPDATE org_balances SET reserved = reserved - ?, updated_at = ? "
                "WHERE organization_id = ?",
                (float(total), _now_iso(), job["organization_id"]))
            conn.execute(
                "UPDATE usage_events SET status=?, reversal_ref=? "
                "WHERE workflow_run_id=? AND status=?",
                (UsageEventStatus.REVERSED.value, run.get("run_id"),
                 run.get("run_id"), UsageEventStatus.RESERVED.value))
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise
        return total

    def settle_usage(self, job: dict, run: dict, reserved: Decimal,
                     actual: Decimal, *, attempt: int = 1,
                     expected_state: Optional[str] = None) -> dict:
        """EXACTLY-ONCE settlement for a SUCCESSFUL attempt.

        The DB-level UNIQUE(idempotency_key) on ``settle:{run}:{attempt}`` plus
        a single transaction (balance + ledger insert + reserved-event release)
        guarantee one successful job produces exactly one usage/ledger entry.
        Concurrent double-settlement attempts race to the unique index; the
        loser rolls back and returns the winner's entry.

        ``expected_state`` optionally guards the settlement: the same
        transaction moves the job to SUCCEEDED only while it still holds that
        state. If a concurrent actor (a cancel request) moved it first, nothing
        is debited and :class:`JobStateConflict` is raised.
        """
        org_id = job["organization_id"]
        actual = _dec(actual, Decimal("0.00")) or Decimal("0.00")
        key = f"settle:{run['run_id']}:{attempt}"
        existing = self.repos.usage.find({"idempotency_key": key})
        if existing:
            return existing  # exactly-once: already settled
        event = UsageEvent(
            organization_id=org_id, user_id=job.get("user_id"),
            service=job.get("service"), workflow_run_id=run.get("run_id"),
            provider="local", provider_reported_cost=float(actual),
            estimated_cost=float(_dec(reserved, Decimal("0.00")) or Decimal("0.00")),
            credits_debited_shadow=float(actual),
            cost_kind=CostKind.REPORTED.value,
            status=UsageEventStatus.FINALIZED.value,
            idempotency_key=key,
            reversal_ref=run.get("run_id"),
            environment=job.get("environment"),
            provenance={"kind": "job_settlement", "job_id": job["id"],
                        "run_id": run["run_id"], "ok": True, "attempt": attempt})
        conn = self.repos.db.conn
        try:
            if expected_state is not None:
                # Guarded completion: the debit commits only while the worker
                # still owns the expected state. A cancel request wins and the
                # job is never charged.
                cur = conn.execute(
                    "UPDATE job_requests SET state=? WHERE id=? AND state=?",
                    (JobState.SUCCEEDED.value, job["id"], expected_state))
                if cur.rowcount == 0:
                    conn.rollback()
                    current = self.repos.job_requests.get(job["id"])
                    raise JobStateConflict(
                        expected_state, (current or {}).get("state"),
                        job_id=job["id"])
                # Mirror the run in the same transaction so job + run never
                # disagree if the process dies right after the debit.
                conn.execute(
                    "UPDATE job_runs SET state=?, finished_at=? WHERE id=?",
                    (JobState.SUCCEEDED.value, _now_iso(), run["id"]))
            # ONE transaction: balance + ledger + reserved-event release.
            conn.execute(
                "UPDATE org_balances SET reserved = reserved - ?, "
                "consumed = consumed + ?, updated_at = ? WHERE organization_id = ?",
                (float(_dec(reserved, Decimal("0.00")) or Decimal("0.00")),
                 float(actual), _now_iso(), org_id))
            conn.execute(
                "UPDATE usage_events SET status=?, reversal_ref=? "
                "WHERE workflow_run_id=? AND status=?",
                (UsageEventStatus.REVERSED.value, run["run_id"],
                 run["run_id"], UsageEventStatus.RESERVED.value))
            self.repos.db.insert_no_commit("usage_events", _event_dict(event))
            conn.commit()
        except JobStateConflict:
            raise
        except Exception:
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            existing = self.repos.usage.find({"idempotency_key": key})
            if existing:
                return existing  # a concurrent settle won; exactly-once holds
            raise
        return self.repos.usage.find({"idempotency_key": key})

    def release_usage(self, job: dict, run: dict) -> None:
        """Release a NON-SUCCESSFUL attempt's reservation. NEVER creates a
        usage/ledger settlement and NEVER debits."""
        self._release_run_reservations(job, run)

    def _release_outstanding_reservations(self, job: dict, run: dict) -> None:
        """Unknown-outcome recovery: release outstanding reservations for the
        run WITHOUT debiting — the handler outcome is unknown."""
        self._release_run_reservations(job, run)

    def _release_reservation_if_any(self, job: dict, run: dict, *, reason: str) -> None:
        if run is None:
            return
        self._release_run_reservations(job, run)

    def _reserved_amount(self, run: dict) -> Decimal:
        events = self.repos.usage.list(
            where={"workflow_run_id": run.get("run_id"),
                   "status": UsageEventStatus.RESERVED.value})
        return sum((_dec(e.get("credits_debited_shadow"), Decimal("0.00"))
                    or Decimal("0.00") for e in events), Decimal("0.00"))

    def _balance(self, org_id: str) -> OrgBalance:
        row = self.repos.org_balances.get(org_id)
        if not row:
            bal = OrgBalance(organization_id=org_id)
            self.repos.org_balances.add(bal)
            return bal
        return OrgBalance(
            organization_id=org_id,
            granted=_dec(row.get("granted"), Decimal("0.00")) or Decimal("0.00"),
            reserved=_dec(row.get("reserved"), Decimal("0.00")) or Decimal("0.00"),
            consumed=_dec(row.get("consumed"), Decimal("0.00")) or Decimal("0.00"))

    def _ensure_balance(self, org_id: str) -> None:
        if self.repos.org_balances.get(org_id) is None:
            self.repos.org_balances.add(OrgBalance(organization_id=org_id))

    def grant(self, org_id: str, amount: Decimal, *, note: Optional[str] = None) -> dict:
        """Explicit credit grant (test/operator tooling; never a billing hook)."""
        amount = _dec(amount, Decimal("0.00")) or Decimal("0.00")
        self._ensure_balance(org_id)
        self.repos.db.conn.execute(
            "UPDATE org_balances SET granted = granted + ?, updated_at = ? "
            "WHERE organization_id = ?",
            (float(amount), _now_iso(), org_id))
        self.repos.db.conn.commit()
        self.audit.record(action="balance.grant", organization_id=org_id,
                          after_meta={"amount": str(amount), "note": note})
        return self._balance_view(org_id)

    # ------------------------------------------------------------------
    # B10 — retry scheduling
    # ------------------------------------------------------------------

    def _schedule_retry(self, job: dict, run: dict, result, attempt: int,
                        *, expected_state: Optional[str] = None) -> None:
        spec = self.registry.spec(job["job_type"])
        backoff = self.backoff_seconds(spec.retry_policy, attempt)
        scheduled = (utcnow() + timedelta(seconds=backoff)).isoformat()
        self._store_error(job, run, result)
        self.repos.db.conn.execute(
            "UPDATE job_runs SET attempts=?, scheduled_time=?, error_code=?, "
            "error_summary=? WHERE id=?",
            (attempt, scheduled, result.error_code, result.error_summary, run["id"]))
        self.repos.db.conn.commit()
        run["attempts"] = attempt
        self._transition(job=job, run=run, new_state=JobState.RETRY_WAIT.value,
                         actor=JobActor.WORKER.value,
                         reason=f"retryable {result.failure_class}",
                         correlation_id=job.get("correlation_id"),
                         expected_state=expected_state)

    @staticmethod
    def backoff_seconds(policy: dict, attempt: int) -> int:
        base = int(policy.get("backoff_base_seconds", 1))
        multiplier = int(policy.get("backoff_multiplier", 2))
        cap = int(policy.get("max_backoff_seconds", 60))
        jitter = float(policy.get("jitter_seconds", 0) or 0)
        exp = min(cap, base * (multiplier ** max(0, attempt - 1)))
        if jitter > 0:
            exp += _time.monotonic() % jitter  # deterministic bounded jitter
        return int(exp)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _create_initial_run(self, job: dict, spec, ctx: RequestContext) -> dict:
        run = JobRun(
            job_request_id=job["id"], state=job["state"], run_id=str(uuid4()),
            attempts=0, max_attempts=spec.retry_policy.get("max_attempts", 3),
            priority=job.get("priority") or 5, correlation_id=job.get("correlation_id"),
            scheduled_time=None,
        )
        self.repos.job_runs.add(run)
        return self.repos.job_runs.get(run.id)

    def _current_run(self, job: dict) -> Optional[dict]:
        runs = self.repos.job_runs.by_request(job["id"])
        if not runs:
            return None
        runs_sorted = sorted(runs, key=lambda r: r.get("created_at") or "", reverse=True)
        return runs_sorted[0]

    def _last_run_id(self, job: dict) -> Optional[str]:
        run = self._current_run(job)
        return run["run_id"] if run else None

    def _job_state(self, job: dict) -> str:
        """Current persisted job state (never the caller's stale snapshot)."""
        fresh = self.repos.job_requests.get(job["id"])
        return ((fresh or job).get("state") or JobState.DRAFT.value)

    def _settlement_exists(self, run: dict, attempt: int) -> bool:
        key = f"settle:{run['run_id']}:{attempt}"
        return self.repos.usage.find({"idempotency_key": key}) is not None

    def _finish_cancelled(self, job: dict, run: dict, *, reason: str,
                          attempts: int = 0,
                          actual_cost: Optional[Decimal] = None,
                          reserved_cost: Optional[Decimal] = None
                          ) -> ExecutionOutcome:
        """Acknowledge a worker-observed cancellation exactly once.

        Cancellation is terminal for the worker: the reservation is released
        (never settled, never debited) and the job moves CANCEL_REQUESTED ->
        CANCELLED. Any other state fails closed rather than overwriting another
        actor's outcome.
        """
        current = self._job_state(job)
        if current not in (JobState.CANCEL_REQUESTED.value,
                           JobState.CANCELLED.value):
            # Fail closed BEFORE touching money: another actor already finished
            # the job and the worker must not overwrite or refund it.
            raise JobStateConflict(JobState.CANCEL_REQUESTED.value, current,
                                   job_id=job["id"])
        self.release_usage(job, run)
        if current == JobState.CANCEL_REQUESTED.value:
            self._transition(job=job, run=run,
                             new_state=JobState.CANCELLED.value,
                             actor=JobActor.WORKER.value, reason=reason,
                             correlation_id=job.get("correlation_id"),
                             expected_state=JobState.CANCEL_REQUESTED.value)
        return ExecutionOutcome(run_id=run["run_id"], job_id=job["id"],
                                state=JobState.CANCELLED.value,
                                failure_class="cancelled", attempts=attempts,
                                actual_cost=actual_cost,
                                reserved_cost=reserved_cost)

    def _after_run_transition(self, *, job: dict, run: dict, new_state: str,
                              actor: str, reason: str,
                              correlation_id: Optional[str] = None,
                              attempts: int = 0,
                              actual_cost: Optional[Decimal] = None,
                              reserved_cost: Optional[Decimal] = None
                              ) -> Optional[ExecutionOutcome]:
        """Transition out of RUNNING, guarded so a cancel request wins.

        Returns a CANCELLED outcome when a concurrent cancel request claimed
        the job first; ``None`` when the requested transition was applied.
        """
        try:
            self._transition(job=job, run=run, new_state=new_state,
                             actor=actor, reason=reason,
                             correlation_id=correlation_id,
                             expected_state=JobState.RUNNING.value)
            return None
        except JobStateConflict as conflict:
            if conflict.actual != JobState.CANCEL_REQUESTED.value:
                raise
            return self._finish_cancelled(
                job, run, reason="cancellation acknowledged", attempts=attempts,
                actual_cost=actual_cost, reserved_cost=reserved_cost)

    def _transition(self, *, job: dict, run: Optional[dict], new_state: str,
                    actor: str, reason: Optional[str],
                    correlation_id: Optional[str] = None,
                    approval_ref: Optional[str] = None,
                    audit: bool = True,
                    expected_state: Optional[str] = None,
                    state_applied: bool = False) -> None:
        if state_applied and not expected_state:
            raise ValueError("state_applied requires expected_state")
        # The authoritative previous state is the CURRENT database state —
        # an operator may have concurrently requested cancellation, etc.
        fresh = self.repos.job_requests.get(job["id"])
        actual = (fresh.get("state") if fresh else job.get("state")) \
            or JobState.DRAFT.value
        if state_applied:
            # The caller already committed the state change atomically (in the
            # settlement transaction); only the evidence is recorded here.
            prev = expected_state
            if actual != new_state:
                raise JobStateConflict(expected_state, actual, job_id=job["id"])
        else:
            prev = actual
            if expected_state is not None and prev != expected_state:
                raise JobStateConflict(expected_state, prev, job_id=job["id"])
        state_transition(
            job_id=job["id"], previous_state=prev, new_state=new_state,
            actor=actor, reason=reason,
            run_id=run.get("run_id") if run else None,
            correlation_id=correlation_id,
        )
        try:
            if expected_state is not None and not state_applied:
                # Guarded write: a concurrent actor (a cancel request, lease
                # recovery) that moved the job first wins. The worker never
                # overwrites it — cancellation is terminal for the worker.
                cur = self.repos.db.conn.execute(
                    "UPDATE job_requests SET state=? WHERE id=? AND state=?",
                    (new_state, job["id"], expected_state))
                if cur.rowcount == 0:
                    self.repos.db.conn.rollback()
                    current = self.repos.job_requests.get(job["id"])
                    raise JobStateConflict(
                        expected_state, (current or {}).get("state"),
                        job_id=job["id"])
            history = JobStateHistory(
                job_id=job["id"], run_id=run.get("run_id") if run else None,
                previous_state=prev, new_state=new_state, actor=actor, reason=reason,
                correlation_id=correlation_id, audit_event_ref=None)
            hist_row = self.repos.job_state_history.add(history)
            # mirror state on run + job
            if run is not None:
                self.repos.db.conn.execute(
                    "UPDATE job_runs SET state=?, finished_at=? WHERE id=?",
                    (new_state, _now_iso() if new_state in TERMINAL_STATES else None,
                     run["id"]))
                run["state"] = new_state
            if expected_state is None:
                self.repos.db.conn.execute(
                    "UPDATE job_requests SET state=? WHERE id=?",
                    (new_state, job["id"]))
            self.repos.db.conn.commit()
            job["state"] = new_state
            if audit:
                audit_ref = self.audit.record(
                    action=f"job.state.{new_state}", actor_user_id=job.get("user_id"),
                    actor_role=actor, organization_id=job["organization_id"],
                    resource_type="job_request", resource_id=job["id"],
                    job_run_ref=run.get("run_id") if run else None,
                    approval_ref=approval_ref,
                    correlation_id=correlation_id,
                    before_meta={"state": prev, "actor": actor},
                    after_meta={"state": new_state, "reason": reason,
                                "correlation_id": correlation_id})
                if hist_row:
                    self.repos.db.conn.execute(
                        "UPDATE job_state_history SET audit_event_ref=? WHERE id=?",
                        (audit_ref["id"], hist_row["id"]))
                    self.repos.db.conn.commit()
        except Exception:
            # Never leak an open transaction on the connection.
            try:
                self.repos.db.conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            raise

    def _record_creation(self, job: dict, run: dict, *,
                         correlation_id: Optional[str] = None) -> None:
        """Creation evidence for the initial (non-transition) DRAFT record."""
        history = JobStateHistory(
            job_id=job["id"], run_id=run["run_id"],
            previous_state="(created)", new_state=JobState.DRAFT.value,
            actor=JobActor.SYSTEM.value, reason="submission created",
            correlation_id=correlation_id)
        self.repos.job_state_history.add(history)

    def _store_error(self, job: dict, run: dict, result) -> None:
        code = (result.error_code or result.failure_class or "unknown")[:200]
        summary = (result.error_summary or "no summary")[:500]
        self.repos.db.conn.execute(
            "UPDATE job_runs SET error_code=?, error_summary=? WHERE id=?",
            (code, summary, run["id"]))
        self.repos.db.conn.commit()

    def _persist_output(self, job: dict, run: dict, result) -> None:
        if result.output is None:
            ref = None
        else:
            ref = f"job/{job['id']}/runs/{run['run_id']}/output"
        self.repos.db.conn.execute(
            "UPDATE job_runs SET output_reference=? WHERE id=?",
            (ref, run["id"]))
        self.repos.db.conn.commit()

    def _cancellation_requested(self, job: dict) -> bool:
        return self._job_state(job) == JobState.CANCEL_REQUESTED.value

    def _require_active_membership(self, org_id: str, user_id: str) -> dict:
        rows = self.repos.memberships.list(
            where={"organization_id": org_id, "user_id": user_id})
        active = [m for m in rows if (m.get("status") or "active") == "active"]
        if not active:
            raise JobValidationError(
                "membership_inactive", "no active membership in this organization")
        return active[0]

    def _owned_job(self, ctx: RequestContext, job_id: str) -> dict:
        org_id = ctx.effective_organization_id
        if not org_id:
            raise JobValidationError("no_organization", "organization required")
        job = self.repos.job_requests.get(job_id)
        if not job or job["organization_id"] != org_id:
            raise JobValidationError("not_found", "job not found", job_id=job_id)
        member = self._require_active_membership(org_id, ctx.user_id or "")
        role = member["role"]
        if role not in (Role.ORGANIZATION_OWNER.value,
                        Role.ORGANIZATION_ADMIN.value, Role.OPERATOR.value,
                        Role.INTERNAL_PLATFORM_ADMIN.value):
            raise JobValidationError("permission_denied", "cannot manage jobs")
        return job

    @staticmethod
    def _is_preview_job(job: dict) -> bool:
        prov = job.get("provenance")
        if isinstance(prov, str):
            try:
                prov = json.loads(prov)
            except (ValueError, TypeError):
                prov = {}
        return bool(prov and prov.get("preview"))

    def _job_view(self, job: dict, ctx: Optional[RequestContext] = None) -> dict:
        runs = self.repos.job_runs.by_request(job["id"])
        return {
            "id": job["id"],
            "organization_id": job["organization_id"],
            "user_id": job["user_id"],
            "service": job.get("service"),
            "job_type": job.get("job_type"),
            "payload_schema_version": job.get("payload_schema_version"),
            "state": job.get("state"),
            "priority": job.get("priority"),
            "requires_approval": bool(job.get("requires_approval")),
            "approval_id": job.get("approval_id"),
            "provider_class": job.get("provider_class"),
            "budget_class": job.get("budget_class"),
            "estimated_cost": _dec(job.get("estimated_cost")),
            "idempotency_key": job.get("idempotency_key"),
            "correlation_id": job.get("correlation_id"),
            "parent_job_id": job.get("parent_job_id"),
            "environment": job.get("environment"),
            "created_at": job.get("created_at"),
            "runs": [self._run_view(r, job) for r in runs],
            "approval_required": bool(job.get("requires_approval")),
        }

    @staticmethod
    def _run_view(run: dict, job: Optional[dict] = None) -> dict:
        return {
            "id": run["id"],
            "run_id": run.get("run_id"),
            "job_request_id": run.get("job_request_id"),
            "state": run.get("state"),
            "attempts": run.get("attempts"),
            "max_attempts": run.get("max_attempts"),
            "priority": run.get("priority"),
            "reserved_cost": _dec(run.get("reserved_cost")),
            "actual_cost": _dec(run.get("actual_cost")),
            "lease_owner": run.get("lease_owner"),
            "lease_expiration": run.get("lease_expiration"),
            "heartbeat_time": run.get("heartbeat_time"),
            "scheduled_time": run.get("scheduled_time"),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "output_reference": run.get("output_reference"),
            "error_code": run.get("error_code"),
            "error_summary": run.get("error_summary"),
            "correlation_id": run.get("correlation_id"),
        }

    @staticmethod
    def _history_view(h: dict) -> dict:
        return {
            "job_id": h.get("job_id"), "run_id": h.get("run_id"),
            "previous_state": h.get("previous_state"),
            "new_state": h.get("new_state"), "actor": h.get("actor"),
            "reason": h.get("reason"), "correlation_id": h.get("correlation_id"),
            "audit_event_ref": h.get("audit_event_ref"),
            "occurred_at": h.get("occurred_at"),
        }

    def _balance_view(self, org_id: str) -> dict:
        bal = self._balance(org_id)
        return {"organization_id": org_id,
                "granted": str(bal.granted), "reserved": str(bal.reserved),
                "consumed": str(bal.consumed), "available": str(bal.available)}


class HandlerResultFallback:
    """Generic failure classification for exceptions raised by handlers."""

    ok = False
    output = None
    failure_class = "unknown"
    error_code = "handler_exception"
    error_summary = "handler raised an unexpected exception"
    actual_cost = Decimal("0.00")
    retryable = True
    output_reference = None

    def __init__(self, exc: Exception) -> None:
        self.error_summary = f"handler raised {type(exc).__name__}"


class _VarResult:
    """Result shape for the cost-variance guard (not a real handler result)."""

    ok = False
    output = None
    failure_class = "budget_variance"
    error_code = "budget_variance"
    error_summary = "actual cost exceeded policy variance"
    actual_cost = Decimal("0.00")
    retryable = False
    output_reference = None

    def __init__(self, actual: Decimal, estimated: Decimal) -> None:
        self.actual_cost = actual
        self.error_summary = (f"actual cost {actual} exceeds estimate {estimated} "
                              "beyond policy variance")


def _as_dict(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _event_dict(event) -> dict:
    """Dataclass -> row dict for insert_no_commit (transactional ledger writes)."""
    return asdict(event)


def _role_has(role: str, permission: str) -> bool:
    from .permissions import has_permission
    return has_permission(role, permission)