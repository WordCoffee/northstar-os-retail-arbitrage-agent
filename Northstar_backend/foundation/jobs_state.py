"""Authoritative job state machine (Phase 1C-04 / Workstream B).

Single source of truth for every legal job-state transition. Pure and
deterministic: no I/O, no database, no network. Persistence and audit emission
live in the job service/worker, which call :func:`transition` and store the
returned evidence.

States (canonical, 1C-04):

- DRAFT                    — created but not submitted for execution.
- PENDING_APPROVAL         — submitted; approval is required and outstanding.
- QUEUED                   — eligible for atomic claiming by a worker.
- LEASED                   — claimed by exactly one worker (lease owner set).
- RUNNING                  — a worker is executing the registered handler.
- RETRY_WAIT               — transient failure; waiting on backoff before re-queue.
- SUCCEEDED                — terminal; handler completed.
- FAILED                   — permanent failure (or failed without retry).
- CANCEL_REQUESTED         — cooperative cancellation requested of a running/leased job.
- CANCELLED                — terminal; cancelled.
- DEAD_LETTER              — terminal; retries exhausted / moved to DLQ.
- EXPIRED                  — lease expired beyond recovery.
- BLOCKED_BUDGET           — blocked by a budget/usage recheck.
- BLOCKED_PROVIDER         — blocked by a provider recheck.
- BLOCKED_AUTHORIZATION    — blocked by an authorization/approval recheck.

The legacy ``enums.JobState`` (requested/queued/running/...) belongs to the
Phase 1B fixture orchestrator and is deliberately NOT extended. This module is
the authoritative machine for 1C-04 durable execution.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


class JobState(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    QUEUED = "queued"
    LEASED = "leased"
    RUNNING = "running"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCEL_REQUESTED = "cancel_requested"
    CANCELLED = "cancelled"
    DEAD_LETTER = "dead_letter"
    EXPIRED = "expired"
    BLOCKED_BUDGET = "blocked_budget"
    BLOCKED_PROVIDER = "blocked_provider"
    BLOCKED_AUTHORIZATION = "blocked_authorization"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class JobActor(str, enum.Enum):
    """Actors permitted to move a job between states."""

    REQUESTOR = "requestor"
    APPROVER = "approver"
    WORKER = "worker"
    SCHEDULER = "scheduler"
    RECOVERY = "recovery"
    OPERATOR = "operator"
    SYSTEM = "system"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


ALL_STATES = frozenset(s.value for s in JobState)
ALL_ACTORS = frozenset(a.value for a in JobActor)


# ---------------------------------------------------------------------------
# Transition table: previous state -> allowed next states
# ---------------------------------------------------------------------------

LEGAL_TRANSITIONS: dict[str, set[str]] = {
    JobState.DRAFT.value: {
        JobState.PENDING_APPROVAL.value,
        JobState.QUEUED.value,
        JobState.CANCELLED.value,
    },
    JobState.PENDING_APPROVAL.value: {
        JobState.QUEUED.value,
        JobState.DRAFT.value,
        JobState.BLOCKED_AUTHORIZATION.value,
        JobState.CANCELLED.value,
    },
    JobState.QUEUED.value: {
        JobState.LEASED.value,
        JobState.CANCELLED.value,
        JobState.BLOCKED_BUDGET.value,
        JobState.BLOCKED_PROVIDER.value,
        JobState.BLOCKED_AUTHORIZATION.value,
    },
    JobState.LEASED.value: {
        JobState.RUNNING.value,
        JobState.QUEUED.value,
        JobState.CANCEL_REQUESTED.value,
        JobState.EXPIRED.value,
        JobState.BLOCKED_BUDGET.value,
        JobState.BLOCKED_PROVIDER.value,
        JobState.BLOCKED_AUTHORIZATION.value,
    },
    JobState.RUNNING.value: {
        JobState.SUCCEEDED.value,
        JobState.RETRY_WAIT.value,
        JobState.FAILED.value,
        JobState.DEAD_LETTER.value,
        JobState.CANCEL_REQUESTED.value,
        JobState.EXPIRED.value,
        JobState.BLOCKED_BUDGET.value,
    },
    JobState.RETRY_WAIT.value: {
        JobState.QUEUED.value,
        JobState.CANCELLED.value,
        JobState.BLOCKED_BUDGET.value,
        JobState.BLOCKED_PROVIDER.value,
        JobState.BLOCKED_AUTHORIZATION.value,
    },
    JobState.CANCEL_REQUESTED.value: {
        JobState.CANCELLED.value,
    },
    JobState.EXPIRED.value: {
        JobState.QUEUED.value,
        JobState.CANCELLED.value,
        JobState.DEAD_LETTER.value,
    },
    JobState.FAILED.value: {
        JobState.QUEUED.value,
        JobState.DEAD_LETTER.value,
        JobState.CANCELLED.value,
    },
    JobState.DEAD_LETTER.value: {
        JobState.QUEUED.value,  # authorized operator manual retry (new run)
    },
    JobState.SUCCEEDED.value: set(),    # terminal
    JobState.CANCELLED.value: set(),    # terminal
    JobState.BLOCKED_BUDGET.value: {
        JobState.QUEUED.value,
        JobState.RETRY_WAIT.value,
        JobState.CANCELLED.value,
    },
    JobState.BLOCKED_PROVIDER.value: {
        JobState.QUEUED.value,
        JobState.RETRY_WAIT.value,
        JobState.CANCELLED.value,
    },
    JobState.BLOCKED_AUTHORIZATION.value: {
        JobState.QUEUED.value,
        JobState.RETRY_WAIT.value,
        JobState.CANCELLED.value,
    },
}


# ---------------------------------------------------------------------------
# State classes
# ---------------------------------------------------------------------------

TERMINAL_STATES = frozenset({
    JobState.SUCCEEDED.value,
    JobState.CANCELLED.value,
    JobState.DEAD_LETTER.value,
})

# Cancellation is terminal FOR THE WORKER: once a cancel request is recorded the
# worker must stop and acknowledge it, so a handler that finished successfully
# can never drive ``cancel_requested -> succeeded``. The only transition a
# worker may still make out of CANCEL_REQUESTED is the acknowledgement to
# CANCELLED (the operator may also drive that acknowledgement).
WORKER_TERMINAL_STATES = TERMINAL_STATES | frozenset({
    JobState.CANCEL_REQUESTED.value,
})

RETRYABLE_STATES = frozenset({
    JobState.RETRY_WAIT.value,
    JobState.FAILED.value,
    JobState.EXPIRED.value,
    JobState.BLOCKED_BUDGET.value,
    JobState.BLOCKED_PROVIDER.value,
    JobState.BLOCKED_AUTHORIZATION.value,
})

CANCELLABLE_STATES = frozenset({
    JobState.DRAFT.value,
    JobState.PENDING_APPROVAL.value,
    JobState.QUEUED.value,
    JobState.LEASED.value,
    JobState.RUNNING.value,
    JobState.RETRY_WAIT.value,
    JobState.EXPIRED.value,
    JobState.FAILED.value,
    JobState.BLOCKED_BUDGET.value,
    JobState.BLOCKED_PROVIDER.value,
    JobState.BLOCKED_AUTHORIZATION.value,
})

LEASE_REQUIRED_STATES = frozenset({
    JobState.LEASED.value,
    JobState.RUNNING.value,
})

BLOCKED_STATES = frozenset({
    JobState.BLOCKED_BUDGET.value,
    JobState.BLOCKED_PROVIDER.value,
    JobState.BLOCKED_AUTHORIZATION.value,
})

# Transitions that require a granted approval before they may occur.
APPROVAL_REQUIRED_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value),
})


# ---------------------------------------------------------------------------
# Actor policy: which actors may drive each transition
# ---------------------------------------------------------------------------

_OPERATORS = {JobActor.REQUESTOR.value, JobActor.OPERATOR.value}
_WORKERS = {JobActor.WORKER.value, JobActor.SYSTEM.value}

ALLOWED_ACTORS: dict[tuple[str, str], set[str]] = {
    # draft lifecycle
    (JobState.DRAFT.value, JobState.PENDING_APPROVAL.value): {JobActor.REQUESTOR.value},
    (JobState.DRAFT.value, JobState.QUEUED.value): {JobActor.REQUESTOR.value},
    (JobState.DRAFT.value, JobState.CANCELLED.value): _OPERATORS,
    # approval lifecycle
    (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value): {JobActor.APPROVER.value},
    (JobState.PENDING_APPROVAL.value, JobState.DRAFT.value): {JobActor.APPROVER.value},
    (JobState.PENDING_APPROVAL.value, JobState.BLOCKED_AUTHORIZATION.value):
        {JobActor.SYSTEM.value},
    (JobState.PENDING_APPROVAL.value, JobState.CANCELLED.value): _OPERATORS,
    # queue lifecycle
    (JobState.QUEUED.value, JobState.LEASED.value): {JobActor.WORKER.value},
    (JobState.QUEUED.value, JobState.CANCELLED.value): _OPERATORS,
    (JobState.QUEUED.value, JobState.BLOCKED_BUDGET.value): _WORKERS,
    (JobState.QUEUED.value, JobState.BLOCKED_PROVIDER.value): _WORKERS,
    (JobState.QUEUED.value, JobState.BLOCKED_AUTHORIZATION.value): _WORKERS,
    # lease lifecycle
    (JobState.LEASED.value, JobState.RUNNING.value): {JobActor.WORKER.value},
    (JobState.LEASED.value, JobState.QUEUED.value): {JobActor.WORKER.value},
    (JobState.LEASED.value, JobState.CANCEL_REQUESTED.value): _OPERATORS,
    (JobState.LEASED.value, JobState.EXPIRED.value):
        {JobActor.RECOVERY.value, JobActor.SYSTEM.value},
    (JobState.LEASED.value, JobState.BLOCKED_BUDGET.value): _WORKERS,
    (JobState.LEASED.value, JobState.BLOCKED_PROVIDER.value): _WORKERS,
    (JobState.LEASED.value, JobState.BLOCKED_AUTHORIZATION.value): _WORKERS,
    # run lifecycle
    (JobState.RUNNING.value, JobState.SUCCEEDED.value): {JobActor.WORKER.value},
    (JobState.RUNNING.value, JobState.RETRY_WAIT.value): {JobActor.WORKER.value},
    (JobState.RUNNING.value, JobState.FAILED.value): {JobActor.WORKER.value},
    (JobState.RUNNING.value, JobState.DEAD_LETTER.value): {JobActor.WORKER.value},
    (JobState.RUNNING.value, JobState.CANCEL_REQUESTED.value): _OPERATORS,
    (JobState.RUNNING.value, JobState.EXPIRED.value):
        {JobActor.RECOVERY.value, JobActor.SYSTEM.value},
    (JobState.RUNNING.value, JobState.BLOCKED_BUDGET.value): {JobActor.WORKER.value},
    # retry wait lifecycle
    (JobState.RETRY_WAIT.value, JobState.QUEUED.value):
        {JobActor.SCHEDULER.value, JobActor.WORKER.value},
    (JobState.RETRY_WAIT.value, JobState.CANCELLED.value): _OPERATORS,
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_BUDGET.value): _WORKERS,
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_PROVIDER.value): _WORKERS,
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_AUTHORIZATION.value): _WORKERS,
    # cooperative cancellation
    (JobState.CANCEL_REQUESTED.value, JobState.CANCELLED.value):
        {JobActor.WORKER.value, JobActor.OPERATOR.value},
    # lease recovery
    (JobState.LEASED.value, JobState.EXPIRED.value):
        {JobActor.RECOVERY.value, JobActor.SYSTEM.value},
    (JobState.RUNNING.value, JobState.EXPIRED.value):
        {JobActor.RECOVERY.value, JobActor.SYSTEM.value},
    (JobState.EXPIRED.value, JobState.QUEUED.value):
        {JobActor.RECOVERY.value},
    (JobState.EXPIRED.value, JobState.CANCELLED.value): {JobActor.OPERATOR.value},
    (JobState.EXPIRED.value, JobState.DEAD_LETTER.value): {JobActor.RECOVERY.value},
    # failure / dead-letter
    (JobState.FAILED.value, JobState.QUEUED.value): {JobActor.OPERATOR.value},
    (JobState.FAILED.value, JobState.DEAD_LETTER.value):
        {JobActor.WORKER.value, JobActor.SYSTEM.value},
    (JobState.FAILED.value, JobState.CANCELLED.value): {JobActor.OPERATOR.value},
    (JobState.DEAD_LETTER.value, JobState.QUEUED.value): {JobActor.OPERATOR.value},
    # blocked states
    (JobState.BLOCKED_BUDGET.value, JobState.QUEUED.value):
        {JobActor.WORKER.value, JobActor.RECOVERY.value, JobActor.OPERATOR.value},
    (JobState.BLOCKED_BUDGET.value, JobState.RETRY_WAIT.value):
        {JobActor.SCHEDULER.value, JobActor.SYSTEM.value},
    (JobState.BLOCKED_BUDGET.value, JobState.CANCELLED.value): {JobActor.OPERATOR.value},
    (JobState.BLOCKED_PROVIDER.value, JobState.QUEUED.value):
        {JobActor.WORKER.value, JobActor.RECOVERY.value, JobActor.OPERATOR.value},
    (JobState.BLOCKED_PROVIDER.value, JobState.RETRY_WAIT.value):
        {JobActor.SCHEDULER.value, JobActor.SYSTEM.value},
    (JobState.BLOCKED_PROVIDER.value, JobState.CANCELLED.value): {JobActor.OPERATOR.value},
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.QUEUED.value):
        {JobActor.WORKER.value, JobActor.RECOVERY.value, JobActor.OPERATOR.value},
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.RETRY_WAIT.value):
        {JobActor.SCHEDULER.value, JobActor.SYSTEM.value},
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.CANCELLED.value):
        {JobActor.OPERATOR.value},
}


# ---------------------------------------------------------------------------
# Reason policy: transitions that REQUIRE an explicit reason / evidence
# ---------------------------------------------------------------------------

REQUIRED_REASON_TRANSITIONS: frozenset[tuple[str, str]] = frozenset({
    # approval
    (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value),
    (JobState.PENDING_APPROVAL.value, JobState.DRAFT.value),
    (JobState.PENDING_APPROVAL.value, JobState.BLOCKED_AUTHORIZATION.value),
    # cancellations
    (JobState.DRAFT.value, JobState.CANCELLED.value),
    (JobState.PENDING_APPROVAL.value, JobState.CANCELLED.value),
    (JobState.QUEUED.value, JobState.CANCELLED.value),
    (JobState.LEASED.value, JobState.CANCEL_REQUESTED.value),
    (JobState.RUNNING.value, JobState.CANCEL_REQUESTED.value),
    (JobState.CANCEL_REQUESTED.value, JobState.CANCELLED.value),
    (JobState.RETRY_WAIT.value, JobState.CANCELLED.value),
    (JobState.EXPIRED.value, JobState.CANCELLED.value),
    (JobState.FAILED.value, JobState.CANCELLED.value),
    # failures / retries
    (JobState.RUNNING.value, JobState.RETRY_WAIT.value),
    (JobState.RUNNING.value, JobState.FAILED.value),
    (JobState.RUNNING.value, JobState.DEAD_LETTER.value),
    (JobState.FAILED.value, JobState.QUEUED.value),
    (JobState.FAILED.value, JobState.DEAD_LETTER.value),
    (JobState.DEAD_LETTER.value, JobState.QUEUED.value),
    # lease expiry
    (JobState.LEASED.value, JobState.EXPIRED.value),
    (JobState.RUNNING.value, JobState.EXPIRED.value),
    (JobState.EXPIRED.value, JobState.QUEUED.value),
    (JobState.EXPIRED.value, JobState.DEAD_LETTER.value),
    # blocks
    (JobState.QUEUED.value, JobState.BLOCKED_BUDGET.value),
    (JobState.QUEUED.value, JobState.BLOCKED_PROVIDER.value),
    (JobState.QUEUED.value, JobState.BLOCKED_AUTHORIZATION.value),
    (JobState.LEASED.value, JobState.BLOCKED_BUDGET.value),
    (JobState.LEASED.value, JobState.BLOCKED_PROVIDER.value),
    (JobState.LEASED.value, JobState.BLOCKED_AUTHORIZATION.value),
    (JobState.RUNNING.value, JobState.BLOCKED_BUDGET.value),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_BUDGET.value),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_PROVIDER.value),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_AUTHORIZATION.value),
    (JobState.BLOCKED_BUDGET.value, JobState.QUEUED.value),
    (JobState.BLOCKED_PROVIDER.value, JobState.QUEUED.value),
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.QUEUED.value),
})


# ---------------------------------------------------------------------------
# Structured errors
# ---------------------------------------------------------------------------

class JobStateError(RuntimeError):
    """Raised for any illegal or incomplete transition request.

    ``code`` is a stable machine-readable reason:

    - unknown_state
    - illegal_transition
    - actor_not_allowed
    - reason_required
    - terminal_state
    """

    def __init__(self, code: str, message: str = "", *,
                 job_id: Optional[str] = None, run_id: Optional[str] = None,
                 previous_state: Optional[str] = None,
                 attempted_state: Optional[str] = None,
                 actor: Optional[str] = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.job_id = job_id
        self.run_id = run_id
        self.previous_state = previous_state
        self.attempted_state = attempted_state
        self.actor = actor


# ---------------------------------------------------------------------------
# Transition evidence
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class JobTransition:
    """Immutable evidence record emitted by :func:`transition`."""

    job_id: str
    previous_state: str
    new_state: str
    actor: str
    timestamp: str
    reason: Optional[str] = None
    run_id: Optional[str] = None
    correlation_id: Optional[str] = None
    audit_event_ref: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "actor": self.actor,
            "timestamp": self.timestamp,
            "reason": self.reason,
            "correlation_id": self.correlation_id,
            "audit_event_ref": self.audit_event_ref,
        }


# ---------------------------------------------------------------------------
# Pure predicates
# ---------------------------------------------------------------------------

def is_terminal(state: str) -> bool:
    return state in TERMINAL_STATES


def is_worker_terminal(state: str) -> bool:
    """True when a worker must stop driving a job.

    Terminal states are finished; CANCEL_REQUESTED is terminal for the worker
    because a pending cancellation wins over the handler's own outcome. A
    worker may only acknowledge that state (CANCEL_REQUESTED -> CANCELLED).
    """
    return state in WORKER_TERMINAL_STATES


def is_cancellable(state: str) -> bool:
    return state in CANCELLABLE_STATES


def is_retryable(state: str) -> bool:
    return state in RETRYABLE_STATES


def is_lease_required(state: str) -> bool:
    return state in LEASE_REQUIRED_STATES


def is_blocked(state: str) -> bool:
    return state in BLOCKED_STATES


def requires_approval(previous: str, new: str) -> bool:
    return (previous, new) in APPROVAL_REQUIRED_TRANSITIONS


def can_transition(previous: str, new: str) -> bool:
    if previous not in ALL_STATES or new not in ALL_STATES:
        return False
    return new in LEGAL_TRANSITIONS.get(previous, set())


def _coerce_state(value: object) -> str:
    if isinstance(value, JobState):
        return value.value
    if isinstance(value, str):
        if value not in ALL_STATES:
            raise JobStateError("unknown_state", f"unknown job state {value!r}",
                                attempted_state=str(value))
        return value
    raise JobStateError("unknown_state", f"job state must be str, got {type(value).__name__}",
                        attempted_state=str(value))


def _coerce_actor(value: object) -> str:
    if isinstance(value, JobActor):
        return value.value
    if isinstance(value, str):
        if value not in ALL_ACTORS:
            raise JobStateError("unknown_state", f"unknown actor {value!r}",
                                actor=str(value))
        return value
    raise JobStateError("unknown_state", f"actor must be str, got {type(value).__name__}",
                        actor=str(value))


def transition(
    *,
    job_id: str,
    previous_state: object,
    new_state: object,
    actor: object,
    reason: Optional[str] = None,
    run_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    audit_event_ref: Optional[str] = None,
    timestamp: Optional[str] = None,
) -> JobTransition:
    """Authoritatively validate and emit a job-state transition.

    Raises :class:`JobStateError` on any illegal or incomplete request. Returns
    immutable evidence that callers must persist/emit.
    """
    prev = _coerce_state(previous_state)
    new = _coerce_state(new_state)
    act = _coerce_actor(actor)

    legal_next = LEGAL_TRANSITIONS.get(prev, set())
    if new not in legal_next:
        raise JobStateError(
            "illegal_transition",
            f"illegal transition {prev} -> {new}",
            job_id=job_id, run_id=run_id,
            previous_state=prev, attempted_state=new, actor=act,
        )

    allowed = ALLOWED_ACTORS.get((prev, new), set())
    if act not in allowed:
        raise JobStateError(
            "actor_not_allowed",
            f"actor {act!r} is not allowed for {prev} -> {new}",
            job_id=job_id, run_id=run_id,
            previous_state=prev, attempted_state=new, actor=act,
        )

    if (prev, new) in REQUIRED_REASON_TRANSITIONS and not reason:
        raise JobStateError(
            "reason_required",
            f"transition {prev} -> {new} requires a reason",
            job_id=job_id, run_id=run_id,
            previous_state=prev, attempted_state=new, actor=act,
        )

    ts = timestamp or datetime.now(timezone.utc).isoformat()
    return JobTransition(
        job_id=job_id,
        run_id=run_id,
        previous_state=prev,
        new_state=new,
        actor=act,
        reason=reason,
        correlation_id=correlation_id,
        audit_event_ref=audit_event_ref,
        timestamp=ts,
    )


def transition_metadata() -> dict:
    """Machine-readable summary of the full transition model (API/audit/docs)."""
    return {
        "states": sorted(ALL_STATES),
        "actors": sorted(ALL_ACTORS),
        "legal_transitions": sorted(
            f"{prev}:{new}" for prev in LEGAL_TRANSITIONS
            for new in LEGAL_TRANSITIONS[prev]),
        "terminal_states": sorted(TERMINAL_STATES),
        "worker_terminal_states": sorted(WORKER_TERMINAL_STATES),
        "retryable_states": sorted(RETRYABLE_STATES),
        "cancellable_states": sorted(CANCELLABLE_STATES),
        "lease_required_states": sorted(LEASE_REQUIRED_STATES),
        "blocked_states": sorted(BLOCKED_STATES),
        "approval_required_transitions": sorted(
            f"{p}:{n}" for p, n in APPROVAL_REQUIRED_TRANSITIONS),
        "reason_required_transitions": sorted(
            f"{p}:{n}" for p, n in REQUIRED_REASON_TRANSITIONS),
        "version": "jobs-state-1.0.0",
    }