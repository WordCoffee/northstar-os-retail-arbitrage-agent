"""The third packaging form: a rigid cylinder (jar, bottle, tube, canister).

Contract under test (unit `pack-01`):

* a cylinder is a *form*, not a category: the design declares it, the plate
  brief and the print insets come from it, and the wrap-around label is warped
  round the body instead of homographed onto a flat quad;
* the label is measured as a band and never painted outside the body: a plate
  with no cylinder in it is refused;
* a drawn plate draws the shape the *design's* form asks for, not the one the
  brief's category suggests — a gift box design on a `food_jar` brief is still a
  box;
* the cylinder front label is laid out for a short face: the wordmark used to
  land on the frame rule and OCR read "WORD COFFEE" as "WORDCOEEEE";
* the shipping pouch stays byte-identical, and a carton is still a carton.
"""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from PIL import Image, ImageDraw

import brand_art as ba
import mockup_compositor as mc
import mockup_quality as mq
import mogra_label_art as mg
import product_picture as pp
from tools.seller_tester.scene_render import renderer_from_name, synthetic_plate

CYLINDER_DESIGNS = ("word-coffee-canister", "word-coffee-mug",
                    "harbor-body-oil", "pine-paws-joint")


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _plate(kind: str, *, width: int = 1536, height: int = 1536,
           units: int = 1, stock=(214, 199, 178)) -> Image.Image:
    return Image.open(io.BytesIO(synthetic_plate(
        width=width, height=height, kind=kind, field="white", units=units,
        stock=stock)["bytes"]))


def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "drawn-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


# ── the form is a declaration, and it names its own plate and insets ────────

def test_the_cylinder_is_a_declared_form():
    assert ba.CYLINDER in ba.FORM_NAMES
    assert "cylinder" in ba.FORM_NAMES[ba.CYLINDER]
    assert ba.PLATE_KINDS[ba.CYLINDER] == "cylinder"
    for design_id in CYLINDER_DESIGNS:
        design = ba.design_for(design_id)
        assert ba.form_of(design) == ba.CYLINDER
        assert ba.plate_kind(design) == "cylinder"
        assert design_id in ba.known()


def test_a_cylinder_plate_brief_is_not_a_pouch_and_not_a_carton():
    cylinder = pp.FORM_PLATE_BRIEFS[ba.CYLINDER]["front"]
    assert "cylindrical" in cylinder
    assert "pouch" not in cylinder and "gift box" not in cylinder
    assert pp.FORM_PLATE_BRIEFS[ba.CYLINDER] is not pp.FORM_PLATE_BRIEFS[ba.GIFT_BOX]
    assert pp.plate_brief("front", ba.CYLINDER) == cylinder


def test_a_design_names_its_own_body_in_the_plate_brief():
    """A mug with a handle and a canister with a lid are not the same object."""
    mug = ba.design_for("word-coffee-mug")
    assert "mug with a handle" in pp.plate_brief("front", ba.CYLINDER, mug)
    tub = ba.design_for("pine-paws-joint")
    assert "supplement tub" in pp.plate_brief("back", ba.CYLINDER, tub)
    assert "turned around" in pp.plate_brief("back", ba.CYLINDER, tub)
    # a form with no per-design subject keeps its own brief
    box = ba.design_for("word-coffee")
    assert pp.plate_brief("front", ba.GIFT_BOX, box) == pp.FORM_PLATE_BRIEFS[ba.GIFT_BOX]["front"]


# ── D-016: the measured body must be the body, on a low-contrast plate ──────

