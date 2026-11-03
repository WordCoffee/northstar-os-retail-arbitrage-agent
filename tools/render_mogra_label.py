"""Render Mogra Organics lion's mane pouch label art: front and back.

A print-shop deliverable, not a diffusion guess. The point of the split is the one
this repo already proved: FLUX gives the photograph, typography is vector-sharp
because it is drawn here, never generated. The label is 1200x1600 px at 300 dpi
with a 44 px trim margin, so a die-cut leaflet or the flat face of a 6 oz pouch
carries it without re-keying anything.

Nothing here claims a certification the brand has not got: no organic seal, no
"FDA approved", no allergen-free badge. The supplement panel carries the values
you gave (one ingredient, 2 g a serving) and the standard disclaimer, and the file
says DRAFT in its own margin so it cannot be mistaken for a released label.

    python tools/render_mogra_label.py --out renders/mogra_lions_mane
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 1600
MARGIN = 44
DPI = 300

INK = (23, 23, 23)
KRAFT = (213, 167, 122)
OLIVE = (157, 186, 139)
IVORY = (245, 238, 226)
GOLD = (201, 162, 39)
PAPER = (247, 243, 235)          # label stock
WHITE = (255, 255, 255)

FONTS = Path(r"C:\Windows\Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    path = FONTS / name
    if not path.is_file():
        raise SystemExit(f"missing font: {path}")
    return ImageFont.truetype(str(path), size)


def serif(size: int) -> ImageFont.FreeTypeFont:
    return font("georgia.ttf", size)


def serif_bold(size: int) -> ImageFont.FreeTypeFont:
    return font("georgiab.ttf", size)


def sans(size: int) -> ImageFont.FreeTypeFont:
    return font("segoeui.ttf", size)


def sans_bold(size: int) -> ImageFont.FreeTypeFont:
    return font("segoeuib.ttf", size)


def tracked(d: ImageDraw.ImageDraw, xy, text: str, f, fill, tracking: float = 0.0):
    """Draw text with letter spacing, centred on x when xy[0] is a centre."""
    if not tracking:
        w = d.textlength(text, font=f)
        d.text((xy[0] - w / 2, xy[1]), text, font=f, fill=fill)
        return
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    x = xy[0] - total / 2
    for ch, w in zip(text, widths):
        d.text((x, xy[1]), ch, font=f, fill=fill)
        x += w + tracking


def wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: float) -> list[str]:
    words, lines, line = text.split(), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=f) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def mushroom_glyph(d: ImageDraw.ImageDraw, cx: float, cy: float, r: float, fill):
    """A simple lined lion's-mane cap + stem. Original geometry, no copied art."""
    d.arc([cx - r, cy - r * 0.72, cx + r, cy + r * 0.62], 180, 360, fill=fill, width=6)
    d.line([(cx - r, cy - r * 0.05), (cx + r, cy - r * 0.05)], fill=fill, width=6)
    # hanging spines under the cap
    for i in range(-4, 5):
        x = cx + i * (r / 5.2)
        d.line([(x, cy - r * 0.05), (x, cy + r * 0.42)], fill=fill, width=4)
    d.line([(cx - r * 0.16, cy + r * 0.30), (cx - r * 0.13, cy + r * 0.95)], fill=fill, width=7)
    d.line([(cx + r * 0.16, cy + r * 0.30), (cx + r * 0.13, cy + r * 0.95)], fill=fill, width=7)


def base(colour=PAPER) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), colour)
    return img, ImageDraw.Draw(img)


