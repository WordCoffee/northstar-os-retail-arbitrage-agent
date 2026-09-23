"""Phase A / A0 — memory + learning HTTP route contract tests."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

c = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_learning(tmp_path, monkeypatch):
    """Keep learning artifacts out of the real learning/ dir."""
    monkeypatch.setenv("NORTHSTAR_LEARNING_DIR", str(tmp_path / "learning"))
    yield


def _ok(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["contract"] == "bff/v1"
    assert body["status"] == "ok"
    return body["data"]


def test_learning_route_envelope_and_novel():
    data = _ok(c.post("/api/v1/learning/route", json={"task": "summarize a novel thing xyz"}))
    assert data["tier"] in ("L0", "L1", "L2", "L3")
    assert "requires_approval" in data


def test_learning_route_live_never_replays():
    data = _ok(c.post("/api/v1/learning/route", json={"task": "publish the listing", "live": True}))
    assert data["tier"] == "L3"
    assert data["action"] == "approval_required"
    assert data["requires_approval"] is True


def test_learning_playbooks_route():
    data = _ok(c.get("/api/v1/learning/playbooks?account_id=default"))
    assert "playbooks" in data and "count" in data


def test_learning_capture_invalid_kind():
    resp = c.post("/api/v1/learning/capture", json={"kind": "bogus", "task": "t"})
    assert resp.status_code == 400


def test_learning_capture_and_distill():
    acct = "a0_route_test"
    data = _ok(c.post("/api/v1/learning/capture", json={
        "kind": "outcome", "task": f"route test task {acct}", "account_id": acct,
        "payload": {"outcome": "accepted"},
    }))
    assert data["record"]["kind"] == "outcome"
    distilled = _ok(c.post("/api/v1/learning/distill", params={"account_id": acct}))
    assert distilled["playbooks"] >= 1


def test_memory_ingest_search_roundtrip():
    acct = "a0_route_test"
    ingest = _ok(c.post("/api/v1/memory/ingest", json={
        "content": "A0 route test brand voice note", "entry_type": "fact",
        "account_id": acct, "source": "test",
    }))
    assert ingest["id"]
    found = _ok(c.post("/api/v1/memory/search", json={
        "intent": "A0 route test", "account_id": acct,
    }))
    assert found["count"] >= 1
    assert "[Memory Bank" in found["context"]


def test_learning_unlearn_requires_target():
    resp = c.post("/api/v1/learning/unlearn", json={})
    assert resp.status_code == 400
