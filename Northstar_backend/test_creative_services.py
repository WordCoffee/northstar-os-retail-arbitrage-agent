"""Tests for the creative service lanes: moderation, storage, providers, and the
/api/listing-forge | /api/social | /api/ad-pilot routes.

Offline and deterministic: the service modules fall back to templates, and the
local LLM is pointed at a closed port so nothing hangs or reaches a provider.
"""

from __future__ import annotations

import pytest
from PIL import Image  # noqa: F401  (keeps Pillow import warm; not used directly)

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative import moderation, providers, storage  # noqa: E402
from creative.service_routes import (  # noqa: E402
    adpilot_router, capabilities_router, listing_router, social_router,
)

import listing_forge  # noqa: E402
import social_pulse  # noqa: E402


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    # Deterministic + fast: force template fallbacks, never a provider call.
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(listing_forge, "_call_llm", lambda *a, **k: "", raising=False)


@pytest.fixture()
def client():
    app = FastAPI()
    for r in (listing_router, social_router, adpilot_router, capabilities_router):
        app.include_router(r)
    return TestClient(app)


PRODUCT = {
    "title": "Mogra Organics Organic Turmeric Powder",
    "brand": "Mogra Organics",
    "category": "Grocery & Gourmet Food",
    "price": 24.99,
    "weight": "5 lb",
}


# ---------------------------------------------------------------------------
# Moderation
# ---------------------------------------------------------------------------

def test_moderation_blocks_regulated_claim():
    r = moderation.screen_text("This supplement will cure everything")
    assert r.allowed is False
    assert any(f["term"] == "cure" for f in r.flags)


def test_moderation_word_boundary_no_false_positive():
    assert moderation.screen_text("A secure, manicured, procured listing").allowed is True


def test_moderation_allows_clean_and_requires_review():
    r = moderation.screen_text("Organic turmeric powder, earthy and golden")
    assert r.allowed is True
    assert r.review_required is True


def test_moderation_payload_walks_nested_strings():
    r = moderation.screen_payload({"a": ["ok", {"b": "USDA certified"}]})
    assert r.allowed is False
    assert r.checked >= 2


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def test_local_storage_roundtrip(tmp_path):
    be = storage.LocalBackend(root=tmp_path)
    info = be.put("a/b.png", b"hello", "image/png")
    assert info["bytes"] == 5
    assert be.exists("a/b.png")
    assert be.get("a/b.png") == b"hello"
    assert be.url("a/b.png").endswith("a/b.png") or be.url("a/b.png").endswith("b.png")
    assert "a/b.png" in be.list()


def test_local_storage_blocks_traversal(tmp_path):
    be = storage.LocalBackend(root=tmp_path)
    with pytest.raises(storage.StorageUnavailable):
        be.put("../escape.png", b"x")


