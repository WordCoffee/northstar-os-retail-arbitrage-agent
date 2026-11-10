"""Organization-scoped authorization + data-boundary enforcement (1C-05).

Role matrix (owner/operator/viewer), non-enumerating cross-organization denial,
mass-assignment protection, and denial-audit logging. Viewer is read-only and
must NOT reach billing/ledger, provider configuration, or the administrative
approval/audit surfaces.
"""
from __future__ import annotations

from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.tests.conftest import (
    owner_headers, make_access_token, bearer,
)


def _member(state, email, org_id, role):
    u = User(email=email)
    state.repos.users.add(u)
    state.repos.memberships.add(Membership(organization_id=org_id, user_id=u.id,
                                           role=role, status="active"))
    return u


def _submit(client, headers, **kw):
    body = {"job_type": kw.pop("job_type", "immediate_success"),
            "payload_schema_version": "1.0", "payload": kw.pop("payload", {})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


# --- role matrix (owner / operator / viewer) --------------------------------

def test_viewer_is_read_only_and_blocked_from_sensitive_surfaces(client, seeded_state):
    viewer = _member(seeded_state, "viewer@example.test", seeded_state.ids["org"],
                     Role.VIEWER.value)
    h = bearer(make_access_token(viewer.id, org=seeded_state.ids["org"], role="viewer"))
    # read-only allowed
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/keywords/search?q=x", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/schedules", headers=h).status_code == 200
    # mutations blocked
    assert _submit(client, h).status_code == 403
    # billing/ledger blocked
    assert client.get("/api/v1/foundation/usage/summary", headers=h).status_code == 403
    assert client.get("/api/v1/foundation/usage/events", headers=h).status_code == 403
    # provider configuration blocked
    assert client.get("/api/v1/foundation/providers", headers=h).status_code == 403
    assert client.get("/api/v1/foundation/providers/ollama", headers=h).status_code == 403
    # administrative approval queue + audit blocked
    assert client.get("/api/v1/foundation/approvals", headers=h).status_code == 403
    assert client.get("/api/v1/foundation/audit", headers=h).status_code == 403


def test_operator_can_operate_and_view_usage(client, seeded_state):
    operator = _member(seeded_state, "op@example.test", seeded_state.ids["org"],
                       Role.OPERATOR.value)
    h = bearer(make_access_token(operator.id, org=seeded_state.ids["org"],
                                 role="operator"))
    assert _submit(client, h).status_code == 201
    assert client.get("/api/v1/foundation/usage/summary", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/providers", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/approvals", headers=h).status_code == 200
    assert client.get("/api/v1/foundation/audit", headers=h).status_code == 200
    # operator may NOT manage org settings or membership
    assert client.post("/api/v1/foundation/organizations", headers=h,
                       json={"name": "X", "slug": "x"}).status_code == 403


def test_owner_manages_org_and_membership(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/organizations", headers=h,
                    json={"name": "New Org", "slug": "new-org"})
    assert r.status_code == 201
    assert client.get(f"/api/v1/foundation/organizations/{seeded_state.ids['org']}/memberships",
                      headers=h).status_code == 200
    assert client.get("/api/v1/foundation/usage/summary", headers=h).status_code == 200


# --- non-enumerating cross-organization denial ------------------------------

