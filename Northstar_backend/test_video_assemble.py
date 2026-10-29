"""V1 — the video assembly lane (REA 1.3 candidate V1).

Proves the service assembles a real clip with real ffprobe metadata, without a
provider, a model or a network call. Skipped when ffmpeg is not installed.
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest
from PIL import Image, ImageDraw

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import studio_video_assemble as sva  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _still(path, colour):
    img = Image.new("RGB", (360, 520), colour)
    d = ImageDraw.Draw(img)
    d.rectangle([40, 60, 320, 460], outline=(20, 20, 20), width=6)
    img.save(path)
    return path


def test_assembles_a_vertical_clip_with_captions(tmp_path):
    a = _still(tmp_path / "a.png", (232, 226, 214))
    b = _still(tmp_path / "b.png", (40, 74, 52))
    out = tmp_path / "ad.mp4"

    meta = sva.assemble([a, b], captions=["first line", "second line"],
                        out_path=out, seconds_per_shot=1.2, size=(360, 640))

    assert meta["ok"] is True
    assert out.is_file() and out.stat().st_size > 10_000
    probe = meta["probe"]
    video = next(s for s in probe["streams"] if s["type"] == "video")
    assert (video["width"], video["height"]) == (360, 640)
    assert video["codec"] == "h264"
    assert abs(probe["duration_s"] - 2.4) < 0.35
    assert meta["captions"] == 2
    assert meta["audio_present"] is False          # no narration asked for


def test_refuses_a_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError):
        sva.assemble([tmp_path / "nope.png"], out_path=tmp_path / "x.mp4")


def test_probe_reports_the_file_it_was_given(tmp_path):
    a = _still(tmp_path / "a.png", (200, 200, 200))
    out = tmp_path / "one.mp4"
    sva.assemble([a], out_path=out, seconds_per_shot=1.0, size=(320, 568))
    p = sva.probe(out)
    assert p["duration_s"] > 0.5
    assert p["streams"][0]["type"] == "video"
