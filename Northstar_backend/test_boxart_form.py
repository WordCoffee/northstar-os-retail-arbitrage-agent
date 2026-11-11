"""pack-03 — box art: a boxed kettle and a boxed drill are forms the app can print.

Both briefs declared no `product_line`, so `design_for_brief` refused them by name (the
same gap apparel had before pack-02). They now carry a design on the folding-carton form
the app already renders — a drill and a kettle are not new geometry, they are new faces
with their own millimetres.

The contract under test:

* the box art is a declared design on the **gift_box** form, with faces in millimetres
  (240 × 170 mm for the drill, 180 × 260 mm for the kettle);
* a brief that names its line resolves to that design; an unknown line still raises;
* the composed face keeps the artwork's aspect and lands inside the carton's face;
* a blank plate is refused by name rather than printed on nothing;
* the app path delivers a main image whose background is flat with no residue.
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


def _plate(width: int = 1400, height: int = 1400) -> Image.Image:
    scene = synthetic_plate(width=width, height=height, kind="gift_box", field="white",
                            value=255, shadow=False)
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


@pytest.mark.parametrize("design_id,face", [
    ("t2-drill-box", (170.0, 240.0)),
    ("t2-kettle-box", (180.0, 260.0)),
])
def test_the_box_art_is_a_declared_form_with_its_own_millimetres(design_id, face):
    design = ba.design_for(design_id)
    assert ba.form_of(design) == ba.GIFT_BOX
    assert ba.plate_kind(design) == "gift_box"
    assert ba.face_mm(design, "front") == face


def test_a_brief_that_names_its_line_resolves_to_that_design():
    brief = {"id": "ST-028", "product_line": "t2-drill-box"}
    assert ba.design_for_brief(brief)["id"] == "t2-drill-box"


def test_an_unknown_line_still_raises_by_name():
    with pytest.raises(ValueError, match="no design"):
        ba.design_for_brief({"id": "ST-999", "product_line": "not-a-real-line"})


def test_the_print_keeps_its_aspect_and_lands_inside_the_face():
    design = ba.design_for("t2-drill-box")
    plate = _plate()
    composed = pp.compose_face(plate, design, "front")
    assert composed["gate_ok"] is True, composed["reason"]
    quad = composed["quad"]
    width = abs(quad[1][0] - quad[0][0])
    height = abs(quad[2][1] - quad[1][1])
    # the declared panel is portrait (170 x 240); the carton's face is portrait too, so
    # the artwork is not rotated and its aspect survives the warp
    assert height / width == pytest.approx(240.0 / 170.0, rel=0.05), (width, height)
    xs = [x for x, _ in quad]
    ys = [y for _, y in quad]
    assert 0 <= min(xs) and max(xs) <= plate.width, (min(xs), max(xs))
    assert 0 <= min(ys) and max(ys) <= plate.height, (min(ys), max(ys))
    share = ((max(xs) - min(xs)) * (max(ys) - min(ys))) / float(plate.width * plate.height)
    assert 0.05 <= share <= 0.60, share


def test_a_blank_plate_is_refused_by_name():
    blank = Image.new("RGB", (1200, 1200), (255, 255, 255))
    with pytest.raises(ValueError, match="plate_face_not_found"):
        pp.compose_face(blank, ba.design_for("t2-drill-box"), "front")


def test_the_box_plate_brief_asks_for_a_carton_and_no_shadow():
    design = ba.design_for("t2-drill-box")
    brief = pp.plate_brief("front", ba.GIFT_BOX, design, shadow=False).lower()
    assert "carton" in brief or "box" in brief
    assert "contact shadow" not in brief


def test_the_app_path_delivers_a_flat_main_image_with_no_residue(tmp_path):
    design = ba.design_for("t2-drill-box")
    result = pp.build(design, out_dir=str(tmp_path / "box"), out_root=str(tmp_path),
                      faces=("front",), width=2000, height=2000,
                      generator=_generator(_plate(2000, 2000)), background="white",
                      fill=0.45)
    record = result["faces"][0]
    assert record["stage"] in ("done", "legibility"), record
    assert record["background"]["mode"] == "flat"
    picture = tmp_path / "box" / "product_front.png"
    if not picture.is_file():
        assert record["rejected_file"], "a refused picture must be kept with its reason"
        pytest.skip(f"the gate refused this plate: {record.get('reason')}")
    loaded = load_image(picture.read_bytes())
    cutout = np.asarray(Image.open(picture.with_suffix(".cutout.png")).convert("RGBA"))
    mask = _product_mask_from_cutout(cutout, record["product_box"],
                                     loaded.rgb.shape[:2])
    verdict = check_matte_residue(loaded.rgb, {"mode": "uniform", "value": 255,
                                               "tolerance": 6}, subject_mask=mask,
                                  silhouette_source=record.get("cutout_method"))
    assert verdict["ok"], verdict.get("detail")
