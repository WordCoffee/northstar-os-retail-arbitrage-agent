"""Phase H / H1 — operator-only private-alpha gate tests (offline)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import alpha_gate  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for name in ("NORTHSTAR_PRIVATE_ALPHA", "NORTHSTAR_ALPHA_ALLOWLIST"):
        monkeypatch.delenv(name, raising=False)
    yield


# --- config helpers ---

def test_alpha_off_by_default(monkeypatch):
    assert alpha_gate.private_alpha_enabled() is False
    assert alpha_gate.decide("GET", "/api/v1/products", None) == (False, "alpha_off")


def test_allowlist_parsing(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", " A@x.com , b@y.com ,")
    assert alpha_gate.alpha_allowlist() == {"a@x.com", "b@y.com"}
    assert alpha_gate.is_allowlisted("A@X.COM") is True
    assert alpha_gate.is_allowlisted("nope@z.com") is False
    assert alpha_gate.is_allowlisted(None) is False


def test_public_paths_never_blocked(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    for p in ("/health", "/api/health", "/api/v1/plans", "/legal/terms",
              "/ui", "/ui/jobs", "/ui/assets/index.js", "/autothink/ui/index.html", "/"):
        assert alpha_gate.decide("GET", p, None) == (False, "public_path"), p


def test_empty_allowlist_fails_closed(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.delenv("NORTHSTAR_ALPHA_ALLOWLIST", raising=False)
    blocked, reason = alpha_gate.decide("GET", "/api/v1/products", None)
    assert blocked is True and reason == "empty_allowlist_fail_closed"


def test_allowlisted_email_passes(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    assert alpha_gate.decide("POST", "/api/v1/listings/generate", "op@x.com") == (False, "allowlisted")


def test_non_allowlisted_blocked(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    blocked, reason = alpha_gate.decide("GET", "/api/v1/products", "other@y.com")
    assert blocked is True and reason == "not_allowlisted"
    # anonymous (demo fallback) is also blocked
    assert alpha_gate.decide("GET", "/api/v1/products", None)[0] is True


# --- token identity ---

def test_identity_from_bearer_token(monkeypatch):
    import auth
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    tok = auth.create_access_token("acct1", "op@x.com", "autothink", role="owner")
    assert alpha_gate.identity_email_from_auth_header("Bearer " + tok) == "op@x.com"
    assert alpha_gate.identity_email_from_auth_header("Bearer garbage") is None
    assert alpha_gate.identity_email_from_auth_header(None) is None
    assert alpha_gate.identity_email_from_auth_header("Token abc") is None


# --- middleware integration ---

def test_middleware_blocks_when_locked(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/api/v1/credits/me")
    assert r.status_code == 403
    body = r.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "private_alpha_locked"


def test_middleware_allows_health_when_locked(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    assert c.get("/health").status_code == 200


def test_middleware_allows_when_alpha_off(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    assert c.get("/api/v1/plans").status_code in (200, 404)


def test_root_redirects_to_ui_in_private_alpha(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/ui"


def test_root_serves_ui_when_alpha_off(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_PRIVATE_ALPHA", raising=False)
    monkeypatch.delenv("NORTHSTAR_ROOT_TO_APP", raising=False)
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"] == "/ui"


def test_root_redirects_to_ui_even_without_gate(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_PRIVATE_ALPHA", raising=False)
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/ui"


def test_auth_paths_are_public_under_gate(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    for p in ("/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"):
        assert alpha_gate.decide("POST", p, None) == (False, "public_path"), p


def test_register_blocked_for_non_allowlisted_under_gate(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_PRIVATE_ALPHA", "1")
    monkeypatch.setenv("NORTHSTAR_ALPHA_ALLOWLIST", "op@x.com")
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.post("/api/v1/auth/register",
               json={"email": "stranger@y.com", "password": "password123"})
    assert r.status_code == 403
    assert "restricted" in r.json()["detail"].lower()
