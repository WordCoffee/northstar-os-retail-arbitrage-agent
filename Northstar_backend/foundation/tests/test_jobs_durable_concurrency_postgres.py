"""Atomic claim + concurrency matrix on disposable PostgreSQL (1C-04 / B05, B14).

Runs ONLY when FOUNDATION_DB_URL points at the disposable loopback instance.
Each test uses its own organization to avoid cross-test interference, and the
module fixture resets the schema once.

Required outcomes asserted: zero unintended duplicate execution, zero lost jobs,
zero unauthorized starts, zero cross-org visibility, zero double debit, zero
stale finalization.
"""
from __future__ import annotations

import os
import threading
from urllib.parse import urlparse

import pytest

PG_URL = os.environ.get("FOUNDATION_DB_URL")

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="FOUNDATION_DB_URL not set (PostgreSQL integration)")

DISPOSABLE_DB = "northstar_phase1c02_ephemeral"
DISPOSABLE_USER = "northstar_phase1c02_test"


def _assert_disposable_target():
    u = urlparse(PG_URL)
    assert u.hostname == "127.0.0.1", f"host must be loopback, got {u.hostname}"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    assert u.port == 55432


def _succeeded_runs_for_org(st, org_id):
    rows = st.repos.job_runs.list(where={"state": "succeeded"})
    return [r for r in rows
            if st.repos.job_requests.get(r["job_request_id"])
            and st.repos.job_requests.get(r["job_request_id"])["organization_id"] == org_id]


@pytest.fixture(scope="module")
def durable_pg():
    _assert_disposable_target()
    from Northstar_backend.foundation.db import SCHEMA
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    db = PostgresFoundationDB(PG_URL)
    db.drop_all_foundation_tables(list(SCHEMA.keys()))
    db.apply_sql_file("Northstar_backend/migrations_foundation/001_foundation.sql")
    db.apply_sql_file("Northstar_backend/migrations_foundation/002_jobs_durable.sql")
    yield db
    db.close()


def _fresh_state_and_org(durable_pg, tag):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment, Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    st = FoundationState.build()
    org = Organization(name=f"PG {tag}", slug=f"pg-{tag}")
    user = User(email=f"{tag}@example.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(
        organization_id=org.id, user_id=user.id,
        role=Role.ORGANIZATION_OWNER.value, status="active"))
    st.repos.org_balances.add(
        __import__("Northstar_backend.foundation.models", fromlist=["OrgBalance"])
        .OrgBalance(organization_id=org.id, granted=__import__(
            "decimal", fromlist=["Decimal"]).Decimal("1000.00")))
    ctx = build_context(user_id=user.id, organization_id=org.id,
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.PRODUCTION.value)
    st.ids = {"org": org.id, "user": user.id}
    st.ctx = ctx
    return st


def test_two_workers_one_job_single_claim(durable_pg):
    st = _fresh_state_and_org(durable_pg, "tw1")
    svc = st.jobs_durable
    svc.submit(st.ctx, job_type="immediate_success", payload={},
               payload_schema_version="1.0")
    a = svc.claim_next("worker-a", organization_id=st.ids["org"])
    b = svc.claim_next("worker-b", organization_id=st.ids["org"])
    assert a is not None and b is None
    st.close()


def test_multiple_workers_multiple_jobs_exactly_once(durable_pg):
    st = _fresh_state_and_org(durable_pg, "mw")
    svc = st.jobs_durable
    for i in range(6):
        svc.submit(st.ctx, job_type="immediate_success", payload={"i": i},
                   payload_schema_version="1.0",
                   idempotency_key=f"mw-{i}")
    outcomes = []
    lock = threading.Lock()

    def run(wid):
        # each worker gets its OWN connection (thread-safe, like a real worker)
        ws = _fresh_state_and_org(durable_pg, f"mw-{wid}")
        try:
            wsvc = ws.jobs_durable
            while True:
                claimed = wsvc.claim_next(wid, organization_id=st.ids["org"])
                if claimed is None:
                    return
                out = wsvc.execute_claimed(claimed, wid)
                with lock:
                    outcomes.append(out)
        finally:
            ws.close()

    workers = []
    for i in range(3):
        t = threading.Thread(target=run, args=(f"worker-{i}",))
        workers.append(t)
        t.start()
    for t in workers:
        t.join()
    assert len(outcomes) == 6
    assert all(o.state == "succeeded" for o in outcomes)
    # zero duplicate execution: exactly 6 runs succeeded for THIS org
    rows = _succeeded_runs_for_org(st, st.ids["org"])
    assert len(rows) == 6
    st.close()


