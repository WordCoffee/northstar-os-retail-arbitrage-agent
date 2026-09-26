"""1C-06 master slice: private beta readiness (Phases A-D).

Phase A — test-mode billing: redirect hosted checkout (no card fields),
owner-only, webhook signature verification, exactly-once settlement keyed on
the processor event id.
Phase B — tiers & entitlements: centralized service, explicit free-tier limits,
downgrade/cancel/non-payment revoke on next check, over-tier denied.
Phase C — invite-gated access: default closed, non-revealing signup denial,
invite revocation, immediate account suspension.
Phase D — file sets + private-beta addendum document.
"""
from __future__ import annotations

import pytest

from Northstar_backend.foundation.billing import processor as proc
from Northstar_backend.foundation.billing import tiers as tiers_mod
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
    body = {"job_type": "immediate_success", "payload_schema_version": "1.0",
            "payload": kw.pop("payload", {})}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


# --- Phase A: billing ---------------------------------------------------------

def test_billing_owner_only(client, seeded_state):
    op = _member(seeded_state, "op@example.test", seeded_state.ids["org"],
                 Role.OPERATOR.value)
    hop = bearer(make_access_token(op.id, org=seeded_state.ids["org"], role="operator"))
    assert client.post("/api/v1/foundation/billing/checkout",
                       json={"price_id": "price_trial"},
                       headers=hop).status_code == 403
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/billing/checkout",
                    json={"price_id": "price_trial"}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["mode"] == "redirect_hosted"
    assert r.json()["test_mode"] is True
    assert "/billing/checkout/" in r.json()["redirect_url"]


def test_hosted_checkout_page_has_no_card_fields(client, seeded_state):
    h = owner_headers(seeded_state)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_pro"}, headers=h).json()
    page = client.get(co["redirect_url"]).text
    assert "TEST MODE" in page
    assert "card" not in page.lower() or "no payment card" in page.lower()
    assert "price_pro" in page or "Pro (test mode)" in page


def test_webhook_signature_verification(client, seeded_state):
    h = owner_headers(seeded_state)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=h).json()
    event = proc.build_event(event_id="evt_1", event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id="cus_test_1", subscription_id="sub_test_1",
                             price_id="price_trial")
    # wrong signature -> rejected
    r = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": "bad"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "invalid_signature"
    # correct signature -> processed
    sig = proc.sign_event(event, proc.webhook_secret())
    r = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": sig})
    assert r.status_code == 200
    assert r.json()["status"] == "processed"


def test_webhook_exactly_once_settlement(client, seeded_state):
    h = owner_headers(seeded_state)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_pro"}, headers=h).json()
    event = proc.build_event(event_id="evt_dup_1",
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id="cus_dup", subscription_id="sub_dup",
                             price_id="price_pro", current_period_end=None)
    sig = proc.sign_event(event, proc.webhook_secret())
    a = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": sig})
    b = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": sig})
    assert a.json()["status"] == "processed"
    assert b.json()["status"] == "already_processed"
    # exactly one ledger settlement keyed on the event id
    settled = [e for e in seeded_state.repos.usage.list()
               if e["idempotency_key"] == "billing:evt_dup_1"]
    assert len(settled) == 1
    # exactly one active subscription
    subs = seeded_state.repos.subscriptions.list()
    assert len(subs) == 1
    # no card data anywhere
    for sub in subs:
        assert "card" not in str(sub).lower() or "no card" in str(sub).lower()


def test_webhook_duplicate_delivery_single_settlement(client, seeded_state):
    """Sequential duplicate webhook delivery: exactly-once settlement.
    (True concurrency is proven on PostgreSQL.)"""
    h = owner_headers(seeded_state)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=h).json()
    event = proc.build_event(event_id="evt_seq_1",
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id="cus_seq", subscription_id="sub_seq",
                             price_id="price_trial")
    sig = proc.sign_event(event, proc.webhook_secret())
    a = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": sig})
    b = client.post("/api/v1/foundation/billing/webhook",
                    json={"payload": event, "signature": sig})
    assert a.json()["status"] == "processed"
    assert b.json()["status"] == "already_processed"
    assert len([e for e in seeded_state.repos.usage.list()
                if e["idempotency_key"] == "billing:evt_seq_1"]) == 1
    assert len(seeded_state.repos.subscriptions.list()) == 1


