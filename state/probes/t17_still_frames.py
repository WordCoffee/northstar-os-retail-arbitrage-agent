"""Contract: social copy is placed inside the UI-safe area and can be read.

Two still surfaces get the same treatment as the video: a declared placement,
measured boxes, and an OCR/contrast check. The listing pack is proven text-safe
and the listing gate refuses a main image with lettering.

No model call: the product picture is synthetic; the placement and the checks
are what is under test.
"""
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image, ImageDraw  # noqa: E402

import social_frames as sf  # noqa: E402


def _product() -> Image.Image:
    img = Image.new("RGBA", (600, 900), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(150, 80), (450, 80), (470, 820), (130, 820)], fill=(213, 167, 122, 255))
    d.rectangle([150, 80, 450, 130], fill=(190, 146, 104, 255))
    return img


def main() -> int:
    product = _product()
    for placement in ("meta-feed", "tiktok", "sponsored-brand"):
        frame = sf.render_social_frame(
            product, placement=placement, headline="LION'S MANE",
            subline="MUSHROOM POWDER", cta="SHOP NOW")
        checked = sf.check_frame(frame, expected_headline="LION'S MANE",
                                 expected_cta="SHOP NOW")
        print(f"{placement}: {frame['canvas']} boxes={frame['boxes']} "
              f"contrast={frame['contrast']} ocr={checked['words']}")
        assert frame["canvas"] == list(
            (__import__("ad_formats").FORMATS[__import__("ad_formats").PLACEMENTS[placement]["canvas"]]["width"],
             __import__("ad_formats").FORMATS[__import__("ad_formats").PLACEMENTS[placement]["canvas"]]["height"]))
        assert frame["inside_safe_area"] is True, frame["safe_zone"]
        assert checked["ok"] is True, checked
        assert checked["headline_hit_ratio"] >= 0.5, checked
        assert checked["cta_hit_ratio"] >= 0.5, checked

    pack = sf.listing_prompt_pack()
    assert len(pack["styles"]) == 5, pack
    for style in pack["styles"]:
        assert style["text_safe"] is True
        assert not any(ch.isdigit() for ch in style["prompt"])
    print("listing styles:", [s["id"] for s in pack["styles"]])

    white = Image.new("RGB", (1024, 1024), (255, 255, 255))
    d = ImageDraw.Draw(white)
    d.rectangle([72, 72, 952, 952], fill=(213, 167, 122))
    good = sf.listing_gate(white)
    print("listing white:", good["checks"], good["score"]["score"], good["score"]["defects"])
    assert good["ok"] is True, good

    grey = Image.new("RGB", (1024, 1024), (200, 200, 200))
    d = ImageDraw.Draw(grey)
    d.rectangle([72, 72, 952, 952], fill=(213, 167, 122))
    bad = sf.listing_gate(grey)
    print("listing grey:", bad["checks"], bad["reason"])
    assert bad["ok"] is False
    assert "listing_rubric_pass" in bad["reason"]

    lettered = white.copy()
    d = ImageDraw.Draw(lettered)
    from PIL import ImageFont
    f = ImageFont.truetype(str(ROOT / "Northstar_backend" / "assets" / "fonts" / "Anton.ttf"), 180)
    d.text((200, 430), "SALE", font=f, fill=(10, 10, 10))
    typed = sf.listing_gate(lettered)
    print("listing lettered:", typed["checks"], typed["reason"])
    assert typed["ok"] is False
    assert "text_free" in typed["reason"]
    print("t17 still frames: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