def front() -> Image.Image:
    img, d = base(PAPER)

    # Frame: a thin gold keyline inset from the trim so nothing sits on the cut.
    d.rectangle([MARGIN - 18, MARGIN - 18, W - MARGIN + 18, H - MARGIN + 18],
                outline=GOLD, width=3)

    # Brand block
    tracked(d, (W / 2, 92), "MOGRA", serif_bold(96), INK, tracking=14)
    tracked(d, (W / 2, 206), "O R G A N I C S", sans(30), (70, 70, 70), tracking=8)
    d.line([(W / 2 - 180, 262), (W / 2 + 180, 262)], fill=GOLD, width=3)

    # Emblem
    mushroom_glyph(d, W / 2, 430, 118, INK)
    d.ellipse([W / 2 - 190, 300, W / 2 + 190, 680], outline=OLIVE, width=4)

    # Product
    tracked(d, (W / 2, 742), "LION'S MANE", serif_bold(132), INK, tracking=4)
    tracked(d, (W / 2, 902), "MUSHROOM POWDER", sans(44), (52, 52, 52), tracking=10)
    d.line([(W / 2 - 260, 976), (W / 2 + 260, 976)], fill=INK, width=2)
    tracked(d, (W / 2, 1000), "HERICIUM ERINACEUS  ·  FRUITING BODY", sans(26), (90, 90, 90), tracking=4)

    # Claim strip (factual, no certification implied)
    strip = [MARGIN, 1088, W - MARGIN, 1214]
    d.rectangle(strip, fill=INK)
    tracked(d, (W / 2, 1112), "100% PURE  ·  NO FILLERS", sans_bold(36), IVORY, tracking=7)
    tracked(d, (W / 2, 1166), "ONE INGREDIENT", sans(24), KRAFT, tracking=9)

    # Weight + form
    tracked(d, (W / 2, 1258), "DIETARY SUPPLEMENT", sans(26), (80, 80, 80), tracking=10)
    tracked(d, (W / 2, 1310), "NET WT. 6 oz (170 g)", serif_bold(56), INK, tracking=2)
    tracked(d, (W / 2, 1386), "POWDER  ·  85 SERVINGS", sans(24), (95, 95, 95), tracking=6)

    # Footer rule + draft mark (in the bleed margin, never on the trim)
    d.line([(W / 2 - 300, 1452), (W / 2 + 300, 1452)], fill=GOLD, width=2)
    tracked(d, (W / 2, 1472), "DISTRIBUTED BY T2 HOLDINGS LLC", sans(22), (90, 90, 90), tracking=5)
    tracked(d, (W / 2, 1520), "DRAFT  ·  VERIFY BEFORE PRINT", sans(18), (150, 120, 90), tracking=4)
    return img


def supplement_panel(d: ImageDraw.ImageDraw, x0: int, y0: int, w: int) -> int:
    """Draw the bordered Supplement Facts panel; returns the y below it."""
    f_title = sans_bold(54)
    f_head = sans_bold(26)
    f_body = sans(26)
    f_small = sans(21)

    # US supplement panels carry a heavy outer rule; the box is the label's anchor.
    # Drawn ONCE at the end so the rule hugs the content instead of leaving a band.
    pad = 18
    box_top = y0 - 10

    d.text((x0, y0), "Supplement Facts", font=f_title, fill=INK)
    y = y0 + 74
    d.text((x0, y), "Servings per container  85", font=f_body, fill=INK)
    y += 34
    d.text((x0, y), "Serving size  1 tsp (2 g)", font=f_body, fill=INK)
    y += 40
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=6)
    y += 8
    d.text((x0, y), "Amount per serving", font=f_head, fill=INK)
    amt = "2,000 mg"
    d.text((x0 + w - d.textlength(amt, font=f_head) - 96, y), amt, font=f_head, fill=INK)
    d.text((x0 + w - 88, y), "% DV", font=f_head, fill=INK)
    y += 34
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=2)
    y += 10

    for line in wrap(d, "Lion's Mane (Hericium erinaceus) fruiting body powder", f_body, w - 150):
        d.text((x0, y), line, font=f_body, fill=INK)
        y += 30
    d.text((x0 + w - d.textlength("2,000 mg", font=f_body) - 96, y - 30), "2,000 mg", font=f_body, fill=INK)
    d.text((x0 + w - 26, y - 30), "†", font=f_body, fill=INK)
    y += 6
    d.line([(x0, y), (x0 + w, y)], fill=INK, width=6)
    y += 12
    for line in wrap(d, "† Daily Value not established.", f_small, w):
        d.text((x0, y), line, font=f_small, fill=INK)
        y += 26
    y += 6
    d.text((x0, y), "Other ingredients: none.", font=f_body, fill=INK)
    y += 30
    box_bottom = y + 16
    d.rectangle([x0 - pad, box_top, x0 + w + pad, box_bottom], outline=INK, width=8)
    return box_bottom + 30


