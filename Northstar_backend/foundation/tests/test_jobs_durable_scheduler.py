"""Persisted scheduler tests (1C-04 / B15).

The scheduler ENQUEUES ONLY — it never executes jobs and never calls providers.
Occurrence idempotency guarantees two scheduler instances enqueue at most one
job per occurrence. GET requests never tick the scheduler.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.jobs_scheduler import JobScheduler, SchedulerError
from Northstar_backend.foundation.jobs_state import JobState
from Northstar_backend.foundation.models import Organization, User, Membership
from Northstar_backend.foundation.tests.conftest import owner_headers


def _iso_from_now(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _make_schedule(seeded_state, *, interval_seconds=3600, enabled=True,
                   owner=None, org_id=None, job_type="immediate_success",
                   first_run_at=None, misfire_policy="skip",
                   concurrency_policy=None):
    svc = seeded_state.jobs_durable
    sched = JobScheduler(svc, seeded_state.repos, scheduler_id="test-sched")
    org = org_id or seeded_state.ids["org"]
    owner_user = owner or seeded_state.ids["user"]
    row = sched.create_schedule(
        organization_id=org, owner_user_id=owner_user,
        job_template={"job_type": job_type, "payload": {"n": 1}},
        interval_seconds=interval_seconds, enabled=enabled,
        first_run_at=first_run_at or _iso_from_now(-5),  # due now
        misfire_policy=misfire_policy,
        concurrency_policy=concurrency_policy)
    return sched, row


def test_scheduler_enqueues_one_job(client, seeded_state):
    sched, row = _make_schedule(seeded_state)
    result = sched.tick()
    assert result["enqueued"] == 1
    # enqueue only: the job is QUEUED, never executed
    jobs = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert len(jobs) == 1
    assert jobs[0]["state"] == JobState.QUEUED.value
    assert seeded_state.repos.job_runs.count() == 1
    assert seeded_state.repos.job_runs.list()[0]["state"] == JobState.QUEUED.value
    # no provider activity, no execution
    assert seeded_state.repos.usage.count() == 0


def test_two_scheduler_instances_one_occurrence(seeded_state):
    sched, row = _make_schedule(seeded_state)
    other = JobScheduler(seeded_state.jobs_durable, seeded_state.repos,
                         scheduler_id="other-sched")
    a = sched.tick()
    b = other.tick()  # second instance sees the same due schedule
    assert a["enqueued"] == 1
    assert b["enqueued"] == 0
    jobs = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert len(jobs) == 1  # exactly one job for the occurrence


def test_tick_is_idempotent(seeded_state):
    sched, row = _make_schedule(seeded_state)
    sched.tick()
    sched.tick()  # next_run_at advanced; nothing new due
    jobs = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert len(jobs) == 1


def test_disabled_schedule_skipped(seeded_state):
    sched, row = _make_schedule(seeded_state, enabled=False)
    result = sched.tick()
    assert result["enqueued"] == 0
    assert seeded_state.repos.job_requests.count() == 0


def test_suspended_org_skipped(seeded_state):
    sched, row = _make_schedule(seeded_state)
    seeded_state.repos.db.conn.execute(
        "UPDATE organizations SET active=0 WHERE id=?", (seeded_state.ids["org"],))
    seeded_state.repos.db.conn.commit()
    result = sched.tick()
    assert result["enqueued"] == 0
    assert seeded_state.repos.job_requests.count() == 0
    # occurrence marked skipped; no job created
    occ = seeded_state.repos.schedule_occurrences.list()
    assert occ and occ[0]["state"] in ("skipped",)


def test_revoked_owner_skipped(seeded_state):
    sched, row = _make_schedule(seeded_state)
    seeded_state.repos.db.conn.execute(
        "UPDATE memberships SET status='revoked' WHERE user_id=? AND organization_id=?",
        (seeded_state.ids["user"], seeded_state.ids["org"]))
    seeded_state.repos.db.conn.commit()
    result = sched.tick()
    assert result["enqueued"] == 0


def test_misfire_window_prevents_catch_up(seeded_state):
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    sched, row = _make_schedule(seeded_state, first_run_at=past)
    result = sched.tick()
    assert result["enqueued"] == 0  # misfire -> skip, no unbounded catch-up
    assert seeded_state.repos.job_requests.count() == 0


def test_misfire_window_with_policy_enqueue(seeded_state):
    past = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    sched, row = _make_schedule(seeded_state, first_run_at=past,
                                misfire_policy="enqueue")
    result = sched.tick()
    assert result["enqueued"] == 1  # policy explicitly allows the catch-up


def test_concurrency_limit_skips(seeded_state):
    sched, row = _make_schedule(seeded_state, first_run_at=_iso_from_now(-5),
                                concurrency_policy={"max_concurrent": 1})
    # one outstanding occurrence already exists
    from Northstar_backend.foundation.models import ScheduleOccurrence
    seeded_state.repos.schedule_occurrences.add(ScheduleOccurrence(
        schedule_id=row["id"], occurrence_key="outstanding-1", state="enqueued"))
    result = sched.tick()
    assert result["enqueued"] == 0
    assert result["skipped"] == 1


def test_cron_schedule_supported(seeded_state):
    svc = seeded_state.jobs_durable
    sched = JobScheduler(svc, seeded_state.repos, scheduler_id="cron-sched")
    row = sched.create_schedule(
        organization_id=seeded_state.ids["org"],
        owner_user_id=seeded_state.ids["user"],
        job_template={"job_type": "immediate_success"},
        cron_expression="*/2 * * * *",  # every 2 minutes
        enabled=True, first_run_at=_iso_from_now(-5))
    nxt = sched.next_run_iso(cron="*/2 * * * *", interval=None)
    assert nxt is not None
    result = sched.tick()
    assert result["enqueued"] == 1


def test_schedule_requires_cron_or_interval(seeded_state):
    svc = seeded_state.jobs_durable
    sched = JobScheduler(svc, seeded_state.repos, scheduler_id="bad-sched")
    import pytest as _pytest
    with _pytest.raises(SchedulerError):
        sched.create_schedule(organization_id=seeded_state.ids["org"],
                              owner_user_id=seeded_state.ids["user"],
                              job_template={"job_type": "x"}, enabled=True)


def test_provider_backed_schedule_default_disabled(seeded_state):
    sched, row = _make_schedule(seeded_state, enabled=True)
    # enabled default is False (create defaults); re-assert explicitly
    svc = seeded_state.jobs_durable
    s2 = JobScheduler(svc, seeded_state.repos, scheduler_id="s2")
    r2 = s2.create_schedule(organization_id=seeded_state.ids["org"],
                            owner_user_id=seeded_state.ids["user"],
                            job_template={"job_type": "immediate_success"},
                            interval_seconds=60)
    assert not r2["enabled"]  # provider-backed schedules default disabled


def test_scheduler_never_executes_or_calls_providers(client, seeded_state):
    sched, row = _make_schedule(seeded_state)
    sched.tick()
    # the enqueued job sits queued; no provider rows needed, no usage
    assert seeded_state.repos.usage.count() == 0
    assert seeded_state.repos.job_runs.list()[0]["lease_owner"] is None


def test_get_schedules_does_not_tick(client, seeded_state):
    h = owner_headers(seeded_state)
    sched, row = _make_schedule(seeded_state)
    before = seeded_state.repos.job_requests.count()
    client.get("/api/v1/foundation/schedules", headers=h)
    client.get("/api/v1/foundation/schedules/posture", headers=h)
    assert seeded_state.repos.job_requests.count() == before  # GET never enqueues
    assert client.get(f"/api/v1/foundation/schedules/{row['id']}",
                      headers=h).status_code == 200


def test_schedule_org_isolation(client, seeded_state):
    h = owner_headers(seeded_state)
    sched, row = _make_schedule(seeded_state)
    other = Organization(name="Other", slug="other")
    user = User(email="other@example.test")
    seeded_state.repos.organizations.add(other)
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.ORGANIZATION_OWNER.value))
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    token = make_access_token(user.id, org=other.id, role="organization_owner")
    r = client.get(f"/api/v1/foundation/schedules/{row['id']}",
                   headers=bearer(token))
    assert r.status_code == 404  # cross-org not found


def test_schedule_api_enable_disable_archive(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/schedules", headers=h, json={
        "job_template": {"job_type": "immediate_success"},
        "interval_seconds": 60, "enabled": False,
        "first_run_at": (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()})
    assert r.status_code == 201, r.text
    sid = r.json()["id"]
    assert r.json()["enabled"] is False
    assert client.post(f"/api/v1/foundation/schedules/{sid}/enable", headers=h).json()["enabled"] is True
    assert client.post(f"/api/v1/foundation/schedules/{sid}/disable", headers=h).json()["enabled"] is False
    assert client.post(f"/api/v1/foundation/schedules/{sid}/archive", headers=h).json()["archived"] is True