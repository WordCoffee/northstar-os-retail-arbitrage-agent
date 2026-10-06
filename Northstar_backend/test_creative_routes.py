"""Offline API tests for the /api/creative/* mockup routes."""

from __future__ import annotations

import base64
import io
import json

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative.routes import router  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:59999")  # offline
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _png_b64(size=(256, 256), color=(255, 255, 255)) -> str:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_health_offline(client):
    r = client.get("/api/creative/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["comfyui"]["up"] is False
    assert "clip" in body["models"]


def test_presets_endpoint(client):
    r = client.get("/api/creative/presets")
    assert r.status_code == 200
    body = r.json()
    assert body["brand"]["name"] == "Mogra Organics"
    assert body["brand"]["tagline"] == "Fuel Your Focus."
    assert "mogra_5lb_clear_handled_pet_jar" in body["containers"]


def test_compose_endpoint(client):
    body = {
        "product": "organic_black_peppercorns",
        "container": "mogra_5lb_clear_handled_pet_jar",
        "source_base64": _png_b64(),
        "filename": "unit_compose.png",
    }
    r = client.post("/api/creative/compose", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["ok"] is True
    assert out["url"] == "/api/creative/file/unit_compose.png"
    assert client.get(out["url"]).status_code == 200


def test_compose_rejects_invented_compliance(client):
    body = {
        "brand": "Mogra Organics",
        "product_name": "Organic Turmeric Powder",
        "net_weight": "NET WT. 5 LB (2.27 kg)",
        "extra_lines": ["USDA Organic"],
        "surface": "plain_rectangle",
        "source_base64": _png_b64(),
    }
    r = client.post("/api/creative/compose", json=body)
    assert r.status_code == 422
    assert "usda" in r.json()["detail"].lower()


def test_compose_requires_source(client):
    r = client.post("/api/creative/compose",
                    json={"product": "organic_turmeric_powder",
                          "surface": "plain_rectangle"})
    assert r.status_code == 400


def test_mockup_requires_product(client):
    r = client.post("/api/creative/mockup", json={"generate": False})
    assert r.status_code == 400


def test_mockup_offline_upload_composes(client):
    body = {
        "product": "organic_white_onion_powder",
        "container": "mogra_32oz_standup_pouch",
        "source_base64": _png_b64(),
    }
    r = client.post("/api/creative/mockup", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["lane"] == "composited_only"
    assert client.get(out["url"]).status_code == 200


def test_mockup_generate_without_comfy_is_503(client):
    r = client.post("/api/creative/mockup",
                    json={"product": "organic_turmeric_powder", "generate": True})
    assert r.status_code == 503


def test_file_endpoint_blocks_traversal(client):
    assert client.get("/api/creative/file/not-a-real-file.png").status_code == 404
    r = client.get("/api/creative/file/bad%20name.png")
    assert r.status_code in (400, 404)
