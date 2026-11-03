"""Designed label artwork for a supplement pouch — front and back.

This is the vector-text half of a product picture: FLUX supplies the photograph
of the package, never the lettering; these panels are drawn at print resolution
with real fonts and exact spelling, then warped onto the measured face by
`mockup_compositor.composite_panel_onto_quad`.

Nothing here invents a claim. There is no organic seal, no "FDA approved" and no
allergen badge unless the design dict explicitly says the brand holds one. The
files carry the draft note in their own margin so they cannot be mistaken for a
released label. Nutrition values and the UPC are supplied by the caller; the
`MOGRA_LIONS_MANE` defaults below are the owner's stated copy and are still
marked DRAFT for verification before print.

Pure PIL. No provider call, no network, no cost.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont

BASE_SIZE = (1200, 1600)
DRAFT_MARGIN = 44
DPI = 300

INK = (23, 23, 23)
KRAFT = (213, 167, 122)
OLIVE = (157, 186, 139)
IVORY = (245, 238, 226)
GOLD = (201, 162, 39)
PAPER = (247, 243, 235)
WHITE = (255, 255, 255)

FONTS = Path(r"C:\Windows\Fonts")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / name
    if not path.is_file():
        raise ValueError(f"label font missing: {path}")
    return ImageFont.truetype(str(path), max(6, int(size)))


def _serif(size: int) -> ImageFont.FreeTypeFont:
    return _font("georgia.ttf", size)


def _serif_bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("georgiab.ttf", size)


def _sans(size: int) -> ImageFont.FreeTypeFont:
    return _font("segoeui.ttf", size)


def _sans_bold(size: int) -> ImageFont.FreeTypeFont:
    return _font("segoeuib.ttf", size)


def _tracked(d: ImageDraw.ImageDraw, xy: Tuple[float, float], text: str, f,
             fill, tracking: float = 0.0) -> None:
    """Draw letter-spaced text centred on xy[0]."""
    if not tracking:
        w = d.textlength(text, font=f)
        d.text((xy[0] - w / 2, xy[1]), text, font=f, fill=fill)
        return
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = xy[0] - total / 2
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=f, fill=fill)
        x += w + tracking


def _wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: float) -> list:
    lines, line = [], ""
    for word in str(text).split():
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=f) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _mushroom_glyph(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill) -> None:
    """A lined lion's-mane cap + stem. Original geometry, no copied art."""
    d.arc([cx - r, cy - r * 0.72, cx + r, cy + r * 0.62], 180, 360, fill=fill, width=6)
    d.line([(cx - r, cy - r * 0.05), (cx + r, cy - r * 0.05)], fill=fill, width=6)
    for i in range(-4, 5):
        x = cx + i * (r / 5.2)
        d.line([(x, cy - r * 0.05), (x, cy + r * 0.42)], fill=fill, width=4)
    d.line([(cx - r * 0.16, cy + r * 0.30), (cx - r * 0.13, cy + r * 0.95)], fill=fill, width=7)
    d.line([(cx + r * 0.16, cy + r * 0.30), (cx + r * 0.13, cy + r * 0.95)], fill=fill, width=7)


# ── the design ──────────────────────────────────────────────────────────────

