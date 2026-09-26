"""1C-04 FINAL GATE — durable execution end-to-end acceptance (1C-04 / B16).

A single compact acceptance surface exercising the full production path:
submission -> approval -> claim -> rechecks -> execution -> settlement ->
output -> audit, plus retry/dead-letter/manual-retry, organization isolation,
GET-side-effect guarantees, and the fake/local-only handler rule.

Passing this gate (with the state machine, migration, claim, concurrency, and
scheduler suites) satisfies the 1C-04 gate criteria.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Environment, Role, ApprovalState
from Northstar_backend.foundation.jobs_durable import DurableJobService
from Northstar_backend.foundation.jobs_state import JobState
from Northstar_backend.foundation.jobs_worker import JobWorker
from Northstar_backend.foundation.models import (
    Organization, User, Membership, OrgBalance,
)
from Northstar_backend.foundation.tests.conftest import owner_headers


def _ctx(seeded_state):
    return build_context(user_id=seeded_state.ids["user"],
                         organization_id=seeded_state.ids["org"],
                         role=Role.ORGANIZATION_OWNER.value,
                         environment=Environment.PRODUCTION.value)


def _submit(client, headers, **kw):
    body = {"job_type": kw.pop("job_type", "immediate_success"),
            "payload_schema_version": "1.0", "payload": kw.pop("payload", {})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


def test_gate_approval_claim_execute_audit_full_path(client, seeded_state):
    """DRAFT -> PENDING_APPROVAL -> QUEUED -> LEASED -> RUNNING -> SUCCEEDED,
    with audit completeness at every consequential event."""
    h = owner_headers(seeded_state)
    r = _submit(client, h, job_type="needs_approval")
    job_id = r.json()["id"]
    assert r.json()["state"] == "pending_approval"
    # approve
    resp = client.post(
        f"/api/v1/foundation/approvals/{r.json()['approval_id']}/decide",
        json={"decision": "granted"}, headers=h)
    assert resp.json()["promoted_jobs"] == [job_id]
    svc = seeded_state.jobs_durable
    claimed = svc.claim_next("gate-worker", organization_id=seeded_state.ids["org"])
    out = svc.execute_claimed(claimed, "gate-worker")
    assert out.state == JobState.SUCCEEDED.value
    # audit completeness: every consequential transition is in the timeline
    timeline = client.get(f"/api/v1/foundation/jobs-durable/{job_id}/audit",
                          headers=h).json()["items"]
    states = [t["new_state"] for t in timeline]
    assert states == ["draft", "pending_approval", "queued", "leased",
                      "running", "succeeded"]
    # run detail reflects output + settlement
    detail = client.get(f"/api/v1/foundation/jobs-durable/{job_id}", headers=h).json()
    assert detail["runs"][0]["output_reference"] is not None
    # usage settlement (idempotent, single finalize)
    finalized = [e for e in seeded_state.repos.usage.for_org(seeded_state.ids["org"])
                 if e["status"] == "finalized"]
    assert len(finalized) == 1


def test_gate_transient_retry_then_success(client, seeded_state):
    svc = seeded_state.jobs_durable
    _submit(client, owner_headers(seeded_state), job_type="transient_failure",
            payload={"succeed_on_attempt": 2})
    claimed = svc.claim_next("w", organization_id=seeded_state.ids["org"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == JobState.RETRY_WAIT.value
    job = svc.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})[0]
    run = svc.repos.job_runs.by_request(job["id"])[0]
    svc.repos.db.conn.execute(
        "UPDATE job_runs SET scheduled_time=? WHERE id=?",
        ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
    svc.repos.db.conn.commit()
    svc._transition(job=job, run=run, new_state=JobState.QUEUED.value,
                    actor="scheduler", reason="backoff elapsed")
    claimed2 = svc.claim_next("w", organization_id=seeded_state.ids["org"])
    out2 = svc.execute_claimed(claimed2, "w")
    assert out2.state == JobState.SUCCEEDED.value
    # financial integrity: one successful job -> exactly ONE settled ledger
    # entry (the failed attempt only released its reservation)
    finalized = [e for e in seeded_state.repos.usage.for_org(seeded_state.ids["org"])
                 if e["status"] == "finalized"]
    assert len(finalized) == 1


def test_gate_dead_letter_then_authorized_retry(client, seeded_state):
    svc = seeded_state.jobs_durable
    job = _submit(client, owner_headers(seeded_state), job_type="transient_failure",
                  payload={"succeed_on_attempt": 99}).json()
    from Northstar_backend.foundation.jobs_state import JobState as JS
    for _ in range(4):
        claimed = svc.claim_next("w", organization_id=seeded_state.ids["org"])
        if claimed is None:
            break
        out = svc.execute_claimed(claimed, "w")
        if out.state == JS.DEAD_LETTER.value:
            break
        j = svc.repos.job_requests.get(job["id"])
        run = svc.repos.job_runs.by_request(job["id"])[0]
        svc.repos.db.conn.execute(
            "UPDATE job_runs SET scheduled_time=? WHERE id=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat(), run["id"]))
        svc.repos.db.conn.commit()
        svc._transition(job=j, run=run, new_state=JS.QUEUED.value,
                        actor="scheduler", reason="backoff elapsed")
    assert out.state == JS.DEAD_LETTER.value
    # simulate the underlying condition being fixed, then authorized manual
    # retry -> new run -> success
    svc.repos.db.conn.execute(
        "UPDATE job_requests SET payload=? WHERE id=?",
        ('{"succeed_on_attempt": 1}', job["id"]))
    svc.repos.db.conn.commit()
    svc.retry(_ctx(seeded_state), job["id"], reason="gate manual retry")
    worker = JobWorker(svc, worker_id="gate-w", organization_id=seeded_state.ids["org"])
    worker.drain(max_iterations=5)
    assert svc.get_job(seeded_state.ids["org"], job["id"])["state"] == JS.SUCCEEDED.value


def test_gate_organization_isolation(client, seeded_state):
    h = owner_headers(seeded_state)
    other = Organization(name="Other", slug="other")
    user = User(email="other@example.test")
    seeded_state.repos.organizations.add(other)
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.OPERATOR.value))
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    token = make_access_token(user.id, org=other.id, role="operator")
    # list for the OTHER org must not see org-A jobs
    _submit(client, h)
    r = client.get("/api/v1/foundation/jobs-durable", headers=bearer(token))
    assert r.status_code == 200 and r.json()["items"] == []
    # detail is 404 (not leaked)
    job_id = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})[0]["id"]
    assert client.get(f"/api/v1/foundation/jobs-durable/{job_id}",
                      headers=bearer(token)).status_code == 404


def test_gate_get_side_effect_audit(client, seeded_state):
    h = owner_headers(seeded_state)
    _submit(client, h)
    before_jobs = seeded_state.repos.job_requests.count()
    before_runs = seeded_state.repos.job_runs.count()
    before_usage = seeded_state.repos.usage.count()
    for url in ("/api/v1/foundation/jobs-durable",
                "/api/v1/foundation/jobs-durable/queue-posture",
                "/api/v1/foundation/jobs-durable/handler-registry",
                "/api/v1/foundation/schedules/posture"):
        assert client.get(url, headers=h).status_code == 200
    assert seeded_state.repos.job_requests.count() == before_jobs
    assert seeded_state.repos.job_runs.count() == before_runs
    assert seeded_state.repos.usage.count() == before_usage


def test_gate_only_local_handlers_execute(seeded_state):
    svc = DurableJobService(seeded_state.repos)
    reg = svc.registry.metadata()
    assert all(h["provider_class"] in ("local", "fixture") for h in reg)
    assert all(h["required_permission"] == "run_local" for h in reg)
    with pytest.raises(Exception):
        svc.submit(_ctx(seeded_state), job_type="remote_external",
                   payload={}, payload_schema_version="1.0")


def test_gate_blocked_job_releases_reservation(client, seeded_state):
    svc = seeded_state.jobs_durable
    svc.grant(seeded_state.ids["org"], Decimal("100.00"))
    _submit(client, owner_headers(seeded_state), job_type="immediate_success",
            payload={"est": 50})
    rows = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})
    seeded_state.repos.db.conn.execute(
        "UPDATE job_requests SET estimated_cost=? WHERE id=?", (50.0, rows[0]["id"]))
    seeded_state.repos.db.conn.commit()
    # revoke membership -> blocked before execution; reservation never held
    seeded_state.repos.db.conn.execute(
        "UPDATE memberships SET status='revoked' WHERE user_id=? AND organization_id=?",
        (seeded_state.ids["user"], seeded_state.ids["org"]))
    seeded_state.repos.db.conn.commit()
    claimed = svc.claim_next("w", organization_id=seeded_state.ids["org"])
    out = svc.execute_claimed(claimed, "w")
    assert out.state == JobState.BLOCKED_AUTHORIZATION.value
    bal = svc._balance(seeded_state.ids["org"])
    assert bal.reserved == 0 and bal.consumed == 0