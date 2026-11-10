"""1C-04 durable schema tests on the SQLite backend (always run).

These assert the SCHEMA spec (single source of truth) contains the additive
durable-execution objects, the generated SQLite DDL actually creates them, and
repository round-trips work. PostgreSQL parity is covered by the equivalent
integration module (test_jobs_durable_postgres.py) against the disposable PG.
"""
from __future__ import annotations

import sqlite3

from Northstar_backend.foundation.db import (
    SCHEMA, SQLITE_DDL, postgres_ddl, validate_sqlite_schema,
)
from Northstar_backend.foundation.db import FoundationDB
from Northstar_backend.foundation.models import (
    Organization, User, Membership, JobRequest, JobRun,
    JobStateHistory, JobSchedule, ScheduleOccurrence,
)
from Northstar_backend.foundation.enums import Role


def test_durable_columns_declared_in_schema():
    req_cols = {c for c, _ in SCHEMA["job_requests"]}
    for c in ("job_type", "payload", "payload_schema_version", "approval_id",
              "provider_class", "budget_class", "estimated_cost",
              "parent_job_id", "correlation_id", "provenance"):
        assert c in req_cols
    run_cols = {c for c, _ in SCHEMA["job_runs"]}
    for c in ("priority", "reserved_cost", "actual_cost", "scheduled_time",
              "heartbeat_time", "lease_owner", "lease_expiration",
              "idempotency_key", "parent_job_id", "correlation_id",
              "output_reference", "error_code", "error_summary",
              "cancellation_state"):
        assert c in run_cols


def test_durable_tables_declared_in_schema():
    for t in ("job_state_history", "job_schedules", "schedule_occurrences"):
        assert t in SCHEMA


def test_money_type_maps_to_numeric_on_postgres():
    pg = postgres_ddl()
    assert '"estimated_cost" NUMERIC' in pg


def test_durable_objects_created_on_sqlite():
    con = sqlite3.connect(":memory:")
    try:
        for stmt in SQLITE_DDL:
            con.execute(stmt)
        for t in ("job_state_history", "job_schedules", "schedule_occurrences"):
            info = con.execute(f"PRAGMA table_info({t})").fetchall()
            assert info, f"table {t} not created"
        req_cols = [r[1] for r in con.execute("PRAGMA table_info(job_requests)").fetchall()]
        assert "job_type" in req_cols and "estimated_cost" in req_cols
        run_cols = [r[1] for r in con.execute("PRAGMA table_info(job_runs)").fetchall()]
        assert "lease_owner" in run_cols and "actual_cost" in run_cols
    finally:
        con.close()


def test_sqlite_schema_equivalence_holds_with_durable_objects():
    report = validate_sqlite_schema()
    assert report["all_match"] is True
    assert report["tables"] == len(SCHEMA)


def test_durable_repository_roundtrip_sqlite():
    db = FoundationDB()
    try:
        org = Organization(name="Durable", slug="durable")
        user = User(email="durable@example.test")
        db.insert("organizations", {
            "id": org.id, "name": org.name, "slug": org.slug,
            "environment": org.environment, "created_at": org.created_at.isoformat()})
        db.insert("users", {
            "id": user.id, "email": user.email, "display_name": user.display_name,
            "active": 1, "created_at": user.created_at.isoformat()})
        db.insert("memberships", {
            "id": __import__("uuid").uuid4().hex, "organization_id": org.id,
            "user_id": user.id, "role": Role.ORGANIZATION_OWNER.value,
            "status": "active", "created_at": org.created_at.isoformat()})

        from Northstar_backend.foundation.repositories import Repositories
        repos = Repositories(db)
        req = JobRequest(organization_id=org.id, user_id=user.id,
                         job_type="immediate_success", payload={"x": 1},
                         payload_schema_version="1.0", provider_class="local",
                         budget_class="free", idempotency_key="k1")
        repos.job_requests.add(req)
        got = repos.job_requests.get(req.id)
        assert got["job_type"] == "immediate_success"
        assert got["idempotency_key"] == "k1"

        run = JobRun(job_request_id=req.id, state="queued", lease_owner="w1",
                     priority=1, error_code=None)
        repos.job_runs.add(run)
        got = repos.job_runs.get(run.id)
        assert got["lease_owner"] == "w1" and got["state"] == "queued"

        repos.job_state_history.add(JobStateHistory(
            job_id=req.id, previous_state="draft", new_state="queued",
            actor="requestor", reason="submit"))
        assert len(repos.job_state_history.for_job(req.id)) == 1

        sched = JobSchedule(organization_id=org.id, owner_user_id=user.id,
                            job_template={"job_type": "immediate_success"},
                            enabled=False)
        repos.job_schedules.add(sched)
        repos.schedule_occurrences.add(ScheduleOccurrence(
            schedule_id=sched.id, occurrence_key="o1", state="enqueued"))
        assert repos.schedule_occurrences.by_key(sched.id, "o1") is not None
    finally:
        db.close()