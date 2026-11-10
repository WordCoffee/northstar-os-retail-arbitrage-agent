"""1C-06 subscriber rules & operations evidence on PostgreSQL (Phases A-F).

Concurrent plan-limit enforcement, plan-change-on-next-check, role-based
visibility, lifecycle transitions, invite non-enumeration, immediate
suspension, admin tools + note separation + override expiry, support org
isolation, dashboard accuracy, safe export, and the full integrated E2E.
Runs ONLY against the disposable loopback PostgreSQL.
"""
from __future__ import annotations

import csv
import io
import os
import threading
import uuid as _uuid
from urllib.parse import urlparse

import pytest

PG_URL = os.environ.get("FOUNDATION_DB_URL")
pytestmark = pytest.mark.skipif(
    not PG_URL, reason="FOUNDATION_DB_URL not set (PostgreSQL integration)")

DISPOSABLE_DB = os.environ.get("NORTHSTAR_PG_TEST_DB", "northstar_phase1c02_ephemeral")
DISPOSABLE_USER = os.environ.get("NORTHSTAR_PG_TEST_USER", "northstar_phase1c02_test")


def _assert_disposable_target():
    u = urlparse(PG_URL)
    assert u.hostname == "127.0.0.1"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    _expected_port = os.environ.get("NORTHSTAR_PG_TEST_PORT")
    if _expected_port:
        assert u.port == int(_expected_port), (
            f"port must match NORTHSTAR_PG_TEST_PORT={_expected_port}, got {u.port}")


@pytest.fixture(scope="module")
def durable_pg():
    _assert_disposable_target()
    from Northstar_backend.foundation.db import SCHEMA
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    db = PostgresFoundationDB(PG_URL)
    db.drop_all_foundation_tables(list(SCHEMA.keys()))
    for m in ("001_foundation.sql", "002_jobs_durable.sql",
              "003_keyword_intel.sql", "004_financial_integrity.sql",
              "005_beta_launch_controls.sql", "006_private_beta_readiness.sql",
              "007_private_beta_operations.sql"):
        db.apply_sql_file(f"Northstar_backend/migrations_foundation/{m}")
    yield db
    db.close()


def _state(tag):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    uniq = _uuid.uuid4().hex[:8]
    st = FoundationState.build()
    org = Organization(name=f"Ops {tag} {uniq}", slug=f"ops-{tag}-{uniq}")
    st.repos.organizations.add(org)
    u = User(email=f"owner-{uniq}@{tag}.test")
    st.repos.users.add(u)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=org.id, user_id=u.id,
                                        role=Role.ORGANIZATION_OWNER.value,
                                        status="active"))
    st.ids = {"org": org.id, "user": u.id}
    st.uniq = uniq
    return st


def _headers(st, org, user, role="organization_owner"):
    from Northstar_backend.foundation.tests.conftest import make_access_token, bearer
    return bearer(make_access_token(user, org=org, role=role))


def _app(st):
    from Northstar_backend.foundation.app import create_app
    from fastapi.testclient import TestClient
    app = create_app()
    app.state.foundation = st
    return TestClient(app)


def _signed_checkout(client, h, price_id, event_id, org):
    from Northstar_backend.foundation.billing import processor as proc
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


def _submit(client, headers, key=None):
    body = {"job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}}
    if key:
        body["idempotency_key"] = key
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


def _platform(st, org):
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User, Membership
    p = User(email=f"plat-{_uuid.uuid4().hex[:8]}@ops.test")
    st.repos.users.add(p)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=org, user_id=p.id,
                                        role=Role.INTERNAL_PLATFORM_ADMIN.value,
                                        status="active"))
    return p


# --- Phase A: plan changes + concurrency ---------------------------------------