MOGRA_LIONS_MANE: Dict[str, Any] = {
    "brand": "MOGRA",
    "brand_suffix": "ORGANICS",
    "product": "LION'S MANE",
    "subtitle": "MUSHROOM POWDER",
    "latin": "HERICIUM ERINACEUS  ·  FRUITING BODY",
    "claim_main": "100% PURE  ·  NO FILLERS",
    "claim_sub": "ONE INGREDIENT",
    "form": "DIETARY SUPPLEMENT",
    "net_weight": "6 oz (170 g)",
    "net_weight_line": "NET WT. 6 oz (170 g)",
    "servings": "POWDER  ·  85 SERVINGS",
    "company": "DISTRIBUTED BY T2 HOLDINGS LLC",
    "draft_note": "DRAFT  ·  VERIFY BEFORE PRINT",
    "back_draft_note": "DRAFT  ·  VERIFY NUTRITION AND UPC BEFORE PRINT",
    "supplement_facts": {
        "title": "Supplement Facts",
        "servings_per_container": "Servings per container  85",
        "serving_size": "Serving size  1 tsp (2 g)",
        "amount_heading": "Amount per serving",
        "rows": [["Lion's Mane (Hericium erinaceus) fruiting body powder", "2,000 mg"]],
        "daily_value_note": "† Daily Value not established.",
        "other_ingredients": "Other ingredients: none.",
    },
    "suggested_use": (
        "Mix one teaspoon (2 g) into water, coffee, tea or a smoothie once daily. "
        "Start with half a teaspoon if you are new to functional mushrooms."),
    "caution": (
        "Consult a physician before use if you are pregnant, nursing, taking "
        "medication or have a medical condition. Keep out of reach of children. "
        "Do not use if the seal is broken. This product is not intended to "
        "diagnose, treat, cure or prevent any disease."),
    "storage": (
        "Store in a cool, dry place, away from direct sunlight. Reseal after "
        "opening and use within 60 days."),
    "about_title": "ABOUT LION'S MANE",
    "about_text": (
        "Hericium erinaceus, known as lion's mane, is a woodland fungus long used "
        "in traditional cooking and herbal practice. This powder is the dried "
        "fruiting body, milled fine and unsweetened. It dissolves best in warm "
        "liquids and has a mild, savoury flavour that disappears in coffee or a "
        "smoothie."),
    "lot_code": "LOT  LM-0000",
    "best_by": "BEST BY  00/0000",
    "barcode_digits": "8 50000 00000 4",
    "barcode_note": "UPC (placeholder)",
    "palette": {"ink": INK, "kraft": KRAFT, "olive": OLIVE, "ivory": IVORY,
                "gold": GOLD, "paper": PAPER},
}


def design_for(product: str = "mogra-lions-mane") -> Dict[str, Any]:
    """A copy of the declared design; callers may edit it without side effects."""
    if product not in ("mogra-lions-mane", "mogra_lions_mane"):
        raise ValueError(f"unknown label design {product!r}")
    return copy.deepcopy(MOGRA_LIONS_MANE)


def _new_canvas(design: Dict[str, Any]) -> Tuple[Image.Image, ImageDraw.ImageDraw]:
    palette = design.get("palette") or {}
    img = Image.new("RGB", BASE_SIZE, palette.get("paper", PAPER))
    return img, ImageDraw.Draw(img)


def front_panel(design: Optional[Dict[str, Any]] = None,
                size: Optional[Sequence[int]] = None) -> Image.Image:
    """Front-of-pack artwork at 1200x1600 (or the requested size, resampled)."""
    dsn = copy.deepcopy(design or MOGRA_LIONS_MANE)
    W, H = BASE_SIZE
    MARGIN = DRAFT_MARGIN
    ink = tuple(dsn.get("palette", {}).get("ink", INK))
    kraft = tuple(dsn.get("palette", {}).get("kraft", KRAFT))
    olive = tuple(dsn.get("palette", {}).get("olive", OLIVE))
    ivory = tuple(dsn.get("palette", {}).get("ivory", IVORY))
    gold = tuple(dsn.get("palette", {}).get("gold", GOLD))

    img, d = _new_canvas(dsn)

    # Frame: a thin gold keyline inset from the trim so nothing sits on the cut.
    d.rectangle([MARGIN - 18, MARGIN - 18, W - MARGIN + 18, H - MARGIN + 18],
                outline=gold, width=3)

    _tracked(d, (W / 2, 92), dsn["brand"], _serif_bold(96), ink, tracking=14)
    _tracked(d, (W / 2, 206), " ".join(dsn["brand_suffix"].upper()), _sans(30),
             (70, 70, 70), tracking=8)
    d.line([(W / 2 - 180, 262), (W / 2 + 180, 262)], fill=gold, width=3)

    _mushroom_glyph(d, W / 2, 430, 118, ink)
    d.ellipse([W / 2 - 190, 300, W / 2 + 190, 680], outline=olive, width=4)

    # Product name: shrink to fit the trim rather than run off it.
    title = dsn["product"].upper()
    title_px = 132
    while title_px > 40:
        f = _serif_bold(title_px)
        if d.textlength(title, font=f) + 4 * max(0, len(title) - 1) <= W - 2 * MARGIN - 20:
            break
        title_px -= 4
    _tracked(d, (W / 2, 742), title, _serif_bold(title_px), ink, tracking=4)
    _tracked(d, (W / 2, 902), dsn["subtitle"].upper(), _sans(44), (52, 52, 52), tracking=10)
    d.line([(W / 2 - 260, 976), (W / 2 + 260, 976)], fill=ink, width=2)
    _tracked(d, (W / 2, 1000), dsn["latin"].upper(), _sans(26), (90, 90, 90), tracking=4)

    strip = [MARGIN, 1088, W - MARGIN, 1214]
    d.rectangle(strip, fill=ink)
    _tracked(d, (W / 2, 1112), dsn["claim_main"].upper(), _sans_bold(36), ivory, tracking=7)
    _tracked(d, (W / 2, 1166), dsn["claim_sub"].upper(), _sans(24), kraft, tracking=9)

    _tracked(d, (W / 2, 1258), dsn["form"].upper(), _sans(26), (80, 80, 80), tracking=10)
    _tracked(d, (W / 2, 1310), dsn["net_weight_line"], _serif_bold(56), ink, tracking=2)
    _tracked(d, (W / 2, 1386), dsn["servings"].upper(), _sans(24), (95, 95, 95), tracking=6)

    d.line([(W / 2 - 300, 1452), (W / 2 + 300, 1452)], fill=gold, width=2)
    _tracked(d, (W / 2, 1472), dsn["company"].upper(), _sans(22), (90, 90, 90), tracking=5)
    _tracked(d, (W / 2, 1520), dsn["draft_note"].upper(), _sans(18), (150, 120, 90), tracking=4)

    if size is not None:
        img = img.resize((int(size[0]), int(size[1])), Image.LANCZOS)
    return img


