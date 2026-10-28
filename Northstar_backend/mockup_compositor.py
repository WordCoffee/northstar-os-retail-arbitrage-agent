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

import compositor_realism as cr

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


def mesh_grid(quad: Sequence, nx: int = 5, ny: int = 7,
              bow_x: float = 0.0, bow_y: float = 0.0) -> np.ndarray:
    """Build a quad mesh from four corners, with optional barrel bow.

    A pouch face is not planar: its side edges bow outward at mid-height and its
    top/bottom edges bow in the same way. `bow_x` moves the mid-height nodes
    outward along the row axis, `bow_y` moves the mid-width nodes along the
    column axis. With both at zero this is a bilinear grid over `quad`, i.e. the
    same geometry a homography produces, so passing it is always safe.

    Returns an (ny, nx, 2) float array of destination (x, y) node positions.
    `quad` order is top-left, top-right, bottom-right, bottom-left.
    """
    q = np.asarray(quad, dtype=float).reshape(4, 2)
    tl, tr, br, bl = q
    grid = np.zeros((ny, nx, 2), dtype=float)
    for j in range(ny):
        t = j / (ny - 1) if ny > 1 else 0.0
        left = tl + (bl - tl) * t
        right = tr + (br - tr) * t
        axis = right - left
        norm = float(np.linalg.norm(axis))
        ux = axis / norm if norm > 1e-9 else np.array([1.0, 0.0])
        widen = bow_x * float(np.sin(np.pi * t))
        left = left - ux * widen
        right = right + ux * widen
        for i in range(nx):
            s = i / (nx - 1) if nx > 1 else 0.0
            p = left + (right - left) * s
            if bow_y:
                # bow the top and bottom edges along the column normal
                uy = np.array([-ux[1], ux[0]])
                p = p + uy * (bow_y * float(np.sin(np.pi * s)) * (1.0 - 2.0 * t))
            grid[j, i] = p
    return grid


def _mesh_pos_and_tangents(grid: np.ndarray, uu: np.ndarray, vv: np.ndarray,
                           pw: float, ph: float):
    """Bilinear mesh position and its tangents at panel coords (uu, vv)."""
    ny, nx = grid.shape[:2]
    gx = np.clip(uu / max(1.0, pw - 1.0) * (nx - 1), 0, nx - 1 - 1e-9)
    gy = np.clip(vv / max(1.0, ph - 1.0) * (ny - 1), 0, ny - 1 - 1e-9)
    i0 = np.floor(gx).astype(int)
    j0 = np.floor(gy).astype(int)
    a = (gx - i0)[..., None]
    b = (gy - j0)[..., None]
    p00 = grid[j0, i0]
    p10 = grid[j0, i0 + 1]
    p01 = grid[j0 + 1, i0]
    p11 = grid[j0 + 1, i0 + 1]
    pos = (1 - a) * (1 - b) * p00 + a * (1 - b) * p10 + (1 - a) * b * p01 + a * b * p11
    d_du = ((1 - b) * (p10 - p00) + b * (p11 - p01)) * ((nx - 1) / max(1.0, pw - 1.0))
    d_dv = ((1 - a) * (p01 - p00) + a * (p11 - p10)) * ((ny - 1) / max(1.0, ph - 1.0))
    return pos, d_du, d_dv


def _refine_to_mesh(uu: np.ndarray, vv: np.ndarray, px: np.ndarray, py: np.ndarray,
                    grid: np.ndarray, pw: float, ph: float, iters: int = 3):
    """Newton-solve the panel (u, v) whose mesh position lands on pixel (px, py).

    The homography inverse is the starting guess, so two or three iterations take
    a 5 px geometric error down to the hundredths of a pixel measured in
    reports/rea_probe/warp_probe.json.
    """
    if grid is None:
        return uu, vv
    for _ in range(max(0, int(iters))):
        pos, d_du, d_dv = _mesh_pos_and_tangents(grid, uu, vv, pw, ph)
        rx = px - pos[..., 0]
        ry = py - pos[..., 1]
        det = d_du[..., 0] * d_dv[..., 1] - d_dv[..., 0] * d_du[..., 1]
        det = np.where(np.abs(det) < 1e-9, 1e-9, det)
        step_u = (rx * d_dv[..., 1] - d_dv[..., 0] * ry) / det
        step_v = (d_du[..., 0] * ry - rx * d_du[..., 1]) / det
        uu = uu + step_u
        vv = vv + step_v
        # Keep the solve bounded without turning out-of-panel pixels into valid
        # ones: the caller's `valid` mask depends on u/v leaving [0, pw-1].
        uu = np.clip(uu, -pw, 2.0 * pw)
        vv = np.clip(vv, -ph, 2.0 * ph)
    return uu, vv


