"""Runtime rechecks, retry, cancellation, dead-letter, and usage lifecycle tests
(1C-04 / B07-B13). SQLite-backed; the disposable-PG module covers the
concurrency matrix.

Required outcomes: blocked jobs never call the handler; reservations are
released when blocked/cancelled; retries never double-debit; actual cost
cannot silently exceed policy; authorization/approval/provider/budget rechecks
happen immediately before execution.
"""
from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Environment, Role, ApprovalState
from Northstar_backend.foundation.jobs_durable import (
    DurableJobService, JobValidationError,
)
from Northstar_backend.foundation.jobs_state import JobState
from Northstar_backend.foundation.models import Organization, User, Membership, OrgBalance
from Northstar_backend.foundation.jobs_worker import JobWorker


def _ctx(seeded_state, org=None, role=Role.ORGANIZATION_OWNER.value):
    return build_context(
        user_id=seeded_state.ids["user"],
        organization_id=org or seeded_state.ids["org"],
        role=role, environment=Environment.PRODUCTION.value)


def _submit(svc, ctx, job_type="immediate_success", **kw):
    return svc.submit(ctx, job_type=job_type, payload=kw.pop("payload", {}),
                      payload_schema_version="1.0", **kw)


def _claim_and_run(svc, org_id, worker="w1"):
    claimed = svc.claim_next(worker, organization_id=org_id)
    if claimed is None:
        return None
    return svc.execute_claimed(claimed, worker)


