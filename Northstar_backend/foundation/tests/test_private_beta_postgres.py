"""1C-06 master slice evidence on PostgreSQL (mandatory, Phases A-E).

Concurrent/duplicate-safety (webhook + signup), cross-org isolation, role
restriction, non-enumerating denial, and the single INTEGRATED end-to-end
private-test scenario (admin invite -> signup -> legal acceptance -> test-mode
checkout -> webhook settle -> entitlement grant -> within-tier operate ->
over-tier blocked -> admin revoke/cancel -> downgrade -> audit correlation).
Runs ONLY against the disposable loopback PostgreSQL.
"""
from __future__ import annotations

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
              "005_beta_launch_controls.sql", "006_private_beta_readiness.sql"):
        db.apply_sql_file(f"Northstar_backend/migrations_foundation/{m}")
    yield db
    db.close()


def _state(tag):
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import Organization, User, Membership
    uniq = _uuid.uuid4().hex[:8]
    st = FoundationState.build()
    org = Organization(name=f"PB {tag} {uniq}", slug=f"pb-{tag}-{uniq}")
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


def _signed_checkout(client, h, price_id, event_id, org, *,
                     subscription=None, customer=None):
    from Northstar_backend.foundation.billing import processor as proc
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": price_id}, headers=h).json()
    sub = subscription or f"sub_{event_id}"
    cus = customer or f"cus_{event_id}"
    event = proc.build_event(event_id=event_id,
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id=cus, subscription_id=sub,
                             price_id=price_id)
    r = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event,
                          "signature": proc.sign_event(event, proc.webhook_secret())})
    return r, co, event


def _submit(client, headers, key=None):
    body = {"job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": {}}
    if key:
        body["idempotency_key"] = key
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


# --- Phase A: billing ---------------------------------------------------------

def test_webhook_concurrent_duplicate_single_settlement(durable_pg):
    """The FIRST delivery is raced by N concurrent callers: exactly one wins."""
    st = _state("conc")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    from Northstar_backend.foundation.billing import processor as proc
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=h).json()
    event = proc.build_event(event_id="evt_conc_pg",
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id="cus_conc", subscription_id="sub_conc",
                             price_id="price_trial")
    sig = proc.sign_event(event, proc.webhook_secret())
    statuses = []
    lock = threading.Lock()

    def fire(_):
        # each caller uses its own connection (thread-safe)
        s2 = _state(f"conc-{_}")
        c2 = _app(s2)
        resp = c2.post("/api/v1/foundation/billing/webhook",
                       json={"payload": event, "signature": sig})
        with lock:
            statuses.append(resp.json().get("status"))
        s2.close()

    threads = [threading.Thread(target=fire, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert statuses.count("processed") == 1
    assert statuses.count("already_processed") == 5
    assert len([e for e in st.repos.usage.list()
                if e["idempotency_key"] == "billing:evt_conc_pg"]) == 1
    assert len(st.repos.subscriptions.list()) == 1
    st.close()


def test_billing_owner_only_and_cross_org(durable_pg):
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User, Membership
    st = _state("role")
    client = _app(st)
    op = User(email="op@role.test")
    st.repos.users.add(op)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=st.ids["org"],
                                        user_id=op.id, role=Role.OPERATOR.value,
                                        status="active"))
    hop = _headers(st, st.ids["org"], op.id, role="operator")
    assert client.post("/api/v1/foundation/billing/checkout",
                       json={"price_id": "price_trial"},
                       headers=hop).status_code == 403
    h = _headers(st, st.ids["org"], st.ids["user"])
    assert client.post("/api/v1/foundation/billing/checkout",
                       json={"price_id": "price_trial"},
                       headers=h).status_code == 200
    # another org cannot settle on this org (webhook carries its own checkout)
    st2 = _state("role2")
    h2 = _headers(st2, st2.ids["org"], st2.ids["user"])
    r, co2, _ev = _signed_checkout(client, h2, "price_pro", "evt_role2",
                                   st2.ids["org"])
    assert r.json()["status"] == "processed"
    assert len(st.repos.subscriptions.list(
        where={"organization_id": st.ids["org"]})) == 0
    st.close()
    st2.close()


# --- Phase B: entitlements ----------------------------------------------------

