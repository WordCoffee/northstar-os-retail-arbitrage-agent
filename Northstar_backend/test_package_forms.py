"""The second packaging form: a brand is a design entry, not a code change.

Contract under test (acceptance A1-A9, `reports/ty/sel06b_acceptance.md`):

* the pouch form is byte-identical to what shipped — the Mogra artwork cannot
  change by accident;
* a folding carton is a *different form*: its own plate brief, its own print
  insets, no Supplement Facts panel;
* a plate with no box in it is refused, never composited;
* a brief that names a product line nobody has designed raises and names the
  brief, rather than quietly rendering a different brand.
"""
from __future__ import annotations

import hashlib
import io
import json

import pytest
from PIL import Image, ImageDraw

import brand_art as ba
import mockup_quality as mq
import mogra_label_art as mg
import product_picture as pp
from tools.seller_tester.scene_render import synthetic_plate


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _box_plate(width=1024, height=1536, box=(330, 300, 700, 1240)) -> Image.Image:
    """A slim pale-pink carton on a pale sweep: two real edges to measure."""
    plate = Image.new("RGB", (width, height), (232, 230, 226))
    d = ImageDraw.Draw(plate)
    d.polygon([(box[0], box[1]), (box[2], box[1]), (box[2] + 10, box[3]),
               (box[0] - 10, box[3])], fill=(240, 196, 202))
    d.rectangle([box[0], box[1], box[2], box[1] + 18], fill=(228, 182, 190))
    return plate


def _pouch_plate(width=1024, height=1536, box=(330, 360, 700, 1240)) -> Image.Image:
    plate = Image.new("RGB", (width, height), (232, 230, 226))
    d = ImageDraw.Draw(plate)
    d.polygon([(box[0], box[1]), (box[2], box[1]), (box[2] + 8, box[3]),
               (box[0] - 8, box[3])], fill=(213, 167, 122))
    d.rectangle([box[0], box[1], box[2], box[1] + 26], fill=(196, 152, 110))
    return plate


def _generator(image: Image.Image):
    def inner(brief, *, width, height, tier, seed):
        return {"bytes": _png(image), "seed": seed, "model": "fake-plate",
                "width": image.width, "height": image.height,
                "used_brief": brief, "contains_text": False}
    return inner


# ── A1 / A8: the design registry ─────────────────────────────────────────────

def test_a_second_brand_declares_a_box_form():
    design = ba.design_for("word-coffee")
    assert ba.form_of(design) == ba.GIFT_BOX
    assert design["brand"] == "WORD COFFEE"
    assert design["script_line"] == "For Mom"
    assert design["tagline"] == "Empowering Moms, One Message at a Time"
    assert "supplement_facts" not in design
    assert design["net_weight"] == "120 g (4.2 oz)"


def test_an_unknown_design_names_the_known_ones():
    with pytest.raises(ValueError) as err:
        ba.design_for("moon-dust")
    message = str(err.value)
    assert "moon-dust" in message
    assert "word-coffee" in message and "mogra-lions-mane" in message


def test_a_design_copy_can_be_edited_without_side_effects():
    first = ba.design_for("word-coffee")
    first["brand"] = "CHANGED"
    assert ba.design_for("word-coffee")["brand"] == "WORD COFFEE"


# ── A2: the shipping pouch is untouched ──────────────────────────────────────

def test_the_pouch_form_is_byte_identical_to_the_shipped_artwork():
    design = ba.design_for("mogra-lions-mane")
    for produced, shipped in (
            (ba.front_panel(design), mg.front_panel(design)),
            (ba.back_panel(design), mg.back_panel(design))):
        assert produced.size == shipped.size
        assert (hashlib.sha256(produced.tobytes()).hexdigest()
                == hashlib.sha256(shipped.tobytes()).hexdigest())


# ── A3 / A4: the box artwork is a carton, not a supplement label ─────────────

def test_the_box_front_carries_the_brand_script_and_weight():
    design = ba.design_for("word-coffee")
    panel = ba.front_panel(design)
    gate = mq.assert_legible(panel, wordmark="WORD COFFEE", net_weight="120 g (4.2 oz)")
    assert gate["ok"] is True, gate
    words = " ".join(gate["words"]).lower()
    assert "for mom" in words, gate["words"]
    assert "empowering moms" in words.replace("enpowering", "empowering"), gate["words"]
    assert "supplement" not in words


