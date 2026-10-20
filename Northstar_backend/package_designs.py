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

import math

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

import numpy as np

import dieline_art as da
from mockup_compositor import draw_cert_icon, recolor

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


def vtext(canvas, x_mm, y_mm, text, f, fill, block_w_mm: float = 96.0, block_h_mm: float = 16.0):
    """Rotated (reads bottom-to-top) text block pasted at (x, y) top-left."""
    tmp = Image.new("RGBA", (P(block_w_mm), P(block_h_mm)), (0, 0, 0, 0))
    ImageDraw.Draw(tmp).text((P(2), P(block_h_mm / 2)), text, font=f, fill=fill, anchor="lm")
    tmp = tmp.rotate(90, expand=True)
    canvas.paste(tmp, (P(x_mm), P(y_mm)), tmp)


def rot_paste(canvas, block: Image.Image, cx_mm: float, cy_mm: float, angle: float):
    """Paste an RGBA block rotated by `angle` degrees around its centre."""
    r = block.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.paste(r, (int(P(cx_mm) - r.width / 2), int(P(cy_mm) - r.height / 2)), r)


def monogram(logo: Image.Image) -> Image.Image:
    """The mortar-and-pestle mark from the logo (upper portion), cropped tight."""
    crop = da.extract_ink_motif(logo, (0, 0, logo.width, int(logo.height * 0.55)), min_alpha=12)
    a = np.array(crop)
    ys, xs = np.where(a[..., 3] > 20)
    if len(xs):
        crop = crop.crop((int(xs.min()) - 4, int(ys.min()) - 4, int(xs.max()) + 5, int(ys.max()) + 5))
    return crop


def wordmark(logo: Image.Image) -> Image.Image:
    """The MOGRA ORGANICS wordmark band from the logo, cropped tight."""
    y0 = int(logo.height * 0.52)
    crop = da.extract_ink_motif(logo, (0, y0, logo.width, logo.height), min_alpha=12)
    a = np.array(crop)
    ys, xs = np.where(a[..., 3] > 20)
    if len(xs):
        crop = crop.crop((int(xs.min()) - 4, 0, int(xs.max()) + 5, crop.height))
    return crop


