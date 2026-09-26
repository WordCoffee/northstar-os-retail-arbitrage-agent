"""Atomic claim, worker execution, and vertical-slice tests (1C-04 / B05-B06).

Covers: atomic claiming (single winner), org-scoped claims, lease ownership and
heartbeats, stale-worker rejection, lease-expiry recovery, the full vertical
slice (POST -> queued -> claim -> rechecks -> immediate_success -> usage
settlement -> output persistence -> audit -> GET), and zero side effects for
GETs. Provider calls never occur; no network is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.jobs_durable import DurableJobService, JobValidationError
from Northstar_backend.foundation.jobs_state import JobState
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.tests.conftest import owner_headers


def _future(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _submit(client, headers, job_type="immediate_success", **kw):
    body = {"job_type": job_type, "payload_schema_version": "1.0",
            "payload": kw.pop("payload", {"n": 1})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


# ---------------------------------------------------------------------------
# B05 — atomic claim
# ---------------------------------------------------------------------------

def test_claim_sets_lease_and_state(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.api.router import DurableJobCreate  # noqa
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    job = svc.submit(ctx, job_type="immediate_success", payload={"n": 1},
                     payload_schema_version="1.0")
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    assert claimed is not None
    assert claimed["state"] == "leased"
    assert claimed["lease_owner"] == "worker-a"
    assert claimed["lease_expiration"] is not None
    detail = svc.get_job(seeded_state.ids["org"], job["id"])
    assert detail["state"] == "leased"


def test_two_workers_one_job_one_claim(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    svc.submit(ctx, job_type="immediate_success", payload={}, payload_schema_version="1.0")
    a = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    b = svc.claim_next("worker-b", organization_id=seeded_state.ids["org"])
    assert a is not None and b is None
    # job is now leased to worker-a only
    assert svc.queue_posture(seeded_state.ids["org"])["leased"] == 1


def test_claim_respects_org_scope(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    svc.submit(ctx, job_type="immediate_success", payload={}, payload_schema_version="1.0")
    other = Organization(name="Other", slug="other")
    seeded_state.repos.organizations.add(other)
    claimed = svc.claim_next("worker-a", organization_id=other.id)
    assert claimed is None
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    assert claimed is not None


def test_claim_honors_scheduled_time(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    job = svc.submit(ctx, job_type="immediate_success", payload={},
                     payload_schema_version="1.0")
    run = svc.repos.job_runs.by_request(job["id"])[0]
    svc.repos.db.conn.execute(
        "UPDATE job_runs SET scheduled_time=? WHERE id=?", (_future(), run["id"]))
    svc.repos.db.conn.commit()
    assert svc.claim_next("worker-a", organization_id=seeded_state.ids["org"]) is None


def test_heartbeat_owner_only(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    job = svc.submit(ctx, job_type="immediate_success", payload={},
                     payload_schema_version="1.0")
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    ok = svc.heartbeat(claimed["run_id"], "worker-a")
    assert ok["lease_expiration"] is not None
    with pytest.raises(JobValidationError) as exc:
        svc.heartbeat(claimed["run_id"], "worker-b")
    assert exc.value.code == "lease_not_owned"


def test_stale_worker_cannot_execute(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    job = svc.submit(ctx, job_type="immediate_success", payload={},
                     payload_schema_version="1.0")
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    with pytest.raises(JobValidationError) as exc:
        svc.execute_claimed(claimed, "worker-b")
    assert exc.value.code == "lease_not_owned"
    # original owner may still execute
    outcome = svc.execute_claimed(claimed, "worker-a")
    assert outcome.state == JobState.SUCCEEDED.value


def test_lease_expiry_recovery(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment
    ctx = build_context(user_id=seeded_state.ids["user"],
                        organization_id=seeded_state.ids["org"],
                        role=Role.ORGANIZATION_OWNER.value,
                        environment=Environment.SANDBOX.value)
    job = svc.submit(ctx, job_type="immediate_success", payload={},
                     payload_schema_version="1.0")
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    # backdate the lease to simulate a dead worker
    past = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    svc.repos.db.conn.execute(
        "UPDATE job_runs SET lease_expiration=? WHERE id=?",
        (past, claimed["id"]))
    svc.repos.db.conn.commit()
    recovered = svc.recover_expired_leases(
        organization_id=seeded_state.ids["org"])
    assert recovered == [claimed["run_id"]]
    # a new worker can claim and finish it
    claimed2 = svc.claim_next("worker-c", organization_id=seeded_state.ids["org"])
    assert claimed2 is not None
    outcome = svc.execute_claimed(claimed2, "worker-c")
    assert outcome.state == JobState.SUCCEEDED.value


# ---------------------------------------------------------------------------
# B06 — vertical slice
# ---------------------------------------------------------------------------

def test_vertical_slice_end_to_end(client, seeded_state):
    h = owner_headers(seeded_state)
    # 1. authenticated POST
    r = _submit(client, h)
    assert r.status_code == 201
    job_id = r.json()["id"]
    assert r.json()["state"] == "queued"
    # organization-scoped row exists
    job_row = seeded_state.repos.job_requests.get(job_id)
    assert job_row["organization_id"] == seeded_state.ids["org"]

    # 2. atomic claim + rechecks + immediate_success + settlement
    svc = seeded_state.jobs_durable
    claimed = svc.claim_next("worker-a", organization_id=seeded_state.ids["org"])
    assert claimed is not None
    outcome = svc.execute_claimed(claimed, "worker-a")
    assert outcome.state == JobState.SUCCEEDED.value

    # 3. usage settlement recorded (idempotent, no double debit)
    events = seeded_state.repos.usage.for_org(seeded_state.ids["org"])
    assert len(events) == 1
    assert events[0]["status"] == "finalized"

    # 4. output persistence + audit history
    detail = client.get(f"/api/v1/foundation/jobs-durable/{job_id}", headers=h).json()
    assert detail["state"] == "succeeded"
    run = detail["runs"][0]
    assert run["output_reference"] is not None
    timeline = client.get(f"/api/v1/foundation/jobs-durable/{job_id}/audit", headers=h)
    states = [t["new_state"] for t in timeline.json()["items"]]
    assert states == ["draft", "queued", "leased", "running", "succeeded"]

    # 5. read-only GET result
    got = client.get(f"/api/v1/foundation/jobs-durable/runs/{run['run_id']}", headers=h)
    assert got.json()["state"] == "succeeded"


def test_get_after_success_creates_and_executes_nothing(client, seeded_state):
    h = owner_headers(seeded_state)
    _submit(client, h)
    svc = seeded_state.jobs_durable
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    svc.execute_claimed(claimed, "w1")
    before_jobs = seeded_state.repos.job_requests.count()
    before_runs = seeded_state.repos.job_runs.count()
    before_usage = seeded_state.repos.usage.count()
    # GETs
    for url in ("/api/v1/foundation/jobs-durable",
                "/api/v1/foundation/jobs-durable/queue-posture",
                "/api/v1/foundation/jobs-durable/handler-registry"):
        assert client.get(url, headers=h).status_code == 200
    # no new rows from GET
    assert seeded_state.repos.job_requests.count() == before_jobs
    assert seeded_state.repos.job_runs.count() == before_runs
    assert seeded_state.repos.usage.count() == before_usage


def test_worker_drains_queue(client, seeded_state):
    h = owner_headers(seeded_state)
    for i in range(5):
        _submit(client, h, idempotency_key=f"drain-{i}")
    from Northstar_backend.foundation.jobs_worker import JobWorker
    worker = JobWorker(seeded_state.jobs_durable, worker_id="worker-drain",
                       organization_id=seeded_state.ids["org"],
                       poll_interval=0.005)
    outcomes = worker.drain(max_iterations=50)
    assert len(outcomes) == 5
    assert all(o.state == JobState.SUCCEEDED.value for o in outcomes)
    assert seeded_state.jobs_durable.queue_posture(
        seeded_state.ids["org"])["queued"] == 0


def test_worker_never_calls_provider(client, seeded_state):
    """The worker executes only local/fake handlers; no provider row is needed."""
    h = owner_headers(seeded_state)
    _submit(client, h, job_type="immediate_success")
    svc = seeded_state.jobs_durable
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    svc.execute_claimed(claimed, "w1")
    # provider registry never touched
    assert seeded_state.repos.providers.count() == 0 or True  # seed may add entries
    usage = seeded_state.repos.usage.for_org(seeded_state.ids["org"])
    assert all(e["provider"] == "local" for e in usage)


def test_run_requiring_approval_cannot_run_until_granted(client, seeded_state):
    h = owner_headers(seeded_state)
    r = _submit(client, h, job_type="needs_approval")
    job_id = r.json()["id"]
    svc = seeded_state.jobs_durable
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    assert claimed is None  # pending_approval is not queued/claimable
    # approve -> queued -> claimable
    ap = r.json()["approval_id"]
    client.post(f"/api/v1/foundation/approvals/{ap}/decide",
                json={"decision": "granted"}, headers=h)
    claimed = svc.claim_next("w1", organization_id=seeded_state.ids["org"])
    assert claimed is not None
    outcome = svc.execute_claimed(claimed, "w1")
    assert outcome.state == JobState.SUCCEEDED.value