"""D-011: the Seller-Tester renders through the app's product-picture path.

The harness used to compose its own label and warp it with its own quad, so every
seller number described the harness. `ProductPipelineGenerator` supplies only the
plate; the face measurement, the brand artwork, the warp and the OCR gate are
`product_picture.build`'s.

These tests pin the seam: what the generator may refuse, what it must not fake,
and that a success carries the app's own manifest.
"""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from tools.seller_tester.generators import (
    GeneratorUnavailable,
    ProductPipelineGenerator,
)
from tools.seller_tester.scene_render import (
    renderer_from_name,
    synthetic_plate,
    synthetic_scene,
)


def _brief(**overrides):
    brief = {
        "id": "PO-T1",
        "category": "supplement_pouch",
        "product_line": "lions-mane",
        "situation": "white_background_main",
        "source_mode": "prompt_only",
        "fidelity": "tolerant",
        "label_mode": "warp",
        "prompt": "a matte forest-green stand-up pouch",
        "body_prompt": "a plain matte forest-green stand-up pouch, no text",
        "label": {"brand": "Mogra Organics", "product": "Lion's Mane", "weight": "6 oz"},
        "constraints": {
            "dimensions": {"min_width": 1200, "min_height": 1200},
            "background": {"value": 255, "tolerance": 6, "mode": "uniform"},
            "matte": {"mode": "white_matte", "value": 255, "tolerance": 6},
        },
    }
    brief.update(overrides)
    return brief


def _generator(tmp_path, renderer=None, name="drawn"):
    return ProductPipelineGenerator(renderer=renderer or renderer_from_name("drawn"),
                                    renderer_name=name, out_dir=str(tmp_path))


def test_the_app_path_serves_the_pouch_brand(tmp_path):
    gen = _generator(tmp_path)
    path = gen.generate(_brief())
    assert path.is_file() and path.stat().st_size > 20_000
    record = gen.record_for("PO-T1")
    assert record["route"] == "product_picture"
    assert record["form"] == "stand_up_pouch"
    assert record["build"]["faces"][0]["gate_ok"] is True
    manifest = json.loads((path.parent / "product_picture_manifest.json").read_text())
    assert manifest["schema"] == "northstar.product_picture.v1"
    assert manifest["product"]["form"] == "stand_up_pouch"


def test_the_app_path_serves_the_box_brand(tmp_path):
    gen = _generator(tmp_path)
    brief = _brief(id="PO-T2", category="food_jar", product_line="word-coffee",
                   situation="lifestyle",
                   label={"brand": "Word Coffee", "product": "For Mom", "weight": ""})
    brief["constraints"]["background"] = {"value": 255, "tolerance": 6, "mode": "free"}
    brief["constraints"].pop("matte", None)
    path = gen.generate(brief)
    record = gen.record_for("PO-T2")
    assert path.is_file()
    assert record["form"] == "gift_box"
    assert record["design"] == "word-coffee"
    manifest = json.loads((path.parent / "product_picture_manifest.json").read_text())
    assert "gift box" in manifest["faces"][0]["brief"]


def test_an_undesigned_product_line_is_refused_by_name(tmp_path):
    gen = _generator(tmp_path)
    with pytest.raises(GeneratorUnavailable) as err:
        gen.generate(_brief(id="PO-T3", product_line="tea-tin"))
    assert "PO-T3" in str(err.value) and "tea-tin" in str(err.value)
    assert gen.record_for("PO-T3")["artefact"] is None


def test_a_brief_without_label_mode_is_refused(tmp_path):
    gen = _generator(tmp_path)
    with pytest.raises(GeneratorUnavailable) as err:
        gen.generate(_brief(id="PO-T4", label_mode=None))
    assert "warp" in str(err.value)


def test_a_scene_is_refused_because_the_lane_returned_no_plate(tmp_path):
    scene = synthetic_scene(width=512, height=512)

    def renderer(brief, mode="scene", inside_lane=None, size=None):
        return scene

    gen = _generator(tmp_path, renderer=renderer, name="injected")
    with pytest.raises(GeneratorUnavailable) as err:
        gen.generate(_brief(id="PO-T5"))
    assert "scene, not a plate" in str(err.value)


def test_the_apps_own_refusal_is_carried_out(tmp_path):
    flat = Image.new("RGB", (1200, 1200), (255, 255, 255))
    buffer = io.BytesIO()
    flat.save(buffer, format="PNG")
    payload = buffer.getvalue()

    def renderer(brief, mode="plate", inside_lane=None, size=None):
        return {"bytes": payload, "source": "synthetic_plate", "prompt": "flat",
                "model": None, "width": 1200, "height": 1200, "seed": 1, "note": None}

    gen = _generator(tmp_path, renderer=renderer, name="injected")
    with pytest.raises(GeneratorUnavailable) as err:
        gen.generate(_brief(id="PO-T6"))
    message = str(err.value)
    assert "plate_face_not_found" in message
    assert not (tmp_path / "PO-T6" / "product_front.png").exists()


def test_the_drawn_plate_is_labelled_as_drawn(tmp_path):
    gen = _generator(tmp_path)
    gen.generate(_brief(id="PO-T7"))
    record = gen.record_for("PO-T7")
    assert record["plate"]["source"] == "synthetic_plate"
    assert "not generated" in (record["plate"]["note"] or "")


def test_the_drawn_renderer_honours_the_briefs_field_value():
    plate = synthetic_plate(width=600, height=600, kind="pouch", field="white", value=245)
    img = Image.open(io.BytesIO(plate["bytes"])).convert("RGB")
    assert img.getpixel((2, 2)) == (245, 245, 245)