def _low_contrast_cylinder(size=(1000, 1200), body=(250, 750), top=150,
                           bottom=1050,*, noise_sigma=0.0, seed=7):
    """A pale body on a paler sweep whose silhouette edges fade near the base.

    The truth is exact: the body spans x 250..750, y 150..1050. Each column is a
    body pixel for only the top `f(x)` share of the body height, and f falls from
    1.0 in the middle of the body to 0.30 at the silhouette edge — the rounded-edge
    shading that makes a fixed mask cut lose the edge.
    """
    import numpy as np

    w, h = size
    bg = np.array([212, 212, 209], dtype=np.float32)
    img = np.tile(bg, (h, w, 1))
    x0, x1 = body
    half = (x1 - x0) / 2.0
    centre = (x0 + x1) / 2.0
    body_h = bottom - top
    xs = np.arange(x0, x1)
    t = np.abs(xs - centre) / half
    f = np.ones_like(t)
    outer = t > 0.55
    f[outer] = 1.0 - (0.70 * (t[outer] - 0.55) / 0.45)
    tint = np.array([238, 238, 235], dtype=np.float32)
    for i, x in enumerate(xs):
        img[top:int(round(top + f[i] * body_h)), x] = tint
    # a soft contact shadow under the base, as a real plate has
    yy, xx = np.mgrid[0:h, 0:w]
    shadow = np.exp(-(((xx - w / 2) / 260.0) ** 2 + ((yy - (bottom + 40)) / 26.0) ** 2))
    img = img * (1 - 0.16 * shadow[..., None])
    if noise_sigma:
        rng = np.random.default_rng(seed)
        img = img + rng.normal(0, noise_sigma, img.shape)
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def test_a_low_contrast_body_is_measured_to_its_silhouette():
    """D-016: a fixed mask cut dropped the pale edge and the label came out small."""
    band = mc.find_cylinder_bands(_low_contrast_cylinder(), count=1)[0]
    width = band[2] - band[0]
    assert 0.97 * 500 <= width <= 1.03 * 500, band
    assert abs(band[1] - 150) <= 12 and abs(band[3] - 1050) <= 12, band


def test_the_measurement_holds_with_plate_grain():
    band = mc.find_cylinder_bands(
        _low_contrast_cylinder(noise_sigma=2.5), count=1)[0]
    width = band[2] - band[0]
    assert 0.97 * 500 <= width <= 1.03 * 500, band


def test_a_tall_side_shadow_is_not_measured_as_body():
    """A shadow column is a thin slice of the height; a body column is most of it."""
    img = _low_contrast_cylinder()
    import numpy as np
    a = np.asarray(img).astype(np.float32)
    # a soft shadow immediately right of the body, masked for 30 % of its height
    sh_top = 150 + int(0.70 * 900)
    a[sh_top:1050, 750:840] = np.array([186, 186, 184], dtype=np.float32)
    ramp = np.linspace(1.0, 0.0, 90, dtype=np.float32)[None, :, None]
    bg = np.array([212, 212, 209], dtype=np.float32)[None, None, :]
    a[sh_top:1050, 750:840] = (bg + (a[sh_top:1050, 750:840] - bg) * ramp)
    shadowed = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")
    band = mc.find_cylinder_bands(shadowed, count=1)[0]
    assert band[2] - band[0] <= 1.01 * 500, band
    # known limit, stated in reports/ty/d016_label_scale_plate.md: when a caller
    # asks for two units, a shadow 30 % of the body height can be counted as one.



def test_the_cylinder_insets_leave_the_shoulder_and_the_base_unprinted():
    pouch = pp.FORM_INSETS[ba.POUCH]
    cylinder = pp.FORM_INSETS[ba.CYLINDER]
    assert cylinder["inset_top"] > cylinder["inset_bottom"], cylinder
    # the label wraps, so its side inset is the smallest of the three forms
    assert cylinder["inset_x"] <= pouch["inset_x"]
    assert cylinder["inset_x"] <= pp.FORM_INSETS[ba.GIFT_BOX]["inset_x"]


def test_a_cylinder_declares_its_visible_half_in_millimetres():
    design = ba.design_for("harbor-body-oil")
    width_mm, height_mm = ba.face_mm(design, "front")
    assert (width_mm, height_mm) == (63.0, 50.0)
    panel = ba.front_panel(design)
    assert abs(panel.size[0] / panel.size[1] - width_mm / height_mm) < 0.01


