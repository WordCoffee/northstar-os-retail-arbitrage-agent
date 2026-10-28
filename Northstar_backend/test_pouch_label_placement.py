"""Regression: the pouch face must be measured on the POUCH, not on the scenery.

T2 visual acceptance failed on 2026-10-28 because `_foreground_mask` compared
every pixel to one outer-ring median colour. A real product plate has more than
one backdrop - here a grey wall above and a bright marble table below - so the
table and the olive sprig were classified as pouch. The silhouette grew to the
whole frame and the label was warped onto a quad that ran off the bottom of the
bag onto the table and out to the right edge: a flat card floating over the
product.

These tests build a two-backdrop scene on purpose. The old code fails them; the
occupancy-based segmentation passes.
"""

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pouch_label as pl


def _two_backdrop_plate(w=760, h=1120):
    """Kraft pouch on a grey wall above / bright marble table below, plus a prop."""
    img = Image.new("RGB", (w, h), (188, 188, 186))          # grey wall
    # bright table, much lighter than the wall - the case that broke the mask
    px = img.load()
    for y in range(int(h * 0.72), h):
        for x in range(w):
            px[x, y] = (247, 246, 244)
    # kraft pouch (warm, saturated) - the thing we must measure
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([int(w * 0.22), int(h * 0.22), int(w * 0.78), int(h * 0.80)],
                        radius=18, fill=(190, 141, 90))
    # an olive sprig touching the pouch's lower right (a prop that used to merge)
    d.ellipse([int(w * 0.72), int(h * 0.70), int(w * 0.99), int(h * 0.86)],
              fill=(120, 140, 90))
    return img


def test_two_backdrop_plate_does_not_measure_the_whole_frame():
    plate = _two_backdrop_plate()
    m = pl.measure_face(plate)
    face = m["face"]
    w, h = plate.size

    # The old mask reported left=0, right=w-1, bottom=h-1 on exactly this scene.
    assert face["left"] > 0, "the table/left edge was counted as pouch"
    assert face["right"] < w - 1, "the right edge (prop/frame) was counted as pouch"
    assert face["bottom"] < h - 1, "the table below the pouch was counted as pouch"
    assert m["coverage"] < 0.55, f"coverage {m['coverage']} means scenery is in the mask"


def test_measured_quad_stays_inside_the_pouch():
    plate = _two_backdrop_plate()
    m = pl.measure_face(plate)
    q = m["quad"]
    face = m["face"]

    for (x, y) in q:
        assert face["left"] - 2 <= x <= face["right"] + 2, f"quad x {x} outside the pouch"
        assert face["top"] - 2 <= y <= face["bottom"] + 2, f"quad y {y} outside the pouch"


def test_quad_skips_the_zipper_weld_and_the_rounded_base():
    """A label must not be warped over the top weld or past the base curve."""
    plate = _two_backdrop_plate()
    m = pl.measure_face(plate)
    face, q = m["face"], m["quad"]
    span = face["bottom"] - face["top"]
    top_y = min(p[1] for p in q)
    bottom_y = max(p[1] for p in q)

    assert top_y >= face["top"] + span * 0.12, "the quad starts on the zipper weld"
    assert bottom_y <= face["bottom"] - span * 0.05, "the quad runs past the pouch base"


def test_low_chroma_pack_falls_back_instead_of_failing():
    """An ivory pack on white seamless has no chroma; the fallback must still work."""
    from PIL import ImageDraw
    img = Image.new("RGB", (600, 800), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([140, 160, 460, 660], radius=14, fill=(244, 238, 228))
    m = pl.measure_face(img)
    assert m["face"]["right"] < 599
    assert m["coverage"] < 0.6
