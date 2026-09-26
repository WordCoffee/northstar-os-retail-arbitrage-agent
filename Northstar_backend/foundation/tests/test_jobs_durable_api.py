"""Durable job API tests (1C-04 / B04).

Authenticated, organization-scoped job submission with server-side validation,
org-scoped idempotency, approval gating, read-only GETs with zero side effects,
and mutation guards (cancel/retry). Zero provider calls, zero job execution in
the request path.
"""
from __future__ import annotations

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.tests.conftest import (
    owner_headers, make_access_token, bearer,
)


def _submit(client, headers, *, job_type="immediate_success", **kw):
    body = {"job_type": job_type,
            "payload_schema_version": kw.pop("payload_schema_version", "1.0"),
            "payload": kw.pop("payload", {"n": 1})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


def test_submit_creates_org_scoped_queued_job(client, seeded_state):
    r = _submit(client, owner_headers(seeded_state))
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["state"] == "queued"
    assert job["job_type"] == "immediate_success"
    assert job["organization_id"] == seeded_state.ids["org"]
    assert job["estimated_cost"] is not None
    # one initial run, mirrored state
    assert len(job["runs"]) == 1
    assert job["runs"][0]["state"] == "queued"


def test_submit_unknown_job_type_fails_closed(client, seeded_state):
    r = _submit(client, owner_headers(seeded_state), job_type="does_not_exist")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unknown_job_type"


def test_submit_unsupported_payload_schema_rejected(client, seeded_state):
    r = _submit(client, owner_headers(seeded_state),
                payload_schema_version="999.0")
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "unsupported_payload_schema"


def test_submit_requires_authentication(client, seeded_state):
    r = _submit(client, {})
    assert r.status_code == 401


def test_submit_org_scoped_idempotency(client, seeded_state):
    h = owner_headers(seeded_state)
    a = _submit(client, h, idempotency_key="idem-1")
    b = _submit(client, h, idempotency_key="idem-1")
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] == b.json()["id"]
    rows = seeded_state.repos.job_requests.list(
        where={"organization_id": seeded_state.ids["org"]})
    assert len(rows) == 1


def test_submit_cross_organization_denied(client, seeded_state):
    other = Organization(name="Other", slug="other")
    seeded_state.repos.organizations.add(other)
    h = {**owner_headers(seeded_state), "X-Org-Id": other.id}
    r = _submit(client, h)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "cross_organization_access_denied"


def test_approval_required_goes_pending_and_promotes(client, seeded_state):
    h = owner_headers(seeded_state)
    r = _submit(client, h, job_type="needs_approval")
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["state"] == "pending_approval"
    assert job["requires_approval"] is True
    assert job["approval_id"]
    # list approvals
    approvals = client.get("/api/v1/foundation/approvals", headers=h).json()["items"]
    assert any(a["id"] == job["approval_id"] for a in approvals)
    # approve
    resp = client.post(
        f"/api/v1/foundation/approvals/{job['approval_id']}/decide",
        json={"decision": "granted", "note": "approved for test"}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.json()["promoted_jobs"] == [job["id"]]
    detail = client.get(f"/api/v1/foundation/jobs-durable/{job['id']}", headers=h)
    assert detail.json()["state"] == "queued"


def test_get_list_detail_run_audit_read_only(client, seeded_state):
    h = owner_headers(seeded_state)
    before = seeded_state.repos.job_requests.count()
    before_runs = seeded_state.repos.job_runs.count()
    before_history = seeded_state.repos.job_state_history.count()

    r = _submit(client, h)
    job_id = r.json()["id"]
    run_id = r.json()["runs"][0]["run_id"]

    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    assert client.get(f"/api/v1/foundation/jobs-durable/{job_id}", headers=h).status_code == 200
    assert client.get(f"/api/v1/foundation/jobs-durable/runs/{run_id}", headers=h).status_code == 200
    assert client.get(f"/api/v1/foundation/jobs-durable/{job_id}/audit", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/jobs-durable/queue-posture", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/jobs-durable/handler-registry", headers=h).status_code == 200

    # GET created no jobs, runs, or history; executed nothing
    assert seeded_state.repos.job_requests.count() == before + 1
    assert seeded_state.repos.job_runs.count() == before_runs + 1
    assert seeded_state.repos.job_state_history.count() == before_history + 2  # creation + queue


def test_cross_org_job_detail_denied(client, seeded_state):
    h = owner_headers(seeded_state)
    job_id = _submit(client, h).json()["id"]
    other = Organization(name="Other", slug="other")
    user = User(email="other@example.test")
    seeded_state.repos.organizations.add(other)
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.OPERATOR.value))
    token = make_access_token(user.id, org=other.id, role="operator")
    r = client.get(f"/api/v1/foundation/jobs-durable/{job_id}", headers=bearer(token))
    assert r.status_code == 404  # org-scoped: not found, not leaked


