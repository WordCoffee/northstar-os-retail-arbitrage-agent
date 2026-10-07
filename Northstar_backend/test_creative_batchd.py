"""Tests for Batch D: gated cloud generation, video spec, the write-action
approval workflow, and asset upload.

Offline and deterministic: cloud/video are exercised at the *gate* and at the
payload level (the network is never touched); approvals use an isolated index.
"""

from __future__ import annotations

import base64
import io

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative import approvals, assets, cloud, video  # noqa: E402
from creative.routes import router as creative_router  # noqa: E402
from creative.service_routes import (  # noqa: E402
    approvals_router, assets_router, media_router,
)


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    monkeypatch.setenv("NORTHSTAR_APPROVALS_INDEX", str(tmp_path / "approvals.json"))
    monkeypatch.delenv("NORTHSTAR_MEDIA_DIR", raising=False)
    monkeypatch.delenv("NORTHSTAR_ASSET_INDEX", raising=False)
    monkeypatch.delenv("NORTHSTAR_MEDIA_STORAGE", raising=False)
    for k in ("FAL_KEY", "OPENROUTER_API_KEY", "REPLICATE_API_TOKEN",
              "MEDIA_GEN_LIVE", "NORTHSTAR_SOCIAL_PUBLISH_ARMED", "NORTHSTAR_ADS_WRITE_ARMED"):
        monkeypatch.delenv(k, raising=False)
    return tmp_path


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(creative_router)
    for r in (media_router, approvals_router, assets_router):
        app.include_router(r)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Cloud client — request shapes (pure)
# ---------------------------------------------------------------------------

def test_build_request_shapes():
    fal = cloud.build_request("fal", "a jar", model="fal-ai/flux-2-pro")
    assert fal["url"].endswith("fal-ai/flux-2-pro")
    assert fal["payload"]["prompt"] == "a jar"

    orr = cloud.build_request("openrouter", "ad copy", model="openai/gpt-image-2")
    assert orr["url"].endswith("/images/generations")
    assert orr["payload"]["model"] == "openai/gpt-image-2"

    rep = cloud.build_request("replicate", "scene")
    assert rep["url"].endswith("/predictions")
    assert rep["payload"]["input"]["prompt"] == "scene"

    with pytest.raises(cloud.ProviderUnavailable):
        cloud.build_request("nope", "x")


def test_estimate_cost():
    assert cloud.estimate_cost("fal", "flux.2-pro") == 0.03
    assert cloud.estimate_cost("openrouter", "gpt-image-2-high") == 0.18
    assert cloud.estimate_cost("fal", "unknown-model") is None


def test_cloud_generate_gated_without_key(monkeypatch):
    with pytest.raises(cloud.ProviderUnavailable):
        cloud.generate("a jar", "fal", "unused.png")


def test_cloud_generate_gated_without_flag(monkeypatch):
    monkeypatch.setenv("FAL_KEY", "present-never-read")
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    with pytest.raises(cloud.ProviderUnavailable):
        cloud.generate("a jar", "fal", "unused.png")


def test_cloud_generate_armed_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("FAL_KEY", "present-never-read")
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    seen = {}

    def fake_post(url, payload, headers, timeout=120):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization", "")
        return {"images": [{"url": "https://cdn.example/out.png"}]}

    monkeypatch.setattr(cloud, "_post_json", fake_post)
    monkeypatch.setattr(cloud, "_http", lambda url, **kw: b"\x89PNG-bytes")
    out = tmp_path / "cloud.png"
    res = cloud.generate("a jar", "fal", out)
    assert res["provider"] == "fal" and res["cost_estimate"] is not None
    assert out.read_bytes() == b"\x89PNG-bytes"
    assert seen["url"].startswith("https://fal.run/")
    assert seen["auth"].startswith("Key ")   # header built without exposing the key


# ---------------------------------------------------------------------------
# Video spec
# ---------------------------------------------------------------------------

def test_video_cost_math():
    assert video.estimate_video_cost("wan-2.5", 15) == 0.75
    assert video.estimate_video_cost("kling-2.6-pro", 15, audio=True) == 2.1
    assert video.estimate_video_cost("nope", 5) is None


def test_video_request_builder():
    req = video.build_video_request("kling-2.6-pro", "person unboxing", duration=15, aspect="9:16")
    assert req["payload"]["duration"] == 15 and req["payload"]["aspect_ratio"] == "9:16"
    img = video.build_video_request("kling-v3-i2v", "pan", image_url="https://x/y.png")
    assert img["payload"]["image_url"] == "https://x/y.png"
    with pytest.raises(ValueError):
        video.build_video_request("nope", "x")


