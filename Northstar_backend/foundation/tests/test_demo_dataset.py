"""P3-T4 labeled demo dataset tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation import demo_dataset as dd
from Northstar_backend.foundation import golden_goose_decision as gg

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value
VIEWER = Role.VIEWER.value
ORG = "org-demo"


def _state(tmp_path):
    st = FoundationState.build(str(tmp_path / "f.db"))
    return st


def test_hidden_by_default(tmp_path):
    st = _state(tmp_path)
    try:
        assert dd.is_enabled(st.db, ORG) is False
        assert dd.sample_count(st.db, ORG) == 0
    finally:
        st.close()


def test_enable_is_labeled_and_persists(tmp_path):
    st = _state(tmp_path)
    try:
        out = dd.set_enabled(st.db, ORG, True, actor_user_id="u1", audit=st.audit)
        assert out["enabled"] is True and out["sample_count"] == 3
        rows = dd.sample_rows(st.db, ORG)
        assert rows and all(r["basis"] == "SAMPLE" for r in rows)
        # persistence across a fresh enable-check (DB-backed, not in-memory)
        assert dd.is_enabled(st.db, ORG) is True
    finally:
        st.close()


def test_disable_restores_off_state(tmp_path):
    st = _state(tmp_path)
    try:
        dd.set_enabled(st.db, ORG, True)
        dd.set_enabled(st.db, ORG, False)
        assert dd.is_enabled(st.db, ORG) is False
        assert dd.sample_count(st.db, ORG) == 0
        # canonical real observation table is untouched (still empty)
        n = st.db.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert int(n) == 0
    finally:
        st.close()


def test_samples_are_separate_from_real_observations(tmp_path):
    st = _state(tmp_path)
    try:
        dd.set_enabled(st.db, ORG, True)
        # sample rows live ONLY in demo_observations, never in observations
        n = st.db.conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        assert int(n) == 0
        s = st.db.conn.execute("SELECT COUNT(*) FROM demo_observations WHERE is_sample=1").fetchone()[0]
        assert int(s) == 3
    finally:
        st.close()


def test_toggle_writes_audit(tmp_path):
    st = _state(tmp_path)
    try:
        dd.set_enabled(st.db, ORG, True, actor_user_id="u1", audit=st.audit)
        dd.set_enabled(st.db, ORG, False, actor_user_id="u1", audit=st.audit)
        rows = [r for r in st.repos.audit.list({})
                if str(r.get("action", "")).startswith("demo_dataset.")]
        assert any(r["action"] == "demo_dataset.enabled" for r in rows)
        assert any(r["action"] == "demo_dataset.disabled" for r in rows)
    finally:
        st.close()


def test_sample_never_reaches_purchase_ready():
    gates_pass = {name: gg.PASS for name in gg.MANDATORY_GATES}
    sample_out = gg.decide(gate_inputs=gates_pass, economics_readiness="COMPLETE",
                           approval={"present": True}, sample=True)
    assert sample_out["purchase_ready"] is False
    assert sample_out["decision_state"] != gg.PURCHASE_READY
    real_out = gg.decide(gate_inputs=gates_pass, economics_readiness="COMPLETE",
                         approval={"present": True}, sample=False)
    assert real_out["decision_state"] == gg.PURCHASE_READY


def _app(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    admin = bootstrap_owner(st, org_name="Demo", user_email="admin@t.test", role=ADMIN, recover=True)
    viewer = bootstrap_owner(st, org_name="Demo2", user_email="viewer@t.test", role=VIEWER, recover=True)
    return app, st, admin, viewer


def test_demo_endpoints_owner_only(monkeypatch):
    app, st, admin, viewer = _app(monkeypatch)
    client = TestClient(app)
    # viewer denied
    assert client.get("/api/v1/foundation/demo/status",
                      headers={"X-User-Id": viewer["user_id"]}).status_code == 403
    assert client.post("/api/v1/foundation/demo/enable",
                       headers={"X-User-Id": viewer["user_id"]}).status_code == 403
    # owner allowed
    assert client.get("/api/v1/foundation/demo/status",
                      headers={"X-User-Id": admin["user_id"]}).json()["enabled"] is False
    en = client.post("/api/v1/foundation/demo/enable",
                     headers={"X-User-Id": admin["user_id"]})
    assert en.status_code == 200 and en.json()["sample_count"] == 3
    dis = client.post("/api/v1/foundation/demo/disable",
                      headers={"X-User-Id": admin["user_id"]})
    assert dis.status_code == 200 and dis.json()["enabled"] is False