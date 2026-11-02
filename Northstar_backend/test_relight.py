"""Relight lane: the official graph wiring, the noise guard, and the package rule."""
from __future__ import annotations

import io
import json
import random
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quality_gate as qg  # noqa: E402
import relight  # noqa: E402


def _smooth() -> bytes:
    im = Image.new("RGB", (128, 128))
    for y in range(128):
        for x in range(128):
            im.putpixel((x, y), (x * 2 % 255, y * 2 % 255, 120))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _noise() -> bytes:
    rnd = random.Random(7)
    im = Image.new("RGB", (128, 128))
    for y in range(128):
        for x in range(128):
            im.putpixel((x, y), (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_the_graph_patches_a_base_checkpoint_with_the_iclight_unet():
    graph = relight.build_graph("src.png", width=768, height=768)
    assert graph["7"]["class_type"] == "CheckpointLoaderSimple"
    assert graph["7"]["inputs"]["ckpt_name"] == relight.BASE_CHECKPOINT
    assert graph["10"]["inputs"]["unet_name"] == relight.IC_MODEL
    # The bug this rewrite fixes: the IC-Light unet is a patch, never the base model.
    assert graph["11"]["inputs"]["model"] == ["7", 0]
    assert graph["11"]["inputs"]["ic_model"] == ["10", 0]
    assert graph["11"]["inputs"]["c_concat"] == ["6", 0]


def test_the_foreground_is_greyed_and_scaled_to_the_canvas():
    graph = relight.build_graph("src.png", width=768, height=512)
    assert graph["5"]["class_type"] == "ICLightApplyMaskGrey"
    assert graph["2"]["inputs"]["width"] == 768
    assert graph["2"]["inputs"]["height"] == 512
    assert graph["6"]["inputs"]["pixels"] == ["5", 0]


def test_the_sampler_uses_an_empty_latent_and_the_documented_settings():
    graph = relight.build_graph("src.png", width=768, height=768, steps=20)
    assert graph["12"]["class_type"] == "EmptyLatentImage"
    sampler = graph["13"]["inputs"]
    assert sampler["latent_image"] == ["12", 0]
    assert sampler["denoise"] == 0.9
    assert sampler["sampler_name"] == "dpmpp_2m_sde"
    assert sampler["scheduler"] == "karras"


def test_the_noise_metric_separates_a_render_from_garbage():
    assert relight.noise_metric(_smooth()) < relight.NOISE_LIMIT
    assert relight.noise_metric(_noise()) > relight.NOISE_LIMIT


def test_a_noise_decode_is_refused_with_the_reason():
    with pytest.raises(relight.RelightUnavailable) as caught:
        relight.assert_usable(_noise())
    assert "relight_output_is_noise" in str(caught.value)


def test_a_partial_download_is_not_availability(tmp_path, monkeypatch):
    (tmp_path / "checkpoints").mkdir()
    (tmp_path / "unet").mkdir()
    (tmp_path / "background_removal").mkdir()
    (tmp_path / "checkpoints" / relight.BASE_CHECKPOINT).write_bytes(b"x" * 1024)
    (tmp_path / "unet" / relight.IC_MODEL).write_bytes(b"x" * 1024)
    (tmp_path / "background_removal" / relight.BG_MODEL).write_bytes(b"x" * 1024)
    monkeypatch.setattr(relight, "_models_dir", lambda: tmp_path)
    state = relight.availability()
    assert state["available"] is False
    assert state["partial"], "a 1 KB file must be reported as partial, not ready"


def _result() -> dict:
    return {"png": _smooth(), "base_checkpoint": relight.BASE_CHECKPOINT,
            "ic_model": relight.IC_MODEL, "prompt": "soft studio light",
            "size": [768, 768], "steps": 20, "cfg": 2.0, "denoise": 0.9,
            "seed": 1, "seconds": 9.1, "noise_metric": 2.8}


def _axes(ok: bool) -> dict:
    return {"available": True, "model": "m", "axes": {
        "design_alignment": ({"status": "pass"} if ok else
                             {"status": "fail", "reason": "brief_mismatch"}),
        "layout": {"status": "pass"},
        "material": {"status": "recorded", "finish": "matte"},
        "typography": {"status": "not_applicable"},
        "form": {"status": "not_applicable"}}}


def test_a_passing_relight_is_packaged(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "score", lambda *a, **k: _axes(True))
    out = relight.package(_result(), source_asset_id="src-1", out_root=tmp_path,
                          run_id="relight_test")
    folder = Path(out["folder"])
    assert sorted(p.name for p in folder.iterdir()) == ["manifest.json", "relit.png"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "relight"
    assert manifest["source_asset_id"] == "src-1"
    assert manifest["quality"]["verdict"]["ok"] is True
    assert manifest["noise_metric"] == 2.8
    assert "typography" in manifest["quality"]["verdict"]["not_applicable"]


def test_a_failing_gate_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(qg, "score", lambda *a, **k: _axes(False))
    out = relight.package(_result(), out_root=tmp_path, run_id="relight_bad")
    assert out["folder"] is None
    assert out["verdict"]["ok"] is False
    assert not (tmp_path / "relight_bad").exists()


def test_the_endpoint_reports_an_unknown_asset(tmp_path):
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-relight"
    try:
        r = TestClient(app).post("/api/design-studio/relight",
                                 json={"asset_id": "no-such-asset"})
        assert r.status_code in (404, 409, 422), r.text
        if r.status_code == 404:
            assert r.json()["detail"] == "Asset not found"
    finally:
        app.dependency_overrides = {}
