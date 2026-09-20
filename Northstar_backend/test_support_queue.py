"""Phase F/S8 — support queue tooling tests (local only)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
import data_layer  # noqa: E402
import support as support_mod  # noqa: E402


@pytest.fixture()
def supdb(tmp_path, monkeypatch):
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "support.db")
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


def _admin_token():
    reg = auth.register_user("op@x.com", "password123", "autothink")
    return auth.create_access_token(reg["id"], reg["email"], "autothink", role="admin")


def _user_token():
    reg = auth.register_user("user@x.com", "password123", "scout")
    return auth.create_access_token(reg["id"], reg["email"], "scout")


def test_create_and_list(supdb):
    t = support_mod.create_ticket("acct1", "Cannot export CSV", "Got a 500 on export")
    assert t["id"].startswith("tkt_") and t["status"] == "open"
    found = support_mod.list_tickets()
    assert len(found) == 1 and found[0]["id"] == t["id"]
    assert len(support_mod.list_tickets("in_progress")) == 0


def test_set_status_and_assign(supdb):
    t = support_mod.create_ticket("acct1", "Subject", "Body")
    r = support_mod.set_status(t["id"], "in_progress")
    assert r["status"] == "in_progress"
    r2 = support_mod.assign(t["id"], "operator-tyrone")
    assert r2["assigned_to"] == "operator-tyrone"
    with pytest.raises(ValueError):
        support_mod.set_status(t["id"], "bogus")
    with pytest.raises(KeyError):
        support_mod.assign("tkt_no", "op")


def test_required_subject(supdb):
    with pytest.raises(ValueError):
        support_mod.create_ticket("acct1", "   ", "x")


def test_routes_create_accepts_demo_user_but_admin_list_gated(client):
    # Demo posture: unauthenticated = foundation member (B2) → create allowed
    # as the 'anonymous' account. The queue LIST remains admin-only.
    created = client.post("/api/v1/support/tickets", json={"subject": "x", "body": "y"})
    assert created.status_code == 200
    assert created.json()["ticket"]["account_id"] == "anonymous"
    assert client.get("/api/v1/support").status_code == 403   # anon not admin


def test_routes_full_flow(client):
    t = _user_token()
    created = client.post("/api/v1/support/tickets", json={"subject": "Hello", "body": "Help"},
                          headers={"Authorization": "Bearer " + t})
    assert created.status_code == 200
    tid = created.json()["ticket"]["id"]
    a = _admin_token()
    listing = client.get("/api/v1/support", headers={"Authorization": "Bearer " + a})
    assert listing.status_code == 200 and len(listing.json()["tickets"]) == 1
    upd = client.patch("/api/v1/support/" + tid, json={"status": "resolved"},
                       headers={"Authorization": "Bearer " + a})
    assert upd.status_code == 200 and upd.json()["ticket"]["status"] == "resolved"
    assert client.patch("/api/v1/support/" + tid, json={"status": "resolved"},
                        headers={"Authorization": "Bearer " + t}).status_code == 403