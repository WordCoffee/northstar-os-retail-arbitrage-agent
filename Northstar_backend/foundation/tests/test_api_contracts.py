"""API contract + authorization tests (TestClient)."""
from __future__ import annotations

from Northstar_backend.foundation.tests.conftest import owner_headers


def test_me_requires_authentication(client):
    # Phase 1C-01: fail-closed — no credentials -> 401.
    r = client.get("/api/v1/foundation/me")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_me_with_owner_headers(client, seeded_state):
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "organization_owner"
    assert "manage_org" in body["permissions"]
    assert body["environment"] == "production"


def test_roles_endpoint(client, seeded_state):
    r = client.get("/api/v1/foundation/roles", headers=owner_headers(seeded_state))
    assert r.status_code == 200
    assert "organization_owner" in r.json()["roles"]


def test_environment_endpoint(client, seeded_state):
    r = client.get("/api/v1/foundation/environment",
                   headers=owner_headers(seeded_state, env="sandbox"))
    assert r.status_code == 200
    assert r.json()["environment"] == "sandbox"
    assert r.json()["writes_allowed"] is True  # not previewing


def test_organizations_requires_authentication(client):
    r = client.get("/api/v1/foundation/organizations")  # no credentials
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_marketplaces_seeded(client, seeded_state):
    r = client.get("/api/v1/foundation/marketplaces", headers=owner_headers(seeded_state))
    assert r.status_code == 200
    codes = [m["code"] for m in r.json()["items"]]
    assert "amazon.com" in codes
    assert r.json()["items"][0]["currency"] == "USD"


def test_identity_submit_creates_product(client, seeded_state):
    r = client.post("/api/v1/foundation/identity/submit",
                    headers=owner_headers(seeded_state),
                    json={"asin": "B0TEST0001", "title": "T"})
    assert r.status_code == 201
    assert r.json()["resolution"] == "new_product"
    assert r.json()["product_id"]


def test_identity_submit_invalid_asin(client, seeded_state):
    r = client.post("/api/v1/foundation/identity/submit",
                    headers=owner_headers(seeded_state), json={"asin": "bad"})
    assert r.status_code == 201
    assert r.json()["resolution"] == "unresolved_candidate"


def test_observation_null_first(client, seeded_state):
    r = client.post("/api/v1/foundation/observations",
                    headers=owner_headers(seeded_state),
                    json={"observation_type": "price", "observed_value": None,
                          "environment": "sandbox"})
    assert r.status_code == 201
    assert r.json()["observation"]["observed_value"] is None
    assert r.json()["meta"]["provenance_class"] == "unavailable"


def test_preview_start_requires_permission(client, seeded_state):
    # viewer role lacks preview
    headers = {"X-User-Id": "u9", "X-Org-Id": "o9", "X-Role": "viewer", "X-Env": "production"}
    r = client.post("/api/v1/foundation/preview/start", headers=headers,
                    json={"target_organization_id": "org2", "reason": "support"})
    assert r.status_code == 403


def test_preview_start_and_read_only_enforcement(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/preview/start", headers=h,
                    json={"target_organization_id": seeded_state.ids["org"],
                          "reason": "support"})
    assert r.status_code == 200
    pid = r.json()["preview_id"]
    # with preview header active, env endpoint reports preview + writes blocked
    h2 = dict(h)
    h2["X-Preview-Id"] = pid
    r2 = client.get("/api/v1/foundation/environment", headers=h2)
    assert r2.json()["is_preview"] is True
    assert r2.json()["writes_allowed"] is False
    # end it
    r3 = client.post("/api/v1/foundation/preview/end", headers=h2, params={"preview_id": pid})
    assert r3.status_code == 200
    assert r3.json()["active"] is False


def test_create_job_and_get(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/jobs", headers=h,
                    json={"service": "prospector", "max_estimated_cost": 5.0,
                          "environment": "sandbox", "idempotency_key": "api-j1"})
    assert r.status_code == 201
    jid = r.json()["job_request"]["id"]
    r2 = client.get(f"/api/v1/foundation/jobs/{jid}", headers=h)
    assert r2.status_code == 200


def test_usage_summary_shadow_label(client, seeded_state):
    r = client.get("/api/v1/foundation/usage/summary", headers=owner_headers(seeded_state))
    assert r.status_code == 200
    assert r.json()["label"] == "SHADOW ESTIMATE"
    assert r.json()["debits_applied"] is False


def test_approval_flow_via_api(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.post("/api/v1/foundation/approvals", headers=h,
                    json={"capability": "listing.publish", "safety_class": "write_external"})
    assert r.status_code == 201
    aid = r.json()["approval"]["id"]
    r2 = client.post(f"/api/v1/foundation/approvals/{aid}/decide", headers=h,
                     json={"decision": "granted"})
    assert r2.status_code == 200
    assert r2.json()["execution"] == "not_performed_phase_1b"


def test_audit_requires_permission(client, seeded_state):
    headers = {"X-User-Id": "u9", "X-Org-Id": "o9", "X-Role": "viewer"}
    r = client.get("/api/v1/foundation/audit", headers=headers)
    assert r.status_code == 403


def test_ui_preference_roundtrip_api(client, seeded_state):
    h = owner_headers(seeded_state)
    r = client.put("/api/v1/foundation/ui/preferences/pinned_width",
                   headers=h, json={"value": 320})
    assert r.status_code == 200
    r2 = client.get("/api/v1/foundation/ui/preferences/pinned_width", headers=h)
    assert r2.status_code == 200
    assert r2.json()["value"] in (320, "320")


def test_error_envelope_shape(client, seeded_state):
    headers = {"X-User-Id": "u9", "X-Org-Id": "o9", "X-Role": "viewer"}
    r = client.get("/api/v1/foundation/audit", headers=headers)
    detail = r.json()["detail"]
    assert set(["code", "message"]).issubset(detail.keys())