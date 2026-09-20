"""Phase F/S7 — invite + onboarding flow tests (code only, email stubbed)."""

from __future__ import annotations

import logging
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
import data_layer  # noqa: E402
import invites as invites_mod  # noqa: E402


@pytest.fixture()
def invdb(tmp_path, monkeypatch):
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "invites.db")
    monkeypatch.setattr(data_layer, "_db_instance", None)
    yield
    if data_layer._db_instance is not None:
        data_layer._db_instance.close()
        data_layer._db_instance = None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "api.db")
    monkeypatch.setattr(data_layer, "_db_instance", None)
    yield TestClient(__import__("main").app)
    if data_layer._db_instance is not None:
        data_layer._db_instance.close()
        data_layer._db_instance = None


def test_create_invite_and_lookup(invdb):
    inv = invites_mod.create_invite("founding_operator")
    assert inv["code"].startswith("invite_")
    assert inv["plan"] == "autothink"
    got = invites_mod.get_invite(inv["code"])
    assert got["cohort"] == "founding_operator" and got["redeemed"] is False


def test_unknown_cohort_rejected(invdb):
    with pytest.raises(ValueError):
        invites_mod.create_invite("nope")


def test_redeem_single_use_and_idempotent(invdb):
    inv = invites_mod.create_invite("founding_operator")
    r1 = invites_mod.redeem_invite(inv["code"], "acct1")
    assert r1["status"] == "redeemed" and r1["cohort"] == "founding_operator"
    # same account re-redeem is idempotent
    r2 = invites_mod.redeem_invite(inv["code"], "acct1")
    assert r2["status"] == "already_redeemed"
    # different account is rejected
    with pytest.raises(PermissionError):
        invites_mod.redeem_invite(inv["code"], "acct2")


def test_redeem_unknown_code(invdb):
    with pytest.raises(KeyError):
        invites_mod.redeem_invite("invite_missing", "acct1")


def test_email_send_is_stubbed(invdb, caplog):
    with caplog.at_level(logging.INFO, logger="northstar.invites"):
        out = invites_mod.send_invite_email("invite_abc", "founding_operator", "x@example.com")
    assert out["status"] == "stubbed"
    assert "stubbed" in caplog.text and "x@example.com" in caplog.text


def test_api_create_requires_admin(client):
    resp = client.post("/api/v1/invites", json={"cohort": "founding_operator"})
    assert resp.status_code == 403                       # anon/demo is not admin


def test_api_create_and_redeem_admin_flow(client, monkeypatch):
    import auth as _auth
    reg = _auth.register_user("o@x.com", "password123", "autothink")
    token = _auth.create_access_token(reg["id"], reg["email"], "autothink", role="admin")
    h = {"Authorization": "Bearer " + token}
    resp = client.post("/api/v1/invites", json={"cohort": "founding_operator"}, headers=h)
    assert resp.status_code == 200
    code = resp.json()["invite"]["code"]
    # lookup public
    assert client.get("/api/v1/invites/" + code).json()["invite"]["cohort"] == "founding_operator"
    # redeem as a non-admin authenticated user
    ur = _auth.register_user("u@x.com", "password123", "foundation")
    utok = _auth.create_access_token(ur["id"], ur["email"], "foundation")
    r = client.post("/api/v1/invites/redeem", json={"code": code}, headers={"Authorization": "Bearer " + utok})
    assert r.status_code == 200 and r.json()["result"]["status"] == "redeemed"