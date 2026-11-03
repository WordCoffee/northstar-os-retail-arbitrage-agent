"""Social frames and listing images: a placement, a box, a check.

Two still surfaces were missing a contract:

* **Social frames** (feed / story / Reels / TikTok / Shorts) had copy generation
  but no asset with the copy placed inside the area the platform's UI leaves
  visible. This module draws the product picture and the vector copy onto the
  placement canvas, returns the measured boxes, and OCRs the result.
* **Listing images** had rules (white background, 80-92% fill) but no
  systematised prompt pack and no gate. The pack below is text-safe by
  construction; the gate refuses a main image that carries lettering or fails
  the listing rubric.

Text is drawn, never diffused. The Amazon main-image rule is respected by
`text_allowed: False`, not by a hidden convention. No network, no model call.
"""
from __future__ import annotations

import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

import ad_formats
import asset_rubric
import text_fidelity

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

PALETTES: Dict[str, Dict[str, Tuple[int, int, int]]] = {
    "forest": {"ground": (31, 58, 46), "ink": (247, 243, 235), "accent": (201, 162, 39),
               "accent_ink": (23, 23, 23)},
    "bone": {"ground": (245, 238, 226), "ink": (28, 46, 38), "accent": (176, 141, 69),
             "accent_ink": (247, 243, 235)},
    "kraft": {"ground": (213, 167, 122), "ink": (28, 46, 38), "accent": (28, 46, 38),
              "accent_ink": (245, 238, 226)},
}

#: Text-safe listing prompts. Lower-case, no digits, no all-caps runs: the same
#: rules `text_fidelity.sanitize_brief_for_render` enforces, applied before the
#: prompt reaches a model. The main image is checked text-free after the render.
LISTING_STYLES: Dict[str, Dict[str, Any]] = {
    "white-bg": {
        "prompt": ("a single kraft stand-up pouch on a pure white seamless sweep, "
                   "centred, filling most of the frame, soft even studio light, no "
                   "props, photoreal commercial product photography, sharp focus"),
        "text_allowed": False,
    },
    "lifestyle": {
        "prompt": ("a kraft stand-up pouch on a pale kitchen counter beside a cup of "
                   "coffee, soft morning window light, shallow depth of field, "
                   "photoreal lifestyle product photography"),
        "text_allowed": True,
    },
    "flat-lay": {
        "prompt": ("a kraft stand-up pouch lying flat on a stone surface with a spoon "
                   "of mushroom powder beside it, shot from directly above, soft "
                   "diffused light, photoreal"),
        "text_allowed": True,
    },
    "macro": {
        "prompt": ("a macro photograph of the pouch seal and the fine powder texture, "
                   "neutral studio light, shallow depth of field, photoreal"),
        "text_allowed": True,
    },
    "scale-shot": {
        "prompt": ("a kraft stand-up pouch held in one hand for scale against a pale "
                   "wall, soft daylight, photoreal product photography"),
        "text_allowed": True,
    },
}


def _font(name: str, size: int, axes: Optional[Sequence[float]] = None
          ) -> ImageFont.FreeTypeFont:
    path = FONT_DIR / name
    font = ImageFont.truetype(str(path), max(8, int(size)))
    if axes is not None:
        try:
            font.set_variation_by_axes(list(axes))
        except Exception:  # noqa: BLE001 - a static font is still usable
            pass
    return font


