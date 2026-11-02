"""Shorts lane: the graph wiring, the frame gate, and the refuse-to-write rule."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quality_gate as qg  # noqa: E402
import shorts  # noqa: E402


def _png(size=(64, 96), colour=(180, 170, 150)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, colour).save(buf, format="PNG")
    return buf.getvalue()


def _result() -> dict:
    return {"video": b"WEBMDATA", "frames": [_png(), _png((64, 96), (150, 160, 170))],
            "frame_count": 33, "fps": 16, "size": [480, 832], "steps": 20,
            "cfg": 5.0, "seed": 7, "model": shorts.WAN_UNET, "seconds": 51.6,
            "video_bytes": 8}


def test_frame_count_snaps_to_the_wan_lattice():
    assert shorts.frame_count(33) == 33
    assert shorts.frame_count(20) == 17
    assert shorts.frame_count(9) == 9
    assert shorts.frame_count(30) == 29


def test_the_graph_uses_the_installed_models_and_samples_the_start_image():
    graph = shorts.build_graph("src.png", width=480, height=832, length=33)
    assert graph["1"]["inputs"]["unet_name"] == shorts.WAN_UNET
    assert graph["2"]["inputs"]["type"] == "wan"
    assert graph["5"]["inputs"]["vae_name"] == shorts.WAN_VAE
    assert graph["7"]["inputs"]["length"] == 33
    assert graph["7"]["inputs"]["start_image"] == ["6", 0]
    assert graph["9"]["inputs"]["latent_image"] == ["7", 0]
    assert graph["10"]["inputs"]["samples"] == ["9", 0]
    assert graph["11"]["class_type"] == "SaveWEBM"
    assert graph["12"]["class_type"] == "SaveImage"      # frames for the gate


def test_a_failing_verdict_writes_nothing(tmp_path, monkeypatch):
    def refuse(*a, **k):
        return {"available": True, "model": "m", "axes": {
            "form": {"status": "not_applicable"},
            "design_alignment": {"status": "pass"},
            "layout": {"status": "fail", "reason": "layout_unbalanced",
                       "detail": "product cut off"},
            "typography": {"status": "not_applicable"},
            "material": {"status": "recorded", "finish": "matte"}}}

    monkeypatch.setattr(qg, "score", refuse)
    out = shorts.package_render(_result(), brief="b", text_requested=False,
                                run_id="short_test", out_root=tmp_path)
    assert out["folder"] is None
    assert out["verdict"]["ok"] is False
    assert not (tmp_path / "short_test").exists()


def test_a_passing_clip_is_packaged_with_its_frames(tmp_path, monkeypatch):
    def accept(*a, **k):
        return {"available": True, "model": "qwen3.5:4b", "axes": {
            "form": {"status": "not_applicable"},
            "design_alignment": {"status": "pass"},
            "layout": {"status": "pass"},
            "typography": {"status": "not_applicable", "reason": "no_text_requested"},
            "material": {"status": "recorded", "finish": "kraft"}}}

    monkeypatch.setattr(qg, "score", accept)
    out = shorts.package_render(_result(), brief="b", text_requested=False,
                                run_id="short_ok", out_root=tmp_path)
    folder = Path(out["folder"])
    names = sorted(p.name for p in folder.iterdir())
    assert names == ["frame_00.png", "frame_01.png", "manifest.json", "short.webm"]
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["kind"] == "shorts_clip"
    assert manifest["frames"] == 33 and manifest["fps"] == 16
    assert manifest["duration_seconds"] == 2.06
    assert manifest["quality"]["verdict"]["ok"] is True

    def nulls(obj, path="m"):
        found = []
        if obj is None:
            found.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(nulls(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(nulls(v, f"{path}[{i}]"))
        return found

    assert nulls(manifest) == []