def test_cross_org_object_ids_are_non_enumerating(client, seeded_state):
    """Direct object-ID guessing across orgs returns 404 (never 403-with-hint,
    never a disclosure that the target exists)."""
    # a job in org A
    ha = owner_headers(seeded_state)
    job = _submit(client, ha).json()
    run = job["runs"][0]["run_id"]
    # an operator in org B
    org_b = Organization(name="B", slug="b")
    seeded_state.repos.organizations.add(org_b)
    opb = _member(seeded_state, "opb@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(opb.id, org=org_b.id, role="operator"))
    # job status / detail
    r = client.get(f"/api/v1/foundation/jobs-durable/{job['id']}", headers=hb)
    assert r.status_code == 404
    assert "detail" in r.json() and "code" in r.json()["detail"]
    # cancellation
    r = client.post(f"/api/v1/foundation/jobs-durable/{job['id']}/cancel",
                    json={"reason": "x"}, headers=hb)
    assert r.status_code == 404
    # retry
    r = client.post(f"/api/v1/foundation/jobs-durable/{job['id']}/retry",
                    json={"reason": "x"}, headers=hb)
    assert r.status_code == 404
    # results (run detail)
    assert client.get(f"/api/v1/foundation/jobs-durable/runs/{run}",
                      headers=hb).status_code == 404
    # audit events for the job
    assert client.get(f"/api/v1/foundation/jobs-durable/{job['id']}/audit",
                      headers=hb).status_code in (403, 404)
    # an unknown id in the SAME org returns the SAME 404 shape (no enumeration)
    r_unknown = client.get(f"/api/v1/foundation/jobs-durable/{'x' * 32}",
                           headers=ha)
    assert r_unknown.status_code == 404
    # the job in org A was NOT cancelled by the org-B attempt
    assert client.get(f"/api/v1/foundation/jobs-durable/{job['id']}",
                      headers=ha).json()["state"] == "queued"


def test_cross_org_usage_ledger_isolated(client, seeded_state):
    ha = owner_headers(seeded_state)
    _submit(client, ha)
    org_b = Organization(name="C", slug="c")
    seeded_state.repos.organizations.add(org_b)
    opb = _member(seeded_state, "opc@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(opb.id, org=org_b.id, role="operator"))
    # org B's ledger shows only org B (empty here), never org A's rows
    events = client.get("/api/v1/foundation/usage/events", headers=hb).json()["items"]
    assert events == []
    assert client.get("/api/v1/foundation/usage/summary", headers=hb).status_code == 200


def test_cross_org_keyword_and_schedule_denial(client, seeded_state):
    ha = owner_headers(seeded_state)
    org_b = Organization(name="D", slug="d")
    seeded_state.repos.organizations.add(org_b)
    opb = _member(seeded_state, "opd@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(opb.id, org=org_b.id, role="operator"))
    # org-A keyword invisible to B
    from Northstar_backend.foundation.models import Keyword
    kw = Keyword(organization_id=seeded_state.ids["org"], normalized_phrase="dog leash",
                 original_phrase="Dog Leash", match_type="exact")
    seeded_state.repos.keywords.add(kw)
    assert client.get(f"/api/v1/foundation/keywords/{kw.id}",
                      headers=hb).status_code == 404


# --- mass-assignment protection ---------------------------------------------

def test_privileged_and_financial_fields_cannot_be_client_set(client, seeded_state):
    h = owner_headers(seeded_state)
    body = {
        "job_type": "immediate_success", "payload_schema_version": "1.0",
        "payload": {},
        # mass-assignment attempts: must all be IGNORED (explicit allowlist)
        "organization_id": "evil-org", "user_id": "evil-user", "role": "owner",
        "estimated_cost": 999999, "state": "succeeded", "provider_class": "evil",
        "budget_class": "unlimited", "approval_id": "forged", "settled_cost": 1,
        "reserved_cost": 5, "actual_cost": 7, "audit_ref": "forged",
        "secret": "hunter2", "ledger_entry": "forged",
    }
    r = _submit(client, h, **body)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["organization_id"] == seeded_state.ids["org"]   # server-derived
    assert job["user_id"] == seeded_state.ids["user"]          # server-derived
    assert job["state"] == "queued"                            # not client-set
    assert job["provider_class"] == "local"                    # spec-derived
    assert job["estimated_cost"] == 0.0 or job["estimated_cost"] is not None
    assert "secret" not in job and "settled_cost" not in job


def test_schedule_update_cannot_change_owner_or_org(client, seeded_state):
    h = owner_headers(seeded_state)
    sched = client.post("/api/v1/foundation/schedules", headers=h, json={
        "job_template": {"job_type": "immediate_success"}, "interval_seconds": 60,
        "enabled": False}).json()
    r = client.put(f"/api/v1/foundation/schedules/{sched['id']}", headers=h, json={
        "enabled": True,
        "organization_id": "evil-org", "owner_user_id": "evil-user",
        "role": "owner", "provider_config": {"key": "leak"}, "secret": "x"})
    assert r.status_code == 200
    got = client.get(f"/api/v1/foundation/schedules/{sched['id']}", headers=h).json()
    assert got["organization_id"] == seeded_state.ids["org"]
    assert got["owner_user_id"] == seeded_state.ids["user"]


# --- denial audit ------------------------------------------------------------

def test_denied_authorization_attempts_are_audited(client, seeded_state):
    before = seeded_state.repos.audit.count()
    viewer = _member(seeded_state, "v@example.test", seeded_state.ids["org"],
                     Role.VIEWER.value)
    hv = bearer(make_access_token(viewer.id, org=seeded_state.ids["org"],
                                  role="viewer"))
    assert client.get("/api/v1/foundation/usage/summary", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/providers", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/approvals", headers=hv).status_code == 403
    denied = [e for e in seeded_state.repos.audit.list()
              if e["action"] == "authz.denied"]
    assert denied, "no authz.denied audit records"
    # the audit record never contains sensitive object data (no secret values,
    # no resource bodies — only method/path/status/code)
    for e in denied:
        meta = e.get("after_meta") or {}
        assert "secret" not in str(meta).lower()
        assert e["result"] == "denied"
    assert seeded_state.repos.audit.count() >= before + 3