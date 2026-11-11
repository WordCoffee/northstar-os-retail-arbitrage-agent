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
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

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
    # A single number bows both sides the same; a (left, right) pair lets a
    # measured pouch keep the asymmetry a real pack has. Positive is outward.
    if np.ndim(bow_x) == 0:
        bow_l = bow_r = float(bow_x)
    else:
        bow_l, bow_r = (float(v) for v in np.asarray(bow_x).reshape(2))
    grid = np.zeros((ny, nx, 2), dtype=float)
    for j in range(ny):
        t = j / (ny - 1) if ny > 1 else 0.0
        left = tl + (bl - tl) * t
        right = tr + (br - tr) * t
        axis = right - left
        norm = float(np.linalg.norm(axis))
        ux = axis / norm if norm > 1e-9 else np.array([1.0, 0.0])
        widen = float(np.sin(np.pi * t))
        left = left - ux * (bow_l * widen)
        right = right + ux * (bow_r * widen)
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


def feather_sigma(residual_px: float, *, lo: float = 1.0, hi: float = 12.0,
                  per_px: float = 2.5) -> float:
    """Edge feather (sigma, px) derived from the measured geometric residual.

    The halo measurement (reports/rea_probe/warp_probe.json) is blunt about this:
    feathering creates no bleed of its own, it only smears whatever geometric
    error is already there. So the feather must follow the residual — a 0.2 px
    fit needs no softening, a 2 px fit needs a few pixels of ramp, and past the
    hi clamp the label is not trustworthy and `compose()` refuses instead.

    A NON-FINITE residual is not a measurement: it means the fit itself failed.
    Returning the default clamp here hid that failure and produced a normal-
    looking composite with a hard edge, so it is refused instead.
    """
    try:
        residual = float(residual_px)
    except (TypeError, ValueError):
        return float(lo)
    if not math.isfinite(residual):
        raise ValueError(
            f"residual_px must be a finite measurement, got {residual_px!r} "
            "(the warp fit failed; refusing to feather it)")
    if residual <= 0:                               # zero or no useful signal
        return float(lo)
    return float(min(hi, max(lo, residual * float(per_px))))