def test_a_cylinder_with_no_declared_label_is_refused_by_name():
    design = ba.design_for("harbor-body-oil")
    design.pop("face_mm")
    with pytest.raises(ValueError) as err:
        ba.face_mm(design, "front")
    assert "harbor-body-oil" in str(err.value)
    assert "face_mm" in str(err.value)


# ── the label artwork: a short face, readable, and never Mogra's ────────────

@pytest.mark.parametrize("design_id", CYLINDER_DESIGNS)
def test_every_cylinder_label_is_legible_on_both_faces(design_id):
    design = ba.design_for(design_id)
    for face, panel_fn in (("front", ba.front_panel), ("back", ba.back_panel)):
        gate = mq.assert_legible(panel_fn(design), wordmark=design["brand"],
                                 net_weight=design["net_weight"])
        assert gate["ok"] is True, (design_id, face, gate["reason"])


def test_the_wordmark_is_not_printed_on_the_frame_rule():
    """Regression: on a 141 x 70 mm label the wordmark sat on the frame rule and
    OCR read "PINE PAWS" as garbage; the label has its own vertical rhythm."""
    design = ba.design_for("pine-paws-joint")
    gate = mq.assert_legible(ba.front_panel(design), wordmark=design["brand"],
                             net_weight=design["net_weight"])
    assert gate["ok"] is True, gate
    words = " ".join(gate["words"]).upper()
    assert "PINE" in words and "PAWS" in words


def test_a_cylinder_label_carries_its_own_copy_not_the_pouch_copy():
    design = ba.design_for("pine-paws-joint")
    words = " ".join(mq.assert_legible(ba.back_panel(design))["words"]).upper()
    assert "PINE" in words
    assert "MOGRA" not in words and "SUPPLEMENT FACTS" not in words
    # the drawn UPC is part of the legal panel; OCR reads 11 of its 12 digits
    assert "0000000007" in words.replace(" ", "")


def test_the_back_label_sections_come_from_the_design():
    design = ba.design_for("harbor-body-oil")
    design["label_sections"] = [{"head": "TEST HEADING", "body": "A test body line."}]
    gate = mq.assert_legible(ba.back_panel(design))
    words = " ".join(gate["words"]).upper().replace(" ", "")
    assert "TESTHEADING" in words, gate["words"]


# ── the compositor: an RGB panel wraps, and the band is measured or refused ──

def test_warp_cylinder_accepts_the_rgb_panel_the_app_produces():
    """Regression: the function indexed an alpha channel, so an RGB design panel
    raised 'operands could not be broadcast' instead of printing a label."""
    plate = _plate("cylinder")
    panel = ba.front_panel(ba.design_for("harbor-body-oil"))
    assert panel.mode == "RGB"
    out = mc.warp_cylinder(plate, panel, (600, 500, 950, 1100), shading=0.4)
    assert out.size == plate.size
    before = plate.crop((600, 500, 950, 1100))
    after = out.crop((600, 500, 950, 1100))
    assert hashlib.sha256(before.tobytes()).hexdigest() != hashlib.sha256(
        after.tobytes()).hexdigest()


def test_a_label_band_with_no_area_is_refused():
    plate = _plate("cylinder")
    with pytest.raises(ValueError) as err:
        mc.warp_cylinder(plate, ba.front_panel(ba.design_for("harbor-body-oil")),
                         (100, 100, 102, 400))
    assert "no area" in str(err.value)


def test_find_label_band_measures_a_drawn_cylinder():
    plate = _plate("cylinder")
    measured = mc.find_label_band(plate, **pp.FORM_INSETS[ba.CYLINDER])
    band = measured["band"]
    assert band[2] - band[0] > plate.width * 0.2
    assert band[3] - band[1] > plate.height * 0.3
    assert len(measured["quad"]) == 4


def test_find_label_band_refuses_a_plate_with_no_cylinder():
    flat = Image.new("RGB", (1024, 1536), (236, 233, 227))
    with pytest.raises(ValueError) as err:
        mc.find_label_band(flat, **pp.FORM_INSETS[ba.CYLINDER])
    assert "plate_face_not_found" in str(err.value)


