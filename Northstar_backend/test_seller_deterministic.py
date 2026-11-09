"""The deterministic stages: infographic copy and the packaging panel.

Two claims are being tested, and they are different. First, **determinism**: the same brief and the
same inputs produce the same bytes, which is what makes these situations testable at all. Second,
**honesty of the geometry**: the text is where the brief says copy lives, the product's own pixels
are not painted over, and a perspective-warped panel is still compared against the artwork it came
from rather than being reported as a fidelity failure.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from PIL import Image  # noqa: E402

from seller_tester import deterministic as D  # noqa: E402
from seller_tester import composite_check as C  # noqa: E402


def _canvas(size=800, colour=(250, 248, 244)):
    return Image.new("RGB", (size, size), colour)


def _png(image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _product(size=(240, 320)):
    """A blocky 'product' with structure, so a similarity score means something."""
    rng = np.random.default_rng(11)
    array = np.zeros((size[1], size[0], 3), dtype=np.uint8)
    array[:] = (30, 110, 70)
    array[20:120, 30:210] = rng.integers(0, 255, size=(100, 180, 3), dtype=np.uint8)
    return array


def _paste(canvas, product, box):
    x, y, width, height = box
    out = np.array(canvas).copy()
    resized = np.array(Image.fromarray(product).resize((width, height)))
    out[y:y + height, x:x + width] = resized
    return out


def test_the_seed_is_stable_and_depends_on_the_brief():
    assert D.stable_seed("HO-001") == D.stable_seed("HO-001")
    assert D.stable_seed("HO-001") != D.stable_seed("HO-002")
    assert isinstance(D.stable_seed("x"), int)


def test_the_infographic_is_byte_identical_on_a_repeat():
    canvas = _png(_canvas())
    brief = {"id": "HO-900", "situation": "infographic", "product_line": "lions-mane"}
    first = D.infographic(canvas, [280, 300, 240, 320], brief)
    second = D.infographic(canvas, [280, 300, 240, 320], brief)
    assert first["bytes"] == second["bytes"]
    assert first["meta"]["margin_ink"] == second["meta"]["margin_ink"]


def test_the_infographic_puts_copy_in_the_margin():
    canvas = _png(_canvas())
    brief = {"id": "HO-901", "situation": "infographic", "product_line": "lions-mane"}
    result = D.infographic(canvas, [280, 300, 240, 320], brief)
    ink = D.margin_ink_fraction(np.asarray(Image.open(__import__("io").BytesIO(result["bytes"]))))
    assert ink >= 0.002, f"margin ink {ink} is below the brief's text_expected bar"
    assert result["meta"]["callouts"] >= 1
    assert result["meta"]["title"] == "LIONS MANE"


def test_the_infographic_does_not_paint_over_the_product():
    product = _product()
    box = (280, 300, 240, 320)
    before = _paste(_canvas(), product, box)
    result = D.infographic(_png(Image.fromarray(before)), list(box),
                           {"id": "HO-902", "product_line": "lions-mane"})
    after = np.asarray(Image.open(__import__("io").BytesIO(result["bytes"])))
    x, y, width, height = box
    assert np.array_equal(before[y:y + height, x:x + width],
                          after[y:y + height, x:x + width]), \
        "the layout drew inside the product box"


def test_the_canvas_is_extended_to_the_brief_aspect_without_cropping():
    """A 4:5 brief used to be failed on `aspect` by a lane that can only produce 1.0."""
    product = _product()
    box = (180, 200, 240, 320)
    before = _paste(_canvas(700), product, box)
    fitted = D.fit_aspect(_png(Image.fromarray(before)), list(box), 0.8)
    out = np.asarray(Image.open(__import__("io").BytesIO(fitted["bytes"])))
    assert round(out.shape[1] / out.shape[0], 3) == 0.8
    assert out.shape[0] > before.shape[0], "the canvas should grow, not shrink"
    # every original pixel is still there, moved down by the new top band
    top = fitted["added"]["top"]
    assert np.array_equal(before, out[top:top + before.shape[0], :before.shape[1]])
    assert fitted["product_box"][1] == box[1] + top


def test_a_square_brief_is_left_alone():
    fitted = D.fit_aspect(_png(_canvas(400)), [10, 10, 100, 100], 1.0)
    assert fitted["added"] == {"width": 0, "height": 0, "top": 0, "left": 0}
    assert fitted["product_box"] == [10, 10, 100, 100]


def test_the_brief_aspect_is_read_from_the_constraints():
    assert D.brief_aspect({"constraints": {"aspect": {"ratio": 0.8}}}) == 0.8
    assert D.brief_aspect({}) == 1.0
    assert D.brief_aspect({"constraints": {"aspect": {"ratio": 99}}}) == 1.0


def test_the_panel_warp_is_byte_identical_on_a_repeat():
    product = _product()
    before = _png(Image.fromarray(_paste(_canvas(), product, (280, 300, 240, 320))))
    brief = {"id": "HO-903", "situation": "packaging_mockup"}
    first = D.panel_warp(before, [280, 300, 240, 320], brief)
    second = D.panel_warp(before, [280, 300, 240, 320], brief)
    assert first["bytes"] == second["bytes"]
    assert first["quad"] == second["quad"]


def test_the_panel_warp_changes_the_artwork_inside_the_quad_only():
    product = _product()
    box = (280, 300, 240, 320)
    before = _paste(_canvas(), product, box)
    after = np.asarray(Image.open(__import__("io").BytesIO(
        D.panel_warp(_png(Image.fromarray(before)), list(box),
                     {"id": "HO-904"})["bytes"])))
    x, y, width, height = box
    assert not np.array_equal(before[y:y + height, x:x + width],
                              after[y:y + height, x:x + width]), "the panel was not warped"
    outside = np.ones(before.shape[:2], dtype=bool)
    outside[y:y + height, x:x + width] = False
    assert np.array_equal(before[outside], after[outside]), "the warp leaked outside its panel"


def test_a_warped_panel_is_compared_against_the_artwork_with_the_same_homography():
    product = _product()
    box = [280, 300, 240, 320]
    canvas = _paste(_canvas(), product, box)
    warped = D.panel_warp(_png(Image.fromarray(canvas)), box, {"id": "HO-905"})
    produced = np.asarray(Image.open(__import__("io").BytesIO(warped["bytes"])))
    verdict = C.check_composite(produced, product, placement_quad=warped["quad"])
    assert verdict["cannot_verify"] is False, verdict
    assert verdict["ok"] is True, verdict
    assert verdict["compared"] == "quad"


def test_a_quad_outside_the_frame_is_a_named_failure():
    produced = np.zeros((200, 200, 3), dtype=np.uint8)
    verdict = C.check_composite(produced, _product(), placement_quad=[[10, 10], [300, 10],
                                                                     [300, 300], [10, 300]])
    assert verdict["ok"] is False
    assert verdict["cannot_verify"] is True
    assert "outside" in verdict["detail"]


def test_a_different_product_in_the_quad_fails():
    product = _product()
    box = [280, 300, 240, 320]
    warped = D.panel_warp(_png(Image.fromarray(_paste(_canvas(), product, box))), box,
                          {"id": "HO-906"})
    produced = np.asarray(Image.open(__import__("io").BytesIO(warped["bytes"])))
    rng = np.random.default_rng(3)
    other = rng.integers(0, 255, size=product.shape, dtype=np.uint8)
    verdict = C.check_composite(produced, other, placement_quad=warped["quad"])
    assert verdict["ok"] is False, verdict


def test_the_packaging_route_records_a_quad_and_a_quad_identity(tmp_path):
    """The generator must survive its own packaging path: this is the test the demo run lacked.

    It runs the real `CompositeGenerator` with an injected scene renderer (no GPU, no model), on a
    brief whose situation is `packaging_mockup`, and asserts the record carries the quad and that
    the identity was measured against the warped panel rather than the flat artwork.
    """
    import json

    from seller_tester.generators import CompositeGenerator

    reference = ROOT / "renders" / "references" / "mogra" / "mogra_pair_main.png"
    brief = {
        "id": "LM-QUAD-01",
        "category": "supplement_pouch",
        "situation": "packaging_mockup",
        "difficulty": 1,
        "source_mode": "uploaded_reference",
        "fidelity": "exact",
        "product_in_frame": True,
        "reference": {"kind": "uploaded_file", "path": str(reference.relative_to(ROOT)),
                      "descriptor": {"filename": reference.name, "mime_type": "image/png",
                                     "subject": "mogra"}},
        "constraints": {"dimensions": {"min_width": 512, "min_height": 512},
                        "aspect": {"ratio": 1.0, "tolerance": 0.05},
                        "background": {"value": 255, "tolerance": 24, "mode": "free"},
                        "fill_pct": {"min": 5, "max": 100, "distance": 40},
                        "matte": {"mode": "any"}},
    }

    class Renderer:
        def __call__(self, brief, mode, inside_lane=None):
            from io import BytesIO

            from PIL import Image

            buffer = BytesIO()
            Image.new("RGB", (1024, 1024), (238, 236, 230)).save(buffer, format="PNG")
            return {"bytes": buffer.getvalue(), "source": "synthetic", "prompt": None,
                    "seed": 0, "steps": 0, "lane": None, "width": 1024, "height": 1024}

    generator = CompositeGenerator(renderer=Renderer(), method="grabcut",
                                   out_dir=tmp_path, repo_root=ROOT, layout="deterministic")
    path = generator.generate(brief)
    assert path.is_file()
    record = (generator.records or [{}])[-1]
    assert record.get("layout", {}).get("kind") == "deterministic", record.get("layout")
    assert record.get("product_quad"), "the packaging route must record where the panel is"
    assert record.get("identity_verdict") == "quad"


@pytest.mark.parametrize("bad", ["auto", "", "anything"])
def test_an_unknown_layout_is_refused(bad):
    from seller_tester.generators import CompositeGenerator

    with pytest.raises(ValueError):
        CompositeGenerator(renderer=object(), layout=bad)