def apply_paper(img: Image.Image, seed: int = 1) -> Image.Image:
    """Subtle paper grain + mottle so flat art reads as printed stock (the
    mockup engine's lighting bake then carries it into the print)."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    rng = np.random.default_rng(seed)
    n = rng.normal(0.0, 1.0, (a.shape[0], a.shape[1])).astype(np.float32)
    m = Image.fromarray(np.clip(128 + n * 22, 0, 255).astype(np.uint8), "L")
    m = m.resize((max(1, a.shape[1] // 26), max(1, a.shape[0] // 26)), Image.BILINEAR)
    mot = np.asarray(m.resize((a.shape[1], a.shape[0]), Image.BICUBIC), dtype=np.float32) - 128.0
    a = a + n[..., None] * 0.7 + mot[..., None] * 0.05
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


def _sprig(d, cx, cy, w_mm, color, width):
    """Minimal two-leaf botanical sprig (drawn) for the front lockup."""
    u = P(w_mm) / 12.0
    cxp, cyp = P(cx), P(cy)
    d.line([(cxp, cyp + 5.2 * u), (cxp, cyp - 4.4 * u)], fill=tuple(color), width=width)
    d.arc([cxp - 6.4 * u, cyp - 6.2 * u, cxp + 0.6 * u, cyp + 0.8 * u], 90, 268,
          fill=tuple(color), width=width)
    d.arc([cxp - 0.6 * u, cyp - 6.2 * u, cxp + 6.4 * u, cyp + 0.8 * u], 272, 90,
          fill=tuple(color), width=width)


def front_lockup(*, variant="stack", ink=FOREST, accent=None, track_org=3.4):
    """NEW MOGRA ORGANICS front logo/print (drawn, sharp): serif MOGRA +
    tracked ORGANICS + botanical sprig. Variants: stack / line / badge.
    Returns an RGBA block (scaled by the caller with paste_w)."""
    if accent is None:
        accent = ink
    W, H = 160.0, 92.0
    img = Image.new("RGBA", (P(W), P(H)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = W / 2.0
    w_stroke = max(2, P(0.36))

    if variant == "stack":
        _sprig(d, cx, 16, 10.5, accent, w_stroke)
        ctext(d, cx, 38, "MOGRA", F("PlayfairDisplay.ttf", 17.0, [700]), ink,
              tracking_mm=1.8)
        rule(d, cx - 20, 48.5, cx - 4.2, accent, 0.35)
        rule(d, cx + 4.2, 48.5, cx + 20, accent, 0.35)
        d.ellipse([P(cx - 1.0), P(47.6), P(cx + 1.0), P(49.4)], fill=tuple(accent))
        ctext(d, cx, 57.5, "ORGANICS", F("Inter.ttf", 4.4, [14, 600]), ink,
              tracking_mm=track_org)
        return img.crop((0, 0, P(W), P(66)))

    if variant == "line":
        f1 = F("PlayfairDisplay.ttf", 13.0, [700])
        f2 = F("Inter.ttf", 3.9, [14, 600])
        t1, t2 = "MOGRA", "ORGANICS"
        w1 = d.textlength(t1, font=f1)
        w2 = d.textlength(t2, font=f2) + P(track_org) * (len(t2) - 1)
        sprig_mm = 9.0
        spr = P(sprig_mm)
        gap = P(4.0)
        total = spr + gap + w1 + gap + w2
        x = P(cx) - total / 2
        _sprig(d, (x + spr * 0.5) / (DPI / 25.4), 26, sprig_mm, accent, w_stroke)
        d.text((x + spr + gap, P(26)), t1, font=f1, fill=ink, anchor="lm")
        d.text((x + spr + 2 * gap + w1, P(26)), t2, font=f2, fill=ink, anchor="lm")
        return img.crop((0, 0, P(W), P(46)))

    # badge: ring + sprig + stacked type inside
    r = 26.0
    d.ellipse([P(cx - r), P(30 - r), P(cx + r), P(30 + r)], outline=tuple(accent),
              width=max(2, P(0.5)))
    d.ellipse([P(cx - r + 1.6), P(30 - r + 1.6), P(cx + r - 1.6), P(30 + r - 1.6)],
              outline=tuple(accent), width=max(2, P(0.22)))
    _sprig(d, cx, 17.5, 8.5, accent, max(2, P(0.3)))
    ctext(d, cx, 31.5, "MOGRA", F("PlayfairDisplay.ttf", 8.6, [700]), ink, tracking_mm=0.9)
    ctext(d, cx, 40.5, "ORGANICS", F("Inter.ttf", 2.7, [14, 600]), ink, tracking_mm=2.1)
    return img.crop((0, 0, P(W), P(62)))


def frame(d, W, H, color, inset_mm=5.0, width_mm=0.8, inset2_mm: Optional[float] = None):
    d.rectangle([P(inset_mm), P(inset_mm), P(W - inset_mm), P(H - inset_mm)],
                outline=tuple(color), width=max(2, P(width_mm)))
    if inset2_mm is not None:
        d.rectangle([P(inset2_mm), P(inset2_mm), P(W - inset2_mm), P(H - inset2_mm)],
                    outline=tuple(color), width=max(1, P(0.35)))


def dome(d, cx, base_y, r, color):
    d.pieslice([P(cx - r), P(base_y - 2 * r), P(cx + r), P(base_y)], 180, 360, fill=tuple(color))


def headline(d, cx, y0_mm, lines, *, size_mm, color, line_gap_mm, max_w_mm, tracking_mm=0.0):
    """Anton stacked display lines, fitted, centred."""
    y = y0_mm
    for line in lines:
        f = fit_size("Anton.ttf", size_mm, None, line, max_w_mm)
        ctext(d, cx, y, line, f, color, tracking_mm=tracking_mm)
        y += line_gap_mm
    return y


def value_capsule(canvas, W, cx, y_mm, w_mm, h_mm, cells, *, bg, fg, sep=None):
    """Bulk-supplement style fact bar: [(big, small), ...] in a rounded capsule."""
    d = ImageDraw.Draw(canvas)
    x0, y0 = cx - w_mm / 2, y_mm - h_mm / 2
    d.rounded_rectangle([P(x0), P(y0), P(x0 + w_mm), P(y0 + h_mm)], radius=P(h_mm / 2),
                        fill=tuple(bg), outline=tuple(fg), width=max(2, P(0.5)))
    n = len(cells)
    cell_w = w_mm / n
    f_big = F("Anton.ttf", h_mm * 0.42)
    f_small = F("Inter.ttf", h_mm * 0.19, [14, 700])
    for i, (big, small) in enumerate(cells):
        ccx = x0 + cell_w * (i + 0.5)
        d.text((P(ccx), P(y_mm - h_mm * 0.08)), big, font=f_big, fill=tuple(fg), anchor="mm")
        d.text((P(ccx), P(y_mm + h_mm * 0.30)), small, font=f_small, fill=tuple(fg), anchor="mm")
        if i and sep is not None:
            sx = x0 + cell_w * i
            d.line([(P(sx), P(y0 + h_mm * 0.18)), (P(sx), P(y0 + h_mm * 0.82))],
                   fill=tuple(sep), width=max(1, P(0.4)))


def organic_seal(canvas, cx, cy, r):
    """Generic 'certified organic' roundel (placeholder mark; certifier text in README)."""
    d = ImageDraw.Draw(canvas)
    d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=(23, 54, 32),
              outline=(255, 255, 255), width=max(2, P(0.6)))
    draw_cert_icon(d, "organic_sprout", P(cx), P(cy - r * 0.30), P(r * 0.42),
                   ink=(255, 255, 255), width=max(2, P(0.45)))
    d.text((P(cx), P(cy + r * 0.28)), "ORGANIC", font=F("Anton.ttf", r * 0.34),
           fill=(255, 255, 255), anchor="mm")
    d.text((P(cx), P(cy + r * 0.66)), "CERTIFIED", font=F("Inter.ttf", r * 0.18, [14, 700]),
           fill=(214, 230, 210), anchor="mm")


def fit_size(name, base_mm, axes, text, max_w_mm):
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    size = base_mm
    while size > 2:
        f = F(name, size, axes)
        if d0.textlength(text, font=f) <= P(max_w_mm):
            return f
        size -= 0.25
    return F(name, size, axes)


# ── barcode + QR helpers (real-looking, deterministic) ─────────────────────

_UPC_L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001",
          "0101111", "0111011", "0110111", "0001011"]
_UPC_R = ["".join("1" if c == "0" else "0" for c in p) for p in _UPC_L]


def _upc_bits(digits12: str) -> str:
    d = [int(c) for c in digits12]
    bits = "101"
    for i in range(6):
        bits += _UPC_L[d[i]]
    bits += "01010"
    for i in range(6, 12):
        bits += _UPC_R[d[i]]
    bits += "101"
    return bits


def upc_a_placeholder(base11: str = "01234567890") -> str:
    d = [int(c) for c in base11]
    s = sum(v * (3 if i % 2 == 0 else 1) for i, v in enumerate(d))
    return base11 + str((10 - s % 10) % 10)


def draw_upc(d, x_mm, y_mm, w_mm, h_mm, digits12) -> None:
    bits = _upc_bits(digits12)
    n = len(bits)
    module = P(w_mm) / n
    x = P(x_mm)
    i = 0
    while i < n:
        j = i
        while j < n and bits[j] == bits[i]:
            j += 1
        if bits[i] == "1":
            guard = i < 3 or (i >= 45 and i < 50) or i >= n - 3
            top = P(y_mm) + (P(h_mm) * 0.12 if guard else 0)
            d.rectangle([int(x), int(top), int(x + module * (j - i)), P(y_mm + h_mm)],
                        fill=(0, 0, 0))
        x += module * (j - i)
        i = j
    f = F("Inter.ttf", 2.1, [14, 400])
    spaced = " ".join(digits12[:1]) + "  " + " ".join(digits12[1:6]) + "  " + \
             " ".join(digits12[6:11]) + "  " + digits12[11]
    d.text((P(x_mm) + P(w_mm) / 2, P(y_mm + h_mm + 2.4)), spaced, font=f, fill=(0, 0, 0), anchor="mm")


def draw_qr(canvas, d, x_mm, y_mm, size_mm, payload, seed=7) -> None:
    """Real QR when the qrcode lib is present; deterministic pattern otherwise."""
    x0, y0, size = P(x_mm), P(y_mm), P(size_mm)
    d.rectangle([x0, y0, x0 + size, y0 + size], fill=(255, 255, 255))
    try:
        import qrcode  # noqa: PLC0415
        img = qrcode.make(payload).convert("L")
        inner = size - 2 * P(1)
        img = img.resize((inner, inner), Image.NEAREST)
        inv = img.point(lambda v: 255 - v)
        canvas.paste(Image.new("RGB", (inner, inner), (0, 0, 0)),
                     (x0 + P(1), y0 + P(1)), inv)
        return
    except Exception:
        pass
    rng = np.random.default_rng(seed)
    n = 25
    module = size / n
    grid = (rng.random((n, n)) < 0.45).astype(int)

    def finder(r0, c0):
        for r in range(7):
            for c in range(7):
                edge = r in (0, 6) or c in (0, 6)
                core = 2 <= r <= 4 and 2 <= c <= 4
                grid[r0 + r, c0 + c] = 1 if (edge or core) else 0
    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for r in range(n):
        for c in range(n):
            if grid[r, c]:
                d.rectangle([int(x0 + c * module), int(y0 + r * module),
                             int(x0 + (c + 1) * module), int(y0 + (r + 1) * module)],
                            fill=(0, 0, 0))


# ── shared BACK template (regulatory layout; colours vary per design) ───────

def render_back(spec: Dict, W: float, H: float, logo: Optional[Image.Image] = None) -> Image.Image:
    """Bulk-supplement grade back: big headline, facts + free-of columns, warning
    block, distributed-by with address, real codes, descriptor line. All filled
    (placeholder values register in BACK_LABEL_REQUIREMENTS.md of the pack)."""
    if spec.get("back") == "j":
        return render_back_j(spec, W, H, logo)
    ground = spec.get("ground_b", spec["ground"])
    ink = spec.get("ink_b", INK)
    img = Image.new("RGB", (P(W), P(H)), tuple(ground))
    d = ImageDraw.Draw(img)
    lum = 0.299 * ground[0] + 0.587 * ground[1] + 0.114 * ground[2]
    dark = lum < 140
    narrow = W < 120.0
    sx = (H / 150.0) if narrow else (H / 210.0)
    sc = (W / 130.0) if narrow else 1.0
    tx = 24.0 if narrow else W * 0.075
    right = (W - 24.0) if narrow else (W - W * 0.075)
    col_w = right - tx

    f_b = F("Inter.ttf", 2.6 * sx, [14, 700])
    f_n = F("Inter.ttf", 2.4 * sx, [14, 400])
    f_s = F("Inter.ttf", 2.1 * sx, [14, 400])

    # header: brand lockup (identity series) or wordmark + organic seal
    if spec.get("logo_lockup") and LOCKUP is not None:
        lockup_stamp(img, W / 2, 8 * sx + 10.0, 27.0 * sc, ink)
    elif logo is not None:
        wm = recolor(wordmark(logo), ink)
        wm_w = min(42.0 * sc, col_w * 0.5)
        wm_r = wm.resize((P(wm_w), max(2, int(P(wm_w) * wm.height / wm.width))), Image.LANCZOS)
        img.paste(wm_r, (int(P(W / 2 - wm_w / 2)), P(8 * sx)), wm_r)
    organic_seal(img, right - 8 * sc, 9 * sx + 8 * sc, 8 * sc)

    # headline + weight
    y = headline(d, W / 2, 36 * sx, ["ORGANIC LION'S MANE", "MUSHROOM POWDER"],
                 size_mm=9.2 * sx, color=ink, line_gap_mm=10.0 * sx,
                 max_w_mm=col_w, tracking_mm=0.2)
    d.text((P(W / 2), P(y + 1.5 * sx)), "170 g (6.0 oz)", font=f_b, fill=ink, anchor="mm")

    if not narrow:
        # ── two-column body (bags) ──────────────────────────────────────────
        cy = 72 * sx
        lw = col_w * 0.47
        rx = tx + col_w * 0.55
        rw = right - rx
        # LEFT: Supplement Facts (white block, black rules)
        sf_h = 46.0
        d.rectangle([P(tx), P(cy), P(tx + lw), P(cy + sf_h)], fill=WHITE)
        d.rectangle([P(tx), P(cy), P(tx + lw), P(cy + sf_h)], outline=(0, 0, 0), width=max(2, P(0.4)))
        yy = cy + 4.0
        ltext(d, tx + 2, yy, "SUPPLEMENT FACTS", F("Anton.ttf", 4.6 * sx), (0, 0, 0))
        yy += 5.6
        rule(d, tx + 2, yy, tx + lw - 2, (0, 0, 0), 0.9)
        yy += 3.4
        ltext(d, tx + 2, yy, "Serving Size: 1 scoop (5 g)", f_b, (0, 0, 0))
        yy += 3.8
        ltext(d, tx + 2, yy, "Servings Per Container: 34", f_n, (0, 0, 0))
        yy += 3.0
        d.rectangle([P(tx), P(yy), P(tx + lw), P(yy + 0.9)], fill=(0, 0, 0))
        yy += 3.4
        ltext(d, tx + 2, yy, "Amount Per Serving", f_n, (0, 0, 0))
        rtext(d, tx + lw - 2, yy, "% Daily Value", f_n, (0, 0, 0))
        yy += 2.6
        rule(d, tx + 2, yy, tx + lw - 2, (0, 0, 0), 0.4)
        yy += 3.4
        ltext(d, tx + 2, yy, "Organic Lion's Mane Mushroom", f_n, (0, 0, 0))
        rtext(d, tx + lw - 2, yy, "5 g   *", f_n, (0, 0, 0))
        yy += 2.9
        ltext(d, tx + 2, yy, "Powder (Hericium erinaceus)", f_s, (0, 0, 0))
        yy += 2.7
        ltext(d, tx + 2, yy, "(Sporocarp)", f_s, (0, 0, 0))
        yy += 2.8
        d.rectangle([P(tx), P(yy), P(tx + lw), P(yy + 0.9)], fill=(0, 0, 0))
        yy += 3.0
        ltext(d, tx + 2, yy, "*Daily Value not established.", f_s, (60, 60, 60))
        yy = cy + sf_h + 5.0
        ltext(d, tx, yy, "Other Ingredients: None", f_b, ink)
        yy += 5.2
        ltext(d, tx, yy, "Color May Vary", f_b, ink)
        yy += 6.2
        ltext(d, tx, yy, "WARNING:", f_b, ink)
        yy += 4.2
        for line in ("*These statements have not been evaluated by", "the FDA. This product is not intended to",
                     "diagnose, treat, cure, or prevent any disease.", "Always consult a physician before taking",
                     "any dietary supplement.", "KEEP OUT OF REACH OF CHILDREN."):
            ltext(d, tx, yy, line, f_s, ink)
            yy += 3.6
        yy += 1.6
        ltext(d, tx, yy, "Lot Number: MO-LM-2601", f_n, ink)
        yy += 4.0
        ltext(d, tx, yy, "Best Before: 01-2028", f_n, ink)
        # RIGHT column: real logo + ABOUT LION'S MANE (grouped), then codes
        yy = cy
        ltext(d, rx, yy, "Free of: Added Sugar, Soy, Dairy, Yeast,", f_b, ink)
        yy += 3.8
        ltext(d, rx, yy, "Gluten, Additives", f_b, ink)
        yy += 6.4
        ltext(d, rx, yy, "Suggested Use:", f_b, ink)
        yy += 4.0
        for line in ("As a dietary supplement, take one scoop", "(about 1 tsp) once daily, or as directed",
                     "by a physician."):
            ltext(d, rx, yy, line, f_n, ink)
            yy += 3.6
        yy += 1.4
        for line in ("Use an accurate milligram scale. Contents", "are sold by weight, not volume. Settling",
                     "may occur."):
            ltext(d, rx, yy, line, f_s, ink)
            yy += 3.4
        yy += 1.0
        ltext(d, rx, yy, "Store in a cool, dry place.", f_n, ink)
        yy += 6.2
        ltext(d, rx, yy, "Distributed Exclusively by:", f_b, ink)
        yy += 4.2
        for line in ("T2 Holdings LLC", "1234 Sample Ave, Suite 100", "Springfield, MO 65801, USA",
                     "Certified Organic by: Example Certifiers, Inc."):
            ltext(d, rx, yy, line, f_s, ink)
            yy += 3.4
        # the REAL logo, prominent and visible — grouped with About Lion's Mane
        yy += 1.6
        rule(d, rx, yy, right, ink, 0.25)
        yy += 3.0
        ltext(d, rx, yy, "MOGRA ORGANICS", f_b, ink)
        yy += 3.6
        if logo is not None:
            lk = recolor(wordmark(logo), ink)
            lkw = 36.0
            lkr = lk.resize((P(lkw), max(2, int(P(lkw) * lk.height / lk.width))), Image.LANCZOS)
            img.paste(lkr, (int(P(rx)), P(yy)), lkr)
            yy += lkr.height / (DPI / 25.4) + 3.0
        ltext(d, rx, yy, "ABOUT LION'S MANE", f_b, ink)
        yy += 3.9
        for line in ("Hericium erinaceus is a woodland mushroom with", "a delicate flavour, enjoyed in daily rituals."):
            ltext(d, rx, yy, line, f_s, ink)
            yy += 3.3
        # codes row (white panel on dark grounds)
        qy = H - 36 * sx
        if dark:
            d.rounded_rectangle([P(rx - 3), P(qy - 3), P(right + 3), P(qy + 25 * sx)], radius=P(2),
                                fill=WHITE)
        draw_qr(d, d, rx, qy, 15.0, "https://mograorganics.com/organic-lions-mane")
        upc = upc_a_placeholder()
        draw_upc(d, rx + 19, qy + 0.5, rw - 19, 13.0, upc)
        d.text((P(rx + 19 + (rw - 19) / 2), P(qy + 22.5)), "X00MOGRA-LM",
               font=F("Inter.ttf", 1.9 * sx, [14, 500]), fill=ink, anchor="mm")
    else:
        # ── single-column body (canister half-wrap, tall-tube safe arc) ─────
        cy = 60 * sx
        lw = col_w
        sf_h = 26 * sx
        d.rectangle([P(tx), P(cy), P(tx + lw), P(cy + sf_h)], fill=WHITE)
        d.rectangle([P(tx), P(cy), P(tx + lw), P(cy + sf_h)], outline=(0, 0, 0), width=max(2, P(0.35)))
        yy = cy + 2.6 * sx
        ltext(d, tx + 1.5, yy, "SUPPLEMENT FACTS", F("Anton.ttf", 3.4 * sx), (0, 0, 0))
        yy += 3.9 * sx
        rule(d, tx + 1.5, yy, tx + lw - 1.5, (0, 0, 0), 0.7)
        yy += 2.6 * sx
        ltext(d, tx + 1.5, yy, "Serving Size: 1 scoop (5 g) - 34 servings", f_s, (0, 0, 0))
        yy += 2.9 * sx
        ltext(d, tx + 1.5, yy, "Organic Lion's Mane Mushroom Powder", f_s, (0, 0, 0))
        rtext(d, tx + lw - 1.5, yy, "5 g *", f_s, (0, 0, 0))
        yy += 2.7 * sx
        ltext(d, tx + 1.5, yy, "(Hericium erinaceus) (Sporocarp)", f_s, (90, 90, 90))
        yy += 2.7 * sx
        ltext(d, tx + 1.5, yy, "Other Ingredients: None. *DV not established.", f_s, (60, 60, 60))
        yy = cy + sf_h + 3.4 * sx
        for line in ("Free of: Added Sugar, Soy, Dairy, Yeast, Gluten, Additives.",
                     "Suggested Use: one scoop (about 1 tsp) once daily, or as",
                     "directed by a physician. Use an accurate milligram scale;",
                     "contents are sold by weight, not volume. Settling may occur.",
                     "Store in a cool, dry place. Color may vary.",
                     "Distributed Exclusively by: T2 Holdings LLC, 1234 Sample",
                     "Ave, Suite 100, Springfield, MO 65801, USA.",
                     "Certified Organic by: Example Certifiers, Inc."):
            ltext(d, tx, yy, line, f_s, ink)
            yy += 2.9 * sx
        yy += 1.2 * sx
        ltext(d, tx, yy, "WARNING: *These statements have not been evaluated by the", f_s, ink)
        yy += 2.6 * sx
        ltext(d, tx, yy, "FDA. Not intended to diagnose, treat, cure, or prevent any", f_s, ink)
        yy += 2.6 * sx
        ltext(d, tx, yy, "disease. Consult a physician. KEEP OUT OF REACH OF CHILDREN.", f_s, ink)
        yy += 2.5 * sx
        ltext(d, tx, yy, "Lot: MO-LM-2601   Best Before: 01-2028", f_n, ink)
        qy = H - 23 * sx
        if dark:
            d.rounded_rectangle([P(tx - 2), P(qy - 2.5), P(right + 2), P(qy + 16 * sx)], radius=P(2), fill=WHITE)
        draw_qr(d, d, tx, qy, 13 * sc, "https://mograorganics.com/organic-lions-mane")
        upc = upc_a_placeholder()
        draw_upc(d, tx + 16 * sc, qy + 1, (col_w - 16 * sc), 9 * sc, upc)

    d.text((P(W / 2), P(H - 4.5 * sx)),
           "NEW - Mogra Organics Organic Lion's Mane Mushroom Powder (170 g)",
           font=F("Inter.ttf", 1.9 * sx, [14, 400]), fill=ink, anchor="mm")
    return img


# ── BAG fronts (5) — 130 x 210 mm panels — BOLD SET ───────────────────

FACTS = [("5 g", "PER SERVING"), ("170 g", "WEIGHT"), ("34", "SERVINGS")]


def bag_01_forest_bold(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), FOREST)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, GOLD_A, inset_mm=5.5, width_mm=0.7)
    d.rectangle([P(6.2), P(8), P(123.8), P(27)], fill=CREAM)
    rule(d, 6.2, 8.0, 123.8, GOLD_A, 0.5)
    rule(d, 6.2, 27.0, 123.8, GOLD_A, 0.5)
    wm = wordmark(logo)
    wm_w = 34.0
    wm_r = wm.resize((P(wm_w), max(2, int(P(wm_w) * wm.height / wm.width))), Image.LANCZOS)
    img.paste(wm_r, (int(P(BAG_W / 2 - wm_w / 2)), P(17.5) - wm_r.height // 2), wm_r)
    organic_seal(img, 111, 40, 8.6)
    headline(d, 65, 52, ["ORGANIC"], size_mm=9.4, color=CREAM, line_gap_mm=11.5,
             max_w_mm=104, tracking_mm=3.0)
    headline(d, 65, 66, ["LION'S MANE"], size_mm=15.0, color=CREAM, line_gap_mm=17.0,
             max_w_mm=104)
    ctext(d, 65, 82.5, "MUSHROOM POWDER", F("Inter.ttf", 3.6, [14, 700]), GOLD_A, tracking_mm=3.2)
    rule(d, 36, 88, 94, GOLD_A, 0.5)
    place_motif(img, recolor(motif, CREAM), 65, 126, 66, 64)
    icon_row(d, 65, 165, 3.4, 10.0, CREAM, disc=FOREST)
    value_capsule(img, BAG_W, 65, 184, 106, 14, FACTS, bg=GOLD_A, fg=FOREST,
                  sep=(160, 128, 52))
    ctext(d, 65, 198.5, "MOGRA ORGANICS - ORGANIC LION'S MANE MUSHROOM POWDER",
          F("Inter.ttf", 2.3, [14, 600]), CREAM, tracking_mm=0.9)
    return img


def bag_02_sticker_fun(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CREAM)
    d = ImageDraw.Draw(img)
    bw, bh = 112.0, 118.0
    b = Image.new("RGBA", (P(bw), P(bh)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    bd.rounded_rectangle([P(1), P(1), P(bw) - P(1), P(bh) - P(1)], radius=P(12),
                         fill=FOREST + (255,), outline=GOLD_B + (255,), width=max(3, P(0.9)))
    roundel(b, logo, bw / 2, 24, 13, field=WHITE, ring=None)
    headline(bd, bw / 2, 50, ["ORGANIC", "LION'S MANE"], size_mm=11.0, color=CREAM,
             line_gap_mm=12.6, max_w_mm=bw - 16)
    ctext(bd, bw / 2, 76, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 700]), GOLD_B,
          tracking_mm=2.2)
    value_capsule(b, bw, bw / 2, 98, bw - 20, 14, FACTS, bg=CREAM, fg=FOREST,
                  sep=(188, 178, 160))
    rot_paste(img, b, 65, 68, -2.5)
    place_motif(img, motif, 65, 162, 74, 56)
    icon_row(d, 65, 190, 3.2, 10.0, FOREST, disc=CREAM)
    organic_seal(img, 17, 195, 8.4)
    ctext(d, 78, 197, "6 OZ (170 G) - LION'S MANE", F("Inter.ttf", 2.4, [14, 600]),
          FOREST, tracking_mm=1.0)
    return img


def bag_03_midnight_luxe(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), INK)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, GOLD_A, inset_mm=5.0, width_mm=0.6, inset2_mm=7.0)
    roundel(img, logo, 65, 25, 13, field=WHITE, ring=GOLD_A, ring_w=0.6)
    organic_seal(img, 112, 30, 8.4)
    headline(d, 65, 56, ["ORGANIC"], size_mm=9.6, color=CREAM, line_gap_mm=11.8,
             max_w_mm=104, tracking_mm=3.2)
    headline(d, 65, 70, ["LION'S MANE"], size_mm=15.5, color=CREAM, line_gap_mm=17.5,
             max_w_mm=104)
    ctext(d, 65, 86.5, "MUSHROOM POWDER", F("Inter.ttf", 3.4, [14, 700]), GOLD_A,
          tracking_mm=3.4)
    rule(d, 36, 92, 94, GOLD_A, 0.5)
    place_motif(img, recolor(motif, GOLD_A), 65, 130, 66, 62)
    icon_row(d, 65, 166, 3.4, 10.0, GOLD_A, disc=INK)
    value_capsule(img, BAG_W, 65, 185, 106, 14, FACTS, bg=GOLD_A, fg=INK,
                  sep=(150, 118, 44))
    ctext(d, 65, 199, "MOGRA ORGANICS - EST. MMXXVI", F("Inter.ttf", 2.3, [14, 600]),
          CREAM, tracking_mm=1.6)
    return img


def bag_04_kilim_arch(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CREAM)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(10), P(7), P(120), P(128)], radius=P(44),
                        corners=(True, True, False, False), fill=FOREST)
    roundel(img, logo, 65, 33, 12, field=WHITE, ring=GOLD_A, ring_w=0.5)
    organic_seal(img, 102, 30, 8.0)
    headline(d, 65, 64, ["ORGANIC"], size_mm=8.6, color=CREAM, line_gap_mm=10.6,
             max_w_mm=88, tracking_mm=2.8)
    headline(d, 65, 77, ["LION'S MANE"], size_mm=13.2, color=CREAM, line_gap_mm=15.0,
             max_w_mm=88)
    ctext(d, 65, 92.5, "MUSHROOM POWDER", F("Inter.ttf", 3.1, [14, 700]), GOLD_B,
          tracking_mm=3.0)
    for k in range(13):
        dome(d, 16 + k * 8.0, 128, 4.0, GOLD_A)
    place_motif(img, motif, 65, 157, 76, 48)
    value_capsule(img, BAG_W, 65, 188, 104, 13, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 65, 200, "MOGRA ORGANICS", F("Inter.ttf", 2.3, [14, 600]), FOREST,
          tracking_mm=1.8)
    return img


def bag_05_split_duo(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, P(84), P(BAG_H)], fill=FOREST)
    rule(d, 84, 0, 84, GOLD_B, 0.8)
    vtext(img, 15, 10, "LION'S MANE", F("Anton.ttf", 11.5), CREAM,
          block_w_mm=112, block_h_mm=15)
    vtext(img, 36, 10, "ORGANIC", F("Anton.ttf", 6.4), GOLD_B,
          block_w_mm=58, block_h_mm=8.6)
    vtext(img, 56, 10, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 700]), CREAM,
          block_w_mm=86, block_h_mm=4.2)
    value_capsule(img, BAG_W, 42, 189, 76, 13, FACTS, bg=CREAM, fg=FOREST,
                  sep=(188, 178, 160))
    roundel(img, logo, 107, 21, 11, field=WHITE, ring=FOREST, ring_w=0.4)
    organic_seal(img, 107, 46, 8.2)
    place_motif(img, motif, 107, 100, 38, 72)
    ctext(d, 107, 152, "6 OZ", F("Anton.ttf", 7.0), FOREST)
    ctext(d, 107, 160, "(170 G)", F("Inter.ttf", 2.4, [14, 600]), FOREST, tracking_mm=1.0)
    icon_grid(d, 107, 181, 4.4, 13.0, 13.0, FOREST, disc=CREAM)
    return img


BAG_FRONTS = {
    "01_forest_bold": bag_01_forest_bold,
    "02_sticker_fun": bag_02_sticker_fun,
    "03_midnight_luxe": bag_03_midnight_luxe,
    "04_kilim_arch": bag_04_kilim_arch,
    "05_split_duo": bag_05_split_duo,
}


# ── bag series 2 (bags only) — the REAL logo, ETCHED into the material ──────

def paste_w(canvas, img, cx, cy, w):
    """Paste an RGBA block scaled to width w mm, centred on (cx, cy)."""
    r = img.resize((P(w), max(2, int(P(w) * img.height / img.width))), Image.LANCZOS)
    canvas.paste(r, (int(P(cx) - r.width / 2), int(P(cy) - r.height / 2)), r)
    return r


def etch_logo(logo, *, base, rim_hi, rim_lo, tint=0.3, offset_mm=0.5,
              softness=0.2, inner=0.55):
    """The real logo as an EMBOSSED stamp — all of its artwork stays visible.

    base    = (dark_tone, light_tone): the logo's own artwork is remapped into
              this tone ramp (its internal detail — letters, mortar, tagline —
              keeps its luminance structure instead of flattening to one fill);
    tint    = how much of the logo's original colour bleeds into the ramp
              (e.g. the leaf greens);
    rim_*   = bevel highlight/shadow tones: top-left rim lit, bottom-right rim
              shaded (raised stamp), plus inner-edge shading so it reads 3D.
    """
    src = logo.convert("RGBA")
    arr = np.asarray(src.convert("RGB"), dtype=np.float32)
    mn = arr.min(axis=2)
    keyed = np.clip((196.0 - mn) * 2.4, 0.0, 255.0)
    existing = np.asarray(src.split()[3], dtype=np.float32)
    alpha = keyed * (existing / 255.0)
    mask = Image.fromarray(alpha.astype(np.uint8), "L")
    W, H = src.size
    m = alpha / 255.0

    # artwork -> tone ramp (dark ink stays dark; detail preserved)
    ink_lum = arr.mean(axis=2)
    sel = alpha > 180
    if sel.any():
        lo = float(np.percentile(ink_lum[sel], 8))
        hi = float(np.percentile(ink_lum[sel], 92))
    else:
        lo, hi = 0.0, 255.0
    norm = np.clip((ink_lum - lo) / max(8.0, hi - lo), 0.0, 1.0)
    b_lo = np.array(base[0], np.float32)
    b_hi = np.array(base[1], np.float32)
    art = b_lo[None, None, :] + (b_hi - b_lo)[None, None, :] * norm[..., None]
    if tint:
        art = art * (1.0 - tint) + arr * tint
    art_img = Image.fromarray(np.clip(art, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    art_img.putalpha(mask)

    o = P(offset_mm)

    def shift_m(dx, dy):
        return np.roll(np.roll(m, dy, axis=0), dx, axis=1) if (dx or dy) else m

    def layer(color, a):
        im = Image.new("RGBA", (W, H), tuple(int(c) for c in color) + (255,))
        a8 = Image.fromarray((np.clip(a, 0.0, 1.0) * 255).astype(np.uint8), "L")
        a8 = a8.filter(ImageFilter.GaussianBlur(max(1, P(softness))))
        im.putalpha(a8)
        return im

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # raised stamp: outer rims (shadow lower-right, light upper-left)...
    out.alpha_composite(layer(rim_lo, shift_m(o, o) * 0.85))
    out.alpha_composite(layer(rim_hi, shift_m(-o, -o) * 0.9))
    # ...the artwork itself (all detail visible)...
    out.alpha_composite(art_img)
    # ...inner-edge shading (band where the shape is but its shifted copy is not)
    out.alpha_composite(layer(rim_hi, m * (1.0 - shift_m(o, o)) * inner))
    out.alpha_composite(layer(rim_lo, m * (1.0 - shift_m(-o, -o)) * inner))
    return out


def bag_b06_etched_heritage(logo, motif) -> Image.Image:
    """Ivory heritage: the real lockup etched into the paper, framed foil rules."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), IVORY)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, GOLD_A, inset_mm=6.0, width_mm=0.5, inset2_mm=8.0)
    et = etch_logo(logo, base=((152, 142, 126), (212, 203, 186)),
                   rim_hi=(255, 253, 246), rim_lo=(172, 156, 134), tint=0.32,
                   offset_mm=0.5, softness=0.13)
    paste_w(img, et, 65, 64, 78)
    headline(d, 65, 120, ["ORGANIC LION'S MANE"], size_mm=8.4, color=FOREST,
             line_gap_mm=10.0, max_w_mm=110, tracking_mm=0.4)
    ctext(d, 65, 131, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 700]), FOREST,
          tracking_mm=3.0)
    rule(d, 42, 137, 88, GOLD_A, 0.5)
    place_motif(img, motif, 65, 162, 64, 38)
    icon_row(d, 65, 185, 3.2, 9.6, FOREST, disc=IVORY)
    value_capsule(img, BAG_W, 65, 198, 108, 12.5, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    return img


def bag_b07_etched_noir(logo, motif) -> Image.Image:
    """Near-black matte ground: the real lockup ghost-etched into the surface."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), INK)
    d = ImageDraw.Draw(img)
    et = etch_logo(logo, base=((52, 64, 54), (118, 134, 114)),
                   rim_hi=(150, 168, 148), rim_lo=(10, 14, 11), tint=0.25,
                   offset_mm=0.55, softness=0.15)
    paste_w(img, et, 65, 96, 116)
    paste_w(img, recolor(wordmark(logo), CREAM), 65, 17, 40)
    rule(d, 24, 24, 106, GOLD_A, 0.5)
    headline(d, 65, 158, ["ORGANIC LION'S MANE"], size_mm=9.4, color=CREAM,
             line_gap_mm=11.0, max_w_mm=110, tracking_mm=0.3)
    ctext(d, 65, 173, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 700]), GOLD_A,
          tracking_mm=3.2)
    value_capsule(img, BAG_W, 65, 189, 108, 12.5, FACTS, bg=GOLD_A, fg=INK,
                  sep=(150, 118, 44))
    return img


def bag_b08_foil_monogram(logo, motif) -> Image.Image:
    """Cream apothecary: the real mortar-and-pestle mark as a raised gold foil."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CREAM)
    d = ImageDraw.Draw(img)
    foil = etch_logo(monogram(logo), base=((140, 106, 32), (236, 206, 130)),
                     rim_hi=(255, 244, 190), rim_lo=(98, 72, 22), tint=0.0,
                     offset_mm=0.5, softness=0.13)
    paste_w(img, foil, 65, 74, 62)
    paste_w(img, recolor(wordmark(logo), FOREST), 65, 128, 54)
    ctext(d, 65, 144, "ORGANIC LION'S MANE", F("Inter.ttf", 3.0, [14, 700]), FOREST,
          tracking_mm=3.4)
    ctext(d, 65, 152, "MUSHROOM POWDER", F("Inter.ttf", 2.6, [14, 600]), FOREST,
          tracking_mm=2.6)
    icon_row(d, 65, 170, 3.2, 9.8, FOREST, disc=CREAM)
    value_capsule(img, BAG_W, 65, 190, 106, 13, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 65, 202, "MOGRA ORGANICS - EST. MMXXVI", F("Inter.ttf", 2.3, [14, 600]),
          FOREST, tracking_mm=1.4)
    return img


def bag_b09_kraft_plate(logo, motif) -> Image.Image:
    """Kraft bag with a printed cream 'label plate' carrying the etched lockup."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), KRAFT)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(14), P(12), P(116), P(198)], radius=P(8), fill=CREAM,
                        outline=GOLD_B, width=max(2, P(0.4)))
    et = etch_logo(logo, base=((152, 142, 126), (212, 203, 186)),
                   rim_hi=(255, 253, 246), rim_lo=(172, 156, 134), tint=0.32,
                   offset_mm=0.45, softness=0.13)
    paste_w(img, et, 65, 48, 56)
    headline(d, 65, 86, ["ORGANIC LION'S MANE"], size_mm=7.8, color=FOREST,
             line_gap_mm=9.4, max_w_mm=92, tracking_mm=0.3)
    ctext(d, 65, 96, "MUSHROOM POWDER", F("Inter.ttf", 2.7, [14, 700]), FOREST,
          tracking_mm=2.6)
    rule(d, 42, 102, 88, GOLD_A, 0.4)
    place_motif(img, motif, 65, 129, 56, 36)
    icon_row(d, 65, 154, 3.0, 9.2, FOREST, disc=CREAM)
    value_capsule(img, BAG_W, 65, 176, 88, 12, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 65, 190, "6 OZ (170 G) - STORE COOL & DRY", F("Inter.ttf", 2.3, [14, 600]),
          FOREST, tracking_mm=1.0)
    ctext(d, 65, 204, "T2 HOLDINGS LLC - MOGRA ORGANICS", F("Inter.ttf", 2.2, [14, 600]),
          INK, tracking_mm=0.8)
    return img


def bag_b10_botanical_spine(logo, motif) -> Image.Image:
    """Sage botanical: etched lockup at the head, vertical spine lettering."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), (146, 172, 128))
    d = ImageDraw.Draw(img)
    vtext(img, 8, 24, "MOGRA ORGANICS", F("Inter.ttf", 2.4, [14, 700]), FOREST,
          block_w_mm=64, block_h_mm=3.8)
    vtext(img, 118, 24, "EST. MMXXVI", F("Inter.ttf", 2.4, [14, 700]), FOREST,
          block_w_mm=44, block_h_mm=3.8)
    et = etch_logo(logo, base=((106, 132, 90), (176, 200, 158)),
                   rim_hi=(214, 230, 198), rim_lo=(80, 104, 68), tint=0.3,
                   offset_mm=0.5, softness=0.13)
    paste_w(img, et, 65, 58, 66)
    rule(d, 32, 102, 98, FOREST, 0.4)
    headline(d, 65, 116, ["ORGANIC LION'S MANE"], size_mm=9.6, color=FOREST,
             line_gap_mm=11.2, max_w_mm=104, tracking_mm=0.3)
    ctext(d, 65, 130, "MUSHROOM POWDER", F("Inter.ttf", 2.9, [14, 700]), FOREST,
          tracking_mm=2.8)
    place_motif(img, motif, 65, 158, 60, 38)
    value_capsule(img, BAG_W, 65, 188, 100, 12.5, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 65, 201, "6 OZ (170 G) - 34 SERVINGS", F("Inter.ttf", 2.3, [14, 600]),
          FOREST, tracking_mm=1.0)
    return img


BAG_FRONTS.update({
    "b06_etched_heritage": bag_b06_etched_heritage,
    "b07_etched_noir": bag_b07_etched_noir,
    "b08_foil_monogram": bag_b08_foil_monogram,
    "b09_kraft_plate": bag_b09_kraft_plate,
    "b10_botanical_spine": bag_b10_botanical_spine,
})


# ── bag series 3: EARTH TONES (bags only, 10 styles, NEW front lockup) ──────

STONE = (231, 225, 214)
MOSS = (46, 64, 52)
CLAY = (176, 106, 84)
SAND = (233, 223, 200)
OLIVE_D = (63, 74, 44)
BARK = (43, 43, 40)
OAT = (242, 234, 219)
WALNUT = (74, 59, 46)
SLATE = (74, 85, 96)
TAUPE = (201, 187, 169)
ESPRESSO = (58, 46, 38)
KELP = (31, 58, 52)
COPPER = (176, 118, 74)
LINEN2 = (243, 238, 228)


def e01_stone_heritage(logo, motif) -> Image.Image:
    """Warm stone + hairline double frame; the new lockup leads."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), STONE)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, MOSS, inset_mm=6.5, width_mm=0.4, inset2_mm=8.2)
    paste_w(img, front_lockup(variant="stack", ink=MOSS, accent=COPPER), 65, 46, 74)
    headline(d, 65, 96, ["ORGANIC LION'S MANE"], size_mm=8.6, color=MOSS,
             line_gap_mm=10.0, max_w_mm=108, tracking_mm=0.3)
    ctext(d, 65, 107, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), WALNUT,
          tracking_mm=3.0)
    rule(d, 44, 113, 86, COPPER, 0.4)
    place_motif(img, recolor(motif, MOSS), 65, 146, 62, 44)
    icon_row(d, 65, 174, 3.2, 9.6, MOSS, disc=STONE)
    value_capsule(img, BAG_W, 65, 192, 104, 13, FACTS, bg=MOSS, fg=STONE,
                  sep=(96, 112, 104))
    return img


def e02_moss_arc(logo, motif) -> Image.Image:
    """Deep moss ground, linen half-moon carrying the lockup."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), MOSS)
    d = ImageDraw.Draw(img)
    dome(d, 65, 152, 54, LINEN2)
    paste_w(img, front_lockup(variant="stack", ink=MOSS, accent=COPPER), 65, 66, 74)
    headline(d, 65, 120, ["ORGANIC LION'S MANE"], size_mm=9.2, color=LINEN2,
             line_gap_mm=10.6, max_w_mm=110, tracking_mm=0.3)
    ctext(d, 65, 132, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), COPPER,
          tracking_mm=3.2)
    place_motif(img, recolor(motif, LINEN2), 65, 158, 58, 38)
    value_capsule(img, BAG_W, 65, 190, 104, 13, FACTS, bg=LINEN2, fg=MOSS,
                  sep=(160, 170, 160))
    return img