# ── the shipping path ──────────────────────────────────────────────────────

def test_a_cylinder_plate_yields_a_gated_labelled_picture(tmp_path):
    design = ba.design_for("harbor-body-oil")
    result = pp.build(design, out_dir=str(tmp_path / "oil"), out_root=str(tmp_path),
                      faces=("front", "back"), generator=_generator(_plate("cylinder")))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    assert result["product"]["form"] == ba.CYLINDER
    # the plate brief names the design's own body, not a generic cylinder
    assert "amber glass bottle" in result["faces"][0]["brief"]
    for record in result["faces"]:
        assert record["units_found"] == 1
        assert record["quad"] and record["quads"]
    manifest = json.loads((tmp_path / "oil" / "product_picture_manifest.json").read_text())
    assert manifest["product"]["form"] == ba.CYLINDER
    assert manifest["checks"]["legible"] is True
    words = " ".join(result["faces"][0]["legibility"]["words"]).upper()
    assert "HARBOR" in words and "MOGRA" not in words


def test_a_plate_with_no_cylinder_is_refused(tmp_path):
    design = ba.design_for("harbor-body-oil")
    flat = Image.new("RGB", (1024, 1536), (236, 233, 227))
    result = pp.build(design, out_dir=str(tmp_path / "oil"), out_root=str(tmp_path),
                      faces=("front",), generator=_generator(flat))
    assert result["ok"] is False
    assert "plate_face_not_found" in result["faces"][0]["reason"]
    assert not (tmp_path / "oil" / "product_front.png").exists()


def test_three_cylinders_are_three_labelled_units(tmp_path):
    design = ba.design_for("pine-paws-joint")
    result = pp.build(design, out_dir=str(tmp_path / "tub"), out_root=str(tmp_path),
                      faces=("front",), units=3, width=3000, height=3000,
                      generator=_generator(_plate("cylinder", width=3000,
                                                 height=3000, units=3)))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    face = result["faces"][0]
    assert face["units_found"] == 3 and len(face["quads"]) == 3
    assert result["checks"]["units_complete"] is True
    centres = [sum(point[0] for point in quad) / 4 for quad in face["quads"]]
    assert centres == sorted(centres), centres


# ── the drawn plate follows the design's form, not the brief's category ─────

def test_the_drawn_body_follows_the_design_not_the_category():
    drawn = renderer_from_name("drawn")
    # a `food_jar` brief whose design is a carton still gets a carton
    box = drawn({"category": "food_jar", "product_line": "word-coffee"})
    assert "gift_box" in box["prompt"]
    # a `food_jar` brief whose design is a cylinder gets a cylinder
    jar = drawn({"category": "food_jar", "product_line": "harbor-body-oil"})
    assert "cylinder" in jar["prompt"]
    assert "gift_box" not in jar["prompt"]


def test_the_shipping_pouch_is_still_byte_identical():
    design = ba.design_for("mogra-lions-mane")
    for produced, shipped in ((ba.front_panel(design), mg.front_panel(design)),
                              (ba.back_panel(design), mg.back_panel(design))):
        assert (hashlib.sha256(produced.tobytes()).hexdigest()
                == hashlib.sha256(shipped.tobytes()).hexdigest())


def test_the_carton_form_is_untouched():
    design = ba.design_for("word-coffee")
    assert ba.form_of(design) == ba.GIFT_BOX
    gate = mq.assert_legible(ba.front_panel(design), wordmark="WORD COFFEE",
                             net_weight="120 g (4.2 oz)")
    assert gate["ok"] is True, gate


# ── the API offers the cylinder designs with their own plate briefs ─────────

def test_the_designs_endpoint_lists_the_cylinder_designs():
    import product_picture_api as api

    body = api.designs(acct="test-account")
    by_id = {d["id"]: d for d in body["designs"]}
    for design_id in CYLINDER_DESIGNS:
        assert design_id in by_id
        assert by_id[design_id]["form"] == ba.CYLINDER
        assert "cylindrical" in by_id[design_id]["plate_briefs"]["front"]