def _luminance(rgb: Sequence[int]) -> float:
    def channel(v: float) -> float:
        c = float(v) / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    la, lb = _luminance(a), _luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def safe_box(width: int, height: int, placement: Dict[str, Any]) -> Dict[str, float]:
    z = placement.get("safe_zones") or {}
    left = width * float(z.get("left_pct", 0)) / 100.0
    right = width * (1 - float(z.get("right_pct", 0)) / 100.0)
    top = height * float(z.get("top_pct", 0)) / 100.0
    bottom = height * (1 - float(z.get("bottom_pct", 0)) / 100.0)
    return {"left": left, "right": right, "top": top, "bottom": bottom,
            "width": max(1.0, right - left), "height": max(1.0, bottom - top)}


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: float) -> List[str]:
    words, lines, line = str(text).split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render_social_frame(product: Image.Image, *, placement: str,
                        headline: str, subline: str = "", cta: str = "",
                        palette: str = "forest") -> Dict[str, Any]:
    """Draw a product picture and vector copy inside a placement's safe area."""
    if placement not in ad_formats.PLACEMENTS:
        raise ValueError(f"placement_unknown: {placement!r}; "
                         f"known: {sorted(ad_formats.PLACEMENTS)}")
    spec = ad_formats.PLACEMENTS[placement]
    canvas = ad_formats.FORMATS[spec["canvas"]]
    width, height = canvas["width"], canvas["height"]
    colours = PALETTES.get(palette) or PALETTES["forest"]
    safe = safe_box(width, height, spec)

    if not spec.get("text_allowed", True):
        if headline or subline or cta:
            raise ValueError(
                f"placement_refuses_copy: {placement} is a no-text placement "
                "(for amazon-main the main image may not carry lettering)")

    img = Image.new("RGB", (width, height), colours["ground"])
    d = ImageDraw.Draw(img)

    # ── text block: measured bottom-up so the CTA sits above the safe floor ──
    text_w = safe["width"]
    headline_px = max(30, int(height * 0.07))
    font_h = _font("PlayfairDisplay.ttf", headline_px, [700])
    lines = _wrap(d, headline, font_h, text_w)[:2]
    while lines and d.textlength(max(lines, key=len), font=font_h) > text_w and headline_px > 30:
        headline_px -= 4
        font_h = _font("PlayfairDisplay.ttf", headline_px, [700])
        lines = _wrap(d, headline, font_h, text_w)[:2]
    line_h = int(headline_px * 1.18)

    font_sub = _font("Inter.ttf", max(18, int(height * 0.026)), [14, 500])
    sub_lines = _wrap(d, subline, font_sub, text_w)[:2] if subline else []
    sub_h = int(height * 0.026 * 1.35) if sub_lines else 0
    cta_px = max(18, int(height * 0.024))
    font_cta = _font("Inter.ttf", cta_px, [14, 700])
    cta_h = int(cta_px * 2.1) if cta else 0
    gap = int(height * 0.018)

    bottom = safe["bottom"] - int(height * 0.01)
    cta_box = None
    if cta:
        pill_w = int(d.textlength(cta, font=font_cta)) + int(cta_px * 1.6)
        pill_w = min(int(text_w), max(pill_w, int(text_w * 0.34)))
        y1 = int(bottom)
        y0 = y1 - cta_h
        x0 = int(safe["left"])
        cta_box = [x0, y0, x0 + pill_w, y1]
        bottom = y0 - gap

    sub_box = None
    if sub_lines:
        y1 = int(bottom)
        y0 = y1 - sub_h * len(sub_lines)
        sub_box = [int(safe["left"]), y0, int(safe["right"]), y1]
        bottom = y0 - gap

    head_h = line_h * len(lines)
    head_y0 = int(bottom - head_h)
    head_box = [int(safe["left"]), head_y0, int(safe["right"]), int(bottom)]

    # ── product picture: the space above the copy, fitted without distortion ──
    product_top = int(safe["top"])
    product_bottom = max(product_top + 40, head_box[1] - gap)
    box_w, box_h = int(text_w), product_bottom - product_top
    art = product.convert("RGB")
    scale = min(box_w / max(1, art.width), box_h / max(1, art.height))
    pw, ph = max(1, int(art.width * scale)), max(1, int(art.height * scale))
    art = art.resize((pw, ph), Image.LANCZOS)
    px = int(safe["left"] + (text_w - pw) / 2)
    py = int(product_top + (box_h - ph) / 2)
    img.paste(art, (px, py))
    product_box = [px, py, px + pw, py + ph]

    # ── draw the copy ───────────────────────────────────────────────────────
    ink = colours["ink"]
    y = head_y0
    for line in lines:
        d.text((safe["left"], y), line, font=font_h, fill=ink)
        y += line_h
    if sub_box:
        y = sub_box[1]
        for line in sub_lines:
            d.text((safe["left"], y), line, font=font_sub, fill=ink)
            y += int(height * 0.026 * 1.35)
    if cta_box:
        d.rounded_rectangle(cta_box, radius=int(cta_h * 0.45),
                            fill=colours["accent"])
        tw = d.textlength(cta, font=font_cta)
        d.text((cta_box[0] + (cta_box[2] - cta_box[0] - tw) / 2,
                cta_box[1] + (cta_h - cta_px) / 2 - 2),
               cta, font=font_cta, fill=colours["accent_ink"])

    boxes = {"headline": head_box,
             "subline": sub_box,
             "cta": cta_box,
             "product": product_box}
    contrasts = {
        "headline": contrast_ratio(ink, colours["ground"]),
        "subline": contrast_ratio(ink, colours["ground"]),
        "cta": (contrast_ratio(colours["accent_ink"], colours["accent"])
                if cta else None),
    }
    inside = all(box is None or (box[0] >= safe["left"] - 1 and box[2] <= safe["right"] + 1
                                 and box[1] >= safe["top"] - 1 and box[3] <= safe["bottom"] + 1)
                 for box in boxes.values())
    return {
        "image": img,
        "placement": placement,
        "canvas": [width, height],
        "safe_zone": safe,
        "boxes": boxes,
        "contrast": contrasts,
        "inside_safe_area": inside,
        "compliance": {"verified": bool(spec.get("verified")),
                       "source": spec["source"]},
    }


