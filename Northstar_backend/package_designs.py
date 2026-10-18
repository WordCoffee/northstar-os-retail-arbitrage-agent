"""MOGRA design system — premium package concepts (5 bags + 5 canisters).

Every design renders TWO deliverables: a FRONT panel and a BACK panel at
300 dpi, mm-true scale. Bags: 130x210 mm front panel. Canisters: kraft-tube
wrap halves (front/back of the cylinder, unrolled at 120 mm tall).

Text is always composited with licensed fonts (Playfair/Inter, OFL); the logo
is the refined high-res master; mushroom engravings are extracted from the
model's raw render. Regulatory zones (Supplement Facts, QR/UPC, lot/best-by,
FDA disclaimer) are labelled placeholders - the required-data checklist ships
in BACK_LABEL_REQUIREMENTS.md inside the export pack.

Creative logo placements across the set: classic roundel, icon-only minimal,
crest arch, split band, off-edge seal, sticker badge, spine lockup, patch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFont

import dieline_art as da
from mockup_compositor import draw_cert_icon

DPI = 300
FONTS = Path(__file__).resolve().parent / "assets" / "fonts"

CREAM = (245, 238, 226)
KRAFT = (213, 167, 122)
OLIVE = (157, 186, 139)
IVORY = (245, 238, 226)
SAGE = (159, 169, 164)
FOREST = (37, 54, 40)
INK = (23, 23, 23)
GOLD_A = (196, 160, 74)
GOLD_B = (214, 158, 62)
CHARCOAL = (42, 42, 45)
WHITE = (255, 255, 255)
GREY = (140, 140, 140)

BAG_W, BAG_H = 130.0, 210.0
CAN_C, CAN_H, CAN_GLUE = 229.3, 120.0, 12.0          # circumference, height, glue tab
CAN_HALF = CAN_C / 2.0


# ── primitives ──────────────────────────────────────────────────────────────

def P(mm: float) -> int:
    return int(round(mm * DPI / 25.4))


def F(name: str, size_mm: float, axes=None):
    return da._font(name, max(8, P(size_mm)), axes)


def ctext(d, cx_mm, y_mm, text, f, fill, tracking_mm=0.0):
    da._clear_text(d, P(cx_mm), P(y_mm), text, f, fill, tracking=P(tracking_mm))


def ltext(d, x_mm, y_mm, text, f, fill):
    d.text((P(x_mm), P(y_mm)), text, font=f, fill=fill, anchor="lm")


def rtext(d, x_mm, y_mm, text, f, fill):
    d.text((P(x_mm), P(y_mm)), text, font=f, fill=fill, anchor="rm")


def rule(d, x0_mm, y_mm, x1_mm, color, width_mm=0.5):
    d.line([(P(x0_mm), P(y_mm)), (P(x1_mm), P(y_mm))], fill=tuple(color), width=max(2, P(width_mm)))


def roundel(canvas: Image.Image, logo: Image.Image, cx, cy, r, *, field=WHITE,
            ring=None, ring_w=0.7, logo_frac=0.72):
    rp = P(r)
    badge = Image.new("RGBA", (2 * rp + P(2), 2 * rp + P(2)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.ellipse([P(1), P(1), badge.width - P(1), badge.height - P(1)], fill=tuple(field) + (255,))
    lw = int(rp * 2 * logo_frac)
    lock = logo.resize((lw, max(2, int(lw * logo.height / logo.width))), Image.LANCZOS)
    badge.paste(lock, ((badge.width - lock.width) // 2, (badge.height - lock.height) // 2), lock)
    mask = Image.new("L", badge.size, 0)
    ImageDraw.Draw(mask).ellipse([P(1), P(1), badge.width - P(1), badge.height - P(1)], fill=255)
    badge.putalpha(ImageChops.multiply(badge.split()[3], mask))
    canvas.paste(badge, (P(cx) - rp - P(1), P(cy) - rp - P(1)), badge)
    if ring:
        ImageDraw.Draw(canvas).ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)],
                                       outline=tuple(ring), width=max(2, P(ring_w)))


def icon_row(d, cx, y, r_mm, gap_mm, ink, disc=CREAM):
    for i, kind in enumerate(("organic_sprout", "non_gmo", "gluten_free", "fruiting_body")):
        draw_cert_icon(d, kind, P(cx + (i - 1.5) * gap_mm), P(y), P(r_mm),
                       ink=ink, ring=ink, disc=disc, width=max(2, P(0.45)))


def icon_grid(d, cx, cy, r_mm, gap_x, gap_y, ink, disc=CREAM):
    pos = [(-gap_x / 2, -gap_y / 2), (gap_x / 2, -gap_y / 2),
           (-gap_x / 2, gap_y / 2), (gap_x / 2, gap_y / 2)]
    for kind, (dx, dy) in zip(("organic_sprout", "non_gmo", "gluten_free", "fruiting_body"), pos):
        draw_cert_icon(d, kind, P(cx + dx), P(cy + dy), P(r_mm),
                       ink=ink, ring=ink, disc=disc, width=max(2, P(0.45)))


def place_motif(canvas, motif, cx, cy, max_w, max_h):
    mw, mh = motif.size
    s = min(P(max_w) / mw, P(max_h) / mh)
    m = motif.resize((max(2, int(mw * s)), max(2, int(mh * s))), Image.LANCZOS)
    canvas.paste(m, (P(cx) - m.width // 2, P(cy) - m.height // 2), m)


def vtext(canvas, x_mm, y_mm, text, f, fill):
    """Rotated (reads bottom-to-top) text block pasted at (x, y) top-left."""
    tmp = Image.new("RGBA", (P(90), P(14)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((P(2), P(7)), text, font=f, fill=fill, anchor="lm")
    tmp = tmp.rotate(90, expand=True)
    canvas.paste(tmp, (P(x_mm), P(y_mm)), tmp)


def fit_size(name, base_mm, axes, text, max_w_mm):
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    size = base_mm
    while size > 2:
        f = F(name, size, axes)
        if d0.textlength(text, font=f) <= P(max_w_mm):
            return f
        size -= 0.25
    return F(name, size, axes)


# ── shared BACK template (regulatory layout; colours vary per design) ───────

def render_back(spec: Dict, W: float, H: float) -> Image.Image:
    ground = spec.get("ground_b", spec["ground"])
    ink = spec.get("ink_b", INK)
    img = Image.new("RGB", (P(W), P(H)), tuple(ground))
    d = ImageDraw.Draw(img)
    sx = H / 210.0                                   # scale against the 210mm reference
    tx, tw = W * 0.08, W * 0.84
    f_title = fit_size("PlayfairDisplay.ttf", 6.0 * sx, [700], spec["title"], tw)
    ltext(d, tx, 11 * sx, spec["title"], f_title, ink)
    f_sm = F("Inter.ttf", 2.7 * sx, [14, 400])
    for i, line in enumerate(spec["desc"]):
        ltext(d, tx, 22 * sx + i * 4.4 * sx, line, f_sm, ink)

    # Supplement Facts — reserved, white block with rules
    sf_w = min(65.0, W * 0.55)
    sf_h = min(110.0, H * 0.50) * (W / 130.0 if W < 130 else 1.0)
    sf_x = W - tx - sf_w
    sf_y = 37 * sx
    d.rectangle([P(sf_x), P(sf_y), P(sf_x + sf_w), P(sf_y + sf_h)], fill=WHITE)
    d.rectangle([P(sf_x), P(sf_y), P(sf_x + sf_w), P(sf_y + sf_h)], outline=(0, 0, 0), width=max(2, P(0.4)))
    ltext(d, sf_x + 2, sf_y + 5 * sx, "SUPPLEMENT FACTS", F("Inter.ttf", 3.1 * sx, [14, 700]), (0, 0, 0))
    ltext(d, sf_x + 2, sf_y + 10 * sx, "awaiting panel data (see requirements)",
          F("Inter.ttf", 2.0 * sx, [14, 400]), (110, 110, 110))
    rows = 8
    for i in range(rows):
        y = sf_y + (16 + i * 4.8) * sx
        if y < sf_y + sf_h - 4:
            rule(d, sf_x + 2, y, sf_x + sf_w - 2, (205, 205, 205), 0.2)

    # left column: usage / storage / origin / distributed / reseal
    f_body = F("Inter.ttf", 2.5 * sx, [14, 400])
    for i, line in enumerate(spec["back_lines"]):
        ltext(d, tx, 37 * sx + i * 4.2 * sx, line, f_body, ink)

    # QR + UPC reserved row
    qr = min(22.0, H * 0.16)
    qy = H * 0.805
    d.rectangle([P(tx), P(qy), P(tx + qr), P(qy + qr)], outline=(0, 0, 0), width=max(2, P(0.4)))
    ltext(d, tx + 1, qy + qr + 2.6, "QR (reserved)", F("Inter.ttf", 2.0 * sx, [14, 400]), (80, 80, 80))
    d.rectangle([P(tx + qr + 6), P(qy + 1), P(tx + qr + 6 + 50 * (qr / 22.0)), P(qy + qr - 2)],
                outline=(0, 0, 0), width=max(2, P(0.4)))
    ltext(d, tx + qr + 6, qy + qr + 2.6, "UPC (reserved)", F("Inter.ttf", 2.0 * sx, [14, 400]), (80, 80, 80))

    # lot / best-by print zone
    lz_x = W - tx - 30
    d.rectangle([P(lz_x), P(qy + 2), P(lz_x + 28), P(qy + 12)], outline=(120, 120, 120), width=max(1, P(0.3)))
    ltext(d, lz_x, qy + 15, "LOT / BEST BY", F("Inter.ttf", 1.9 * sx, [14, 400]), (100, 100, 100))
    ltext(d, lz_x, qy + 18, "(printed at fill)", F("Inter.ttf", 1.9 * sx, [14, 400]), (130, 130, 130))

    # FDA disclaimer
    f_dis = F("Inter.ttf", 2.0 * sx, [14, 400])
    ctext(d, W / 2, H - 11 * sx, "*These statements have not been evaluated by the FDA. This product", f_dis, ink)
    ctext(d, W / 2, H - 7 * sx, "is not intended to diagnose, treat, cure or prevent any disease.", f_dis, ink)
    return img


# ── BAG fronts (5) — 130 x 210 mm panels ───────────────────────────────────

def bag_01_kraft_classic(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), KRAFT)
    d = ImageDraw.Draw(img)
    roundel(img, logo, 65, 42, 30, field=WHITE, ring=GOLD_A, ring_w=0.7)
    ctext(d, 65, 84, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 8.2, [700], "ORGANIC LION'S MANE", 112), CREAM)
    ctext(d, 65, 95.5, "MUSHROOM POWDER", F("Inter.ttf", 3.4, [14, 640]), CREAM, tracking_mm=1.1)
    place_motif(img, motif, 65, 129, 52, 58)
    icon_row(d, 65, 161.7, 3.4, 9.5, INK)
    ctext(d, 65, 193.2, "6 oz (170 g)", F("Inter.ttf", 3.2, [14, 560]), CREAM)
    rule(d, 39, 193.2, 52, GOLD_A, 0.6)
    rule(d, 78, 193.2, 91, GOLD_A, 0.6)
    return img


def bag_02_ivory_minimal(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), IVORY)
    d = ImageDraw.Draw(img)
    roundel(img, logo, 20, 17, 11, field=WHITE, ring=None)
    f_t = fit_size("PlayfairDisplay.ttf", 10.5, [700], "ORGANIC LION'S MANE", 104)
    ctext(d, 65, 54, "ORGANIC LION'S MANE", f_t, FOREST)
    ctext(d, 65, 66, "MUSHROOM POWDER", F("Inter.ttf", 3.2, [14, 520]), FOREST, tracking_mm=1.6)
    rule(d, 25, 73, 105, SAGE, 0.4)
    place_motif(img, motif, 65, 122, 70, 78)
    icon_row(d, 65, 180, 3.3, 9.5, FOREST, disc=IVORY)
    ctext(d, 65, 197, "6 oz (170 g)", F("Inter.ttf", 3.0, [14, 520]), FOREST)
    return img


def bag_03_forest_apothecary(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), FOREST)
    d = ImageDraw.Draw(img)
    roundel(img, logo, 65, 40, 28, field=WHITE, ring=GOLD_A, ring_w=0.7)
    ctext(d, 65, 82, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 8.0, [700], "ORGANIC LION'S MANE", 112), CREAM)
    ctext(d, 65, 93, "MUSHROOM POWDER", F("Inter.ttf", 3.2, [14, 620]), GOLD_A, tracking_mm=1.4)
    from mockup_compositor import recolor
    place_motif(img, recolor(motif, GOLD_A), 65, 128, 50, 56)
    icon_row(d, 65, 162, 3.4, 9.5, CREAM, disc=FOREST)
    ctext(d, 65, 193.5, "6 oz (170 g)", F("Inter.ttf", 3.2, [14, 560]), CREAM)
    rule(d, 39, 193.5, 52, GOLD_A, 0.6)
    rule(d, 78, 193.5, 91, GOLD_A, 0.6)
    return img


def bag_04_split_band(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), IVORY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, P(136), P(BAG_W), P(BAG_H)], fill=FOREST)
    roundel(img, logo, 30, 36, 22, field=WHITE, ring=GOLD_B, ring_w=0.6)
    f_t = fit_size("PlayfairDisplay.ttf", 7.4, [700], "ORGANIC LION'S MANE", 68)
    rtext(d, 118, 30, "ORGANIC", f_t, FOREST)
    rtext(d, 118, 41, "LION'S MANE", f_t, FOREST)
    rtext(d, 118, 51, "MUSHROOM POWDER", F("Inter.ttf", 2.8, [14, 520]), FOREST, )
    place_motif(img, motif, 65, 96, 56, 62)
    rule(d, 12, 76, 118, SAGE, 0.4)
    icon_row(d, 65, 160, 3.4, 10.0, CREAM, disc=FOREST)
    ctext(d, 65, 184, "6 oz (170 g)", F("Inter.ttf", 3.2, [14, 560]), CREAM)
    rule(d, 39, 184, 52, GOLD_B, 0.6)
    rule(d, 78, 184, 91, GOLD_B, 0.6)
    return img


def bag_05_arch_crest(logo, motif) -> Image.Image:
    from PIL import ImageDraw as _D
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CREAM)
    d = _D.Draw(img)
    d.rounded_rectangle([P(20), P(10), P(110), P(80)], radius=P(34), fill=FOREST, corners=(True, True, False, False))
    roundel(img, logo, 65, 40, 21, field=WHITE, ring=None)
    ctext(d, 65, 98, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 8.4, [700], "ORGANIC LION'S MANE", 108), FOREST)
    ctext(d, 65, 109, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 620]), FOREST, tracking_mm=1.6)
    place_motif(img, motif, 65, 148, 52, 62)
    icon_row(d, 65, 182, 3.2, 9.5, FOREST, disc=CREAM)
    ctext(d, 65, 197, "6 oz (170 g)", F("Inter.ttf", 3.0, [14, 520]), FOREST)
    return img


BAG_FRONTS = {
    "01_kraft_classic": bag_01_kraft_classic,
    "02_ivory_minimal": bag_02_ivory_minimal,
    "03_forest_apothecary": bag_03_forest_apothecary,
    "04_split_band": bag_04_split_band,
    "05_arch_crest": bag_05_arch_crest,
}


# ── CANISTER wrap fronts (5) — half wrap 114.65 x 120 mm ───────────────────

def can_06_kraft_catalogue(logo, motif) -> Image.Image:
    """Stone & Grove-homage: kraft tube, big stacked display type + icon grid."""
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    ltext(d, 14, 20, "MOGRA ORGANICS", F("Inter.ttf", 3.0, [14, 600]), INK)
    f1 = F("PlayfairDisplay.ttf", 8.0, [700])
    ltext(d, 14, 34, "ORGANIC", f1, INK)
    f2 = F("PlayfairDisplay.ttf", 11.0, [700])
    ltext(d, 14, 48, "LION'S MANE", f2, INK)
    ltext(d, 14, 60, "MUSHROOM POWDER - 6 OZ (170 G)", F("Inter.ttf", 2.6, [14, 500]), INK)
    f_p = F("Inter.ttf", 2.3, [14, 400])
    for i, line in enumerate(("A richly earthy mushroom powder,", "gently dried and milled for a", "smooth daily ritual cup.")):
        ltext(d, 14, 70 + i * 4.0, line, f_p, INK)
    icon_grid(d, 88, 78, 4.2, 16, 16, INK, disc=KRAFT)
    # olive sticker badge (reference homage): sprout icon + name inside
    sd = 26
    sticker = Image.new("RGBA", (P(sd), P(sd)), (0, 0, 0, 0))
    sdc = ImageDraw.Draw(sticker)
    sdc.ellipse([0, 0, P(sd) - 1, P(sd) - 1], fill=OLIVE + (255,))
    draw_cert_icon(sdc, "organic_sprout", P(sd / 2), P(sd / 2) - P(3), P(5.4), ink=CREAM, width=max(2, P(0.5)))
    sdc.text((P(sd / 2), P(17.5)), "LION'S MANE", font=F("Inter.ttf", 1.9, [14, 700]), fill=CREAM, anchor="mm")
    img.paste(sticker, (P(86), P(13)), sticker)
    ctext(d, CAN_HALF / 2, 112, "6 oz (170 g) - MOGRA ORGANICS", F("Inter.ttf", 2.4, [14, 500]), INK)
    return img


def can_07_roundel_band(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    roundel(img, logo, CAN_HALF / 2, 30, 22, field=WHITE, ring=GOLD_A, ring_w=0.6)
    ctext(d, CAN_HALF / 2, 60, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 6.4, [700], "ORGANIC LION'S MANE", 100), FOREST)
    ctext(d, CAN_HALF / 2, 70, "MUSHROOM POWDER", F("Inter.ttf", 2.6, [14, 600]), FOREST, tracking_mm=1.2)
    place_motif(img, motif, CAN_HALF / 2, 95, 40, 34)
    icon_row(d, CAN_HALF / 2, 114, 2.2, 7.0, INK, disc=KRAFT)
    return img


def can_08_vertical_spine(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    rule(d, 24, 10, 24, FOREST, 0.4)
    vtext(img, 10, 6, "MOGRA ORGANICS", F("Inter.ttf", 3.0, [14, 600]), FOREST)
    f1 = fit_size("PlayfairDisplay.ttf", 8.6, [700], "ORGANIC LION'S", 58)
    ltext(d, 33, 26, "ORGANIC", f1, FOREST)
    ltext(d, 33, 38, "LION'S MANE", f1, FOREST)
    ltext(d, 33, 50, "MUSHROOM POWDER", F("Inter.ttf", 2.4, [14, 520]), FOREST)
    place_motif(img, motif, 76, 78, 42, 44)
    icon_row(d, 56, 110, 2.2, 7.2, INK, disc=KRAFT)
    return img


def can_09_bottom_band(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    roundel(img, logo, CAN_HALF / 2, 16, 9, field=WHITE, ring=None)
    ctext(d, CAN_HALF / 2, 34, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 7.2, [700], "ORGANIC LION'S MANE", 100), FOREST)
    ctext(d, CAN_HALF / 2, 44, "MUSHROOM POWDER", F("Inter.ttf", 2.6, [14, 600]), FOREST, tracking_mm=1.4)
    place_motif(img, motif, CAN_HALF / 2, 68, 44, 34)
    d.rectangle([0, P(86), P(CAN_HALF), P(CAN_H)], fill=FOREST)
    icon_row(d, CAN_HALF / 2, 97, 2.3, 7.4, CREAM, disc=FOREST)
    ctext(d, CAN_HALF / 2, 111, "6 oz (170 g)", F("Inter.ttf", 2.6, [14, 560]), CREAM)
    return img


def can_10_ivory_patch(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(10), P(12), P(CAN_HALF - 10), P(104)], radius=P(10), fill=IVORY,
                        outline=SAGE, width=max(1, P(0.3)))
    roundel(img, logo, CAN_HALF / 2, 34, 17, field=WHITE, ring=None)
    ctext(d, CAN_HALF / 2, 56, "ORGANIC LION'S MANE", fit_size("PlayfairDisplay.ttf", 5.8, [700], "ORGANIC LION'S MANE", 80), FOREST)
    ctext(d, CAN_HALF / 2, 65, "MUSHROOM POWDER", F("Inter.ttf", 2.2, [14, 560]), FOREST, tracking_mm=1.2)
    place_motif(img, motif, CAN_HALF / 2, 85, 34, 26)
    icon_row(d, CAN_HALF / 2, 98, 1.9, 6.2, FOREST, disc=IVORY)
    ctext(d, CAN_HALF / 2, 111, "6 oz (170 g)", F("Inter.ttf", 2.4, [14, 500]), INK)
    return img


CAN_FRONTS = {
    "06_kraft_catalogue": can_06_kraft_catalogue,
    "07_roundel_band": can_07_roundel_band,
    "08_vertical_spine": can_08_vertical_spine,
    "09_bottom_band": can_09_bottom_band,
    "10_ivory_patch": can_10_ivory_patch,
}


# ── design registry (title/desc/back colours per design) ────────────────────

def design_specs() -> List[Dict]:
    common_back = [
        "Suggested use: one scoop daily in water, tea or your favourite drink.",
        "Store in a cool, dry place. Keep out of direct sunlight.",
        "Country of origin: see stamp. Distributed by T2 Holdings LLC.",
        "Reseal after each use.",
    ]
    desc1 = ["A richly earthy lion's mane mushroom", "powder, gently dried and milled", "for a smooth daily ritual cup."]
    specs = []
    themes = {
        "01_kraft_classic": dict(kind="bag", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "02_ivory_minimal": dict(kind="bag", ground=IVORY, ground_b=IVORY, ink_b=FOREST),
        "03_forest_apothecary": dict(kind="bag", ground=FOREST, ground_b=FOREST, ink_b=CREAM),
        "04_split_band": dict(kind="bag", ground=IVORY, ground_b=IVORY, ink_b=FOREST),
        "05_arch_crest": dict(kind="bag", ground=CREAM, ground_b=CREAM, ink_b=FOREST),
        "06_kraft_catalogue": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "07_roundel_band": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "08_vertical_spine": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "09_bottom_band": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "10_ivory_patch": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
    }
    for key, th in themes.items():
        specs.append({**th, "key": key, "title": "ORGANIC LION'S MANE",
                      "desc": desc1, "back_lines": common_back})
    return specs
