"""Authoritative job state machine tests (1C-04 / B01).

Every legal transition is exercised; representative illegal transitions,
actor violations, reason violations, and unknown states are asserted. The
machine is pure and deterministic — no DB, no I/O.
"""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.jobs_state import (
    ALL_STATES,
    ALLOWED_ACTORS,
    APPROVAL_REQUIRED_TRANSITIONS,
    BLOCKED_STATES,
    CANCELLABLE_STATES,
    JobActor,
    JobState,
    JobStateError,
    LEASE_REQUIRED_STATES,
    LEGAL_TRANSITIONS,
    RETRYABLE_STATES,
    REQUIRED_REASON_TRANSITIONS,
    TERMINAL_STATES,
    can_transition,
    is_blocked,
    is_cancellable,
    is_lease_required,
    is_retryable,
    is_terminal,
    requires_approval,
    transition,
    transition_metadata,
)

JOB = "job-1"
RUN = "run-1"


# ---------------------------------------------------------------------------
# helper
# ---------------------------------------------------------------------------

def _do(previous, new, actor=JobActor.WORKER.value, reason="r", **kw):
    return transition(job_id=JOB, previous_state=previous, new_state=new,
                      actor=actor, reason=reason, run_id=RUN, **kw)


# ---------------------------------------------------------------------------
# state catalog
# ---------------------------------------------------------------------------

def test_all_required_states_present():
    required = [
        "draft", "pending_approval", "queued", "leased", "running",
        "retry_wait", "succeeded", "failed", "cancel_requested", "cancelled",
        "dead_letter", "expired", "blocked_budget", "blocked_provider",
        "blocked_authorization",
    ]
    assert sorted(required) == sorted(s.value for s in JobState)
    assert len(JobState) == 15


def test_every_state_is_declared_exactly_once():
    values = [s.value for s in JobState]
    assert len(values) == len(set(values))


# ---------------------------------------------------------------------------
# every legal transition
# ---------------------------------------------------------------------------

