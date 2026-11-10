"""1C-06 subscriber rules & operations (Phases A-D).

Plan & usage view (role-aware), lifecycle state machine, admin tools
(grant/plan/suspend/resume/downgrade/cancel/notes/override), onboarding pack,
support tickets with tester-visible/internal note separation, and org
isolation. Entitlement checks flow ONLY through the centralized service.
"""
from __future__ import annotations

import uuid as _uuid

import pytest

from Northstar_backend.foundation.billing import processor as proc
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.models import Organization, Membership, User
from Northstar_backend.foundation.operations import lifecycle as lc
from Northstar_backend.foundation.tests.conftest import (
    owner_headers, make_access_token, bearer,
)


def _member(state, email, org_id, role):
    u = User(email=email)
    state.repos.users.add(u)
    state.repos.memberships.add(Membership(organization_id=org_id, user_id=u.id,
                                           role=role, status="active"))
    return u


def _platform(state, org_id):
    return _member(state, "platform@example.test", org_id,
                   Role.INTERNAL_PLATFORM_ADMIN.value)


def _submit(client, headers, **kw):
    body = {"job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": kw.pop("payload", {})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


def _signed_checkout(client, h, price_id, event_id, org):
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": price_id}, headers=h).json()
    event = proc.build_event(event_id=event_id,
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id=f"cus_{event_id}",
                             subscription_id=f"sub_{event_id}",
                             price_id=price_id)
    return client.post("/api/v1/foundation/billing/webhook",
                       json={"payload": event,
                             "signature": proc.sign_event(event, proc.webhook_secret())})


# --- Phase A: plan & usage view ------------------------------------------------

def test_plan_usage_owner_operator_viewer_visibility(client, seeded_state):
    owner = _member(seeded_state, "owner@example.test", seeded_state.ids["org"],
                    Role.ORGANIZATION_OWNER.value)
    op = _member(seeded_state, "op@example.test", seeded_state.ids["org"],
                 Role.OPERATOR.value)
    viewer = _member(seeded_state, "v@example.test", seeded_state.ids["org"],
                     Role.VIEWER.value)
    ho = bearer(make_access_token(owner.id, org=seeded_state.ids["org"],
                                  role="organization_owner"))
    hop = bearer(make_access_token(op.id, org=seeded_state.ids["org"], role="operator"))
    hv = bearer(make_access_token(viewer.id, org=seeded_state.ids["org"], role="viewer"))
    # owner: full view
    r = client.get("/api/v1/foundation/plan-usage", headers=ho)
    assert r.status_code == 200
    body = r.json()
    assert "usage" in body and "seats" in body and "lifecycle_state" in body
    assert body["plan"]["tier"] == "free"
    assert body["usage"]["max_jobs_per_month"] == 1000
    # operator: usage visible
    assert client.get("/api/v1/foundation/plan-usage", headers=hop).json()["usage"]
    # viewer: restricted (no usage/seats/limits)
    v = client.get("/api/v1/foundation/plan-usage", headers=hv).json()
    assert v["role_restricted"] is True
    assert "usage" not in v and "seats" not in v


def test_plan_change_affects_next_check(client, seeded_state):
    h = owner_headers(seeded_state)
    platform = _platform(seeded_state, seeded_state.ids["org"])
    hp = bearer(make_access_token(platform.id, org=seeded_state.ids["org"],
                                  role="internal_platform_admin"))
    # subscribe to trial (5 jobs) via webhook
    _signed_checkout(client, h, "price_trial", "evt_plan_1", seeded_state.ids["org"])
    for i in range(5):
        assert _submit(client, h, idempotency_key=f"pl-{i}").status_code == 201
    assert _submit(client, h).status_code == 403  # trial limit reached
    # admin changes plan to free -> the NEXT check allows a job (free limit)
    r = client.post(f"/api/v1/foundation/admin/orgs/{seeded_state.ids['org']}/plan",
                    headers=hp, json={"cohort": "free", "reason": "test"})
    assert r.status_code == 200
    assert client.get("/api/v1/foundation/plan-usage",
                      headers=h).json()["plan"]["tier"] == "free"
    assert _submit(client, h).status_code == 201  # next check sees the new plan


def test_denial_reason_non_leaky(client, seeded_state):
    h = owner_headers(seeded_state)
    _signed_checkout(client, h, "price_trial", "evt_dl_1", seeded_state.ids["org"])
    for i in range(5):
        _submit(client, h, idempotency_key=f"dl-{i}")
    r = _submit(client, h)
    assert r.status_code == 403
    d = r.json()["detail"]
    assert d["code"] == "entitlement_denied"
    # non-leaky: no other org's data, no tier disclosure beyond the plan view
    assert "example" not in d["message"].lower() or "account" in d["message"]
    # the plan view explains the denial
    pu = client.get("/api/v1/foundation/plan-usage", headers=h).json()
    assert pu["usage"]["monthly_jobs_used"] == 5


# --- Phase B: lifecycle state machine -----------------------------------------

def test_lifecycle_state_machine_valid_and_invalid(client, seeded_state):
    org = seeded_state.ids["org"]
    svc = seeded_state.lifecycle
    svc.initialize(org, actor="u", reason="org created")
    assert svc.current_state(org) == lc.INVITED
    # ILLEGAL: invited -> active (must pass through onboarding)
    with pytest.raises(Exception) as e:
        svc.set_state(org, lc.ACTIVE, actor="u", reason="x", transition=True)
    assert e.value.code == "illegal_transition"
    svc.transition(org, to_state=lc.ONBOARDING, actor="u", reason="accepted")
    svc.transition(org, to_state=lc.ACTIVE, actor="u", reason="onboarded")
    assert svc.current_state(org) == lc.ACTIVE
    svc.transition(org, to_state=lc.SUSPENDED, actor="u", reason="abuse")
    assert svc.current_state(org) == lc.SUSPENDED
    # history is append-only with actor/prior/new/reason
    hist = svc.history(org)
    states = [h["new_state"] for h in hist]
    assert states == ["invited", "onboarding", "active", "suspended"]
    assert all(h["actor"] == "u" for h in hist)


def test_suspension_blocks_next_authenticated_request(client, seeded_state):
    org = seeded_state.ids["org"]
    h = owner_headers(seeded_state)
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    seeded_state.lifecycle.set_state(org, lc.SUSPENDED, actor="admin", reason="test")
    # the NEXT authenticated request is blocked
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 403
    # resume restores access
    seeded_state.lifecycle.set_state(org, lc.ACTIVE, actor="admin", reason="ok")
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200


def test_invite_reissue_expire_revoke_non_enumeration(client, seeded_state):
    h = owner_headers(seeded_state)
    inv = client.post("/api/v1/foundation/invites", headers=h,
                      json={"email": "t@example.test",
                            "role": Role.OPERATOR.value}).json()
    row = seeded_state.repos.invites.get(inv["invite_id"])
    # reissue: a second pending invite for the same email is rejected
    r2 = client.post("/api/v1/foundation/invites", headers=h,
                     json={"email": "t@example.test",
                           "role": Role.VIEWER.value})
    assert r2.status_code == 400 and r2.json()["detail"]["code"] == "invite_pending"
    # expire -> signup denied (non-revealing)
    seeded_state.db.conn.execute(
        "UPDATE invites SET status='expired' WHERE id=?", (inv["invite_id"],))
    seeded_state.db.conn.commit()
    r3 = client.post("/api/v1/foundation/signup",
                     json={"email": "t@example.test", "invite_code": row["invite_code"]})
    assert r3.status_code == 403 and r3.json()["detail"]["code"] == "signup_denied"
    # revoke -> denied
    seeded_state.db.conn.execute(
        "UPDATE invites SET status='pending' WHERE id=?", (inv["invite_id"],))
    seeded_state.db.conn.commit()
    client.post(f"/api/v1/foundation/invites/{inv['invite_id']}/revoke",
                headers=h, json={"reason": "no longer"})
    r4 = client.post("/api/v1/foundation/signup",
                     json={"email": "t@example.test", "invite_code": row["invite_code"]})
    assert r4.status_code == 403
    # wrong email for a valid code -> denied (identical shape)
    r5 = client.post("/api/v1/foundation/signup",
                     json={"email": "other@example.test", "invite_code": row["invite_code"]})
    assert r5.status_code == 403
    assert r5.json()["detail"]["message"] == r3.json()["detail"]["message"]


# --- Phase C: admin tools -------------------------------------------------------

def test_admin_tools_lifecycle_and_notes(client, seeded_state):
    org = seeded_state.ids["org"]
    platform = _platform(seeded_state, org)
    hp = bearer(make_access_token(platform.id, org=org,
                                  role="internal_platform_admin"))
    seeded_state.lifecycle.initialize(org, actor="u", reason="created")
    # grant (invited -> onboarding)
    r = client.post(f"/api/v1/foundation/admin/orgs/{org}/grant",
                    headers=hp, json={"reason": "approved"})
    assert r.status_code == 200
    assert r.json()["lifecycle_state"] == lc.ONBOARDING
    # suspend
    client.post(f"/api/v1/foundation/admin/orgs/{org}/suspend",
                headers=hp, json={"reason": "compliance"})
    h = owner_headers(seeded_state)
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 403
    # resume
    client.post(f"/api/v1/foundation/admin/orgs/{org}/resume",
                headers=hp, json={"reason": "cleared"})
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    # downgrade -> free
    client.post(f"/api/v1/foundation/admin/orgs/{org}/downgrade",
                headers=hp, json={"reason": "trial ended"})
    assert client.get("/api/v1/foundation/plan-usage", headers=h).json()["plan"]["tier"] == "free"
    # internal note + history
    client.post(f"/api/v1/foundation/admin/orgs/{org}/notes",
                headers=hp, json={"note": "internal: high-trust tester"})
    hist = client.get(f"/api/v1/foundation/admin/orgs/{org}/history",
                      headers=hp).json()
    assert any(n["note"] == "internal: high-trust tester" for n in hist["notes"])
    assert hist["lifecycle"]


def test_internal_notes_never_exposed_to_testers(client, seeded_state):
    org = seeded_state.ids["org"]
    platform = _platform(seeded_state, org)
    hp = bearer(make_access_token(platform.id, org=org,
                                  role="internal_platform_admin"))
    client.post(f"/api/v1/foundation/admin/orgs/{org}/notes",
                headers=hp, json={"note": "SECRET-INTERNAL: do not expose"})
    # the tester-facing surface must not contain the note
    h = owner_headers(seeded_state)
    for url in ("/api/v1/foundation/plan-usage",
                "/api/v1/foundation/jobs-durable",
                "/api/v1/foundation/entitlements"):
        body = client.get(url, headers=h)
        assert "SECRET-INTERNAL" not in body.text
    # the admin history endpoint requires platform admin
    hv = bearer(make_access_token(_member(seeded_state, "op2@example.test", org,
                                          Role.OPERATOR.value).id, org=org,
                                  role="operator"))
    assert client.get(f"/api/v1/foundation/admin/orgs/{org}/history",
                      headers=hv).status_code == 403


def test_temporary_override_expiry(client, seeded_state):
    org = seeded_state.ids["org"]
    platform = _platform(seeded_state, org)
    hp = bearer(make_access_token(platform.id, org=org,
                                  role="internal_platform_admin"))
    h = owner_headers(seeded_state)
    # grant a trial-like override: export_enabled true for the free org
    client.post(f"/api/v1/foundation/admin/orgs/{org}/override", headers=hp, json={
        "feature": "export_enabled", "value": True,
        "reason": "manual grant", "permanent": False,
        "expires_at": "2099-01-01T00:00:00+00:00"})
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["export_enabled"] is True
    # expire it -> next check revokes
    seeded_state.db.conn.execute(
        "UPDATE entitlement_overrides SET expires_at=? WHERE feature='export_enabled'",
        ("2000-01-01T00:00:00+00:00",))
    seeded_state.db.conn.commit()
    ent2 = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent2["export_enabled"] is False


# --- Phase D: onboarding pack + support -----------------------------------------

def test_onboarding_pack_and_completion(client, seeded_state):
    h = owner_headers(seeded_state)
    pack = client.get("/api/v1/foundation/onboarding-pack").json()
    assert pack["welcome"] and pack["task_script"]
    st = client.get("/api/v1/foundation/onboarding", headers=h).json()
    assert st["completed"] is False
    client.post("/api/v1/foundation/onboarding/complete", headers=h,
                json={"step": "invite_issued"})
    st2 = client.get("/api/v1/foundation/onboarding", headers=h).json()
    assert st2["checklist"]["invite_issued"] is True


def test_support_ticket_submit_triage_note_separation(client, seeded_state):
    org = seeded_state.ids["org"]
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/support/tickets", headers=h, json={
        "category": "bug", "severity": "high", "subject": "job hung",
        "description": "the job stuck in leased"})
    assert r.status_code == 201, r.text
    ref = r.json()["reference_id"]
    assert r.json()["no_secrets_warning"]
    # triage (platform admin) adds an internal note + tester-visible note
    platform = _platform(seeded_state, org)
    hp = bearer(make_access_token(platform.id, org=org,
                                  role="internal_platform_admin"))
    tid = r.json()["ticket_id"]
    client.post(f"/api/v1/foundation/support/tickets/{tid}/triage",
                headers=hp, json={"status": "investigating",
                                  "internal_note": "INTERNAL: infra suspicion",
                                  "tester_visible_note": "we are investigating"})
    # tester view: internal note hidden, tester-visible shown
    tv = client.get(f"/api/v1/foundation/support/tickets/{tid}", headers=h).json()
    assert tv["tester_visible_note"] == "we are investigating"
    assert "INTERNAL" not in str(tv)
    # internal view (platform): internal note visible
    iv = client.post(f"/api/v1/foundation/support/tickets/{tid}/triage",
                     headers=hp, json={"status": "resolved"}).json()
    assert iv["internal_note"] == "INTERNAL: infra suspicion"


def test_support_tickets_org_isolated(client, seeded_state):
    h = owner_headers(seeded_state)
    client.post("/api/v1/foundation/support/tickets", headers=h, json={
        "category": "other", "severity": "low", "subject": "a", "description": "b"})
    tid = seeded_state.repos.support_tickets.for_org(seeded_state.ids["org"])[0]["id"]
    org_b = Organization(name="B", slug="b")
    seeded_state.repos.organizations.add(org_b)
    opb = _member(seeded_state, "opb@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(opb.id, org=org_b.id, role="operator"))
    assert client.get("/api/v1/foundation/support/tickets", headers=hb).json()["items"] == []
    assert client.get(f"/api/v1/foundation/support/tickets/{tid}",
                      headers=hb).status_code == 404