def warp_panel(photo: Image.Image, panel: Image.Image, quad: Sequence,
               shading: float = 0.5, realism: Optional[Dict[str, Any]] = None,
               maps: Optional[Any] = None,
               metrics_out: Optional[Dict[str, Any]] = None,
               grid: Optional[Any] = None, mesh_iters: int = 3) -> Image.Image:
    """4-point homography (panel -> quad), bilinear, realism-integrated.

    Pass ``grid`` (an (ny, nx, 2) node array, see :func:`mesh_grid`) to warp
    through a mesh instead of a single homography. A 5x7 mesh took the mean
    reprojection error against a synthetic curved face from 5.413 px to
    0.676 px (reports/rea_probe/warp_probe.json); the homography stays exact at
    the four corners, which is why it is still the fallback.

    With ``maps`` (a compositor_realism.SurfaceMaps built from the plate) the
    print takes the full surface-realism recipe: luminance displacement,
    soft-light shading, capped specular, grain sync, opt-in fold/AO/print-sim
    and a scene tonal match. ``shading`` is the master dial (0 = flat paste,
    0.5 = research default). Without ``maps`` it falls back to the legacy
    shading-only blend (kept for callers that have no plate access).
    """
    PW, PH = panel.size
    H = _homography([(0, 0), (PW, 0), (PW, PH), (0, PH)], list(quad))
    Hinv = np.linalg.inv(H)
    W, Hpx = photo.size
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    if grid is not None:
        g = np.asarray(grid, dtype=float)
        xs = list(xs) + [float(g[..., 0].min()), float(g[..., 0].max())]
        ys = list(ys) + [float(g[..., 1].min()), float(g[..., 1].max())]
    m = 6
    x0, x1 = max(0, int(min(xs)) - m), min(W, int(max(xs)) + m)
    y0, y1 = max(0, int(min(ys)) - m), min(Hpx, int(max(ys)) + m)
    gx, gy = np.meshgrid(np.arange(x0, x1), np.arange(y0, y1))
    pts = np.stack([gx.astype(float), gy.astype(float), np.ones_like(gx, dtype=float)], axis=-1)
    uv = pts @ Hinv.T
    u = uv[..., 0] / uv[..., 2]
    v = uv[..., 1] / uv[..., 2]

    if grid is not None:
        u, v = _refine_to_mesh(
            u, v, gx.astype(float), gy.astype(float),
            np.asarray(grid, dtype=float), float(PW), float(PH), iters=mesh_iters)

    # reality pass 1: luminance displacement (ink rides the surface's folds)
    if maps is not None and shading > 0:
        params = {**cr.DEFAULTS, **(realism or {})}
        if params.get("displacement_k", 0) > 0:
            sm = maps.slice(x0, x1, y0, y1)
            scale_u = PW / max(1.0, float(x1 - x0))
            scale_v = PH / max(1.0, float(y1 - y0))
            du, dv = cr.displacement_shift(sm, scale_u, scale_v, params)
            u = u + du
            v = v + dv
            if metrics_out is not None:
                metrics_out["displacement_max_px"] = float(
                    max(np.abs(du).max(), np.abs(dv).max()) / max(scale_u, scale_v))

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
    base = np.array(photo, dtype=np.float32)
    region = base[y0:y1, x0:x1]

    if maps is not None and shading > 0:
        sm = maps.slice(x0, x1, y0, y1)
        params = {**cr.DEFAULTS, **(realism or {})}
        region, metrics = cr.composite_panel(region, samp, sm, params, shading=shading)
        if metrics_out is not None:
            metrics_out.update(metrics)
    else:
        # legacy path: flat shading blend (no plate maps available)
        alpha = samp[..., 3:4] / 255.0
        luma = region.mean(axis=2, keepdims=True)
        ref = np.median(luma) + 1e-6
        mod = 1.0 + shading * (np.clip(luma / ref, 0.85, 1.15) - 1.0)
        ink = samp[..., :3] * mod
        region[:] = np.clip(ink * alpha + region * (1 - alpha), 0, 255)
    return Image.fromarray(base.astype("uint8"), "RGB")