def e03_clay_bands(logo, motif) -> Image.Image:
    """Soft clay with linen top band + deep moss footer band."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CLAY)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, P(BAG_W), P(48)], fill=LINEN2)
    d.rectangle([0, P(168), P(BAG_W), P(BAG_H)], fill=MOSS)
    paste_w(img, front_lockup(variant="stack", ink=CLAY, accent=WALNUT), 65, 26, 68)
    headline(d, 65, 76, ["ORGANIC LION'S MANE"], size_mm=9.0, color=LINEN2,
             line_gap_mm=10.4, max_w_mm=112, tracking_mm=0.3)
    ctext(d, 65, 88, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), LINEN2,
          tracking_mm=3.2)
    place_motif(img, recolor(motif, LINEN2), 65, 126, 58, 40)
    value_capsule(img, BAG_W, 65, 154, 104, 13, FACTS, bg=LINEN2, fg=MOSS,
                  sep=(160, 170, 160))
    icon_row(d, 65, 180, 3.2, 9.6, LINEN2, disc=MOSS)
    ctext(d, 65, 196, "6 OZ (170 G) - 34 SERVINGS", F("Inter.ttf", 2.4, [14, 600]),
          LINEN2, tracking_mm=1.4)
    return img


def e04_sand_hero(logo, motif) -> Image.Image:
    """Pale sand, oversized lockup as the whole hero."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SAND)
    d = ImageDraw.Draw(img)
    paste_w(img, front_lockup(variant="stack", ink=OLIVE_D, accent=COPPER), 65, 84, 104)
    headline(d, 65, 132, ["ORGANIC LION'S MANE"], size_mm=10.2, color=OLIVE_D,
             line_gap_mm=11.8, max_w_mm=110, tracking_mm=0.3)
    ctext(d, 65, 148, "MUSHROOM POWDER", F("Inter.ttf", 3.2, [14, 600]), WALNUT,
          tracking_mm=3.6)
    rule(d, 44, 154, 86, COPPER, 0.4)
    place_motif(img, recolor(motif, OLIVE_D), 65, 178, 46, 32)
    value_capsule(img, BAG_W, 65, 197, 104, 13, FACTS, bg=OLIVE_D, fg=SAND,
                  sep=(96, 108, 78))
    return img


def e05_bark_editorial(logo, motif) -> Image.Image:
    """Soft charcoal, left-aligned editorial grid with copper rules."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), BARK)
    d = ImageDraw.Draw(img)
    paste_w(img, front_lockup(variant="line", ink=LINEN2, accent=COPPER), 38, 24, 56)
    rule(d, 10, 42, 120, COPPER, 0.4)
    f1 = fit_size("Anton.ttf", 12.0, None, "ORGANIC", 104)
    ltext(d, 10, 66, "ORGANIC", f1, LINEN2)
    f2 = fit_size("Anton.ttf", 16.5, None, "LION'S MANE", 112)
    ltext(d, 10, 84, "LION'S MANE", f2, LINEN2)
    ltext(d, 10, 98, "MUSHROOM POWDER", F("Inter.ttf", 3.2, [14, 600]), COPPER)
    d.line([(52, 112), (52, 150)], fill=tuple(COPPER), width=max(2, P(0.35)))
    place_motif(img, recolor(motif, LINEN2), 91, 131, 52, 38)
    value_capsule(img, BAG_W, 65, 172, 100, 13, FACTS, bg=LINEN2, fg=BARK,
                  sep=(170, 170, 160))
    ctext(d, 65, 192, "6 OZ (170 G) - STORE COOL & DRY", F("Inter.ttf", 2.4, [14, 600]),
          LINEN2, tracking_mm=1.2)
    return img


def e06_olive_badge(logo, motif) -> Image.Image:
    """Deep olive with the ringed badge lockup."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OLIVE_D)
    d = ImageDraw.Draw(img)
    paste_w(img, front_lockup(variant="badge", ink=LINEN2, accent=COPPER), 65, 50, 141)
    headline(d, 65, 100, ["ORGANIC LION'S MANE"], size_mm=9.0, color=LINEN2,
             line_gap_mm=10.4, max_w_mm=108, tracking_mm=0.3)
    ctext(d, 65, 112, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), COPPER,
          tracking_mm=3.2)
    place_motif(img, recolor(motif, LINEN2), 65, 142, 56, 38)
    value_capsule(img, BAG_W, 65, 176, 104, 13, FACTS, bg=LINEN2, fg=OLIVE_D,
                  sep=(160, 170, 150))
    ctext(d, 65, 196, "6 OZ (170 G) - 34 SERVINGS", F("Inter.ttf", 2.4, [14, 600]),
          LINEN2, tracking_mm=1.4)
    return img


def e07_oat_split(logo, motif) -> Image.Image:
    """Creamy oat with a deep moss footer block."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OAT)
    d = ImageDraw.Draw(img)
    d.rectangle([0, P(150), P(BAG_W), P(BAG_H)], fill=MOSS)
    paste_w(img, front_lockup(variant="stack", ink=ESPRESSO, accent=COPPER), 65, 44, 72)
    headline(d, 65, 88, ["ORGANIC LION'S MANE"], size_mm=9.0, color=ESPRESSO,
             line_gap_mm=10.4, max_w_mm=110, tracking_mm=0.3)
    ctext(d, 65, 100, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), WALNUT,
          tracking_mm=3.2)
    rule(d, 44, 106, 86, COPPER, 0.4)
    place_motif(img, recolor(motif, ESPRESSO), 65, 130, 54, 36)
    value_capsule(img, BAG_W, 65, 168, 104, 13, FACTS, bg=OAT, fg=MOSS,
                  sep=(170, 160, 140))
    ctext(d, 65, 190, "6 OZ (170 G) - 34 SERVINGS", F("Inter.ttf", 2.4, [14, 600]),
          OAT, tracking_mm=1.4)
    return img


def e08_slate_formal(logo, motif) -> Image.Image:
    """Blue-slate with a fine cream frame and copper accents."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SLATE)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, LINEN2, inset_mm=6.8, width_mm=0.35, inset2_mm=8.4)
    paste_w(img, front_lockup(variant="line", ink=LINEN2, accent=COPPER), 65, 44, 84)
    headline(d, 65, 94, ["ORGANIC LION'S MANE"], size_mm=8.8, color=LINEN2,
             line_gap_mm=10.2, max_w_mm=106, tracking_mm=0.3)
    ctext(d, 65, 106, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), COPPER,
          tracking_mm=3.2)
    place_motif(img, recolor(motif, LINEN2), 65, 140, 56, 40)
    value_capsule(img, BAG_W, 65, 180, 104, 13, FACTS, bg=COPPER, fg=SLATE,
                  sep=(150, 106, 76))
    ctext(d, 65, 199, "6 OZ (170 G) - 34 SERVINGS", F("Inter.ttf", 2.4, [14, 600]),
          LINEN2, tracking_mm=1.4)
    return img


