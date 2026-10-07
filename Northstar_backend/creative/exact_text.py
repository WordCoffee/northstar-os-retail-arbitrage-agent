"""Deterministic exact-text compositor.

The AI image lane is never the source of truth for text. This module draws the
final brand name, product name, descriptor, net weight and other copy with a
real font, then composites it onto the generated scene — as a rectangle or a
four-corner quad (perspective), with optional barrel curvature for jars.

Everything here is deterministic and offline: identical inputs produce
identical pixels. No network, no model, no randomness.

Public API
----------
* ``LabelSpec``            — the exact text to place.
* ``render_label_layer``   — render text into an RGBA label rect.
* ``quad_homography``      — solve the perspective mapping.
* ``warp_to_quad``         — perspective-warp an RGBA layer onto a quad.
* ``compose_exact_text``   — full compose of a ``LabelSpec`` onto a source image.
* ``compose_from_file``    — same, reading/writing PNG paths.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import presets

RGBAColor = Tuple[int, int, int, int]
Point = Tuple[float, float]
Quad = Sequence[Point]

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

# (serif, bold) -> ordered candidate filenames. First existing wins.
_FONT_CANDIDATES: Dict[Tuple[bool, bool], List[str]] = {
    (True, True): ["georgiab.ttf", "timesbd.ttf", "cambriab.ttf", "constanb.ttf", "georgia.ttf"],
    (True, False): ["georgia.ttf", "times.ttf", "cambria.ttc", "constan.ttf"],
    (False, True): ["seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "verdanab.ttf"],
    (False, False): ["segoeui.ttf", "arial.ttf", "calibri.ttf", "verdana.ttf", "tahoma.ttf"],
}


def _font_dirs() -> List[Path]:
    dirs: List[Path] = []
    env = os.environ.get("NORTHSTAR_FONT_DIR")
    if env:
        dirs.append(Path(env))
    windir = os.environ.get("WINDIR", r"C:\Windows")
    dirs.append(Path(windir) / "Fonts")
    dirs.append(Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts")
    # A few common *nix locations (harmless on Windows).
    dirs.extend([Path("/usr/share/fonts"), Path("/Library/Fonts")])
    return dirs


def _find_font_file(serif: bool, bold: bool) -> Optional[Path]:
    for d in _font_dirs():
        if not d.exists():
            continue
        for name in _FONT_CANDIDATES[(serif, bold)]:
            p = d / name
            if p.exists():
                return p
    return None


# --- bundled brand fonts (SIL Open Font License 1.1) ------------------------
# Libre Baskerville (display/serif) + DM Sans (UI/sans) are the Northstar OS
# design-system fonts, adopted as the Mogra display/UI fonts. Both are OFL 1.1
# and shipped under assets/fonts/ with their license texts. If they are absent,
# the compositor falls back to OS fonts and reports that honestly.
_BRAND_FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_BRAND_FILES = {
    (True, True): "LibreBaskerville-VF.ttf",
    (True, False): "LibreBaskerville-VF.ttf",
    (False, True): "DMSans-VF.ttf",
    (False, False): "DMSans-VF.ttf",
}
_BRAND_WEIGHT = {(True, True): 700, (True, False): 400, (False, True): 700, (False, False): 500}


def _brand_font_dir() -> Path:
    env = os.environ.get("NORTHSTAR_BRAND_FONT_DIR")
    return Path(env) if env else _BRAND_FONT_DIR


def _norm_axis(name: Any) -> str:
    try:
        return (name.decode() if isinstance(name, (bytes, bytearray)) else str(name)).lower()
    except Exception:
        return ""


def _apply_weight(font: ImageFont.FreeTypeFont, weight: int) -> None:
    """Set variable-font axes (weight, optical size) if the face supports them."""
    try:
        axes = font.get_variation_axes()
    except Exception:
        return
    if not axes:
        return
    values: List[float] = []
    for a in axes:
        nm = _norm_axis(a.get("name", ""))
        try:
            if "weight" in nm:
                values.append(float(weight))
            elif "optical" in nm or nm == "opsz":
                values.append(14.0)
            else:
                values.append(float(a.get("default", a.get("minimum", 0))))
        except Exception:
            values.append(float(a.get("default", a.get("minimum", 0)) or 0))
    try:
        font.set_variation_by_axes(values)
    except Exception:
        pass


def brand_fonts() -> Dict[str, Any]:
    """Report the bundled brand fonts (honest: says when it falls back)."""
    d = _brand_font_dir()
    serif = d / "LibreBaskerville-VF.ttf"
    sans = d / "DMSans-VF.ttf"
    bundled = serif.exists() and sans.exists()
    return {
        "dir": str(d),
        "bundled": bundled,
        "serif": serif.name if serif.exists() else None,
        "sans": sans.name if sans.exists() else None,
        "license": "SIL Open Font License 1.1",
        "source": "brand" if bundled else "system_fallback",
    }


def font_source(serif: bool, bold: bool) -> str:
    """Which face ``load_font`` will use: bundled brand font or OS fallback."""
    fe = _BRAND_FILES[(serif, bold)]
    if (_brand_font_dir() / fe).exists():
        return "brand"
    if _find_font_file(serif, bold) is not None:
        return "system"
    return "default"


_FONT_CACHE: Dict[Tuple[bool, bool, int], ImageFont.FreeTypeFont] = {}


def load_font(size: int, *, serif: bool = False, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a real font at ``size`` px.

    Prefers the bundled brand font (correct weight via variable axes), then an
    OS font, then Pillow's default — deterministic at every step.
    """
    size = max(6, int(size))
    key = (serif, bold, size)
    cached = _FONT_CACHE.get(key)
    if cached is not None:
        return cached

    brand_path = _brand_font_dir() / _BRAND_FILES[(serif, bold)]
    if brand_path.exists():
        font = ImageFont.truetype(str(brand_path), size)
        _apply_weight(font, _BRAND_WEIGHT[(serif, bold)])
    else:
        path = _find_font_file(serif, bold)
        if path is not None:
            font = ImageFont.truetype(str(path), size)
        else:  # pragma: no cover - only when no font at all is discoverable
            font = ImageFont.load_default(size=size)
    _FONT_CACHE[key] = font
    return font