def warp_cylinder(photo: Image.Image, panel: Image.Image, rect: Sequence,
                  shading: float = 0.5) -> Image.Image:
    """Wrap a flat panel around a vertical cylinder seen frontally (front half).

    rect = (x0, y0, x1, y1) of the tube's visible face. Panel width maps across
    the visible arc (180deg) with horizontal foreshortening toward the edges and
    a cylindrical luminance falloff, multiplied with the plate's own shading so
    the print follows the tube's light.
    """
    x0, y0, x1, y1 = [int(v) for v in rect]
    cx = (x0 + x1) / 2.0
    R = max(1.0, (x1 - x0) / 2.0)
    PW, PH = panel.size
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
    d = (gx - cx) / R
    valid = np.abs(d) < 1.0
    theta = np.arcsin(np.clip(d, -1.0, 1.0))
    u = (theta / np.pi + 0.5) * (PW - 1)
    v = (gy - y0) / max(1, (y1 - y0)) * (PH - 1)
    pa = np.asarray(panel, dtype=np.float32)
    u0 = np.floor(np.clip(u, 0, PW - 1)).astype(int)
    v0 = np.floor(np.clip(v, 0, PH - 1)).astype(int)
    u1 = np.minimum(u0 + 1, PW - 1)
    v1 = np.minimum(v0 + 1, PH - 1)
    wu = np.clip(u - u0, 0, 1)[..., None]
    wv = np.clip(v - v0, 0, 1)[..., None]
    samp = (pa[v0, u0] * (1 - wu) * (1 - wv) + pa[v0, u1] * wu * (1 - wv)
            + pa[v1, u0] * (1 - wu) * wv + pa[v1, u1] * wu * wv)
    out = np.array(photo, dtype=np.float32)
    region = out[y0:y1 + 1, x0:x1 + 1]
    cyl = np.cos(theta) ** 0.45
    cyl = 1.0 + shading * (cyl - 1.0)
    plate_luma = region.mean(axis=2, keepdims=True) / 255.0
    ink = samp[..., :3] * cyl[..., None] * (0.65 + 0.55 * plate_luma)
    alpha = (samp[..., 3:4] / 255.0) * valid[..., None]
    region[:] = np.clip(ink * alpha + region * (1 - alpha), 0, 255)
    return Image.fromarray(out.astype("uint8"), "RGB")


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
                   shading: float = 0.5,
                   realism: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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

    # surface maps measured once from the (erased) plate; both faces share them
    maps = cr.build_surface_maps(plate)
    params = {**cr.DEFAULTS, **(realism or {})}
    face_metrics: List[Dict[str, Any]] = []
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
        fm: Dict[str, Any] = {}
        plate = warp_panel(plate, panel, quad, shading=shading,
                           realism=params, maps=maps, metrics_out=fm)
        face_metrics.append({k: (round(v, 4) if isinstance(v, float) else v)
                             for k, v in fm.items()})

    out_path.parent.mkdir(parents=True, exist_ok=True)
    plate.save(out_path, quality=95)
    return {
        "template_id": template_id, "out_path": str(out_path),
        "size": list(plate.size), "skus": [s.get("title") for s in skus],
        "quads": len(quads), "erases": len(erases),
        "realism": {k: v for k, v in params.items()},
        "face_metrics": face_metrics,
        "note": "Deterministic compositing: real logo + real fonts warped onto the "
                "plate's pouch faces with surface-realism passes (displacement, "
                "soft-light, specular, grain, tonal match). Text is composited, "
                "never generated.",
    }