def e09_taupe_watermark(logo, motif) -> Image.Image:
    """Mushroom taupe with a tonal engraved motif watermark behind the type."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), TAUPE)
    d = ImageDraw.Draw(img)
    place_motif(img, recolor(motif, (214, 201, 184)), 65, 128, 104, 92)
    paste_w(img, front_lockup(variant="stack", ink=ESPRESSO, accent=WALNUT), 65, 46, 74)
    headline(d, 65, 98, ["ORGANIC LION'S MANE"], size_mm=8.8, color=ESPRESSO,
             line_gap_mm=10.2, max_w_mm=108, tracking_mm=0.3)
    ctext(d, 65, 110, "MUSHROOM POWDER", F("Inter.ttf", 3.0, [14, 600]), WALNUT,
          tracking_mm=3.2)
    rule(d, 44, 116, 86, WALNUT, 0.4)
    value_capsule(img, BAG_W, 65, 184, 104, 13, FACTS, bg=ESPRESSO, fg=TAUPE,
                  sep=(140, 124, 108))
    ctext(d, 65, 201, "MOGRA ORGANICS - EST. MMXXVI", F("Inter.ttf", 2.4, [14, 600]),
          ESPRESSO, tracking_mm=1.4)
    return img


def e10_kelp_luxe(logo, motif) -> Image.Image:
    """Deep kelp green, copper hairline frame, generous whitespace."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), KELP)
    d = ImageDraw.Draw(img)
    frame(d, BAG_W, BAG_H, COPPER, inset_mm=6.0, width_mm=0.4)
    paste_w(img, front_lockup(variant="line", ink=LINEN2, accent=COPPER), 65, 36, 80)
    headline(d, 65, 92, ["ORGANIC LION'S MANE"], size_mm=10.6, color=LINEN2,
             line_gap_mm=12.2, max_w_mm=110, tracking_mm=0.3)
    ctext(d, 65, 110, "MUSHROOM POWDER", F("Inter.ttf", 3.2, [14, 600]), COPPER,
          tracking_mm=3.6)
    rule(d, 44, 117, 86, COPPER, 0.4)
    place_motif(img, recolor(motif, LINEN2), 65, 150, 60, 40)
    value_capsule(img, BAG_W, 65, 188, 104, 13, FACTS, bg=COPPER, fg=KELP,
                  sep=(150, 100, 64))
    return img


BAG_FRONTS.update({
    "e01_stone_heritage": e01_stone_heritage,
    "e02_moss_arc": e02_moss_arc,
    "e03_clay_bands": e03_clay_bands,
    "e04_sand_hero": e04_sand_hero,
    "e05_bark_editorial": e05_bark_editorial,
    "e06_olive_badge": e06_olive_badge,
    "e07_oat_split": e07_oat_split,
    "e08_slate_formal": e08_slate_formal,
    "e09_taupe_watermark": e09_taupe_watermark,
    "e10_kelp_luxe": e10_kelp_luxe,
})


# ── bag series 4: LION'S MANE 6 oz (130x210 + 40 gusset, mfr size #2) ───────
# Completely new design language: Cormorant Garamond + Jost, new devices
# (arc-text seal, spec ledger, contour field, wreath, tile, type stack).
# Only the brand LOGO carries over from earlier sets.

ICE = (244, 241, 234)
NAVY = (32, 44, 58)
CEDAR = (74, 44, 34)
PIST = (205, 214, 180)
WHEAT2 = (222, 205, 172)
GRANITE = (108, 108, 104)
ROSE = (223, 197, 184)
SAGE2 = (176, 190, 168)
OAT2 = (238, 231, 216)
PLUM = (74, 52, 60)
FOREST2 = (36, 52, 44)


def brand_line(d, x_mm, y_mm, text, ink, accent, *, align="left", size=3.1):
    """Jost tracked brand/utility line (new series' brand voice)."""
    f = F("Jost.ttf", size, [500])
    if align == "left":
        ltext(d, x_mm, y_mm, text, f, ink)
    else:
        ctext(d, x_mm, y_mm, text, f, ink, tracking_mm=size * 0.62)


def brand_sprig(d, cx, y, ink, accent, w_mm=9.0):
    _sprig(d, cx, y, w_mm, accent, max(2, P(0.34)))


def contour_lines(d, x0, x1, y0, y1, n, color, *, amp_mm=2.2, width_mm=0.25, phase=0.0):
    """Topographic contour field (new-series ornament)."""
    import math
    step = 2.5
    xs = [x0 + i * step for i in range(int((x1 - x0) / step) + 1)]
    for k in range(n):
        yb = y0 + (y1 - y0) * (k / max(1, n - 1))
        pts = [(P(x), P(yb + amp_mm * math.sin((x - x0) / 14.0 * math.pi + phase + k * 0.9)))
               for x in xs]
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=tuple(color), width=max(1, P(width_mm)))


def factsline(d, cx, y_mm, text, ink, accent, *, w_mm=66.0):
    """Hairline colophon with a centred interpunct line (replaces the capsule)."""
    rule(d, cx - w_mm / 2, y_mm, cx + w_mm / 2, accent, 0.3)
    ctext(d, cx, y_mm + 4.8, text, F("Jost.ttf", 2.5, [500]), ink, tracking_mm=1.6)
    rule(d, cx - w_mm / 2, y_mm + 8.6, cx + w_mm / 2, accent, 0.3)


def arc_text(canvas, cx, cy, r, text, f, fill, *, total_deg=210.0, flip=False):
    """Text set along a circle (seal device): each glyph rotated to the path."""
    import math
    d = ImageDraw.Draw(canvas)
    widths = [d.textlength(ch, font=f) for ch in text]
    gap = P(0.4)
    total_px = sum(widths) + gap * max(0, len(text) - 1)
    rpx = max(2.0, float(P(r)))
    beta_total = math.degrees(total_px / rpx)
    pos = -total_px / 2.0
    for ch, w in zip(text, widths):
        beta = (pos + w / 2.0) / rpx          # radians along the arc
        bpos = (math.pi - beta) if flip else beta
        px = P(cx) + P(r) * math.sin(bpos)
        py = P(cy) - P(r) * math.cos(bpos)
        rot = math.degrees(bpos) - (180.0 if flip else 0.0)
        sw, sh = int(max(8, w + P(2))), int(P(f.size * 2.2 / (DPI / 25.4)))
        glyph = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((sw // 2, sh // 2), ch, font=f, fill=tuple(fill) + (255,),
                                   anchor="mm")
        g = glyph.rotate(-rot, expand=True, resample=Image.BICUBIC)
        canvas.paste(g, (int(px - g.width / 2), int(py - g.height / 2)), g)
        pos += w + gap


def sprig_block(w_mm, color, stroke_mm=0.36):
    img = Image.new("RGBA", (P(w_mm), P(w_mm * 0.85)), (0, 0, 0, 0))
    _sprig(ImageDraw.Draw(img), w_mm / 2, w_mm * 0.52, w_mm * 0.8, color, max(2, P(stroke_mm)))
    return img


def f01_porcelain_type(logo, motif) -> Image.Image:
    """Porcelain ground; Cormorant title-case type + one small engraving."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), ICE)
    d = ImageDraw.Draw(img)
    brand_sprig(d, 65, 20, FOREST, FOREST, 10.0)
    brand_line(d, 65, 34, "MOGRA ORGANICS", FOREST, FOREST, align="center", size=3.0)
    ctext(d, 65, 78, "Organic Lion's Mane", F("CormorantGaramond.ttf", 15.5, [600]), FOREST)
    ctext(d, 65, 94, "Mushroom Powder", F("CormorantGaramond-Italic.ttf", 6.4, [500]), COPPER)
    place_motif(img, motif, 65, 140, 58, 44)
    factsline(d, 65, 180, "170 G  ·  34 SERVINGS  ·  5 G PER SCOOP", FOREST, COPPER)
    return img


def f02_cedar_seal(logo, motif) -> Image.Image:
    """Deep cedar ground; the hero is an arc-text seal."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CEDAR)
    d = ImageDraw.Draw(img)
    ctext(d, 65, 84.5, "170 g", F("CormorantGaramond.ttf", 11.0, [600]), LINEN2)
    arc_text(img, 65, 84.5, 30.0, "MOGRA ORGANICS · ORGANIC LION'S MANE",
             F("Jost.ttf", 2.9, [500]), LINEN2, total_deg=250.0)
    arc_text(img, 65, 84.5, 24.5, "SINGLE INGREDIENT · GENTLY MILLED",
             F("Jost.ttf", 1.9, [400]), COPPER, total_deg=170.0, flip=True)
    for rr, wdt in ((33.5, 0.5), (22.0, 0.3)):
        d.ellipse([P(65 - rr), P(84.5 - rr), P(65 + rr), P(84.5 + rr)],
                  outline=tuple(COPPER), width=max(2, P(wdt)))
    ctext(d, 65, 132, "Organic Lion's Mane", F("CormorantGaramond.ttf", 10.5, [600]), LINEN2)
    brand_line(d, 65, 146, "MUSHROOM POWDER", LINEN2, COPPER, align="center", size=2.8)
    place_motif(img, recolor(motif, LINEN2), 65, 172, 44, 26)
    return img


def f03_linen_ledger(logo, motif) -> Image.Image:
    """Oat ground; a spec ledger of hairline rows."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OAT2)
    d = ImageDraw.Draw(img)
    brand_line(d, 65, 20, "MOGRA ORGANICS", ESPRESSO, COPPER, align="center", size=3.0)
    rows = (("INGREDIENT", "Hericium erinaceus"), ("PART", "Sporocarp"),
            ("TEXTURE", "Fine stone mill"), ("SERVING", "One scoop · 5 g"),
            ("ORIGIN", "Packed in the USA"))
    y = 48.0
    for i, (lab, val) in enumerate(rows):
        rule(d, 22, y - 6.4, 108, COPPER, 0.22)
        ltext(d, 26, y, lab, F("Jost.ttf", 2.6, [500]), WALNUT)
        rtext(d, 104, y, val, F("CormorantGaramond.ttf", 4.6, [500]), ESPRESSO)
        y += 13.0
    rule(d, 22, y - 6.4, 108, COPPER, 0.22)
    ctext(d, 65, 148, "Lion's Mane", F("CormorantGaramond.ttf", 16.0, [600]), ESPRESSO)
    ctext(d, 65, 164, "Organic Mushroom Powder", F("CormorantGaramond-Italic.ttf", 5.0, [500]),
          WALNUT)
    factsline(d, 65, 182, "170 G  ·  34 SERVINGS", ESPRESSO, COPPER)
    return img


def f04_wheat_minimal(logo, motif) -> Image.Image:
    """Wheat ground; one enormous italic line and negative space."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), WHEAT2)
    d = ImageDraw.Draw(img)
    brand_sprig(d, 65, 24, WALNUT, WALNUT, 8.0)
    brand_line(d, 65, 36, "MOGRA ORGANICS", WALNUT, WALNUT, align="center", size=2.4)
    f_it = fit_size("CormorantGaramond-Italic.ttf", 24.0, [500], "Lion's Mane", 112)
    ctext(d, 65, 104, "Lion's Mane", f_it, ESPRESSO)
    rule(d, 40, 118, 90, WALNUT, 0.3)
    ctext(d, 65, 126, "ORGANIC MUSHROOM POWDER · 170 G", F("Jost.ttf", 2.7, [500]),
          ESPRESSO, tracking_mm=2.2)
    ctext(d, 65, 190, "5 g per scoop  ·  34 servings  ·  reseal after use",
          F("Jost.ttf", 2.2, [400]), WALNUT, tracking_mm=0.8)
    return img


def f05_pistachio_contour(logo, motif) -> Image.Image:
    """Pistachio ground with a topographic contour field."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), PIST)
    d = ImageDraw.Draw(img)
    contour_lines(d, -4, 134, 26, 150, 12, (176, 190, 148), amp_mm=3.0, phase=0.7)
    brand_line(d, 65, 20, "MOGRA ORGANICS", FOREST2, (120, 140, 96), align="center", size=3.0)
    headline(d, 65, 176, ["ORGANIC LION'S MANE"], size_mm=8.6, color=FOREST2,
             line_gap_mm=10.0, max_w_mm=110, tracking_mm=2.6)
    ctext(d, 65, 190, "MUSHROOM POWDER · 170 G · 34 SERVINGS", F("Jost.ttf", 2.5, [500]),
          (96, 116, 84), tracking_mm=1.4)
    place_motif(img, recolor(motif, FOREST2), 65, 160, 40, 24)
    return img


def f06_porcelain_tile(logo, motif) -> Image.Image:
    """Porcelain ground with a single deep tile block carrying the content."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), ICE)
    d = ImageDraw.Draw(img)
    brand_line(d, 65, 24, "MOGRA ORGANICS", FOREST2, COPPER, align="center", size=3.0)
    ctext(d, 65, 40, "Organic Mushroom Powder", F("CormorantGaramond-Italic.ttf", 5.4, [500]),
          WALNUT)
    d.rounded_rectangle([P(16), P(92), P(114), P(190)], radius=P(7), fill=FOREST2)
    ctext(d, 65, 124, "Lion's Mane", F("CormorantGaramond.ttf", 15.0, [600]), LINEN2)
    ctext(d, 65, 140, "HERICIUM ERINACEUS · SPOROCARP", F("Jost.ttf", 2.4, [500]), PIST,
          tracking_mm=1.3)
    place_motif(img, recolor(motif, PIST), 65, 166, 42, 26)
    ctext(d, 65, 203, "170 g  ·  34 servings  ·  5 g per scoop", F("Jost.ttf", 2.3, [400]),
          ESPRESSO, tracking_mm=0.8)
    return img


def f07_rose_wreath(logo, motif) -> Image.Image:
    """Dusty rose ground; a broken wreath ring with sprigs at the gaps."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), ROSE)
    d = ImageDraw.Draw(img)
    r = 52.0
    d.arc([P(65 - r), P(96 - r), P(65 + r), P(96 + r)], 205, 335, fill=tuple(PLUM),
          width=max(2, P(0.45)))
    d.arc([P(65 - r), P(96 - r), P(65 + r), P(96 + r)], 25, 155, fill=tuple(PLUM),
          width=max(2, P(0.45)))
    rot_paste(img, sprig_block(13.0, PLUM), 65, 43, 0)
    rot_paste(img, sprig_block(13.0, PLUM), 65, 149, 180)
    ctext(d, 65, 84, "Lion's Mane", F("CormorantGaramond.ttf", 13.0, [600]), PLUM)
    ctext(d, 65, 98, "ORGANIC · 170 G", F("Jost.ttf", 2.5, [500]), WALNUT, tracking_mm=2.0)
    ctext(d, 65, 112, "MUSHROOM POWDER", F("Jost.ttf", 2.2, [400]), WALNUT, tracking_mm=1.6)
    brand_line(d, 65, 176, "MOGRA ORGANICS", PLUM, PLUM, align="center", size=2.6)
    factsline(d, 65, 190, "34 SERVINGS  ·  5 G PER SCOOP", PLUM, WALNUT, w_mm=62.0)
    return img


def f08_granite_stack(logo, motif) -> Image.Image:
    """Granite ground; a huge three-line displayed name."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), GRANITE)
    d = ImageDraw.Draw(img)
    brand_line(d, 65, 22, "MOGRA ORGANICS", (236, 233, 224), (236, 233, 224),
               align="center", size=2.8)
    headline(d, 65, 62, ["ORGANIC"], size_mm=13.0, color=(238, 235, 226),
             line_gap_mm=15.5, max_w_mm=112, tracking_mm=1.2)
    rule(d, 30, 76, 100, (238, 235, 226), 0.3)
    headline(d, 65, 92, ["LION'S MANE"], size_mm=16.0, color=(238, 235, 226),
             line_gap_mm=18.5, max_w_mm=112)
    ctext(d, 65, 112, "MUSHROOM POWDER · 170 G", F("Jost.ttf", 2.6, [500]), (206, 204, 196),
          tracking_mm=2.4)
    place_motif(img, recolor(motif, (238, 235, 226)), 65, 150, 52, 34)
    ctext(d, 65, 186, "34 servings · 5 g per scoop · single ingredient",
          F("Jost.ttf", 2.3, [400]), (206, 204, 196), tracking_mm=0.8)
    return img


def f09_plum_prescription(logo, motif) -> Image.Image:
    """Deep plum ground; a single-hairline label box + ruled utility rows."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), PLUM)
    d = ImageDraw.Draw(img)
    d.rectangle([P(18), P(24), P(112), P(116)], outline=tuple((212, 186, 172)),
                width=max(2, P(0.4)))
    ctext(d, 65, 42, "Organic", F("CormorantGaramond-Italic.ttf", 5.6, [500]), (212, 186, 172))
    ctext(d, 65, 62, "Lion's Mane", F("CormorantGaramond.ttf", 14.0, [600]), LINEN2)
    ctext(d, 65, 78, "MUSHROOM POWDER", F("Jost.ttf", 2.6, [500]), COPPER, tracking_mm=2.4)
    ctext(d, 65, 92, "170 G · 34 SERVINGS · 5 G PER SCOOP", F("Jost.ttf", 2.3, [400]),
          (206, 184, 172), tracking_mm=1.2)
    ctext(d, 65, 106, "MOGRA ORGANICS", F("Jost.ttf", 2.8, [600]), LINEN2, tracking_mm=3.0)
    y = 134.0
    for label, val in (("GENTLY DRIED", "low temperature"), ("STONE MILLED", "fine & even"),
                       ("NOTHING ADDED", "single ingredient")):
        rule(d, 22, y - 5.6, 108, (150, 116, 108), 0.22)
        ltext(d, 26, y, label, F("Jost.ttf", 2.4, [500]), (206, 184, 172))
        rtext(d, 104, y, val, F("CormorantGaramond-Italic.ttf", 4.2, [500]), LINEN2)
        y += 12.5
    rule(d, 22, y - 5.6, 108, (150, 116, 108), 0.22)
    place_motif(img, recolor(motif, (212, 186, 172)), 65, 190, 40, 24)
    return img


def f10_ice_botanical(logo, motif) -> Image.Image:
    """Porcelain ground; the engraved botanical at hero scale."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), ICE)
    d = ImageDraw.Draw(img)
    place_motif(img, recolor(motif, (206, 196, 176)), 65, 132, 122, 116)
    brand_line(d, 65, 20, "MOGRA ORGANICS", FOREST2, COPPER, align="center", size=3.0)
    ctext(d, 65, 52, "Lion's Mane", F("CormorantGaramond.ttf", 16.5, [600]), FOREST2)
    ctext(d, 65, 68, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.7, [500]), WALNUT,
          tracking_mm=2.6)
    place_motif(img, motif, 65, 132, 58, 52)
    factsline(d, 65, 186, "170 G  ·  34 SERVINGS  ·  5 G PER SCOOP", FOREST2, COPPER)
    return img


