"""S4 — local pre-upload validator.

Two things are defended here:
  1. the rules are the platforms' own documented rules (sources in
     reports/social_media_asset_specs_20261028.md), and
  2. this table cannot silently drift from the UI's table in presets.js — the
     parity test parses the JavaScript.
"""

from __future__ import annotations

import io
import re
import sys
from pathlib import Path

import pytest
from PIL import Image

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import social_validate as sv  # noqa: E402

REPO = _HERE.parent
PRESETS = REPO / "northstar-os-ui" / "src" / "studio" / "engine" / "presets.js"


def _png(size, mode="RGB", colour=(230, 225, 215)):
    buf = io.BytesIO()
    Image.new(mode, size, colour).save(buf, format="PNG")
    return buf.getvalue()


def test_a_correct_pinterest_pin_passes():
    report = sv.validate(_png((1000, 1500)), "pin", caption="Organic lion's mane")
    assert report["ok"] is True
    assert report["confidence"] == "VERIFIED"
    assert {c["id"] for c in report["checks"]} >= {"bytes", "format", "aspect_ratio", "colour"}


def test_wrong_ratio_blocks_at_one_percent():
    # a 1:1 file for a 4:5 canvas is 20% off, so it must block
    report = sv.validate(_png((1080, 1080)), "ig-post")
    assert report["ok"] is False
    assert "aspect_ratio" in report["blocked"]


def test_ratio_within_tolerance_passes():
    # 1432x1800 is within 1% of 4:5
    report = sv.validate(_png((1432, 1800)), "ig-post")
    ratio_check = next(c for c in report["checks"] if c["id"] == "aspect_ratio")
    assert ratio_check["status"] == "pass"


def test_an_undersized_youtube_thumb_blocks():
    report = sv.validate(_png((320, 180)), "yt-thumb")
    assert report["ok"] is False
    assert "min_dimension" in report["blocked"]


def test_caption_over_the_documented_cap_blocks():
    short = sv.validate(_png((1200, 628)), "x-post", caption="x" * 280)
    long = sv.validate(_png((1200, 628)), "x-post", caption="x" * 281)
    assert short["ok"] is True
    assert long["ok"] is False and "caption_length" in long["blocked"]


def test_cmyk_is_flagged_not_silently_accepted():
    buf = io.BytesIO()
    Image.new("CMYK", (1200, 628), (0, 10, 20, 0)).save(buf, format="JPEG")
    report = sv.validate(buf.getvalue(), "x-post")
    colour = next(c for c in report["checks"] if c["id"] == "colour")
    assert colour["status"] == "warn"
    assert report["ok"] is True          # a warning is not a block


def test_a_file_over_the_cap_blocks():
    spec = sv.SPECS["x-post"]
    fake = b"x" * (spec["max_bytes"] + 1)
    report = sv.validate(fake, "x-post")
    assert report["ok"] is False
    assert "bytes" in report["blocked"]


def test_unknown_canvas_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        sv.validate(_png((10, 10)), "myspace")


def test_unverified_rules_are_declared():
    report = sv.validate(_png((1000, 1500)), "pin")
    assert any("TikTok" in rule for rule in report["unverified_rules"])


def test_parity_with_the_ui_table():
    """Every canvas in Python must exist in presets.js with the same w/h."""
    js = PRESETS.read_text(encoding="utf-8", errors="replace")
    ui = {}
    for line in js.splitlines():
        m = re.search(r"id:\s*'([\w-]+)'", line)
        w = re.search(r"\bw:\s*(\d+)", line)
        h = re.search(r"\bh:\s*(\d+)", line)
        if m and w and h:
            ui[m.group(1)] = (int(w.group(1)), int(h.group(1)))

    for canvas, spec in sv.SPECS.items():
        if canvas in ("pin-video", "x-vertical"):
            continue                      # video canvases: the UI uses a frame size
        assert canvas in ui, f"{canvas} missing from presets.js"
        assert ui[canvas] == (spec["w"], spec["h"]), (
            f"{canvas}: python {spec['w']}x{spec['h']} vs UI {ui[canvas]}")