def _supplement_panel(d: ImageDraw.ImageDraw, facts: Dict[str, Any], x0: int,
                      y0: int, w: int) -> int:
    """Draw the bordered Supplement Facts panel; returns the y below it."""
    f_title = _sans_bold(54)
    f_head = _sans_bold(26)
    f_body = _sans(26)
    f_small = _sans(21)
    pad = 18
    box_top = y0 - 10

    d.text((x0, y0), facts.get("title", "Supplement Facts"), font=f_title, fill=INK)
    y = y0 + 74
    d.text((x0, y), facts["servings_per_container"], font=f_body, fill=INK)
    y += 34
    d.text((x0, y), facts["serving_size"], font=f_body, fill=INK)
    y += 40
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=6)
    y += 8
    d.text((x0, y), facts.get("amount_heading", "Amount per serving"), font=f_head, fill=INK)
    first_value = str((facts.get("rows") or [["", ""]])[0][1])
    d.text((x0 + w - d.textlength(first_value, font=f_head) - 96, y), first_value,
           font=f_head, fill=INK)
    d.text((x0 + w - 88, y), "% DV", font=f_head, fill=INK)
    y += 34
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=2)
    y += 10

    for label, value in facts.get("rows") or []:
        lines = _wrap(d, str(label), f_body, w - 150)
        start = y
        for line in lines:
            d.text((x0, y), line, font=f_body, fill=INK)
            y += 30
        d.text((x0 + w - d.textlength(str(value), font=f_body) - 96, start),
               str(value), font=f_body, fill=INK)
        d.text((x0 + w - 26, start), "†", font=f_body, fill=INK)
        y += 6
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=6)
    y += 12
    for line in _wrap(d, facts.get("daily_value_note", ""), f_small, w):
        d.text((x0, y), line, font=f_small, fill=INK)
        y += 26
    y += 6
    d.text((x0, y), facts.get("other_ingredients", ""), font=f_body, fill=INK)
    y += 30
    box_bottom = y + 16
    d.rectangle([x0 - pad, box_top, x0 + w + pad, box_bottom], outline=INK, width=8)
    return box_bottom + 30