def test_plan_change_affects_next_check(durable_pg):
    st = _state("pc")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    _signed_checkout(client, h, "price_trial", "evt_pc_1", st.ids["org"])
    for i in range(5):
        assert _submit(client, h, key=f"pc-{i}").status_code == 201
    assert _submit(client, h).status_code == 403  # trial limit reached
    p = _platform(st, st.ids["org"])
    hp = _headers(st, st.ids["org"], p.id, role="internal_platform_admin")
    r = client.post(f"/api/v1/foundation/admin/orgs/{st.ids['org']}/plan",
                    headers=hp, json={"cohort": "free", "reason": "t"})
    assert r.status_code == 200
    assert client.get("/api/v1/foundation/plan-usage", headers=h).json()["plan"]["tier"] == "free"
    assert _submit(client, h).status_code == 201  # next check sees the new plan
    st.close()


def test_concurrent_attempts_cannot_exceed_limit(durable_pg):
    """N concurrent submissions against a 5-job trial limit: at most 5 succeed
    (atomic counter), the rest are denied 403 entitlement_denied."""
    st = _state("conc")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    _signed_checkout(client, h, "price_trial", "evt_conc_ops", st.ids["org"])
    statuses = []
    lock = threading.Lock()

    def fire(i):
        s2 = _state(f"conc-{i}")
        c2 = _app(s2)
        r = _submit(c2, _headers(s2, st.ids["org"], st.ids["user"]),
                    key=f"conc-{i}")
        with lock:
            statuses.append(r.status_code)
        s2.close()

    threads = [threading.Thread(target=fire, args=(i,)) for i in range(12)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    allowed = statuses.count(201)
    denied = statuses.count(403)
    assert allowed == 5
    assert denied == 7
    st.close()


def test_role_based_plan_usage_visibility(durable_pg):
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User, Membership
    st = _state("rb")
    client = _app(st)
    v = User(email=f"v-{st.uniq}@rb.test")
    st.repos.users.add(v)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=st.ids["org"],
                                        user_id=v.id, role=Role.VIEWER.value,
                                        status="active"))
    hv = _headers(st, st.ids["org"], v.id, role="viewer")
    ho = _headers(st, st.ids["org"], st.ids["user"])
    body_v = client.get("/api/v1/foundation/plan-usage", headers=hv).json()
    assert body_v["role_restricted"] is True and "usage" not in body_v
    body_o = client.get("/api/v1/foundation/plan-usage", headers=ho).json()
    assert "usage" in body_o and "seats" in body_o
    st.close()


# --- Phase B: lifecycle + invites -----------------------------------------------

def test_lifecycle_transitions_and_suspension(durable_pg):
    from Northstar_backend.foundation.operations import lifecycle as lc
    st = _state("lc")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    svc = st.lifecycle
    svc.initialize(st.ids["org"], actor="u", reason="created")
    with pytest.raises(Exception):
        svc.set_state(st.ids["org"], lc.ACTIVE, actor="u", reason="x", transition=True)
    svc.transition(st.ids["org"], to_state=lc.ONBOARDING, actor="u", reason="acc")
    svc.transition(st.ids["org"], to_state=lc.ACTIVE, actor="u", reason="ok")
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    svc.transition(st.ids["org"], to_state=lc.SUSPENDED, actor="u", reason="abuse")
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 403
    # platform admin can still operate the suspended org
    p = _platform(st, st.ids["org"])
    hp = _headers(st, st.ids["org"], p.id, role="internal_platform_admin")
    assert client.get("/api/v1/foundation/admin/dashboard",
                      headers=hp).status_code == 200
    svc.transition(st.ids["org"], to_state=lc.ACTIVE, actor="u", reason="ok")
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 200
    hist = svc.history(st.ids["org"])
    assert [x["new_state"] for x in hist] == ["invited", "onboarding", "active",
                                              "suspended", "active"]
    st.close()


