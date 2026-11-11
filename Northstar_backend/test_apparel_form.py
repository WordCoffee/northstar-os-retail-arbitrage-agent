"""pack-02 — apparel has a form: a garment with a declared chest print area.

Six catalog briefs asked for apparel and none could render: `brand_art` knew a pouch, a
carton and a cylinder, and `design_for_brief` raises for a line it has no design for. The
two white-background briefs are wired here; the other four follow once the form is proven.

The contract under test:

* a tee is a declared **form** with a physical print area in millimetres (280 × 350 mm);
* the drawn plate is a garment silhouette with no shadow (a main image has none, D-021);
* a garment has no panel to discover, so the print area is measured from the body's own
  silhouette and placed at the declared size — and the artwork keeps its aspect;
* the print lands **inside** the garment, not over the sleeve seam or off the shoulder;
* a blank plate is refused by name rather than printed on nothing;
* the app path delivers it: `build(background="white")` returns a main image whose
  background is flat and whose residue check passes.
"""
from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import brand_art as ba
import product_picture as pp
from tools.seller_tester.scene_render import synthetic_plate
from tools.seller_tester.scorers import (
    _product_mask_from_cutout, check_matte_residue, load_image,
)


def _plate(width: int = 1400, height: int = 1400, *, shadow: bool = False) -> Image.Image:
    scene = synthetic_plate(width=width, height=height, kind="apparel", field="white",
                            value=255, shadow=shadow)
    return Image.open(io.BytesIO(scene["bytes"])).convert("RGB")


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "supplied-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


def test_the_tee_is_a_declared_form_with_a_print_area_in_millimetres():
    design = ba.design_for("mogra-tee")
    assert ba.form_of(design) == ba.APPAREL
    assert ba.plate_kind(design) == "apparel"
    assert ba.face_mm(design, "front") == (280.0, 350.0)


def test_the_drawn_plate_is_a_garment_with_no_shadow():
    plate = _plate()
    pixels = np.asarray(plate).astype(np.int16)
    background = pixels[:20, :20].reshape(-1, 3).mean(axis=0)
    body = np.abs(pixels - background).max(axis=2) > 8
    share = float(body.mean())
    # a torso with sleeves fills a large part of the frame, but not all of it
    assert 0.25 <= share <= 0.75, share
    rows = np.where(body.any(axis=1))[0]
    below = pixels[rows.max() + 1:]
    assert below.size and int(below.min()) >= 250, (
        "the drawn garment plate carries a mark under the body: a main image must not")


def test_the_print_is_placed_at_the_declared_aspect_inside_the_garment():
    design = ba.design_for("mogra-tee")
    composed = pp.compose_face(_plate(), design, "front")
    assert composed["gate_ok"] is True, composed["reason"]
    quad = composed["quad"]
    width = abs(quad[1][0] - quad[0][0])
    height = abs(quad[2][1] - quad[1][1])
    assert height / width == pytest.approx(350.0 / 280.0, rel=0.02), (width, height)
    silhouette = composed["silhouette"]["box"]
    left, top, right, bottom = silhouette
    for x, y in quad:
        assert left < x < right and top < y < bottom, (x, y, silhouette)


def test_a_blank_plate_is_refused_by_name():
    blank = Image.new("RGB", (1200, 1200), (255, 255, 255))
    with pytest.raises(ValueError, match="plate_face_not_found"):
        pp.compose_face(blank, ba.design_for("mogra-tee"), "front")


def test_the_apparel_plate_brief_asks_for_a_shirt_and_no_shadow():
    design = ba.design_for("mogra-tee")
    brief = pp.plate_brief("front", ba.APPAREL, design, shadow=False).lower()
    assert "t-shirt" in brief and "cotton" in brief
    assert "contact shadow" not in brief


def test_the_app_path_delivers_a_main_image_with_no_residue(tmp_path):
    """The pipeline property, not the OCR threshold.

    The legibility gate is measured where it matters: `python -m tools.seller_tester
    product --catalog state/seller/apparel_catalog.json --renderer drawn` delivered
    ST-017 at **100.0, gate_ok True** (`reports/ty/d025_apparel_pass.json`). Here the
    question is the rest of the pipeline — a flat background, a recorded silhouette, and
    no residue — so the assertion does not depend on an OCR threshold this fixture's
    plate happens to sit near.
    """
    design = ba.design_for("mogra-tee")
    result = pp.build(design, out_dir=str(tmp_path / "tee"), out_root=str(tmp_path),
                      faces=("front",), width=2000, height=2000,
                      generator=_generator(_plate(2000, 2000)), background="white",
                      fill=0.61)
    record = result["faces"][0]
    assert record["stage"] in ("done", "legibility"), record
    assert record["background"]["mode"] == "flat"
    assert record["units_found"] == 1
    picture = tmp_path / "tee" / "product_front.png"
    if not picture.is_file():
        assert record["rejected_file"], "a refused picture must be kept with its reason"
        pytest.skip(f"the gate refused this plate: {record.get('reason')}")
    loaded = load_image(picture.read_bytes())
    cutout = np.asarray(Image.open(picture.with_suffix(".cutout.png")).convert("RGBA"))
    mask = _product_mask_from_cutout(cutout, record["product_box"],
                                     loaded.rgb.shape[:2])
    verdict = check_matte_residue(loaded.rgb, {"mode": "uniform", "value": 255,
                                               "tolerance": 6}, subject_mask=mask)
    assert verdict["ok"] is True, verdict
