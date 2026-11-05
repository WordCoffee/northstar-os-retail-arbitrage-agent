"""Stitched shorts: plan the clips, render them chained, stitch and gate.

The engine is injected. These tests prove the orchestration that turns a 15 s
request into six sampler calls and one checked MP4, and that a failed picture
gate leaves no file behind.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import quality_gate as qg
import shorts
import video_stitch as vs


def _lavfi_clip(path: Path, frames: int) -> Path:
    result = subprocess.run([
        vs.FFMPEG, "-y", "-f", "lavfi",
        "-i", "testsrc2=size=480x832:rate=16:duration=10",
        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-500:]
    return path


def _frame_png() -> bytes:
    from io import BytesIO
    from PIL import Image
    buf = BytesIO()
    Image.new("RGB", (64, 96), (180, 170, 150)).save(buf, format="PNG")
    return buf.getvalue()


def test_sampler_canvas_caps_the_long_edge_at_832():
    assert shorts.sampler_canvas(1080, 1920) == (464, 832)
    assert shorts.sampler_canvas(1920, 1080) == (832, 464)
    assert shorts.sampler_canvas(1080, 1080) == (832, 832)


def test_a_multi_clip_request_is_stitched_from_the_plan(tmp_path):
    calls = []

    def render(source, *, prompt, width, height, length, steps, cfg, seed, fps):
        calls.append({"w": width, "h": height, "frames": length, "seed": seed})
        clip = _lavfi_clip(tmp_path / f"clip_{len(calls)}.mp4", length)
        return {"video": clip.read_bytes(), "frames": []}

    out = tmp_path / "short.mp4"
    result = shorts.generate_stitched(b"PNG", out_path=out, platform="tiktok",
                                      seconds=3, render=render)
    assert result["ok"] is True
    assert len(calls) == 2
    assert {c["frames"] for c in calls} == {45}
    assert {c["seed"] for c in calls} == {1, 2}
    assert (calls[0]["w"], calls[0]["h"]) == (464, 832)
    assert result["render_canvas"] == [464, 832]
    assert result["final"]["nb_frames"] == 90
    assert out.is_file()


def test_a_failed_picture_gate_deletes_the_stitched_file(tmp_path, monkeypatch):
    def render(source, *, prompt, width, height, length, steps, cfg, seed, fps):
        clip = _lavfi_clip(tmp_path / f"clip_{seed}.mp4", length)
        return {"video": clip.read_bytes(), "frames": [_frame_png()]}

    monkeypatch.setattr(qg, "score", lambda *a, **k: {"score": 1.0})
    monkeypatch.setattr(qg, "verdict", lambda scored: {"ok": False,
                                                       "reasons": ["copy_not_readable"]})
    monkeypatch.setattr(qg, "manifest_block", lambda scored, verdict: {"score": scored})
    out = tmp_path / "refused.mp4"
    result = shorts.generate_stitched(b"PNG", out_path=out, platform="tiktok",
                                      seconds=3, render=render)
    assert result["ok"] is False
    assert "video_quality_refused" in result["reason"]
    assert not out.exists()


def test_the_shorts_endpoint_wires_the_stitched_branch(tmp_path, monkeypatch):
    """The endpoint's stitched branch must actually run, not just the service.

    The orchestration tests above passed while the endpoint raised
    ``NameError: uuid`` on the first real multi-clip request: the branch had
    never been executed. This drives the route itself with the engine stubbed,
    so a missing import or a renamed helper fails here instead of after a
    twenty-minute render.
    """
    import design_studio_api as api
    import studio_generation as sg
    from fastapi.testclient import TestClient
    from main import app

    media = tmp_path / "data" / "studio_generated"
    media.mkdir(parents=True)
    (media / "src.png").write_bytes(_frame_png())
    # The route derives the asset directory from its own __file__; point that at
    # tmp_path so the test never writes into the real data directory.
    monkeypatch.setattr(api, "__file__", str(tmp_path / "design_studio_api.py"))

    class _Assets:
        def get_by_id(self, asset_id, account_id=None):
            return {"storage_key": "src.png"}

    class _DesignStudio:
        assets = _Assets()

    class _DB:
        design_studio = _DesignStudio()

    monkeypatch.setattr(api, "get_northstar_db", lambda: _DB())
    monkeypatch.setattr(sg, "engine_status",
                        lambda: {"armed": True, "reachable": True, "engine": "stub"})

    captured = {}

    def fake_stitched(source, *, out_path, platform, seconds=None, **kw):
        captured.update({"platform": platform, "seconds": seconds,
                         "bytes_in": len(source)})
        Path(out_path).write_bytes(b"stub-mp4")
        return {"ok": True, "checks": {"duration_ok": True},
                "quality": {"verdict": {"ok": True}}, "seconds": 1.0,
                "final": {"nb_frames": 462}}

    monkeypatch.setattr(shorts, "generate_stitched", fake_stitched)
    app.dependency_overrides[api.studio_account] = lambda: "org-t2"
    try:
        client = TestClient(app)
        response = client.post("/api/design-studio/shorts", json={
            "asset_id": "asset-1", "prompt": "the pouch rotates on a pale sweep",
            "platform": "shorts", "seconds": 15, "steps": 20})
    finally:
        app.dependency_overrides = {}
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True
    assert "short_stitched_" in Path(body["file"]).name
    assert Path(body["file"]).name.endswith(".mp4")
    assert body["format"]["clips"] == 6
    assert captured == {"platform": "shorts", "seconds": 15.0, "bytes_in": len(_frame_png())}