def test_invite_non_enumeration_pg(durable_pg):
    from Northstar_backend.foundation.enums import Role
    st = _state("inv")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    inv = client.post("/api/v1/foundation/invites", headers=h,
                      json={"email": f"t-{st.uniq}@inv.test",
                            "role": Role.OPERATOR.value}).json()
    code = st.repos.invites.get(inv["invite_id"])["invite_code"]
    # wrong email -> non-revealing
    a = client.post("/api/v1/foundation/signup",
                    json={"email": "x@y.test", "invite_code": code})
    # no invite -> non-revealing
    b = client.post("/api/v1/foundation/signup",
                    json={"email": "q@w.test", "invite_code": "zzz"})
    assert a.status_code == b.status_code == 403
    assert a.json()["detail"]["message"] == b.json()["detail"]["message"]
    st.close()


# --- Phase C: admin tools -------------------------------------------------------

def test_admin_notes_not_exposed_and_override_expiry(durable_pg):
    st = _state("ad")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    p = _platform(st, st.ids["org"])
    hp = _headers(st, st.ids["org"], p.id, role="internal_platform_admin")
    client.post(f"/api/v1/foundation/admin/orgs/{st.ids['org']}/notes",
                headers=hp, json={"note": "SUPER-SECRET-INTERNAL"})
    for url in ("/api/v1/foundation/plan-usage", "/api/v1/foundation/entitlements"):
        assert "SUPER-SECRET-INTERNAL" not in client.get(url, headers=h).text
    # non-platform operator cannot see notes/history
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User, Membership
    op = User(email=f"op-{st.uniq}@ad.test")
    st.repos.users.add(op)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=st.ids["org"],
                                        user_id=op.id, role=Role.OPERATOR.value,
                                        status="active"))
    hop = _headers(st, st.ids["org"], op.id, role="operator")
    assert client.get(f"/api/v1/foundation/admin/orgs/{st.ids['org']}/history",
                      headers=hop).status_code == 403
    # override with expiry
    client.post(f"/api/v1/foundation/admin/orgs/{st.ids['org']}/override",
                headers=hp, json={"feature": "export_enabled", "value": True,
                                  "reason": "grant", "permanent": False,
                                  "expires_at": "2099-01-01T00:00:00+00:00"})
    assert client.get("/api/v1/foundation/entitlements", headers=h).json()["export_enabled"] is True
    st.db.conn.execute(
        "UPDATE entitlement_overrides SET expires_at=%s WHERE feature='export_enabled'",
        ("2000-01-01T00:00:00+00:00",))
    st.db.conn.commit()
    assert client.get("/api/v1/foundation/entitlements",
                      headers=h).json()["export_enabled"] is False
    st.close()


# --- Phase D: support ------------------------------------------------------------

def test_support_org_isolation_and_note_separation(durable_pg):
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    st = _state("sup")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    r = client.post("/api/v1/foundation/support/tickets", headers=h, json={
        "category": "bug", "severity": "high", "subject": "s",
        "description": "d"})
    tid = r.json()["ticket_id"]
    p = _platform(st, st.ids["org"])
    hp = _headers(st, st.ids["org"], p.id, role="internal_platform_admin")
    client.post(f"/api/v1/foundation/support/tickets/{tid}/triage",
                headers=hp, json={"internal_note": "IN", "tester_visible_note": "TV"})
    tv = client.get(f"/api/v1/foundation/support/tickets/{tid}", headers=h).json()
    assert tv["tester_visible_note"] == "TV" and "IN" not in str(tv)
    # another org cannot see this ticket
    org_b = Organization(name=f"B {st.uniq}", slug=f"b-{st.uniq}")
    st.repos.organizations.add(org_b)
    ub = User(email=f"b-{st.uniq}@b.test")
    st.repos.users.add(ub)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=org_b.id, user_id=ub.id,
                                        role=Role.OPERATOR.value, status="active"))
    hb = _headers(st, org_b.id, ub.id, role="operator")
    assert client.get(f"/api/v1/foundation/support/tickets/{tid}",
                      headers=hb).status_code == 404
    st.close()


# --- Phase E: dashboard + export --------------------------------------------------

