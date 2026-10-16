"""Mockup compositor — deterministic typography pass over clean plates.

The pipeline this closes (2026-10-16): the image model paints the PHOTO (matte
pouches, scene, lighting) and never draws letters; this compositor then lays out
a flat "print panel" — operator's real logo, real fonts (Playfair Display /
Inter, OFL), extracted/recoloured line art, drawn certification icons — and
warps it onto each pouch face with an exact 4-point homography. Text is
composited, never generated; spelling is exact by construction.

Plate-specific geometry (per-pouch face quads, badge-erase circles, glyph box)
lives in ``data/compose_presets.json`` keyed by template id - honest limitation:
a NEW plate needs its quads, which we currently take from a grid overlay pass
(auto-detection is future work). Templates carry the layout; presets carry the
plate geometry.

No provider calls, no network, no cost. Pure PIL + numpy.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
PRESETS_PATH = Path(__file__).resolve().parent / "data" / "compose_presets.json"

CREAM = (245, 238, 226)


# ── fonts ───────────────────────────────────────────────────────────────────

def load_font(name: str, size: int, axes: Optional[Sequence[float]] = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS_DIR / name), size)
    if axes is not None:
        try:
            f.set_variation_by_axes(list(axes))
        except Exception:
            pass
    return f


def fit_font(name: str, size: int, axes, text: str, max_w: float, d: ImageDraw.ImageDraw):
    while size > 16:
        f = load_font(name, size, axes)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return load_font(name, size, axes)


def centered(d: ImageDraw.ImageDraw, cx: float, y: float, text: str, f, fill, tracking: float = 0.0):
    widths = [d.textlength(ch, font=f) for ch in text]
    total = sum(widths) + tracking * max(0, len(text) - 1)
    x = cx - total / 2
    for ch, w_ in zip(text, widths):
        d.text((x, y), ch, font=f, fill=fill, anchor="lm")
        x += w_ + tracking


# ── colour utilities ────────────────────────────────────────────────────────

def prepare_logo(logo_path: Path, frame_crop: int = 52) -> Tuple[Image.Image, Tuple[int, int, int]]:
    """Crop inside the logo file's frame and return (inner RGBA, field colour)."""
    raw = Image.open(logo_path).convert("RGBA")
    inner = raw.crop((frame_crop // 2, frame_crop // 2, raw.width - frame_crop // 2, raw.height - frame_crop // 2))
    # the operator file has an outer margin too; crop inside the cream frame
    inner = raw.crop((frame_crop, frame_crop, raw.width - frame_crop, raw.height - frame_crop))
    arr = np.array(inner.convert("RGB"))
    edge = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3),
                           arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
    field = tuple(int(c) for c in np.median(edge, axis=0))
    return inner, field


def key_cream(img: Image.Image) -> Image.Image:
    """Cream/white background -> transparent (soft alpha from min-channel)."""
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
    """Recolour ink; greenish pixels (leaves) keep their original colour."""
    a = np.array(img).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    green = (g > r + 18) & (g > b + 18)
    out = a.copy()
    out[..., 0], out[..., 1], out[..., 2] = color
    out[green, 0], out[green, 1], out[green, 2] = a[green, 0], a[green, 1], a[green, 2]
    return Image.fromarray(out.astype("uint8"), "RGBA")


def extract_glyph(plate: Image.Image, box: Sequence[int]) -> Image.Image:
    """Pull line art out of the plate (e.g. the engraved mushroom in a badge)."""
    return key_cream(plate.convert("RGB").crop(tuple(box)))


# ── erase ───────────────────────────────────────────────────────────────────

def erase_circle(photo: Image.Image, center: Sequence[float], r: float,
                 feather: float = 70.0, ring: Tuple[float, float] = (3.0, 30.0)) -> Image.Image:
    """Feathered circular erase: ring-median colour from an annulus that
    excludes the target itself; wide feather so no halo ring remains."""
    cx, cy = float(center[0]), float(center[1])
    x0, y0 = int(max(0, cx - r - feather - 20)), int(max(0, cy - r - feather - 20))
    x1, y1 = int(min(photo.width, cx + r + feather + 20)), int(min(photo.height, cy + r + feather + 20))
    arr = np.array(photo)
    band = arr[y0:y1, x0:x1].astype(np.float32)
    yy, xx = np.mgrid[0:band.shape[0], 0:band.shape[1]]
    dist = np.sqrt((xx + x0 - cx) ** 2 + (yy + y0 - cy) ** 2)
    ann = band[(dist >= r + ring[0]) & (dist <= r + ring[1])]
    color = np.median(ann, axis=0) if len(ann) else np.array([255, 255, 255], np.float32)
    # radial luminance continuation: blend the local shading into the fill so
    # the patch follows the pouch's soft gradient instead of sitting flat.
    luma = band.mean(axis=2)
    med = np.median(luma[(dist >= r + 4) & (dist <= r + 60)]) + 1e-6
    local = np.clip(luma / med, 0.9, 1.1)[..., None]
    fill = (color[None, None, :] * local).astype(np.float32)
    alpha = np.clip((r - dist) / feather, 0.0, 1.0)[..., None]
    band = fill * alpha + band * (1 - alpha)
    arr[y0:y1, x0:x1] = band.astype("uint8")
    return Image.fromarray(arr, "RGB")


def erase_rect(photo: Image.Image, box: Sequence[float], feather: float = 26.0,
               ring: float = 14.0) -> Image.Image:
    """Feathered rectangular erase (e.g. the plate's original icon strip)."""
    x0, y0, x1, y1 = [float(v) for v in box]
    pad = int(feather + ring + 8)
    bx0, by0 = int(max(0, x0 - pad)), int(max(0, y0 - pad))
    bx1, by1 = int(min(photo.width, x1 + pad)), int(min(photo.height, y1 + pad))
    arr = np.array(photo)
    band = arr[by0:by1, bx0:bx1].astype(np.float32)
    h, w = band.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    gx0, gy0, gx1, gy1 = x0 - bx0, y0 - by0, x1 - bx0, y1 - by0
    inside = (xx >= gx0) & (xx <= gx1) & (yy >= gy0) & (yy <= gy1)
    dx = np.maximum(np.maximum(gx0 - xx, xx - gx1), 0)
    dy = np.maximum(np.maximum(gy0 - yy, yy - gy1), 0)
    dist = np.sqrt(dx * dx + dy * dy)
    ring_zone = (dist >= 2) & (dist <= ring)
    ann = band[ring_zone]
    color = np.median(ann, axis=0) if len(ann) else np.array([200, 200, 200], np.float32)
    luma = band.mean(axis=2)
    med = np.median(luma[ring_zone]) + 1e-6 if ring_zone.any() else 1.0
    local = np.clip(luma / med, 0.9, 1.1)[..., None]
    fill = (color[None, None, :] * local).astype(np.float32)
    alpha = np.clip(1.0 - dist / feather, 0.0, 1.0)[..., None]
    band = fill * alpha + band * (1 - alpha)
    arr[by0:by1, bx0:bx1] = band.astype("uint8")
    return Image.fromarray(arr, "RGB")


# ── certification icons (drawn as vectors, never generated) ─────────────────

_ICON_SPECS = ("organic_sprout", "non_gmo", "gluten_free", "fruiting_body")


def draw_cert_icon(d: ImageDraw.ImageDraw, kind: str, cx: float, cy: float, r: float,
                   ink, ring=None, disc=None, width: int = 3) -> None:
    """Cream disc + line glyph; matches the brief's 'tiny circular icons'."""
    if disc is not None:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(disc) + (255,))
    if ring is not None:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=tuple(ring) + (255,), width=2)
    ink_col = tuple(ink) + (255,)
    u = r / 10.0  # unit scale
    if kind == "organic_sprout":       # leaf pair
        d.arc([cx - 6 * u, cy - 5 * u, cx + 6 * u, cy + 7 * u], 200, 340, fill=ink_col, width=width)
        d.arc([cx - 2 * u, cy - 7 * u, cx + 6 * u, cy + 1 * u], 20, 160, fill=ink_col, width=width)
        d.line([(cx, cy + 6 * u), (cx, cy - 1 * u)], fill=ink_col, width=width)
    elif kind == "non_gmo":            # butterfly: two wing pairs + body
        d.ellipse([cx - 7 * u, cy - 5 * u, cx - 1 * u, cy + 1 * u], outline=ink_col, width=width)
        d.ellipse([cx + 1 * u, cy - 5 * u, cx + 7 * u, cy + 1 * u], outline=ink_col, width=width)
        d.ellipse([cx - 5 * u, cy + 1 * u, cx - 1 * u, cy + 5 * u], outline=ink_col, width=width)
        d.ellipse([cx + 1 * u, cy + 1 * u, cx + 5 * u, cy + 5 * u], outline=ink_col, width=width)
        d.line([(cx, cy - 6 * u), (cx, cy + 6 * u)], fill=ink_col, width=width)
    elif kind == "gluten_free":        # wheat stalk + slash
        d.line([(cx, cy + 6 * u), (cx, cy - 6 * u)], fill=ink_col, width=width)
        for dy in (2 * u, -1 * u, -4 * u):
            d.line([(cx, cy + dy), (cx - 4 * u, cy + dy - 3 * u)], fill=ink_col, width=width)
            d.line([(cx, cy + dy), (cx + 4 * u, cy + dy - 3 * u)], fill=ink_col, width=width)
        d.line([(cx - 6 * u, cy + 6 * u), (cx + 6 * u, cy - 6 * u)], fill=ink_col, width=width + 1)
    else:                               # fruiting_body: mushroom
        d.arc([cx - 6 * u, cy - 6 * u, cx + 6 * u, cy + 4 * u], 180, 360, fill=ink_col, width=width)
        d.line([(cx - 6 * u, cy - 1 * u), (cx + 6 * u, cy - 1 * u)], fill=ink_col, width=width)
        d.line([(cx - 2.5 * u, cy - 1 * u), (cx - 3.5 * u, cy + 6 * u)], fill=ink_col, width=width)
        d.line([(cx + 2.5 * u, cy - 1 * u), (cx + 3.5 * u, cy + 6 * u)], fill=ink_col, width=width)


