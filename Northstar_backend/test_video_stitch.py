"""Stitch contracts: the planner, the encoder and the ffprobe checks.

The sampler is injected: these tests exercise the part that decides whether a
file is a deliverable (canvas, duration, codec, size), which is where a "video"
usually stops being one.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

import video_formats as vf
import video_stitch as vs


def _lavfi_clip(path: Path, frames: int, *, size="480x832", rate=16) -> Path:
    result = subprocess.run([
        vs.FFMPEG, "-y", "-f", "lavfi",
        "-i", f"testsrc2=size={size}:rate={rate}:duration=10",
        "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
        "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-500:]
    return path


def test_the_planner_exposes_the_exact_deliverable_length():
    p = vf.plan("tiktok", 15)
    assert p["target_frames"] == 450
    assert p["total_frames"] >= p["target_frames"]


def test_stitching_needs_clips(tmp_path):
    with pytest.raises(vs.StitchError, match="no_clips"):
        vs.stitch_clips([], tmp_path / "x.mp4", platform="tiktok", seconds=3)


def test_render_and_stitch_uses_the_plan_and_checks_the_file(tmp_path):
    calls = []

    def render(index, frames):
        calls.append((index, frames))
        path = tmp_path / f"src_{index}.mp4"
        _lavfi_clip(path, frames)
        return path.read_bytes()

    out = tmp_path / "short.mp4"
    result = vs.render_and_stitch(render, out, platform="tiktok", seconds=3)
    assert [c[0] for c in calls] == [0, 1]          # 90 frames = 2 x 45
    assert {c[1] for c in calls} == {45}
    final = result["final"]
    assert final["nb_frames"] == 90
    assert (final["width"], final["height"]) == (1080, 1920)
    assert final["codec"] == "h264"
    assert final["duration"] == pytest.approx(3.0, abs=1 / 30 + 1e-3)
    assert all(result["checks"].values())
    assert out.is_file()


def test_a_wrong_canvas_is_refused_with_the_measured_value(tmp_path, monkeypatch):
    clip = _lavfi_clip(tmp_path / "one.mp4", 45)
    real_probe = vs.probe
    calls = {"n": 0}

    def wrong_probe(path):
        rec = real_probe(path)
        calls["n"] += 1
        if calls["n"] == 2:          # the final file, not the normalised clip
            rec = {**rec, "width": 720}
        return rec

    monkeypatch.setattr(vs, "probe", wrong_probe)
    with pytest.raises(vs.StitchError, match="canvas_exact"):
        vs.stitch_clips([clip], tmp_path / "bad.mp4", platform="tiktok", seconds=3)
