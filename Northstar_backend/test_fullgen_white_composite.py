"""D-022: a main-image brief must not be finished with a contact shadow under the product.

Found while closing D-020. The full-generation route already re-composes the product on
the brief's flat canvas (`generators._generate_cut_and_compose` → `white_canvas_png`), but
it then calls `product_composite.place_product` with its default `shadow=True`, which paints
a measured soft ellipse under the product. On 255 white that ellipse *is* the grey pool:
eight published artefacts carry 10.2 % to 25.6 % of the frame as residue
(`reports/ty/d020_residue_audit.json`).

A main image has no shadow. A free/scene brief keeps it: a product floating above its own
shadow in a lifestyle picture is the wrong defect in the other direction.

The checks are written first: one asserts the argument the composite is called with, and
one measures the delivered picture with the residue instrument the pass already uses.
"""
from __future__ import annotations

import io
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

import product_composite as composite
from tools.seller_tester.generators import CompositeGenerator
from tools.seller_tester.scorers import check_matte_residue, load_image

BG = (255, 255, 255)
PRODUCT = (620, 380, 1380, 1520)


def _scene_png(width: int = 2000, height: int = 2000) -> bytes:
    """A generated-looking plate: a coloured pack on a grey sweep."""
    image = Image.new("RGB", (width, height), (198, 198, 196))
    draw = ImageDraw.Draw(image)
    draw.rectangle(list(PRODUCT), fill=(52, 96, 70))
    draw.rectangle([PRODUCT[0], PRODUCT[1], PRODUCT[2], PRODUCT[1] + 40],
                   fill=(40, 74, 54))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _brief(*, background: dict, matte: dict | None = None,
           brief_id: str = "T-D022") -> dict:
    return {
        "id": brief_id, "category": "supplement_pouch",
        "situation": "white_background_main", "source_mode": "prompt_only",
        "fidelity": "tolerant", "label_mode": "none",
        "constraints": {
            "dimensions": {"min_width": 1000, "min_height": 1000,
                           "max_width": 4000, "max_height": 4000},
            "aspect": {"ratio": 1.0, "tolerance": 0.02},
            "background": dict(background),
            "matte": dict(matte or {"mode": "white_matte", "value": 255,
                                    "tolerance": 6, "max_border_std": 6}),
            "fill_pct": {"min": 10, "max": 60, "distance": 20},
            "text_rule": "no_text",
            "file_size": {"min_bytes": 1000, "max_bytes": 20000000},
        },
        "pass_score": 70,
    }


def _generator(tmp_path, *, calls: list) -> CompositeGenerator:
    def renderer(brief, mode="scene", inside_lane=None, size=None):
        return {"bytes": _scene_png(), "source": "generated", "prompt": "a pack on a sweep",
                "model": None, "width": 2000, "height": 2000, "seed": 1, "note": None}

    original = composite.place_product

    def spy(scene, product, **kwargs):
        calls.append(dict(kwargs))
        return original(scene, product, **kwargs)

    composite.place_product = spy
    return CompositeGenerator(renderer=renderer, renderer_name="injected",
                              out_dir=tmp_path / "out", repo_root=tmp_path, seed=1)


def _finish(generator) -> None:
    composite.place_product = _ORIGINAL_PLACE


_ORIGINAL_PLACE = composite.place_product


def test_a_main_image_is_composed_without_a_contact_shadow(tmp_path):
    calls: list = []
    generator = _generator(tmp_path, calls=calls)
    try:
        generator.generate(_brief(background={"mode": "uniform", "value": 255,
                                             "tolerance": 6}))
    finally:
        _finish(generator)
    assert calls, "place_product was never called"
    assert calls[0].get("shadow") is False, (
        f"a main image was composed with shadow={calls[0].get('shadow')!r}")


def test_a_free_background_keeps_its_contact_shadow(tmp_path):
    calls: list = []
    generator = _generator(tmp_path, calls=calls)
    try:
        generator.generate(_brief(background={"mode": "free"},
                                  matte={"mode": "any"}))
    finally:
        _finish(generator)
    assert calls and calls[0].get("shadow") is True, (
        "a lifestyle picture must keep the product's shadow")


def test_the_delivered_main_image_has_no_residue(tmp_path):
    calls: list = []
    generator = _generator(tmp_path, calls=calls)
    brief = _brief(background={"mode": "uniform", "value": 255, "tolerance": 6})
    try:
        path = generator.generate(brief)
    finally:
        _finish(generator)
    record = generator.record_for(brief["id"])
    cutout = np.asarray(Image.open(path.with_suffix(".cutout.png")).convert("RGBA"))
    loaded = load_image(path.read_bytes())
    from tools.seller_tester.scorers import _product_mask_from_cutout

    mask = _product_mask_from_cutout(cutout, record.get("product_box"),
                                     loaded.rgb.shape[:2])
    verdict = check_matte_residue(loaded.rgb, brief["constraints"]["background"],
                                  subject_mask=mask)
    assert verdict["ok"] is True, verdict
    assert verdict["residue_pct"] <= 0.5, verdict


def test_the_control_a_shadowed_composition_fails_the_same_check(tmp_path):
    """The measurement has teeth: the same picture with the shadow on is residue."""
    plate = Image.open(io.BytesIO(_scene_png())).convert("RGB")
    from tools.seller_tester.generators import white_canvas_png

    cut = np.zeros((plate.height, plate.width), dtype=np.uint8)
    cut[PRODUCT[1]:PRODUCT[3], PRODUCT[0]:PRODUCT[2]] = 255
    import product_cutout as pc

    cut_png = pc.rgba_png_bytes(np.asarray(plate), cut)
    bg = white_canvas_png(2000, 255)
    shadowed = composite.place_product(bg, cut_png, scale=0.62, anchor=(0.5, 0.6),
                                       shadow=True)
    clean = composite.place_product(bg, cut_png, scale=0.62, anchor=(0.5, 0.6),
                                    shadow=False)
    brief = _brief(background={"mode": "uniform", "value": 255, "tolerance": 6})
    spec = brief["constraints"]["background"]

    def residue(placed):
        loaded = load_image(placed["bytes"])
        from tools.seller_tester.scorers import _product_mask_from_cutout

        mask = _product_mask_from_cutout(
            np.asarray(Image.open(io.BytesIO(cut_png)).convert("RGBA")),
            placed["product_box"], loaded.rgb.shape[:2])
        return check_matte_residue(loaded.rgb, spec, subject_mask=mask)

    bad = residue(shadowed)
    good = residue(clean)
    assert bad["ok"] is False, json.dumps(bad)
    assert good["ok"] is True, json.dumps(good)