BAG_FRONTS.update({
    "f01_porcelain_type": f01_porcelain_type,
    "f02_cedar_seal": f02_cedar_seal,
    "f03_linen_ledger": f03_linen_ledger,
    "f04_wheat_minimal": f04_wheat_minimal,
    "f05_pistachio_contour": f05_pistachio_contour,
    "f06_porcelain_tile": f06_porcelain_tile,
    "f07_rose_wreath": f07_rose_wreath,
    "f08_granite_stack": f08_granite_stack,
    "f09_plum_prescription": f09_plum_prescription,
    "f10_ice_botanical": f10_ice_botanical,
})


# ── bag series 5: BOLD IDENTITY (real logo on the front, high contrast) ─────

BONE = (240, 235, 224)
TERRA = (170, 88, 60)
TEAL = (30, 62, 62)
OLIVE2 = (86, 96, 56)
CHAR = (44, 44, 46)
SLATE2 = (62, 74, 88)
BLUSH = (226, 205, 196)


def logo_block(canvas, logo, cx, cy, w_mm, ink):
    """The real MOGRA logo (full lockup, leaves kept green) at size w_mm."""
    paste_w(canvas, recolor(logo, ink), cx, cy, w_mm)


def legend(d, cx, y, ink, *, text="170 G   ·   34 SERVINGS   ·   5 G PER SCOOP", size=2.7):
    """Letterspaced single-line fact legend (no rules, no capsule)."""
    ctext(d, cx, y, text, F("Jost.ttf", size, [500]), ink, tracking_mm=size * 0.9)


def g01_ink_sash(logo, motif) -> Image.Image:
    """Ink ground, full-height bone sash carrying the identity."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), INK)
    d = ImageDraw.Draw(img)
    d.rectangle([P(76), 0, P(BAG_W), P(BAG_H)], fill=BONE)
    place_motif(img, recolor(motif, BONE), 38, 104, 62, 74)
    logo_block(img, logo, 103, 40, 36, INK)
    rule(d, 84, 66, 122, INK, 0.4)
    headline(d, 103, 84, ["ORGANIC"], size_mm=7.2, color=INK, line_gap_mm=8.6,
             max_w_mm=40, tracking_mm=2.0)
    headline(d, 103, 99, ["LION'S", "MANE"], size_mm=10.4, color=INK, line_gap_mm=11.8,
             max_w_mm=40)
    ctext(d, 103, 128, "MUSHROOM POWDER", F("Jost.ttf", 2.4, [500]), TERRA, tracking_mm=1.6)
    rule(d, 84, 140, 122, INK, 0.4)
    legend(d, 103, 152, INK, text="170 G", size=2.6)
    legend(d, 103, 160, INK, text="34 SERVINGS", size=2.6)
    legend(d, 103, 168, INK, text="5 G PER SCOOP", size=2.6)
    return img


def g02_bone_spill(logo, motif) -> Image.Image:
    """Bone ground, terracotta label panel the botanical spills over."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), BONE)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(14), P(46), P(116), P(198)], radius=P(8), fill=TERRA)
    place_motif(img, recolor(motif, TERRA), 65, 48, 74, 54)
    logo_block(img, logo, 65, 96, 36, BONE)
    rule(d, 34, 122, 96, BONE, 0.4)
    ctext(d, 65, 138, "Lion's Mane", F("CormorantGaramond.ttf", 16.5, [600]), BONE)
    ctext(d, 65, 152, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.6, [500]), BONE,
          tracking_mm=2.4)
    legend(d, 65, 182, BONE)
    return img


def g03_terra_sun(logo, motif) -> Image.Image:
    """Terracotta ground, bone sun disc holding the logo."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), TERRA)
    d = ImageDraw.Draw(img)
    d.ellipse([P(25), P(34), P(105), P(114)], fill=BONE)
    logo_block(img, logo, 65, 74, 34, TERRA)
    ctext(d, 65, 140, "Lion's Mane", F("CormorantGaramond.ttf", 17.0, [600]), BONE)
    ctext(d, 65, 154, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.7, [500]), BONE,
          tracking_mm=2.6)
    place_motif(img, recolor(motif, BONE), 65, 178, 52, 30)
    legend(d, 65, 198, BONE)
    return img


def g04_teal_horizon(logo, motif) -> Image.Image:
    """Deep teal, full-bleed bone horizon band with the reversed title."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), TEAL)
    d = ImageDraw.Draw(img)
    d.rectangle([0, P(112), P(BAG_W), P(148)], fill=BONE)
    logo_block(img, logo, 65, 58, 42, BONE)
    ctext(d, 65, 106, "ORGANIC", F("Jost.ttf", 2.8, [500]), BONE, tracking_mm=3.0)
    ctext(d, 65, 131, "Lion's Mane", F("CormorantGaramond.ttf", 17.0, [600]), TEAL)
    legend(d, 65, 142, TEAL, text="170 G   ·   34 SERVINGS", size=2.5)
    place_motif(img, recolor(motif, BONE), 65, 176, 56, 34)
    legend(d, 65, 198, BONE, text="MUSHROOM POWDER   ·   5 G PER SCOOP", size=2.4)
    return img


def g05_olive_identity(logo, motif) -> Image.Image:
    """Olive ground, identity-first: the real logo at hero scale."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OLIVE2)
    d = ImageDraw.Draw(img)
    logo_block(img, logo, 65, 56, 52, BONE)
    rule(d, 40, 92, 90, BONE, 0.4)
    ctext(d, 65, 112, "Lion's Mane", F("CormorantGaramond.ttf", 19.0, [600]), BONE)
    ctext(d, 65, 130, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.8, [500]), BONE,
          tracking_mm=2.8)
    place_motif(img, recolor(motif, BONE), 65, 166, 54, 34)
    legend(d, 65, 194, BONE)
    return img


def g06_charcoal_banner(logo, motif) -> Image.Image:
    """Charcoal ground, bone banner with reversed title, botanical above."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CHAR)
    d = ImageDraw.Draw(img)
    place_motif(img, recolor(motif, BONE), 65, 70, 70, 56)
    d.rectangle([0, P(138), P(BAG_W), P(168)], fill=BONE)
    ctext(d, 65, 153, "Lion's Mane", F("CormorantGaramond.ttf", 16.0, [600]), CHAR)
    logo_block(img, logo, 65, 186, 34, BONE)
    legend(d, 65, 204, BONE, text="ORGANIC   ·   170 G   ·   34 SERVINGS", size=2.4)
    return img


def g07_slate_halo(logo, motif) -> Image.Image:
    """Slate ground, halo rings around the real logo."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SLATE2)
    d = ImageDraw.Draw(img)
    for rr, wdt in ((30.0, 0.35), (34.5, 0.22)):
        d.ellipse([P(65 - rr), P(62 - rr), P(65 + rr), P(62 + rr)], outline=tuple(BONE),
                  width=max(2, P(wdt)))
    logo_block(img, logo, 65, 62, 36, BONE)
    ctext(d, 65, 124, "Lion's Mane", F("CormorantGaramond.ttf", 17.0, [600]), BONE)
    ctext(d, 65, 138, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.7, [500]), BONE,
          tracking_mm=2.6)
    place_motif(img, recolor(motif, BONE), 65, 170, 52, 32)
    legend(d, 65, 198, BONE)
    return img


def g08_blush_column(logo, motif) -> Image.Image:
    """Blush ground, full-height plum column on the left."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), BLUSH)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, P(44), P(BAG_H)], fill=PLUM)
    logo_block(img, logo, 22, 48, 26, BLUSH)
    rule(d, 8, 76, 36, BLUSH, 0.35)
    headline(d, 22, 96, ["LION'S", "MANE"], size_mm=9.0, color=BLUSH, line_gap_mm=10.4,
             max_w_mm=30)
    ctext(d, 22, 124, "POWDER", F("Jost.ttf", 2.5, [500]), BLUSH, tracking_mm=2.2)
    place_motif(img, recolor(motif, PLUM), 87, 92, 58, 50)
    ctext(d, 87, 148, "Organic", F("CormorantGaramond-Italic.ttf", 6.4, [500]), PLUM)
    ctext(d, 87, 164, "Lion's Mane", F("CormorantGaramond.ttf", 12.0, [600]), PLUM)
    legend(d, 87, 186, PLUM, text="170 G   ·   34 SERVINGS", size=2.4)
    ctext(d, 87, 198, "MUSHROOM POWDER", F("Jost.ttf", 2.2, [500]), WALNUT, tracking_mm=1.8)
    return img


def g09_bone_stamp(logo, motif) -> Image.Image:
    """Bone ground, a big ink stamp disc cropped by the top-right edge."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), BONE)
    d = ImageDraw.Draw(img)
    d.ellipse([P(30), P(8), P(134), P(112)], fill=INK)
    logo_block(img, logo, 79, 58, 34, BONE)
    ctext(d, 65, 142, "Lion's Mane", F("CormorantGaramond.ttf", 17.0, [600]), INK)
    ctext(d, 65, 156, "ORGANIC MUSHROOM POWDER", F("Jost.ttf", 2.7, [500]), WALNUT,
          tracking_mm=2.6)
    place_motif(img, recolor(motif, INK), 65, 182, 50, 30)
    legend(d, 65, 200, INK, text="170 G   ·   34 SERVINGS   ·   5 G PER SCOOP", size=2.4)
    return img


def g10_forest_duo(logo, motif) -> Image.Image:
    """Forest ground, bone label panel top and bottom botanicals."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), FOREST2)
    d = ImageDraw.Draw(img)
    logo_block(img, logo, 65, 46, 38, BONE)
    place_motif(img, recolor(motif, BONE), 65, 26, 34, 20)
    d.rounded_rectangle([P(22), P(72), P(108), P(158)], radius=P(4), fill=BONE)
    ctext(d, 65, 96, "Organic Lion's Mane", F("CormorantGaramond.ttf", 12.6, [600]), FOREST2)
    rule(d, 36, 110, 94, FOREST2, 0.35)
    ctext(d, 65, 122, "MUSHROOM POWDER", F("Jost.ttf", 2.7, [500]), WALNUT, tracking_mm=2.4)
    legend(d, 65, 140, WALNUT, text="170 G   ·   34 SERVINGS", size=2.4)
    ctext(d, 65, 150, "5 G PER SCOOP", F("Jost.ttf", 2.2, [400]), WALNUT, tracking_mm=1.4)
    place_motif(img, recolor(motif, BONE), 65, 180, 48, 30)
    legend(d, 65, 199, BONE, text="MOGRA ORGANICS", size=2.5)
    return img


BAG_FRONTS.update({
    "g01_ink_sash": g01_ink_sash,
    "g02_bone_spill": g02_bone_spill,
    "g03_terra_sun": g03_terra_sun,
    "g04_teal_horizon": g04_teal_horizon,
    "g05_olive_identity": g05_olive_identity,
    "g06_charcoal_banner": g06_charcoal_banner,
    "g07_slate_halo": g07_slate_halo,
    "g08_blush_column": g08_blush_column,
    "g09_bone_stamp": g09_bone_stamp,
    "g10_forest_duo": g10_forest_duo,
})


# ── bag series H: HERO (10 designs, 100% unique, no shared composition) ─────

INK2 = (20, 20, 22)
PARCHMENT = (246, 240, 228)
CEDAR2 = (156, 82, 62)
TEAL2 = (34, 78, 86)
SLATE3 = (90, 104, 116)
FOREST3 = (44, 70, 56)
ROSE2 = (198, 158, 142)
OCHRE = (186, 130, 74)
SAGE3 = (136, 148, 132)
VIOLET = (82, 64, 92)


def logo_ink(logo, ink):
    """The real logo as clean ink on transparency — wordmark + monogram,
    leaves kept green — for stamping directly onto bag color."""
    return recolor(wordmark(logo), ink)


def stamp_logo(canvas, logo_img, cx, cy, w_mm, ink):
    paste_w(canvas, recolor(logo_img, ink), cx, cy, w_mm)


# ── full-lockup stamp (v2 sharp master) ──────────────────────────────────────

LOCKUP: Optional[Image.Image] = None
_LOCKUP_BBOX: Optional[Tuple[int, int, int, int]] = None


def set_logo_assets(lockup: Optional[Image.Image] = None) -> None:
    """Register the high-res lockup RGBA (emblem + EST 2023 + wordmark +
    tagline) used by the identity series. Built by refine_mogra_logo.py."""
    global LOCKUP, _LOCKUP_BBOX
    LOCKUP = lockup
    _LOCKUP_BBOX = None
    if lockup is not None:
        a = np.array(lockup)[..., 3]
        ys, xs = np.where(a > 40)
        if len(xs):
            _LOCKUP_BBOX = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)


def lockup_stamp(canvas, cx, cy, visible_w_mm, ink):
    """Paste the full MOGRA lockup so its VISIBLE ink is `visible_w_mm` wide,
    ink-centred on (cx, cy); green leaves keep their colour (recolor rule)."""
    if LOCKUP is None or _LOCKUP_BBOX is None:
        raise RuntimeError("lockup asset not set - call set_logo_assets() first")
    lx0, ly0, lx1, ly1 = _LOCKUP_BBOX
    s = P(visible_w_mm) / (lx1 - lx0)
    r = LOCKUP.resize((max(2, int(LOCKUP.width * s)), max(2, int(LOCKUP.height * s))), Image.LANCZOS)
    r = recolor(r, ink)
    bx, by = (lx0 + lx1) / 2 * s, (ly0 + ly1) / 2 * s
    canvas.paste(r, (int(P(cx) - bx), int(P(cy) - by)), r)
    return r


def big_name(d, cx, y, lines, ink, *, size_mm=16, gap_mm=2.0, max_w=112,
             font="CormorantGaramond.ttf", axes=[600]):
    yy = y
    for line in lines:
        f = fit_size(font, size_mm, axes, line, max_w)
        ctext(d, cx, yy, line, f, ink, tracking_mm=0.4)
        yy += f.size / (DPI / 25.4) + gap_mm
    return yy


def fact_ledge(d, cx, y, ink, *, lines=("170 G", "34 SERVINGS", "5 G PER SCOOP"),
               gap_mm=3.6):
    for i, line in enumerate(lines):
        ctext(d, cx, y + i * gap_mm, line, F("Jost.ttf", 2.5, [500]), ink,
              tracking_mm=0.8)


def h01_porcelain_monument(logo, motif) -> Image.Image:
    """Porcelain: monument. Giant centered logo wordmark, small text below."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), PARCHMENT)
    d = ImageDraw.Draw(img)
    stamp_logo(img, logo_ink(logo, FOREST3), 65, 30, 78, FOREST3)
    big_name(d, 65, 110, ["ORGANIC", "LION'S MANE"], FOREST3, size_mm=15.5,
             gap_mm=1.5, max_w=112)
    ctext(d, 65, 148, "MUSHROOM POWDER", F("Jost.ttf", 3.0, [500]), CEDAR2,
          tracking_mm=3.4)
    rule(d, 36, 156, 94, CEDAR2, 0.4)
    fact_ledge(d, 65, 170, FOREST3)
    place_motif(img, recolor(motif, FOREST3), 65, 196, 60, 32)
    return img


def h02_cedar_tower(logo, motif) -> Image.Image:
    """Cedar: full-height reversed type tower on the right edge."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CEDAR2)
    d = ImageDraw.Draw(img)
    d.rectangle([P(44), 0, P(BAG_W), P(BAG_H)], fill=PARCHMENT)
    stamp_logo(img, logo_ink(logo, CEDAR2), 24, 40, 30, CEDAR2)
    ctext(d, 24, 80, "LION'S", F("Jost.ttf", 3.6, [800]), PARCHMENT,
          tracking_mm=2.0)
    ctext(d, 24, 98, "MANE", F("Jost.ttf", 3.6, [800]), PARCHMENT, tracking_mm=2.0)
    ctext(d, 24, 116, "ORGANIC POWDER", F("Jost.ttf", 2.2, [500]), PARCHMENT,
          tracking_mm=1.8)
    rule(d, 8, 132, 40, CEDAR2, 0.3)
    big_name(d, 86, 66, ["ORGANIC LION'S MANE"], CEDAR2, size_mm=10.5, max_w=44)
    fact_ledge(d, 86, 112, CEDAR2)
    place_motif(img, recolor(motif, CEDAR2), 86, 160, 40, 30)
    return img


def h03_teal_arc(logo, motif) -> Image.Image:
    """Teal: wordmark inside a shallow arc, botanical hero below."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), TEAL2)
    d = ImageDraw.Draw(img)
    for rr in (36.0, 31.0):
        d.arc([P(65 - rr), P(108 - rr), P(65 + rr), P(108 + rr)], 200, 340,
              fill=tuple(PARCHMENT), width=max(2, P(0.35)))
    stamp_logo(img, logo_ink(logo, PARCHMENT), 65, 116, 40, PARCHMENT)
    big_name(d, 65, 146, ["ORGANIC", "LION'S MANE"], PARCHMENT, size_mm=13.5,
             gap_mm=1.0, max_w=96)
    fact_ledge(d, 65, 186, PARCHMENT, lines=("170 G", "34 SERVINGS"))
    place_motif(img, recolor(motif, PARCHMENT), 65, 198, 70, 40)
    return img


def h04_slate_ticket(logo, motif) -> Image.Image:
    """Slate: ticket-strip layout, left edge runs full height."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SLATE3)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, P(12), P(BAG_H)], fill=PARCHMENT)
    stamp_logo(img, logo_ink(logo, SLATE3), 6, 46, 20, SLATE3)
    vtext(img, 8, 104, "MOGRA ORGANICS · ORGANIC LION'S MANE · 170 G",
          F("Jost.ttf", 2.2, [500]), PARCHMENT, block_w_mm=88, block_h_mm=3.2)
    big_name(d, 84, 78, ["ORGANIC", "LION'S MANE"], PARCHMENT, size_mm=14.0,
             gap_mm=1.2, max_w=48)
    fact_ledge(d, 84, 120, PARCHMENT)
    place_motif(img, recolor(motif, PARCHMENT), 84, 152, 50, 34)
    return img