# ---------------------------------------------------------------------------
# Spec
# ---------------------------------------------------------------------------

@dataclass
class LabelSpec:
    """The exact text to composite. Fields default to empty (not drawn)."""

    brand: str = ""
    tagline: str = ""
    product_name: str = ""
    descriptor: str = ""
    net_weight: str = ""
    ingredients: str = ""
    rear_placeholders: List[str] = field(default_factory=list)
    extra_lines: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LabelSpec":
        return cls(
            brand=(d.get("brand") or "").strip(),
            tagline=(d.get("tagline") or "").strip(),
            product_name=(d.get("product_name") or d.get("title") or "").strip(),
            descriptor=(d.get("descriptor") or d.get("subtitle") or "").strip(),
            net_weight=(d.get("net_weight") or "").strip(),
            ingredients=(d.get("ingredients") or "").strip(),
            rear_placeholders=list(d.get("rear_placeholders") or []),
            extra_lines=list(d.get("extra_lines") or []),
        )

    def texts(self) -> List[str]:
        out = [self.brand, self.tagline, self.product_name, self.descriptor,
               self.net_weight, self.ingredients, *self.extra_lines, *self.rear_placeholders]
        return [t for t in out if t]


# ---------------------------------------------------------------------------
# Brand-content guard
# ---------------------------------------------------------------------------

class BrandContentError(ValueError):
    """Raised when a Mogra label would invent regulated/compliance content."""


def check_brand_content(spec: LabelSpec, *, enabled: bool = True) -> None:
    """Refuse to composite tokens that would fabricate compliance data.

    This is a guard, not a filter: it fails loudly so no invented certification
    seal, nutrition panel, UPC, lot code, or supplier statement can be drawn.
    """
    if not enabled:
        return
    blob = " ".join(spec.texts()).lower()
    for token in presets.FORBIDDEN_CONTENT_TOKENS:
        if token in blob:
            raise BrandContentError(
                f"refusing to composite disallowed content token: {token!r} "
                f"(Mogra brand rule: no invented seals, nutrition facts, UPCs, "
                f"lot codes, or supplier/legal statements)"
            )


# ---------------------------------------------------------------------------
# Text layout
# ---------------------------------------------------------------------------