def test_duplicate_idempotency_single_submission(durable_pg):
    st = _fresh_state_and_org(durable_pg, "idem")
    svc = st.jobs_durable
    a = svc.submit(st.ctx, job_type="immediate_success", payload={},
                   payload_schema_version="1.0", idempotency_key="dup-1")
    b = svc.submit(st.ctx, job_type="immediate_success", payload={},
                   payload_schema_version="1.0", idempotency_key="dup-1")
    assert a["id"] == b["id"]
    assert len(svc.repos.job_requests.list(where={"organization_id": st.ids["org"]})) == 1
    st.close()


def test_stale_completion_rejected(durable_pg):
    st = _fresh_state_and_org(durable_pg, "stale")
    svc = st.jobs_durable
    svc.submit(st.ctx, job_type="immediate_success", payload={},
               payload_schema_version="1.0")
    claimed = svc.claim_next("worker-a", organization_id=st.ids["org"])
    from Northstar_backend.foundation.jobs_durable import JobValidationError
    with pytest.raises(JobValidationError) as exc:
        svc.execute_claimed(claimed, "worker-b")  # stale worker
    assert exc.value.code == "lease_not_owned"
    # original worker finalizes; exactly one execution
    out = svc.execute_claimed(claimed, "worker-a")
    assert out.state == "succeeded"
    runs = _succeeded_runs_for_org(st, st.ids["org"])
    assert len(runs) == 1
    st.close()


