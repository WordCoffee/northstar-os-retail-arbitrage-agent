"""D-021: a main-image brief must not be photographed with a contact shadow.

Found while closing D-020. `synthetic_plate` draws a base shadow "so the plate is not a
sticker on a flat field" (`scene_render.py:431`), and the plate prompts ask the model for
"a gentle contact shadow". On a **main image** — the product alone on a flat value — that
shadow is not a selling cue, it is a defect: the cutout keeps it (it is attached), the
silhouette then includes it, and the D-020 residue check reads 0.00 % on a picture a
seller cannot list.

So the plate itself must be shadowless for a main-image brief, on both routes:

* the drawn stand-in (`synthetic_plate(shadow=False)`) draws no base shadow;
* the real plate brief (`plate_brief(..., shadow=False)`) asks for no contact shadow.

Free-background briefs keep the shadow: a lifestyle picture with the product floating
above its own shadow would be the wrong defect.

The checks are written first, and they compare two plates rather than assert a geometry:
the pixel set that differs between `shadow=True` and `shadow=False` is the shadow, and in
the clean plate every one of those pixels is the bare field.
"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

import brand_art as ba
import product_picture as pp
from tools.seller_tester.scene_render import renderer_from_name, synthetic_plate


def _plate(**kwargs) -> np.ndarray:
    scene = synthetic_plate(width=1024, height=1024, kind="pouch", field="white",
                            value=255, units=1, **kwargs)
    from io import BytesIO

    with Image.open(BytesIO(scene["bytes"])) as opened:
        return np.asarray(opened.convert("RGB"))


def _main_image_brief() -> dict:
    return {
        "id": "T-D021", "category": "supplement_pouch", "situation": "white_background_main",
        "source_mode": "prompt_only", "product_line": "lions-mane", "label_mode": "warp",
        "constraints": {
            "background": {"mode": "uniform", "value": 255, "tolerance": 6},
            "matte": {"mode": "white_matte", "value": 255, "tolerance": 6},
        },
    }


def _free_brief() -> dict:
    brief = _main_image_brief()
    brief["constraints"] = {"background": {"mode": "free"}, "matte": {"mode": "any"}}
    return brief


# ── the drawn plate ───────────────────────────────────────────────────────────

def test_a_shadowless_plate_draws_no_shadow_and_a_shadowed_one_does():
    clean = _plate(shadow=False)
    shadowed = _plate(shadow=True)
    changed = (clean != shadowed).any(axis=2)
    assert int(changed.sum()) > 1000, "the base shadow was not drawn at all"
    # The shadow's own territory is below the body: the body's last marked row is where
    # the clean plate stops, and every row under it must be the bare field there.
    marked_rows = np.where((clean < 250).any(axis=2).any(axis=1))[0]
    base = int(marked_rows.max())
    below = slice(base + 1, None)
    assert not (clean[below] < 250).any(), "the clean plate carries a mark below the body"
    assert (shadowed[below] < 250).any(), "the shadowed plate has no shadow below the body"


def test_the_drawn_renderer_drops_the_shadow_for_a_main_image_brief():
    render = renderer_from_name("drawn")
    main = render(_main_image_brief(), size=(1024, 1024))
    free = render(_free_brief(), size=(1024, 1024))
    from io import BytesIO

    with Image.open(BytesIO(main["bytes"])) as opened:
        main_rgb = np.asarray(opened.convert("RGB"))
    with Image.open(BytesIO(free["bytes"])) as opened:
        free_rgb = np.asarray(opened.convert("RGB"))
    assert int((free_rgb != main_rgb).any(axis=2).sum()) > 1000, (
        "a free-background brief must keep its shadow; a main image must not")
    kind = ba.plate_kind(ba.design_for_brief(_main_image_brief()))
    direct = _plate(shadow=False) if kind == "pouch" else None
    if direct is not None:
        assert np.array_equal(main_rgb, direct), (
            "the drawn main-image plate is not the shadowless plate")


# ── the real plate brief ──────────────────────────────────────────────────────

def test_the_plate_brief_stops_asking_for_a_contact_shadow():
    design = ba.design_for("mogra-lions-mane")
    for form in (ba.POUCH, ba.GIFT_BOX, ba.CYLINDER):
        shadowed = pp.plate_brief("front", form, design, shadow=True).lower()
        clean = pp.plate_brief("front", form, design, shadow=False).lower()
        assert "contact shadow" in shadowed
        assert "contact shadow" not in clean, (form, clean)
        assert "no shadow" in clean or "shadowless" in clean, (form, clean)


def test_a_bundle_brief_stops_asking_for_a_shadow_under_each():
    design = ba.design_for("mogra-lions-mane")
    clean = pp.plate_brief("front", ba.POUCH, design, units=3, shadow=False).lower()
    assert "contact shadow" not in clean, clean


def test_build_asks_the_plate_for_no_shadow_on_a_main_image(tmp_path):
    asked: dict = {}

    def generator(brief, *, width, height, tier, seed):
        asked["brief"] = brief
        image = Image.new("RGB", (1200, 1200), (255, 255, 255))
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        return {"bytes": buffer.getvalue(), "seed": seed, "model": "supplied",
                "width": 1200, "height": 1200, "used_brief": brief,
                "contains_text": False}

    pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "w"),
             out_root=str(tmp_path), faces=("front",), width=1200, height=1200,
             generator=generator, background="white")
    assert "contact shadow" not in asked["brief"].lower(), asked["brief"]

    asked.clear()
    pp.build(ba.design_for("mogra-lions-mane"), out_dir=str(tmp_path / "s"),
             out_root=str(tmp_path), faces=("front",), width=1200, height=1200,
             generator=generator)
    assert "contact shadow" in asked["brief"].lower(), asked["brief"]