def h05_forest_crest(logo, motif) -> Image.Image:
    """Forest: crest container, logo sits inside crest top."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), FOREST3)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(16), P(10), P(114), P(96)], radius=P(14), fill=PARCHMENT)
    stamp_logo(img, logo_ink(logo, FOREST3), 65, 46, 60, FOREST3)
    big_name(d, 65, 114, ["ORGANIC", "LION'S MANE"], PARCHMENT, size_mm=14.0,
             gap_mm=1.2, max_w=94)
    ctext(d, 65, 148, "MUSHROOM POWDER", F("Jost.ttf", 3.0, [500]), OCHRE,
          tracking_mm=3.0)
    rule(d, 42, 156, 88, PARCHMENT, 0.4)
    fact_ledge(d, 65, 172, PARCHMENT)
    place_motif(img, recolor(motif, PARCHMENT), 65, 194, 56, 30)
    return img


def h06_rose_slab(logo, motif) -> Image.Image:
    """Rose: huge single slab of type, logo at bottom center."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), ROSE2)
    d = ImageDraw.Draw(img)
    big_name(d, 65, 60, ["LION'S", "MANE"], PARCHMENT, size_mm=19.0, gap_mm=0.0,
             max_w=112)
    ctext(d, 65, 104, "ORGANIC", F("Jost.ttf", 3.2, [800]), PARCHMENT,
          tracking_mm=4.0)
    ctext(d, 65, 118, "MUSHROOM POWDER", F("Jost.ttf", 2.6, [500]), OCHRE,
          tracking_mm=2.6)
    rule(d, 44, 130, 86, PARCHMENT, 0.4)
    stamp_logo(img, logo_ink(logo, PARCHMENT), 65, 150, 34, PARCHMENT)
    fact_ledge(d, 65, 180, PARCHMENT)
    place_motif(img, recolor(motif, PARCHMENT), 65, 196, 52, 28)
    return img


def h07_ochre_fold(logo, motif) -> Image.Image:
    """Ochre: diagonal fold illusion with logo on the flap."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OCHRE)
    d = ImageDraw.Draw(img)
    d.polygon([(P(0), P(0)), (P(130), P(40)), (P(130), P(210)), (P(0), P(170))],
              fill=PARCHMENT)
    stamp_logo(img, logo_ink(logo, PARCHMENT), 66, 56, 44, PARCHMENT)
    big_name(d, 66, 110, ["ORGANIC LION'S MANE"], PARCHMENT, size_mm=12.0,
             gap_mm=1.4, max_w=100)
    fact_ledge(d, 66, 146, PARCHMENT)
    place_motif(img, recolor(motif, PARCHMENT), 66, 172, 60, 40)
    return img


def h08_sage_wash(logo, motif) -> Image.Image:
    """Sage: soft wash, logo set in a hand-drawn circle."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SAGE3)
    d = ImageDraw.Draw(img)
    d.ellipse([P(18), P(14), P(112), P(108)], outline=tuple(FOREST3),
              width=max(2, P(0.5)))
    d.ellipse([P(24), P(20), P(106), P(102)], outline=tuple(FOREST3),
              width=max(2, P(0.2)))
    stamp_logo(img, logo_ink(logo, FOREST3), 65, 62, 52, FOREST3)
    big_name(d, 65, 120, ["ORGANIC", "LION'S MANE"], FOREST3, size_mm=13.0,
             gap_mm=1.0, max_w=92)
    fact_ledge(d, 65, 160, FOREST3)
    place_motif(img, recolor(motif, FOREST3), 65, 182, 54, 34)
    return img


def h09_violet_block(logo, motif) -> Image.Image:
    """Violet: single deep block top third, reversed logo + type."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), PARCHMENT)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, P(BAG_W), P(86)], fill=VIOLET)
    d.rectangle([P(14), P(14), P(116), P(78)], fill=VIOLET)
    stamp_logo(img, logo_ink(logo, PARCHMENT), 65, 34, 60, PARCHMENT)
    big_name(d, 65, 96, ["LION'S", "MANE"], PARCHMENT, size_mm=14.0, gap_mm=0.8,
             max_w=100)
    fact_ledge(d, 65, 130, PARCHMENT)
    place_motif(img, recolor(motif, PARCHMENT), 65, 156, 70, 42)
    ctext(d, 65, 200, "ORGANIC MUSHROOM POWDER · 170 G",
          F("Jost.ttf", 2.6, [500]), VIOLET, tracking_mm=2.2)
    return img


def h10_monogram_only(logo, motif) -> Image.Image:
    """Bone: nothing but the real logo mark and one line of type."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), BONE)
    d = ImageDraw.Draw(img)
    stamp_logo(img, logo_ink(logo, CEDAR2), 65, 70, 84, CEDAR2)
    rule(d, 44, 146, 86, CEDAR2, 0.4)
    big_name(d, 65, 160, ["ORGANIC LION'S MANE"], CEDAR2, size_mm=13.0,
             gap_mm=1.4, max_w=112)
    fact_ledge(d, 65, 196, CEDAR2, lines=("170 G", "34 SERVINGS"))
    place_motif(img, recolor(motif, CEDAR2), 65, 194, 30, 18)
    return img


BAG_FRONTS.update({
    "h01_porcelain_monument": h01_porcelain_monument,
    "h02_cedar_tower": h02_cedar_tower,
    "h03_teal_arc": h03_teal_arc,
    "h04_slate_ticket": h04_slate_ticket,
    "h05_forest_crest": h05_forest_crest,
    "h06_rose_slab": h06_rose_slab,
    "h07_ochre_fold": h07_ochre_fold,
    "h08_sage_wash": h08_sage_wash,
    "h09_violet_block": h09_violet_block,
    "h10_monogram_only": h10_monogram_only,
})


# ── bag series I: IDENTITY (10 designs, 100% unique, no shared composition) ─

IIVORY = (247, 243, 236)
DARK = (24, 24, 26)
SEA = (48, 86, 94)
BRICK = (164, 74, 62)
MOON = (218, 204, 188)
IVY = (64, 82, 68)
CLAY2 = (190, 134, 98)
PLUM2 = (94, 72, 86)
MIST = (168, 178, 174)
OBSIDIAN = (38, 38, 40)


def i01_logo_monument(logo, motif) -> Image.Image:
    """Logo is the hero: the full lockup across the top half."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), IIVORY)
    d = ImageDraw.Draw(img)
    lockup_stamp(img, 65, 52, 58, DARK)
    rule(d, 44, 92, 86, DARK, 0.4)
    big_name(d, 65, 116, ["ORGANIC LION'S MANE"], DARK, size_mm=15.0, gap_mm=1.6,
             max_w=112)
    fact_ledge(d, 65, 156, DARK, lines=("170 G", "34 SERVINGS", "5 G PER SCOOP"))
    place_motif(img, recolor(motif, DARK), 65, 190, 56, 30)
    return img


def i02_vertical_spine(logo, motif) -> Image.Image:
    """Type runs vertically down the left edge; logo centered on right."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), DARK)
    d = ImageDraw.Draw(img)
    vtext(img, 14, 30, "MOGRA ORGANICS · ORGANIC LION'S MANE MUSHROOM POWDER",
          F("Jost.ttf", 2.4, [500]), IIVORY, block_w_mm=100, block_h_mm=3.2)
    big_name(d, 84, 60, ["ORGANIC", "LION'S MANE"], IIVORY, size_mm=15.0,
             gap_mm=1.4, max_w=44)
    lockup_stamp(img, 84, 130, 25, IIVORY)
    fact_ledge(d, 84, 172, IIVORY, lines=("170 G", "34 SERVINGS"))
    place_motif(img, recolor(motif, IIVORY), 84, 194, 44, 26)
    return img


def i03_center_seal(logo, motif) -> Image.Image:
    """Logo inside a circular seal at center; type wrapped around."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), MOON)
    d = ImageDraw.Draw(img)
    for rr in (42.0, 37.0, 32.0):
        d.arc([P(65 - rr), P(94 - rr), P(65 + rr), P(94 + rr)], 180, 360,
              fill=tuple(CLAY2), width=max(2, P(0.3)))
    lockup_stamp(img, 65, 94, 32, CLAY2)
    big_name(d, 65, 152, ["ORGANIC LION'S MANE"], CLAY2, size_mm=13.0, gap_mm=1.4,
             max_w=100)
    fact_ledge(d, 65, 190, CLAY2, lines=("170 G", "34 SERVINGS"))
    return img


def i04_off_edge_type(logo, motif) -> Image.Image:
    """Type runs off left and right edges; logo bottom center."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), SEA)
    d = ImageDraw.Draw(img)
    big_name(d, 65, 50, ["ORGANIC LION'S MANE"], MOON, size_mm=17.0, gap_mm=1.6,
             max_w=126)
    ctext(d, 65, 86, "MUSHROOM POWDER", F("Jost.ttf", 3.2, [500]), MOON,
          tracking_mm=4.0)
    rule(d, 22, 100, 108, MOON, 0.4)
    lockup_stamp(img, 65, 130, 28, MOON)
    fact_ledge(d, 65, 156, MOON)
    place_motif(img, recolor(motif, MOON), 65, 190, 60, 34)
    return img


def i05_diagonal_split(logo, motif) -> Image.Image:
    """Diagonal split corner-to-corner; logo on the dark half."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), CLAY2)
    d = ImageDraw.Draw(img)
    d.polygon([(P(0), P(0)), (P(130), P(0)), (P(130), P(210)), (P(0), P(70))],
              fill=BRICK)
    lockup_stamp(img, 76, 125, 22, CLAY2)
    big_name(d, 70, 162, ["ORGANIC LION'S MANE"], CLAY2, size_mm=11.0, gap_mm=1.4,
             max_w=60)
    fact_ledge(d, 70, 194, CLAY2, lines=("170 G", "34 SERVINGS"))
    place_motif(img, recolor(motif, CLAY2), 70, 188, 30, 18)
    return img


def i06_drawn_circle(logo, motif) -> Image.Image:
    """Hand-drawn circle around logo; type inside."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), IVY)
    d = ImageDraw.Draw(img)
    d.ellipse([P(22), P(30), P(108), P(116)], outline=tuple(IIVORY),
              width=max(2, P(0.5)))
    d.ellipse([P(28), P(36), P(102), P(110)], outline=tuple(IIVORY),
              width=max(2, P(0.2)))
    lockup_stamp(img, 65, 72, 36, IIVORY)
    big_name(d, 65, 126, ["ORGANIC", "LION'S MANE"], IIVORY, size_mm=13.0,
             gap_mm=1.2, max_w=92)
    fact_ledge(d, 65, 164, IIVORY)
    place_motif(img, recolor(motif, IIVORY), 65, 190, 52, 30)
    return img


def i07_asymmetric_corner(logo, motif) -> Image.Image:
    """Logo top-left small; type justified right, large. (Ink was the ground
    colour before - the logo and headline were invisible; now MOON on PLUM2.)"""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), PLUM2)
    d = ImageDraw.Draw(img)
    lockup_stamp(img, 30, 34, 20, MOON)
    rule(d, 10, 64, 50, MOON, 0.3)
    big_name(d, 88, 56, ["ORGANIC", "LION'S MANE"], MOON, size_mm=16.0,
             gap_mm=1.8, max_w=80)
    ctext(d, 88, 98, "MUSHROOM POWDER", F("Jost.ttf", 3.0, [500]), MOON,
          tracking_mm=3.2)
    fact_ledge(d, 88, 122, MOON, lines=("170 G", "34 SERVINGS", "5 G PER SCOOP"))
    place_motif(img, recolor(motif, MOON), 88, 158, 48, 28)
    return img


def i08_logo_in_shape(logo, motif) -> Image.Image:
    """Logo reversed out of a dark rounded rect in center. (Reverse-out means
    the ground colour on IVY - the previous IVY-on-IVY stamp was invisible.)"""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), MIST)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([P(26), P(62), P(104), P(130)], radius=P(10), fill=IVY)
    lockup_stamp(img, 65, 96, 32, MIST)
    big_name(d, 65, 146, ["ORGANIC LION'S MANE"], IVY, size_mm=14.0, gap_mm=1.6,
             max_w=92)
    fact_ledge(d, 65, 184, IVY, lines=("170 G", "34 SERVINGS", "5 G PER SCOOP"))
    place_motif(img, recolor(motif, IVY), 65, 194, 40, 24)
    return img