def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
          max_w: float) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    cur = words[0]
    for w in words[1:]:
        trial = f"{cur} {w}"
        if _text_width(draw, trial, font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _draw_centered(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont,
                   cx: float, y: float, fill: RGBAColor) -> float:
    """Draw ``text`` centred on ``cx`` with its top at ``y``. Returns new y."""
    box = draw.textbbox((0, 0), text, font=font)
    w = box[2] - box[0]
    h = box[3] - box[1]
    draw.text((cx - w / 2 - box[0], y - box[1]), text, font=font, fill=fill)
    return y + h


def _fit_font(draw: ImageDraw.ImageDraw, text: str, size: float, *,
              serif: bool, bold: bool, max_w: float, floor: int = 8) -> ImageFont.FreeTypeFont:
    """Height-derived size, shrunk so a single line fits ``max_w`` (no clipping)."""
    s = max(floor, int(size))
    font = load_font(s, serif=serif, bold=bold)
    if not text or max_w <= 0:
        return font
    w = _text_width(draw, text, font)
    if w > max_w:
        s = max(floor, int(s * max_w / w))
        font = load_font(s, serif=serif, bold=bold)
    return font


def _fit_wrap_font(draw: ImageDraw.ImageDraw, text: str, size: float, *,
                   serif: bool, bold: bool, max_w: float,
                   floor: int = 8) -> ImageFont.FreeTypeFont:
    """Shrink until the longest word fits ``max_w`` so wrapping never overflows."""
    s = max(floor, int(size))
    words = [w for w in text.split() if w]
    if not words:
        return load_font(s, serif=serif, bold=bold)
    while s > floor:
        font = load_font(s, serif=serif, bold=bold)
        if max(_text_width(draw, wd, font) for wd in words) <= max_w:
            return font
        s = int(s * 0.92)
    return load_font(floor, serif=serif, bold=bold)


def render_label_layer(spec: LabelSpec, size: Tuple[int, int],
                       style: Dict[str, Any]) -> Image.Image:
    """Render ``spec`` into an RGBA layer of ``size`` (w, h) using ``style``.

    The layout is a classic front-of-pack block:
    brand / tagline / rule / product / descriptor / net weight / extras.
    Font sizes scale with the layer height so presets are resolution independent.
    """
    w, h = int(size[0]), int(size[1])
    w = max(w, 32)
    h = max(h, 32)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    ink: RGBAColor = tuple(style.get("ink", (26, 44, 34, 255)))  # type: ignore[assignment]
    accent: RGBAColor = tuple(style.get("accent", ink))  # type: ignore[assignment]
    muted: RGBAColor = tuple(style.get("muted", ink))  # type: ignore[assignment]
    serif = bool(style.get("serif", True))
    panel = style.get("panel", None)
    radius = int(float(style.get("radius_frac", 0.05)) * min(w, h))
    pad = int(float(style.get("padding_frac", 0.10)) * min(w, h))
    border = int(float(style.get("border_frac", 0.0)) * min(w, h))
    shadow = bool(style.get("shadow", False))

    if panel is not None:
        panel_rgba: RGBAColor = tuple(panel)  # type: ignore[assignment]
        if shadow:
            sh = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sh)
            off = max(2, int(0.012 * h))
            sd.rounded_rectangle([off, off, w - 1, h - 1], radius=radius,
                                 fill=(0, 0, 0, 90))
            sh = sh.filter(ImageFilter.GaussianBlur(max(2, off)))
            layer = Image.alpha_composite(layer, sh)
            draw = ImageDraw.Draw(layer)
        draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=panel_rgba)
        if border > 0:
            draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius,
                                   outline=accent, width=border)

    inner_w = w - 2 * pad
    cx = w / 2

    # Base type scale relative to layer height, then width-fitted so nothing clips.
    f_brand = _fit_font(draw, spec.brand, h * 0.115, serif=serif, bold=True, max_w=inner_w)
    f_tag = _fit_font(draw, spec.tagline, h * 0.052, serif=serif, bold=False, max_w=inner_w)
    f_prod = _fit_wrap_font(draw, spec.product_name, h * 0.150, serif=serif, bold=True,
                            max_w=inner_w)
    f_desc = _fit_wrap_font(draw, spec.descriptor, h * 0.062, serif=serif, bold=False,
                            max_w=inner_w)
    f_weight = _fit_font(draw, spec.net_weight, h * 0.066, serif=False, bold=True,
                         max_w=inner_w)
    f_small = load_font(int(h * 0.044), serif=False, bold=False)

    y = pad
    if spec.brand:
        y = _draw_centered(draw, spec.brand, f_brand, cx, y, ink)
    if spec.tagline:
        y += int(h * 0.010)
        y = _draw_centered(draw, spec.tagline, f_tag, cx, y, accent)

    if spec.brand or spec.tagline:
        rw = inner_w * 0.34
        ry = y + int(h * 0.028)
        draw.line([cx - rw / 2, ry, cx + rw / 2, ry], fill=accent,
                  width=max(1, int(h * 0.006)))
        y = ry

    # Product + descriptor as the visual centre of the panel.
    block: List[Tuple[str, ImageFont.FreeTypeFont, RGBAColor, int]] = []
    if spec.product_name:
        for ln in _wrap(draw, spec.product_name, f_prod, inner_w):
            block.append((ln, f_prod, ink, int(h * 0.010)))
    if spec.descriptor:
        for ln in _wrap(draw, spec.descriptor, f_desc, inner_w):
            block.append((ln, f_desc, muted, int(h * 0.010)))
    for ln, font, color, gap in block:
        y += gap
        y = _draw_centered(draw, ln, font, cx, y, color)

    extras: List[Tuple[str, ImageFont.FreeTypeFont, RGBAColor]] = []
    if spec.net_weight:
        extras.append((spec.net_weight, f_weight, ink))
    if spec.ingredients:
        for ln in _wrap(draw, f"Ingredients: {spec.ingredients}", f_small, inner_w):
            extras.append((ln, f_small, muted))
    for ln in spec.extra_lines:
        for wl in _wrap(draw, ln, f_small, inner_w):
            extras.append((wl, f_small, muted))
    for ln in spec.rear_placeholders:
        for wl in _wrap(draw, ln, f_small, inner_w):
            extras.append((wl, f_small, muted))

    # Anchor trailing extras to the bottom of the panel.
    if extras:
        gap = int(h * 0.014)
        heights = [draw.textbbox((0, 0), t, font=f)[3] - draw.textbbox((0, 0), t, font=f)[1]
                   for t, f, _ in extras]
        block_h = sum(heights) + gap * (len(extras) - 1)
        y = max(y + int(h * 0.02), h - pad - block_h)
        for (ln, font, color), hh in zip(extras, heights):
            _draw_centered(draw, ln, font, cx, y, color)
            y += hh + gap

    return layer