# ── panel rendering + warping ───────────────────────────────────────────────

def render_panel(*, size: Sequence[int], badge: Dict[str, Any], title: Dict[str, Any],
                 subtitle: Dict[str, Any], glyph: Optional[Dict[str, Any]],
                 icons: Optional[Dict[str, Any]], footer: Dict[str, Any],
                 logo: Optional[Image.Image], glyph_img: Optional[Image.Image],
                 gold, field_color) -> Image.Image:
    W, H = int(size[0]), int(size[1])
    panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)

    cx, cy, r = badge["cx"], badge["cy"], badge["r"]
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=tuple(field_color) + (255,))
    if logo is not None and badge.get("logo", True):
        lock_w = int(2 * r * badge.get("logo_width_frac", 0.72))
        lock = logo.resize((lock_w, int(lock_w * logo.height / logo.width)), Image.LANCZOS)
        badge_img = Image.new("RGBA", (int(2 * r) + 12, int(2 * r) + 12), (0, 0, 0, 0))
        ImageDraw.Draw(badge_img).ellipse([6, 6, int(2 * r) + 6, int(2 * r) + 6],
                                          fill=tuple(field_color) + (255,))
        badge_img.paste(lock, ((badge_img.width - lock.width) // 2,
                               (badge_img.height - lock.height) // 2), lock)
        mask = Image.new("L", badge_img.size, 0)
        ImageDraw.Draw(mask).ellipse([6, 6, int(2 * r) + 6, int(2 * r) + 6], fill=255)
        badge_img.putalpha(ImageChops.multiply(badge_img.split()[3], mask))
        panel.paste(badge_img, (int(cx - r) - 6, int(cy - r) - 6), badge_img)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=tuple(gold) + (255,), width=5)

    f_title = fit_font(title["font"], title["size"], title.get("axes"),
                       title["text"], title.get("max_w", int(W * 0.86)), d)
    centered(d, W / 2, title["y"], title["text"], f_title, tuple(title.get("color", CREAM)))
    f_sub = load_font(subtitle["font"], subtitle["size"], subtitle.get("axes"))
    centered(d, W / 2, subtitle["y"], subtitle["text"], f_sub,
             tuple(subtitle.get("color", CREAM)), tracking=subtitle.get("tracking", 0))

    if glyph_img is not None and glyph:
        g = recolor(glyph_img, tuple(gold)).resize(
            (glyph["w"], int(glyph["w"] * glyph_img.height / glyph_img.width)), Image.LANCZOS)
        panel.paste(g, (int(W / 2 - g.width / 2), int(glyph["y"])), g)

    if icons:
        kinds = icons.get("kinds", _ICON_SPECS)
        ir = icons.get("r", 26)
        gap = icons.get("gap", 74)
        y = icons["y"]
        n = len(kinds)
        for i, kind in enumerate(kinds):
            x = W / 2 + (i - (n - 1) / 2) * gap
            draw_cert_icon(d, kind, x, y, ir, ink=gold, ring=gold, disc=CREAM,
                           width=icons.get("width", 3))

    f_foot = load_font(footer["font"], footer["size"], footer.get("axes"))
    centered(d, W / 2, footer["y"], footer["text"], f_foot, tuple(footer.get("color", CREAM)))
    if footer.get("rules", True):
        d.line([(W / 2 - 210, footer["y"]), (W / 2 - 106, footer["y"])],
               fill=tuple(gold) + (170,), width=2)
        d.line([(W / 2 + 106, footer["y"]), (W / 2 + 210, footer["y"])],
               fill=tuple(gold) + (170,), width=2)
    return panel


def _homography(src, dst) -> np.ndarray:
    A = []
    for (x, y), (u, v) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -u * x, -u * y, -u])
        A.append([0, 0, 0, x, y, 1, -v * x, -v * y, -v])
    A = np.array(A, dtype=float)
    _, _, Vt = np.linalg.svd(A)
    H = Vt[-1].reshape(3, 3)
    return H / H[2, 2]