def check_frame(frame: Dict[str, Any], *, expected_headline: str,
                expected_cta: str = "") -> Dict[str, Any]:
    """OCR the frame and check the boxes and contrast it was drawn with."""
    img: Image.Image = frame["image"]
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = text_fidelity.check_text_in_image(buf.getvalue())
    words = " ".join(result.get("words") or []).upper()

    def hit_ratio(text: str) -> float:
        expected = [w for w in re.findall(r"[A-Za-z']{3,}", text.upper())]
        if not expected:
            return 1.0
        hits = sum(1 for w in expected if w in words)
        return round(hits / len(expected), 3)

    headline_ratio = hit_ratio(expected_headline)
    cta_ratio = hit_ratio(expected_cta) if expected_cta else 1.0
    contrast_ok = (frame["contrast"]["headline"] >= 4.5
                   and (frame["contrast"]["cta"] is None or frame["contrast"]["cta"] >= 4.5))
    checks = {
        "ocr_available": result.get("status") == "ok",
        "headline_read": headline_ratio >= 0.5,
        "cta_read": cta_ratio >= 0.5,
        "inside_safe_area": bool(frame["inside_safe_area"]),
        "contrast_aa": contrast_ok,
    }
    failed = [k for k, ok in checks.items() if not ok]
    return {"ok": not failed, "checks": checks, "words": result.get("words"),
            "headline_hit_ratio": headline_ratio, "cta_hit_ratio": cta_ratio,
            "contrast": frame["contrast"],
            "reason": "" if not failed else "frame_contract_failed: " + ", ".join(failed)}


def listing_prompt_pack() -> Dict[str, Any]:
    """Text-safe prompts per listing style, each with the gate that follows it."""
    rows = []
    for key, row in LISTING_STYLES.items():
        prep = text_fidelity.sanitize_brief_for_render(row["prompt"])
        if prep["brief_empty"] or prep["expected_terms"]:
            raise ValueError(f"listing_prompt_not_text_safe: {key}")
        rows.append({"id": key, "prompt": row["prompt"],
                     "text_allowed": row["text_allowed"],
                     "gate": ("text_free + listing rubric" if not row["text_allowed"]
                              else "listing rubric"),
                     "text_safe": True})
    return {"styles": rows,
            "note": ("Prompts are lower-case art direction; the main image is OCR-checked "
                     "text-free and the listing rubric checks background purity and fill.")}


def listing_gate(image: Any) -> Dict[str, Any]:
    """Refuse a listing image that carries lettering or fails the listing rubric."""
    if isinstance(image, Image.Image):
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        payload = buf.getvalue()
    else:
        payload = bytes(image)
    scored = asset_rubric.score_listing(payload)
    text = text_fidelity.verify_asset_text(payload, brief=None, text_safe=True)
    verdict = text.get("verdict")
    checks = {
        "listing_rubric_pass": scored.get("verdict") == "pass",
        "text_free": verdict == "text_free",
        "ocr_available": (text.get("check") or {}).get("status") == "ok",
    }
    failed = [k for k, ok in checks.items() if not ok]
    return {"ok": not failed, "checks": checks, "score": scored,
            "text": text, "reason": "" if not failed else
            "listing_image_refused: " + ", ".join(failed)}


__all__ = ["render_social_frame", "check_frame", "safe_box", "contrast_ratio",
           "listing_prompt_pack", "listing_gate", "LISTING_STYLES", "PALETTES"]
