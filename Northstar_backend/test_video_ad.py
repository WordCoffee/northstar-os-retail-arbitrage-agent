"""End-to-end video: script -> clips -> stitch -> captions -> audio -> checks.

The scene renderer is synthetic; the stitch, caption and audio stages are real.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import video_ad
import video_stitch as vs

PRODUCT = {
    "brand": "MOGRA", "product": "LION'S MANE", "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)", "claims": ["100% PURE", "NO FILLERS"],
}


def _fake_render(scene, frames):
    tmp = Path(scene.get("_tmp") or ".")
    path = tmp / f"clip_{scene['index']}_{frames}.mp4"
    result = subprocess.run([
        vs.FFMPEG, "-y", "-f", "lavfi",
        "-i", "testsrc2=size=480x832:rate=30:duration=10",
        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return path.read_bytes()


def test_the_whole_pipeline_produces_a_checked_video(tmp_path):
    def render(scene, frames):
        scene = {**scene, "_tmp": str(tmp_path)}
        return _fake_render(scene, frames)

    manifest = video_ad.produce(PRODUCT, platform="tiktok", seconds=3,
                                out_dir=tmp_path / "out", render_scene=render,
                                seed=5)
    assert manifest["ok"] is True, manifest
    final = Path(manifest["file"])
    assert final.is_file() and final.stat().st_size > 100_000
    assert all(manifest["checks"].values()), manifest["checks"]
    assert manifest["stitch"]["final"]["nb_frames"] == 90
    assert manifest["stitch"]["final"]["width"] == 1080
    assert manifest["audio"]["checks"]["has_audio"] is True
    assert abs(manifest["audio"]["integrated_lufs"] + 16.0) <= 2.0
    assert manifest["captions"]["check"]["ok"] is True
    assert (tmp_path / "out" / "video_ad_manifest.json").is_file()


def test_no_plate_and_no_renderer_is_refused(tmp_path):
    with pytest.raises(video_ad.VideoAdError, match="video_ad_plate_missing"):
        video_ad.produce(PRODUCT, platform="tiktok", seconds=3,
                         out_dir=tmp_path / "out")

def _plate_png() -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (512, 768), (235, 230, 219))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 392, 660], fill=(213, 167, 122))
    d.rectangle([150, 300, 360, 430], fill=(247, 243, 235))
    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_scene_source_changes_the_camera_per_beat():
    plate = _plate_png()
    hook = video_ad.scene_source(plate, {"beat": "hook"})
    proof = video_ad.scene_source(plate, {"beat": "proof"})
    product = video_ad.scene_source(plate, {"beat": "product"})
    assert hook != proof and hook != product and proof != product
    assert video_ad.scene_source(plate, {"beat": "proof"}) == proof


def test_vary_framing_records_a_distinct_source_per_beat(tmp_path):
    def render(scene, frames):
        path = tmp_path / f"clip_{scene['index']}_{frames}.mp4"
        result = subprocess.run([
            vs.FFMPEG, "-y", "-f", "lavfi",
            "-i", "testsrc2=size=480x832:rate=30:duration=10",
            "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr[-300:]
        return path.read_bytes()

    manifest = video_ad.produce(PRODUCT, platform="tiktok", seconds=3,
                                out_dir=tmp_path / "out", plate_png=_plate_png(),
                                render_scene=render, vary_framing=True)
    hashes = {c["source_sha256"] for c in manifest["clips"]}
    assert len(hashes) >= 3, hashes
    assert manifest["vary_framing"] is True