def test_cancel_queued_job(client, seeded_state):
    h = owner_headers(seeded_state)
    job_id = _submit(client, h).json()["id"]
    r = client.post(f"/api/v1/foundation/jobs-durable/{job_id}/cancel",
                    json={"reason": "changed mind"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "cancelled"
    detail = client.get(f"/api/v1/foundation/jobs-durable/{job_id}", headers=h).json()
    assert detail["state"] == "cancelled"
    timeline = client.get(f"/api/v1/foundation/jobs-durable/{job_id}/audit", headers=h).json()
    states = [t["new_state"] for t in timeline["items"]]
    assert "cancelled" in states


def test_retry_only_for_failed_or_dead_letter(client, seeded_state):
    h = owner_headers(seeded_state)
    job_id = _submit(client, h).json()["id"]
    r = client.post(f"/api/v1/foundation/jobs-durable/{job_id}/retry",
                    json={"reason": "retry"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "not_retryable"


def test_viewer_cannot_submit(client, seeded_state):
    user = User(email="viewer@example.test")
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=seeded_state.ids["org"], user_id=user.id,
        role=Role.VIEWER.value))
    token = make_access_token(user.id, org=seeded_state.ids["org"], role="viewer")
    r = _submit(client, bearer(token))
    assert r.status_code == 403


def test_operator_cannot_cancel_other_org_job(client, seeded_state):
    h = owner_headers(seeded_state)
    job_id = _submit(client, h).json()["id"]
    other = Organization(name="Other", slug="other")
    user = User(email="op@example.test")
    seeded_state.repos.organizations.add(other)
    seeded_state.repos.users.add(user)
    seeded_state.repos.memberships.add(Membership(
        organization_id=other.id, user_id=user.id, role=Role.OPERATOR.value))
    token = make_access_token(user.id, org=other.id, role="operator")
    r = client.post(f"/api/v1/foundation/jobs-durable/{job_id}/cancel",
                    json={"reason": "x"}, headers=bearer(token))
    assert r.status_code in (403, 404)


def test_handler_registry_only_local(client, seeded_state):
    r = client.get("/api/v1/foundation/jobs-durable/handler-registry",
                   headers=owner_headers(seeded_state))
    data = r.json()
    assert data["only_local_handlers"] is True
    types = {h["job_type"] for h in data["handlers"]}
    for t in ("immediate_success", "slow_success", "transient_failure",
              "permanent_failure", "timeout", "rate_limit", "malformed_output",
              "cancellable", "cost_variance", "needs_approval"):
        assert t in types


def test_submission_never_executes(client, seeded_state):
    """Submitting creates rows only — the run stays queued (never runs)."""
    h = owner_headers(seeded_state)
    r = _submit(client, h, job_type="slow_success")
    assert r.status_code == 201
    detail = client.get(f"/api/v1/foundation/jobs-durable/{r.json()['id']}", headers=h).json()
    assert detail["runs"][0]["state"] == "queued"
    assert detail["runs"][0]["lease_owner"] is None
    assert seeded_state.repos.job_runs.count() == 1
    assert seeded_state.repos.usage.count() == 0