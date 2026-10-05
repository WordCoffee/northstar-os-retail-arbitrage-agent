"""Creative media readiness contract — offline, no network, no secrets.

These tests exercise the pure ``build_readiness`` contract with monkeypatched
gate/backend accessors and fake probes. Nothing here installs, starts, arms, or
contacts a provider, and no engine is probed over the network.
"""
from __future__ import annotations

import json

import pytest

from foundation.api import creative


def _readiness(monkeypatch, *, armed, local, cloud, probe):
    monkeypatch.setattr(creative, "_media_live_armed", lambda: armed)
    monkeypatch.setattr(creative, "_local_generation_configured", lambda: local)
    monkeypatch.setattr(creative, "_cloud_key_present", lambda: cloud)
    return creative.build_readiness(probe=probe)


def test_default_is_planned_not_armed(monkeypatch):
    r = _readiness(monkeypatch, armed=False, local=True, cloud=False, probe=lambda: "reachable")
    assert r["generation"] == "planned_not_armed"
    assert r["reason"] == "media_gate_off"
    assert r["armed"] is False
    assert r["media_live"] is False
    assert r["provider_gated"] is False
    assert r["backend"] == "local"
    assert r["local_engine"] == {"state": "reachable", "kind": "comfyui"}


def test_armed_local_reachable_is_local_available(monkeypatch):
    r = _readiness(monkeypatch, armed=True, local=True, cloud=False, probe=lambda: "reachable")
    assert r["generation"] == "local_available"
    assert r["armed"] is True


def test_armed_local_unreachable_with_cloud_key_is_provider_gated(monkeypatch):
    r = _readiness(monkeypatch, armed=True, local=True, cloud=True, probe=lambda: "unreachable")
    assert r["generation"] == "provider_gated"
    assert r["provider_gated"] is True
    assert r["local_engine"]["state"] == "unreachable"


def test_armed_no_backend_is_unavailable(monkeypatch):
    r = _readiness(monkeypatch, armed=True, local=False, cloud=False, probe=lambda: "unreachable")
    assert r["generation"] == "unavailable"
    assert r["backend"] == "none"


def test_probe_failure_is_a_state_not_a_crash(monkeypatch):
    def boom():
        raise RuntimeError("probe exploded")

    r = _readiness(monkeypatch, armed=False, local=True, cloud=False, probe=boom)
    assert r["local_engine"]["state"] == "unknown"
    assert r["generation"] == "planned_not_armed"


def test_probe_unknown_is_accepted(monkeypatch):
    r = _readiness(monkeypatch, armed=False, local=True, cloud=False, probe=lambda: "weird")
    assert r["local_engine"]["state"] == "unknown"


def test_contract_leaks_no_secrets(monkeypatch):
    r = _readiness(monkeypatch, armed=False, local=True, cloud=False, probe=lambda: "reachable")
    blob = json.dumps(r).lower()
    # No credential material, no raw env/config values, no endpoint URLs.
    for forbidden in ("api_key", "token", "secret", "password", "http://", "https://", "comfyui_url"):
        assert forbidden not in blob
    # Only booleans / safe identifiers are exposed for provider state.
    assert isinstance(r["cloud_key_present"], bool)
    assert r["cloud_key_present"] is False
    assert set(r["local_engine"].keys()) == {"state", "kind"}


def test_readiness_route_is_registered():
    paths = {getattr(route, "path", "") for route in creative.router.routes}
    assert "/api/v1/foundation/creative/readiness" in paths


def test_readiness_route_returns_contract_when_authenticated(client, seeded_state, monkeypatch):
    from conftest import make_access_token, bearer
    monkeypatch.setattr(creative, "_media_live_armed", lambda: False)
    monkeypatch.setattr(creative, "probe_local_engine", lambda: "unreachable")
    token = make_access_token(seeded_state.ids["user"], org=seeded_state.ids["org"])
    r = client.get("/api/v1/foundation/creative/readiness", headers=bearer(token))
    assert r.status_code == 200
    body = r.json()
    assert body["generation"] == "planned_not_armed"
    assert body["armed"] is False
    assert body["media_live"] is False
    assert "notes" in body
    # Path B provider architecture is present but unarmed.
    assert isinstance(body.get("providers"), list)
    assert isinstance(body.get("routing_hooks"), dict)
    assert isinstance(body.get("spend_caps"), dict)
    assert body["spend_caps"].get("enforced") is False
    assert isinstance(body.get("local_setup"), dict)
    assert body["local_setup"].get("ready_for_local_generation") is False
    assert isinstance(body.get("pipeline"), dict)
    assert "stages" in body["pipeline"]