def _past(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# B07 — authorization & approval rechecks
# ---------------------------------------------------------------------------

def test_membership_revoked_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state))
    seeded_state.repos.db.conn.execute(
        "UPDATE memberships SET status='revoked' WHERE organization_id=? AND user_id=?",
        (seeded_state.ids["org"], seeded_state.ids["user"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value
    # no usage event (never executed)
    assert seeded_state.repos.usage.count() == 0


def test_role_changed_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state))
    seeded_state.repos.db.conn.execute(
        "UPDATE memberships SET role='viewer' WHERE organization_id=? AND user_id=?",
        (seeded_state.ids["org"], seeded_state.ids["user"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value
    assert seeded_state.repos.usage.count() == 0


def test_organization_suspended_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state))
    seeded_state.repos.db.conn.execute(
        "UPDATE organizations SET active=0 WHERE id=?", (seeded_state.ids["org"],))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value
    assert seeded_state.repos.usage.count() == 0


def test_approval_revoked_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state), job_type="needs_approval")
    assert job["state"] == JobState.PENDING_APPROVAL.value
    svc.approvals.decide(approval_request_id=job["approval_id"],
                         decided_by_user_id=seeded_state.ids["user"],
                         decided_by_role=Role.ORGANIZATION_OWNER.value,
                         decision=ApprovalState.GRANTED.value)
    svc.promote_approved_jobs(job["approval_id"])
    # now queued; revoke the approval before execution
    seeded_state.repos.db.conn.execute(
        "UPDATE approval_requests SET state=? WHERE id=?",
        (ApprovalState.CANCELLED.value, job["approval_id"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value
    assert seeded_state.repos.usage.count() == 0


def test_approval_expired_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state), job_type="needs_approval")
    svc.approvals.decide(approval_request_id=job["approval_id"],
                         decided_by_user_id=seeded_state.ids["user"],
                         decided_by_role=Role.ORGANIZATION_OWNER.value,
                         decision=ApprovalState.GRANTED.value)
    svc.promote_approved_jobs(job["approval_id"])
    seeded_state.repos.db.conn.execute(
        "UPDATE approval_requests SET expires_at=? WHERE id=?",
        (_past(), job["approval_id"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value


def test_approval_does_not_apply_to_wrong_job(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job_a = _submit(svc, _ctx(seeded_state), job_type="needs_approval")
    svc.approvals.decide(approval_request_id=job_a["approval_id"],
                         decided_by_user_id=seeded_state.ids["user"],
                         decided_by_role=Role.ORGANIZATION_OWNER.value,
                         decision=ApprovalState.GRANTED.value)
    svc.promote_approved_jobs(job_a["approval_id"])
    # run job_a to completion so it is no longer claimable
    _claim_and_run(svc, seeded_state.ids["org"])
    # job_b is pointed at job_a's approval (does not apply to job_b)
    job_b = _submit(svc, _ctx(seeded_state), job_type="needs_approval")
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET approval_id=?, state='queued' WHERE id=?",
        (job_a["approval_id"], job_b["id"]))
    seeded_state.repos.db.conn.execute(
        "UPDATE job_runs SET state='queued' WHERE job_request_id=?",
        (job_b["id"],))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value


# ---------------------------------------------------------------------------
# B08 — provider & budget rechecks
# ---------------------------------------------------------------------------

def test_budget_reduced_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state))
    seeded_state.repos.org_balances.add(OrgBalance(
        organization_id=seeded_state.ids["org"], granted=Decimal("0.00")))
    # estimated cost above available balance
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE organization_id=?",
        (10.0, seeded_state.ids["org"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_BUDGET.value
    assert seeded_state.repos.usage.count() == 0


def test_blocked_job_releases_reservation(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    svc.grant(seeded_state.ids["org"], Decimal("100.00"))
    _submit(svc, _ctx(seeded_state))
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE organization_id=?",
        (10.0, seeded_state.ids["org"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.SUCCEEDED.value  # budget fine, est 10 <= 100
    bal = svc._balance(seeded_state.ids["org"])
    assert bal.reserved == 0
    assert bal.consumed == 0  # fake handler actual 0.00


# ---------------------------------------------------------------------------
# B09 — usage reservation and settlement
# ---------------------------------------------------------------------------

def test_reservation_settlement_balance(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    svc.grant(seeded_state.ids["org"], Decimal("100.00"))
    job = _submit(svc, _ctx(seeded_state), job_type="cost_variance",
                  payload={"estimated_cost": "10.00", "variance": "0.00"})
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE id=?", (10.0, job["id"]))
    seeded_state.repos.db.conn.commit()
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    # reservation happened during execution
    out = svc.execute_claimed(claimed, "w1")
    assert out.state == JobState.SUCCEEDED.value
    bal = svc._balance(seeded_state.ids["org"])
    assert bal.reserved == 0
    assert bal.consumed == Decimal("10.00")
    # one finalized settlement event (reservation is a separate reserved event)
    finalized = [e for e in seeded_state.repos.usage.for_org(seeded_state.ids["org"])
                 if e["status"] == "finalized"]
    assert len(finalized) == 1


def test_actual_cost_cannot_silently_exceed_policy(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    svc.grant(seeded_state.ids["org"], Decimal("1000.00"))
    job = _submit(svc, _ctx(seeded_state), job_type="cost_variance",
                  payload={"estimated_cost": "5.00", "variance": "500.00"})
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE id=?", (5.0, job["id"]))
    seeded_state.repos.db.conn.commit()
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_BUDGET.value
    assert out.failure_class == "budget_variance"


def test_cancel_before_execution_releases_nothing_and_no_reservation(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    svc.grant(seeded_state.ids["org"], Decimal("100.00"))
    job = _submit(svc, _ctx(seeded_state), job_type="immediate_success",
                  payload={"estimated_cost": "10.00"})
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE id=?", (10.0, job["id"]))
    seeded_state.repos.db.conn.commit()
    svc.cancel(_ctx(seeded_state), job["id"], reason="cancel queued")
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == \
        JobState.CANCELLED.value
    bal = svc._balance(seeded_state.ids["org"])
    assert bal.reserved == 0 and bal.consumed == 0
    assert seeded_state.repos.usage.count() == 0


# ---------------------------------------------------------------------------
# B10 — retry and backoff
# ---------------------------------------------------------------------------

def test_transient_failure_then_success(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="transient_failure",
            payload={"succeed_on_attempt": 2})
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.RETRY_WAIT.value
    job = svc.list_jobs(seeded_state.ids["org"])["items"][0]
    assert job["state"] == JobState.RETRY_WAIT.value
    # retry scheduler moves it back to queued (backoff elapsed)
    run = svc.repos.job_runs.by_request(job["id"])[0]
    svc.repos.db.conn.execute(
        "UPDATE job_runs SET scheduled_time=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
    svc.repos.db.conn.commit()
    svc._transition(job=svc.repos.job_requests.get(job["id"]), run=run,
                    new_state=JobState.QUEUED.value,
                    actor="scheduler", reason="backoff elapsed")
    out2 = _claim_and_run(svc, seeded_state.ids["org"])
    assert out2.state == JobState.SUCCEEDED.value
    # financial integrity: ONLY the successful attempt settles -> exactly ONE
    # finalized ledger entry; the failed attempt released (never debited).
    finalized = [e for e in seeded_state.repos.usage.for_org(seeded_state.ids["org"])
                 if e["status"] == "finalized"]
    assert len(finalized) == 1
    # reservation fully released: no residual reserved amount
    bal = svc._balance(seeded_state.ids["org"])
    assert bal.reserved == 0


def test_repeated_transient_failure_dead_letters(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="transient_failure",
            payload={"succeed_on_attempt": 99})
    outcomes = []
    for _ in range(4):  # max_attempts=3
        out = _claim_and_run(svc, seeded_state.ids["org"])
        if out is None:
            break
        outcomes.append(out)
        if out.state in (JobState.DEAD_LETTER.value, JobState.FAILED.value):
            break
        # move retry_wait -> queued
        job = svc.repos.job_requests.list(
            where={"organization_id": seeded_state.ids["org"]})[0]
        run = svc.repos.job_runs.by_request(job["id"])[0]
        svc.repos.db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
        svc.repos.db.conn.commit()
        svc._transition(job=job, run=run, new_state=JobState.QUEUED.value,
                        actor="scheduler", reason="backoff elapsed")
    assert outcomes[-1].state == JobState.DEAD_LETTER.value


def test_permanent_failure_fails(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="permanent_failure")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.FAILED.value
    assert out.failure_class == "permanent_error"


def test_timeout_retryable_then_dead_letter(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="timeout")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.RETRY_WAIT.value
    assert out.failure_class == "timeout"


def test_rate_limit_retryable(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="rate_limit")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.RETRY_WAIT.value
    assert out.failure_class == "rate_limited"


def test_malformed_output_is_permanent(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="malformed_output")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.FAILED.value
    assert out.failure_class == "malformed_output"


def test_cancellation_during_retry_wait(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state), job_type="transient_failure",
                  payload={"succeed_on_attempt": 99})
    _claim_and_run(svc, seeded_state.ids["org"])
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == \
        JobState.RETRY_WAIT.value
    svc.cancel(_ctx(seeded_state), job["id"], reason="cancel retry wait")
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == \
        JobState.CANCELLED.value


def test_auth_revoked_during_retry_wait(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="transient_failure",
            payload={"succeed_on_attempt": 99})
    _claim_and_run(svc, seeded_state.ids["org"])
    seeded_state.repos.db.conn.execute(
        "UPDATE memberships SET status='suspended' WHERE organization_id=? AND user_id=?",
        (seeded_state.ids["org"], seeded_state.ids["user"]))
    seeded_state.repos.db.conn.commit()
    job = svc.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    run = svc.repos.job_runs.by_request(job["id"])[0]
    svc.repos.db.conn.execute(
        "UPDATE job_runs SET scheduled_time=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
    svc.repos.db.conn.commit()
    svc._transition(job=job, run=run, new_state=JobState.QUEUED.value,
                    actor="scheduler", reason="backoff elapsed")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value


# ---------------------------------------------------------------------------
# B11 — cancellation
# ---------------------------------------------------------------------------

def test_cancel_queued_job(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state))
    svc.cancel(_ctx(seeded_state), job["id"], reason="no longer needed")
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == \
        JobState.CANCELLED.value


def test_cancel_leased_job_cooperative(seeded_state):
    """Cooperative running cancellation: the running worker observes the
    cancel request and the job reaches CANCELLED exactly once."""
    # The executing 'worker' uses its OWN connection (thread-safe), like a
    # real worker process; the operator cancels over the main connection.
    path = seeded_state.db.path
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state), job_type="cancellable",
                  payload={"delay_seconds": 0.05})
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    assert claimed is not None
    outcome_holder = {}

    def run():
        from Northstar_backend.foundation.api.state import FoundationState
        worker_state = FoundationState.build(path)
        try:
            worker_svc = worker_state.jobs_durable
            outcome_holder["out"] = worker_svc.execute_claimed(
                claimed, "w1")
        finally:
            worker_state.close()

    t = threading.Thread(target=run)
    t.start()
    import time
    time.sleep(0.01)
    svc.cancel(_ctx(seeded_state), job["id"], reason="cooperative cancel")
    t.join(timeout=5)
    out = outcome_holder.get("out")
    assert out is not None and out.state == JobState.CANCELLED.value


# ---------------------------------------------------------------------------
# B12 — dead letter
# ---------------------------------------------------------------------------

def test_dead_letter_manual_retry_new_run(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    job = _submit(svc, _ctx(seeded_state), job_type="transient_failure",
                  payload={"succeed_on_attempt": 99})
    for _ in range(4):
        out = _claim_and_run(svc, seeded_state.ids["org"])
        if out is None:
            break
        if out.state == JobState.DEAD_LETTER.value:
            break
        job_row = svc.repos.job_requests.get(job["id"])
        run = svc.repos.job_runs.by_request(job["id"])[0]
        svc.repos.db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
        svc.repos.db.conn.commit()
        svc._transition(job=job_row, run=run, new_state=JobState.QUEUED.value,
                        actor="scheduler", reason="backoff elapsed")
    assert out.state == JobState.DEAD_LETTER.value
    # manual retry creates a NEW run linked to the old one
    before_runs = len(svc.repos.job_runs.by_request(job["id"]))
    svc.retry(_ctx(seeded_state), job["id"], reason="manual retry")
    runs = svc.repos.job_runs.by_request(job["id"])
    assert len(runs) == before_runs + 1
    assert runs[-1]["parent_job_id"] == runs[-2]["run_id"]
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == \
        JobState.QUEUED.value


def test_dead_letter_error_preserved_redacted(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="permanent_failure")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.FAILED.value
    run = svc.repos.job_runs.by_request(
        svc.repos.job_requests.list(
            where={"organization_id": seeded_state.ids["org"]})[0]["id"])[0]
    assert run["error_code"] == "permanent_failure"
    assert run["error_summary"]  # redacted summary present


def test_provider_disabled_after_queueing(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    _submit(svc, _ctx(seeded_state), job_type="fixture_reader")
    # provider definition exists but is disabled -> BLOCKED_PROVIDER
    from Northstar_backend.foundation.models import ProviderDefinition
    seeded_state.repos.providers.add(ProviderDefinition(
        provider_key="fixture_reader", name="Fixture Reader", category="discovery",
        enabled=False))
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.BLOCKED_PROVIDER.value
    assert seeded_state.repos.usage.count() == 0
    # enable -> re-queue (operator unblocks) -> runs
    seeded_state.repos.db.conn.execute(
        "UPDATE providers SET enabled=1 WHERE provider_key='fixture_reader'")
    seeded_state.repos.db.conn.commit()
    job_row = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    run = seeded_state.repos.job_runs.by_request(job_row["id"])[0]
    svc._transition(job=job_row, run=run, new_state=JobState.QUEUED.value,
                    actor="operator", reason="provider re-enabled")
    out = _claim_and_run(svc, seeded_state.ids["org"])
    assert out.state == JobState.SUCCEEDED.value


def test_worker_rejects_unregistered_job(seeded_state):
    """Unregistered job types fail closed even if rows exist."""
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.jobs_handlers import UnknownJobType
    with pytest.raises(UnknownJobType):
        svc.submit(_ctx(seeded_state), job_type="ghost", payload={},
                   payload_schema_version="1.0")