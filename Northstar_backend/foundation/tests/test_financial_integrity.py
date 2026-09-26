"""Financial-integrity gate tests (1C-04 vertical slice).

Mandatory acceptance: idempotent submission (scoped to account + request type)
returns the ORIGINAL job/result; exactly-once settlement protected by a
DB-level unique + transaction; failed/cancelled/unknown-result jobs never
settle; every transition writes an append-only audit record correlated by
request ID / job ID / actor ID / timestamp.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Environment, Role
from Northstar_backend.foundation.jobs_durable import DurableJobService
from Northstar_backend.foundation.jobs_state import JobState
from Northstar_backend.foundation.models import Organization, User, Membership
from Northstar_backend.foundation.jobs_worker import JobWorker


def _mk_state():
    fd, path = tempfile.mkstemp(prefix="ns_fin_", suffix=".db")
    os.close(fd)
    from Northstar_backend.foundation.api.state import FoundationState
    st = FoundationState.build(path)
    org = Organization(name="Fin", slug="fin")
    user = User(email="fin@example.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                        role=Role.ORGANIZATION_OWNER.value))
    st.ids = {"org": org.id, "user": user.id}
    st.ctx = build_context(user_id=user.id, organization_id=org.id,
                           role=Role.ORGANIZATION_OWNER.value,
                           environment=Environment.PRODUCTION.value)
    return st


def _submit(svc, ctx, *, job_type="immediate_success", **kw):
    return svc.submit(ctx, job_type=job_type, payload=kw.pop("payload", {}),
                      payload_schema_version="1.0", **kw)


def _drain(st, org_id):
    w = JobWorker(st.jobs_durable, worker_id="fin-w",
                  organization_id=org_id, poll_interval=0.005)
    return w.drain(max_iterations=200)


def _finalized(st, org_id):
    return [e for e in st.repos.usage.for_org(org_id)
            if e["status"] == "finalized"]


# --- idempotent submission (account + request type scope) -------------------

def test_idempotent_replay_returns_original_job_and_result():
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        a = _submit(svc, st.ctx, idempotency_key="idem-1", correlation_id="req-1")
        _drain(st, st.ids["org"])
        b = _submit(svc, st.ctx, idempotency_key="idem-1", correlation_id="req-1")
        assert a["id"] == b["id"]
        assert b["state"] == "succeeded"  # returns the ORIGINAL job/result
        assert b["runs"][0]["output_reference"] is not None
        assert len(st.repos.job_requests.list(
            where={"organization_id": st.ids["org"]})) == 1
        assert len(_finalized(st, st.ids["org"])) == 1  # one execution, one settle
    finally:
        st.close()


def test_idempotency_scoped_to_request_type():
    """Same key + DIFFERENT job_type -> a NEW job (never a wrong replay)."""
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        a = _submit(svc, st.ctx, job_type="immediate_success",
                    idempotency_key="shared-key")
        b = _submit(svc, st.ctx, job_type="slow_success",
                    idempotency_key="shared-key")
        assert a["id"] != b["id"]
        assert a["job_type"] == "immediate_success"
        assert b["job_type"] == "slow_success"
        assert len(st.repos.job_requests.list(
            where={"organization_id": st.ids["org"]})) == 2
    finally:
        st.close()


# --- exactly-once settlement --------------------------------------------------

def test_retry_after_timeout_single_settlement():
    """Timeout is retryable; the eventual success settles EXACTLY once."""
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        job = _submit(svc, st.ctx, job_type="timeout",
                      payload={"succeed_on_attempt": 2},
                      idempotency_key="to-1")
        out = _drain(st, st.ids["org"])
        assert out and out[0].state == JobState.RETRY_WAIT.value
        # drive retry: backdate scheduled_time, re-queue, drain
        run = st.repos.job_runs.by_request(job["id"])[0]
        st.db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
        st.db.conn.commit()
        svc._transition(job=st.repos.job_requests.get(job["id"]), run=run,
                        new_state=JobState.QUEUED.value,
                        actor="scheduler", reason="backoff elapsed")
        _drain(st, st.ids["org"])
        assert svc.get_job(st.ids["org"], job["id"])["state"] == "succeeded"
        assert len(_finalized(st, st.ids["org"])) == 1
        bal = svc._balance(st.ids["org"])
        assert bal.reserved == 0
    finally:
        st.close()


def test_double_settlement_attempt_single_entry():
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        svc.grant(st.ids["org"], Decimal("100.00"))
        job = _submit(svc, st.ctx, job_type="cost_variance",
                      payload={"estimated_cost": "10.00", "variance": "0.00"},
                      idempotency_key="ds-1")
        st.db.conn.execute(
            "UPDATE job_requests SET estimated_cost=? WHERE id=?", (10.0, job["id"]))
        st.db.conn.commit()
        claimed = svc.claim_next("w", organization_id=st.ids["org"])
        run = st.repos.job_runs.get(claimed["id"])
        run_row = st.repos.job_runs.get(claimed["id"])
        out = svc.execute_claimed(claimed, "w")
        assert out.state == "succeeded"
        # a SECOND settlement attempt for the SAME (run, attempt) is a no-op
        svc.settle_usage(job, run_row, Decimal("10.00"), Decimal("10.00"), attempt=1)
        assert len(_finalized(st, st.ids["org"])) == 1
        bal = svc._balance(st.ids["org"])
        assert bal.consumed == Decimal("10.00")  # never double-debited
        assert bal.reserved == 0
    finally:
        st.close()


def test_failed_handler_never_settles():
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        _submit(svc, st.ctx, job_type="permanent_failure", idempotency_key="pf-1")
        _drain(st, st.ids["org"])
        assert len(_finalized(st, st.ids["org"])) == 0
        bal = svc._balance(st.ids["org"])
        assert bal.consumed == 0 and bal.reserved == 0
    finally:
        st.close()


def test_cancelled_job_never_settles():
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        job = _submit(svc, st.ctx, idempotency_key="cn-1")
        svc.cancel(st.ctx, job["id"], reason="no longer needed")
        _drain(st, st.ids["org"])
        assert svc.get_job(st.ids["org"], job["id"])["state"] == "cancelled"
        assert len(_finalized(st, st.ids["org"])) == 0
    finally:
        st.close()


def test_unknown_result_release_releases_reservation_no_settlement():
    """Worker dies after reserving but before settling: recovery RELEASES the
    reservation; nothing settles; re-execution reserves fresh and settles once."""
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        svc.grant(st.ids["org"], Decimal("100.00"))
        job = _submit(svc, st.ctx, job_type="cost_variance",
                      payload={"estimated_cost": "10.00", "variance": "0.00"},
                      idempotency_key="cr-1")
        st.db.conn.execute(
            "UPDATE job_requests SET estimated_cost=? WHERE id=?", (10.0, job["id"]))
        st.db.conn.commit()
        claimed = svc.claim_next("dead-worker", organization_id=st.ids["org"])
        # simulate crash AFTER the worker reserved but BEFORE settling: call
        # the same reservation step the worker performs, then backdate the
        # lease with no finalize (unknown outcome).
        job_row = st.repos.job_requests.get(job["id"])
        run_row = st.repos.job_runs.get(claimed["id"])
        svc.reserve_usage(job_row, run_row, Decimal("10.00"), attempt=1)
        past = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
        st.db.conn.execute(
            "UPDATE job_runs SET lease_expiration=? WHERE id=?", (past, claimed["id"]))
        st.db.conn.commit()
        reserved_before = svc._balance(st.ids["org"]).reserved
        assert reserved_before == Decimal("10.00")
        svc.recover_expired_leases(organization_id=st.ids["org"])
        bal = svc._balance(st.ids["org"])
        assert bal.reserved == 0  # released, never settled
        assert len(_finalized(st, st.ids["org"])) == 0
        # re-execution reserves fresh and settles exactly once
        _drain(st, st.ids["org"])
        assert svc.get_job(st.ids["org"], job["id"])["state"] == "succeeded"
        assert len(_finalized(st, st.ids["org"])) == 1
        assert svc._balance(st.ids["org"]).consumed == Decimal("10.00")
    finally:
        st.close()


# --- audit chain --------------------------------------------------------------

def test_audit_chain_correlated():
    """request -> job -> execution -> audit: every transition is append-only and
    correlated by correlation_id (request ID), job ID, actor, timestamp."""
    st = _mk_state()
    try:
        svc = DurableJobService(st.repos)
        job = _submit(svc, st.ctx, idempotency_key="audit-1",
                      correlation_id="req-chain-1")
        _drain(st, st.ids["org"])
        events = st.repos.audit.list(
            where={"organization_id": st.ids["org"], "correlation_id": "req-chain-1"})
        assert events, "audit chain missing correlation_id"
        actions = {e["action"] for e in events}
        for expected in ("job.submit", "job.state.queued", "job.state.leased",
                         "job.state.running", "job.state.succeeded"):
            assert expected in actions
        for e in events:
            assert e["correlation_id"] == "req-chain-1"
            assert e["resource_id"] == job["id"]      # job ID
            assert e["actor_user_id"] == st.ids["user"]  # actor ID
            assert e["occurred_at"]                    # timestamp
        # job_state_history is the append-only transition record (newest-first)
        history = st.repos.job_state_history.for_job(job["id"])
        states = [h["new_state"] for h in reversed(history)]
        assert states == ["draft", "queued", "leased", "running", "succeeded"]
    finally:
        st.close()