def warp_panel(photo: Image.Image, panel: Image.Image, quad: Sequence,
               shading: float = 0.5) -> Image.Image:
    """Exact 4-point homography (panel -> quad), bilinear, shading-blended."""
    PW, PH = panel.size
    H = _homography([(0, 0), (PW, 0), (PW, PH), (0, PH)], list(quad))
    Hinv = np.linalg.inv(H)
    W, Hpx = photo.size
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    m = 6
    x0, x1 = max(0, int(min(xs)) - m), min(W, int(max(xs)) + m)
    y0, y1 = max(0, int(min(ys)) - m), min(Hpx, int(max(ys)) + m)
    gx, gy = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    pts = np.stack([gx.astype(float), gy.astype(float), np.ones_like(gx, dtype=float)], axis=-1)
    uv = pts @ Hinv.T
    u = uv[..., 0] / uv[..., 2]
    v = uv[..., 1] / uv[..., 2]
    pa = np.asarray(panel, dtype=np.float32)
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
    alpha = samp[..., 3:4] / 255.0
    base = np.array(photo, dtype=np.float32)
    region = base[y0:y1, x0:x1]
    luma = region.mean(axis=2, keepdims=True)
    ref = np.median(luma) + 1e-6
    mod = 1.0 + shading * (np.clip(luma / ref, 0.85, 1.15) - 1.0)
    ink = samp[..., :3] * mod
    region[:] = np.clip(ink * alpha + region * (1 - alpha), 0, 255)
    return Image.fromarray(base.astype("uint8"), "RGB")