def test_the_box_back_is_not_a_supplement_panel():
    design = ba.design_for("word-coffee")
    panel = ba.back_panel(design)
    gate = mq.assert_legible(panel, wordmark="WORD COFFEE", net_weight="120 g (4.2 oz)")
    assert gate["ok"] is True, gate
    words = " ".join(gate["words"]).lower()
    assert "supplement" not in words and "daily value" not in words
    assert "ingredients" in words.replace(" ", "")
    assert "850000000004" in words.replace(" ", "")


def test_the_box_face_is_the_declared_size():
    design = ba.design_for("word-coffee")
    w_mm, h_mm = ba.face_mm(design, "front")
    panel = ba.front_panel(design)
    ratio = panel.size[0] / panel.size[1]
    assert abs(ratio - (w_mm / h_mm)) < 0.01


def test_a_box_is_not_inset_like_a_pouch_weld():
    pouch = pp.FORM_INSETS[ba.POUCH]
    box = pp.FORM_INSETS[ba.GIFT_BOX]
    assert box["inset_top"] < pouch["inset_top"]
    assert box["inset_bottom"] < pouch["inset_bottom"]


# ── A9: a brief reaches its design, and never falls back ─────────────────────

def test_a_brief_resolves_by_its_product_line():
    assert ba.design_for_brief({"id": "PO-002", "product_line": "word-coffee"})["brand"] == "WORD COFFEE"
    assert ba.form_of(ba.design_for_brief({"id": "PO-001", "product_line": "lions-mane"})) == ba.POUCH


def test_a_brief_with_an_undesigned_line_names_itself():
    with pytest.raises(ValueError) as err:
        ba.design_for_brief({"id": "PO-099", "product_line": "tea-tin"})
    assert "PO-099" in str(err.value) and "tea-tin" in str(err.value)
    with pytest.raises(ValueError):
        ba.design_for_brief({"id": "PO-100"})


# ── A5 / A6 / A7: the shipping path ─────────────────────────────────────────

def test_a_box_plate_yields_a_gated_carton_picture(tmp_path):
    design = ba.design_for("word-coffee")
    result = pp.build(design, out_dir=str(tmp_path / "wc"), out_root=str(tmp_path),
                      faces=("front",), generator=_generator(_box_plate()))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    assert result["product"]["form"] == ba.GIFT_BOX
    record = result["faces"][0]
    assert "gift box" in record["brief"] and "pouch" not in record["brief"]
    path = tmp_path / "wc" / "product_front.png"
    assert path.is_file() and path.stat().st_size > 20_000
    manifest = json.loads((tmp_path / "wc" / "product_picture_manifest.json").read_text())
    assert manifest["product"]["form"] == ba.GIFT_BOX
    assert manifest["checks"]["legible"] is True


def test_a_plate_with_no_box_is_refused(tmp_path):
    design = ba.design_for("word-coffee")
    flat = Image.new("RGB", (1024, 1536), (236, 233, 227))
    result = pp.build(design, out_dir=str(tmp_path / "wc"), out_root=str(tmp_path),
                      faces=("front",), generator=_generator(flat))
    assert result["ok"] is False
    assert "plate_face_not_found" in result["faces"][0]["reason"]
    assert not (tmp_path / "wc" / "product_front.png").exists()


def test_the_default_build_still_asks_for_a_pouch_plate(tmp_path):
    result = pp.build(out_dir=str(tmp_path), out_root=str(tmp_path),
                      faces=("front",), generator=_generator(_pouch_plate()))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    assert result["product"]["form"] == ba.POUCH
    assert "pouch" in result["faces"][0]["brief"]
    assert result["faces"][0]["quad"], "the pouch face must still be measured"


def test_a_carton_plate_composes_the_carton_panel_not_the_pouch_panel(tmp_path):
    design = ba.design_for("word-coffee")
    result = pp.build(design, out_dir=str(tmp_path / "wc"), out_root=str(tmp_path),
                      faces=("front",), generator=_generator(_box_plate()))
    words = " ".join(result["faces"][0]["legibility"]["words"]).lower()
    assert "word" in words and "coffee" in words
    assert "mogra" not in words


# ── the API offers both brands, and validates against the design's own form ──

