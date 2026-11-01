"""Complete package generation: four formats, design, dieline, mockup, manifest."""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_art
import package_pipeline as pp

ROOT = Path(__file__).resolve().parent.parent
BG = (208, 208, 208)
BODY = (176, 146, 116)
SIDE = (140, 116, 92)


def _png(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _box_plate():
    img = Image.new("RGB", (512, 640), BG)
    ImageDraw.Draw(img).rectangle([140, 120, 372, 520], fill=BODY)
    return img


def _bottle_plate():
    img = Image.new("RGB", (512, 640), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([230, 80, 282, 140], fill=BODY)
    d.polygon([(230, 140), (200, 190), (200, 540), (312, 540),
               (312, 190), (282, 140)], fill=BODY)
    return img


def _tube_plate():
    img = Image.new("RGB", (512, 640), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([210, 70, 302, 90], fill=BODY)
    d.polygon([(220, 90), (292, 90), (300, 520), (212, 520)], fill=BODY)
    d.rectangle([210, 520, 302, 540], fill=BODY)
    return img


PLATES = {"box": _box_plate, "bottle": _bottle_plate, "tube": _tube_plate}
DIMS = {
    "pouch": {"width_mm": 100, "height_mm": 200, "gusset_mm": 40},
    "box": {"width_mm": 80, "depth_mm": 40, "height_mm": 180},
    "bottle": {"diameter": 60, "height": 200, "label_height": 80,
               "label_top_offset": 30},
    "tube": {"diameter": 40, "height": 160},
}


def _spec(kind):
    return {
        "format": kind,
        "brand": "MOGRA ORGANICS",
        "theme": "forest",
        "title": "Mogra Forest Dusk",
        "subtitle": "Organic Mushroom Powder",
        "weight": "NET WT 6 OZ (170 g)",
        "servings": "34",
        "claims": ["Fruiting body", "Dual extracted", "Lab verified"],
        "icons": ["organic_sprout", "non_gmo", "gluten_free"],
        "ingredients": ["Organic reishi mushroom powder."],
        "suggested_use": "Mix one teaspoon into warm water daily.",
        "warnings": ["Consult a physician if pregnant or nursing."],
        "company": "Northstar OS LLC",
        "address": "123 Forest Lane, Portland, OR 97205",
        "country_of_origin": "USA",
        "lot_code": "LOT 2026-10",
        "dims": DIMS[kind],
    }


def _plate_path(kind, tmp_path):
    if kind == "pouch":
        candidate = ROOT / "exports" / "flow_formats_live_verified_20261031" / "pouch" / "01_plate.png"
        if candidate.is_file():
            return candidate
        pytest.skip("pouch fixture plate is not present")
    path = tmp_path / f"{kind}_plate.png"
    path.write_bytes(_png(PLATES[kind]()))
    return path


@pytest.mark.parametrize("kind", ["pouch", "box", "bottle", "tube"])
def test_four_formats_build_and_save(kind, tmp_path):
    plate = _plate_path(kind, tmp_path)
    out = tmp_path / kind
    result = pp.build_package(_spec(kind), plate_path=plate, out_dir=out)
    assert result["ok"] is True, result.get("questions") or result.get("warnings")
    assert result["format"] == kind
    assert {"front", "back", "side", "sheet", "mockup"} <= set(result["panels"])
    assert result["dieline"]["svg"].startswith("<svg")
    assert result["dieline"]["pdf"].startswith(b"%PDF")
    # Cylindrical labels are cut for the circumference, not the diameter.
    if kind == "bottle":
        assert result["dieline"]["flat_width_mm"] > 150
    if kind == "tube":
        assert result["dieline"]["flat_width_mm"] > 100
    assert result.get("mockup_quad") and len(result["mockup_quad"]) == 4
    assert result.get("mockup_method")
    assert result.get("quality", {}).get("verdict")

    files = pp.save_package(result, out)
    assert {"front", "back", "side", "sheet", "mockup", "dieline_svg",
            "dieline_pdf", "manifest"} <= set(files)
    manifest = json.loads((out / files["manifest"]).read_text(encoding="utf-8"))
    assert manifest["format"] == kind
    assert manifest["files"] == {k: v for k, v in files.items() if k != "manifest"}
    assert manifest["mockup_quad"] == result["mockup_quad"]
    # Ty's review (tys_4e9dd69a9dc8) flagged the missing spec snapshot.
    assert manifest["spec"]["title"] == "Mogra Forest Dusk"
    assert manifest["spec"]["ingredients"] == ["Organic reishi mushroom powder."]
    assert manifest["spec"]["dims"] == DIMS[kind]
    # JSON must stay free of raw bytes (the original save bug).
    json.dumps(manifest)


def test_missing_inputs_are_format_specific():
    base = _spec("box")
    base.pop("title")
    base["dims"] = {}
    gaps = pp.missing_inputs(base, "box")
    fields = {g["field"] for g in gaps}
    assert "title" in fields
    assert "dims.width_mm" in fields
    assert "dims.depth_mm" in fields
    assert "dims.height_mm" in fields
    assert "dims.gusset_mm" not in fields


def test_incomplete_order_returns_questions_not_art():
    spec = {"format": "box", "dims": {}}
    result = pp.build_package(spec)
    assert result["ok"] is False
    assert result["status"] == "needs_input"
    assert result["questions"]
    assert result["assets"] == []


@pytest.mark.parametrize("kind,size", [("box", (80, 180)), ("tube", (40, 124)),
                                       ("bottle", (45, 80)), ("pouch", (100, 148))])
def test_dynamic_front_is_mm_true(kind, size):
    spec = _spec(kind)
    art = package_art.render_front(spec, width_mm=size[0], height_mm=size[1])
    assert art.mode == "RGB"
    # 300 dpi: 11.811 px/mm, allowing the integer rounding in pd.P.
    assert abs(art.width - size[0] * 300 / 25.4) <= 2
    assert abs(art.height - size[1] * 300 / 25.4) <= 2
    # A blank design would be a single flat colour; a real front has many.
    extrema = art.convert("L").getextrema()
    assert extrema[1] - extrema[0] > 20


def test_theme_selection_falls_back_safely():
    spec = _spec("box")
    spec["theme"] = "not-a-theme"
    art = package_art.render_front(spec, width_mm=80, height_mm=180)
    assert art.size == (round(80 * 300 / 25.4), round(180 * 300 / 25.4))