def back_panel(design: Optional[Dict[str, Any]] = None,
               size: Optional[Sequence[int]] = None) -> Image.Image:
    """Back-of-pack artwork with a real Supplement Facts block."""
    dsn = copy.deepcopy(design or MOGRA_LIONS_MANE)
    W, H = BASE_SIZE
    MARGIN = DRAFT_MARGIN
    ink = tuple(dsn.get("palette", {}).get("ink", INK))
    gold = tuple(dsn.get("palette", {}).get("gold", GOLD))

    img, d = _new_canvas(dsn)
    d.rectangle([MARGIN - 18, MARGIN - 18, W - MARGIN + 18, H - MARGIN + 18],
                outline=gold, width=3)

    _tracked(d, (W / 2, 80), f"{dsn['brand']} {dsn['brand_suffix']}".upper(),
             _serif_bold(48), ink, tracking=6)
    d.line([(W / 2 - 190, 152), (W / 2 + 190, 152)], fill=gold, width=3)
    # The net weight is part of the legal panel; it appears on the back too so a
    # rear product picture can be checked for it.
    _tracked(d, (W / 2, 166), str(dsn.get("net_weight_line") or "").upper(),
             _serif_bold(40), ink, tracking=2)

    y = _supplement_panel(d, dsn["supplement_facts"], MARGIN + 20, 250,
                          W - 2 * MARGIN - 40)

    y += 6
    d.text((MARGIN + 20, y), "SUGGESTED USE", font=_sans_bold(24), fill=ink)
    y += 36
    for line in _wrap(d, dsn["suggested_use"], _sans(24), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=_sans(24), fill=ink)
        y += 30

    y += 16
    d.text((MARGIN + 20, y), "CAUTION", font=_sans_bold(24), fill=ink)
    y += 36
    for line in _wrap(d, dsn["caution"], _sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=_sans(21), fill=ink)
        y += 27

    y += 14
    for line in _wrap(d, dsn["storage"], _sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=_sans(21), fill=ink)
        y += 27

    y += 24
    d.line([(MARGIN + 20, y), (W - MARGIN - 20, y)], fill=gold, width=2)
    y += 22
    d.text((MARGIN + 20, y), dsn["about_title"].upper(), font=_sans_bold(24), fill=ink)
    y += 36
    for line in _wrap(d, dsn["about_text"], _sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=_sans(21), fill=ink)
        y += 27

    y += 24
    d.rectangle([MARGIN + 20, y, MARGIN + 470, y + 96], outline=(170, 170, 170), width=2)
    d.text((MARGIN + 34, y + 14), dsn["lot_code"], font=_sans(20), fill=ink)
    d.text((MARGIN + 34, y + 48), dsn["best_by"], font=_sans(20), fill=ink)

    by = H - 300
    d.rectangle([MARGIN + 20, by - 16, W - MARGIN - 20, by + 158],
                outline=(180, 180, 180), width=2)
    d.text((MARGIN + 34, by), dsn["barcode_note"], font=_sans(18), fill=(110, 110, 110))
    bars = [2, 1, 3, 1, 1, 2, 2, 1, 1, 3, 1, 2, 1, 1, 2, 3, 1, 1, 2, 1, 3, 1, 2, 2, 1, 1, 3, 2]
    x = MARGIN + 34
    for i, bw in enumerate(bars):
        if i % 2 == 0:
            d.rectangle([x, by + 34, x + bw * 4, by + 110], fill=ink)
        x += bw * 4 + 2
    _tracked(d, (W / 2 + 150, by + 118), dsn["barcode_digits"], _sans(22), ink, tracking=4)

    _tracked(d, (W / 2, H - 96), dsn["back_draft_note"].upper(), _sans(18),
             (150, 120, 90), tracking=3)

    if size is not None:
        img = img.resize((int(size[0]), int(size[1])), Image.LANCZOS)
    return img


def panels(design: Optional[Dict[str, Any]] = None) -> Dict[str, Image.Image]:
    return {"front": front_panel(design), "back": back_panel(design)}


def manifest(design: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    dsn = design or MOGRA_LIONS_MANE
    return {
        "brand": dsn["brand"],
        "brand_suffix": dsn["brand_suffix"],
        "product": dsn["product"],
        "net_weight": dsn["net_weight"],
        "format": "stand-up pouch, front and back panels",
        "size_px": list(BASE_SIZE),
        "dpi": DPI,
        "trim_margin_px": DRAFT_MARGIN,
        "status": "DRAFT - nutrition values and UPC must be verified before print",
        "claims": {"organic_seal": False, "fda": False, "allergen_badge": False,
                   "note": "no certification is claimed that the brand has not got"},
    }


__all__ = ["MOGRA_LIONS_MANE", "design_for", "front_panel", "back_panel",
           "panels", "manifest", "BASE_SIZE", "DPI"]