def test_storage_status_defaults_local(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_MEDIA_STORAGE", raising=False)
    s = storage.storage_status()
    assert s["backend"] == "local" and s["configured"] is True


def test_storage_status_s3_without_bucket(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MEDIA_STORAGE", "s3")
    monkeypatch.delenv("NORTHSTAR_S3_BUCKET", raising=False)
    s = storage.storage_status()
    assert s["backend"] == "s3" and s["configured"] is False
    with pytest.raises(storage.StorageUnavailable):
        storage.get_backend()


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

def test_provider_status_shape(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    st = providers.provider_status(probe_local=True)
    assert "local" in st and "cloud" in st and "write" in st
    assert set(st["cloud"]) == {"fal", "openrouter", "replicate"}
    assert st["media_live_armed"] is False


def test_write_policy_defaults_off():
    wp = providers.write_policy()
    assert wp["publishing"]["armed"] is False
    assert wp["ad_spend"]["requires_approval"] is True


def test_cloud_armed_requires_flag_and_key(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "present-but-never-read")
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    assert providers.cloud_armed("fal") is False
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    assert providers.cloud_armed("fal") is True


# ---------------------------------------------------------------------------
# ListingForge lane
# ---------------------------------------------------------------------------

def test_listing_generate(client):
    r = client.post("/api/listing-forge/generate", json={"product": PRODUCT})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True and j["review_required"] is True
    assert j["title"]["title"]
    assert isinstance(j["bullets"]["bullets"], list) and j["bullets"]["bullets"]
    assert j["description"]["description"]
    assert "composite" in j["score"]
    assert "ok" in j["compliance"]


def test_listing_generate_requires_product(client):
    r = client.post("/api/listing-forge/generate", json={})
    assert r.status_code == 400


def test_listing_generate_blocked_by_moderation(client):
    bad = {**PRODUCT, "title": "USDA certified miracle turmeric"}
    r = client.post("/api/listing-forge/generate", json={"product": bad})
    assert r.status_code == 422
    assert "moderation" in r.json()["detail"]["message"]


def test_listing_score_and_compliance(client):
    s = client.post("/api/listing-forge/score", json={
        "product": PRODUCT, "title": "Organic Turmeric Powder 5 lb Bold Golden",
        "bullets": ["Premium organic turmeric powder", "Earthy golden flavor"],
        "description": "Organic turmeric powder for daily cooking."})
    assert s.status_code == 200 and "composite" in s.json()["score"]
    c = client.post("/api/listing-forge/compliance", json={"title": "Clean title", "brand": "Mogra Organics"})
    assert c.status_code == 200 and "ok" in c.json()


# ---------------------------------------------------------------------------
# SocialPulse lane
# ---------------------------------------------------------------------------

def test_social_caption(client):
    r = client.post("/api/social/caption", json={"product": PRODUCT, "platform": "instagram"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["caption"]
    assert j["review_required"] is True


def test_social_calendar(client):
    r = client.post("/api/social/calendar", json={"products": [PRODUCT], "days": 7})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and isinstance(j["calendar"], list) and j["days"] >= 1


def test_social_brand_voice_upload_path(client, monkeypatch):
    store = {}

    def fake_save(brand, profile, account_id="default"):
        store[brand] = {**profile, "brand": brand}
        return "entry-123"

    monkeypatch.setattr(social_pulse, "save_brand_voice", fake_save)
    monkeypatch.setattr(social_pulse, "load_brand_voice", lambda b: store.get(b, {"brand": b}))

    r = client.post("/api/social/brand-voice", json={
        "brand": "Mogra Organics",
        "profile": {"tone": "warm", "emoji_usage": "light"}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["entry_id"] == "entry-123"
    assert j["saved"]["tone"] == "warm"

    g = client.get("/api/social/brand-voice", params={"brand": "Mogra Organics"})
    assert g.status_code == 200 and g.json()["voice"]["tone"] == "warm"


def test_social_brand_voice_requires_profile(client):
    r = client.post("/api/social/brand-voice", json={"brand": "Mogra Organics"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# AdPilot lane (planning only)
# ---------------------------------------------------------------------------

def test_adpilot_bid_recommendation(client):
    r = client.post("/api/ad-pilot/bid-recommendation", json={
        "keyword": "turmeric powder", "current_bid": 0.75, "acos": 42.0,
        "target_acos": 30.0, "clicks": 25, "orders": 1, "impressions": 900})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and "recommended_bid" in j
    assert "no live ad change" in j["notice"]


def test_adpilot_target_acos(client):
    r = client.post("/api/ad-pilot/target-acos", json={"product_cost": 8.0, "amazon_price": 24.99})
    assert r.status_code == 200 and r.json()["ok"]


def test_adpilot_negatives_and_structure(client):
    n = client.post("/api/ad-pilot/negative-candidates", json={"keywords": [
        {"keyword": "free turmeric", "clicks": 20, "orders": 0}]})
    assert n.status_code == 200 and "candidates" in n.json()
    s = client.post("/api/ad-pilot/campaign-structure", json={
        "asin": "B0TEST123", "product_title": "Mogra Turmeric", "keywords": ["turmeric"]})
    assert s.status_code == 200 and s.json()["ok"]


# ---------------------------------------------------------------------------
# Capabilities
# ---------------------------------------------------------------------------

def test_capabilities_endpoint(client, monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
    r = client.get("/api/creative/capabilities")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    ids = {s["id"] for s in j["services"]}
    assert {"creativestudio", "listingforge", "socialpulse", "adpilot"} <= ids
    assert j["storage"]["backend"] == "local"
    assert j["moderation"]["require_review"] is True
