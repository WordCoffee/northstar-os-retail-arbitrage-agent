"""image_prep tests — MAIN framing + compliance measurement, fully offline.

Synthetic cutouts only: no model, no network, no ComfyUI.
"""

from __future__ import annotations

import io
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import image_prep as ip  # noqa: E402


def _cutout(w=400, h=400, box=(150, 100, 250, 300), color=(30, 60, 45)) -> Image.Image:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=color + (255,))
    return img


def _png(img: Image.Image, mode=None) -> bytes:
    buf = io.BytesIO()
    (img.convert(mode) if mode else img).save(buf, format="PNG")
    return buf.getvalue()


def test_alpha_bbox_and_trim():
    img = _cutout()
    assert ip.alpha_bbox(img) == (150, 100, 251, 301)
    trimmed = ip.trim_to_alpha(img)
    assert trimmed.size == (101, 201)
    empty = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    assert ip.alpha_bbox(empty) is None
    assert ip.trim_to_alpha(empty).size == (10, 10)


def test_frame_on_white_centres_and_fills():
    img = _cutout(box=(150, 100, 250, 300))     # 100x200 product in a 400x400 canvas
    framed = ip.frame_on_white(img, fill=0.85, size=1000)
    assert framed.size == (1000, 1000)
    arr = np.asarray(framed)
    # background is pure white; the product is opaque and centred
    assert (arr[0, 0] == [255, 255, 255, 255]).all()
    # measure the product from the alpha ORIGINAL scaled: use the compliance
    # measurement, which reads the non-white area of the opaque frame
    rep = ip.check_main_compliance(_png(framed.convert("RGB")), min_side=500)
    assert abs(rep["fill_longest_side"] - 0.85) < 0.02, rep
    box = rep["product_bbox"]
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    assert abs(cx - 500) <= 2 and abs(cy - 500) <= 2


def test_frame_on_white_does_not_square_a_wide_product_when_asked():
    wide = _cutout(w=600, h=200, box=(50, 50, 550, 150))
    framed = ip.frame_on_white(wide, fill=0.8, size=1000, square=False)
    assert framed.width == 1000
    assert framed.height < framed.width


def test_frame_on_white_bytes_reports_upscale_honestly():
    small = _cutout(w=120, h=120, box=(40, 40, 80, 100))
    out = ip.frame_on_white_bytes(_png(small), fill=0.85, size=1000)
    assert out["upscaled"] is True and out["scale_applied"] > 1.0
    # a product that already fills most of a large canvas is not upscaled
    big = ip.frame_on_white_bytes(_png(_cutout(2000, 2000, box=(100, 100, 1900, 1900))),
                                  fill=0.85, size=1000)
    assert big["upscaled"] is False


def test_check_main_compliance_passes_a_framed_cutout():
    framed = ip.frame_on_white(_cutout(), fill=0.88, size=2000)
    rep = ip.check_main_compliance(_png(framed.convert("RGB")))
    assert rep["verdict"] == "compliant", rep["blockers"]
    assert rep["background_white_frac"] == 1.0
    assert rep["fill_longest_side"] > 0.85


def test_check_main_compliance_names_every_blocker():
    # off-white background, no alpha, product too small, wrong size
    img = Image.new("RGB", (600, 600), (240, 238, 230))
    ImageDraw.Draw(img).rectangle([280, 280, 340, 340], fill=(20, 20, 20))
    rep = ip.check_main_compliance(_png(img), min_fill=0.85, min_side=2000,
                                   require_square=True)
    assert rep["verdict"] == "blocked"
    joined = " ".join(rep["blockers"])
    assert "not pure white" in joined
    assert "2000px" in joined
    assert rep["fill_measurable"] is False, \
        "without alpha the product cannot be separated from a non-white background"
    assert rep["fill_longest_side"] is None

    # with alpha, the fill blocker becomes a real measurement
    tiny = _cutout(600, 600, box=(280, 280, 340, 340))
    rep2 = ip.check_main_compliance(_png(tiny), min_fill=0.85, min_side=100)
    assert rep2["fill_measurable"] is True
    assert "fills" in " ".join(rep2["blockers"])


def test_check_main_compliance_reports_fill_both_ways():
    framed = ip.frame_on_white(_cutout(box=(150, 100, 250, 300)), fill=0.85, size=1000)
    rep = ip.check_main_compliance(_png(framed.convert("RGB")), min_side=500)
    assert rep["fill_area"] < rep["fill_longest_side"], \
        "a tall product fills far more of its longest side than of the frame area"


def test_check_main_compliance_handles_a_flat_white_image():
    rep = ip.check_main_compliance(_png(Image.new("RGB", (100, 100), (255, 255, 255))))
    assert rep["verdict"] == "blocked"
    assert any("no product detected" in b for b in rep["blockers"]), rep["blockers"]