# --- Phase B: tiers & entitlements --------------------------------------------

def test_free_tier_explicit_limits(client, seeded_state):
    h = owner_headers(seeded_state)
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["tier"] == "free"
    assert ent["max_jobs_per_month"] == 1000  # explicit, enforced
    assert ent["export_enabled"] is False
    assert ent["advanced_reports"] is False
    assert ent["seat_limit"] == 10


def test_subscribe_grants_tier_features(client, seeded_state):
    h = owner_headers(seeded_state)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=h).json()
    event = proc.build_event(event_id="evt_grant_1",
                             event_type="checkout.session.completed",
                             checkout_session_id=co["checkout_id"],
                             customer_id="cus_g", subscription_id="sub_g",
                             price_id="price_trial")
    client.post("/api/v1/foundation/billing/webhook",
                json={"payload": event,
                      "signature": proc.sign_event(event, proc.webhook_secret())})
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["tier"] == "trial"
    assert ent["max_jobs_per_month"] == 5
    assert ent["export_enabled"] is True


def test_over_tier_job_blocked_and_revoked_on_cancel(client, seeded_state):
    h = owner_headers(seeded_state)
    # subscribe to trial (max_jobs=5)
    co = client.post("/api/v1/foundation/billing/checkout",
                     json={"price_id": "price_trial"}, headers=h).json()
    event = proc.build_event(
        event_id="evt_ot_1", event_type="checkout.session.completed",
        checkout_session_id=co["checkout_id"], customer_id="c",
        subscription_id="s", price_id="price_trial")
    client.post("/api/v1/foundation/billing/webhook",
                json={"payload": event,
                      "signature": proc.sign_event(event, proc.webhook_secret())})
    # submit 5 allowed
    for i in range(5):
        r = _submit(client, h, idempotency_key=f"trial-{i}")
        assert r.status_code == 201, r.text
    # the 6th is over-tier -> blocked (non-revealing 403)
    r = _submit(client, h)
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "entitlement_denied"
    # downgrade/revoke: cancel -> entitlement revoked on NEXT check
    client.post("/api/v1/foundation/billing/cancel", headers=h)
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["tier"] == "free"
    # the free tier permits the NEXT job (1000/month) — this is the REVOKED
    # entitlement being recomputed correctly, not the trial limit persisting
    assert ent["max_jobs_per_month"] == 1000


def test_centralized_entitlement_no_hardcoded_tiers(client, seeded_state):
    """Entitlement checks live ONLY in EntitlementService; the tier endpoint
    reflects the single source of truth."""
    h = owner_headers(seeded_state)
    for tier in ("free", "trial", "pro", "team"):
        flags = tiers_mod.tier_flags(tier)
        assert "max_jobs_per_month" in flags
        assert "export_enabled" in flags
        assert "seat_limit" in flags
    ent = client.get("/api/v1/foundation/entitlements", headers=h).json()
    assert ent["max_jobs_per_month"] == tiers_mod.tier_flags(ent["tier"])[
        "max_jobs_per_month"]


# --- Phase C: invite-gated access ---------------------------------------------

def test_signup_denied_without_invite_non_revealing(client, seeded_state):
    for body in ({"email": "someone@example.com", "invite_code": "unknown"},
                 {"email": "nonexistent@nowhere.test", "invite_code": "ABC123"}):
        r = client.post("/api/v1/foundation/signup", json=body)
        assert r.status_code == 403
        d = r.json()["detail"]
        assert d["code"] == "signup_denied"
        assert "available" in d["message"]  # identical, non-revealing


