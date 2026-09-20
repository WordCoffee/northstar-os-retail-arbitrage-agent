"""B4 tests — security boundaries (security-boundaries/v1).

Proves least-privilege admin is technically enforced at the boundary, and that
role checks fail closed.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import auth_deps  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


# ---------- dependency-level enforcement ----------

def test_require_admin_allows_admin():
    user = {"id": "u1", "role": "admin"}
    assert asyncio.run(auth_deps.require_admin(user=user)) is user


def test_require_admin_rejects_non_admin():
    from fastapi import HTTPException
    for role in ("member", "operator", "owner", "bogus", None):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(auth_deps.require_admin(user={"id": "u1", "role": role}))
        assert exc.value.status_code == 403


def test_require_role_dependency_fails_closed():
    from fastapi import HTTPException
    check = auth_deps.require_role("operator")
    assert asyncio.run(check(user={"role": "owner"})) == {"role": "owner"}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(check(user={"role": "member"}))
    assert exc.value.status_code == 403
    with pytest.raises(HTTPException):
        asyncio.run(check(user={"role": "admin"}))   # admin is not a tenant role


# ---------- endpoint-level enforcement ----------

def test_admin_endpoint_denies_anonymous(client):
    # demo/anonymous fallback is a member -> forbidden
    resp = client.get("/api/v1/admin/accounts/whatever")
    assert resp.status_code == 403
    assert "Administrator" in resp.json()["detail"]


def test_admin_endpoint_allows_admin_and_whitelists_fields(client, monkeypatch):
    target = {
        "id": "acct9", "email": "o@x.com", "plan": "mover", "created_at": "2026-09-19",
        "password_hash": "$2b$secret", "is_active": 1, "last_login_at": "2026-09-19",
    }
    monkeypatch.setattr(auth, "get_user", lambda uid: dict(target))
    token = auth.create_access_token("acct9", "o@x.com", "autothink", role="admin")
    resp = client.get("/api/v1/admin/accounts/acct9", headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 200
    account = resp.json()["account"]
    assert set(account) == {"id", "email", "plan", "created_at"}
    for forbidden in ("password_hash", "is_active", "last_login_at"):
        assert forbidden not in account


def test_admin_endpoint_unknown_id_404(client, monkeypatch):
    def _get(uid):
        if uid == "acct9":
            return {"id": "acct9", "email": "o@x.com", "plan": "autothink", "created_at": "2026-09-19"}
        return None
    monkeypatch.setattr(auth, "get_user", _get)
    token = auth.create_access_token("acct9", "o@x.com", "autothink", role="admin")
    resp = client.get("/api/v1/admin/accounts/missing", headers={"Authorization": "Bearer " + token})
    assert resp.status_code == 404


def test_auth_me_still_works_for_demo(client):
    # boundary addition must not break the existing demo read path
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["mode"] == "demo"