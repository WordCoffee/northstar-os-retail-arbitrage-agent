"""Job foundation tests (owner decision 4)."""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.jobs import JobOrchestrator, BudgetExceeded
from Northstar_backend.foundation.models import JobRequest
from Northstar_backend.foundation.enums import JobState, FailureClass


def _mk_request(state, **kw):
    defaults = dict(organization_id=state.ids["org"], user_id=state.ids["user"],
                    service="prospector", environment="sandbox")
    defaults.update(kw)
    return JobRequest(**defaults)


def test_job_request_idempotency(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    a = jobs.request_job(_mk_request(seeded_state, idempotency_key="j1"))
    b = jobs.request_job(_mk_request(seeded_state, idempotency_key="j1"))
    assert a["id"] == b["id"]
    assert seeded_state.repos.job_requests.count() == 1


def test_state_machine_valid_transitions(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state))
    run = jobs.create_run(req["id"])
    jobs.transition(run["id"], JobState.RUNNING.value)
    jobs.transition(run["id"], JobState.SUCCEEDED.value)
    got = seeded_state.repos.job_runs.get(run["id"])
    assert got["state"] == JobState.SUCCEEDED.value


def test_state_machine_rejects_illegal_transition(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state))
    run = jobs.create_run(req["id"])
    with pytest.raises(ValueError):
        jobs.transition(run["id"], JobState.SUCCEEDED.value)  # queued -> succeeded illegal


def test_retry_exhaustion_dead_letters(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state))
    run = jobs.create_run(req["id"])
    # follow the legal retry cycle: queued -> running -> retry_scheduled -> queued
    jobs.transition(run["id"], JobState.RUNNING.value)
    for _ in range(3):
        jobs.transition(run["id"], JobState.RETRY_SCHEDULED.value)
        cur = seeded_state.repos.job_runs.get(run["id"])["state"]
        if cur == JobState.RETRY_SCHEDULED.value:
            jobs.transition(run["id"], JobState.QUEUED.value)
            jobs.transition(run["id"], JobState.RUNNING.value)
    got = seeded_state.repos.job_runs.get(run["id"])
    assert got["state"] == JobState.DEAD_LETTER.value


def test_budget_ceiling_enforced(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state, max_estimated_cost=1.0))
    result = jobs.execute_fixture(req["id"], lambda r: (5.0, True))
    assert result.state == JobState.FAILED.value
    assert result.failure_class == FailureClass.BUDGET_EXCEEDED.value


def test_fixture_execution_success(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state, max_estimated_cost=10.0))
    result = jobs.execute_fixture(req["id"], lambda r: (0.0, True))
    assert result.state == JobState.SUCCEEDED.value
    assert result.estimated_cost == 0.0


def test_fixture_execution_failure_classified(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state))
    result = jobs.execute_fixture(req["id"], lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    assert result.state == JobState.FAILED.value
    assert result.failure_class == FailureClass.UNKNOWN.value


def test_cancel_run(seeded_state):
    jobs = JobOrchestrator(seeded_state.repos)
    req = jobs.request_job(_mk_request(seeded_state))
    run = jobs.create_run(req["id"])
    jobs.cancel(run["id"])
    got = seeded_state.repos.job_runs.get(run["id"])
    assert got["state"] == JobState.CANCELLED.value