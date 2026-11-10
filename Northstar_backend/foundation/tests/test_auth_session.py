"""P2-T5b backend auth/session tests (SQLite; test credentials only)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from Northstar_backend.foundation import credentials
from Northstar_backend.foundation.app import create_app
from Northstar_backend.foundation.bootstrap import bootstrap_owner
from Northstar_backend.foundation.enums import Role

EMAIL = "owner@test.test"
PW = "OwnerPassw0rd!23"


def _app_with_owner(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", "test-owner-secret")
    monkeypatch.delenv("NORTHSTAR_JWT_ISSUER", raising=False)
    monkeypatch.delenv("NORTHSTAR_JWT_AUDIENCE", raising=False)
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    app = create_app()
    st = app.state.foundation
    credentials.ensure_table(st.db)
    r = bootstrap_owner(st, org_name="Test", user_email=EMAIL,
                        role=Role.INTERNAL_PLATFORM_ADMIN.value, recover=True)
    credentials.create(st.db, user_id=r["user_id"], email=EMAIL, password=PW)
    return app


def _lower_headers(r):
    return {k.lower(): v for k, v in r.headers.items()}


def test_login_sets_httponly_cookie_and_no_token_in_body(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    r = client.post("/api/v1/foundation/auth/login", json={"email": EMAIL, "password": PW})
    assert r.status_code == 200
    sc = _lower_headers(r).get("set-cookie", "").lower()
    assert "ns_session=" in sc
    assert "httponly" in sc
    # P0-04 (2026-10-09): the session cookie moved to path "/" for the
    # single-origin suite (see foundation/auth_session.py); sync expectation.
    assert "path=/;" in sc
    assert "samesite=strict" in sc
    assert "secure" not in sc  # development transport is http
    assert "token" not in r.json()
    assert "password" not in r.text.lower()


def test_invalid_login_generic_error(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    r = client.post("/api/v1/foundation/auth/login",
                    json={"email": EMAIL, "password": "wrong-password"})
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_credentials"
    assert "wrong-password" not in r.text


def test_cookie_authenticates_me(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    r = client.post("/api/v1/foundation/auth/login", json={"email": EMAIL, "password": PW})
    uid = r.json()["user_id"]
    me = client.get("/api/v1/foundation/me")
    assert me.status_code == 200
    assert me.json()["user_id"] == uid


def test_signed_out_me_is_401(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    r = client.get("/api/v1/foundation/me")
    assert r.status_code == 401


def test_csrf_required_and_mismatch_denied(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    client.post("/api/v1/foundation/auth/login", json={"email": EMAIL, "password": PW})
    # Missing header -> denied.
    r = client.post("/api/v1/foundation/auth/logout")
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "csrf_failed"
    # Mismatched header -> denied.
    r2 = client.post("/api/v1/foundation/auth/logout",
                     headers={"X-CSRF-Token": "not-the-cookie"})
    assert r2.status_code == 403


def test_logout_revokes_and_clears_session(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    client.post("/api/v1/foundation/auth/login", json={"email": EMAIL, "password": PW})
    csrf = client.cookies.get("ns_csrf")
    assert csrf
    r = client.post("/api/v1/foundation/auth/logout", headers={"X-CSRF-Token": csrf})
    assert r.status_code == 200
    # After logout the session is gone -> unauthenticated.
    assert client.get("/api/v1/foundation/me").status_code == 401


def test_login_rate_limited(monkeypatch):
    app = _app_with_owner(monkeypatch)
    client = TestClient(app)
    codes = []
    for _ in range(7):
        codes.append(client.post("/api/v1/foundation/auth/login",
                                 json={"email": EMAIL, "password": "nope"}).status_code)
    assert 429 in codes


def test_hosted_fail_closed_ignores_dev_shim_and_requires_shared_store(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NORTHSTAR_JWT_SECRET", "prod-owner-secret-value")
    monkeypatch.setenv("NORTHSTAR_JWT_ISSUER", "https://northstar.example")
    monkeypatch.setenv("NORTHSTAR_JWT_AUDIENCE", "northstar-api")
    monkeypatch.delenv("NS_FOUNDATION_ALLOW_REMOTE_DEV", raising=False)
    monkeypatch.setenv("DB_URL", "")
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    monkeypatch.delenv("NS_FOUNDATION_BIND_HOST", raising=False)
    app = create_app()
    st = app.state.foundation
    credentials.ensure_table(st.db)
    r = bootstrap_owner(st, org_name="Test", user_email=EMAIL,
                        role=Role.INTERNAL_PLATFORM_ADMIN.value, recover=True)
    credentials.create(st.db, user_id=r["user_id"], email=EMAIL, password=PW)
    client = TestClient(app)
    # Header-based impersonation must NOT authenticate a hosted request.
    assert client.get("/api/v1/foundation/me",
                      headers={"X-User-Id": r["user_id"]}).status_code == 401
    # Hosted login fails closed without a shared throttle store (SQLite here).
    lr = client.post("/api/v1/foundation/auth/login", json={"email": EMAIL, "password": PW})
    assert lr.status_code == 503
    assert lr.json()["detail"]["code"] == "auth_store_unavailable"


def test_secure_cookie_attributes_in_production_like(monkeypatch):
    """HTTPS cookie attributes are asserted at the transport layer, separately
    from any local HTTP walkthrough."""
    from Northstar_backend.foundation.auth_session import (
        session_cookie_kwargs, csrf_cookie_kwargs,
    )
    monkeypatch.setenv("ENVIRONMENT", "production")
    s = session_cookie_kwargs("t")
    c = csrf_cookie_kwargs("t")
    assert s["secure"] is True and s["httponly"] is True and s["samesite"] == "strict"
    # P0-04 (2026-10-09): single-origin suite -> session cookie path "/".
    assert s["path"] == "/"
    assert c["secure"] is True and c["httponly"] is False and c["path"] == "/"
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert session_cookie_kwargs("t")["secure"] is False