# ---------------------------------------------------------------------------
# Perspective / quad mapping
# ---------------------------------------------------------------------------

def quad_homography(dst_quad: Quad, src_quad: Quad) -> List[float]:
    """Solve the 8 PIL PERSPECTIVE coefficients mapping destination -> source.

    For an output pixel ``(x, y)`` the sampler reads
    ``u = (a x + b y + c) / (g x + h y + 1)`` and
    ``v = (d x + e y + f) / (g x + h y + 1)``.
    Both quads are four points in the same corner order.
    """
    import numpy as np

    a_rows: List[List[float]] = []
    b_vals: List[float] = []
    for (x, y), (u, v) in zip(dst_quad, src_quad):
        a_rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b_vals.append(u)
        a_rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b_vals.append(v)
    a = np.asarray(a_rows, dtype=float)
    b = np.asarray(b_vals, dtype=float)
    # Least-squares: exact for 4 correspondences, well-posed for >4.
    coeffs, *_ = np.linalg.lstsq(a, b, rcond=None)
    return [float(c) for c in coeffs]


def _apply_curvature(layer: Image.Image, curvature: float, *, max_wrap: float = 0.95) -> Image.Image:
    """Cylindrical horizontal foreshortening so a flat label reads as wrapped.

    Each output column is sourced through an ``asin`` mapping, compressing the
    label toward its left and right edges the way a flat label wraps a cylinder.
    Rows are untouched, so text stays sharp and nothing smears. ``curvature`` in
    ``0..1`` scales the wrap (0 = flat).
    """
    if curvature <= 0:
        return layer
    import numpy as np

    wrap = max(0.0, min(max_wrap, float(curvature)))
    half = (math.pi / 2.0) * wrap
    sin_half = math.sin(half) or 1.0
    w, h = layer.size

    arr = np.asarray(layer.convert("RGBA"), dtype=np.float64)
    xs = (np.arange(w) + 0.5) / w
    u = xs * 2.0 - 1.0                              # screen -1..1
    theta = np.arcsin(np.clip(u * sin_half, -1.0, 1.0))
    t = 0.5 + theta / (2.0 * half)                  # texture 0..1
    src_x = np.clip(t * w, 0, w - 1)
    x0 = np.floor(src_x).astype(int)
    x1 = np.clip(x0 + 1, 0, w - 1)
    fr = (src_x - x0)[None, :, None]
    sampled = arr[:, x0, :] * (1.0 - fr) + arr[:, x1, :] * fr
    return Image.fromarray(np.clip(sampled, 0, 255).astype("uint8"), "RGBA")


