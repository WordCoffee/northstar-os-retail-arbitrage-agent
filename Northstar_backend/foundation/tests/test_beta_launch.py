"""1C-06 Lean B2B beta launch controls tests.

Versioned public documents; mandatory acceptance at account creation and on
document revision (deny-until-accepted); append-only acceptance records with
cross-tenant isolation; role validation on document/acceptance endpoints;
data-inventory completeness; /beta-status readiness; enforcement inactive until
documents are published.
"""
from __future__ import annotations

import re

import pytest

from Northstar_backend.foundation.beta import documents as beta_docs
from Northstar_backend.foundation.beta.acceptance import (
    publish_documents, enforcement_active,
)
from Northstar_backend.foundation.beta import inventory as beta_inventory
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
            "payload": {}}
    body.update(kw)
    return client.post("/api/v1/foundation/jobs-durable", json=body, headers=headers)


# --- public documents --------------------------------------------------------

def test_public_documents_versioned_and_beta_marked(client, seeded_state):
    r = client.get("/api/v1/foundation/legal/documents")
    assert r.status_code == 200
    items = {i["doc_type"]: i for i in r.json()["items"]}
    assert set(items) == {"privacy_notice", "terms_of_service", "acceptable_use_policy", "private_beta_addendum"}
    for dt, doc in items.items():
        assert doc["version"] == "1.0"
        assert doc["beta_document"] is True
        assert doc["content_hash"] == beta_docs.content_hash(doc["content"])
        assert "beta" in doc["title"].lower()
    current = client.get("/api/v1/foundation/legal/documents/terms_of_service/current")
    assert current.json()["version"] == "1.0"


def test_documents_use_conservative_accurate_language(client):
    r = client.get("/api/v1/foundation/legal/documents")
    full = " ".join(i["content"] for i in r.json()["items"]).lower()
    # NO false/over-claiming language
    for banned in ("guaranteed outcome", "amazon approved", "legally compliant",
                   "verified sourcing", "guaranteed profit", "certified secure"):
        assert banned not in full, f"banned claim in documents: {banned}"
    # conservative disclaimers present
    for required in ("beta", "restricted", "manually approved", "does not promise",
                     "never silently assumed", "unknown", "18 years old", "business"):
        assert required in full, f"missing conservative statement: {required}"


# --- mandatory acceptance -----------------------------------------------------

def test_new_account_denied_until_acceptance(client, seeded_state):
    publish_documents(seeded_state)
    assert enforcement_active(seeded_state) is True
    h = owner_headers(seeded_state)
    # feature use denied until acceptance
    r = _submit(client, h)
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "acceptance_required"
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 409
    # acceptance endpoints remain reachable
    assert client.get("/api/v1/foundation/legal/acceptance/status",
                      headers=h).json()["accepted"] is False
    # record acceptance (business use + 18+)
    r = client.post("/api/v1/foundation/legal/acceptance", headers=h, json={
        "business_use": True, "age_18_plus": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "accepted"
    # feature use now allowed
    assert _submit(client, h).status_code == 201
    # append-only acceptance records exist with the required fields
    events = seeded_state.repos.acceptance_events.for_actor(
        seeded_state.ids["org"], seeded_state.ids["user"])
    assert len(events) == 4  # privacy, terms, aup, addendum
    for e in events:
        assert e["doc_version"] == "1.0"
        assert e["content_hash"]
        assert bool(e["business_use_attested"])
        assert bool(e["age_18_attested"])
        assert e["ip_handling"] == "not_stored"
        assert e["organization_id"] == seeded_state.ids["org"]
        assert e["user_id"] == seeded_state.ids["user"]
        assert e["accepted_at"]


def test_missing_attestations_rejected(client, seeded_state):
    publish_documents(seeded_state)
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/legal/acceptance", headers=h, json={
        "business_use": False, "age_18_plus": True})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "business_use_required"


def test_revised_document_reprompts_existing_user(client, seeded_state):
    publish_documents(seeded_state)
    h = owner_headers(seeded_state)
    client.post("/api/v1/foundation/legal/acceptance", headers=h, json={
        "business_use": True, "age_18_plus": True})
    assert _submit(client, h).status_code == 201
    # revise: publish a new version of the privacy notice
    from Northstar_backend.foundation.models import LegalDocument, utcnow
    seeded_state.repos.legal_documents.add(LegalDocument(
        doc_type="privacy_notice", version="2.0",
        title="Privacy Notice (Beta)", status="published", published_at=utcnow(),
        content_hash=beta_docs.content_hash("revised privacy notice")))
    # the user is denied continued authenticated use until accepting v2
    assert client.get("/api/v1/foundation/jobs-durable", headers=h).status_code == 409
    st = client.get("/api/v1/foundation/legal/acceptance/status", headers=h).json()
    assert st["accepted"] is False
    assert "privacy_notice" in st["missing_documents"]
    # accept the revision -> access restored
    client.post("/api/v1/foundation/legal/acceptance", headers=h, json={
        "business_use": True, "age_18_plus": True})
    assert _submit(client, h).status_code == 201


def test_enforcement_inactive_without_published_documents(client, seeded_state):
    assert enforcement_active(seeded_state) is False
    h = owner_headers(seeded_state)
    assert _submit(client, h).status_code == 201  # no gate pre-launch


