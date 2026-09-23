"""Batch 0 — AutothinK workspace API is mounted in the main app (smoke).

Offline: only asserts route existence + response shape. Does NOT call Ollama
(that path is exercised manually / by the live smoke pass).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402

c = TestClient(app)


def test_autothink_models_route_exists_and_shaped():
    r = c.get("/api/autothink/models")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("local_available", "cloud_available", "models"):
        assert key in body
    assert isinstance(body["models"], list)


def test_autothink_history_route_exists():
    r = c.get("/api/autothink/history?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "entries" in body and "total" in body


def test_autothink_run_rejects_empty_query():
    r = c.post("/api/autothink/run", json={"query": "   ", "provider": "local"})
    assert r.status_code == 422


def test_autothink_routes_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/autothink/models" in paths
    assert "/api/autothink/run" in paths
    assert "/api/autothink/history" in paths


def test_reference_docs_mount_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/reference" in paths