LEGAL_CASES = [
    # draft lifecycle
    (JobState.DRAFT.value, JobState.PENDING_APPROVAL.value, JobActor.REQUESTOR.value, "submit"),
    (JobState.DRAFT.value, JobState.QUEUED.value, JobActor.REQUESTOR.value, "submit"),
    (JobState.DRAFT.value, JobState.CANCELLED.value, JobActor.OPERATOR.value, "cancel"),
    # approval lifecycle
    (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value, JobActor.APPROVER.value, "granted"),
    (JobState.PENDING_APPROVAL.value, JobState.DRAFT.value, JobActor.APPROVER.value, "denied"),
    (JobState.PENDING_APPROVAL.value, JobState.BLOCKED_AUTHORIZATION.value,
     JobActor.SYSTEM.value, "approval expired"),
    (JobState.PENDING_APPROVAL.value, JobState.CANCELLED.value,
     JobActor.OPERATOR.value, "cancel"),
    # queue lifecycle
    (JobState.QUEUED.value, JobState.LEASED.value, JobActor.WORKER.value, "claim"),
    (JobState.QUEUED.value, JobState.CANCELLED.value, JobActor.OPERATOR.value, "cancel"),
    (JobState.QUEUED.value, JobState.BLOCKED_BUDGET.value, JobActor.WORKER.value, "budget"),
    (JobState.QUEUED.value, JobState.BLOCKED_PROVIDER.value, JobActor.WORKER.value, "provider"),
    (JobState.QUEUED.value, JobState.BLOCKED_AUTHORIZATION.value,
     JobActor.WORKER.value, "auth"),
    # lease lifecycle
    (JobState.LEASED.value, JobState.RUNNING.value, JobActor.WORKER.value, "start"),
    (JobState.LEASED.value, JobState.QUEUED.value, JobActor.WORKER.value, "release"),
    (JobState.LEASED.value, JobState.CANCEL_REQUESTED.value,
     JobActor.OPERATOR.value, "cancel"),
    (JobState.LEASED.value, JobState.EXPIRED.value,
     JobActor.RECOVERY.value, "lease expired"),
    (JobState.LEASED.value, JobState.BLOCKED_BUDGET.value, JobActor.WORKER.value, "budget"),
    (JobState.LEASED.value, JobState.BLOCKED_PROVIDER.value, JobActor.WORKER.value, "provider"),
    (JobState.LEASED.value, JobState.BLOCKED_AUTHORIZATION.value,
     JobActor.WORKER.value, "auth"),
    # run lifecycle
    (JobState.RUNNING.value, JobState.SUCCEEDED.value, JobActor.WORKER.value, "ok"),
    (JobState.RUNNING.value, JobState.RETRY_WAIT.value, JobActor.WORKER.value, "transient"),
    (JobState.RUNNING.value, JobState.FAILED.value, JobActor.WORKER.value, "permanent"),
    (JobState.RUNNING.value, JobState.DEAD_LETTER.value, JobActor.WORKER.value, "exhausted"),
    (JobState.RUNNING.value, JobState.CANCEL_REQUESTED.value,
     JobActor.OPERATOR.value, "cancel"),
    (JobState.RUNNING.value, JobState.EXPIRED.value,
     JobActor.SYSTEM.value, "lease expired"),
    (JobState.RUNNING.value, JobState.BLOCKED_BUDGET.value, JobActor.WORKER.value, "variance"),
    # retry wait
    (JobState.RETRY_WAIT.value, JobState.QUEUED.value, JobActor.SCHEDULER.value, "backoff"),
    (JobState.RETRY_WAIT.value, JobState.CANCELLED.value, JobActor.OPERATOR.value, "cancel"),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_BUDGET.value, JobActor.WORKER.value, "budget"),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_PROVIDER.value,
     JobActor.WORKER.value, "provider"),
    (JobState.RETRY_WAIT.value, JobState.BLOCKED_AUTHORIZATION.value,
     JobActor.WORKER.value, "auth"),
    # cooperative cancellation
    (JobState.CANCEL_REQUESTED.value, JobState.CANCELLED.value,
     JobActor.WORKER.value, "ack"),
    # lease recovery
    (JobState.EXPIRED.value, JobState.QUEUED.value, JobActor.RECOVERY.value, "reclaim"),
    (JobState.EXPIRED.value, JobState.CANCELLED.value, JobActor.OPERATOR.value, "cancel"),
    (JobState.EXPIRED.value, JobState.DEAD_LETTER.value, JobActor.RECOVERY.value, "exhausted"),
    # failure / dead-letter
    (JobState.FAILED.value, JobState.QUEUED.value, JobActor.OPERATOR.value, "retry"),
    (JobState.FAILED.value, JobState.DEAD_LETTER.value, JobActor.SYSTEM.value, "dlq"),
    (JobState.FAILED.value, JobState.CANCELLED.value, JobActor.OPERATOR.value, "cancel"),
    (JobState.DEAD_LETTER.value, JobState.QUEUED.value,
     JobActor.OPERATOR.value, "manual retry"),
    # blocked states
    (JobState.BLOCKED_BUDGET.value, JobState.QUEUED.value,
     JobActor.RECOVERY.value, "unblocked"),
    (JobState.BLOCKED_BUDGET.value, JobState.RETRY_WAIT.value,
     JobActor.SCHEDULER.value, "recheck"),
    (JobState.BLOCKED_BUDGET.value, JobState.CANCELLED.value,
     JobActor.OPERATOR.value, "cancel"),
    (JobState.BLOCKED_PROVIDER.value, JobState.QUEUED.value,
     JobActor.OPERATOR.value, "unblocked"),
    (JobState.BLOCKED_PROVIDER.value, JobState.RETRY_WAIT.value,
     JobActor.SYSTEM.value, "recheck"),
    (JobState.BLOCKED_PROVIDER.value, JobState.CANCELLED.value,
     JobActor.OPERATOR.value, "cancel"),
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.QUEUED.value,
     JobActor.WORKER.value, "unblocked"),
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.RETRY_WAIT.value,
     JobActor.SYSTEM.value, "recheck"),
    (JobState.BLOCKED_AUTHORIZATION.value, JobState.CANCELLED.value,
     JobActor.OPERATOR.value, "cancel"),
]


@pytest.mark.parametrize("prev,new,actor,reason", LEGAL_CASES)
def test_every_legal_transition(prev, new, actor, reason):
    ev = _do(prev, new, actor, reason)
    assert ev.previous_state == prev
    assert ev.new_state == new
    assert ev.actor == actor
    assert ev.reason == reason
    assert ev.run_id == RUN


def test_legal_transition_table_matches_parameterized_suite():
    """The parameterized suite covers every (prev,new) pair in the table."""
    declared = {(p, n) for p in LEGAL_TRANSITIONS for n in LEGAL_TRANSITIONS[p]}
    tested = {(p, n) for p, n, _a, _r in LEGAL_CASES}
    assert tested == declared


# ---------------------------------------------------------------------------
# representative illegal transitions
# ---------------------------------------------------------------------------

