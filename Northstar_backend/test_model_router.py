"""Phase H / H2 — dual-engine model router tests (offline)."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import model_router as mr  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for n in ("OPENROUTER_API_KEY", "OPENAI_API_KEY", "CLOUD_MODEL_LIVE"):
        monkeypatch.delenv(n, raising=False)
    yield


# --- local resolution ---

def test_local_defaults_by_tier():
    assert mr.resolve("local", "T1").model == "qwen3:4b"
    assert mr.resolve("local", "T2").model == "northstar-qwen3:rev1"
    assert mr.resolve("local", "T3").model == "northstar-qwen3:rev1"
    assert mr.resolve("local", "V1").model == "qwen2.5vl:7b"
    assert mr.resolve("local", "T2").available is True


def test_local_model_override():
    r = mr.resolve("local", "T2", "qwen3:14b")
    assert r.model == "qwen3:14b" and r.available is True


# --- cloud resolution + gating ---

def test_cloud_not_armed_without_key():
    r = mr.resolve("cloud", "T2")
    assert r.available is False and r.reason == "cloud_not_armed"


def test_cloud_not_armed_with_key_but_no_flag(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "present")
    r = mr.resolve("cloud", "T2")
    assert r.available is False and r.reason == "cloud_not_armed"


def test_cloud_armed_resolves_deepseek_lane(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "present")
    monkeypatch.setenv("CLOUD_MODEL_LIVE", "1")
    t2 = mr.resolve("cloud", "T2")
    assert t2.available is True
    assert t2.model == "deepseek/deepseek-v4-flash-0731"
    assert t2.pin == "relace/fp4"
    t3 = mr.resolve("cloud", "T3")
    assert t3.model == "deepseek/deepseek-v4.1-flash" and t3.pin == "deepinfra/fp8"
    t1 = mr.resolve("cloud", "T1")
    assert t1.model.endswith(":free")


def test_cloud_vision_unavailable():
    r = mr.resolve("cloud", "V1")
    assert r.available is False and r.reason == "cloud_tier_unavailable"


# --- bad input ---

def test_unknown_provider_and_tier():
    assert mr.resolve("quantum", "T2").reason == "unknown_provider"
    assert mr.resolve("local", "T9").reason == "unknown_tier"


# --- consent policy ---

def test_consent_on_escalation_only():
    assert mr.requires_consent("T1", "T2") is True
    assert mr.requires_consent("T2", "T3") is True
    assert mr.requires_consent("T2", "T1") is False
    assert mr.requires_consent("T2", "T2") is False
    assert mr.requires_consent(None, "T3") is False


def test_consent_prompt_shape():
    p = mr.consent_prompt("T1", "T3")
    assert p["code"] == "tier_change_consent"
    assert p["from_tier"] == "T1" and p["to_tier"] == "T3"
    assert mr.consent_prompt("T2", "T1") is None


# --- credit weights + catalog ---

def test_credit_weights_are_ordered():
    w = mr.TIER_CREDIT_WEIGHT
    assert w["T1"] < w["T2"] < w["T3"]
    assert w["V1"] < w["V2"] < w["V3"]


def test_catalog_shape():
    c = mr.catalog(["qwen3:4b", "northstar-qwen3:rev1"])
    assert c["providers"] == ["local", "cloud"]
    assert "T2" in c["tiers"] and "V3" in c["tiers"]
    assert c["local"]["defaults"]["T2"] == "northstar-qwen3:rev1"
    assert c["local"]["installed"] == ["qwen3:4b", "northstar-qwen3:rev1"]
    assert c["cloud"]["live_armed"] is False


# --- endpoint ---

def test_models_endpoint_envelope(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
    from fastapi.testclient import TestClient
    from main import app
    c = TestClient(app)
    r = c.get("/api/v1/models")
    assert r.status_code == 200
    b = r.json()
    assert b["contract"] == "bff/v1" and b["status"] == "ok"
    assert "local" in b["data"] and "cloud" in b["data"]
    # Presence flags are booleans; the actual value depends on the runtime
    # environment (importing main may load .env), so never assert a value.
    assert isinstance(b["data"]["cloud"]["key_present"], bool)
    assert isinstance(b["data"]["cloud"]["live_armed"], bool)
