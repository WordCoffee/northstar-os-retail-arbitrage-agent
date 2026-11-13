"""Stray scene geometry: found, filled when the background permits, kept and reported when not.

D-019 is the case where the model paints a wire, a dashed rule or a ring into the *scene*, which a
free-background brief keeps. The fill is a median-of-ring inpaint: deterministic, no model. It is
right for a flat or softly graded field and honest about a textured one — there it leaves the
component alone and says so, because a smear is worse than a visible wire.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "Northstar_backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "Northstar_backend"))

import scene_cleanup  # noqa: E402


def _scene(*, stray: bool, textured: bool = False) -> tuple[bytes, tuple]:
    image = Image.new("RGB", (400, 400), (250, 248, 244))
    draw = ImageDraw.Draw(image)
    if textured:
        rng = np.random.default_rng(3)
        noise = rng.integers(0, 90, (400, 400, 3), dtype=np.uint8)
        base = np.asarray(image).astype(np.uint8)
        image = Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8), "RGB")
        draw = ImageDraw.Draw(image)
    # the product, centred
    draw.rectangle([150, 140, 250, 300], fill=(40, 90, 70))
    if stray:
        draw.line([(300, 40), (360, 40)], fill=(20, 20, 20), width=4)      # a rule line
        draw.line([(60, 60), (60, 130)], fill=(20, 20, 20), width=3)       # a wire
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue(), (150, 140, 250, 300)


def test_no_stray_geometry_is_a_no_op():
    png, box = _scene(stray=False)
    out, report = scene_cleanup.fill_stray(png, box)
    assert report["found_pixels"] == 0
    assert out == png


def test_stray_marks_are_filled_on_a_flat_field():
    png, box = _scene(stray=True)
    out, report = scene_cleanup.fill_stray(png, box)
    assert report["found_pixels"] > 0
    assert report["filled"] > 0
    assert report["kept"] == 0
    assert report["filled_components"] == 2

    before = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    after = np.asarray(Image.open(io.BytesIO(out)).convert("RGB"))
    # the rule line's pixels changed; the product did not
    assert not np.array_equal(before[38:43, 298:362], after[38:43, 298:362])
    assert np.array_equal(before[200:240, 180:220], after[200:240, 180:220])


def test_a_textured_background_is_reported_not_smeared():
    png, box = _scene(stray=True, textured=True)
    out, report = scene_cleanup.fill_stray(png, box)
    assert report["found_pixels"] > 0
    assert report["filled"] == 0
    assert report["kept"] > 0
    assert report["skipped"], "a textured ring must be explained, not silently filled"
    assert out == png


def test_a_scene_that_is_mostly_stray_is_not_repainted():
    image = Image.new("RGB", (200, 200), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    draw.rectangle([80, 80, 120, 120], fill=(10, 10, 10))
    draw.rectangle([0, 0, 199, 30], fill=(10, 10, 10))    # 15% of the frame
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    out, report = scene_cleanup.fill_stray(buffer.getvalue(), (80, 80, 120, 120))
    assert report["fraction"] > 0.03
    assert report["filled"] == 0
    assert report["skipped"]
    assert out == buffer.getvalue()