ILLEGAL_CASES = [
    (JobState.QUEUED.value, JobState.SUCCEEDED.value, JobActor.WORKER.value, "skip"),
    (JobState.DRAFT.value, JobState.RUNNING.value, JobActor.WORKER.value, "jump"),
    (JobState.DRAFT.value, JobState.LEASED.value, JobActor.WORKER.value, "jump"),
    (JobState.DRAFT.value, JobState.SUCCEEDED.value, JobActor.WORKER.value, "jump"),
    (JobState.QUEUED.value, JobState.RUNNING.value, JobActor.WORKER.value, "no-claim"),
    (JobState.RUNNING.value, JobState.CANCELLED.value, JobActor.WORKER.value, "direct"),
    (JobState.RETRY_WAIT.value, JobState.RUNNING.value, JobActor.WORKER.value, "jump"),
    (JobState.SUCCEEDED.value, JobState.QUEUED.value, JobActor.WORKER.value, "reopen"),
    (JobState.SUCCEEDED.value, JobState.RUNNING.value, JobActor.WORKER.value, "reopen"),
    (JobState.CANCELLED.value, JobState.QUEUED.value, JobActor.OPERATOR.value, "reopen"),
    (JobState.DEAD_LETTER.value, JobState.RUNNING.value, JobActor.WORKER.value, "in-place"),
    (JobState.DEAD_LETTER.value, JobState.SUCCEEDED.value, JobActor.WORKER.value, "in-place"),
    (JobState.LEASED.value, JobState.SUCCEEDED.value, JobActor.WORKER.value, "no-start"),
    (JobState.CANCEL_REQUESTED.value, JobState.RUNNING.value, JobActor.WORKER.value, "undo"),
    (JobState.BLOCKED_BUDGET.value, JobState.RUNNING.value, JobActor.WORKER.value, "jump"),
    (JobState.PENDING_APPROVAL.value, JobState.RUNNING.value, JobActor.APPROVER.value, "jump"),
]


@pytest.mark.parametrize("prev,new,actor,reason", ILLEGAL_CASES)
def test_illegal_transitions_raise(prev, new, actor, reason):
    with pytest.raises(JobStateError) as exc:
        _do(prev, new, actor, reason)
    assert exc.value.code == "illegal_transition"
    assert exc.value.previous_state == prev
    assert exc.value.attempted_state == new
    assert not can_transition(prev, new)


# ---------------------------------------------------------------------------
# terminal / retryable / cancellable / lease / blocked classifications
# ---------------------------------------------------------------------------

def test_terminal_states_are_absorbing():
    for s in TERMINAL_STATES:
        assert is_terminal(s)
        assert not is_cancellable(s)
        assert not is_retryable(s)
    # SUCCEEDED and CANCELLED are fully absorbing; DEAD_LETTER permits only the
    # authorized operator manual retry (new run).
    assert LEGAL_TRANSITIONS["succeeded"] == set()
    assert LEGAL_TRANSITIONS["cancelled"] == set()
    assert LEGAL_TRANSITIONS["dead_letter"] == {"queued"}


def test_terminal_states_exact_set():
    assert TERMINAL_STATES == frozenset(
        {"succeeded", "cancelled", "dead_letter"})


def test_retryable_states_exact_set():
    assert RETRYABLE_STATES == frozenset(
        {"retry_wait", "failed", "expired", "blocked_budget",
         "blocked_provider", "blocked_authorization"})


def test_cancellable_states_exact_set():
    non_cancellable = {"succeeded", "cancelled", "dead_letter", "cancel_requested"}
    assert CANCELLABLE_STATES == frozenset(ALL_STATES - non_cancellable)


def test_lease_required_states_exact_set():
    assert LEASE_REQUIRED_STATES == frozenset({"leased", "running"})


def test_blocked_states_exact_set():
    assert BLOCKED_STATES == frozenset(
        {"blocked_budget", "blocked_provider", "blocked_authorization"})


def test_is_helpers_agree():
    for s in ALL_STATES:
        assert is_blocked(s) == (s in BLOCKED_STATES)
        assert is_retryable(s) == (s in RETRYABLE_STATES)


# ---------------------------------------------------------------------------
# approval-required transitions
# ---------------------------------------------------------------------------

def test_approval_required_transition_defined():
    assert (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value) \
        in APPROVAL_REQUIRED_TRANSITIONS
    assert requires_approval(JobState.PENDING_APPROVAL.value,
                             JobState.QUEUED.value)
    assert not requires_approval(JobState.DRAFT.value, JobState.QUEUED.value)


def test_approval_grant_requires_approver_actor():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.PENDING_APPROVAL.value, JobState.QUEUED.value,
            JobActor.WORKER.value, "granted")
    assert exc.value.code == "actor_not_allowed"


# ---------------------------------------------------------------------------
# actor policy
# ---------------------------------------------------------------------------

def test_claim_requires_worker():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.QUEUED.value, JobState.LEASED.value,
            JobActor.REQUESTOR.value, "claim")
    assert exc.value.code == "actor_not_allowed"


def test_submit_requires_requestor():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.DRAFT.value, JobState.QUEUED.value,
            JobActor.WORKER.value, "submit")
    assert exc.value.code == "actor_not_allowed"


