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
    assert r.json()["persisted"] is False


def test_unauthenticated_evaluate_is_401(monkeypatch):
    app, admin, _ = _app(monkeypatch)
    c = TestClient(app)
    assert c.post("/api/v1/foundation/golden-goose/evaluate", json={}).status_code == 401