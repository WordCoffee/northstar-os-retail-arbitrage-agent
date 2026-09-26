"""Financial-integrity gate on PostgreSQL (owner-prioritized vertical slice).

Required proofs, all on real PostgreSQL (disposable loopback):
  1. concurrent duplicate submissions -> ONE job, both callers receive the
     ORIGINAL job/result (never a second payable execution);
  2. retry-after-timeout -> exactly one ledger settlement;
  3. double-settlement attempt -> exactly one ledger entry (DB-level unique);
  4. failed handler -> zero settlements.

Runs ONLY when FOUNDATION_DB_URL points at the disposable loopback instance.
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
    assert u.hostname == "127.0.0.1"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    assert u.port == 55432


def _fresh(durable_pg, tag):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment, Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    st = FoundationState.build()
    org = Organization(name=f"Fin {tag}", slug=f"fin-{tag}")
    user = User(email=f"{tag}@fin.test")
    st.repos.organizations.add(org)
    st.repos.users.add(user)
    st.repos.memberships.add(Membership(organization_id=org.id, user_id=user.id,
                                        role=Role.ORGANIZATION_OWNER.value,
                                        status="active"))
    ctx = build_context(user_id=user.id, organization_id=org.id,
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.PRODUCTION.value)
    st.ids = {"org": org.id, "user": user.id}
    st.ctx = ctx
    return st


def _conn(org_id, user_id):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment, Role
    st = FoundationState.build()
    ctx = build_context(user_id=user_id, organization_id=org_id,
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.PRODUCTION.value)
    return st, ctx


def _finalized(st, org_id):
    return [e for e in st.repos.usage.list(where={"status": "finalized"})
            if st.repos.usage.get(e["id"])["organization_id"] == org_id]


@pytest.fixture(scope="module")
def durable_pg():
    _assert_disposable_target()
    from Northstar_backend.foundation.db import SCHEMA
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    db = PostgresFoundationDB(PG_URL)
    db.drop_all_foundation_tables(list(SCHEMA.keys()))
    for m in ("001_foundation.sql", "002_jobs_durable.sql",
              "003_keyword_intel.sql", "004_financial_integrity.sql"):
        db.apply_sql_file(f"Northstar_backend/migrations_foundation/{m}")
    yield db
    db.close()


def test_concurrent_duplicate_submission_single_job(durable_pg):
    """The mandatory gate: N concurrent duplicate submissions must create ONE
    job and every caller must receive the ORIGINAL job/result."""
    st = _fresh(durable_pg, "dup")
    org, user = st.ids["org"], st.ids["user"]
    results = []
    lock = threading.Lock()

    def submit_once(wid):
        cs, cctx = _conn(org, user)
        try:
            r = cs.jobs_durable.submit(
                cctx, job_type="immediate_success", payload={"w": wid},
                payload_schema_version="1.0", idempotency_key="dup-gate-1",
                correlation_id=f"dup-req-{wid}")
            with lock:
                results.append(r)
        finally:
            cs.close()

    threads = [threading.Thread(target=submit_once, args=(f"w{i}",))
               for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # exactly one job row
    rows = st.repos.job_requests.list(
        where={"organization_id": org, "idempotency_key": "dup-gate-1"})
    assert len(rows) == 1, f"expected 1 job, got {len(rows)}"
    job_id = rows[0]["id"]
    # every caller received the ORIGINAL job id
    assert all(r["id"] == job_id for r in results)
    assert len({r["id"] for r in results}) == 1
    # one run, one payable execution
    assert len(st.repos.job_runs.by_request(job_id)) == 1
    # execute once via a worker
    from Northstar_backend.foundation.jobs_worker import JobWorker
    worker = JobWorker(st.jobs_durable, worker_id="dup-w",
                       organization_id=org, poll_interval=0.005)
    worker.drain(max_iterations=50)
    assert st.jobs_durable.get_job(org, job_id)["state"] == "succeeded"
    finalized = _finalized(st, org)
    assert len(finalized) == 1  # exactly-once settlement
    st.close()


def test_double_settlement_attempt_single_entry(durable_pg):
    st = _fresh(durable_pg, "dbl")
    from decimal import Decimal
    svc = st.jobs_durable
    svc.grant(st.ids["org"], Decimal("100.00"))
    job = svc.submit(st.ctx, job_type="cost_variance",
                     payload={"estimated_cost": "10.00", "variance": "0.00"},
                     payload_schema_version="1.0", idempotency_key="dbl-1")
    st.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=%s WHERE id=%s", (10.0, job["id"]))
    st.db.conn.commit()
    claimed = svc.claim_next("w", organization_id=st.ids["org"])
    run = st.repos.job_runs.get(claimed["id"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == "succeeded"
    # a SECOND settlement attempt for the same (run, attempt) must be a no-op
    svc.settle_usage(job, run, Decimal("10.00"), Decimal("10.00"), attempt=1)
    finalized = _finalized(st, st.ids["org"])
    assert len(finalized) == 1
    bal = st.repos.org_balances.get(st.ids["org"])
    assert abs(float(bal["consumed"]) - 10.0) < 0.001
    assert float(bal["reserved"]) == 0.0
    st.close()


def test_failed_handler_never_settles(durable_pg):
    st = _fresh(durable_pg, "fail")
    svc = st.jobs_durable
    svc.submit(st.ctx, job_type="permanent_failure", payload={},
               payload_schema_version="1.0", idempotency_key="fail-1")
    claimed = svc.claim_next("w", organization_id=st.ids["org"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == "failed"
    assert len(_finalized(st, st.ids["org"])) == 0
    bal = st.repos.org_balances.get(st.ids["org"])
    assert float(bal["consumed"]) == 0.0 and float(bal["reserved"]) == 0.0
    st.close()


def test_retry_after_timeout_single_settlement(durable_pg):
    from datetime import datetime, timedelta, timezone
    from Northstar_backend.foundation.jobs_state import JobState
    st = _fresh(durable_pg, "tmo")
    svc = st.jobs_durable
    job = svc.submit(st.ctx, job_type="timeout",
                     payload={"succeed_on_attempt": 2},
                     payload_schema_version="1.0", idempotency_key="tmo-1")
    claimed = svc.claim_next("w", organization_id=st.ids["org"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == JobState.RETRY_WAIT.value
    run = st.repos.job_runs.by_request(job["id"])[0]
    st.db.conn.execute(
        "UPDATE job_runs SET scheduled_time=%s WHERE id=%s",
        ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
    st.db.conn.commit()
    svc._transition(job=st.repos.job_requests.get(job["id"]), run=run,
                    new_state=JobState.QUEUED.value,
                    actor="scheduler", reason="backoff elapsed")
    claimed2 = svc.claim_next("w", organization_id=st.ids["org"])
    out2 = svc.execute_claimed(claimed2, "w")
    assert out2.state == "succeeded"
    assert len(_finalized(st, st.ids["org"])) == 1
    st.close()