def warp_to_quad(layer: Image.Image, out_size: Tuple[int, int], quad: Quad,
                 curvature: float = 0.0) -> Image.Image:
    """Perspective-warp an RGBA ``layer`` onto ``quad`` in an ``out_size`` canvas."""
    w, h = layer.size
    if curvature > 0:
        layer = _apply_curvature(layer, curvature)
    src_quad = [(0.0, 0.0), (float(w), 0.0), (float(w), float(h)), (0.0, float(h))]
    coeffs = quad_homography(quad, src_quad)
    return layer.transform(
        (int(out_size[0]), int(out_size[1])),
        Image.PERSPECTIVE,
        coeffs,
        resample=Image.BICUBIC,
        fillcolor=(0, 0, 0, 0),
    )


# ---------------------------------------------------------------------------
# Surface helpers
# ---------------------------------------------------------------------------

def normalize_quad(surface: Dict[str, Any], size: Tuple[int, int]) -> Tuple[Quad, float]:
    """Return (quad_px, curvature) for a surface preset or explicit override."""
    w, h = size
    quad_norm = surface.get("quad_norm")
    if quad_norm is None and surface.get("rect_norm"):
        x0, y0, x1, y1 = surface["rect_norm"]
        quad_norm = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]
    if quad_norm is None:
        quad_norm = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]
    quad = [(float(p[0]) * w, float(p[1]) * h) for p in quad_norm]
    return quad, float(surface.get("curvature", 0.0) or 0.0)


def _quad_size(quad: Quad) -> Tuple[int, int]:
    def dist(a: Point, b: Point) -> float:
        return math.hypot(a[0] - b[0], a[1] - b[1])

    ul, ur, lr, ll = quad
    w = max(dist(ul, ur), dist(ll, lr))
    h = max(dist(ul, ll), dist(ur, lr))
    return max(16, int(round(w))), max(16, int(round(h)))


# ---------------------------------------------------------------------------
# Compose
# ---------------------------------------------------------------------------

def compose_exact_text(source: Image.Image, spec: LabelSpec,
                       surface: Dict[str, Any], style: Dict[str, Any],
                       *, supersample: int = 2, enforce_brand: bool = True,
                       return_params: bool = False):
    """Composite exact text onto ``source``. Returns the composited ``Image``.

    ``surface`` may be a preset dict (``quad_norm``/``curvature``) or an explicit
    override. ``style`` is a resolved style dict (see ``presets.STYLE_PRESETS``).
    """
    check_brand_content(spec, enabled=enforce_brand)
    if isinstance(style, str):  # tolerate a style preset key for convenience
        style = presets.get_style(style)
    src = source.convert("RGBA")
    size = src.size
    quad, curvature = normalize_quad(surface, size)

    lw, lh = _quad_size(quad)
    ss = max(1, int(supersample))
    layer = render_label_layer(spec, (lw * ss, lh * ss), style)
    warped = warp_to_quad(layer, size, quad, curvature)
    out = Image.alpha_composite(src, warped)

    if not return_params:
        return out
    params = {
        "quad_norm": [[round(p[0] / size[0], 5), round(p[1] / size[1], 5)] for p in quad],
        "curvature": curvature,
        "label_px": [lw, lh],
        "supersample": ss,
        "style": style,
        "spec": spec.__dict__,
    }
    return out, params


def compose_from_file(source_path: str | os.PathLike, out_path: str | os.PathLike,
                      spec: LabelSpec, surface: Dict[str, Any], style: Dict[str, Any],
                      *, supersample: int = 2, enforce_brand: bool = True) -> Dict[str, Any]:
    """Read ``source_path``, composite, write PNG to ``out_path``. Returns params."""
    with Image.open(source_path) as im:
        image = im.convert("RGBA")
    out, params = compose_exact_text(image, spec, surface, style,
                                     supersample=supersample,
                                     enforce_brand=enforce_brand,
                                     return_params=True)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.convert("RGB").save(out_path, format="PNG")
    params["source"] = str(source_path)
    params["output"] = str(out_path)
    params["size"] = list(out.size)
    return params