def back() -> Image.Image:
    img, d = base(PAPER)
    d.rectangle([MARGIN - 18, MARGIN - 18, W - MARGIN + 18, H - MARGIN + 18],
                outline=GOLD, width=3)

    tracked(d, (W / 2, 80), "MOGRA ORGANICS", serif_bold(48), INK, tracking=6)
    d.line([(W / 2 - 190, 152), (W / 2 + 190, 152)], fill=GOLD, width=3)

    y = supplement_panel(d, MARGIN + 20, 200, W - 2 * MARGIN - 40)

    # Directions
    d.text((MARGIN + 20, y), "SUGGESTED USE", font=sans_bold(24), fill=INK)
    y += 36
    for line in wrap(d, "Mix one teaspoon (2 g) into water, coffee, tea or a smoothie once "
                        "daily. Start with half a teaspoon if you are new to functional mushrooms.",
                     sans(24), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=sans(24), fill=INK)
        y += 30

    # Warnings
    y += 16
    d.text((MARGIN + 20, y), "CAUTION", font=sans_bold(24), fill=INK)
    y += 36
    for line in wrap(d, "Consult a physician before use if you are pregnant, nursing, taking "
                        "medication or have a medical condition. Keep out of reach of children. "
                        "Do not use if the seal is broken. This product is not intended to "
                        "diagnose, treat, cure or prevent any disease.", sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=sans(21), fill=INK)
        y += 27

    # Storage + lot block
    y += 14
    for line in wrap(d, "Store in a cool, dry place, away from direct sunlight. Reseal after "
                        "opening and use within 60 days.", sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=sans(21), fill=INK)
        y += 27

    # About block: fills the panel with facts, not decoration.
    y += 24
    d.line([(MARGIN + 20, y), (W - MARGIN - 20, y)], fill=GOLD, width=2)
    y += 22
    d.text((MARGIN + 20, y), "ABOUT LION'S MANE", font=sans_bold(24), fill=INK)
    y += 36
    for line in wrap(d, "Hericium erinaceus, known as lion's mane, is a woodland fungus long used in "
                        "traditional cooking and herbal practice. This powder is the dried fruiting "
                        "body, milled fine and unsweetened. It dissolves best in warm liquids and has "
                        "a mild, savoury flavour that disappears in coffee or a smoothie.",
                     sans(21), W - 2 * MARGIN - 40):
        d.text((MARGIN + 20, y), line, font=sans(21), fill=INK)
        y += 27

    # Lot / best-by block (placeholder values, clearly marked)
    y += 24
    d.rectangle([MARGIN + 20, y, MARGIN + 470, y + 96], outline=(170, 170, 170), width=2)
    d.text((MARGIN + 34, y + 14), "LOT  LM-0000", font=sans(20), fill=INK)
    d.text((MARGIN + 34, y + 48), "BEST BY  00/0000", font=sans(20), fill=INK)

    # Barcode block (Code128-style bars, placeholder digits)
    by = H - 300
    d.rectangle([MARGIN + 20, by - 16, W - MARGIN - 20, by + 158], outline=(180, 180, 180), width=2)
    d.text((MARGIN + 34, by), "UPC (placeholder)", font=sans(18), fill=(110, 110, 110))
    bars = [2, 1, 3, 1, 1, 2, 2, 1, 1, 3, 1, 2, 1, 1, 2, 3, 1, 1, 2, 1, 3, 1, 2, 2, 1, 1, 3, 2]
    x = MARGIN + 34
    for i, bw in enumerate(bars):
        if i % 2 == 0:
            d.rectangle([x, by + 34, x + bw * 4, by + 110], fill=INK)
        x += bw * 4 + 2
    tracked(d, (W / 2 + 150, by + 118), "8 50000 00000 4", sans(22), INK, tracking=4)

    # Draft mark in the bleed margin
    tracked(d, (W / 2, H - 96), "DRAFT  ·  VERIFY NUTRITION AND UPC BEFORE PRINT",
            sans(18), (150, 120, 90), tracking=3)
    return img


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path("renders") / "mogra_lions_mane"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    front_img, back_img = front(), back()
    paths = {}
    for name, img in (("front", front_img), ("back", back_img)):
        path = out / f"mogra_lions_mane_{name}_label.png"
        img.save(path, dpi=(DPI, DPI))
        paths[name] = str(path)

    manifest = {
        "brand": "Mogra Organics", "product": "Lion's Mane Mushroom Powder",
        "net_weight": "6 oz (170 g)", "format": "stand-up pouch, front and back panels",
        "size_px": [W, H], "dpi": DPI, "trim_margin_px": MARGIN,
        "palette": {"ink": INK, "kraft": KRAFT, "olive": OLIVE, "ivory": IVORY, "gold": GOLD},
        "files": paths,
        "status": "DRAFT - nutrition values and UPC must be verified before print",
        "claims": {"organic_seal": False, "fda": False, "allergen_badge": False,
                   "note": "no certification is claimed that the brand has not got"},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"files": paths, "size": [W, H], "dpi": DPI}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
