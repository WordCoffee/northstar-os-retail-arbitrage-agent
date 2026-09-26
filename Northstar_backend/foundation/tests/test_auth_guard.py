"""Auth guard tests (Phase 1C-01): client-host resolution, proxy trust, dev-shim
locality, and remote-without-auth denial.

Amendment criteria covered here: G3 (reverse proxy cannot appear loopback),
G4 (forwarded headers trusted only from configured proxies), G6 (dev headers
ignored outside local development), G7 (fail-closed).
"""
from __future__ import annotations

import types

from fastapi.testclient import TestClient

from Northstar_backend.foundation.authn import (
    effective_client_host, is_loopback_host, trusted_proxies,
)
from Northstar_backend.foundation.tests.conftest import owner_headers


def _req(host, headers=None):
    return types.SimpleNamespace(
        client=types.SimpleNamespace(host=host) if host is not None else None,
        headers=headers or {},
    )


# --- is_loopback_host --------------------------------------------------------

def test_loopback_hosts():
    for h in ("127.0.0.1", "127.0.0.5", "::1", "localhost", "testclient"):
        assert is_loopback_host(h)
    for h in ("10.0.0.1", "203.0.113.9", "example.com", None, ""):
        assert not is_loopback_host(h)


# --- effective_client_host ---------------------------------------------------

def test_direct_loopback_peer():
    assert effective_client_host(_req("127.0.0.1"), trusted=set()) == "127.0.0.1"


def test_remote_peer_without_forwarding():
    assert effective_client_host(_req("203.0.113.9"), trusted=set()) == "203.0.113.9"


def test_spoofed_xff_from_untrusted_peer_is_not_honored():
    # A loopback-ish or remote peer that is NOT a trusted proxy sends XFF=127.0.0.1.
    r = _req("testclient", headers={"x-forwarded-for": "127.0.0.1"})
    host = effective_client_host(r, trusted=set())
    assert host == "untrusted-proxy"
    assert not is_loopback_host(host)  # cannot masquerade as local


def test_trusted_proxy_honors_xff_chain():
    r = _req("10.0.0.2", headers={"x-forwarded-for": "203.0.113.9, 10.0.0.2"})
    host = effective_client_host(r, trusted={"10.0.0.2"})
    assert host == "203.0.113.9"
    assert not is_loopback_host(host)


def test_trusted_proxy_loopback_client_stays_loopback():
    r = _req("10.0.0.2", headers={"x-forwarded-for": "127.0.0.1"})
    host = effective_client_host(r, trusted={"10.0.0.2"})
    assert host == "127.0.0.1"
    assert is_loopback_host(host)


def test_missing_client_info_is_none():
    assert effective_client_host(_req(None), trusted=set()) is None


def test_trusted_proxies_parsing(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_TRUSTED_PROXIES", "10.0.0.1, 10.0.0.2")
    assert trusted_proxies() == {"10.0.0.1", "10.0.0.2"}


# --- dev-shim locality (HTTP) ------------------------------------------------

def test_unauthenticated_localhost_is_rejected(client):
    r = client.get("/api/v1/foundation/me")
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_dev_shim_allowed_on_loopback(client, seeded_state):
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 200
    assert r.json()["role"] == "organization_owner"


def test_dev_shim_rejected_from_remote_client(seeded_state):
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    remote = TestClient(app, client=("203.0.113.9", 5000))
    r = remote.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "authentication_required"


def test_spoofed_xff_from_remote_peer_cannot_bypass(seeded_state):
    from Northstar_backend.foundation.app import create_app
    app = create_app()
    app.state.foundation = seeded_state
    remote = TestClient(app, client=("203.0.113.9", 5000))
    r = remote.get("/api/v1/foundation/me",
                   headers={"X-Forwarded-For": "127.0.0.1",
                            **owner_headers(seeded_state)})
    assert r.status_code == 401


def test_dev_headers_ignored_outside_development(client, seeded_state, monkeypatch):
    # ENVIRONMENT=production + no dev shim -> dev headers must be ignored.
    monkeypatch.setenv("ENVIRONMENT", "production")
    r = client.get("/api/v1/foundation/me", headers=owner_headers(seeded_state))
    assert r.status_code == 401