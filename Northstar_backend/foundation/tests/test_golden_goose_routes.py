"""P5-T2 Golden Goose decision route tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation import golden_goose_decision as gg

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value
VIEWER = Role.VIEWER.value
GATES_PASS = {name: gg.PASS for name in gg.MANDATORY_GATES}
HIGH = {k: 1.0 for k in ("net_profit", "demand", "bsr_stability")}


def _app(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    admin = bootstrap_owner(st, org_name="GG", user_email="admin@t.test", role=ADMIN, recover=True)
    viewer = bootstrap_owner(st, org_name="GG2", user_email="viewer@t.test", role=VIEWER, recover=True)
    return app, admin, viewer


def test_evaluate_score_alone_never_purchase_ready(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    body = {"gate_inputs": {}, "economics_readiness": "COMPLETE",
            "component_scores": HIGH, "component_weights": HIGH,
            "resale_inputs": {"net_per_unit": 50, "est_monthly_sales": 1000}}
    r = c.post("/api/v1/foundation/golden-goose/evaluate", json=body,
               headers={"X-User-Id": admin["user_id"]})
    assert r.status_code == 200
    d = r.json()["decision"]
    assert d["purchase_ready"] is False and d["decision_state"] != gg.PURCHASE_READY
    assert r.json()["resale_score"]["purchase_ready"] is False


def test_evaluate_gates_plus_approval_can_reach_purchase_ready(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    body = {"gate_inputs": GATES_PASS, "economics_readiness": "COMPLETE",
            "approval": {"present": True}}
    r = c.post("/api/v1/foundation/golden-goose/evaluate", json=body,
               headers={"X-User-Id": admin["user_id"]})
    assert r.json()["decision"]["decision_state"] == gg.PURCHASE_READY


def test_sample_can_never_reach_purchase_ready(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    body = {"gate_inputs": GATES_PASS, "economics_readiness": "COMPLETE",
            "approval": {"present": True}, "sample": True}
    r = c.post("/api/v1/foundation/golden-goose/evaluate", json=body,
               headers={"X-User-Id": admin["user_id"]})
    assert r.json()["decision"]["purchase_ready"] is False


def test_queue_is_empty_and_honest(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    r = c.get("/api/v1/foundation/golden-goose/queue",
              headers={"X-User-Id": admin["user_id"]})
    assert r.status_code == 200 and r.json()["items"] == []
    assert r.json()["basis"] == "UNKNOWN"


def test_get_unknown_item_is_404(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    r = c.get("/api/v1/foundation/golden-goose/nope",
              headers={"X-User-Id": admin["user_id"]})
    assert r.status_code == 404


def test_decision_route_requires_approve_permission(monkeypatch):
    app, admin, viewer = _app(monkeypatch)
    c = TestClient(app)
    body = {"gate_inputs": GATES_PASS, "economics_readiness": "COMPLETE",
            "approval": {"present": True}}
    # viewer lacks approve
    assert c.post("/api/v1/foundation/golden-goose/x/decision", json=body,
                  headers={"X-User-Id": viewer["user_id"]}).status_code == 403
    # admin can decide
    r = c.post("/api/v1/foundation/golden-goose/x/decision", json=body,
               headers={"X-User-Id": admin["user_id"]})
    assert r.status_code == 200 and r.json()["decision"]["decision_state"] == gg.PURCHASE_READY
    assert r.json()["persisted"] is True


def test_decision_round_trip_persists(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    from Northstar_backend.foundation.golden_goose_store import upsert_item
    c = TestClient(app)
    org = admin["organization_id"]
    upsert_item(app.state.foundation.db, org,
                {"item_id": "GG-1", "match_state": gg.QUALIFIED_FOR_REVIEW,
                 "resale_score": 0.8, "net_per_unit": 9.0,
                 "economics_complete": True, "policy_exclusion_flag": 0})
    # item is readable and appears in the queue (org-scoped)
    g = c.get("/api/v1/foundation/golden-goose/GG-1", headers={"X-User-Id": admin["user_id"]})
    assert g.status_code == 200 and g.json()["item_id"] == "GG-1"
    q = c.get("/api/v1/foundation/golden-goose/queue", headers={"X-User-Id": admin["user_id"]})
    assert [i["item_id"] for i in q.json()["items"]] == ["GG-1"] and q.json()["basis"] == "OBSERVED"
    # record a decision, reload, and see it persisted
    body = {"gate_inputs": GATES_PASS, "economics_readiness": "COMPLETE", "approval": {"present": True}}
    d = c.post("/api/v1/foundation/golden-goose/GG-1/decision", json=body,
               headers={"X-User-Id": admin["user_id"]})
    assert d.json()["persisted"] is True
    g2 = c.get("/api/v1/foundation/golden-goose/GG-1", headers={"X-User-Id": admin["user_id"]})
    assert g2.json()["latest_decision"]["decision_state"] == gg.PURCHASE_READY


def test_item_is_tenant_scoped(monkeypatch):
    app, admin, viewer = _app(monkeypatch)
    from Northstar_backend.foundation.golden_goose_store import upsert_item
    c = TestClient(app)
    upsert_item(app.state.foundation.db, admin["organization_id"],
                {"item_id": "GG-2", "resale_score": 0.5})
    # viewer in a different org cannot see it
    r = c.get("/api/v1/foundation/golden-goose/GG-2", headers={"X-User-Id": viewer["user_id"]})
    assert r.status_code == 404


def test_persisted_item_projection_drops_raw_payload(monkeypatch):
    """P4-T3b: customer-facing item/view responses expose derived fields only —
    the raw embedded payload (which may carry restricted third-party source
    fields) is never returned."""
    app, admin, _ = _app(monkeypatch)
    from Northstar_backend.foundation.golden_goose_store import upsert_item
    c = TestClient(app)
    org = admin["organization_id"]
    raw = {
        "item_id": "GG-RAW", "match_state": gg.QUALIFIED_FOR_REVIEW,
        "resale_score": 0.75, "net_per_unit": 5.5, "economics_complete": True,
        "policy_exclusion_flag": 0,
        # embedded restricted third-party source field that must not leak
        "source": "sellersprite_historical_export",
        "source_url": "https://x.example/secret",
        "deep_observation": {"cost": 9.99},
    }
    upsert_item(app.state.foundation.db, org, raw)
    g = c.get("/api/v1/foundation/golden-goose/GG-RAW", headers={"X-User-Id": admin["user_id"]})
    assert g.status_code == 200
    body = g.json()
    # derived fields preserved
    assert body["item_id"] == "GG-RAW"
    assert body["match_state"] == gg.QUALIFIED_FOR_REVIEW
    assert body["resale_score"] == 0.75
    # raw embedded third-party fields never exposed
    assert "payload_json" not in body
    assert "source_url" not in body
    assert "deep_observation" not in body
    assert "payload" not in body
    # record remains a derived opportunity record, not labeled CUSTOMER_OK
    assert body.get("customer_ok") is None
    q = c.get("/api/v1/foundation/golden-goose/queue", headers={"X-User-Id": admin["user_id"]})
    qi = q.json()["items"][0]
    assert qi["item_id"] == "GG-RAW"
    assert "payload_json" not in qi and "source_url" not in qi and "deep_observation" not in qi



def test_unauthenticated_evaluate_is_401(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    assert c.post("/api/v1/foundation/golden-goose/evaluate", json={}).status_code == 401