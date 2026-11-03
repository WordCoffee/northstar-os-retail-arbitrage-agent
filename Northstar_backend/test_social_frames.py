"""Still placements: social frames and listing images.

The listing rubric used to flag a text-free main image as `copy_not_readable` -
a correct main image could never pass. That regression is pinned here, along
with the frame OCR and safe-box checks.
"""
from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

import ad_formats
import asset_rubric
import social_frames as sf


def _product() -> Image.Image:
    img = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(150, 80), (450, 80), (470, 820), (130, 820)], fill=(213, 167, 122, 255))
    return img


def _listing(colour=(255, 255, 255), margin=72) -> Image.Image:
    img = Image.new("RGB", (1024, 1024), colour)
    ImageDraw.Draw(img).rectangle([margin, margin, 1024 - margin, 1024 - margin],
                                  fill=(213, 167, 122))
    return img


def test_every_placement_declares_a_canvas_and_safe_zones():
    for key, row in ad_formats.PLACEMENTS.items():
        canvas = ad_formats.FORMATS[row["canvas"]]
        assert canvas["width"] % 8 == 0 and canvas["height"] % 8 == 0
        z = row["safe_zones"]
        assert 0 <= z["top_pct"] < 100 and 0 <= z["bottom_pct"] < 100
        assert 0 <= z["left_pct"] < 100 and 0 <= z["right_pct"] < 100
        assert "verified" in row and "source" in row


def test_a_no_text_placement_refuses_copy():
    with pytest.raises(ValueError, match="placement_refuses_copy"):
        sf.render_social_frame(_product(), placement="amazon-main",
                               headline="LION'S MANE")


def test_social_frame_copy_is_inside_the_safe_area_and_readable():
    for placement in ("meta-feed", "tiktok"):
        frame = sf.render_social_frame(_product(), placement=placement,
                                       headline="LION'S MANE",
                                       subline="MUSHROOM POWDER", cta="SHOP NOW")
        assert frame["inside_safe_area"] is True
        assert frame["contrast"]["headline"] >= 4.5
        assert frame["contrast"]["cta"] >= 4.5
        checked = sf.check_frame(frame, expected_headline="LION'S MANE",
                                 expected_cta="SHOP NOW")
        assert checked["ok"] is True, checked
        assert checked["headline_hit_ratio"] >= 0.5
        assert checked["cta_hit_ratio"] >= 0.5


def test_the_listing_prompt_pack_is_text_safe():
    pack = sf.listing_prompt_pack()
    assert {s["id"] for s in pack["styles"]} == {
        "white-bg", "lifestyle", "flat-lay", "macro", "scale-shot"}
    for style in pack["styles"]:
        assert style["text_safe"] is True
        assert not any(ch.isdigit() for ch in style["prompt"])


def test_a_text_free_listing_image_passes_the_rubric():
    scored = asset_rubric.score_listing(_png(_listing()))
    assert "copy_not_readable" not in scored["defects"], scored
    assert scored["verdict"] == "pass", scored


def test_a_grey_background_is_refused():
    gate = sf.listing_gate(_listing(colour=(200, 200, 200)))
    assert gate["ok"] is False
    assert "listing_rubric_pass" in gate["reason"]


def test_lettering_on_a_main_image_is_refused():
    img = _listing()
    d = ImageDraw.Draw(img)
    from PIL import ImageFont
    from pathlib import Path
    font = ImageFont.truetype(str(Path(__file__).resolve().parent / "assets" / "fonts"
                                   / "Anton.ttf"), 180)
    d.text((200, 430), "SALE", font=font, fill=(10, 10, 10))
    gate = sf.listing_gate(img)
    assert gate["ok"] is False
    assert "text_free" in gate["reason"]


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