def test_dashboard_accuracy_and_safe_export(durable_pg):
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.operations import lifecycle as lc
    st = _state("dash")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    _signed_checkout(client, h, "price_trial", "evt_dash_1", st.ids["org"])
    for i in range(3):
        _submit(client, h, key=f"dash-{i}")
    p = _platform(st, st.ids["org"])
    hp = _headers(st, st.ids["org"], p.id, role="internal_platform_admin")
    rows = client.get("/api/v1/foundation/admin/dashboard",
                      headers=hp).json()["items"]
    me = next(x for x in rows if x["organization_id"] == st.ids["org"])
    assert me["plan_tier"] == "trial"
    assert me["monthly_jobs_used"] == 3
    assert me["max_jobs_per_month"] == 5
    # export
    export = client.get("/api/v1/foundation/admin/dashboard/export",
                        headers=hp).text
    parsed = list(csv.DictReader(io.StringIO(export)))
    mine = next(x for x in parsed if x["organization_id"] == st.ids["org"])
    assert mine["plan_tier"] == "trial"
    assert mine["monthly_jobs_used"] == "3"
    # safe field set: no secret tokens anywhere
    low = export.lower()
    for token in ("secret", "token", "password", "card", "credential",
                  "provider_key", "api_key"):
        assert token not in low, f"excluded token in export: {token}"
    st.close()


# --- Phase F: integrated E2E ------------------------------------------------------

