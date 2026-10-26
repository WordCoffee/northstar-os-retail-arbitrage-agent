"""Batch 0 - AutothinK workspace API is mounted in the main app (smoke).

Offline: only asserts route existence + response shape. Does NOT call Ollama
(that path is exercised manually / by the live smoke pass).

P0-04 (2026-10-09): these routes used to be public. They now require a session,
so the smoke assertions are 401 without one and 200 with one. The test builds a
real token and patches only the user lookup, so no operator database is read.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient  # noqa: E402

import auth  # noqa: E402
from main import app  # noqa: E402

c = TestClient(app)

_TEST_EMAIL = "smoke@northstar.local"


def _token(tenant: str = "tenant-smoke") -> str:
    return auth.create_access_token(
        "user-smoke", _TEST_EMAIL, "autothink", role="owner", tenant_id=tenant
    )


def _as_tenant(tenant: str = "tenant-smoke"):
    return patch.object(auth, "get_user", return_value={
        "id": "user-smoke", "email": _TEST_EMAIL, "plan": "autothink",
        "role": "owner", "tenant_id": tenant,
    })


def test_autothink_models_route_exists_and_shaped():
    with _as_tenant():
        r = c.get("/api/autothink/models", headers={"Authorization": "Bearer " + _token()})
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("local_available", "cloud_available", "models"):
        assert key in body
    assert isinstance(body["models"], list)


def test_autothink_history_route_exists():
    with _as_tenant():
        r = c.get("/api/autothink/history?limit=5",
                  headers={"Authorization": "Bearer " + _token()})
    assert r.status_code == 200
    body = r.json()
    assert "entries" in body and "total" in body


def test_autothink_run_rejects_empty_query():
    with _as_tenant():
        r = c.post("/api/autothink/run", json={"query": "   ", "provider": "local"},
                   headers={"Authorization": "Bearer " + _token()})
    assert r.status_code == 422


def test_autothink_models_refuses_without_a_session():
    r = c.get("/api/autothink/models")
    assert r.status_code == 401, r.text


def test_autothink_history_refuses_without_a_session():
    r = c.get("/api/autothink/history?limit=5")
    assert r.status_code == 401, r.text


def test_autothink_run_refuses_without_a_session():
    r = c.post("/api/autothink/run", json={"query": "hello", "provider": "local"})
    assert r.status_code == 401, r.text


def test_autothink_routes_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/api/autothink/models" in paths
    assert "/api/autothink/run" in paths
    assert "/api/autothink/history" in paths
    assert "/api/autothink/cancel" in paths
    assert "/api/autothink/usage" in paths
    assert "/api/autothink/jobs/{run_id}" in paths


def test_reference_docs_mount_registered():
    paths = {getattr(route, "path", "") for route in app.routes}
    assert "/reference" in paths


def test_autothink_history_empty_store_non_5xx():
    with _as_tenant(tenant="tenant-empty"):
        r = c.get("/api/autothink/history?limit=5",
                  headers={"Authorization": "Bearer " + _token("tenant-empty")})
    assert r.status_code < 500, r.text


def test_autothink_usage_empty_store_non_5xx():
    with _as_tenant(tenant="tenant-empty2"):
        r = c.get("/api/autothink/usage",
                  headers={"Authorization": "Bearer " + _token("tenant-empty2")})
    assert r.status_code < 500, r.text


def test_autothink_job_missing_run_non_5xx():
    with _as_tenant(tenant="tenant-empty3"):
        r = c.get("/api/autothink/jobs/does-not-exist",
                  headers={"Authorization": "Bearer " + _token("tenant-empty3")})
    assert r.status_code < 500, r.text
    assert r.status_code == 404


def test_autothink_run_non_5xx_on_empty_store():
    with _as_tenant(tenant="tenant-empty4"):
        r = c.post("/api/autothink/run", json={"query": "hello", "provider": "local"},
                   headers={"Authorization": "Bearer " + _token("tenant-empty4")})
    assert r.status_code < 500, r.text