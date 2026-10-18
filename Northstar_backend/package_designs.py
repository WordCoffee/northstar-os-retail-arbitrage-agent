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

    # header: wordmark + organic seal
    if logo is not None:
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
        # About Us + the real logo (tinted to the back's ink so it reads on any ground)
        yy += 5.0
        ltext(d, tx, yy, "ABOUT US", f_b, ink)
        yy += 3.9
        for line in ("Mogra Organics makes everyday wellness", "simple: single-ingredient lion's mane,",
                     "dried and milled, nothing added."):
            ltext(d, tx, yy, line, f_s, ink)
            yy += 3.3
        if logo is not None:
            wmr = recolor(wordmark(logo), ink)
            wm2 = wmr.resize((P(24.0), max(2, int(P(24.0) * wmr.height / wmr.width))), Image.LANCZOS)
            img.paste(wm2, (P(tx), P(yy + 1.2)), wm2)
        # RIGHT column
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
        yy += 6.4
        ltext(d, rx, yy, "Distributed Exclusively by:", f_b, ink)
        yy += 4.2
        for line in ("T2 Holdings LLC", "1234 Sample Ave, Suite 100", "Springfield, MO 65801, USA",
                     "Certified Organic by: Example Certifiers, Inc."):
            ltext(d, rx, yy, line, f_s, ink)
            yy += 3.4
        # codes row (white panel on dark grounds)
        qy = H - 40 * sx
        if dark:
            d.rounded_rectangle([P(rx - 3), P(qy - 3), P(right + 3), P(qy + 34)], radius=P(2),
                                fill=WHITE)
        draw_qr(d, d, rx, qy, 17.0, "https://mograorganics.com/organic-lions-mane")
        upc = upc_a_placeholder()
        draw_upc(d, rx + 21, qy + 1, rw - 21, 15.0, upc)
        d.text((P(rx + 21 + (rw - 21) / 2), P(qy + 19.5)), "X00MOGRA-LM",
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
