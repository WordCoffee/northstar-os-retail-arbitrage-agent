"""A+ page brief: full page, exact canvases, deterministic, claims screened."""
from __future__ import annotations

import pytest

import aplus_brief as ab
import aplus_layout as geo
import aplus_render as ar

PRODUCT = {
    "brand": "MOGRA", "product": "LION'S MANE", "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)", "claims": ["100% PURE", "NO FILLERS"],
}


def test_the_page_has_every_module_and_each_one_passes_qa():
    result = ab.build_page(PRODUCT)
    assert result["page"]["ok"] is True
    assert not result["page"]["problems"]
    kinds = [m["kind"] for m in result["modules"]]
    assert kinds == list(ab.PAGE_MODULES)
    for module in result["modules"]:
        assert module["qa"]["ok"] is True, module
        assert tuple(module["size"]) == tuple(geo.CANVAS[module["kind"]])
        assert module["bytes"] < 2 * 1024 * 1024


def test_the_pack_is_deterministic():
    first = ab.build_page(PRODUCT)
    second = ab.build_page(PRODUCT)
    assert [m["sha256"] for m in first["modules"]] == [
        m["sha256"] for m in second["modules"]]


def test_a_prohibited_medical_claim_is_refused_before_a_pixel():
    with pytest.raises(ar.AplusNotPerfect) as err:
        ab.build_page({**PRODUCT, "claims": ["cures disease"]})
    assert "prohibited" in str(err.value).lower()


def test_the_brief_uses_the_declared_product_facts():
    specs = ab.page_copy(PRODUCT)
    kinds = [s["kind"] for s in specs]
    assert kinds == list(ab.PAGE_MODULES)
    header = next(s for s in specs if s["kind"] == "header")["copy"]
    assert header["headline"] == "LION'S MANE"
    assert header["kicker"] == "MOGRA"

def test_three_tiles_use_the_real_plate_not_placeholder_art():
    from PIL import Image, ImageDraw
    a = Image.new("RGB", (1200, 900), (240, 236, 226))
    ImageDraw.Draw(a).rectangle([100, 100, 500, 800], fill=(30, 80, 60))
    b = Image.new("RGB", (1200, 900), (240, 236, 226))
    ImageDraw.Draw(b).rectangle([100, 100, 500, 800], fill=(200, 90, 40))
    first = {m["kind"]: m["sha256"] for m in ab.build_page(PRODUCT, image=a)["modules"]}
    second = {m["kind"]: m["sha256"] for m in ab.build_page(PRODUCT, image=b)["modules"]}
    assert first["three_tiles"] != second["three_tiles"]

def test_square_and_landscape_plates_get_three_distinct_tiles():
    import hashlib
    from PIL import Image, ImageDraw
    for size in ((800, 800), (1200, 700)):
        plate = Image.new("RGB", size, (240, 236, 226))
        ImageDraw.Draw(plate).rectangle([50, 50, size[0] - 50, size[1] - 50],
                                        fill=(40, 90, 70))
        hashes = {hashlib.sha256(t.tobytes()).hexdigest()
                  for t in ab._derived_tiles(plate, 3)}
        assert len(hashes) == 3, (size, hashes)
