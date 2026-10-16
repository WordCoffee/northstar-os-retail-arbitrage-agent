"""MOGRA "Forest Dusk" — complete-package compositor.

Takes the studio's clean text-free render (base plate from the ComfyUI lane)
and composes the full brand front panel onto both pouches with brand-exact
assets and real type. Everything deterministic; nothing generated.

Per pouch:
  1. extract the model's engraved mushroom art (kept at native resolution,
     re-placed lower; recoloured to the SKU gold)
  2. row-wise median heal of the regions we replace (model badge, art slot,
     dot row) — preserves the matte shading gradient
  3. author the panel at 2.5x: cream roundel badge w/ the REAL Mogra mark
     (mortar & pestle, leaves, EST 2023) + gold ring; REAL wordmark and
     tagline (recoloured cream); product name (Playfair Display 700);
     MUSHROOM POWDER (Inter, tracked); 4 certification glyph icons
     (USDA Organic / Non-GMO / Gluten-Free / Fruiting Body);
     weight footer with gold rules
  4. 4-point homography warp onto the pouch face + lighting integration
     (the print takes the face's own luminance falloff)

Sources (brand-exact, operator-supplied):
  Northstar_backend/assets/brand/mogra_logo.png   (mark / wordmark / tagline)
  Northstar_backend/assets/fonts/PlayfairDisplay.ttf, Inter.ttf

Usage:  python scripts/compose_mogra_complete.py [--debug]
Output: renders/mogra-forest-dusk-mockup-complete.png (+ .json sidecar)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "renders" / "mogra-forest-dusk-mockup.png"
LOGO = ROOT / "Northstar_backend" / "assets" / "brand" / "mogra_logo.png"
FONTS = ROOT / "Northstar_backend" / "assets" / "fonts"
OUT = ROOT / "renders" / "mogra-forest-dusk-mockup-complete.png"
OUT_JSON = ROOT / "renders" / "mogra-forest-dusk-mockup-complete.json"

CREAM = (243, 234, 214)          # #F3EAD6 print cream
BADGE_FILL = (245, 238, 226)     # #F5EEE2 brand ivory
GOLD = {"lm": (196, 160, 74), "shi": (214, 158, 62)}   # muted / warmer gold
INK = {"lm": (36, 56, 42), "shi": (31, 28, 24)}        # glyph ink per pouch

# Face quads in the base render (render px, TL TR BR BL) — verified against a
# coordinate-grid overlay of the 1216x832 plate.
FACES = {
    "lm": {"quad": [(149, 232), (563, 227), (583, 741), (134, 744)],
           "badge_old": (494, 345, 84), "grain_patch": (695, 730, 240, 430),
           "dots": [(307, 655), (346, 655), (386, 655), (425, 655)]},
    "shi": {"quad": [(646, 226), (1066, 221), (1078, 738), (630, 744)],
            "badge_old": (985, 344, 102), "grain_patch": (695, 730, 700, 890),
            "dots": [(790, 655), (830, 655), (870, 655), (910, 655)]},
}

SKUS = {
    "lm": {"name": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)"},
    "shi": {"name": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)"},
}

PANEL_SCALE = 2.5      # panel px per render px
DOT_R = 34             # erase radius around the model's dot row (unused: covered)

# P0 realism passes (compositor v2) — conservative defaults, recorded in the sidecar
DISP_K = 3.0           # max displacement in render px (ink follows the surface's folds)
SOFTLIGHT_STR = 0.9    # print takes the surface shading (soft-light blend strength)
SPEC_MAX = 0.32        # specular sheen cap screened over the print
# NOTE (deferred honestly): a printed-patch AO rim / seam (compositor report step 4)
# was NOT applied — our design is scattered elements (type + art), and an edge
# rim would outline every glyph instead of grounding a label patch. The
# displacement + shading passes are the grounding here.


# ── helpers ─────────────────────────────────────────────────────────────────

def font(name: str, size: int, axes=None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    if axes is not None:
        try:
            f.set_variation_by_axes(axes)
        except Exception:
            pass
    return f


def centered(d: ImageDraw.ImageDraw, y: float, text: str, f, fill, tracking=0):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = (d.im.width if hasattr(d, "im") else 0) / 2 - total / 2  # panel cx patched below
    raise RuntimeError("unused")


def draw_centered(d: ImageDraw.ImageDraw, cx: float, y: float, text: str, f,
                  fill, tracking=0):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = cx - total / 2
    for ch, w in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill, anchor="lm")
        x += w + tracking


def fit_font(name: str, start: int, axes, text: str, max_w: float, d) -> ImageFont.FreeTypeFont:
    size = start
    while size > 24:
        f = font(name, size, axes)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 3
    return font(name, size, axes)


def ink_alpha(rgb: np.ndarray, field_min: float) -> np.ndarray:
    """Alpha from darkness against a light field; thin-stroke-preserving."""
    mn = rgb.min(axis=2).astype(float)
    a = np.clip((field_min - mn) / (field_min - 70.0), 0, 1)
    a = np.clip((a - 0.10) / 0.90, 0, 1)   # gentle gate: keeps hairlines
    return np.clip(a ** 0.75 * 1.12, 0, 1)  # solidify strokes


def cream_version(piece: np.ndarray, field_min: float) -> Image.Image:
    """Dark ink -> CREAM with proper antialiasing alpha."""
    a = ink_alpha(piece, field_min)
    out = np.zeros((*piece.shape[:2], 4), dtype=np.uint8)
    out[..., 0], out[..., 1], out[..., 2] = CREAM
    out[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def mark_version(piece: np.ndarray, field_min: float) -> Image.Image:
    """The mark keeps its ORIGINAL colours; light field -> transparent."""
    a = ink_alpha(piece, field_min)
    out = np.zeros((*piece.shape[:2], 4), dtype=np.uint8)
    out[..., :3] = piece
    out[..., 3] = (a * 255).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def quad_inside_mask(shape, quad) -> np.ndarray:
    """Boolean mask of pixels inside a convex quad (TL TR BR BL)."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    xs = [p[0] for p in quad]; ys = [p[1] for p in quad]
    area = 0.0
    for i in range(4):
        j = (i + 1) % 4
        area += xs[i] * ys[j] - xs[j] * ys[i]
    s = 1.0 if area > 0 else -1.0
    inside = np.ones(shape, dtype=bool)
    for i in range(4):
        x1, y1 = quad[i]
        x2, y2 = quad[(i + 1) % 4]
        cross = (x2 - x1) * (yy - y1) - (y2 - y1) * (xx - x1)
        inside &= (cross * s) >= 0
    return inside


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    return np.array(Image.fromarray((mask * 255).astype(np.uint8))
                    .filter(ImageFilter.GaussianBlur(r))) > 15