def warp_panel(photo: Image.Image, panel: Image.Image, quad: Sequence,
               shading: float = 0.5, realism: Optional[Dict[str, Any]] = None,
               maps: Optional[Any] = None,
               metrics_out: Optional[Dict[str, Any]] = None,
               grid: Optional[Any] = None, mesh_iters: int = 3,
               edge_feather: Optional[float] = None) -> Image.Image:
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
    # Pixel-centre convention: panel pixel (0,0) is the CENTRE of the first
    # pixel and must land on the quad's top-left corner. Using PW/PH here mapped
    # the panel's outer EDGE to the corner, which shifted the print half a pixel
    # and dropped the last row/column from the face.
    H = _homography([(0, 0), (PW - 1, 0), (PW - 1, PH - 1), (0, PH - 1)], list(quad))
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
    # A pixel whose centre lands exactly on the quad boundary is INSIDE the
    # printed face; the inverse homography returns -1e-13 there because the fit
    # is numeric, not symbolic. Without an epsilon that boundary row/column is
    # rejected and a 1 px line of plate shows along every edge of the label.
    eps = 1e-6
    valid = ((u >= -eps) & (u <= PW - 1 + eps)
             & (v >= -eps) & (v <= PH - 1 + eps))
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
    if edge_feather:
        # Ramp INWARD from the panel's own border, never outward. The halo probe
        # showed outward paint is the entire bleed (1 px overshoot = 28 % of the
        # panel's contrast); an inward ramp cannot create one, it only softens
        # the print where it meets the surface.
        # + half the ramp at the boundary gives the geometric edge 50 %
        # coverage (an anti-aliased edge) instead of erasing it, so a corner
        # that lands exactly on the quad is still painted.
        inside = np.minimum(np.minimum(u, PW - 1 - u), np.minimum(v, PH - 1 - v))
        ramp = np.clip((inside + 0.5 * float(edge_feather)) / max(1e-6, float(edge_feather)),
                       0.0, 1.0)
        samp[..., 3] = samp[..., 3] * ramp
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

    A design panel is RGB (the vector artwork is opaque), and this function
    indexes an alpha channel, so the panel is converted here: passing an RGB
    panel used to raise a broadcast error instead of printing a label.
    """
    x0, y0, x1, y1 = [int(v) for v in rect]
    if x1 - x0 < 4 or y1 - y0 < 4:
        raise ValueError(f"label band has no area: {(x0, y0, x1, y1)}")
    panel = panel.convert("RGBA")
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


# ── panel composite + plate face detection ──────────────────────────────────

def _quad_area(quad: Sequence) -> float:
    """Shoelace area of a 4-point polygon, in px^2."""
    pts = [(float(p[0]), float(p[1])) for p in quad]
    s = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


def composite_panel_onto_quad(plate: Image.Image, panel: Image.Image,
                              quad: Sequence[Sequence[float]], *,
                              feather: Optional[float] = 1.5,
                              shading: float = 0.0,
                              realism: Optional[Dict[str, Any]] = None,
                              maps: Optional[Any] = None,
                              grid: Optional[Any] = None,
                              crop_to_content: bool = True) -> Image.Image:
    """Warp a designed RGBA panel onto a plate's four-corner face quad.

    This is the product-picture primitive: the plate is a photograph of the
    package, the panel is the artwork that belongs on its face, and the result
    is the plate at its own size. The panel's own corners are mapped exactly to
    `quad` (a 4-point homography), so registration does not depend on a guess;
    pixels whose panel coordinate falls outside the artwork are left as the
    photograph, so nothing is painted outside the face.

    `crop_to_content` removes a transparent trim margin before the warp: a
    designed panel exported at a fixed canvas often carries a few transparent
    pixels of bleed, and those must not consume part of the printed face.

    `shading` (0..1) and `realism` opt into the surface pass in
    :func:`warp_panel`; the default 0 is a pure composite, which is what a
    contract check wants and what a flat plate needs.
    """
    if plate is None or not isinstance(plate, Image.Image):
        raise TypeError("plate must be a PIL Image")
    if panel is None or not isinstance(panel, Image.Image):
        raise TypeError("panel must be a PIL Image")
    if quad is None or len(quad) != 4:
        raise ValueError("quad must have four (x, y) corners")
    if _quad_area(quad) < 4.0:
        raise ValueError("quad area is degenerate; refusing to composite")

    base = plate.convert("RGB")
    art = panel.convert("RGBA")

    if crop_to_content:
        alpha = art.getchannel("A").point(lambda v: 255 if v > 8 else 0)
        box = alpha.getbbox()
        if box is not None:
            bw, bh = box[2] - box[0], box[3] - box[1]
            if bw >= 4 and bh >= 4 and (bw * bh) >= 0.25 * art.width * art.height:
                art = art.crop(box)

    if shading and maps is None:
        maps = cr.build_surface_maps(base)

    return warp_panel(base, art, quad, shading=shading, realism=realism,
                      maps=maps, grid=grid, edge_feather=feather)


def find_panel_quad(image: Union[Image.Image, str, Path], *,
                    inset_x: float = 0.075, inset_top: float = 0.20,
                    inset_bottom: float = 0.10,
                    threshold: float = 26.0) -> List[List[float]]:
    """Find the printable front face of the package in a plate, or refuse.

    The measurement is the one `pouch_label.measure_face` already uses (chroma
    segmentation, sub-pixel side edges, RANSAC quadratic fit, inset from the
    weld and the base). A plate with no package in it is a refusal, never a
    guess: compositing artwork onto a flat studio shot is exactly how a label
    gets delivered when a product picture was asked for.

    Raises ``ValueError('plate_face_not_found: …')`` when there is no face, and
    ``ValueError('plate_face_unreliable: …')`` when a face was measured but its
    geometry residual is too large to print on.
    """
    if isinstance(image, Image.Image):
        img = image.convert("RGB")
    else:
        try:
            img = Image.open(image).convert("RGB")
        except Exception as exc:  # noqa: BLE001 - an unreadable plate is a refusal
            raise ValueError(f"plate_face_not_found: cannot open plate ({exc})") from exc

    try:
        import pouch_label  # local import: pouch_label imports this module
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"plate_face_not_found: face measurement unavailable ({exc})") from exc

    try:
        measured = pouch_label.measure_face(
            img, inset_x=inset_x, inset_top=inset_top,
            inset_bottom=inset_bottom, threshold=threshold)
    except ValueError as exc:
        raise ValueError(f"plate_face_not_found: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"plate_face_not_found: measurement failed ({exc})") from exc

    quad = measured.get("quad") if isinstance(measured, dict) else None
    if not quad or len(quad) != 4:
        raise ValueError("plate_face_not_found: measurement returned no quad")
    if _quad_area(quad) < 0.02 * img.width * img.height:
        raise ValueError(
            "plate_face_not_found: the measured face covers less than 2% of the "
            f"plate ({_quad_area(quad):.0f} px^2)")

    residual = measured.get("geom_residual_px")
    if residual is not None and float(residual) > pouch_label.MAX_GEOM_RESIDUAL_PX:
        raise ValueError(
            f"plate_face_unreliable: edge/mesh residual {float(residual):.2f} px "
            f"exceeds {pouch_label.MAX_GEOM_RESIDUAL_PX:.1f} px")
    return [[float(p[0]), float(p[1])] for p in quad]


def _filled_run(share, minimum: float, offset: int, stop: int):
    """The longest contiguous run of indices whose `share` clears `minimum`.

    Used to trim a contact shadow off a measured body: a shadow column covers a
    small share of the component's height, the body's columns cover most of it.
    Falls back to the whole span when no run clears the threshold, so a genuinely
    soft-edged package is measured rather than refused.
    """
    import numpy as np

    values = np.asarray(share, dtype=np.float32)
    if values.size == 0:
        return float(offset), float(stop)
    inside = values >= float(minimum)
    best_start, best_len, run_start = 0, 0, None
    for index, flag in enumerate(inside):
        if flag and run_start is None:
            run_start = index
        elif not flag and run_start is not None:
            if index - run_start > best_len:
                best_start, best_len = run_start, index - run_start
            run_start = None
    if run_start is not None and len(inside) - run_start > best_len:
        best_start, best_len = run_start, len(inside) - run_start
    if best_len <= 0:
        return float(offset), float(stop)
    return float(offset + best_start), float(offset + best_start + best_len)


def _runs(flags):
    """The contiguous True runs of a 1-D boolean array, as (start, stop) inclusive."""
    runs = []
    start = None
    for index, flag in enumerate(flags):
        if flag and start is None:
            start = index
        elif not flag and start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(flags) - 1))
    return runs


def find_cylinder_bands(image: Union[Image.Image, str, Path], *, count: int = 1,
                        threshold: float = 16.0,
                        min_width_frac: float = 0.12,
                        min_height_frac: float = 0.22,
                        ) -> List[List[float]]:
    """Measure the body of each rigid cylinder in a studio plate, or refuse.

    A pouch face is measured by chroma segmentation, which assumes the package is
    saturated kraft against a pale sweep. A real FLUX plate of a beige cylinder on
    a beige sweep defeats it: measured on the first real plate (2026-11-11) the
    "face" was a 153 x 121 px patch of shadow, and a correctly-gated picture went
    out with a 15 % label on a 70 % body.

    So a cylinder is measured by **difference from its own background**: the
    background colour is the median of the four corner patches, and a body is a
    column band that differs from it for most of its height. A contact shadow is
    different in colour but only for a thin slice of a column, so a column profile
    separates body from shadow without merging two units into one blob. A band too
    small to be a package is a refusal, never a smaller label.

    The mask cut is **relative to the plate's own subject contrast**, not a fixed
    16 levels: on a pale body against a pale sweep the silhouette edge differs by
    only a few levels, and a fixed cut drops it, so the measured body came out
    narrower than the body and the label was drawn small (D-016, measured
    2026-11-11: 479 px measured for a 500 px body, now 493 px). The cut stays at
    or below `threshold` and never below the noise floor, so a caller can tighten
    it but cannot make it looser than the plate justifies.
    """
    import numpy as np

    if isinstance(image, Image.Image):
        img = image.convert("RGB")
    else:
        try:
            img = Image.open(image).convert("RGB")
        except Exception as exc:  # noqa: BLE001 - an unreadable plate is a refusal
            raise ValueError(f"plate_face_not_found: cannot open plate ({exc})") from exc
    try:
        import cv2
    except Exception as exc:  # noqa: BLE001 - without cv2 there is no component pass
        raise ValueError(f"plate_face_not_found: cylinder measurement needs cv2 ({exc})") from exc

    rgb = np.asarray(img).astype(np.float32)
    h, w = rgb.shape[:2]
    patch = max(8, min(w, h) // 40)
    corners = np.concatenate([
        rgb[:patch, :patch].reshape(-1, 3), rgb[:patch, -patch:].reshape(-1, 3),
        rgb[-patch:, :patch].reshape(-1, 3), rgb[-patch:, -patch:].reshape(-1, 3)])
    background = np.median(corners, axis=0)
    diff = np.abs(rgb - background.reshape(1, 1, 3)).max(axis=2)
    # The plate sets its own contrast: 20 % of its strongest subject pixel, capped
    # by the caller's threshold and floored above the sweep's noise. See D-016.
    strong = float(np.percentile(diff, 99.5))
    cut = max(5.0, min(float(threshold), 0.20 * strong))
    mask = (diff > cut).astype(np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    # The body's *vertical* extent is measured on the caller's own cut, not the
    # fine one: the fine cut reaches into a soft contact shadow at the base and
    # grew the band by 8 % (measured 2026-11-11: bottom 1125 px for a 1050 px
    # body). The fine cut is for the silhouette edge only.
    firm = (diff > float(threshold)).astype(np.uint8)
    firm = cv2.morphologyEx(firm, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    firm = cv2.morphologyEx(firm, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))

    total = int(mask.sum())
    if total < 0.02 * w * h:
        raise ValueError("plate_face_not_found: the plate has no subject against its "
                         "own background")

    # A body is a column band that is masked for most of its height; a contact
    # shadow is masked for only a thin slice of a column. So each body is found
    # from the tallest column and grown outwards while the columns stay above a
    # fraction of that peak (hysteresis), which does not need the body and the
    # background to be far apart in colour at every pixel.
    columns = mask.sum(axis=0).astype(np.float32)
    bodies: List[List[float]] = []
    working = columns.copy()
    for _ in range(max(1, int(count))):
        if working.max() <= 0:
            break
        peak = int(working.argmax())
        threshold = max(0.35 * float(working[peak]), 0.02 * h)
        left = peak
        while left > 0 and columns[left - 1] >= threshold:
            left -= 1
        right = peak
        while right < w - 1 and columns[right + 1] >= threshold:
            right += 1
        working[max(0, left - 8):min(w, right + 9)] = 0.0
        if right - left < min_width_frac * w:
            continue
        band = firm[:, left:right + 1]
        rows = band.sum(axis=1).astype(np.float32) / float(right - left + 1)
        row_runs = [run for run in _runs(rows >= 0.35)
                    if run[1] - run[0] >= min_height_frac * h]
        if not row_runs:
            continue
        top, bottom = max(row_runs, key=lambda run: run[1] - run[0])
        bodies.append([float(left), float(top), float(right + 1), float(bottom + 1)])
    if not bodies:
        raise ValueError(
            "plate_face_not_found: no package-sized body in the plate "
            f"(nothing at least {min_width_frac:.0%} of the width and "
            f"{min_height_frac:.0%} of the height)")
    bodies.sort(key=lambda body: body[0])
    if len(bodies) < max(1, int(count)):
        raise ValueError(f"units_not_found: measured {len(bodies)} of {int(count)} "
                         "cylinder bodies")
    return [[round(value, 2) for value in body] for body in bodies[:max(1, int(count))]]


def find_label_band(image: Union[Image.Image, str, Path], *,
                    inset_x: float = 0.045, inset_top: float = 0.12,
                    inset_bottom: float = 0.09,
                    threshold: float = 26.0) -> Dict[str, Any]:
    """Measure the printable label band of a rigid cylinder, or refuse.

    A cylinder has no four-corner face: the label runs around the visible half
    of the tube, so what is measured is a *band* — the axis-aligned rectangle of
    the package's front face, inset from the shoulder and the base. The
    measurement reuses :func:`find_panel_quad` (the proven chroma segmentation
    and side-edge fit) and takes the bounding rectangle of that quad, so a bowed
    side still yields the band the label wraps.

    Raises ``ValueError('plate_face_not_found: …')`` when there is no cylinder
    in the plate. A plate with no package is never composited onto.
    """
    quad = find_panel_quad(image, inset_x=inset_x, inset_top=inset_top,
                           inset_bottom=inset_bottom, threshold=threshold)
    xs = [float(point[0]) for point in quad]
    ys = [float(point[1]) for point in quad]
    band = [min(xs), min(ys), max(xs), max(ys)]
    if band[2] - band[0] < 8 or band[3] - band[1] < 8:
        raise ValueError(f"plate_face_not_found: measured band has no area {band}")
    return {"band": [round(value, 2) for value in band], "quad": quad}


# ── several faces in one plate (a bundle) ───────────────────────────────────

def find_panel_quads(image: Union[Image.Image, str, Path], *, count: int = 1,
                     inset_x: float = 0.075, inset_top: float = 0.20,
                     inset_bottom: float = 0.10, threshold: float = 26.0,
                     ) -> List[List[List[float]]]:
    """Measure the front face of each package in a plate, left to right.

    A bundle picture holds two or three units. `find_panel_quad` measures one
    face by treating the tallest coloured object as the product; with three units
    that is still one of them. This segments the same foreground mask into
    components, keeps the ``count`` tallest (a prop or a shadow cannot outvote a
    package), sorts them left to right and measures each on its own crop with the
    pouch measurement, so the insets and the bow fit stay per-face.

    Fewer measured faces than asked for is the caller's refusal, not a guess: a
    bundle that shows one unit is not a bundle.
    """
    if isinstance(image, Image.Image):
        img = image.convert("RGB")
    else:
        img = Image.open(image).convert("RGB")
    import numpy as np

    import pouch_label

    if count <= 1:
        return [find_panel_quad(img, inset_x=inset_x, inset_top=inset_top,
                                inset_bottom=inset_bottom, threshold=threshold)]

    mask = None
    labels = None
    keep: List[int] = []
    found = pouch_label.package_components(img, threshold=threshold)
    if found is not None:
        labels, keep = found
        mask = (labels > 0)
    if mask is None or not mask.any():
        raise ValueError("plate_face_not_found: the plate has no separable subject")
    try:
        import cv2
    except Exception as exc:  # noqa: BLE001 - without cv2 there is no component pass
        raise ValueError(f"plate_face_not_found: multi-face measurement needs cv2 ({exc})") from exc

    total = mask.astype(bool).sum()
    n, labels, stats, _ = cv2.connectedComponentsWithStats(
        mask.astype(np.uint8), connectivity=8)
    boxes = []
    for index in range(1, n):
        x, y, w, h, area = stats[index]
        if area < 0.02 * total or h < 0.10 * img.height:
            continue
        boxes.append((index, int(x), int(y), int(w), int(h), int(area)))
    if not boxes:
        raise ValueError("plate_face_not_found: no package-sized component in the plate")
    boxes.sort(key=lambda box: -box[4])
    chosen = sorted(boxes[:max(1, int(count))], key=lambda box: box[1])

    rgb = np.asarray(img).copy()
    quads: List[List[List[float]]] = []
    for index, x, y, w, h, _area in chosen:
        # Measure each unit on its own: everything that is not this component is
        # flattened to the plate's own background, so the neighbouring units
        # cannot join the silhouette and the insets stay per face.
        left = max(0, x - int(w * 0.10))
        top = max(0, y - int(h * 0.06))
        right = min(img.width, x + w + int(w * 0.10))
        bottom = min(img.height, y + h + int(h * 0.06))
        crop = rgb[top:bottom, left:right].copy()
        component = labels[top:bottom, left:right] == index
        outside = ~component
        if outside.sum() < 64:
            continue
        background = np.median(crop[outside].reshape(-1, 3), axis=0)
        crop[outside] = background.astype(np.uint8)
        try:
            measured = find_panel_quad(Image.fromarray(crop), inset_x=inset_x,
                                       inset_top=inset_top,
                                       inset_bottom=inset_bottom,
                                       threshold=threshold)
        except ValueError:
            continue
        quads.append([[float(px + left), float(py + top)] for px, py in measured])
    if not quads:
        raise ValueError("plate_face_not_found: the components had no measurable face")
    return quads


# ── presets ─────────────────────────────────────────────────────────────────

DEFAULT_TEMPLATES: Dict[str, Dict[str, Any]] = {    "mogra-forest-dusk": {
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

# ── Base-plate neutralisation (blank-plate architecture) ─────────────────────
def neutralize_quad(img: Image.Image, quad: Sequence[Sequence[float]], *,
                    feather: int = 10, inset: float = 0.78) -> Tuple[Image.Image, Dict[str, Any]]:
    """Flatten everything under the label target BEFORE any realism pass.

    The compositor deliberately modulates print with the plate's own luminance so
    a label inherits creases. That same mechanism lets text the image model burned
    into the plate bleed THROUGH the label - measured 2026-10-30: a garbled
    '8551/0m0' and a ghosted logo survived `field_alpha=255`.

    This fills the label polygon with the plate's own median field colour, feathered
    so no seam shows. After it, the region has no edges for the realism pass to
    re-introduce.

    Returns (image, info) where info records the sampled colour and area.
    """
    base = img.convert("RGB").copy()
    pts = [(float(p[0]), float(p[1])) for p in quad]
    if len(pts) < 3:
        return base, {"neutralized": False, "reason": "quad_too_small"}

    mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(mask).polygon(pts, fill=255)

    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    inner = [(cx + (x - cx) * inset, cy + (y - cy) * inset) for x, y in pts]
    inner_mask = Image.new("L", base.size, 0)
    ImageDraw.Draw(inner_mask).polygon(inner, fill=255)

    arr = np.asarray(base)
    sel = np.asarray(inner_mask) > 0
    if int(sel.sum()) < 200:
        sel = np.asarray(mask) > 0
        inner_used = False
    else:
        inner_used = True
    if int(sel.sum()) < 50:
        return base, {"neutralized": False, "reason": "region_too_small"}

    field = np.median(arr[sel], axis=0).astype(int)
    fill = Image.new("RGB", base.size, tuple(int(v) for v in field))
    soft = mask.filter(ImageFilter.GaussianBlur(max(1, int(feather))))
    out = Image.composite(fill, base, soft)

    return out, {
        "neutralized": True,
        "field_rgb": [int(v) for v in field],
        "area_px": int((np.asarray(mask) > 0).sum()),
        "sampled_inner": inner_used,
        "feather_px": int(feather),
    }
