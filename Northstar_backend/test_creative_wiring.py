"""Tests for the credential-gated wiring: cloud scene lane, S3 file serving,
the readiness doctor, and the live write clients behind approvals.

Offline. Cloud/video and write calls are exercised at the gate, the payload level,
and via injected fakes — the network is never touched.
"""

from __future__ import annotations

import io
import sys
import types

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative import approvals, mogra_mockup, storage, write_clients  # noqa: E402
from creative.routes import router as creative_router  # noqa: E402
from creative.service_routes import approvals_router, media_router  # noqa: E402


class _ClientError(Exception):
    pass


def _fake_boto3(monkeypatch):
    store: dict = {}

    class FakeClient:
        def put_object(self, Bucket, Key, Body, ContentType=None):
            store[Key] = Body

        def get_object(self, Bucket, Key):
            if Key not in store:
                raise _ClientError("NoSuchKey")
            return {"Body": io.BytesIO(store[Key])}

        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://s3.example/{Params['Bucket']}/{Params['Key']}?sig=signed"

        def head_object(self, Bucket, Key):
            if Key not in store:
                raise _ClientError("404")
            return {}

    boto3 = types.ModuleType("boto3")
    boto3.client = lambda *a, **k: FakeClient()
    monkeypatch.setitem(sys.modules, "boto3", boto3)
    bo = types.ModuleType("botocore")
    ex = types.ModuleType("botocore.exceptions")
    ex.ClientError = _ClientError
    monkeypatch.setitem(sys.modules, "botocore", bo)
    monkeypatch.setitem(sys.modules, "botocore.exceptions", ex)
    return store


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    monkeypatch.setenv("NORTHSTAR_APPROVALS_INDEX", str(tmp_path / "approvals.json"))
    for k in ("NORTHSTAR_MEDIA_DIR", "NORTHSTAR_ASSET_INDEX", "NORTHSTAR_MEDIA_STORAGE",
              "NORTHSTAR_S3_BUCKET", "MEDIA_GEN_LIVE", "FAL_KEY", "OPENROUTER_API_KEY",
              "REPLICATE_API_TOKEN", "NORTHSTAR_SOCIAL_PUBLISH_ARMED",
              "NORTHSTAR_ADS_WRITE_ARMED", "COMFYUI_URL", "X_ACCESS_TOKEN",
              "AMAZON_ADS_REFRESH_TOKEN", "AMAZON_ADS_CLIENT_ID", "AMAZON_ADS_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")
    return tmp_path


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(creative_router)
    for r in (media_router, approvals_router):
        app.include_router(r)
    return TestClient(app)


# ---------------------------------------------------------------------------
# #2 object store — end-to-end file serving
# ---------------------------------------------------------------------------

def test_local_file_route_serves_file(client, tmp_path):
    Image.new("RGB", (24, 24), (10, 20, 30)).save(tmp_path / "a.png")
    r = client.get("/api/creative/file/a.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"


def test_s3_file_route_redirects_to_signed_url(monkeypatch, tmp_path):
    _fake_boto3(monkeypatch)
    monkeypatch.setenv("NORTHSTAR_MEDIA_STORAGE", "s3")
    monkeypatch.setenv("NORTHSTAR_S3_BUCKET", "bkt")
    storage.get_backend().put("signed.png", b"data", "image/png")

    app = FastAPI()
    app.include_router(creative_router)
    c = TestClient(app, follow_redirects=False)
    r = c.get("/api/creative/file/signed.png")
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://s3.example/bkt/")
    assert "sig=signed" in r.headers["location"]


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

def test_doctor_reports_missing_and_probes_storage(client):
    r = client.get("/api/creative/doctor")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["storage"]["probe"]["roundtrip"] is True          # local round-trip
    missing = " ".join(j["missing_to_arm"])
    assert "FAL_KEY" in missing and "MEDIA_GEN_LIVE=1" in missing
    assert "social" in j["write_clients"] and "ads" in j["write_clients"]


# ---------------------------------------------------------------------------
# #1 cloud scene lane
# ---------------------------------------------------------------------------

def test_scene_lane_cloud_unarmed_is_honest(tmp_path):
    src = None
    with pytest.raises(RuntimeError) as ei:
        mogra_mockup.build_mockup(
            product="organic_turmeric_powder", container="mogra_5lb_clear_handled_pet_jar",
            generate=True, scene_lane="cloud", cloud_provider="fal",
            out_path=tmp_path / "x.png")
    assert "cloud not armed" in str(ei.value)


def test_scene_lane_auto_no_lane_is_honest(tmp_path):
    with pytest.raises(RuntimeError):
        mogra_mockup.build_mockup(
            product="organic_turmeric_powder", container="mogra_5lb_clear_handled_pet_jar",
            generate=True, scene_lane="auto", out_path=tmp_path / "x.png")


# ---------------------------------------------------------------------------
# #3 write clients
# ---------------------------------------------------------------------------

def test_social_request_builders():
    assert write_clients.build_social_request("x", {"text": "hi"})["url"].endswith("/2/tweets")
    assert "image_url" in write_clients.build_social_request("instagram", {"caption": "c"})["payload"]
    assert "message" in write_clients.build_social_request("facebook", {"caption": "c"})["payload"]
    assert write_clients.build_social_request("linkedin", {"caption": "c"})["url"].endswith("/ugcPosts")
    assert write_clients.build_social_request("tiktok", {"caption": "c"})["url"].startswith("https://open.tiktokapis.com")
    with pytest.raises(write_clients.WriteUnavailable):
        write_clients.build_social_request("myspace", {})


def test_publish_not_configured(monkeypatch):
    monkeypatch.delenv("X_ACCESS_TOKEN", raising=False)
    with pytest.raises(write_clients.WriteUnavailable) as ei:
        write_clients.publish("x", {"text": "hi"})
    assert "X_ACCESS_TOKEN" in ei.value.missing


def test_ads_not_ready(monkeypatch):
    assert write_clients.ads_ready() is False
    with pytest.raises(write_clients.WriteUnavailable) as ei:
        write_clients.ads_write({"bid": 1})
    assert set(ei.value.missing) == set(write_clients.ADS_ENVS)


def test_approved_armed_but_not_configured(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ADS_WRITE_ARMED", "1")
    rec = approvals.request("ads_write", {"campaign": "c1"})
    approvals.decide(rec["id"], approve=True, by="owner")
    out = approvals.execute(rec["id"])
    assert out["executed"] is False and out["reason"] == "not_configured"
    assert "AMAZON_ADS_REFRESH_TOKEN" in out["missing"]


def test_approved_armed_and_configured_executes(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_SOCIAL_PUBLISH_ARMED", "1")
    monkeypatch.setenv("X_ACCESS_TOKEN", "present-never-read")
    called = {}

    def fake_publish(platform, post):
        called["platform"] = platform
        return {"published": True, "platform": platform, "status": 200}

    monkeypatch.setattr(write_clients, "publish", fake_publish)
    rec = approvals.request("social_publish", {"platform": "x", "text": "hello"},
                            requested_by="op")
    approvals.decide(rec["id"], approve=True, by="owner")
    out = approvals.execute(rec["id"])
    assert out["executed"] is True and out["result"]["published"] is True
    assert called["platform"] == "x"
    assert approvals.get(rec["id"])["status"] == "executed"


def test_posture_reports_configured_flags():
    p = approvals.posture()
    assert p["kinds"]["social_publish"]["configured"] is False
    assert "social_platforms" in p and "ads" in p