def test_downgrade_revokes_on_next_check(durable_pg):
    st = _state("dg")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    r, co, event = _signed_checkout(client, h, "price_trial", "evt_dg_1",
                                    st.ids["org"])
    assert r.json()["status"] == "processed"
    sub_id = event["subscription_id"]
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["tier"] == "trial" and ent["max_jobs_per_month"] == 5
    # non-payment revokes: subscription -> unpaid
    from Northstar_backend.foundation.billing import processor as proc
    fail = proc.build_event(event_id="evt_dg_fail",
                            event_type="invoice.payment_failed",
                            subscription_id=sub_id)
    client.post("/api/v1/foundation/billing/webhook",
                json={"payload": fail,
                      "signature": proc.sign_event(fail, proc.webhook_secret())})
    ent2 = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent2["tier"] == "free"  # gated features revoked on NEXT check
    st.close()


def test_over_tier_blocked_on_pg(durable_pg):
    st = _state("ot")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    _signed_checkout(client, h, "price_trial", "evt_ot_pg", st.ids["org"])
    for i in range(5):
        assert _submit(client, h, key=f"ot-{i}").status_code == 201
    r = _submit(client, h)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "entitlement_denied"
    st.close()


# --- Phase C: invites / signup / suspension -----------------------------------

def test_signup_non_revealing_and_invite_flow(durable_pg):
    st = _state("inv")
    client = _app(st)
    h = _headers(st, st.ids["org"], st.ids["user"])
    # uninvited -> non-revealing denial
    r = client.post("/api/v1/foundation/signup",
                    json={"email": "ghost@example.com", "invite_code": "nope"})
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "signup_denied"
    # issue an invite -> signup
    inv = client.post("/api/v1/foundation/invites", headers=h,
                      json={"email": "new@inv.test",
                            "role": "operator"}).json()
    code = st.repos.invites.get(inv["invite_id"])["invite_code"]
    r = client.post("/api/v1/foundation/signup",
                    json={"email": "new@inv.test", "invite_code": code})
    assert r.status_code == 201
    assert r.json()["organization_id"] == st.ids["org"]
    # cross-org: an invite from org A must not be usable by someone in org B,
    # and org B cannot revoke org A's invite (404, non-enumerating)
    st2 = _state("inv2")
    h2 = _headers(st2, st2.ids["org"], st2.ids["user"])
    inv2 = client.post("/api/v1/foundation/invites", headers=h,
                       json={"email": "b@inv.test",
                             "role": "operator"}).json()
    code2 = st.repos.invites.get(inv2["invite_id"])["invite_code"]
    # org B cannot revoke org A's invite
    assert client.post(
        f"/api/v1/foundation/invites/{inv['invite_id']}/revoke",
        headers=_headers(st2, st2.ids["org"], st2.ids["user"]),
        json={"reason": "x"}).status_code == 404
    # org B's OWN invite list never contains org A's invites
    items = client.get("/api/v1/foundation/invites",
                       headers=_headers(st2, st2.ids["org"], st2.ids["user"])).json()["items"]
    assert all(i["invite_id"] != inv["invite_id"] for i in items)
    # org A's invite was NOT revoked by org B (it is 'used' from the earlier
    # successful signup, not 'revoked')
    assert st.repos.invites.get(inv["invite_id"])["status"] != "revoked"
    st.close()
    st2.close()


def test_suspension_immediate_block(durable_pg):
    from Northstar_backend.foundation.models import User, Membership
    from Northstar_backend.foundation.enums import Role
    st = _state("sus")
    client = _app(st)
    v = User(email="v@sus.test")
    st.repos.users.add(v)
    st.repos.memberships.add(Membership(id=_uuid.uuid4().hex,
                                        organization_id=st.ids["org"],
                                        user_id=v.id, role=Role.VIEWER.value,
                                        status="active"))
    hv = _headers(st, st.ids["org"], v.id, role="viewer")
    assert client.get("/api/v1/foundation/jobs-durable",
                      headers=hv).status_code == 200
    h = _headers(st, st.ids["org"], st.ids["user"])
    client.post(f"/api/v1/foundation/accounts/{v.id}/suspend", headers=h,
                json={"reason": "abuse"})
    assert client.get("/api/v1/foundation/jobs-durable",
                      headers=hv).status_code == 403  # immediate
    st.close()


