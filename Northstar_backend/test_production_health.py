"""Readiness for the API process: the snapshot and the `/readyz` route.

The snapshot is pure and local, so most of these tests need no app. The route
tests import `main` (as the rest of the suite already does) and prove the HTTP
contract: 200 when ready, 503 with the failing checks when not.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import production_health as ph

_EXPECTED_CHECKS = {
    "rate_limit_posture",
    "redaction",
    "data_dir_writable",
    "ui_build",
    "foundation_store",
    "live_posture",
}


def test_snapshot_is_ready_in_this_tree():
    snapshot = ph.readiness_snapshot()
    assert snapshot["status"] == "ready", snapshot["failed_checks"]
    assert snapshot["failed_checks"] == []
    assert set(snapshot["checks"]) == _EXPECTED_CHECKS
    for name, check in snapshot["checks"].items():
        assert "ok" in check and "critical" in check, name
    assert snapshot["service"] == "northstar-backend"
    assert snapshot["uptime_seconds"] >= 0
    json.dumps(snapshot)  # the route serialises it as-is


def test_a_failed_critical_check_makes_the_process_not_ready(monkeypatch):
    monkeypatch.setattr(
        ph, "_check_redaction",
        lambda: {"ok": False, "critical": True, "reason": "filter missing"},
    )
    snapshot = ph.readiness_snapshot()
    assert snapshot["status"] == "not-ready"
    assert snapshot["failed_checks"] == ["redaction"]
    assert snapshot["checks"]["redaction"]["reason"] == "filter missing"


def test_a_failed_non_critical_check_does_not_drain_the_process(monkeypatch):
    monkeypatch.setattr(
        ph, "_check_ui_build",
        lambda: {"ok": False, "critical": False, "reason": "no dist"},
    )
    snapshot = ph.readiness_snapshot()
    assert snapshot["status"] == "ready"
    assert snapshot["failed_checks"] == []


def test_the_ui_build_is_only_critical_in_production_like_environments(monkeypatch, tmp_path):
    monkeypatch.setattr(ph, "REPO_ROOT", tmp_path)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    check = ph._check_ui_build()
    assert check["present"] is False
    assert check["critical"] is False
    assert check["ok"] is True

    for environment in ("production", "staging", "beta"):
        monkeypatch.setenv("ENVIRONMENT", environment)
        check = ph._check_ui_build()
        assert check["critical"] is True, environment
        assert check["ok"] is False, environment
        assert ph.readiness_snapshot()["status"] == "not-ready", environment


def test_a_missing_foundation_store_is_not_ready(monkeypatch, tmp_path):
    monkeypatch.delenv("DB_URL", raising=False)
    monkeypatch.delenv("FOUNDATION_DB_URL", raising=False)
    monkeypatch.setenv("FOUNDATION_DB_PATH", str(tmp_path / "absent.db"))
    check = ph._check_foundation_store()
    assert check["checked"] is False
    assert check["ok"] is False
    assert check["critical"] is True


def test_a_postgres_backend_is_reported_not_probed(monkeypatch):
    monkeypatch.setenv("DB_URL", "postgresql://northstar@postgres/northstar")
    check = ph._check_foundation_store()
    assert check["backend"] == "postgres"
    assert check["checked"] is False
    assert check["ok"] is True
    assert check["critical"] is False


def test_environment_is_reported_as_unset(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    assert ph.readiness_snapshot()["environment"] == "unset"
    monkeypatch.setenv("ENVIRONMENT", "Production")
    assert ph.readiness_snapshot()["environment"] == "production"


# ---------------------------------------------------------------------------
# The HTTP surface
# ---------------------------------------------------------------------------

def test_readyz_routes_answer_ready():
    from fastapi.testclient import TestClient

    import main

    client = TestClient(main.app)
    for path in ("/readyz", "/health/readyz"):
        response = client.get(path)
        assert response.status_code == 200, path
        body = response.json()
        assert body["status"] == "ready"
        assert set(body["checks"]) == _EXPECTED_CHECKS


def test_readyz_answers_503_with_the_failing_checks(monkeypatch):
    from fastapi.testclient import TestClient

    import main

    monkeypatch.setattr(
        ph, "readiness_snapshot",
        lambda: {"status": "not-ready", "failed_checks": ["foundation_store"],
                 "checks": {"foundation_store": {"ok": False}}},
    )
    client = TestClient(main.app)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["failed_checks"] == ["foundation_store"]


def test_the_readiness_routes_are_exempt_from_the_rate_limiter():
    source = (Path(__file__).resolve().parent / "rate_limiter.py").read_text(
        encoding="utf-8", errors="replace")
    for path in ("/health", "/health/detailed", "/health/readyz", "/readyz"):
        assert f'"{path}"' in source, path


def test_probe_local_reads_a_live_json_payload():
    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):  # keep the test output quiet
            return

        def do_GET(self):  # noqa: N802 - stdlib naming
            body = json.dumps({"status": "ready", "checks": {}}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/readyz"
        result = ph.probe_local(url, timeout=2.0)
    finally:
        server.shutdown()
        server.server_close()
    assert result["status_code"] == 200
    assert result["body"]["status"] == "ready"
