"""Label mode: the model draws an unlettered body, the pipeline composes the lettering.

Measured 2026-11-11 by the local judge: the diffusion model spells "MOGGARA" for "MOGRA
ORGANICS" and "AOW" for "Word Coffee". `label_warp` composes and warps the label deterministically,
but it needs (a) a body prompt with no lettering in it and (b) the label's own fields. These tests
hold both halves of that contract, plus the catalogue data that makes it real.
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for extra in (str(ROOT / "tools"), str(ROOT / "Northstar_backend")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from seller_tester.scene_render import full_prompt  # noqa: E402
from seller_tester import label_warp  # noqa: E402


def test_a_warp_brief_is_prompted_for_an_unlettered_body():
    brief = {"label_mode": "warp", "body_prompt": "a plain matte green pouch, no lettering",
             "prompt": "a pouch reading MOGRA ORGANICS"}
    assert full_prompt(brief) == "a plain matte green pouch, no lettering"


def test_a_warp_brief_without_a_body_prompt_is_refused_not_silently_double_lettered():
    with pytest.raises(ValueError) as exc:
        full_prompt({"label_mode": "warp", "prompt": "a pouch reading MOGRA ORGANICS"})
    assert "body_prompt" in str(exc.value)


def test_a_brief_without_label_mode_still_uses_its_prompt():
    brief = {"prompt": "a pouch reading MOGRA ORGANICS"}
    assert full_prompt(brief) == "a pouch reading MOGRA ORGANICS"


def test_the_label_panel_carries_the_briefs_own_words():
    brief = {"label": {"brand": "Mogra Organics",
                       "product": "Organic Lion's Mane Mushroom Powder",
                       "weight": "6 oz (170 g)", "lines": []}}
    panel = Image.open(BytesIO(label_warp.compose_label(brief))).convert("L")
    import numpy as np

    ink = (np.asarray(panel) < 128).mean()
    assert ink > 0.02, "the label panel is blank: nothing would be printed on the product"


def test_the_label_panel_is_deterministic():
    brief = {"label": {"brand": "Word Coffee", "product": "For Mom",
                       "lines": ["Empowering Moms, One Message at a Time"]}}
    assert label_warp.compose_label(brief) == label_warp.compose_label(brief)


def test_every_catalogue_warp_brief_has_the_fields_the_warp_needs():
    payload = json.loads((ROOT / "ty" / "seller_briefs_heldout_modes.json")
                         .read_text(encoding="utf-8"))
    warped = [b for b in payload["briefs"] if str(b.get("label_mode") or "") == "warp"]
    assert warped, "no brief uses the label warp: the lettering is back on the model"
    for brief in warped:
        label = brief.get("label") or {}
        assert label.get("brand"), f"{brief['id']}: no brand to print"
        assert label.get("product"), f"{brief['id']}: no product line to print"
        assert brief.get("body_prompt"), f"{brief['id']}: no unlettered body prompt"
        lowered = brief["body_prompt"].lower()
        for forbidden in ("reading ", "printed ", "the words "):
            assert forbidden not in lowered, (
                f"{brief['id']}: the body prompt still asks for lettering ({forbidden!r})")


def test_the_product_name_is_wrapped_not_truncated():
    """`line[:28]` printed "ORGANIC LION'S MANE MUSHROOM P" and the judge read the missing word.

    A label that states the wrong copy is worse than a label that is hard to read: one is a
    defect in the product, the other is a defect in the photograph.
    """
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (900, 1200)))
    blocks = label_warp._fit_lines(draw, "ORGANIC LION'S MANE MUSHROOM POWDER",
                                   max_width=756, start_size=64)
    joined = " ".join(text for text, _ in blocks)
    assert joined == "ORGANIC LION'S MANE MUSHROOM POWDER", f"copy was lost: {joined!r}"
    assert len(blocks) >= 2, "a 36-character block at 64 pt does not fit one 756 px line"


def test_the_tagline_survives_the_wrap():
    from PIL import Image, ImageDraw

    draw = ImageDraw.Draw(Image.new("RGB", (900, 1200)))
    text = "Empowering Moms, One Message at a Time"
    blocks = label_warp._fit_lines(draw, text, max_width=756, start_size=44)
    assert " ".join(t for t, _ in blocks) == text
    assert all(size <= 44 for _, size in blocks)


def test_the_panel_gets_darker_when_the_long_name_is_printed_in_full():
    import numpy as np

    short = {"label": {"brand": "Mogra Organics", "product": "Organic Lion's Mane"}}
    long_ = {"label": {"brand": "Mogra Organics",
                       "product": "Organic Lion's Mane Mushroom Powder"}}
    a = np.asarray(Image.open(BytesIO(label_warp.compose_label(short))).convert("L"))
    b = np.asarray(Image.open(BytesIO(label_warp.compose_label(long_))).convert("L"))
    assert (b < 128).sum() > (a < 128).sum(), "the longer copy must actually be printed"
