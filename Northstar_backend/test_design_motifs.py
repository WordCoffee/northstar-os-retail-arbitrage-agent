"""D-027 — a design names its own motif, and a pack never borrows a loaner.

Found by pack-03: `brand_art._spec` set `motif="bean"` for any design that did not declare
one, so a drill carton and a kettle carton both carried three coffee beans — the only
illustration on the pack. The rule these checks hold:

* `_spec` invents no motif; a design that names none prints none;
* every design that prints on a carton names a motif the renderer can actually draw;
* an unknown name draws nothing and says so (`draw_motif` returns False), which is how a
  typo becomes a blank panel rather than someone else's picture;
* on the panel itself, "no motif" leaves the band empty and a named motif fills it.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import brand_art as ba
import package_art as pa


def _front(design_id: str) -> Image.Image:
    design = ba.design_for(design_id)
    return pa.render_front_box(ba._spec(design), width_mm=170.0, height_mm=240.0)


def _motif_band_ink(image: Image.Image) -> int:
    """Coloured (non-paper, non-ink) pixels in the band where the motif is drawn."""
    rgb = np.asarray(image.convert("RGB")).astype(int)
    height = rgb.shape[0]
    band = rgb[int(height * 0.55):int(height * 0.68)]
    spread = band.max(axis=2) - band.min(axis=2)
    return int((spread > 25).sum())


def test_the_spec_invents_no_motif():
    spec = ba._spec({"id": "x", "brand": "X"})
    assert "motif" not in spec


@pytest.mark.parametrize("design_id", ["t2-drill-box", "t2-kettle-box",
                                       "word-coffee", "harbor-body-oil", "mogra-tee"])
def test_every_carton_design_names_a_drawable_motif(design_id):
    design = ba.design_for(design_id)
    motif = design.get("motif")
    assert motif, f"{design_id} names no motif; a carton would print a blank hero area"
    assert motif in pa.MOTIFS, (design_id, motif, pa.MOTIFS)


def test_the_two_box_art_designs_do_not_share_one_illustration():
    drill = ba.design_for("t2-drill-box").get("motif")
    kettle = ba.design_for("t2-kettle-box").get("motif")
    assert drill != kettle


def test_an_unknown_motif_draws_nothing_and_says_so():
    canvas = Image.new("RGB", (400, 400), (255, 255, 255))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(canvas)
    existing = np.asarray(canvas).sum()
    assert pa.draw_motif(draw, "not-a-motif", 50, 50, 20, 20, (200, 0, 0)) is False
    assert np.asarray(canvas).sum() == existing


def test_the_motif_band_is_empty_without_a_motif_and_filled_with_one():
    bare = _front("t2-drill-box")
    design = dict(ba.design_for("t2-drill-box"))
    design.pop("motif", None)
    blank = pa.render_front_box(ba._spec(design), width_mm=170.0, height_mm=240.0)
    a = np.asarray(blank.convert("RGB")).astype(int)
    b = np.asarray(bare.convert("RGB")).astype(int)
    assert a.shape == b.shape
    differing = np.abs(a - b).max(axis=2) > 8
    assert int(differing.sum()) > 200, (
        "naming a motif changed nothing on the panel")
    rows = np.nonzero(differing)[0]
    height = a.shape[0]
    # the hero area sits at H*0.615 in package_art.render_front_box; the change must be
    # there and nowhere else, which is what "the design's own illustration" means
    assert rows.min() >= height * 0.50, (rows.min() / height)
    assert rows.max() <= height * 0.75, (rows.max() / height)