def test_the_designs_endpoint_lists_every_brand_with_its_form():
    import product_picture_api as api

    body = api.designs(acct="test-account")
    by_id = {d["id"]: d for d in body["designs"]}
    assert set(by_id) == {"mogra-lions-mane", "word-coffee"}
    assert by_id["mogra-lions-mane"]["form"] == ba.POUCH
    assert by_id["word-coffee"]["form"] == ba.GIFT_BOX
    assert "pouch" in by_id["mogra-lions-mane"]["plate_briefs"]["front"]
    assert "gift box" in by_id["word-coffee"]["plate_briefs"]["front"]
    assert by_id["word-coffee"]["face_mm"] == [100.0, 200.0]


def test_the_api_refuses_an_unknown_brand_by_name():
    import product_picture_api as api
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        api.create_product_picture(api.ProductPictureIn(product="moon-dust"), acct="t")
    assert err.value.status_code == 422
    assert "word-coffee" in str(err.value.detail)


def test_the_api_validates_faces_against_the_designs_form():
    import product_picture_api as api
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as err:
        api.create_product_picture(
            api.ProductPictureIn(product="word-coffee", faces=["side"]), acct="t")
    assert err.value.status_code == 422
    assert "front" in str(err.value.detail)


# ── a bundle is three units, and it is measured as three ────────────────────

def test_three_units_are_measured_left_to_right():
    from tools.seller_tester.scene_render import synthetic_plate
    import mockup_compositor as mc

    plate = Image.open(io.BytesIO(
        synthetic_plate(width=2000, height=2000, kind="gift_box",
                        field="white", units=3)["bytes"]))
    quads = mc.find_panel_quads(plate, count=3, **pp.FORM_INSETS[ba.GIFT_BOX])
    assert len(quads) == 3
    centres = [sum(point[0] for point in quad) / 4 for quad in quads]
    assert centres == sorted(centres), centres
    assert centres[2] - centres[0] > 200


def test_a_three_unit_build_writes_three_panels_and_says_so(tmp_path):
    from tools.seller_tester.scene_render import synthetic_plate

    plate = Image.open(io.BytesIO(
        synthetic_plate(width=2000, height=2000, kind="gift_box",
                        field="white", units=3)["bytes"]))
    result = pp.build(ba.design_for("word-coffee"), out_dir=str(tmp_path / "b"),
                      out_root=str(tmp_path), faces=("front",), units=3,
                      width=2000, height=2000, generator=_generator(plate))
    assert result["ok"] is True, json.dumps(result["faces"], indent=2)
    face = result["faces"][0]
    assert face["units_found"] == 3 and len(face["quads"]) == 3
    assert result["product"]["units"] == 3
    assert result["checks"]["units_complete"] is True


def test_a_bundle_plate_with_one_unit_is_refused(tmp_path):
    from tools.seller_tester.scene_render import synthetic_plate

    plate = Image.open(io.BytesIO(
        synthetic_plate(width=2000, height=2000, kind="gift_box",
                        field="white", units=1)["bytes"]))
    result = pp.build(ba.design_for("word-coffee"), out_dir=str(tmp_path / "b"),
                      out_root=str(tmp_path), faces=("front",), units=3,
                      width=2000, height=2000, generator=_generator(plate))
    assert result["ok"] is False
    assert "units_not_found: measured 1 of 3" in result["faces"][0]["reason"]
    assert not (tmp_path / "b" / "product_front.png").exists()


def test_one_unit_is_still_one_unit(tmp_path):
    plate = Image.open(io.BytesIO(
        synthetic_plate(width=2000, height=2000, kind="gift_box",
                        field="white", units=1)["bytes"]))
    result = pp.build(ba.design_for("word-coffee"), out_dir=str(tmp_path / "b"),
                      out_root=str(tmp_path), faces=("front",), width=2000,
                      height=2000, generator=_generator(plate))
    assert result["ok"] is True
    assert result["faces"][0]["units_found"] == 1


def test_the_api_carries_units_and_bounds_them():
    import product_picture_api as api

    assert api.ProductPictureIn(product="word-coffee").units == 1
    assert api.ProductPictureIn(product="word-coffee", units=3).units == 3
    with pytest.raises(Exception):
        api.ProductPictureIn(product="word-coffee", units=0)
