"""U3 — logo placement (REA 1.6 candidate U3).

Baseline this closes: 5 of 60 surveyed turns asked where the logo goes and no
tool served them at all (reports/rea_probe/smui_intents.json).

The contract defended here: the anchor is MEASURED (flattest perimeter cell) or
the operator's explicit choice — never invented — and the result reports the
flatness scores and the ink/backdrop contrast it achieved.
"""

from __future__ import annotations

import io
import os
import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import logo_placement as lp  # noqa: E402


def _plate(path, busy_centre=True):
    """A plate with texture in the middle and a calm top-left corner."""
    img = Image.new("RGB", (600, 800), (232, 226, 214))
    d = ImageDraw.Draw(img)
    if busy_centre:
        for i in range(40):
            x = 150 + (i * 37) % 300
            d.line([(x, 300), (x + 40, 460)], fill=(60, 90, 70), width=6)
    img.save(path)
    return path


def _logo(path, colour=(150, 40, 40, 255)):
    img = Image.new("RGBA", (400, 300), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([60, 40, 340, 260], fill=colour)
    img.save(path)
    return path


def test_auto_anchor_avoids_a_busy_centre(tmp_path):
    plate = _plate(tmp_path / "p.png")
    logo = _logo(tmp_path / "l.png")
    out = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="auto", scale=0.15)
    assert out["placement"]["anchor"] != "center"
    scores = out["quality"]["flatness_scores"]
    chosen = out["placement"]["anchor"]
    # the chosen cell must really be the calmest perimeter cell
    perimeter = {k: v for k, v in scores.items() if k != "center"}
    assert chosen == min(perimeter, key=perimeter.get)
    assert out["quality"]["chosen_flatness"] <= max(perimeter.values())


def test_explicit_anchor_is_honoured_exactly(tmp_path):
    plate = _plate(tmp_path / "p.png")
    logo = _logo(tmp_path / "l.png")
    out = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="bottom-right",
                   scale=0.12, margin=0.05)
    p = out["placement"]
    assert p["anchor"] == "bottom-right"
    assert p["x"] + p["width"] <= out["size"][0]
    assert p["y"] + p["height"] <= out["size"][1]
    # bottom-right corner, within one margin step
    assert p["x"] > out["size"][0] * 0.5 and p["y"] > out["size"][1] * 0.5


def test_the_logo_actually_lands_on_the_pixels(tmp_path):
    plate = _plate(tmp_path / "p.png")
    logo = _logo(tmp_path / "l.png")
    before = np.asarray(Image.open(plate).convert("RGB"), dtype=int)
    out = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="top-left", scale=0.2,
                   opacity=1.0)
    after = np.asarray(Image.open(io.BytesIO(out["bytes"])).convert("RGB"), dtype=int)
    p = out["placement"]
    region = (slice(p["y"], p["y"] + p["height"]), slice(p["x"], p["x"] + p["width"]))
    assert np.abs(after[region] - before[region]).max() > 40


def test_low_contrast_is_reported_not_hidden(tmp_path):
    plate = _plate(tmp_path / "p.png", busy_centre=False)
    logo = _logo(tmp_path / "l.png", colour=(230, 228, 222, 255))   # near the plate tone
    out = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="top-left", scale=0.15)
    assert out["quality"]["contrast_ratio"] < 1.5
    assert out["quality"]["contrast_ok"] is False


def test_bad_arguments_are_refused(tmp_path):
    plate = _plate(tmp_path / "p.png")
    logo = _logo(tmp_path / "l.png")
    with pytest.raises(ValueError):
        lp.place(plate.read_bytes(), logo.read_bytes(), anchor="middle-centre")
    with pytest.raises(ValueError):
        lp.place(plate.read_bytes(), logo.read_bytes(), scale=1.4)
    with pytest.raises(ValueError):
        lp.place(plate.read_bytes(), logo.read_bytes(), opacity=1.5)
    with pytest.raises(ValueError):
        lp.place(plate.read_bytes(), logo.read_bytes(), blend="screen")


def test_multiply_blend_still_writes_the_mark(tmp_path):
    plate = _plate(tmp_path / "p.png")
    logo = _logo(tmp_path / "l.png")
    normal = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="top-left",
                      scale=0.15, blend="normal")
    mult = lp.place(plate.read_bytes(), logo.read_bytes(), anchor="top-left",
                    scale=0.15, blend="multiply")
    assert normal["bytes"] != mult["bytes"]
