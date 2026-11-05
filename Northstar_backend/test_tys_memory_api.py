"""The live memory routes: store, search, facts — admin-gated, fallback-safe."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))


def _client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    import tys_api
    from tys_ops import memory

    index = memory.MemoryIndex(str(tmp_path / "memory.db"), semantic=False)
    monkeypatch.setattr(tys_api, "_MEMORY", index)
    app.dependency_overrides[tys_api.require_tys_admin] = lambda: {"role": "owner"}
    return TestClient(app), app


def test_memory_text_and_search(monkeypatch, tmp_path):
    client, app = _client(monkeypatch, tmp_path)
    try:
        wrote = client.post("/api/admin/tys/memory/text",
                            json={"account": "op", "text": "The render lane takes the GPU lock."})
        assert wrote.status_code == 200, wrote.text
        assert wrote.json()["chunks"] == 1

        found = client.get("/api/admin/tys/memory/search",
                           params={"q": "GPU lock", "account": "op", "k": 3})
        assert found.status_code == 200, found.text
        body = found.json()
        assert body["hits"] and "GPU" in body["hits"][0]["text"]
    finally:
        app.dependency_overrides = {}


def test_memory_fact_supersession(monkeypatch, tmp_path):
    client, app = _client(monkeypatch, tmp_path)
    try:
        first = client.post("/api/admin/tys/memory/facts",
                            json={"account": "op", "subject": "storage",
                                  "predicate": "video", "value": "retained"})
        assert first.status_code == 200, first.text
        second = client.post("/api/admin/tys/memory/facts",
                             json={"account": "op", "subject": "storage",
                                   "predicate": "video", "value": "none",
                                   "confidence": 0.9})
        assert second.json()["contradiction"]["previous"] == "retained"
        facts = client.get("/api/admin/tys/memory/facts", params={"account": "op"})
        live = [f for f in facts.json()["facts"] if f["status"] == "live"]
        assert len(live) == 1 and live[0]["value"] == "none"
    finally:
        app.dependency_overrides = {}


def test_memory_routes_require_admin(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    import tys_api

    app.dependency_overrides = {}
    client = TestClient(app)
    response = client.get("/api/admin/tys/memory/search", params={"q": "x"})
    assert response.status_code in (401, 403)
