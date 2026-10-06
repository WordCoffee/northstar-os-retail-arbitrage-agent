"""Tests for the local image-generation core (offline: no engine, no network).

These lock the three things that matter for an armed lane:
  1. the workflow is the *proven* FLUX graph, not an invented one;
  2. every refusal path raises a stable ``code`` BEFORE any work happens;
  3. the localhost-only boundary actually refuses a non-loopback engine.
"""
from __future__ import annotations

import base64

import pytest

from Northstar_backend import local_image_gen as lig


def test_workflow_is_the_proven_flux_graph():
    wf = lig.build_flux_workflow("a mug", 1024, 768, 28, 42)
    assert wf["1"]["class_type"] == "UNETLoader"
    assert wf["2"]["class_type"] == "DualCLIPLoader"
    assert wf["2"]["inputs"]["type"] == "flux"
    assert wf["3"]["class_type"] == "VAELoader"
    assert wf["4"]["inputs"]["text"] == "a mug"
    assert wf["6"]["inputs"] == {"width": 1024, "height": 768, "batch_size": 1}
    assert wf["7"]["inputs"]["steps"] == 28
    assert wf["7"]["inputs"]["seed"] == 42
    assert wf["7"]["inputs"]["cfg"] == 1.0
    # wiring: sampler <- model/pos/neg/latent, decode <- sampler, save <- decode
    assert wf["7"]["inputs"]["model"] == ["1", 0]
    assert wf["7"]["inputs"]["latent_image"] == ["6", 0]
    assert wf["8"]["inputs"]["samples"] == ["7", 0]
    assert wf["9"]["inputs"]["images"] == ["8", 0]


@pytest.mark.parametrize("kwargs,code", [
    (dict(prompt="   ", width=1024, height=1024, steps=28), "empty_prompt"),
    (dict(prompt="x" * (lig.MAX_PROMPT_CHARS + 1), width=1024, height=1024, steps=28), "prompt_too_long"),
    (dict(prompt="x", width=64, height=1024, steps=28), "bad_dimension"),
    (dict(prompt="x", width=1024, height=99999, steps=28), "bad_dimension"),
    (dict(prompt="x", width=1024, height=1024, steps=0), "bad_steps"),
    (dict(prompt="x", width=1024, height=1024, steps=999), "bad_steps"),
])
def test_validation_refuses_before_any_work(kwargs, code):
    with pytest.raises(lig.GenerationError) as ei:
        lig.generate_image(**kwargs)
    assert ei.value.code == code


def test_gate_off_refuses(monkeypatch):
    monkeypatch.setattr(lig, "media_gate_on", lambda: False)
    with pytest.raises(lig.GenerationError) as ei:
        lig.generate_image("x", 1024, 1024, 28)
    assert ei.value.code == "media_gate_off"
    assert ei.value.status == 409


def test_non_loopback_engine_is_refused(monkeypatch):
    monkeypatch.setenv("COMFYUI_URL", "http://example.com:8188")
    with pytest.raises(lig.GenerationError) as ei:
        lig._assert_loopback(lig.engine_url())
    assert ei.value.code == "engine_not_localhost"


def test_unreachable_engine_refuses(monkeypatch):
    monkeypatch.setattr(lig, "media_gate_on", lambda: True)
    monkeypatch.setattr(lig, "engine_reachable", lambda *a, **k: False)
    with pytest.raises(lig.GenerationError) as ei:
        lig.generate_image("x", 1024, 1024, 28)
    assert ei.value.code == "engine_unreachable"
    assert ei.value.status == 503


def test_data_url_roundtrip():
    payload = b"\x89PNG\r\n\x1a\nnot-really-a-png"
    url = lig.to_data_url({"image_bytes": payload, "mime": "image/png"})
    assert url.startswith("data:image/png;base64,")
    assert base64.b64decode(url.split(",", 1)[1]) == payload


# --------------------------------------------------------------------------- #
# route contract (core mocked: no engine, no network)
# --------------------------------------------------------------------------- #

_PATH = "/api/v1/foundation/creative/generate"


def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from Northstar_backend.foundation.api import creative
    from Northstar_backend.foundation.api.deps import get_context

    app = FastAPI()
    app.include_router(creative.router)
    app.dependency_overrides[get_context] = lambda: object()
    return TestClient(app), creative


def test_route_success_shape(monkeypatch):
    client, creative = _client()
    mod = creative._local_image_gen()

    monkeypatch.setattr(mod, "generate_image", lambda *a, **k: {
        "prompt_id": "pid-1", "seconds": 1.5, "width": 1024, "height": 1024,
        "steps": 28, "seed": 7, "engine": "http://127.0.0.1:8188",
        "bytes": 1234, "mime": "image/png", "image_bytes": b"png",
    })
    monkeypatch.setattr(mod, "to_data_url", lambda r: "data:image/png;base64,AAAA")

    res = client.post(_PATH, json={"prompt": "a mug", "width": 1024, "height": 1024, "steps": 28})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["image"].startswith("data:image/png;base64,")
    assert body["prompt_id"] == "pid-1"
    assert body["seed"] == 7


@pytest.mark.parametrize("code,status", [
    ("media_gate_off", 409),
    ("engine_unreachable", 503),
    ("timeout", 504),
])
def test_route_maps_refusal_codes(monkeypatch, code, status):
    client, creative = _client()
    mod = creative._local_image_gen()

    def _boom(*a, **k):
        raise mod.GenerationError(code, f"refused: {code}", status=status)

    monkeypatch.setattr(mod, "generate_image", _boom)
    res = client.post(_PATH, json={"prompt": "a mug"})
    assert res.status_code == status
    assert res.json()["detail"]["code"] == code


def test_route_rejects_non_integer_steps():
    client, _ = _client()
    res = client.post(_PATH, json={"prompt": "a mug", "steps": "abc"})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "bad_request"