def i09_curved_arcs(logo, motif) -> Image.Image:
    """Type on top and bottom arcs; logo center."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OBSIDIAN)
    d = ImageDraw.Draw(img)
    for rr in (28.0, 24.0):
        d.arc([P(65 - rr), P(44 - rr), P(65 + rr), P(44 + rr)], 190, 350,
              fill=tuple(IIVORY), width=max(2, P(0.3)))
        d.arc([P(65 - rr), P(166 - rr), P(65 + rr), P(166 + rr)], 10, 170,
              fill=tuple(IIVORY), width=max(2, P(0.3)))
    lockup_stamp(img, 65, 104, 31, IIVORY)
    big_name(d, 65, 158, ["ORGANIC LION'S MANE"], IIVORY, size_mm=12.0,
             gap_mm=1.4, max_w=100)
    fact_ledge(d, 65, 196, IIVORY, lines=("170 G", "34 SERVINGS"))
    return img


def i10_logo_hero(logo, motif) -> Image.Image:
    """Logo center-right, large; type left-aligned bottom."""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), OCHRE)
    d = ImageDraw.Draw(img)
    lockup_stamp(img, 92, 70, 38, CEDAR2)
    big_name(d, 42, 126, ["ORGANIC LION'S MANE"], CEDAR2, size_mm=12.0,
             gap_mm=1.6, max_w=60)
    fact_ledge(d, 42, 164, CEDAR2, lines=("170 G", "34 SERVINGS", "5 G PER SCOOP"))
    place_motif(img, recolor(motif, CEDAR2), 92, 190, 44, 28)
    return img


BAG_FRONTS.update({
    "i01_logo_monument": i01_logo_monument,
    "i02_vertical_spine": i02_vertical_spine,
    "i03_center_seal": i03_center_seal,
    "i04_off_edge_type": i04_off_edge_type,
    "i05_diagonal_split": i05_diagonal_split,
    "i06_drawn_circle": i06_drawn_circle,
    "i07_asymmetric_corner": i07_asymmetric_corner,
    "i08_logo_in_shape": i08_logo_in_shape,
    "i09_curved_arcs": i09_curved_arcs,
    "i10_logo_hero": i10_logo_hero,
})


# ── CANISTER wrap fronts (5) — half wrap 114.65 x 120 mm, safe arc x24..91 ──

def can_06_wall_of_type(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    ctext(d, 57.5, 13, "MOGRA ORGANICS", F("Inter.ttf", 2.6, [14, 700]), INK,
          tracking_mm=2.0)
    rule(d, 30, 17, 85, INK, 0.4)
    organic_seal(img, 84.5, 12.5, 6.4)
    headline(d, 57.5, 32, ["LION'S MANE"], size_mm=12.8, color=INK, line_gap_mm=14.0,
             max_w_mm=66)
    headline(d, 57.5, 45, ["MUSHROOM", "POWDER"], size_mm=9.0, color=INK,
             line_gap_mm=10.2, max_w_mm=66)
    ctext(d, 57.5, 68, "ORGANIC", F("Inter.ttf", 2.5, [14, 700]), FOREST, tracking_mm=2.6)
    rule(d, 30, 72, 85, INK, 0.4)
    ctext(d, 57.5, 78, "GENTLY DRIED AND MILLED FOR A", F("Inter.ttf", 2.2, [14, 400]),
          INK, tracking_mm=0.4)
    ctext(d, 57.5, 82.5, "SMOOTH DAILY RITUAL CUP.", F("Inter.ttf", 2.2, [14, 400]),
          INK, tracking_mm=0.4)
    icon_row(d, 57.5, 92, 2.5, 7.6, INK, disc=KRAFT)
    value_capsule(img, CAN_HALF, 57.5, 105, 66, 11, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 57.5, 116, "170 G (6 OZ)", F("Inter.ttf", 2.2, [14, 600]), INK,
          tracking_mm=1.2)
    return img


def can_07_dome_gold(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), FOREST)
    d = ImageDraw.Draw(img)
    dome(d, 57.5, 37, 27, GOLD_A)
    organic_seal(img, 31, 14, 6.6)
    place_motif(img, monogram(logo), 57.5, 23, 22, 13)
    headline(d, 57.5, 50, ["LION'S MANE"], size_mm=10.6, color=CREAM, line_gap_mm=12.0,
             max_w_mm=67)
    ctext(d, 57.5, 62, "MUSHROOM POWDER", F("Inter.ttf", 2.8, [14, 700]), GOLD_A,
          tracking_mm=2.6)
    place_motif(img, recolor(motif, CREAM), 57.5, 81, 48, 26)
    icon_row(d, 57.5, 97, 2.4, 7.4, CREAM, disc=FOREST)
    value_capsule(img, CAN_HALF, 57.5, 109, 66, 11, FACTS, bg=GOLD_A, fg=FOREST,
                  sep=(150, 118, 44))
    ctext(d, 57.5, 117.5, "MOGRA ORGANICS", F("Inter.ttf", 2.1, [14, 600]), CREAM,
          tracking_mm=1.6)
    return img


def can_08_stamp_roll(logo, motif) -> Image.Image:
    import math
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    ctext(d, 57.5, 12, "MOGRA ORGANICS", F("Inter.ttf", 2.5, [14, 700]), INK,
          tracking_mm=1.8)
    organic_seal(img, 84.5, 12.5, 6.2)
    bw = 62.0
    b = Image.new("RGBA", (P(bw), P(bw)), (0, 0, 0, 0))
    bd = ImageDraw.Draw(b)
    c0 = bw / 2
    bd.ellipse([P(1.5), P(1.5), P(bw - 1.5), P(bw - 1.5)], outline=INK + (255,),
               width=max(2, P(0.8)))
    bd.ellipse([P(4.5), P(4.5), P(bw - 4.5), P(bw - 4.5)], outline=FOREST + (255,),
               width=max(2, P(0.5)))
    for ang in range(0, 360, 12):
        px = c0 + 30.4 * math.cos(math.radians(ang))
        py = c0 + 30.4 * math.sin(math.radians(ang))
        bd.ellipse([P(px - 1.5), P(py - 1.5), P(px + 1.5), P(py + 1.5)], fill=KRAFT + (255,))
    place_motif(b, monogram(logo), c0, 16, 20, 12)
    ctext(bd, c0, 25, "ORGANIC", F("Inter.ttf", 2.2, [14, 700]), FOREST, tracking_mm=1.8)
    headline(bd, c0, 34, ["LION'S"], size_mm=7.4, color=INK, line_gap_mm=8.6, max_w_mm=40)
    headline(bd, c0, 42.5, ["MANE"], size_mm=7.4, color=INK, line_gap_mm=8.6, max_w_mm=40)
    ctext(bd, c0, 50.5, "MUSHROOM POWDER", F("Inter.ttf", 2.0, [14, 600]), FOREST,
          tracking_mm=1.2)
    ctext(bd, c0, 55.5, "170 G (6 OZ)", F("Inter.ttf", 1.8, [14, 500]), FOREST,
          tracking_mm=0.8)
    rot_paste(img, b, 57.5, 54, -8)
    ctext(d, 57.5, 92, "GENTLY DRIED - SMOOTH - EARTHY", F("Inter.ttf", 2.1, [14, 600]),
          INK, tracking_mm=0.8)
    value_capsule(img, CAN_HALF, 57.5, 105, 66, 11, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 57.5, 116.5, "STORE COOL & DRY - RESEAL AFTER USE",
          F("Inter.ttf", 2.0, [14, 600]), INK, tracking_mm=0.6)
    return img


def can_09_edge_stripe(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), CREAM)
    d = ImageDraw.Draw(img)
    d.rectangle([P(24), 0, P(33), P(CAN_H)], fill=FOREST)
    d.rectangle([P(33), 0, P(36), P(CAN_H)], fill=GOLD_B)
    d.rectangle([P(79), 0, P(82), P(CAN_H)], fill=GOLD_B)
    d.rectangle([P(82), 0, P(91), P(CAN_H)], fill=FOREST)
    vtext(img, 26.3, 26, "EST. MMXXVI", F("Inter.ttf", 2.2, [14, 600]), CREAM,
          block_w_mm=52, block_h_mm=3.4)
    vtext(img, 84.4, 26, "MOGRA ORGANICS", F("Inter.ttf", 2.2, [14, 600]), CREAM,
          block_w_mm=44, block_h_mm=3.4)
    ctext(d, 57.5, 22, "ORGANIC", F("Inter.ttf", 2.6, [14, 700]), FOREST, tracking_mm=2.8)
    headline(d, 57.5, 34, ["LION'S"], size_mm=9.2, color=INK, line_gap_mm=10.4,
             max_w_mm=41)
    headline(d, 57.5, 45, ["MANE"], size_mm=9.2, color=INK, line_gap_mm=10.4,
             max_w_mm=41)
    ctext(d, 57.5, 54.5, "MUSHROOM POWDER", F("Inter.ttf", 2.2, [14, 700]), FOREST,
          tracking_mm=1.4)
    rule(d, 43, 59, 72, SAGE, 0.4)
    place_motif(img, motif, 57.5, 73, 36, 24)
    ctext(d, 57.5, 92, "170 G (6 OZ)", F("Anton.ttf", 4.2), INK)
    value_capsule(img, CAN_HALF, 57.5, 104, 41, 9.5,
                  [("5 g", "PER SERVING"), ("34", "SERVINGS")],
                  bg=FOREST, fg=CREAM, sep=(96, 116, 96))
    ctext(d, 57.5, 115.5, "1 SCOOP DAILY", F("Inter.ttf", 2.0, [14, 600]), FOREST,
          tracking_mm=1.2)
    return img


def can_10_concentric(logo, motif) -> Image.Image:
    img = Image.new("RGB", (P(CAN_HALF), P(CAN_H)), KRAFT)
    d = ImageDraw.Draw(img)
    ctext(d, 57.5, 12, "MOGRA ORGANICS", F("Inter.ttf", 2.5, [14, 700]), INK,
          tracking_mm=1.8)
    organic_seal(img, 84.5, 12.5, 6.2)
    d.ellipse([P(24.5), P(27), P(90.5), P(93)], fill=FOREST)
    d.ellipse([P(29.5), P(32), P(85.5), P(88)], outline=CREAM, width=max(2, P(0.5)))
    d.ellipse([P(36.5), P(39), P(78.5), P(81)], outline=GOLD_A, width=max(2, P(0.4)))
    d.ellipse([P(43), P(45.5), P(72), P(74.5)], outline=CREAM, width=max(2, P(0.35)))
    roundel(img, logo, 57.5, 48, 7.5, field=WHITE, ring=None)
    ctext(d, 57.5, 61.5, "LION'S MANE", F("Anton.ttf", 6.4), CREAM)
    ctext(d, 57.5, 68, "MUSHROOM POWDER", F("Inter.ttf", 2.1, [14, 700]), CREAM,
          tracking_mm=1.8)
    ctext(d, 57.5, 77, "170 G (6 OZ)", F("Inter.ttf", 2.1, [14, 600]), GOLD_A,
          tracking_mm=1.0)
    ctext(d, 57.5, 97, "GENTLY DRIED - MILLED FOR A DAILY RITUAL",
          F("Inter.ttf", 2.0, [14, 400]), INK, tracking_mm=0.6)
    value_capsule(img, CAN_HALF, 57.5, 107, 66, 10, FACTS, bg=FOREST, fg=CREAM,
                  sep=(96, 116, 96))
    ctext(d, 57.5, 117.5, "STORE COOL & DRY", F("Inter.ttf", 2.0, [14, 600]), INK,
          tracking_mm=1.2)
    return img


CAN_FRONTS = {
    "06_wall_of_type": can_06_wall_of_type,
    "07_dome_gold": can_07_dome_gold,
    "08_stamp_roll": can_08_stamp_roll,
    "09_edge_stripe": can_09_edge_stripe,
    "10_concentric": can_10_concentric,
}


# ── design registry (title/desc/back colours per design) ────────────────────



# ── bag series J: OPERATOR CONCEPTS (2026-10-19) ────────────────────────────
#
# The two directions the operator supplied as concept sheets — "01 Olive + Kraft"
# and "02 Botanical Luxe" — rebuilt for the Lion's Mane 6 oz pouch.
#
# Fidelity notes (deliberate, not accidental):
#   * Hero art is the operator's OWN Hericium photograph
#     (assets/brand/hericium_source.jpg, cropped from IMG20240320001655.jpg),
#     re-plated as an ink illustration. The shipped motif_lionsmane.png is a
#     button mushroom (Agaricus) — it is NOT Hericium, so it is not used here.
#   * The plate is flat-fielded first (the photo of a printed label has its own
#     lighting gradient) and then ramped ground→body→shadow, so the label field
#     lands exactly on the bag colour and the art dissolves into the stock.
#   * Back panels carry the REAL label data from the current product label
#     (1000 mg scoop, ~170 servings, Mogran Organics 2442 S Collins St) rather
#     than the T2 Holdings placeholder used by the bulk back renderer.

J_KRAFT = (203, 171, 128)
J_OLIVE = (95, 106, 60)
J_OLIVE_D = (72, 82, 46)
J_INK = (54, 48, 32)
J_FOREST = (44, 64, 46)
J_CREAM = (243, 238, 226)
J_SOURCE = Path(__file__).resolve().parent / "assets" / "brand" / "hericium_source.jpg"
_PLATE_CACHE: Dict[tuple, Image.Image] = {}


def _smoothstep(e0: float, e1: float, x):
    t = np.clip((x - e0) / max(1e-6, (e1 - e0)), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def hericium_plate(ground, body, shadow, *, flat: float = 1.0) -> Image.Image:
    """Turn the operator's Hericium photograph into a printed plate that sits on
    `ground`: the label field dissolves into the stock, the body reads `body`,
    and the strand shadows read `shadow`."""
    key = (tuple(ground), tuple(body), tuple(shadow), round(flat, 3))
    cached = _PLATE_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    im = Image.open(J_SOURCE).convert("RGB")
    im = im.resize((im.width * 2, im.height * 2), Image.LANCZOS)
    g = np.asarray(im.convert("L"), dtype=np.float32) / 255.0

    # flat-field: the crop is a PHOTOGRAPH OF A PRINTED LABEL, so it carries the
    # label's own lighting gradient. Divide it out or the plate shows a rectangle.
    bg = Image.fromarray((g * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(im.width / 6.0))
    b = np.asarray(bg, dtype=np.float32) / 255.0
    b = np.maximum(b, 1e-3)
    # pin the paper field to exactly 1.0 so it maps onto the bag colour
    ring = np.concatenate([b[:24].ravel(), b[-24:].ravel(), b[:, :24].ravel(), b[:, -24:].ravel()])
    b = b / max(float(np.median(ring)), 1e-3)
    t = np.clip(g / b * flat, 0.0, 1.12)
    t = np.clip((t - 0.5) * 1.06 + 0.5, 0.0, 1.10)

    body_t = _smoothstep(0.30, 0.93, t) * (1.0 - _smoothstep(0.955, 1.03, t))
    col = (np.array(shadow, dtype=np.float32)[None, None]
           + body_t[..., None] * (np.array(body, dtype=np.float32) - np.array(shadow, dtype=np.float32))[None, None])
    edge = _smoothstep(1.0, 1.09, t)[..., None]
    col = col * (1.0 - edge) + np.array(ground, dtype=np.float32)[None, None] * edge

    # feather the crop border into the stock (the plate is a rectangle)
    h, w = t.shape
    yy, xx = np.mgrid[0:h, 0:w]
    fe = np.clip(np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / (w * 0.035), 0, 1)
    # pin the paper field onto the stock exactly: measure the plate's own field
    # colour and shift every field pixel by the residual to the bag colour
    ring = np.concatenate([col[:30].reshape(-1, 3), col[-30:].reshape(-1, 3),
                           col[:, :30].reshape(-1, 3), col[:, -30:].reshape(-1, 3)])
    field = np.median(ring, axis=0)
    delta = np.array(ground, dtype=np.float32) - field
    dist = np.abs(col - field[None, None]).mean(axis=2)
    near = np.exp(-(dist / 11.0) ** 2)[..., None]
    col = col + delta[None, None] * near
    col = col * fe[..., None] + np.array(ground, dtype=np.float32)[None, None] * (1 - fe[..., None])
    plate = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), "RGB")
    _PLATE_CACHE[key] = plate
    return plate.copy()


def hericium_plaque(ground, body, shadow, *, feather: float = 0.16) -> Image.Image:
    """Feathered elliptical plaque of the same photograph for a dark ground: the
    art is a soft-edged printed panel rather than a hard rectangle."""
    key = ("plaque", tuple(ground), tuple(body), tuple(shadow), round(feather, 3))
    cached = _PLATE_CACHE.get(key)
    if cached is not None:
        return cached.copy()
    base = hericium_plate(body, body, shadow).convert("RGB")
    g = np.asarray(base.convert("L"), dtype=np.float32) / 255.0
    h, w = g.shape
    yy, xx = np.mgrid[0:h, 0:w]
    nx = (xx - w * 0.5) / (w * 0.52)
    ny = (yy - h * 0.5) / (h * 0.54)
    r = np.sqrt(nx ** 2 + ny ** 2)
    a = np.clip((1.02 - r) / feather, 0, 1)
    a = a * a * (3 - 2 * a)
    out = np.zeros((h, w, 4), dtype=np.uint8)
    out[..., :3] = np.array(base, dtype=np.uint8)
    out[..., 3] = (a * 250).astype(np.uint8)
    img = Image.fromarray(out, "RGBA")
    _PLATE_CACHE[key] = img
    return img.copy()


def usda_roundel(canvas, cx, cy, r, ink=J_OLIVE_D, paper=WHITE) -> None:
    """White USDA-style roundel: double ring, leaf, USDA, ORGANIC."""
    d = ImageDraw.Draw(canvas)
    d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=tuple(paper))
    d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], outline=tuple(ink), width=max(2, P(0.55)))
    d.ellipse([P(cx - r * 0.86), P(cy - r * 0.86), P(cx + r * 0.86), P(cy + r * 0.86)],
              outline=tuple(ink), width=max(1, P(0.18)))
    draw_cert_icon(d, "organic_sprout", P(cx), P(cy - r * 0.46), P(r * 0.26), ink=ink)
    d.text((P(cx), P(cy + r * 0.10)), "USDA", font=F("Anton.ttf", r * 0.30),
           fill=tuple(ink), anchor="mm")
    d.text((P(cx), P(cy + r * 0.52)), "ORGANIC", font=F("Inter.ttf", r * 0.20, [14, 700]),
           fill=tuple(ink), anchor="mm")


def _seal_line(d) -> None:
    """Heat-seal / zipper impression across the head of the pouch."""
    for y, w, c in ((24.0, 0.45, (176, 146, 104)), (26.2, 0.22, (188, 158, 116)),
                    (27.4, 0.22, (188, 158, 116))):
        d.line([(0, P(y)), (P(BAG_W), P(y))], fill=c, width=max(1, P(w)))


def _leaf(d, x, y, ln, wd, ang, color) -> None:
    """One lens-shaped leaf on a stem, drawn as a filled polygon."""
    pts_a, pts_b = [], []
    for i in range(11):
        u = i / 10.0
        bx = x + math.cos(ang) * ln * u
        by = y + math.sin(ang) * ln * u
        off = wd * math.sin(math.pi * u) * 0.5
        nx, ny = -math.sin(ang) * off, math.cos(ang) * off
        pts_a.append((bx + nx, by + ny))
        pts_b.append((bx - nx, by - ny))
    d.polygon(pts_a + pts_b[::-1], fill=tuple(color))
    d.line([(x, y), (x + math.cos(ang) * ln, y + math.sin(ang) * ln)],
           fill=tuple(color), width=max(1, P(0.2)))


def leaf_branch(canvas, cx, cy, height_mm, color, *, flip: bool = False) -> None:
    """Herbal sprig: a curved stem carrying six paired leaves."""
    d = ImageDraw.Draw(canvas)
    h = height_mm
    x0, y0 = P(cx), P(cy + h * 0.5)
    bend = 0.28 * h * (-1 if flip else 1)
    pts = []
    for i in range(25):
        u = i / 24.0
        pts.append((x0 + bend * math.sin(math.pi * u) * (1 if flip else -1) + (P(h * 0.20) if not flip else -P(h * 0.20)) * u,
                    y0 - P(h) * u))
    d.line(pts, fill=tuple(color), width=max(2, P(0.30)))
    for i, u in enumerate((0.22, 0.40, 0.58, 0.74, 0.88)):
        px = x0 + (P(h * 0.20) if not flip else -P(h * 0.20)) * u + bend * math.sin(math.pi * u) * (1 if flip else -1)
        py = y0 - P(h) * u
        ln = P(h * (0.30 - 0.03 * i))
        wd = P(h * (0.16 - 0.015 * i))
        _leaf(d, px, py, ln, wd, math.radians(-145 + (10 * i) * (1 if flip else 1)), color)
        _leaf(d, px, py, ln * 0.92, wd * 0.92, math.radians(-35 - (10 * i)), color)


def j01_olive_kraft(logo, motif) -> Image.Image:
    """Olive + Kraft: kraft stock, tracked serif caps, engraved Hericium plate,
    olive net-weight band, USDA roundel. (Operator concept 01.)"""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), J_KRAFT)
    d = ImageDraw.Draw(img)
    _seal_line(d)

    if LOCKUP is not None:
        lockup_stamp(img, BAG_W / 2, 50.5, 40.0, J_INK)
    else:
        paste_w(img, recolor(logo, J_INK), BAG_W / 2, 50.5, 40.0)

    dy = 69.0
    rule(d, 30, dy, 59, J_OLIVE_D, 0.28)
    rule(d, 71, dy, 100, J_OLIVE_D, 0.28)
    s = P(1.35)
    d.polygon([(P(65), P(dy) - s), (P(65) + s, P(dy)), (P(65), P(dy) + s), (P(65) - s, P(dy))],
              fill=tuple(J_OLIVE_D))

    ctext(d, 65, 78.0, "ORGANIC LION'S MANE", F("PlayfairDisplay.ttf", 5.6, [600]), J_INK,
          tracking_mm=0.95)
    ctext(d, 65, 86.4, "MUSHROOM POWDER", F("PlayfairDisplay.ttf", 3.5, [500]), J_INK,
          tracking_mm=1.55)
    ctext(d, 65, 94.0, "Hericium erinaceus", F("CormorantGaramond-Italic.ttf", 5.0, [500]), J_INK)

    plate = hericium_plate(J_KRAFT, (222, 196, 156), (74, 60, 36)).convert("RGBA")
    paste_w(img, plate, 65, 142.0, 78.0)

    usda_roundel(img, 27.5, 175.0, 8.2, J_OLIVE_D)

    d.rectangle([0, P(184.5), P(BAG_W), P(196.5)], fill=J_OLIVE)
    rule(d, 0, 184.5, BAG_W, J_OLIVE_D, 0.5)
    ctext(d, 65, 190.5, "NET WT 6 OZ (170 g)", F("PlayfairDisplay.ttf", 3.4, [600]), J_CREAM,
          tracking_mm=0.75)
    ctext(d, 65, 203.0, "MOGRA ORGANICS  ·  EST. 2023", F("Inter.ttf", 1.9, [14, 500]), J_INK,
          tracking_mm=1.1)
    return img


def j02_botanical_luxe(logo, motif) -> Image.Image:
    """Botanical Luxe: bone stock, oversized lowercase serif, forest botanical
    sweep carrying the Hericium plate, vegan/non-GMO footer. (Concept 02.)"""
    img = Image.new("RGB", (P(BAG_W), P(BAG_H)), J_CREAM)
    d = ImageDraw.Draw(img)

    # ── identity: the real lockup, top-left
    if LOCKUP is not None:
        lockup_stamp(img, 24.0, 23.0, 27.0, J_FOREST)
    else:
        paste_w(img, recolor(logo, J_FOREST), 24.0, 23.0, 27.0)

    # ── botanical sweep (bottom-right)
    cx, cy, r = 155.0, 255.0, 135.0
    d.ellipse([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], fill=J_FOREST)
    d.arc([P(cx - r), P(cy - r), P(cx + r), P(cy + r)], 180, 270,
          fill=(150, 140, 96), width=max(2, P(0.55)))

    leaf_branch(img, 112.0, 124.0, 32.0, (196, 200, 168), flip=True)

    paste_w(img, hericium_plaque(J_FOREST, (246, 240, 222), (30, 48, 32), feather=0.12),
            108.0, 167.0, 53.0)

    # ── editorial type block (left)
    ltext(d, 13.5, 44.0, "organic", F("CormorantGaramond-Italic.ttf", 8.2, [500]), J_OLIVE)
    ltext(d, 12.5, 61.5, "lion's", F("PlayfairDisplay.ttf", 21.0, [500]), J_FOREST)
    ltext(d, 12.5, 79.5, "mane", F("PlayfairDisplay.ttf", 21.0, [500]), J_FOREST)
    ltext(d, 13.5, 94.0, "MUSHROOM POWDER", F("Jost.ttf", 3.3, [500]), J_FOREST)
    ltext(d, 13.5, 101.0, "Hericium erinaceus", F("CormorantGaramond-Italic.ttf", 4.9, [500]), J_FOREST)

    # ── footer (on the sweep: cream ink inside the green)
    usda_roundel(img, 23.0, 182.0, 7.4, J_FOREST, paper=(250, 247, 238))
    ltext(d, 46.0, 178.6, "VEGAN", F("Jost.ttf", 2.6, [600]), J_CREAM)
    ltext(d, 46.0, 183.8, "NON-GMO", F("Jost.ttf", 2.6, [600]), J_CREAM)
    ltext(d, 46.0, 195.0, "NET WT 6 OZ (170 g)", F("Jost.ttf", 2.7, [500]), J_CREAM)
    return img


BACK_J_USE = [
    "Mix one scoop (approx. 1000 mg) into tea, coffee,",
    "or your favourite drink once daily for two weeks,",
    "then adjust the dose if needed.",
]
BACK_J_DETAIL = [
    "Lion's Mane (Hericium erinaceus) has been used for over 2000",
    "years in the mountainous regions of Asia. Our powder is milled",
    "from the fruiting bodies of organic Hericium erinaceus and is",
    "always free of additives, fillers and pesticides.",
]


def _cert_badge(d, x, y, w, h, label, ink, paper):
    d.rounded_rectangle([P(x), P(y), P(x + w), P(y + h)], radius=P(1.2),
                        fill=tuple(paper), outline=tuple(ink), width=max(1, P(0.25)))
    d.text((P(x + w / 2), P(y + h / 2)), label, font=F("Inter.ttf", 1.75, [14, 700]),
           fill=tuple(ink), anchor="mm")


def render_back_j(spec: Dict, W: float, H: float, logo: Optional[Image.Image] = None) -> Image.Image:
    """Back panel for the J (operator-concept) series, carrying the real label
    data of the current Mogra Organics Lion's Mane pouch."""
    ground = tuple(spec.get("ground_b", spec["ground"]))
    ink = tuple(spec.get("ink_b", J_INK))
    img = Image.new("RGB", (P(W), P(H)), ground)
    d = ImageDraw.Draw(img)
    plate_paper = J_CREAM if spec.get("plate", True) else ground
    d.rounded_rectangle([P(6), P(7), P(W - 6), P(H - 8)], radius=P(2.2),
                        fill=plate_paper, outline=J_OLIVE_D, width=max(2, P(0.4)))

    if LOCKUP is not None:
        lockup_stamp(img, W / 2, 22.0, 27.0, J_INK)

    ctext(d, W / 2, 38.0, "ORGANIC LION'S MANE", F("PlayfairDisplay.ttf", 4.6, [600]), ink,
          tracking_mm=0.7)
    ctext(d, W / 2, 43.6, "MUSHROOM POWDER  ·  170 g (6.0 oz)", F("Inter.ttf", 2.2, [14, 600]),
          ink, tracking_mm=0.8)

    fx, fy, fw, fh = 12.0, 48.0, W - 24.0, 41.0
    d.rectangle([P(fx), P(fy), P(fx + fw), P(fy + fh)], fill=WHITE, outline=(0, 0, 0),
                width=max(2, P(0.45)))
    yy = fy + 2.4
    ltext(d, fx + 2.2, yy + 1.6, "Supplement Facts", F("PlayfairDisplay.ttf", 5.4, [700]), (0, 0, 0))
    yy += 6.4
    rule(d, fx + 2, yy, fx + fw - 2, (0, 0, 0), 0.8)
    yy += 3.0
    ltext(d, fx + 2, yy, "Serving Size: 1 scoop (approx. 1000 mg)", F("Inter.ttf", 2.05, [14, 600]), (0, 0, 0))
    yy += 3.0
    ltext(d, fx + 2, yy, "Servings Per Container: approx. 170", F("Inter.ttf", 2.05, [14, 400]), (0, 0, 0))
    yy += 2.6
    d.rectangle([P(fx), P(yy), P(fx + fw), P(yy + 0.8)], fill=(0, 0, 0))
    yy += 2.9
    ltext(d, fx + 2, yy, "Amount Per Serving", F("Inter.ttf", 1.95, [14, 700]), (0, 0, 0))
    rtext(d, fx + fw - 2, yy, "% Daily Value", F("Inter.ttf", 1.95, [14, 700]), (0, 0, 0))
    yy += 2.3
    rule(d, fx + 2, yy, fx + fw - 2, (0, 0, 0), 0.35)
    yy += 2.9
    ltext(d, fx + 2, yy, "Total Carbohydrate", F("Inter.ttf", 2.05, [14, 400]), (0, 0, 0))
    rtext(d, fx + fw - 2, yy, "<1 g   <1%", F("Inter.ttf", 2.05, [14, 400]), (0, 0, 0))
    yy += 3.4
    ltext(d, fx + 2, yy, "Organic Lion's Mane (fruiting bodies)", F("Inter.ttf", 2.05, [14, 700]), (0, 0, 0))
    rtext(d, fx + fw - 2, yy, "1000 mg   **", F("Inter.ttf", 2.05, [14, 400]), (0, 0, 0))
    yy += 3.0
    ltext(d, fx + 2, yy, "(Hericium erinaceus)", F("Inter.ttf", 1.9, [14, 400]), (60, 60, 60))
    yy += 2.4
    d.rectangle([P(fx), P(yy), P(fx + fw), P(yy + 0.8)], fill=(0, 0, 0))
    yy += 2.6
    ltext(d, fx + 2, yy, "** Daily Value not established.", F("Inter.ttf", 1.85, [14, 400]), (60, 60, 60))

    yy = fy + fh + 5.0
    ltext(d, 12, yy, "Other Ingredients: None.", F("Inter.ttf", 2.15, [14, 600]), ink)
    yy += 5.4
    for line in BACK_J_DETAIL:
        ltext(d, 12, yy, line, F("Inter.ttf", 1.95, [14, 400]), ink)
        yy += 3.2
    yy += 2.2
    ltext(d, 12, yy, "Suggested Use", F("Inter.ttf", 2.15, [14, 700]), ink)
    yy += 3.6
    for line in BACK_J_USE:
        ltext(d, 12, yy, line, F("Inter.ttf", 1.95, [14, 400]), ink)
        yy += 3.1
    yy += 1.6
    ltext(d, 12, yy, "Store in a cool, dark, dry place. Warning: not intended for children.",
          F("Inter.ttf", 1.85, [14, 400]), ink)
    yy += 2.9
    ltext(d, 12, yy, "Not intended to diagnose, treat, cure or prevent any disease.",
          F("Inter.ttf", 1.85, [14, 400]), ink)
    yy += 4.4
    ltext(d, 12, yy, "Distributed by Mogran Organics", F("Inter.ttf", 1.95, [14, 700]), ink)
    yy += 2.9
    ltext(d, 12, yy, "2442 S Collins St, Ste 108 PMB 1157, Arlington TX 76014, USA",
          F("Inter.ttf", 1.8, [14, 400]), ink)

    cy = H - 54.0
    _cert_badge(d, 12.0, cy, 22.0, 9.4, "HALAL", J_OLIVE_D, WHITE)
    _cert_badge(d, 36.0, cy, 24.0, 9.4, "KOSHER", J_OLIVE_D, WHITE)
    _cert_badge(d, 62.0, cy, 26.0, 9.4, "ISO 9001", J_OLIVE_D, WHITE)
    _cert_badge(d, 90.0, cy, 28.0, 9.4, "ISO 22000", J_OLIVE_D, WHITE)

    qy = H - 40.0
    draw_qr(d, d, 12.0, qy, 16.0, "https://mograorganics.com/organic-lions-mane")
    draw_upc(d, 32.0, qy + 1.0, W - 46.0, 13.0, upc_a_placeholder())
    d.text((P(32.0 + (W - 46.0) / 2), P(qy + 24.0)), "LOT MO-LM-2601   ·   BEST BY 01-2028   ·   X00MOGRA-LM",
           font=F("Inter.ttf", 1.7, [14, 500]), fill=ink, anchor="mm")

    d.text((P(W / 2), P(H - 10.5)),
           "*These statements have not been evaluated by the FDA. KEEP OUT OF REACH OF CHILDREN.",
           font=F("Inter.ttf", 1.6, [14, 400]), fill=ink, anchor="mm")
    return img