def test_video_generate_gated():
    with pytest.raises(cloud.ProviderUnavailable):
        video.generate_video("wan-2.5", "a clip")


def test_video_catalog_flags_watermark():
    cat = video.video_catalog()
    assert "veo-3.1-fast" in cat["models"]
    assert video.VIDEO_MODELS["veo-3.1-fast"]["watermark"] == "SynthID"


# ---------------------------------------------------------------------------
# Approval workflow
# ---------------------------------------------------------------------------

def test_approval_flow_pending_approved_disarmed():
    rec = approvals.request("social_publish", {"post": "hello"}, requested_by="op")
    assert rec["status"] == "pending"
    assert approvals.get(rec["id"])["kind"] == "social_publish"

    approvals.decide(rec["id"], approve=True, by="owner")
    assert approvals.get(rec["id"])["status"] == "approved"

    # approved but not armed -> honest block
    out = approvals.execute(rec["id"])
    assert out["executed"] is False and out["reason"] == "write_actions_disarmed"


def test_approval_execute_requires_approval():
    rec = approvals.request("ads_write", {"cid": "1"})
    out = approvals.execute(rec["id"])
    assert out["executed"] is False and out["reason"] == "not_approved"


def test_approval_armed_but_not_configured(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ADS_WRITE_ARMED", "1")
    rec = approvals.request("ads_write", {"cid": "1"})
    approvals.decide(rec["id"], approve=True, by="owner")
    out = approvals.execute(rec["id"])
    assert out["executed"] is False and out["reason"] == "not_configured"
    assert "AMAZON_ADS_REFRESH_TOKEN" in out["missing"]


def test_approval_reject():
    rec = approvals.request("social_publish", {})
    approvals.decide(rec["id"], approve=False, by="owner", note="not now")
    assert approvals.get(rec["id"])["status"] == "rejected"
    assert approvals.execute(rec["id"])["reason"] == "not_approved"


def test_approval_posture():
    p = approvals.posture()
    assert set(p["kinds"]) == {"social_publish", "ads_write"}
    assert p["kinds"]["ads_write"]["approval_kind"] == "real_money"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def test_cloud_route_gated(client):
    r = client.post("/api/creative/cloud/generate", json={"prompt": "a jar", "provider": "fal"})
    assert r.status_code == 503
    assert "not armed" in r.json()["detail"]


def test_video_estimate_route(client):
    r = client.get("/api/creative/video/estimate", params={"model": "wan-2.5", "seconds": 15})
    assert r.status_code == 200 and r.json()["cost_estimate"] == 0.75
    m = client.get("/api/creative/video/models")
    assert m.status_code == 200 and "models" in m.json()


def test_video_generate_route_gated(client):
    r = client.post("/api/creative/video/generate", json={"prompt": "clip", "model": "wan-2.5"})
    assert r.status_code == 503


def test_approvals_routes(client):
    c = client.post("/api/creative/approvals", json={"kind": "social_publish", "payload": {"x": 1}})
    assert c.status_code == 200, c.text
    rid = c.json()["request"]["id"]
    d = client.post(f"/api/creative/approvals/{rid}/decide", json={"approve": True})
    assert d.status_code == 200 and d.json()["request"]["status"] == "approved"
    e = client.post(f"/api/creative/approvals/{rid}/execute")
    assert e.status_code == 200 and e.json()["executed"] is False
    lst = client.get("/api/creative/approvals")
    assert lst.status_code == 200 and lst.json()["posture"]["pending"] == 0


def test_approvals_bad_kind(client):
    assert client.post("/api/creative/approvals", json={"kind": "nope"}).status_code == 400


def test_asset_upload_route(client, tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), (200, 180, 90)).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    r = client.post("/api/creative/assets/upload",
                    json={"filename": "uploaded.png", "data_base64": b64, "product": "turmeric"})
    assert r.status_code == 200, r.text
    assert r.json()["asset"]["key"] == "uploaded.png"
    assert (tmp_path / "uploaded.png").exists()
    assert any(a["key"] == "uploaded.png" for a in assets.list_assets())


def test_asset_upload_requires_fields(client):
    assert client.post("/api/creative/assets/upload", json={"filename": "x.png"}).status_code == 400