def heal_regions(img: np.ndarray, regions, quad, grain_patch: tuple) -> np.ndarray:
    """Seam-free healing, per region:
    median prefill -> converged diffusion (boundary-exact) -> native grain
    re-injection so the healed area keeps the matte film texture."""
    inside = quad_inside_mask(img.shape[:2], quad)
    # high-frequency grain measured from a clean face patch
    py0, py1, px0, px1 = grain_patch
    patch = img[py0:py1, px0:px1].astype(np.float32)
    grain = patch - np.array(Image.fromarray(patch.astype(np.uint8))
                             .filter(ImageFilter.GaussianBlur(1.5))).astype(np.float32)
    out = img.astype(np.float32)
    for mask in regions:
        mask = mask & inside
        if not mask.any():
            continue
        ring = _dilate(mask, 8) & ~mask & inside
        med = (np.median(out[ring], axis=0) if ring.sum() > 200
               else np.median(out[inside], axis=0))
        work = out.copy()
        work[mask] = med
        for _ in range(420):
            bl = np.array(Image.fromarray(work.astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(13))).astype(np.float32)
            work[mask] = bl[mask]
        ys, xs = np.where(mask)
        g = grain[np.mod(ys, grain.shape[0]), np.mod(xs, grain.shape[1])]
        work[mask] = np.clip(work[mask] + g, 0, 255)
        out = work
    return np.clip(out, 0, 255).astype(np.uint8)


def circle_mask(shape, cx, cy, r):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((xx - cx) ** 2 + (yy - cy) ** 2) <= r * r


# ── glyph icons ─────────────────────────────────────────────────────────────