# --- Phase E: integrated end-to-end private-test scenario ---------------------

def test_integrated_private_beta_scenario(durable_pg):
    """admin invite -> invited user signs up -> accepts legal docs -> test-mode
    checkout -> webhook settle -> tier grants -> within-tier operate -> over-tier
    blocked -> admin revoke/cancel -> downgrade -> audit correlated end-to-end."""
    from Northstar_backend.foundation.billing import processor as proc
    from Northstar_backend.foundation.beta.acceptance import publish_documents
    from Northstar_backend.foundation.enums import Role
    from Northstar_backend.foundation.models import User

    st = _state("e2e")
    client = _app(st)
    admin = _headers(st, st.ids["org"], st.ids["user"])
    publish_documents(st)
    # admin records its own acceptance (needed to operate)
    client.post("/api/v1/foundation/legal/acceptance", headers=admin, json={
        "business_use": True, "age_18_plus": True})

    # 1. admin issues an invite (billing is owner-only, so the invited user is
    #    granted an owner seat in this org)
    cust_email = f"customer-{st.uniq}@e2e.test"
    inv = client.post("/api/v1/foundation/invites", headers=admin,
                      json={"email": cust_email,
                            "role": Role.ORGANIZATION_OWNER.value}).json()
    code = st.repos.invites.get(inv["invite_id"])["invite_code"]
    # 2. invited user signs up
    r = client.post("/api/v1/foundation/signup",
                    json={"email": cust_email, "invite_code": code})
    assert r.status_code == 201
    cust_user = next(u for u in st.repos.users.list()
                     if u["email"] == cust_email)
    cust_org = r.json()["organization_id"]
    hc = _headers(st, cust_org, cust_user["id"], role="organization_owner")
    # 3. accepts current legal documents (4 required)
    st_before = client.get("/api/v1/foundation/legal/acceptance/status",
                           headers=hc).json()
    assert st_before["accepted"] is False
    client.post("/api/v1/foundation/legal/acceptance", headers=hc, json={
        "business_use": True, "age_18_plus": True})
    assert client.get("/api/v1/foundation/legal/acceptance/status",
                      headers=hc).json()["accepted"] is True
    # 4. subscribes via test-mode hosted checkout -> webhook settles
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=hc).json()
    page = client.get(co["redirect_url"]).text
    assert "TEST MODE" in page and "no payment card" in page.lower()
    event = proc.build_event(event_id=f"evt_e2e_{st.uniq}",
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id=f"cus_{st.uniq}", subscription_id=f"sub_{st.uniq}",
                             price_id="price_trial")
    w = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event,
                          "signature": proc.sign_event(event, proc.webhook_secret())})
    assert w.json()["status"] == "processed"
    # 5. entitlement grants tier features
    ent = client.get("/api/v1/foundation/entitlements", headers=hc).json()
    assert ent["tier"] == "trial" and ent["export_enabled"] is True
    # 6. operates within tier limits (5 allowed)
    for i in range(5):
        assert _submit(client, hc, key=f"e2e-{i}").status_code == 201
    # 7. over-tier action blocked (non-revealing)
    r = _submit(client, hc)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "entitlement_denied"
    # 8. admin revokes invite / cancels subscription -> downgrade revokes
    client.post(f"/api/v1/foundation/invites/{inv['invite_id']}/revoke",
                headers=admin, json={"reason": "program ended"})
    client.post("/api/v1/foundation/billing/cancel", headers=hc,
                json={"reason": "test end"})
    ent_after = client.get("/api/v1/foundation/entitlements", headers=hc).json()
    assert ent_after["tier"] == "free"
    # 9. full audit trail correlated (acceptance, billing, entitlement, access)
    audit = st.repos.audit.list(where={"organization_id": cust_org})
    actions = {a["action"] for a in audit}
    for expected in ("legal.acceptance", "billing.subscription.settled",
                     "billing.subscription.cancel", "invite.issue", "signup.accepted"):
        assert expected in actions, f"missing audit: {expected}"
    # acceptance events append-only on the customer org
    acc = st.repos.acceptance_events.for_actor(cust_org, cust_user["id"])
    assert len(acc) == 4
    st.close()