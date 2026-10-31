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
    # Local TEXT tiers resolve to Bojo, the resident CPU-pinned Ollama model that
    # actually serves T1-T3. The Ty 27B orchestrator is a llama.cpp worker on
    # 127.0.0.1:8080, not an Ollama model, so it is not a chat tier.
    assert mr.resolve("local", "T1").model == "bojo"
    assert mr.resolve("local", "T2").model == "bojo"
    assert mr.resolve("local", "T3").model == "bojo"
    # The suite and the router must not drift apart again.
    for tier in ("T1", "T2", "T3"):
        assert mr.SUITE["text"]["tiers"][tier]["local"] == "bojo"
        assert mr.SUITE["text"]["tiers"][tier]["local_engine"] == "bojo"
    # Vision tiers use a dedicated VL model: the 27B text model ships no
    # projector (ollama show capabilities: tools/thinking/completion only).
    assert mr.resolve("local", "V1").model == "qwen2.5vl:7b"
    assert mr.resolve("local", "T2").available is True


def test_local_text_tier_reports_a_missing_model(tmp_path):
    """A configured-but-absent local model must not advertise itself as ready."""
    r = mr.resolve("local", "T2", installed=["qwen2.5vl:7b"])
    assert r.available is False and r.reason == "local_model_not_installed"
    ok = mr.resolve("local", "T2", installed=["bojo", "qwen2.5vl:7b"])
    assert ok.available is True and ok.reason == "ok"


def test_installed_matching_ignores_ollama_latest_tag():
    """Ollama reports `bojo:latest`; the suite names `bojo`. Same model."""
    r = mr.resolve("local", "T2", installed=["bojo:latest", "qwen2.5vl:7b"])
    assert r.available is True and r.reason == "ok"
    assert mr.resolve("local", "V1", installed=["qwen2.5vl:7b"]).available is True


def test_no_local_alternate_is_advertised():
    """The old qwen3:14b fallback was never on disk."""
    assert mr.LOCAL_ALTERNATES == {}
    assert mr.catalog(["bojo"])["local"]["alternates"] == {}


def test_local_engines_are_documented_from_the_measured_profile():
    engines = mr.catalog(["bojo"])["local_engines"]
    ty, bojo = engines["ty"], engines["bojo"]
    # The measured profile is authoritative: the current launcher runs 17408
    # context with q8_0 KV. The old 65536/q4_0 line was a target, not the
    # running config (the suite description says so).
    assert ty["context_tokens"] == 17408 and ty["kv_cache"].startswith("q8_0")
    assert ty["residency"].startswith("on demand")
    assert bojo["gpu_layers"] == 0 and bojo["context_tokens"] == 8192


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
    c = mr.catalog(["bojo", "qwen2.5vl:7b"])
    assert c["providers"] == ["local", "cloud"]
    assert "T2" in c["tiers"] and "V3" in c["tiers"]
    assert c["local"]["defaults"]["T2"] == "bojo"
    assert c["local"]["installed"] == ["bojo", "qwen2.5vl:7b"]
    assert c["text_local_status"] == {"T1": "ok", "T2": "ok", "T3": "ok"}
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


# --- service + vision resolution (Phase A / A2) ---

def test_resolve_for_service_cloud_default():
    d = mr.resolve_for_service("goldengoose")
    assert d["known"] is True and d["tier"] == "T2"
    assert d["resolution"].model == "deepseek/deepseek-v4-flash-0731"
    assert mr.resolve_for_service("listingforge")["media"] == ["V2", "V3"]


def test_resolve_for_service_t1_services():
    for svc in ("sourcescout", "thewatch", "rankledger", "rivalboard", "theledger"):
        assert mr.resolve_for_service(svc)["tier"] == "T1"


def test_resolve_for_service_operator_local():
    d = mr.resolve_for_service("autothink", provider="local")
    assert d["resolution"].model == "bojo"
    assert d["escalation_tier"] == "T3"


def test_resolve_for_service_unknown_fails_closed():
    d = mr.resolve_for_service("does_not_exist")
    assert d["known"] is False and d["reason"] == "unknown_service"


def test_resolve_vision_understand_cloud():
    r = mr.resolve_vision("V1", "cloud", "understand")
    assert r.model == "qwen/qwen3.7-flash"
    assert r.backend == "openrouter"
    assert r.available is False and r.reason == "not_armed"


def test_resolve_vision_understand_local():
    r = mr.resolve_vision("V2", "local", "understand")
    assert r.model == "qwen2.5vl:7b" and r.available is True


def test_resolve_vision_generate_local_comfyui():
    r = mr.resolve_vision("V1", "local", "generate")
    assert r.backend == "comfyui" and r.model == "comfyui:flux2-klein-4b" and r.available is True


def test_resolve_vision_generate_cloud_gated():
    final = mr.resolve_vision("V2", "cloud", "generate", quality="final")
    assert final.model == "flux.2-pro" and final.backend == "fal"
    assert final.available is False  # no FAL_KEY / MEDIA_GEN_LIVE


# --- local vision truthfulness (2026-10-22) ---

def test_resolve_vision_local_missing_model_is_not_available():
    r = mr.resolve_vision("V1", "local", "understand", installed=["northstaros-qwen3.8:27b"])
    assert r.available is False
    assert r.reason == "local_model_not_installed"
    assert r.model == "qwen2.5vl:7b"  # config value still reported


def test_resolve_vision_local_present_model_is_available():
    r = mr.resolve_vision("V1", "local", "understand",
                          installed=["qwen2.5vl:7b", "northstaros-qwen3.8:27b"])
    assert r.available is True and r.reason == "ok"


def test_catalog_vision_local_status_tracks_installed():
    missing = mr.catalog([])["vision_local_status"]
    assert set(missing.values()) == {"local_model_not_installed"}
    present = mr.catalog(["qwen2.5vl:7b"])["vision_local_status"]
    assert set(present.values()) == {"ok"}


def test_media_armed_requires_gate(monkeypatch):
    assert mr.media_live_armed() is False
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    assert mr.media_live_armed() is True


def test_catalog_includes_suite_and_services():
    c = mr.catalog([])
    assert "vision" in c and "services" in c
    assert "goldengoose" in c["services"]
    assert "media_armed" in c
