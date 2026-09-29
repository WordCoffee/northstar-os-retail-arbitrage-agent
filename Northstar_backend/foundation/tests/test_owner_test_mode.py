"""P3-T1 Owner Test Mode flag/scope/banner tests."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation import owner_test_mode as otm
from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.enums import Role

ADMIN = Role.INTERNAL_PLATFORM_ADMIN.value


def test_flag_off_is_zero_behavior_change(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_OWNER_TEST_MODE", raising=False)
    assert otm.is_owner_test_mode(role=ADMIN, environment="development") is False
    assert otm.is_owner_test_mode(role=ADMIN, environment="production") is False
    assert otm.flag_enabled() is False


def test_flag_on_scope(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    assert otm.is_owner_test_mode(role=ADMIN, environment="development") is True
    assert otm.is_owner_test_mode(role=ADMIN, environment="staging") is True
    assert otm.is_owner_test_mode(role=Role.OPERATOR.value, environment="development") is False
    assert otm.is_owner_test_mode(role=ADMIN, environment="production_tenant") is False


def test_self_approval_defaults_off(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_OWNER_SELF_APPROVAL", raising=False)
    assert otm.self_approval_enabled() is False
    monkeypatch.setenv("NORTHSTAR_OWNER_SELF_APPROVAL", "1")
    assert otm.self_approval_enabled() is True


def _admin_app(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    r = bootstrap_owner(st, org_name="Test", user_email="admin@test.test",
                        role=ADMIN, recover=True)
    return app, r["user_id"]


def test_environment_exposes_flag_off(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_OWNER_TEST_MODE", raising=False)
    app, uid = _admin_app(monkeypatch)
    client = TestClient(app)
    body = client.get("/api/v1/foundation/environment",
                      headers={"X-User-Id": uid}).json()
    assert body["owner_test_mode"] is False
    assert body["owner_test_mode_banner"] is None
    assert body["owner_self_approval"] is False


def test_environment_exposes_flag_on_for_owner(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_OWNER_TEST_MODE", "1")
    app, uid = _admin_app(monkeypatch)
    client = TestClient(app)
    body = client.get("/api/v1/foundation/environment",
                      headers={"X-User-Id": uid}).json()
    assert body["owner_test_mode"] is True
    assert "OWNER TEST MODE" in body["owner_test_mode_banner"]