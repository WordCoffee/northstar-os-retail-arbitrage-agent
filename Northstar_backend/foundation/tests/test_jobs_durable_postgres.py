"""1C-04 durable schema + repository integration tests on disposable PostgreSQL.

Runs ONLY when FOUNDATION_DB_URL points at the disposable loopback instance
(same guardrails as test_postgres_integration.py). Skipped otherwise, so the
offline SQLite suite is never affected.
"""
from __future__ import annotations

import os
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


def _state():
    from Northstar_backend.foundation.api.state import FoundationState
    st = FoundationState.build()
    return st


def test_durable_schema_objects_present(durable_pg):
    fp = durable_pg.schema_fingerprint()
    tables = fp["tables"]
    for t in ("job_state_history", "job_schedules", "schedule_occurrences"):
        assert t in tables
    assert "job_type" in tables["job_requests"]
    assert "payload" in tables["job_requests"]
    assert "estimated_cost" in tables["job_requests"]
    for c in ("lease_owner", "lease_expiration", "heartbeat_time",
              "reserved_cost", "actual_cost", "output_reference",
              "error_code", "error_summary", "cancellation_state"):
        assert c in tables["job_runs"]


def test_durable_foreign_keys_present(durable_pg):
    fp = durable_pg.schema_fingerprint()
    names = [c for v in fp["constraints"].values() for c in v]
    for fk in ("fk_job_requests_organization_id", "fk_job_runs_job_request_id",
               "fk_job_schedules_organization_id",
               "fk_schedule_occurrences_schedule_id"):
        assert any(fk in n for n in names)


def test_money_columns_are_numeric(durable_pg):
    cur = durable_pg._raw.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='job_requests' "
        "AND column_name='estimated_cost'")
    r = cur.fetchone()
    assert r["data_type"] == "numeric"
    cur = durable_pg._raw.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='job_runs' "
        "AND column_name='reserved_cost'")
    r = cur.fetchone()
    assert r["data_type"] == "numeric"


def test_durable_repositories_roundtrip(durable_pg):
    from Northstar_backend.foundation.models import (
        Organization, User, Membership, JobRequest, JobRun,
        JobStateHistory, JobSchedule, ScheduleOccurrence,
    )
    from Northstar_backend.foundation.enums import Role
    st = _state()
    try:
        org = Organization(name="Durable", slug="durable")
        user = User(email="durable@example.test")
        st.repos.organizations.add(org)
        st.repos.users.add(user)
        st.repos.memberships.add(Membership(
            organization_id=org.id, user_id=user.id,
            role=Role.ORGANIZATION_OWNER.value, status="active"))

        req = JobRequest(organization_id=org.id, user_id=user.id,
                         service="svc", job_type="immediate_success",
                         payload={"x": 1}, payload_schema_version="1.0",
                         provider_class="local", budget_class="free",
                         idempotency_key="pg-durable-key")
        st.repos.job_requests.add(req)
        assert st.repos.job_requests.get(req.id)["job_type"] == "immediate_success"

        run = JobRun(job_request_id=req.id, state="queued", run_id="pg-run-1",
                     priority=3, lease_owner="worker-a")
        st.repos.job_runs.add(run)
        got = st.repos.job_runs.get(run.id)
        assert got["lease_owner"] == "worker-a"
        assert got["priority"] == 3

        st.repos.job_state_history.add(JobStateHistory(
            job_id=req.id, run_id="pg-run-1", previous_state="draft",
            new_state="queued", actor="requestor", reason="submit"))
        assert len(st.repos.job_state_history.for_job(req.id)) == 1

        sched = JobSchedule(organization_id=org.id, owner_user_id=user.id,
                            job_template={"job_type": "immediate_success"},
                            enabled=False, timezone="UTC")
        st.repos.job_schedules.add(sched)
        st.repos.schedule_occurrences.add(ScheduleOccurrence(
            schedule_id=sched.id, occurrence_key="occ-1", state="enqueued"))
        assert st.repos.schedule_occurrences.by_key(sched.id, "occ-1") is not None
    finally:
        st.close()


def test_org_scoped_idempotency_enforced(durable_pg):
    from Northstar_backend.foundation.models import (
        Organization, User, JobRequest,
    )
    st = _state()
    try:
        org = Organization(name="Idem A", slug="idem-a")
        org2 = Organization(name="Idem B", slug="idem-b")
        user = User(email="idem@example.test")
        st.repos.organizations.add(org)
        st.repos.organizations.add(org2)
        st.repos.users.add(user)
        a = JobRequest(organization_id=org.id, user_id=user.id,
                       idempotency_key="shared-key", job_type="immediate_success")
        b = JobRequest(organization_id=org.id, user_id=user.id,
                       idempotency_key="shared-key", job_type="immediate_success")
        c = JobRequest(organization_id=org2.id, user_id=user.id,
                       idempotency_key="shared-key", job_type="immediate_success")
        st.repos.job_requests.add(a)
        with pytest.raises(Exception):
            st.repos.job_requests.add(b)  # duplicate within org -> rejected
        st.repos.job_requests.add(c)      # cross-org same key -> allowed
        rows = st.repos.job_requests.list(
            where={"idempotency_key": "shared-key"})
        assert len(rows) == 2
    finally:
        st.close()


def test_foreign_key_violation_rejected(durable_pg):
    from Northstar_backend.foundation.models import JobRequest, JobRun
    st = _state()
    try:
        run = JobRun(job_request_id="no-such-request", state="queued")
        with pytest.raises(Exception):
            st.repos.job_runs.add(run)
        req = JobRequest(organization_id="no-such-org", job_type="x")
        with pytest.raises(Exception):
            st.repos.job_requests.add(req)
    finally:
        st.close()