BAG_FRONTS.update({
    "j01_olive_kraft": j01_olive_kraft,
    "j02_botanical_luxe": j02_botanical_luxe,
})


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
        "01_forest_bold": dict(kind="bag", ground=FOREST, ground_b=FOREST, ink_b=CREAM),
        "02_sticker_fun": dict(kind="bag", ground=CREAM, ground_b=CREAM, ink_b=FOREST),
        "03_midnight_luxe": dict(kind="bag", ground=INK, ground_b=INK, ink_b=CREAM),
        "04_kilim_arch": dict(kind="bag", ground=CREAM, ground_b=CREAM, ink_b=FOREST),
        "05_split_duo": dict(kind="bag", ground=CREAM, ground_b=FOREST, ink_b=CREAM),
        "b06_etched_heritage": dict(kind="bag", ground=IVORY, ground_b=IVORY, ink_b=FOREST),
        "b07_etched_noir": dict(kind="bag", ground=INK, ground_b=INK, ink_b=CREAM),
        "b08_foil_monogram": dict(kind="bag", ground=CREAM, ground_b=CREAM, ink_b=FOREST),
        "b09_kraft_plate": dict(kind="bag", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "b10_botanical_spine": dict(kind="bag", ground=(146, 172, 128), ground_b=(146, 172, 128), ink_b=FOREST),
        "e01_stone_heritage": dict(kind="bag", ground=STONE, ground_b=STONE, ink_b=MOSS),
        "e02_moss_arc": dict(kind="bag", ground=MOSS, ground_b=MOSS, ink_b=LINEN2),
        "e03_clay_bands": dict(kind="bag", ground=CLAY, ground_b=CLAY, ink_b=LINEN2),
        "e04_sand_hero": dict(kind="bag", ground=SAND, ground_b=SAND, ink_b=OLIVE_D),
        "e05_bark_editorial": dict(kind="bag", ground=BARK, ground_b=BARK, ink_b=LINEN2),
        "e06_olive_badge": dict(kind="bag", ground=OLIVE_D, ground_b=OLIVE_D, ink_b=LINEN2),
        "e07_oat_split": dict(kind="bag", ground=OAT, ground_b=OAT, ink_b=ESPRESSO),
        "e08_slate_formal": dict(kind="bag", ground=SLATE, ground_b=SLATE, ink_b=LINEN2),
        "e09_taupe_watermark": dict(kind="bag", ground=TAUPE, ground_b=TAUPE, ink_b=ESPRESSO),
        "e10_kelp_luxe": dict(kind="bag", ground=KELP, ground_b=KELP, ink_b=LINEN2),
        "f01_porcelain_type": dict(kind="bag", ground=ICE, ground_b=ICE, ink_b=FOREST2),
        "f02_cedar_seal": dict(kind="bag", ground=CEDAR, ground_b=CEDAR, ink_b=LINEN2),
        "f03_linen_ledger": dict(kind="bag", ground=OAT2, ground_b=OAT2, ink_b=ESPRESSO),
        "f04_wheat_minimal": dict(kind="bag", ground=WHEAT2, ground_b=WHEAT2, ink_b=ESPRESSO),
        "f05_pistachio_contour": dict(kind="bag", ground=PIST, ground_b=PIST, ink_b=FOREST2),
        "f06_porcelain_tile": dict(kind="bag", ground=ICE, ground_b=ICE, ink_b=FOREST2),
        "f07_rose_wreath": dict(kind="bag", ground=ROSE, ground_b=ROSE, ink_b=PLUM),
        "f08_granite_stack": dict(kind="bag", ground=GRANITE, ground_b=GRANITE, ink_b=(238, 235, 226)),
        "f09_plum_prescription": dict(kind="bag", ground=PLUM, ground_b=PLUM, ink_b=LINEN2),
        "f10_ice_botanical": dict(kind="bag", ground=ICE, ground_b=ICE, ink_b=FOREST2),
        "g01_ink_sash": dict(kind="bag", ground=INK, ground_b=INK, ink_b=BONE),
        "g02_bone_spill": dict(kind="bag", ground=BONE, ground_b=BONE, ink_b=FOREST2),
        "g03_terra_sun": dict(kind="bag", ground=TERRA, ground_b=TERRA, ink_b=BONE),
        "g04_teal_horizon": dict(kind="bag", ground=TEAL, ground_b=TEAL, ink_b=BONE),
        "g05_olive_identity": dict(kind="bag", ground=OLIVE2, ground_b=OLIVE2, ink_b=BONE),
        "g06_charcoal_banner": dict(kind="bag", ground=CHAR, ground_b=CHAR, ink_b=BONE),
        "g07_slate_halo": dict(kind="bag", ground=SLATE2, ground_b=SLATE2, ink_b=BONE),
        "g08_blush_column": dict(kind="bag", ground=BLUSH, ground_b=BLUSH, ink_b=PLUM),
        "g09_bone_stamp": dict(kind="bag", ground=BONE, ground_b=BONE, ink_b=INK),
        "g10_forest_duo": dict(kind="bag", ground=FOREST2, ground_b=FOREST2, ink_b=BONE),
        "h01_porcelain_monument": dict(kind="bag", ground=PARCHMENT, ground_b=PARCHMENT, ink_b=FOREST3),
        "h02_cedar_tower": dict(kind="bag", ground=CEDAR2, ground_b=CEDAR2, ink_b=PARCHMENT),
        "h03_teal_arc": dict(kind="bag", ground=TEAL2, ground_b=TEAL2, ink_b=PARCHMENT),
        "h04_slate_ticket": dict(kind="bag", ground=SLATE3, ground_b=SLATE3, ink_b=PARCHMENT),
        "h05_forest_crest": dict(kind="bag", ground=FOREST3, ground_b=FOREST3, ink_b=PARCHMENT),
        "h06_rose_slab": dict(kind="bag", ground=ROSE2, ground_b=ROSE2, ink_b=PARCHMENT),
        "h07_ochre_fold": dict(kind="bag", ground=OCHRE, ground_b=OCHRE, ink_b=PARCHMENT),
        "h08_sage_wash": dict(kind="bag", ground=SAGE3, ground_b=SAGE3, ink_b=FOREST3),
        "h09_violet_block": dict(kind="bag", ground=PARCHMENT, ground_b=PARCHMENT, ink_b=VIOLET),
        "h10_monogram_only": dict(kind="bag", ground=BONE, ground_b=BONE, ink_b=CEDAR2),
        "i01_logo_monument": dict(kind="bag", ground=IIVORY, ground_b=IIVORY, ink_b=DARK,
                                  logo_lockup=True),
        "i02_vertical_spine": dict(kind="bag", ground=DARK, ground_b=DARK, ink_b=IIVORY,
                                   logo_lockup=True),
        "i03_center_seal": dict(kind="bag", ground=MOON, ground_b=MOON, ink_b=CLAY2,
                                logo_lockup=True),
        "i04_off_edge_type": dict(kind="bag", ground=SEA, ground_b=SEA, ink_b=MOON,
                                  logo_lockup=True),
        "i05_diagonal_split": dict(kind="bag", ground=CLAY2, ground_b=CLAY2, ink_b=BRICK,
                                   logo_lockup=True),
        "i06_drawn_circle": dict(kind="bag", ground=IVY, ground_b=IVY, ink_b=IIVORY,
                                 logo_lockup=True),
        "i07_asymmetric_corner": dict(kind="bag", ground=PLUM2, ground_b=PLUM2, ink_b=MOON,
                                      logo_lockup=True),
        "i08_logo_in_shape": dict(kind="bag", ground=MIST, ground_b=MIST, ink_b=IVY,
                                  logo_lockup=True),
        "i09_curved_arcs": dict(kind="bag", ground=OBSIDIAN, ground_b=OBSIDIAN, ink_b=IIVORY,
                                logo_lockup=True),
        "i10_logo_hero": dict(kind="bag", ground=OCHRE, ground_b=OCHRE, ink_b=CEDAR2,
                              logo_lockup=True),
        "j01_olive_kraft": dict(kind="bag", ground=J_KRAFT, ground_b=J_KRAFT, ink_b=J_INK,
                                logo_lockup=True, back="j"),
        "j02_botanical_luxe": dict(kind="bag", ground=J_CREAM, ground_b=J_CREAM,
                                   ink_b=J_INK, logo_lockup=True, back="j", plate=False),
        "06_wall_of_type": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "07_dome_gold": dict(kind="canister", ground=FOREST, ground_b=FOREST, ink_b=CREAM),
        "08_stamp_roll": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
        "09_edge_stripe": dict(kind="canister", ground=CREAM, ground_b=CREAM, ink_b=FOREST),
        "10_concentric": dict(kind="canister", ground=KRAFT, ground_b=KRAFT, ink_b=INK),
    }
    for key, th in themes.items():
        specs.append({**th, "key": key, "title": "ORGANIC LION'S MANE",
                      "desc": desc1, "back_lines": common_back,
                      "reseal": ("Press lid closed to seal after each use."
                                 if th["kind"] == "canister" else
                                 "Reseal zipper firmly after each use.")})
    return specs