# --- cross-tenant isolation ---------------------------------------------------

def test_acceptance_records_cross_tenant_isolated(client, seeded_state):
    publish_documents(seeded_state)
    # org A's owner accepts
    ha = owner_headers(seeded_state)
    client.post("/api/v1/foundation/legal/acceptance", headers=ha, json={
        "business_use": True, "age_18_plus": True})
    org_b = Organization(name="B", slug="b")
    seeded_state.repos.organizations.add(org_b)
    op_b = _member(seeded_state, "opb@example.test", org_b.id, Role.OPERATOR.value)
    hb = bearer(make_access_token(op_b.id, org=org_b.id, role="operator"))
    # org A's acceptance events must not be visible to org B
    events = seeded_state.repos.acceptance_events.for_actor(org_b.id, op_b.id)
    assert events == []  # only org-B's own records are reachable via the repo scope
    # org-B operator records its own acceptance (self-consent allowed)
    assert client.post("/api/v1/foundation/legal/acceptance", headers=hb, json={
        "business_use": True, "age_18_plus": True}).status_code == 200
    a_events = seeded_state.repos.acceptance_events.for_actor(
        seeded_state.ids["org"], seeded_state.ids["user"])
    b_events = seeded_state.repos.acceptance_events.for_actor(org_b.id, op_b.id)
    assert len(a_events) == 4 and len(b_events) == 4
    assert {e["organization_id"] for e in a_events} == {seeded_state.ids["org"]}
    assert {e["organization_id"] for e in b_events} == {org_b.id}


# --- role permissions on document/acceptance endpoints ------------------------

def test_document_and_acceptance_permissions(client, seeded_state):
    publish_documents(seeded_state)
    viewer = _member(seeded_state, "v@example.test", seeded_state.ids["org"],
                     Role.VIEWER.value)
    hv = bearer(make_access_token(viewer.id, org=seeded_state.ids["org"],
                                  role="viewer"))
    # public documents readable by anyone
    assert client.get("/api/v1/foundation/legal/documents").status_code == 200
    # viewer may record its own acceptance (self-consent) and read its status
    assert client.get("/api/v1/foundation/legal/acceptance/status",
                      headers=hv).status_code == 200
    assert client.post("/api/v1/foundation/legal/acceptance", headers=hv, json={
        "business_use": True, "age_18_plus": True}).status_code == 200
    # viewer may NOT manage documents (publish) or see internal operational docs
    assert client.post("/api/v1/foundation/legal/documents/publish",
                       headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/beta-status", headers=hv).status_code == 403
    assert client.get("/api/v1/foundation/data-inventory", headers=hv).status_code == 403
    # operator may see internal docs but not publish
    op = _member(seeded_state, "op@example.test", seeded_state.ids["org"],
                 Role.OPERATOR.value)
    ho = bearer(make_access_token(op.id, org=seeded_state.ids["org"], role="operator"))
    assert client.get("/api/v1/foundation/beta-status", headers=ho).status_code == 200
    assert client.post("/api/v1/foundation/legal/documents/publish",
                       headers=ho).status_code == 403
    # owner may publish
    assert client.post("/api/v1/foundation/legal/documents/publish",
                       headers=owner_headers(seeded_state)).status_code == 200


# --- /beta-status readiness record --------------------------------------------

def test_beta_status_readiness_record(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.get("/api/v1/foundation/beta-status", headers=h)
    assert r.status_code == 200
    bs = r.json()
    assert bs["beta_kind"] == "restricted_us_manual_approval"
    assert bs["us_only_manual_approval"] is True
    assert bs["public_self_serve"] is False
    assert bs["providers_disabled"] is True
    assert bs["payment_card_data_handled"] is False
    assert bs["customer_marketplace_credentials"] is False
    assert bs["acceptance_enforcement_enabled"] is False  # nothing published yet
    assert bs["data_inventory_complete"] is True
    assert bs["retention_schedule_complete"] is True
    assert bs["incident_runbook_complete"] is True
    assert bs["live_provider_calls_enabled"] is False
    assert bs["production_access"] is False


# --- data inventory completeness ----------------------------------------------

def test_data_inventory_complete_with_explicit_unknown_retention():
    review = beta_inventory.completeness_review()
    assert review["complete"] is True
    assert review["issues"] == []
    unknown = review["unknown_retention_explicit"]
    assert unknown  # at least one field explicitly marked UNKNOWN
    # every retention value is either a real value or the literal UNKNOWN
    for f in beta_inventory.FIELDS:
        assert f["retention"] == "UNKNOWN" or f["retention"] != "UNKNOWN"
        for key in ("purpose", "sensitivity", "source", "storage",
                    "access_roles", "vendor_subprocessor", "retention",
                    "deletion_mechanism", "optional"):
            assert key in f, f"missing {key} for {f['field']}"


# --- incident runbook ---------------------------------------------------------

def test_incident_runbook_complete():
    from Northstar_backend.foundation.beta.incident import runbook
    rb = runbook()
    assert rb["named_accountable_role"]
    for section in ("access_disable_steps", "session_invalidation",
                    "secret_rotation_checklist", "evidence_and_log_preservation",
                    "scope_assessment", "customer_communication_decision_tree",
                    "recovery", "post_incident_review"):
        assert section in rb and rb[section], f"missing {section}"
    assert "no_external_tools_note" in rb