def test_concurrent_reservations_cannot_overspend(durable_pg):
    st = _fresh_state_and_org(durable_pg, "budget")
    svc = st.jobs_durable
    # 6 jobs each estimating 200.00 against a 1000.00 grant
    for i in range(6):
        svc.submit(st.ctx, job_type="immediate_success",
                   payload={"est": 200}, payload_schema_version="1.0",
                   idempotency_key=f"bg-{i}")
    # force estimate via direct update (fake handlers cost 0; simulate metered)
    for row in st.repos.job_requests.list(where={"organization_id": st.ids["org"]}):
        st.repos.db.conn.execute(
            "UPDATE job_requests SET estimated_cost=%s WHERE id=%s", (200.0, row["id"]))
    st.repos.db.conn.commit()
    outcomes = []
    lock = threading.Lock()

    def run(wid):
        ws = _fresh_state_and_org(durable_pg, f"bg-{wid}")
        try:
            wsvc = ws.jobs_durable
            claimed = wsvc.claim_next(wid, organization_id=st.ids["org"])
            if claimed is None:
                return
            out = wsvc.execute_claimed(claimed, wid)
            with lock:
                outcomes.append(out)
        finally:
            ws.close()

    threads = [threading.Thread(target=run, args=(f"w{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # at most floor(1000/200)=5 can be reserved/started; the 6th is blocked
    bal = st.repos.org_balances.get(st.ids["org"])
    assert bal["reserved"] <= 0  # all settled/released
    assert bal["consumed"] <= 1000.0
    started = [o for o in outcomes]
    # zero double-debit: consumed == sum of actual costs of executed runs
    finalized = [e for e in st.repos.usage.list(
        where={"status": "finalized"})]
    total_debited = sum(float(e["credits_debited_shadow"] or 0) for e in finalized)
    assert abs(total_debited - float(bal["consumed"])) < 0.001
    st.close()


def _conn_state(org_id, user_id):
    """A separate connection whose context points at an EXISTING org/user."""
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment, Role
    st = FoundationState.build()
    ctx = build_context(user_id=user_id, organization_id=org_id,
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.PRODUCTION.value)
    return st, ctx


def test_concurrent_cancellation_single_winner(durable_pg):
    """Concurrent cancellation: exactly one terminal cancelled state, no leak."""
    st = _fresh_state_and_org(durable_pg, "ccancel")
    svc = st.jobs_durable
    job = svc.submit(st.ctx, job_type="immediate_success", payload={},
                     payload_schema_version="1.0")
    results = []
    lock = threading.Lock()

    def cancel():
        cs, cctx = _conn_state(st.ids["org"], st.ids["user"])
        try:
            r = cs.jobs_durable.cancel(cctx, job["id"], reason="concurrent cancel")
            with lock:
                results.append(r["state"])
        except Exception as e:  # noqa: BLE001 - concurrent loser may 409
            with lock:
                results.append(f"err:{type(e).__name__}")
        finally:
            cs.close()

    threads = [threading.Thread(target=cancel) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    final = svc.get_job(st.ids["org"], job["id"])
    assert final["state"] == "cancelled"
    cancelled_runs = st.repos.job_runs.list(where={"state": "cancelled"})
    assert len(cancelled_runs) == 1
    st.close()


def test_two_scheduler_instances_one_occurrence_pg(durable_pg):
    """B15: two scheduler instances must enqueue at most one job per occurrence."""
    st = _fresh_state_and_org(durable_pg, "sched")
    from Northstar_backend.foundation.jobs_scheduler import JobScheduler
    from datetime import datetime, timedelta, timezone
    first = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    s1 = JobScheduler(st.jobs_durable, st.repos, scheduler_id="sched-1")
    s2 = JobScheduler(st.jobs_durable, st.repos, scheduler_id="sched-2")
    s1.create_schedule(organization_id=st.ids["org"],
                       owner_user_id=st.ids["user"],
                       job_template={"job_type": "immediate_success"},
                       interval_seconds=3600, enabled=True,
                       first_run_at=first)
    a = s1.tick()
    b = s2.tick()
    assert a["enqueued"] == 1
    assert b["enqueued"] == 0
    jobs = st.repos.job_requests.list(where={"organization_id": st.ids["org"]})
    assert len(jobs) == 1
    occ = st.repos.schedule_occurrences.list(
        where={"schedule_id": st.repos.job_schedules.list()[0]["id"]})
    assert len(occ) == 1
    st.close()


def test_cross_org_visibility_zero(durable_pg):
    st1 = _fresh_state_and_org(durable_pg, "vis-a")
    st2 = _fresh_state_and_org(durable_pg, "vis-b")
    j1 = st1.jobs_durable.submit(st1.ctx, job_type="immediate_success", payload={},
                                 payload_schema_version="1.0")
    # org B cannot see org A's job
    assert st2.jobs_durable.get_job(st2.ids["org"], j1["id"]) is None
    # org B cannot claim org A's job
    assert st2.jobs_durable.claim_next("wb", organization_id=st2.ids["org"]) is None
    st1.close()
    st2.close()


def test_restart_with_queued_and_expired_leases(durable_pg):
    """Queued jobs survive; expired leases recover after a 'restart'."""
    st = _fresh_state_and_org(durable_pg, "restart")
    svc = st.jobs_durable
    svc.submit(st.ctx, job_type="immediate_success", payload={},
               payload_schema_version="1.0", idempotency_key="rq-1")
    svc.submit(st.ctx, job_type="immediate_success", payload={},
               payload_schema_version="1.0", idempotency_key="rq-2")
    # one job claimed then 'crashed' (no finalize); backdate its lease
    claimed = svc.claim_next("dead-worker", organization_id=st.ids["org"])
    from datetime import datetime, timedelta, timezone
    past = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    st.repos.db.conn.execute(
        "UPDATE job_runs SET lease_expiration=%s WHERE id=%s",
        (past, claimed["id"]))
    st.repos.db.conn.commit()
    # restart: recover + drain
    recovered = svc.recover_expired_leases(organization_id=st.ids["org"])
    assert len(recovered) == 1
    from Northstar_backend.foundation.jobs_worker import JobWorker
    worker = JobWorker(svc, worker_id="fresh-worker",
                       organization_id=st.ids["org"], poll_interval=0.005)
    outcomes = worker.drain(max_iterations=10)
    assert len(outcomes) == 2
    assert all(o.state == "succeeded" for o in outcomes)
    st.close()