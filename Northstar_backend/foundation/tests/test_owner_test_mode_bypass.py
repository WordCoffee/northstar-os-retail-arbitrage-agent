"""P3-T2 Owner Test Mode bypass tests (RBAC, audit, self-approval gating)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation.api.state import FoundationState
from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.context import build_context
from Northstar_backend.foundation.enums import Role
from Northstar_backend.foundation.permissions import evaluate, PERM_PURCHASE

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value


def test_rbac_owner_holds_every_permission(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    allowed, reason = evaluate(build_context(role=ADMIN), PERM_PURCHASE)
    assert allowed is True
    assert reason == "owner_test_mode"


def test_rbac_non_admin_is_not_bypassed(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    allowed, _ = evaluate(build_context(role=Role.VIEWER.value), PERM_PURCHASE)
    assert allowed is False


def test_flag_off_reason_is_not_owner_test_mode(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_OWNER_TEST_MODE", raising=False)
    allowed, reason = evaluate(build_context(role=ADMIN), PERM_PURCHASE)
    assert allowed is True and reason == "ok"


def _admin_app(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    r = bootstrap_owner(st, org_name="Test", user_email="admin@test.test",
                        role=ADMIN, recover=True)
    return app, st, r["user_id"]


def test_unrelated_page_load_does_not_flood_audit(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    app, st, uid = _admin_app(monkeypatch)
    client = TestClient(app)
    client.get("/api/v1/foundation/environment", headers={"X-User-Id": uid})
    client.get("/api/v1/foundation/roles", headers={"X-User-Id": uid})
    rows = st.repos.audit.list({})
    otm_rows = [x for x in rows if str(x.get("action", "")).startswith("owner_test_mode.")]
    assert otm_rows == [], "owner_test_mode must only audit ACTUAL bypasses, not page loads"


def _state(tmp_path):
    return FoundationState.build(str(tmp_path / "foundation.db"))


def _approval(st):
    r = bootstrap_owner(st, org_name="Test", user_email="owner@test.test",
                        role=ADMIN, recover=True)
    req = st.approvals.request(organization_id=r["organization_id"],
                               requested_by_user_id=r["user_id"],
                               capability="listing.publish")
    return r, req


def test_self_approval_denied_by_default(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.delenv("NORTHSTAR_OWNER_SELF_APPROVAL", raising=False)
    st = _state(tmp_path)
    try:
        r, req = _approval(st)
        with pytest.raises(PermissionError):
            st.approvals.decide(approval_request_id=req["id"],
                                decided_by_user_id=r["user_id"], decided_by_role=ADMIN)
        denied = st.repos.audit.list({"action": "approval.decide"})
        assert any(row.get("result") == "denied" for row in denied)
    finally:
        st.close()


def test_self_approval_allowed_when_flag_on(monkeypatch, tmp_path):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    monkeypatch.setenv("NORTHSTAR_OWNER_SELF_APPROVAL", "1")
    st = _state(tmp_path)
    try:
        r, req = _approval(st)
        out = st.approvals.decide(approval_request_id=req["id"],
                                  decided_by_user_id=r["user_id"], decided_by_role=ADMIN)
        assert out["state"] == "granted"
    finally:
        st.close()