def test_integrated_private_beta_operations_e2e(durable_pg):
    """admin approves org -> invite -> owner signs up -> legal acceptance ->
    onboarding completed -> plan visible -> usage within limits -> over-limit
    denial explained -> support ticket -> admin note/triage -> admin downgrade/
    suspend -> next request reflects change -> dashboard + export show final
    state -> audit chain correlates."""
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    from Northstar_backend.foundation.operations import lifecycle as lc
    from Northstar_backend.foundation.beta.acceptance import publish_documents, record_acceptance
    from Northstar_backend.foundation.context import build_context
    from Northstar_backend.foundation.enums import Environment

    st = _state("e2e")
    client = _app(st)
    publish_documents(st)
    # ONE target org: the platform admin (operator) + the invited tester both
    # live here; the admin manages the org and the tester is the customer.
    target_org = Organization(name=f"Tester {st.uniq}", slug=f"t-{st.uniq}")
    st.repos.organizations.add(target_org)
    op_user = User(email=f"operator-{st.uniq}@ops.test")
    st.repos.users.add(op_user)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=target_org.id,
                                        user_id=op_user.id,
                                        role=Role.INTERNAL_PLATFORM_ADMIN.value,
                                        status="active"))
    hop = _headers(st, target_org.id, op_user.id, role="internal_platform_admin")
    record_acceptance(st, build_context(user_id=op_user.id,
                                        organization_id=target_org.id,
                                        role=Role.INTERNAL_PLATFORM_ADMIN.value,
                                        environment=Environment.PRODUCTION.value),
                      business_use=True, age_18_plus=True, request_id="op-accept")
    # 1. admin approves org (initialize + grant)
    st.lifecycle.initialize(target_org.id, actor=op_user.id, reason="created")
    st.admin_ops.grant(build_context(user_id=op_user.id, organization_id=target_org.id,
                                     role=Role.INTERNAL_PLATFORM_ADMIN.value,
                                     environment=Environment.PRODUCTION.value),
                       target_org.id, reason="approved")
    assert st.lifecycle.current_state(target_org.id) == lc.ONBOARDING
    # 2. invite issued for the tester owner (same org)
    email = f"owner-{st.uniq}@tester.test"
    inv = client.post("/api/v1/foundation/invites", headers=hop,
                      json={"email": email,
                            "role": Role.ORGANIZATION_OWNER.value}).json()
    code = st.repos.invites.get(inv["invite_id"])["invite_code"]
    # 3. owner signs up INTO the target org
    r = client.post("/api/v1/foundation/signup",
                    json={"email": email, "invite_code": code})
    assert r.status_code == 201
    assert r.json()["organization_id"] == target_org.id
    owner = next(u for u in st.repos.users.list() if u["email"] == email)
    ht = _headers(st, target_org.id, owner["id"], role="organization_owner")
    # 4. legal acceptance
    client.post("/api/v1/foundation/legal/acceptance", headers=ht, json={
        "business_use": True, "age_18_plus": True})
    # 5. onboarding completed
    oc = client.post("/api/v1/foundation/onboarding/complete", headers=ht, json={})
    assert oc.status_code == 200, oc.text
    assert client.get("/api/v1/foundation/onboarding", headers=ht).json()["completed"] is True
    # onboarding complete -> org moves to ACTIVE
    st.lifecycle.transition(target_org.id, to_state=lc.ACTIVE,
                            actor=op_user.id, reason="onboarded")
    # 6. plan visible in-app (free by default)
    pu = client.get("/api/v1/foundation/plan-usage", headers=ht).json()
    assert pu["plan"]["tier"] == "free"
    # 7. subscribe via test checkout -> trial
    _signed_checkout(client, ht, "price_trial", f"evt_e2e_{st.uniq}", target_org.id)
    assert client.get("/api/v1/foundation/plan-usage",
                      headers=ht).json()["plan"]["tier"] == "trial"
    # 8. usage within limits (5)
    for i in range(5):
        assert _submit(client, ht, key=f"e2e-{i}-{st.uniq}").status_code == 201
    # 9. over-limit denial explained (plan view shows usage)
    over = _submit(client, ht)
    assert over.status_code == 403
    pu2 = client.get("/api/v1/foundation/plan-usage", headers=ht).json()
    assert pu2["usage"]["monthly_jobs_used"] == 5
    # 10. support ticket + internal triage/note
    tk = client.post("/api/v1/foundation/support/tickets", headers=ht, json={
        "category": "usability", "severity": "medium", "subject": "x",
        "description": "y"})
    tid = tk.json()["ticket_id"]
    client.post(f"/api/v1/foundation/support/tickets/{tid}/triage",
                headers=hop, json={"status": "investigating",
                                   "internal_note": "seen by ops",
                                   "tester_visible_note": "noted"})
    client.post(f"/api/v1/foundation/admin/orgs/{target_org.id}/notes",
                headers=hop, json={"note": "trial cohort"})
    # 11. admin downgrades + suspends
    client.post(f"/api/v1/foundation/admin/orgs/{target_org.id}/downgrade",
                headers=hop, json={"reason": "trial end"})
    assert client.get("/api/v1/foundation/plan-usage",
                      headers=ht).json()["plan"]["tier"] == "free"
    client.post(f"/api/v1/foundation/admin/orgs/{target_org.id}/suspend",
                headers=hop, json={"reason": "review"})
    # 12. next request reflects suspended status
    assert client.get("/api/v1/foundation/plan-usage",
                      headers=ht).status_code == 403
    # 13. dashboard + export show final state
    rows = client.get("/api/v1/foundation/admin/dashboard",
                      headers=hop).json()["items"]
    row = next(x for x in rows if x["organization_id"] == target_org.id)
    assert row["lifecycle_state"] == lc.SUSPENDED
    assert row["plan_tier"] == "free"
    export = client.get("/api/v1/foundation/admin/dashboard/export",
                        headers=hop).text
    parsed = list(csv.DictReader(io.StringIO(export)))
    ex = next(x for x in parsed if x["organization_id"] == target_org.id)
    assert ex["lifecycle_state"] == "suspended"
    # 14. audit chain correlates all steps
    audit = st.repos.audit.list(where={"organization_id": target_org.id})
    actions = {a["action"] for a in audit}
    for expected in ("signup.accepted", "legal.acceptance",
                     "billing.subscription.settled", "support.ticket.submit",
                     "support.ticket.triage", "admin.note.add",
                     "admin.plan.change", "org.lifecycle.suspended",
                     "org.lifecycle.downgraded"):
        assert expected in actions, f"missing audit: {expected}"
    st.close()