def test_success_requires_worker():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.RUNNING.value, JobState.SUCCEEDED.value,
            JobActor.OPERATOR.value, "ok")
    assert exc.value.code == "actor_not_allowed"


def test_manual_retry_requires_operator():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.FAILED.value, JobState.QUEUED.value,
            JobActor.WORKER.value, "retry")
    assert exc.value.code == "actor_not_allowed"


def test_dead_letter_manual_retry_requires_operator():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.DEAD_LETTER.value, JobState.QUEUED.value,
            JobActor.WORKER.value, "manual retry")
    assert exc.value.code == "actor_not_allowed"


def test_every_transition_has_an_actor_policy():
    for prev in LEGAL_TRANSITIONS:
        for new in LEGAL_TRANSITIONS[prev]:
            assert (prev, new) in ALLOWED_ACTORS, f"missing actor policy {prev}->{new}"


# ---------------------------------------------------------------------------
# reason policy
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prev,new,actor", [
    (JobState.PENDING_APPROVAL.value, JobState.QUEUED.value, JobActor.APPROVER.value),
    (JobState.QUEUED.value, JobState.CANCELLED.value, JobActor.OPERATOR.value),
    (JobState.RUNNING.value, JobState.FAILED.value, JobActor.WORKER.value),
    (JobState.RUNNING.value, JobState.RETRY_WAIT.value, JobActor.WORKER.value),
    (JobState.RUNNING.value, JobState.BLOCKED_BUDGET.value, JobActor.WORKER.value),
    (JobState.CANCEL_REQUESTED.value, JobState.CANCELLED.value, JobActor.WORKER.value),
])
def test_reason_required(prev, new, actor):
    with pytest.raises(JobStateError) as exc:
        _do(prev, new, actor, reason=None)
    assert exc.value.code == "reason_required"


def test_success_does_not_require_reason():
    ev = _do(JobState.RUNNING.value, JobState.SUCCEEDED.value,
             JobActor.WORKER.value, reason=None)
    assert ev.reason is None


def test_reason_required_table_is_declared():
    """Every declared reason-required transition must be exercised in the suite."""
    declared = set(REQUIRED_REASON_TRANSITIONS)
    exercised = {tuple(c[:2]) for c in LEGAL_CASES} & declared
    assert exercised == declared


# ---------------------------------------------------------------------------
# unknown / malformed inputs
# ---------------------------------------------------------------------------

def test_unknown_state_rejected():
    with pytest.raises(JobStateError) as exc:
        transition(job_id=JOB, previous_state="warp", new_state="queued",
                   actor=JobActor.WORKER.value)
    assert exc.value.code == "unknown_state"


def test_unknown_new_state_rejected():
    with pytest.raises(JobStateError) as exc:
        _do(JobState.QUEUED.value, "warp", JobActor.WORKER.value, "r")
    assert exc.value.code == "unknown_state"


def test_unknown_actor_rejected():
    with pytest.raises(JobStateError):
        _do(JobState.QUEUED.value, JobState.LEASED.value, "minion", "r")


def test_enum_members_and_strings_are_interchangeable():
    a = transition(job_id=JOB, previous_state=JobState.QUEUED,
                   new_state=JobState.LEASED, actor=JobActor.WORKER,
                   reason="r", run_id=RUN)
    b = transition(job_id=JOB, previous_state="queued", new_state="leased",
                   actor="worker", reason="r", run_id=RUN)
    assert a.new_state == b.new_state == "leased"


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------

def test_transition_evidence_shape():
    ev = _do(JobState.QUEUED.value, JobState.LEASED.value,
             JobActor.WORKER.value, "claim",
             correlation_id="corr-9", audit_event_ref="audit-1")
    d = ev.to_dict()
    assert d["job_id"] == JOB
    assert d["run_id"] == RUN
    assert d["previous_state"] == "queued"
    assert d["new_state"] == "leased"
    assert d["actor"] == "worker"
    assert d["reason"] == "claim"
    assert d["correlation_id"] == "corr-9"
    assert d["audit_event_ref"] == "audit-1"
    assert "T" in d["timestamp"] and d["timestamp"].endswith("+00:00")


def test_transition_evidence_immutable():
    ev = _do(JobState.QUEUED.value, JobState.LEASED.value,
             JobActor.WORKER.value, "claim")
    with pytest.raises(Exception):
        ev.new_state = "running"  # frozen dataclass


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------

def test_metadata_shape():
    m = transition_metadata()
    assert m["version"] == "jobs-state-1.0.0"
    assert set(m["states"]) == ALL_STATES
    assert set(m["terminal_states"]) == TERMINAL_STATES
    assert "queued:leased" in m["legal_transitions"]
    assert "pending_approval:queued" in m["approval_required_transitions"]
    assert "running:failed" in m["reason_required_transitions"]