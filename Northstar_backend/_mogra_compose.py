"""Temp: MOGRA FOREST DUSK compositor v2 — numpy homography warp (no PIL coeffs).

panel (700x1000, RGBA) -> pouch face quad via exact 4-point homography,
bilinear-sampled, composited. Real logo keyed to cream, Playfair/Inter text,
engraved glyph from the render recoloured gold. Iterating; delete after approval.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "data" / "studio_generated" / "44318b36606f4c859487c250d5a0a671.png"
LOGO_SRC = Path(r"C:\Users\T2Hol\Downloads\png")
FONTS = ROOT / "assets" / "fonts"
OUT = ROOT / "data" / "studio_generated" / "mogra_forest_dusk_composed.png"

CREAM = (245, 238, 226)
GOLD_A = (196, 160, 74)
GOLD_B = (214, 158, 62)

QUAD_GREEN = [(124, 455), (558, 452), (568, 1002), (112, 1006)]  # TL TR BR BL
QUAD_CHARC = [(642, 452), (1124, 455), (1116, 1008), (650, 1004)]
BADGE_CENTER = (352, 672)   # model badge circle on the green bag
BADGE_RADIUS = 128          # full cover incl. gold ring + pad
GLYPH_BOX = (292, 590, 452, 740)
PW, PH = 700, 1000


def font(name, size, axes=None):
    f = ImageFont.truetype(str(FONTS / name), size)
    if axes is not None:
        try:
            f.set_variation_by_axes(axes)
        except Exception:
            pass
    return f


def key_cream(img: Image.Image) -> Image.Image:
    a = np.array(img.convert("RGBA")).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mn = np.minimum(np.minimum(r, g), b)
    green = (g > r + 18) & (g > b + 18)
    alpha = np.clip((212 - mn) * 2.6, 0, 255)
    alpha[green] = a[..., 3][green]
    out = a.copy()
    out[..., 3] = alpha
    return Image.fromarray(out.astype("uint8"), "RGBA")


def recolor(img: Image.Image, color) -> Image.Image:
    a = np.array(img).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > r + 18) & (g > b + 18)
    out = a.copy()
    out[..., 0], out[..., 1], out[..., 2] = color
    out[green, 0], out[green, 1], out[green, 2] = a[green, 0], a[green, 1], a[green, 2]
    return Image.fromarray(out.astype("uint8"), "RGBA")


def erase_badge(photo: Image.Image) -> Image.Image:
    """Circular feathered erase of the model badge: ring-median colour from an
    annulus that excludes the badge itself."""
    cx, cy = BADGE_CENTER
    r = BADGE_RADIUS
    x0, y0 = max(0, cx - r - 60), max(0, cy - r - 60)
    x1, y1 = min(photo.width, cx + r + 60), min(photo.height, cy + r + 60)
    arr = np.array(photo)
    band = arr[y0:y1, x0:x1]
    yy, xx = np.mgrid[0:band.shape[0], 0:band.shape[1]]
    dist = np.sqrt((xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2)
    ring = band[(dist >= r + 4) & (dist <= r + 36)]
    color = tuple(int(c) for c in np.median(ring, axis=0))
    alpha = np.clip((r - dist) / 60.0, 0, 1)[..., None]
    patch = np.full_like(band, color).astype(np.float32)
    band[:] = (patch * alpha + band.astype(np.float32) * (1 - alpha)).astype("uint8")
    return Image.fromarray(arr, "RGB")


def centered(draw, y, text, f, fill, tracking=0):
    widths = [draw.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = PW / 2 - total / 2
    for ch, w_ in zip(text, widths):
        draw.text((x, y), ch, font=f, fill=fill, anchor="lm")
        x += w_ + tracking


def fit_font(name, size, axes, text, max_w, draw):
    while size > 18:
        f = font(name, size, axes)
        if draw.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(name, size, axes)


def build_panel(glyph, sku) -> Image.Image:
    panel = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)

    # cream roundel badge, circularly masked: the logo's OWN background colour
    # fills the circle and the mask cuts the rectangle's corners away entirely.
    from PIL import ImageChops  # noqa: PLC0415
    cx, cy, r = PW // 2, 300, 178
    # badge circle colour = the logo-card's own field (sampled from its border
    # band) so the card and the circle are indistinguishable.
    _la = np.array(logo_square.convert("RGB"))
    _edge = np.concatenate([_la[:8].reshape(-1, 3), _la[-8:].reshape(-1, 3),
                            _la[:, :8].reshape(-1, 3), _la[:, -8:].reshape(-1, 3)])
    logo_bg = tuple(int(c) for c in np.median(_edge, axis=0))
    print("badge bg sampled:", logo_bg)
    badge = Image.new("RGBA", (2 * r + 12, 2 * r + 12), (0, 0, 0, 0))
    ImageDraw.Draw(badge).ellipse([6, 6, 2 * r + 6, 2 * r + 6], fill=logo_bg + (255,))
    lock_w = int(2 * r * 0.72)
    lock = logo_square.resize((lock_w, int(lock_w * logo_square.height / logo_square.width)), Image.LANCZOS)
    badge.paste(lock, ((badge.width - lock.width) // 2, (badge.height - lock.height) // 2), lock)
    mask = Image.new("L", badge.size, 0)
    ImageDraw.Draw(mask).ellipse([6, 6, 2 * r + 6, 2 * r + 6], fill=255)
    badge.putalpha(ImageChops.multiply(badge.split()[3], mask))
    panel.paste(badge, (cx - r - 6, cy - r - 6), badge)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=tuple(sku["gold"]) + (255,), width=5)

    # product names
    f_name = fit_font("PlayfairDisplay.ttf", 64, [700], sku["name"], 600, d)
    centered(d, 560, sku["name"], f_name, CREAM)
    f_sub = font("Inter.ttf", 27, [14, 640])
    centered(d, 616, "MUSHROOM POWDER", f_sub, CREAM, tracking=9)

    # engraved mushroom glyph in gold (extracted from the render's badge)
    g_w = 190
    g = glyph.resize((g_w, int(g_w * glyph.height / glyph.width)), Image.LANCZOS)
    g = recolor(g, sku["gold"])
    panel.paste(g, (PW // 2 - g_w // 2, 668), g)

    # footer weight + thin gold rules
    f_foot = font("Inter.ttf", 26, [14, 560])
    centered(d, 942, sku["weight"], f_foot, CREAM)
    d.line([(140, 942), (244, 942)], fill=tuple(sku["gold"]) + (170,), width=2)
    d.line([(PW - 244, 942), (PW - 140, 942)], fill=tuple(sku["gold"]) + (170,), width=2)
    return panel


def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    A = np.array(A, dtype=float)
    _, _, Vt = np.linalg.svd(A)
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def warp_panel(photo: Image.Image, panel: Image.Image, quad) -> Image.Image:
    """Exact 4-point homography: panel -> photo quad, bilinear sampled."""
    src = [(0, 0), (PW, 0), (PW, PH), (0, PH)]
    H = homography(src, list(quad))
    Hinv = np.linalg.inv(H)
    W, Hpx = photo.size
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    m = 4
    x0, x1 = max(0, int(min(xs)) - m), min(W, int(max(xs)) + m)
    y0, y1 = max(0, int(min(ys)) - m), min(Hpx, int(max(ys)) + m)
    gx, gy = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    ones = np.ones_like(gx, dtype=float)
    pts = np.stack([gx.astype(float), gy.astype(float), ones], axis=-1)  # H,W,3
    uv = pts @ Hinv.T
    u = uv[..., 0] / uv[..., 2]
    v = uv[..., 1] / uv[..., 2]
    pa = np.asarray(panel, dtype=np.float32)  # PH,PW,4
    valid = (u >= 0) & (u <= PW - 1) & (v >= 0) & (v <= PH - 1)
    uc = np.clip(u, 0, PW - 1)
    vc = np.clip(v, 0, PH - 1)
    u0 = np.floor(uc).astype(int)
    v0 = np.floor(vc).astype(int)
    u1 = np.minimum(u0 + 1, PW - 1)
    v1 = np.minimum(v0 + 1, PH - 1)
    wu = (uc - u0)[..., None]
    wv = (vc - v0)[..., None]
    samp = (pa[v0, u0] * (1 - wu) * (1 - wv) + pa[v0, u1] * wu * (1 - wv)
            + pa[v1, u0] * (1 - wu) * wv + pa[v1, u1] * wu * wv)
    samp[~valid] = 0
    alpha = (samp[..., 3:4] / 255.0)
    base = np.array(photo, dtype=np.float32)
    region = base[y0:y1, x0:x1]
    region[:] = samp[..., :3] * alpha + region * (1 - alpha)
    return Image.fromarray(base.astype("uint8"), "RGB")


# ── build ───────────────────────────────────────────────────────────────────
logo_full = Image.open(LOGO_SRC).convert("RGBA").crop((14, 14, 485, 391))
# the file wraps its white field in a thin cream rounded frame - crop inside
# the frame so the badge circle (white) matches the field seamlessly.
logo_inner = logo_full.crop((52, 52, logo_full.width - 52, logo_full.height - 52))
_lf = np.array(logo_inner.convert("RGB")).astype(int)
_ink = (_lf.min(axis=2) < 235)
_ys, _xs = np.where(_ink)
print("ink bbox:", int(_xs.min()), int(_ys.min()), int(_xs.max()), int(_ys.max()),
      "of", logo_inner.size)
logo_square = logo_inner

photo = Image.open(SRC).convert("RGB")
photo = erase_badge(photo)
glyph = recolor(key_cream(Image.open(SRC).convert("RGB").crop(GLYPH_BOX)), GOLD_A)

SKU1 = {"name": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)", "gold": GOLD_A}
SKU2 = {"name": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)", "gold": GOLD_B}

photo = warp_panel(photo, build_panel(glyph, SKU1), QUAD_GREEN)
photo = warp_panel(photo, build_panel(glyph, SKU2), QUAD_CHARC)
photo.save(OUT, quality=95)
print("composed:", OUT, photo.size)