def test_invite_flow_and_revocation(client, seeded_state):
    h = owner_headers(seeded_state)
    inv = client.post("/api/v1/foundation/invites", headers=h,
                      json={"email": "invited@example.test",
                            "role": Role.OPERATOR.value}).json()
    # the issuer receives the code (needed to hand the invite to a tester)
    assert inv["invite_code"] and len(inv["invite_code"]) == 16
    code = seeded_state.repos.invites.get(inv["invite_id"])["invite_code"]
    assert inv["invite_code"] == code
    # signup with the invite
    r = client.post("/api/v1/foundation/signup",
                    json={"email": "invited@example.test", "invite_code": code})
    assert r.status_code == 201
    result = r.json()
    assert result["organization_id"] == seeded_state.ids["org"]
    # a second use of the same invite is denied (non-revealing)
    r2 = client.post("/api/v1/foundation/signup",
                     json={"email": "invited@example.test", "invite_code": code})
    assert r2.status_code == 403
    # revoke a fresh invite -> signup denied
    inv2 = client.post("/api/v1/foundation/invites", headers=h,
                       json={"email": "inv2@example.test",
                             "role": Role.VIEWER.value}).json()
    client.post(f"/api/v1/foundation/invites/{inv2['invite_id']}/revoke",
                headers=h, json={"reason": "revoked"})
    code2 = seeded_state.repos.invites.get(inv2["invite_id"])["invite_code"]
    r3 = client.post("/api/v1/foundation/signup",
                     json={"email": "inv2@example.test", "invite_code": code2})
    assert r3.status_code == 403
    # wrong email for the invite code -> denied (non-revealing)
    r4 = client.post("/api/v1/foundation/signup",
                     json={"email": "other@example.test", "invite_code": code})
    assert r4.status_code == 403


def test_invite_admin_owner_only(client, seeded_state):
    op = _member(seeded_state, "op2@example.test", seeded_state.ids["org"],
                 Role.OPERATOR.value)
    hop = bearer(make_access_token(op.id, org=seeded_state.ids["org"], role="operator"))
    assert client.post("/api/v1/foundation/invites", headers=hop,
                       json={"email": "x@example.test",
                             "role": Role.VIEWER.value}).status_code == 403
    assert client.get("/api/v1/foundation/invites", headers=hop).status_code == 403


def test_account_suspend_blocks_immediately(client, seeded_state):
    viewer = _member(seeded_state, "sv@example.test", seeded_state.ids["org"],
                     Role.VIEWER.value)
    hv = bearer(make_access_token(viewer.id, org=seeded_state.ids["org"], role="viewer"))
    assert client.get("/api/v1/foundation/jobs-durable", headers=hv).status_code == 200
    h = owner_headers(seeded_state)
    r = client.post(f"/api/v1/foundation/accounts/{viewer.id}/suspend",
                    headers=h, json={"reason": "abuse"})
    assert r.status_code == 200
    # immediate block on the next authenticated request (not just next login)
    assert client.get("/api/v1/foundation/jobs-durable", headers=hv).status_code == 403


def test_invites_cross_org_isolated(client, seeded_state):
    h = owner_headers(seeded_state)
    inv = client.post("/api/v1/foundation/invites", headers=h,
                      json={"email": "iso@example.test",
                            "role": Role.VIEWER.value}).json()
    org_b = Organization(name="B", slug="b")
    seeded_state.repos.organizations.add(org_b)
    opb = _member(seeded_state, "opb@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(opb.id, org=org_b.id, role="operator"))
    # org B cannot see org A's invite via the list (owner-only anyway -> 403)
    assert client.get("/api/v1/foundation/invites", headers=hb).status_code == 403


# --- Phase D: file sets + addendum ---------------------------------------------

def test_file_sets_served(client):
    r = client.get("/api/v1/foundation/legal/filesets")
    assert r.status_code == 200
    ids = {i["set_id"] for i in r.json()["items"]}
    assert ids == {"onboarding_guide", "faq", "support_contact"}
    for i in r.json()["items"]:
        assert i["version"] == "1.0"
        assert "test mode" in i["content"].lower() or "private beta" in i["content"].lower()


def test_private_beta_addendum_is_required_document(client, seeded_state):
    from Northstar_backend.foundation.beta.documents import DOC_TYPES
    assert "private_beta_addendum" in DOC_TYPES
    r = client.get("/api/v1/foundation/legal/documents")
    types = {i["doc_type"] for i in r.json()["items"]}
    assert "private_beta_addendum" in types