# ── presets ─────────────────────────────────────────────────────────────────

DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "mogra-forest-dusk": {
        "description": "Two-pouch forest dusk mockup: cream logo roundel, serif "
                       "product names, gold engraved glyph, four cert icons, weight footers.",
        "panel": {"size": [700, 1000]},
        "badge": {"cx": 350, "cy": 300, "r": 178, "logo_width_frac": 0.72},
        "title": {"font": "PlayfairDisplay.ttf", "axes": [700], "size": 64,
                  "y": 560, "max_w": 600},
        "subtitle": {"font": "Inter.ttf", "axes": [14, 640], "size": 27,
                     "y": 616, "tracking": 9, "text": "MUSHROOM POWDER"},
        "glyph": {"y": 668, "w": 190},
        "icons": {"y": 872, "r": 26, "gap": 74, "kinds": list(_ICON_SPECS)},
        "footer": {"font": "Inter.ttf", "axes": [14, 560], "size": 26, "y": 942},
    },
}


def load_presets() -> Dict[str, Dict[str, Any]]:
    if PRESETS_PATH.is_file():
        try:
            return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def get_preset(template_id: str) -> Optional[Dict[str, Any]]:
    return load_presets().get(template_id)


def compose_mockup(*, template_id: str, plate_path: Path, logo_path: Path,
                   out_path: Path, skus: Optional[List[Dict[str, Any]]] = None,
                   quads: Optional[List[List]] = None,
                   erases: Optional[List[Dict[str, Any]]] = None,
                   glyph_box: Optional[Sequence[int]] = None,
                   shading: float = 0.5) -> Dict[str, Any]:
    """Full typography pass: erase badges on the plate, compose panels, warp them."""
    if template_id not in DEFAULT_TEMPLATES:
        raise ValueError(f"unknown template {template_id!r}")
    tpl = DEFAULT_TEMPLATES[template_id]
    preset = get_preset(template_id) or {}
    quads = quads or preset.get("quads")
    erases = erases or preset.get("erases") or []
    glyph_box = glyph_box or preset.get("glyph_box")
    skus = skus or preset.get("skus")
    if not quads or len(quads) < 1 or not skus or len(skus) < len(quads):
        raise ValueError("compose requires per-face quads and one SKU spec per face "
                         "(from the template preset or the request body)")

    plate = Image.open(plate_path).convert("RGB")
    logo, field_color = prepare_logo(Path(logo_path))
    glyph_img = extract_glyph(plate, glyph_box) if glyph_box else None

    for e in erases:
        if "rect" in e:
            plate = erase_rect(plate, e["rect"], feather=float(e.get("feather", 26.0)))
        else:
            plate = erase_circle(plate, e["center"], float(e["r"]))

    plate0 = plate.copy()
    for i, (quad, sku) in enumerate(zip(quads, skus)):
        glyph_here = glyph_img if sku.get("glyph", True) else None
        panel = render_panel(
            size=tpl["panel"]["size"], badge=tpl["badge"],
            title={**tpl["title"], "text": sku["title"]},
            subtitle={**tpl["subtitle"], "text": sku.get("subtitle", tpl["subtitle"]["text"])},
            glyph=(tpl["glyph"] if glyph_here is not None else None),
            icons={**tpl["icons"], "kinds": sku.get("icons", tpl["icons"]["kinds"])}
            if tpl.get("icons") else None,
            footer={**tpl["footer"], "text": sku["weight"]},
            logo=logo, glyph_img=glyph_here,
            gold=tuple(sku.get("gold", (196, 160, 74))), field_color=field_color,
        )
        plate = warp_panel(plate, panel, quad, shading=shading)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plate.save(out_path, quality=95)
    return {
        "template_id": template_id, "out_path": str(out_path),
        "size": list(plate.size), "skus": [s.get("title") for s in skus],
        "quads": len(quads), "erases": len(erases),
        "note": "Deterministic compositing: real logo + real fonts warped onto the "
                "plate's pouch faces. Text is composited, never generated.",
    }