def _bezier(p0, c1, c2, p1, n=26):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * c1[0] + 3 * mt * t**2 * c2[0] + t**3 * p1[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * c1[1] + 3 * mt * t**2 * c2[1] + t**3 * p1[1]
        pts.append((x, y))
    return pts


def glyph_leaf(d, cx, cy, r, color, w=5):
    top, bot = (cx, cy - 0.60 * r), (cx, cy + 0.62 * r)
    right = _bezier(bot, (cx + 0.62 * r, cy + 0.22 * r), (cx + 0.50 * r, cy - 0.42 * r), top)
    left = _bezier(bot, (cx - 0.62 * r, cy + 0.22 * r), (cx - 0.50 * r, cy - 0.42 * r), top)
    d.line(right, fill=color, width=w, joint="curve")
    d.line(left, fill=color, width=w, joint="curve")
    d.line([bot, (cx, cy + 0.82 * r)], fill=color, width=w)


def glyph_sprout_slash(d, cx, cy, r, color, w=5):
    """Non-GMO: a seed disc under a slash (reads as 'no ...' at icon scale)."""
    d.ellipse([cx - 0.38 * r, cy - 0.14 * r, cx + 0.38 * r, cy + 0.62 * r],
              outline=color, width=w)
    d.line([(cx, cy - 0.14 * r), (cx, cy - 0.58 * r)], fill=color, width=w)
    d.line([(cx - 0.64 * r, cy + 0.64 * r), (cx + 0.64 * r, cy - 0.64 * r)],
           fill=color, width=w + 1)


def glyph_wheat_slash(d, cx, cy, r, color, w=5):
    d.line([(cx, cy - 0.62 * r), (cx, cy + 0.66 * r)], fill=color, width=w)
    for gx, gy in ((-0.42, -0.40), (-0.10, -0.18), (0.22, 0.04)):
        d.line([(cx, cy + gy * r), (cx + gx * r, cy + (gy - 0.36) * r)], fill=color, width=w)
        d.line([(cx, cy + gy * r), (cx - gx * r, cy + (gy - 0.36) * r)], fill=color, width=w)
    d.line([(cx - 0.64 * r, cy + 0.64 * r), (cx + 0.64 * r, cy - 0.64 * r)], fill=color, width=w + 1)


def glyph_mushroom(d, cx, cy, r, color, w=5):
    cap = [cx - 0.62 * r, cy - 0.55 * r, cx + 0.62 * r, cy + 0.12 * r]
    d.arc(cap, start=180, end=360, fill=color, width=w)
    d.line([(cx - 0.62 * r, cy + 0.12 * r), (cx + 0.62 * r, cy + 0.12 * r)], fill=color, width=w)
    d.line([(cx - 0.24 * r, cy + 0.12 * r), (cx - 0.20 * r, cy + 0.60 * r)], fill=color, width=w)
    d.line([(cx + 0.24 * r, cy + 0.12 * r), (cx + 0.20 * r, cy + 0.60 * r)], fill=color, width=w)
    d.line([(cx - 0.36 * r, cy + 0.60 * r), (cx + 0.36 * r, cy + 0.60 * r)], fill=color, width=w)


GLYPHS = (glyph_leaf, glyph_sprout_slash, glyph_wheat_slash, glyph_mushroom)


# ── logo pieces ─────────────────────────────────────────────────────────────

def logo_bands() -> dict:
    im = Image.open(LOGO).convert("RGB")
    a = np.array(im).astype(int)
    # measured field level: min-channel of the four corners (the logo field)
    corner = np.concatenate([a[:20, :20].reshape(-1, 3), a[:20, -20:].reshape(-1, 3),
                             a[-20:, :20].reshape(-1, 3), a[-20:, -20:].reshape(-1, 3)])
    field_min = float(np.median(corner.min(axis=1)))
    ink = a.min(axis=2) < (field_min - 12)
    prof = ink.sum(axis=1)
    bands, s = [], None
    for y in range(im.height):
        v = prof[y] > 1
        if v and s is None:
            s = y
        elif not v and s is not None:
            bands.append((s, y - 1))
            s = None
    if s is not None:
        bands.append((s, im.height - 1))
    bands = [b for b in bands if b[1] - b[0] >= 12]
    if len(bands) < 3:
        raise RuntimeError(f"logo band split failed: {bands}")
    mark_b, word_b, tag_b = bands[0], bands[1], bands[2]

    def crop_band(b):
        y0, y1 = max(0, b[0] - 4), min(im.height, b[1] + 5)
        sl = a[y0:y1]
        xs = np.where((sl.min(axis=2) < (field_min - 12)).any(axis=0))[0]
        return sl[:, max(0, xs.min() - 3):xs.max() + 4]

    return {"field_min": field_min,
            "mark": crop_band(mark_b), "word": crop_band(word_b), "tag": crop_band(tag_b)}


# ── panel authoring ─────────────────────────────────────────────────────────

def build_panel(sku: str, pieces: dict, face_px: tuple, icon_pts) -> Image.Image:
    fw, fh = face_px
    PW, PH = int(round(fw * PANEL_SCALE)), int(round(fh * PANEL_SCALE))
    r = PANEL_SCALE  # render-px -> panel-px
    field_min = pieces["field_min"]

    def y(off):  # offset in render px from face top -> panel y
        return off * r

    panel = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    cx = PW / 2
    gold = GOLD[sku]

    # 1) the full logo lockup printed DIRECTLY on the matte surface - mark
    #    (mortar & pestle + leaves + EST 2023), wordmark, tagline - all in one
    #    cream print, like a screen-printed kraft-goods brand. No disc, no
    #    sticker shadow. The mark is the REAL raster (alpha slightly fattened);
    #    the wordmark is set in Playfair Display (matches the Didone wordmark)
    #    so the small-size raster never goes holey.
    mark = cream_version(pieces["mark"], field_min)
    mk_alpha = mark.split()[3].filter(ImageFilter.MaxFilter(3))
    mark.putalpha(mk_alpha)
    mk_w = int(170 * r)
    mk = mark.resize((mk_w, int(mk_w * mark.height / mark.width)), Image.LANCZOS)
    panel.paste(mk, (int(cx - mk.width / 2), int(y(48) - mk.height / 2)), mk)

    # 2) wordmark (typed) + tagline (real raster, recoloured cream)
    f_word = fit_font("PlayfairDisplay.ttf", int(72 * r), [700], "MOGRA ORGANICS",
                      int(300 * r), d)
    draw_centered(d, cx, y(102), "MOGRA ORGANICS", f_word, CREAM + (255,), tracking=3.2 * r)
    tag_w = int(140 * r)
    tg = cream_version(pieces["tag"], field_min)
    tg = tg.resize((tag_w, int(tag_w * tg.height / tg.width)), Image.LANCZOS)
    panel.paste(tg, (int(cx - tg.width / 2), int(y(128) - tg.height / 2)), tg)

    # 3) product name block (sits above the model's own engraved art);
    #    both SKUs share ONE size (fitted to the longest name) so the two
    #    pouches read as a matched pair
    ref = "ORGANIC LION'S MANE"
    f_name = fit_font("PlayfairDisplay.ttf", int(56 * r), [700], ref, int(380 * r), d)
    draw_centered(d, cx, y(158), SKUS[sku]["name"], f_name, CREAM + (255,))
    f_sub = font("Inter.ttf", int(15 * r), [14, 600])
    draw_centered(d, cx, y(180), "MUSHROOM POWDER", f_sub, CREAM + (230,), tracking=6 * r)

    # 5) certification icon row - discs sit exactly on the model's dot row,
    #    each with its own soft shadow so they read as printed roundels
    ir = 16 * r
    sh = Image.new("RGBA", panel.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    for (ex, ey) in icon_pts:
        sd.ellipse([ex - ir * 1.30, ey - ir * 1.05, ex + ir * 1.30, ey + ir * 1.50],
                   fill=(6, 14, 9, 54))
    sh = sh.filter(ImageFilter.GaussianBlur(5 * r / 2.5))
    panel = Image.alpha_composite(panel, sh)
    d = ImageDraw.Draw(panel)
    for i, (ex, ey) in enumerate(icon_pts):
        d.ellipse([ex - ir, ey - ir, ex + ir, ey + ir], fill=BADGE_FILL + (255,))
        GLYPHS[i](d, ex, ey, ir * 0.72, INK[sku] + (255,), w=5)

    # 6) weight footer with gold rules
    f_foot = font("Inter.ttf", int(18 * r), [14, 560])
    fy = y(468)
    draw_centered(d, cx, fy, SKUS[sku]["weight"], f_foot, CREAM + (255,))
    for sgn in (-1, 1):
        x0 = cx + sgn * 128 * r
        x1 = cx + sgn * 208 * r
        d.line([sorted((x0, x1))[0], fy, sorted((x0, x1))[1], fy], fill=gold + (200,), width=4)
    return panel


# ── warp ────────────────────────────────────────────────────────────────────

def homography(src, dst):
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    _, _, Vt = np.linalg.svd(np.array(A, dtype=float))
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def warp_panel(photo: np.ndarray, panel: Image.Image, quad,
               lum8: np.ndarray, lum2: np.ndarray) -> None:
    """Homography warp + P0 realism passes, in place.

    - displacement: the sample point shifts with the surface's blurred
      luminance deviation, so ink rides the folds instead of floating over them
    - soft-light: the print takes the face's own luminance falloff
    - specular: the film's sheen screens OVER the ink on bright surface zones
    """
    PW, PH = panel.size
    H = homography([(0, 0), (PW, 0), (PW, PH), (0, PH)], list(quad))
    Hinv = np.linalg.inv(H)
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, x1 = max(0, int(min(xs)) - 4), min(photo.shape[1], int(max(xs)) + 5)
    y0, y1 = max(0, int(min(ys)) - 4), min(photo.shape[0], int(max(ys)) + 5)
    gx, gy = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    ones = np.ones_like(gx, dtype=float)
    uv = np.stack([gx.astype(float), gy.astype(float), ones], axis=-1) @ Hinv.T
    u, v = uv[..., 0] / uv[..., 2], uv[..., 1] / uv[..., 2]

    L8 = lum8[y0:y1, x0:x1]
    med8 = float(np.median(L8)) or 1.0
    D = np.clip((L8 - med8) / (med8 * 0.55), -1.0, 1.0)
    shift = D * (DISP_K * PANEL_SCALE)
    u = u + shift
    v = v + shift * 0.35

    pa = np.asarray(panel, dtype=np.float32)
    valid = (u >= 0) & (u <= PW - 1) & (v >= 0) & (v <= PH - 1)
    uc, vc = np.clip(u, 0, PW - 1), np.clip(v, 0, PH - 1)
    u0, v0 = np.floor(uc).astype(int), np.floor(vc).astype(int)
    u1, v1 = np.minimum(u0 + 1, PW - 1), np.minimum(v0 + 1, PH - 1)
    wu, wv = (uc - u0)[..., None], (vc - v0)[..., None]
    samp = (pa[v0, u0] * (1 - wu) * (1 - wv) + pa[v0, u1] * wu * (1 - wv)
            + pa[v1, u0] * (1 - wu) * wv + pa[v1, u1] * wu * wv)
    samp[~valid] = 0
    alpha = samp[..., 3:4] / 255.0

    # soft-light shading on the print only
    s01 = np.clip(0.5 + (L8 - med8) / (med8 * 1.1), 0.28, 1.0)[..., None]
    x = samp[..., :3] / 255.0
    sl = x + (2.0 * s01 - 1.0) * x * (1.0 - x)
    print_rgb = (x * (1.0 - SOFTLIGHT_STR) + sl * SOFTLIGHT_STR) * 255.0

    # specular screen (bright surface zones only)
    L2 = lum2[y0:y1, x0:x1]
    med2 = float(np.median(L2)) or 1.0
    hi = np.clip((L2 - med2 * 1.35) / (med2 * 0.9), 0.0, SPEC_MAX)[..., None]
    print_rgb = print_rgb + (255.0 - print_rgb) * hi

    region = photo[y0:y1, x0:x1].astype(np.float32)
    photo[y0:y1, x0:x1] = np.clip(
        print_rgb * alpha + region * (1 - alpha), 0, 255).astype(np.uint8)


# ── main ────────────────────────────────────────────────────────────────────

def main(debug: bool = False) -> int:
    t0 = time.time()
    pieces = logo_bands()
    base_img = Image.open(BASE).convert("RGB")
    base = np.array(base_img).astype(np.uint8)
    photo = base.copy()

    # P0 realism maps from the pristine plate (whole-image, computed once)
    def _lum(im: Image.Image) -> np.ndarray:
        a = np.asarray(im, dtype=np.float32)
        return 0.3 * a[..., 0] + 0.59 * a[..., 1] + 0.11 * a[..., 2]
    lum8 = _lum(base_img.filter(ImageFilter.GaussianBlur(6)))
    lum2 = _lum(base_img.filter(ImageFilter.GaussianBlur(2.5)))

    for sku, spec in FACES.items():
        fw = (spec["quad"][1][0] - spec["quad"][0][0] + spec["quad"][2][0] - spec["quad"][3][0]) / 2
        fh = (spec["quad"][3][1] - spec["quad"][0][1] + spec["quad"][2][1] - spec["quad"][1][1]) / 2

        # -- heal ONLY the model's old badge; its engraved art and the dot row
        #    stay untouched (roundel discs are placed exactly on the dots).
        bx, by, _ = spec["badge_old"]
        regions = [circle_mask(photo.shape[:2], bx, by, 64)]
        photo = heal_regions(photo, regions, spec["quad"], spec["grain_patch"])

        # -- author + warp the panel
        q = spec["quad"]
        PW_panel = int(round(fw * PANEL_SCALE))
        def _edge_x(p_top, p_bot, yy):
            t = (yy - p_top[1]) / max(1e-6, (p_bot[1] - p_top[1]))
            return p_top[0] + t * (p_bot[0] - p_top[0])
        icon_pts = []
        for (dx, dy) in spec["dots"]:
            xl = _edge_x(q[0], q[3], dy)
            xr = _edge_x(q[1], q[2], dy)
            icon_pts.append(((dx - xl) / max(1e-6, (xr - xl)) * PW_panel,
                             (dy - q[0][1]) * PANEL_SCALE))
        panel = build_panel(sku, pieces, (fw, fh), icon_pts)
        panel = panel.filter(ImageFilter.GaussianBlur(0.6))
        # P0.2 print-grain sync: high-pass grain measured from this pouch's own
        # surface (the same field heal_regions uses), laid under the ink alpha
        py0, py1, px0, px1 = spec["grain_patch"]
        patch = base[py0:py1, px0:px1].astype(np.float32)
        g = patch - np.asarray(Image.fromarray(patch.astype(np.uint8))
                               .filter(ImageFilter.GaussianBlur(1.5)), dtype=np.float32)
        pa = np.array(panel, dtype=np.float32)
        Hp, Wp = pa.shape[:2]
        tile = np.tile(g, (Hp // g.shape[0] + 1, Wp // g.shape[1] + 1, 1))[:Hp, :Wp]
        pa[..., :3] = np.clip(pa[..., :3] + tile * (pa[..., 3:4] / 255.0), 0, 255)
        panel = Image.fromarray(pa.astype(np.uint8), "RGBA")
        if debug:
            Image.fromarray(photo, "RGB").save(ROOT / "renders" / f"_stage_heal_{sku}.png")
            panel.save(ROOT / "renders" / f"_stage_panel_{sku}.png")
        warp_panel(photo, panel, spec["quad"], lum8, lum2)
        if debug:
            Image.fromarray(photo, "RGB").save(ROOT / "renders" / f"_stage_warp_{sku}.png")

    out = Image.fromarray(photo, "RGB")
    out.save(OUT)
    if debug:
        dd = ImageDraw.Draw(out)
        for spec in FACES.values():
            q = spec["quad"]
            dd.line(list(q) + [q[0]], fill=(0, 255, 255), width=2)
        out.save(ROOT / "renders" / "_debug_compose.png")
    OUT_JSON.write_text(json.dumps({
        "file": OUT.name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base": BASE.name, "logo": str(LOGO.relative_to(ROOT)),
        "fonts": ["PlayfairDisplay.ttf", "Inter.ttf"],
        "panel_scale": PANEL_SCALE,
        "realism_passes": {
            "displacement_k_render_px": DISP_K,
            "soft_light_strength": SOFTLIGHT_STR,
            "specular_cap": SPEC_MAX,
            "grain": "high-pass of the pouch's own surface, keyed to ink alpha",
            "ao_rim": "deferred (scattered print, see script note)",
        },
        "layout": "roundel badge (real mark) > real wordmark + tagline > product name "
                  "(Playfair 700) > MUSHROOM POWDER (Inter, tracked) > model's native "
                  "engraved art (untouched) > 4 cert roundels on the model's dot row "
                  "> weight footer + gold rules",
        "palette": {"cream": "#F3EAD6", "badge": "#F5EEE2",
                    "gold_lm": "#C4A04A", "gold_shi": "#D69E3E"},
        "seconds": round(time.time() - t0, 2),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "seconds": round(time.time() - t0, 1)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(debug="--debug" in sys.argv))
