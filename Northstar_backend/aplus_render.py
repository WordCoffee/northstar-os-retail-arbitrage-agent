"""A+ module renderer — the pixel half of `aplus_layout`.

`aplus_layout` decides WHERE everything goes; this module decides what it looks
like. Every rectangle it draws into comes from `aplus_layout.pixel_plan()`, so a
renderer cannot invent a safe area, a copy band or a tile position.

Design rules
------------
* **Deterministic.** Same inputs produce byte-identical output: no randomness, no
  system fonts, no timestamps in the pixels.
* **Copy is drawn, never generated.** The model paints the plate; type is
  composited here, which is the only way text stays correct.
* **Judged by measurement, not by claim.** `qa` reports the real canvas, the real
  contrast under every text block, the real type sizes, the real file weight.
  `assert_perfect()` refuses to hand back an asset that is not upload-ready.
* **Legibility is guaranteed by construction.** When the plate is too busy under
  the copy, a scrim is strengthened until the measured contrast passes; if no
  scrim can pass, the copy moves onto an opaque brand field. The mode actually
  used is recorded.
* **Prohibited copy is refused before a pixel is written**, via
  `specialists.image_aplus.screen_copy` (price, promotion, shipping, competitor,
  medical claim).

The output satisfies `specialists.image_aplus.validate_module_image`: exact
canvas, PNG or JPG, under 2 MB.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import aplus_layout as geo
import mockup_compositor as mc

try:  # the copy screen is the planner's, not a second opinion
    from specialists import image_aplus as aplus_spec
except Exception:  # pragma: no cover - import shape only
    aplus_spec = None  # type: ignore[assignment]

FONTS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

HEAD_FONT = "PlayfairDisplay.ttf"
BODY_FONT = "Inter.ttf"
HEAD_AXES = [700]
BODY_AXES = [14, 520]
KICKER_AXES = [14, 640]

#: Paper/bone + pine ink, the house palette. A caller may override any of these.
DEFAULT_BRAND: Dict[str, Any] = {
    "field": (247, 244, 237),
    "ink": (23, 38, 32),
    "accent": (170, 135, 82),
}

CONTRAST_LARGE = 3.0       # WCAG AA, >= 24 px
CONTRAST_BODY = 4.5        # WCAG AA, everything smaller
LARGE_TEXT_PX = 24
MIN_BODY_PX = 14
MIN_HEAD_PX = 24
MAX_BYTES = 2 * 1024 * 1024
SCRIM_STEPS = (0.0, 0.15, 0.28, 0.40, 0.52, 0.64, 0.76, 0.88)
MIN_IMAGE_SCALE = 0.5      # kept for callers; a plate must not be blown up past 2x
MAX_UPSCALE = 2.0
OVERLAY_MAX_VARIANCE = 0.06   # type may not sit on busy print
OVERLAY_MIN_CONTRAST = 6.0    # a photo backdrop needs more headroom than a field
COPY_STYLES = ("panel", "overlay")
LABEL_CELL = (240, 236, 226)   # quiet header cell in a comparison table
ZEBRA_CELL = (252, 250, 246)
TILE_KINDS = ("three_tiles", "four_tiles")
BAND_KINDS = ("header", "banner")
PREMIUM_KINDS = ("premium_desktop", "premium_mobile")


class AplusNotPerfect(ValueError):
    """Raised when a rendered module is not upload-ready. Carries the defects."""

    def __init__(self, problems: Sequence[str], detail: str = ""):
        self.problems = list(problems)
        self.detail = detail
        super().__init__("; ".join(self.problems) or "not upload-ready")


# ── colour ──────────────────────────────────────────────────────────────────

def _rgb(value: Any, default: Sequence[int]) -> Tuple[int, int, int]:
    """Accept '#rrggbb', 'rrggbb', a 3-sequence or None."""
    if value is None:
        return tuple(int(c) for c in default)  # type: ignore[return-value]
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) == 3:
            s = "".join(ch * 2 for ch in s)
        if len(s) != 6:
            raise ValueError(f"colour {value!r} is not a hex triplet")
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    seq = list(value)
    if len(seq) < 3:
        raise ValueError(f"colour {value!r} needs three channels")
    return tuple(max(0, min(255, int(c))) for c in seq[:3])  # type: ignore[return-value]


def _channel_luminance(c: float) -> float:
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(colour: Sequence[int]) -> float:
    """WCAG relative luminance, 0..1."""
    r, g, b = (float(c) for c in list(colour)[:3])
    return (0.2126 * _channel_luminance(r) + 0.7152 * _channel_luminance(g)
            + 0.0722 * _channel_luminance(b))


def contrast_ratio(a: Any, b: Any) -> float:
    """WCAG contrast ratio between two luminance values or two colours."""
    la = float(a) if isinstance(a, (int, float)) else luminance(a)
    lb = float(b) if isinstance(b, (int, float)) else luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def _brand(brand: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = dict(DEFAULT_BRAND)
    src.update({k: v for k, v in (brand or {}).items() if v is not None})
    out = {
        "field": _rgb(src.get("field"), DEFAULT_BRAND["field"]),
        "ink": _rgb(src.get("ink"), DEFAULT_BRAND["ink"]),
        "accent": _rgb(src.get("accent"), DEFAULT_BRAND["accent"]),
        "head_font": str(src.get("head_font") or HEAD_FONT),
        "body_font": str(src.get("body_font") or BODY_FONT),
        "head_axes": list(src.get("head_axes") or HEAD_AXES),
        "body_axes": list(src.get("body_axes") or BODY_AXES),
    }
    return out


# ── imagery ─────────────────────────────────────────────────────────────────

def _as_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value
    if isinstance(value, (bytes, bytearray)):
        return Image.open(io.BytesIO(bytes(value)))
    return Image.open(Path(value))


def cover(img: Image.Image, w: int, h: int) -> Tuple[Image.Image, float]:
    """object-fit: cover via the layout's crop maths.

    The returned factor is the SOURCE->BOX scale: 0.4 means the plate is
    downscaled to 40% (sharp), 2.0 means it is blown up 2x (soft).
    """
    crop = geo.crop_rect(img.width, img.height, w, h)
    src = crop["source"]
    box = img.crop((src["x"], src["y"], src["x"] + src["w"], src["y"] + src["h"]))
    scale = round(w / max(1, box.width), 4)
    return box.convert("RGB").resize((w, h), Image.LANCZOS), scale


def _paste_cover(canvas: Image.Image, img: Image.Image, rect: Dict[str, int]) -> float:
    placed, scale = cover(img, rect["w"], rect["h"])
    canvas.paste(placed, (rect["x"], rect["y"]))
    return scale


def _field_canvas(w: int, h: int, brand: Dict[str, Any]) -> Image.Image:
    return Image.new("RGB", (w, h), brand["field"])


# ── text engine ─────────────────────────────────────────────────────────────

def text_width(d: ImageDraw.ImageDraw, text: str, font, tracking: float = 0.0) -> float:
    if tracking:
        return sum(d.textlength(ch, font=font) for ch in text) + tracking * max(0, len(text) - 1)
    return float(d.textlength(text, font=font))


def wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: float,
         tracking: float = 0.0) -> List[str]:
    """Greedy word wrap. A single word wider than the band is hard-split."""
    words = str(text or "").split()
    if not words:
        return []
    lines: List[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if text_width(d, trial, font, tracking) <= max_w or not cur:
            if not cur and text_width(d, word, font, tracking) > max_w:
                # hard split an over-long token so it can never overflow
                chunk = ""
                for ch in word:
                    if text_width(d, chunk + ch, font, tracking) > max_w and chunk:
                        lines.append(chunk)
                        chunk = ch
                    else:
                        chunk += ch
                cur = chunk
                continue
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _font(name: str, size: int, axes: Optional[Sequence[float]]):
    return mc.load_font(name, int(size), axes)


def fit_block(d: ImageDraw.ImageDraw, text: str, *, name: str, axes: Optional[Sequence[float]],
              size: int, min_size: int, max_w: float, max_h: float,
              line_ratio: float = 1.22, tracking: float = 0.0) -> Dict[str, Any]:
    """Shrink until the whole string fits the band. `fits` is honest about failure."""
    size = int(size)
    floor = max(1, int(min_size))
    while size >= floor:
        f = _font(name, size, axes)
        lines = wrap(d, text, f, max_w, tracking)
        line_h = max(1, int(round(size * line_ratio)))
        widest = max((text_width(d, ln, f, tracking) for ln in lines), default=0.0)
        if lines and widest <= max_w + 0.5 and len(lines) * line_h <= max_h:
            return {"font": f, "lines": lines, "size": size, "line_h": line_h,
                    "fits": True, "width": widest}
        size -= 1
    f = _font(name, floor, axes)
    lines = wrap(d, text, f, max_w, tracking)
    line_h = max(1, int(round(floor * line_ratio)))
    return {"font": f, "lines": lines, "size": floor, "line_h": line_h,
            "fits": False, "width": max((text_width(d, ln, f, tracking) for ln in lines),
                                        default=0.0)}


def draw_block(d: ImageDraw.ImageDraw, block: Dict[str, Any], *, x: float, y: float,
               w: float, h: float, fill, align: str = "left", valign: str = "top",
               tracking: float = 0.0) -> Dict[str, Any]:
    """Draw a fitted block inside (x, y, w, h) and return its real ink box."""
    lines = block["lines"]
    font = block["font"]
    line_h = block["line_h"]
    total_h = line_h * len(lines)
    if valign == "middle":
        top = y + (h - total_h) / 2.0
    elif valign == "bottom":
        top = y + h - total_h
    else:
        top = y

    boxes: List[Tuple[float, float, float, float]] = []
    for i, line in enumerate(lines):
        tw = text_width(d, line, font, tracking)
        if align == "center":
            lx = x + (w - tw) / 2.0
        elif align == "right":
            lx = x + w - tw
        else:
            lx = x
        ly = top + i * line_h
        if tracking:
            cx = lx
            for ch in line:
                d.text((cx, ly), ch, font=font, fill=fill, anchor="la")
                cx += d.textlength(ch, font=font) + tracking
        else:
            d.text((lx, ly), line, font=font, fill=fill, anchor="la")
        boxes.append(d.textbbox((lx, ly), line, font=font, anchor="la"))
    if not boxes:
        return {"bbox": None, "lines": [], "size": block["size"], "fits": block["fits"]}
    return {
        "bbox": [int(min(b[0] for b in boxes)), int(min(b[1] for b in boxes)),
                 int(max(b[2] for b in boxes)), int(max(b[3] for b in boxes))],
        "lines": list(lines),
        "size": block["size"],
        "fits": block["fits"],
    }


# ── measured contrast ───────────────────────────────────────────────────────

def _shrink(rect: Dict[str, int], pad: int) -> Dict[str, int]:
    """Inset a rect, never below 1 px - used so a decorative keyline is not
    mistaken for the backdrop behind the type."""
    w = max(1, int(rect["w"]) - 2 * pad)
    h = max(1, int(rect["h"]) - 2 * pad)
    return {"x": int(rect["x"]) + pad, "y": int(rect["y"]) + pad, "w": w, "h": h}


def _rect_luminance_grid(img: Image.Image, rect: Dict[str, int], step: int = 16) -> np.ndarray:
    """Luminance of the composed background, sampled on a coarse grid."""
    x, y, w, h = rect["x"], rect["y"], rect["w"], rect["h"]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(img.width, x + w), min(img.height, y + h)
    if x1 <= x0 or y1 <= y0:
        return np.array([1.0], dtype=np.float32)
    arr = np.asarray(img.crop((x0, y0, x1, y1)).convert("RGB"), dtype=np.float32) / 255.0
    lin = np.where(arr <= 0.04045, arr / 12.92, ((arr + 0.055) / 1.055) ** 2.4)
    lum = 0.2126 * lin[..., 0] + 0.7152 * lin[..., 1] + 0.0722 * lin[..., 2]
    step = max(1, int(step))
    sampled = lum[::step, ::step]
    return sampled.reshape(-1) if sampled.size else lum.reshape(-1)


def worst_contrast(img: Image.Image, rect: Dict[str, int], fill: Sequence[int]) -> float:
    """Lowest contrast between the ink colour and any sampled backdrop cell.

    Local worst case, not an average: an average lets one bright patch behind a
    headline pass while the headline itself is unreadable.
    """
    cells = _rect_luminance_grid(img, rect)
    ink_lum = luminance(fill)
    light_ink = ink_lum > 0.35
    ratios = [(max(ink_lum, c) + 0.05) / (min(ink_lum, c) + 0.05) for c in cells]
    if not ratios:
        return 21.0
    if light_ink:
        return round(float(min(ratios)), 2)
    # dark ink on a dark cell is fine; the failure mode is a bright cell
    return round(float(min(ratios)), 2)


def band_variance(img: Image.Image, rect: Dict[str, int]) -> float:
    """How busy the backdrop is, 0..1 (standard deviation of luminance).

    Contrast alone does not make type readable: 5:1 against a photo of printed
    packaging still collides with the printing. A flat backdrop scores near 0.
    """
    cells = _rect_luminance_grid(img, rect, step=8)
    if cells.size < 4:
        return 0.0
    return round(float(cells.std()), 4)


# ── scrim ───────────────────────────────────────────────────────────────────

def _ramp_mask(size: Tuple[int, int], *, side: str, band: Dict[str, int],
               feather: int, strength: float) -> Image.Image:
    w, h = size
    strength = max(0.0, min(1.0, float(strength)))
    if strength <= 0:
        return Image.new("L", size, 0)
    ys = np.arange(h, dtype=np.float32)[:, None]
    xs = np.arange(w, dtype=np.float32)[None, :]
    feather = max(1, int(feather))
    if side == "left":
        edge = float(band["x"] + band["w"])
        alpha = np.clip((edge + feather - xs) / feather, 0.0, 1.0)
    elif side == "right":
        edge = float(band["x"])
        alpha = np.clip((xs - edge + feather) / feather, 0.0, 1.0)
    else:  # vertical, bottom-up (premium full-bleed modules)
        edge = float(band["y"])
        alpha = np.clip((ys - edge + feather) / feather, 0.0, 1.0)
    alpha = np.broadcast_to(alpha, (h, w)).astype(np.float32) * strength
    return Image.fromarray((alpha * 255.0).astype(np.uint8), "L")


def _scrim_colour(brand: Dict[str, Any], ink: Sequence[int]) -> Tuple[int, int, int]:
    """A scrim must push the backdrop AWAY from the ink, never toward it.

    Pick whichever brand colour stands off the type more: a light veil for dark
    type, a dark veil for light type. Using one hard-coded "darken it" scrim is
    the classic way to make light labels unreadable.
    """
    field = tuple(brand["field"])
    ink_c = tuple(brand["ink"])
    return field if contrast_ratio(ink, field) >= contrast_ratio(ink, ink_c) else ink_c  # type: ignore[return-value]


def _with_scrim(base: Image.Image, brand: Dict[str, Any], *, side: str,
                band: Dict[str, int], strength: float,
                ink: Sequence[int]) -> Image.Image:
    if strength <= 0:
        return base
    out = base.copy()
    mask = _ramp_mask(base.size, side=side, band=band,
                      feather=int(max(24, band["w"] * 0.5)), strength=strength)
    out.paste(Image.new("RGB", base.size, _scrim_colour(brand, ink)), (0, 0), mask)
    return out


def _settle_copy_background(base: Image.Image, brand: Dict[str, Any], *, side: str,
                            band: Dict[str, int], ink, target: float) -> Tuple[Image.Image, str, float]:
    """Strengthen a scrim until the measured contrast passes, else go opaque.

    Returns (background, mode, achieved_contrast). `mode` is one of
    ``none``, ``scrim`` or ``field`` and is recorded in the QA payload.
    """
    if worst_contrast(base, band, ink) >= target:
        return base, "none", worst_contrast(base, band, ink)
    best = base
    best_contrast = worst_contrast(base, band, ink)
    for strength in SCRIM_STEPS[1:]:
        candidate = _with_scrim(base, brand, side=side, band=band, strength=strength, ink=ink)
        got = worst_contrast(candidate, band, ink)
        if got > best_contrast:
            best, best_contrast = candidate, got
        if got >= target:
            return candidate, "scrim", got
    # No scrim can rescue it: the copy gets its own opaque plate.
    opaque = base.copy()
    d = ImageDraw.Draw(opaque)
    d.rectangle([band["x"], band["y"], band["x"] + band["w"], band["y"] + band["h"]],
                fill=brand["field"])
    got = worst_contrast(opaque, band, ink)
    return opaque, "field", got


def _legible_text_colour(colour: Sequence[int], bg: Image.Image, rect: Dict[str, int],
                         ink: Sequence[int], *, target: float = CONTRAST_BODY
                         ) -> Tuple[Tuple[int, int, int], bool]:
    """A brand accent used for TYPE must be readable, or be darkened toward ink.

    The accent still owns rules, icons and keylines - only text uses the adjusted
    value, so the brand reads the same while the small caps stay legible.
    """
    base = _rgb(colour, (0, 0, 0))
    if worst_contrast(bg, rect, base) >= target:
        return base, False
    for step in range(1, 8):
        t = step * 0.12
        trial = tuple(int(round(base[i] * (1 - t) + list(ink)[i] * t)) for i in range(3))
        if worst_contrast(bg, rect, trial) >= target:
            return trial, True  # type: ignore[return-value]
    return _rgb(ink, (0, 0, 0)), True


def _legible_against(colour: Sequence[int], bg: Sequence[int], ink: Sequence[int],
                     *, target: float = CONTRAST_BODY) -> Tuple[Tuple[int, int, int], bool]:
    """Darken a brand colour toward ink until it reads on a known flat fill."""
    base = _rgb(colour, (0, 0, 0))
    bg_c = tuple(bg)  # type: ignore[assignment]
    if contrast_ratio(base, bg_c) >= target:
        return base, False
    for step in range(1, 9):
        t = step * 0.12
        trial = tuple(int(round(base[i] * (1 - t) + list(ink)[i] * t)) for i in range(3))
        if contrast_ratio(trial, bg_c) >= target:
            return trial, True  # type: ignore[return-value]
    return _rgb(ink, (0, 0, 0)), True


# ── per-kind renderers ──────────────────────────────────────────────────────

def _copy_texts(copy: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("headline", "sub", "kicker", "cta"):
        val = copy.get(key)
        if isinstance(val, str) and val.strip():
            out.append(val)
    for key in ("bullets", "tiles"):
        for item in copy.get(key) or []:
            if isinstance(item, str):
                out.append(item)
    for row in copy.get("rows") or []:
        if isinstance(row, dict):
            out.append(str(row.get("label") or ""))
            for val in row.get("values") or []:
                out.append(str(val))
    for col in copy.get("columns") or []:
        out.append(str(col))
    return [t for t in out if t.strip()]


def _screen_copy(copy: Dict[str, Any]) -> None:
    if aplus_spec is None:  # pragma: no cover
        return
    hits: List[Dict[str, str]] = []
    for text in _copy_texts(copy):
        hits.extend(aplus_spec.screen_copy(text))
    if hits:
        seen = {h["match"].lower() for h in hits}
        raise AplusNotPerfect(
            [f"prohibited A+ copy: {m}" for m in sorted(seen)],
            detail=json.dumps(hits[:8], ensure_ascii=False))


def _block_record(name: str, drawn: Dict[str, Any], container: Dict[str, int],
                  contrast: float) -> Dict[str, Any]:
    return {
        "id": name,
        "text": " / ".join(drawn.get("lines") or []),
        "size": int(drawn.get("size") or 0),
        "bbox": drawn.get("bbox"),
        "container": {k: int(container[k]) for k in ("x", "y", "w", "h")},
        "contrast": round(float(contrast), 2),
        "fits": bool(drawn.get("fits")),
    }


def _render_band(kind: str, plan: Dict[str, Any], copy: Dict[str, Any],
                 brand: Dict[str, Any], image: Optional[Any], logo: Optional[Any],
                 copy_side: str, copy_style: str = "panel") -> Dict[str, Any]:
    w, h = geo.CANVAS[kind]
    band = plan["copy"]
    base = _field_canvas(w, h, brand)
    scale = 1.0
    if image is not None:
        scale = _paste_cover(base, _as_image(image), plan["image"])
    ink = brand["ink"]

    if copy_style == "overlay":
        base, mode, achieved = _settle_copy_background(
            base, brand, side=copy_side, band=band, ink=ink, target=OVERLAY_MIN_CONTRAST)
    else:
        # A reserved panel: the copy owns its column, the photograph owns the
        # rest. Type never lands on whatever printing the plate happens to carry,
        # which is the difference between "contrast passed" and "reads cleanly".
        d0 = ImageDraw.Draw(base)
        d0.rectangle([band["x"], band["y"], band["x"] + band["w"], band["y"] + band["h"]],
                     fill=brand["field"])
        edge_x = band["x"] + band["w"] if copy_side == "left" else band["x"]
        d0.line([(edge_x, 0), (edge_x, h)], fill=brand["accent"], width=max(2, h // 200))
        mode, achieved = "panel", contrast_ratio(ink, brand["field"])

    canvas = base.copy()
    d = ImageDraw.Draw(canvas)
    pad = geo.SAFE_INSET
    inner_x = band["x"] + pad
    inner_w = max(1, band["w"] - 2 * pad)
    inner_y = band["y"] + pad
    inner_h = max(1, band["h"] - 2 * pad)
    align = "left" if copy_side == "left" else "right"

    accent_text, accent_adjusted = _legible_text_colour(brand["accent"], base, band, ink)
    notes: List[str] = []
    if accent_adjusted:
        notes.append("accent darkened for legible small caps")
    measure = _shrink(band, 6) if copy_style == "panel" else band

    records: List[Dict[str, Any]] = []
    y = inner_y

    if logo is not None:
        mark = _as_image(logo).convert("RGBA")
        max_w = int(inner_w * 0.56)
        max_h = int(inner_h * 0.22)
        r = min(max_w / max(1, mark.width), max_h / max(1, mark.height))
        size = (max(1, int(mark.width * r)), max(1, int(mark.height * r)))
        mark = mark.resize(size, Image.LANCZOS)
        lx = inner_x if align == "left" else inner_x + inner_w - size[0]
        canvas.paste(mark, (int(lx), int(y)), mark)
        y += size[1] + int(h * 0.035)
        records.append(_block_record("logo", {"bbox": [int(lx), int(y - size[1] - int(h * 0.035)),
                                                      int(lx) + size[0], int(y - int(h * 0.035))],
                                               "lines": ["logo"], "size": 0, "fits": True},
                                     band, 21.0))

    kicker = str(copy.get("kicker") or "").strip()
    if kicker:
        kb = fit_block(d, kicker.upper(), name=brand["body_font"], axes=KICKER_AXES,
                       size=max(MIN_BODY_PX, int(h * 0.032)), min_size=MIN_BODY_PX,
                       max_w=inner_w, max_h=int(h * 0.08), tracking=2.0)
        drawn = draw_block(d, kb, x=inner_x, y=y, w=inner_w, h=kb["line_h"] * len(kb["lines"]),
                           fill=accent_text, align=align, tracking=2.0)
        records.append(_block_record("kicker", drawn, band,
                                     worst_contrast(base, measure, accent_text)))
        y += int(kb["line_h"] * len(kb["lines"])) + int(h * 0.014)

    headline = str(copy.get("headline") or "").strip()
    head_h = int(inner_h * (0.52 if str(copy.get("sub") or "").strip() else 0.72))
    if headline:
        hb = fit_block(d, headline, name=brand["head_font"], axes=brand["head_axes"],
                       size=max(MIN_HEAD_PX, int(h * (0.115 if kind == "header" else 0.10))),
                       min_size=MIN_HEAD_PX, max_w=inner_w, max_h=head_h, line_ratio=1.16)
        drawn = draw_block(d, hb, x=inner_x, y=y, w=inner_w, h=head_h, fill=ink,
                           align=align, valign="top")
        records.append(_block_record("headline", drawn, band, worst_contrast(base, measure, ink)))
        y += int(hb["line_h"] * len(hb["lines"])) + int(h * 0.030)

    sub = str(copy.get("sub") or "").strip()
    if sub:
        rule_y = y
        d.line([(inner_x if align == "left" else inner_x + inner_w - inner_w * 0.30, rule_y),
                (inner_x + inner_w * 0.30 if align == "left" else inner_x + inner_w, rule_y)],
               fill=brand["accent"], width=max(2, h // 260))
        y += int(h * 0.032)
        sb = fit_block(d, sub, name=brand["body_font"], axes=brand["body_axes"],
                       size=max(MIN_BODY_PX, int(h * 0.042)), min_size=MIN_BODY_PX,
                       max_w=inner_w, max_h=max(MIN_BODY_PX, inner_y + inner_h - y),
                       line_ratio=1.34)
        drawn = draw_block(d, sb, x=inner_x, y=y, w=inner_w,
                           h=max(MIN_BODY_PX, inner_y + inner_h - y), fill=ink,
                           align=align, valign="top")
        records.append(_block_record("sub", drawn, band, worst_contrast(base, measure, ink)))

    return {"canvas": canvas, "records": records, "copy_mode": mode,
            "copy_contrast": achieved, "image_scale": scale, "layout": plan,
            "band_variance": band_variance(base, band), "notes": notes}


def _render_premium(kind: str, plan: Dict[str, Any], copy: Dict[str, Any],
                    brand: Dict[str, Any], image: Optional[Any],
                    logo: Optional[Any], copy_style: str = "panel") -> Dict[str, Any]:
    w, h = geo.CANVAS[kind]
    safe = plan["safe"]
    band = {"x": safe["x"], "y": safe["y"] + int(safe["h"] * 0.46),
            "w": safe["w"], "h": int(safe["h"] * 0.54)}
    base = _field_canvas(w, h, brand)
    scale = 1.0
    if image is not None:
        scale = _paste_cover(base, _as_image(image), plan["image"])
    ink = brand["ink"]
    if copy_style == "overlay":
        base, mode, achieved = _settle_copy_background(
            base, brand, side="bottom", band=band, ink=ink, target=OVERLAY_MIN_CONTRAST)
    else:
        d0 = ImageDraw.Draw(base)
        d0.rectangle([band["x"], band["y"], band["x"] + band["w"],
                      band["y"] + band["h"]], fill=brand["field"])
        d0.line([(band["x"], band["y"]), (band["x"] + band["w"], band["y"])],
                fill=brand["accent"], width=max(2, h // 220))
        mode, achieved = "panel", contrast_ratio(ink, brand["field"])

    measure = _shrink(band, 6) if copy_style == "panel" else band
    canvas = base.copy()
    d = ImageDraw.Draw(canvas)
    y = band["y"]
    records: List[Dict[str, Any]] = []
    inner_w = band["w"]
    headline = str(copy.get("headline") or "").strip()
    if headline:
        hb = fit_block(d, headline, name=brand["head_font"], axes=brand["head_axes"],
                       size=max(MIN_HEAD_PX, int(h * 0.10)), min_size=MIN_HEAD_PX,
                       max_w=inner_w, max_h=int(band["h"] * 0.55), line_ratio=1.16)
        drawn = draw_block(d, hb, x=band["x"], y=y, w=inner_w, h=int(band["h"] * 0.55),
                           fill=ink, align="center", valign="top")
        records.append(_block_record("headline", drawn, band, worst_contrast(base, measure, ink)))
        y += int(hb["line_h"] * len(hb["lines"])) + int(h * 0.02)
    sub = str(copy.get("sub") or "").strip()
    if sub:
        sb = fit_block(d, sub, name=brand["body_font"], axes=brand["body_axes"],
                       size=max(MIN_BODY_PX, int(h * 0.038)), min_size=MIN_BODY_PX,
                       max_w=inner_w, max_h=max(MIN_BODY_PX, band["y"] + band["h"] - y),
                       line_ratio=1.34)
        drawn = draw_block(d, sb, x=band["x"], y=y, w=inner_w,
                           h=max(MIN_BODY_PX, band["y"] + band["h"] - y),
                           fill=ink, align="center", valign="top")
        records.append(_block_record("sub", drawn, band, worst_contrast(base, measure, ink)))
    if logo is not None:
        mark = _as_image(logo).convert("RGBA")
        max_w = int(inner_w * 0.22)
        r = min(max_w / max(1, mark.width), (band["h"] * 0.18) / max(1, mark.height))
        if r > 0:
            size = (max(1, int(mark.width * r)), max(1, int(mark.height * r)))
            mark = mark.resize(size, Image.LANCZOS)
            canvas.paste(mark, (band["x"], band["y"] - size[1] - int(h * 0.02)), mark)
    return {"canvas": canvas, "records": records, "copy_mode": mode,
            "copy_contrast": achieved, "image_scale": scale, "layout": plan,
            "band_variance": band_variance(base, band), "notes": []}


def _render_logo(plan: Dict[str, Any], copy: Dict[str, Any], brand: Dict[str, Any],
                 logo: Optional[Any]) -> Dict[str, Any]:
    w, h = geo.CANVAS["logo"]
    canvas = _field_canvas(w, h, brand)
    safe = plan["safe"]
    records: List[Dict[str, Any]] = []
    if logo is not None:
        mark = _as_image(logo).convert("RGBA")
        r = min(safe["w"] / max(1, mark.width), safe["h"] / max(1, mark.height))
        size = (max(1, int(mark.width * r)), max(1, int(mark.height * r)))
        mark = mark.resize(size, Image.LANCZOS)
        pos = (safe["x"] + (safe["w"] - size[0]) // 2, safe["y"] + (safe["h"] - size[1]) // 2)
        canvas.paste(mark, pos, mark)
        records.append({"id": "logo", "text": "logo", "size": 0,
                        "bbox": [pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]],
                        "container": safe, "contrast": 21.0, "fits": True})
    else:
        d = ImageDraw.Draw(canvas)
        word = str(copy.get("headline") or copy.get("brand") or "").strip()
        if not word:
            raise AplusNotPerfect(["logo module needs a logo image or a brand name"])
        fb = fit_block(d, word, name=brand["head_font"], axes=brand["head_axes"],
                       size=int(h * 0.42), min_size=MIN_HEAD_PX,
                       max_w=safe["w"], max_h=safe["h"], line_ratio=1.1)
        drawn = draw_block(d, fb, x=safe["x"], y=safe["y"], w=safe["w"], h=safe["h"],
                           fill=brand["ink"], align="center", valign="middle")
        records.append(_block_record("wordmark", drawn, safe,
                                     contrast_ratio(brand["ink"], brand["field"])))
    return {"canvas": canvas, "records": records, "copy_mode": "field",
            "copy_contrast": 21.0, "image_scale": 1.0, "layout": plan}


def _render_tiles(kind: str, plan: Dict[str, Any], copy: Dict[str, Any],
                  brand: Dict[str, Any], tiles: Optional[Sequence[Any]],
                  copy_style: str = "panel") -> Dict[str, Any]:
    w, h = geo.CANVAS[kind]
    canvas = _field_canvas(w, h, brand)
    rects = plan["tiles"]
    if not rects:
        raise AplusNotPerfect([f"{kind} has no tiles in the layout"])
    if not tiles:
        raise AplusNotPerfect([f"{kind} needs tile imagery"])

    captions = [str(c).strip() for c in (copy.get("tiles") or copy.get("bullets") or [])]
    records: List[Dict[str, Any]] = []
    scales: List[float] = []
    reused = len(tiles) == 1 and len(rects) > 1

    for i, rect in enumerate(rects):
        src = tiles[i] if i < len(tiles) else tiles[-1]
        scales.append(_paste_cover(canvas, _as_image(src), rect))
        caption = captions[i] if i < len(captions) else ""
        if not caption:
            continue
        band_h = max(int(rect["h"] * 0.30), MIN_BODY_PX * 2)
        band = {"x": rect["x"], "y": rect["y"] + rect["h"] - band_h,
                "w": rect["w"], "h": band_h}
        if copy_style == "overlay":
            base_bg = canvas.copy()
            settled, mode, achieved = _settle_copy_background(
                base_bg, brand, side="bottom", band=band, ink=brand["ink"],
                target=OVERLAY_MIN_CONTRAST)
            canvas.paste(settled, (0, 0))
        else:
            # A caption strip is a design element, not a wash over the photograph.
            d0 = ImageDraw.Draw(canvas)
            d0.rectangle([band["x"], band["y"], band["x"] + band["w"],
                          band["y"] + band["h"]], fill=brand["field"])
            d0.line([(band["x"], band["y"] - 3), (band["x"] + band["w"], band["y"] - 3)],
                    fill=brand["accent"], width=3)
            mode, achieved = "panel", contrast_ratio(brand["ink"], brand["field"])
        bg = canvas.copy()      # read contrast off the backdrop, never off the type
        d = ImageDraw.Draw(canvas)
        cb = fit_block(d, caption, name=brand["body_font"], axes=brand["body_axes"],
                       size=max(MIN_BODY_PX, int(rect["w"] * 0.075)),
                       min_size=MIN_BODY_PX,
                       max_w=rect["w"] - 2 * 10, max_h=band_h - 10, line_ratio=1.26)
        drawn = draw_block(d, cb, x=rect["x"] + 10, y=band["y"] + 4,
                           w=rect["w"] - 20, h=band_h - 8, fill=brand["ink"],
                           align="center", valign="middle")
        rec = _block_record(f"tile{i}", drawn, rect,
                            worst_contrast(bg, _shrink(band, 4), brand["ink"]))
        rec["copy_mode"] = mode
        records.append(rec)

    return {"canvas": canvas, "records": records, "copy_mode": "panel",
            "copy_contrast": min([r["contrast"] for r in records], default=21.0),
            "image_scale": min(scales) if scales else 1.0,
            "image_scale_max": max(scales) if scales else 1.0,
            "tiles_reused": reused, "layout": plan,
            "band_variance": 0.0, "notes": []}


def _render_comparison(plan: Dict[str, Any], copy: Dict[str, Any],
                       brand: Dict[str, Any]) -> Dict[str, Any]:
    w, h = geo.CANVAS["comparison"]
    comp = plan["comparison"]
    canvas = _field_canvas(w, h, brand)
    d = ImageDraw.Draw(canvas)
    ink, accent, field = brand["ink"], brand["accent"], brand["field"]

    head = comp["header"]
    d.rectangle([head["x"], head["y"], head["x"] + head["w"], head["y"] + head["h"]],
                fill=ink)
    records: List[Dict[str, Any]] = []

    columns = [str(c) for c in (copy.get("columns") or [])][:2]
    while len(columns) < 2:
        columns.append("Standard")

    rows = comp["rows"]
    row_h = comp["row_h"]
    label_col = comp["label_col"]
    cols = comp["columns"]

    body_top = head["h"]
    for i in range(rows):
        y0 = body_top + i * row_h
        if i % 2 == 1:
            d.rectangle([0, y0, w - 1, y0 + row_h - 1], fill=ZEBRA_CELL)
        d.line([(0, y0), (w - 1, y0)], fill=(226, 220, 208), width=1)

    # Contrast is measured on the BACKDROP, before any type lands on it.
    # Measuring afterwards would compare the ink with itself and always read 1:1.
    bg = canvas.copy()

    # Header: the title only. Column names belong in the table's first body row,
    # where they sit directly above the values they describe.
    title = str(copy.get("headline") or "Compare the range").strip()
    tb = fit_block(d, title, name=brand["head_font"], axes=brand["head_axes"],
                   size=max(MIN_HEAD_PX, int(head["h"] * 0.50)), min_size=MIN_BODY_PX,
                   max_w=head["w"] - 2 * geo.SAFE_INSET, max_h=head["h"] - 12,
                   line_ratio=1.1)
    drawn = draw_block(d, tb, x=head["x"] + geo.SAFE_INSET, y=head["y"] + 6,
                       w=head["w"] - 2 * geo.SAFE_INSET, h=head["h"] - 12,
                       fill=field, align="left", valign="middle")
    records.append(_block_record("headline", drawn, head, worst_contrast(bg, head, field)))

    # A quiet header cell names the left column without eating a body row.
    label_header = str(copy.get("label_header") or "Feature").strip()
    cell = LABEL_CELL
    d.rectangle([0, body_top, label_col["w"] - 1, body_top + row_h - 1], fill=cell)
    kicker_colour, _ = _legible_against(accent, cell, ink)
    cap_b = fit_block(d, label_header.upper(), name=brand["body_font"], axes=KICKER_AXES,
                      size=max(11, int(row_h * 0.24)), min_size=10,
                      max_w=label_col["w"] - 16, max_h=row_h - 10, tracking=1.4)
    drawn = draw_block(d, cap_b, x=label_col["x"] + 8, y=body_top + 5,
                       w=label_col["w"] - 16, h=row_h - 10, fill=kicker_colour,
                       align="left", valign="middle", tracking=1.4)
    records.append(_block_record("label_header", drawn, label_col,
                                 contrast_ratio(kicker_colour, cell)))

    for ci, col in enumerate(cols):
        cb = fit_block(d, columns[ci], name=brand["body_font"], axes=BODY_AXES,
                       size=max(12, int(row_h * 0.30)), min_size=10,
                       max_w=col["w"] - 20, max_h=row_h - 12, tracking=0.6)
        drawn = draw_block(d, cb, x=col["x"] + 10, y=body_top + 6, w=col["w"] - 20,
                           h=row_h - 12, fill=ink, align="center", valign="middle")
        records.append(_block_record(f"column{ci}", drawn, col,
                                     worst_contrast(bg, col, ink)))

    specs = [r for r in (copy.get("rows") or []) if isinstance(r, dict)]
    for i, rule in enumerate(specs[:rows - 1]):
        y0 = body_top + (i + 1) * row_h
        label = str(rule.get("label") or "").strip()
        if label:
            lb = fit_block(d, label, name=brand["body_font"], axes=BODY_AXES,
                           size=max(MIN_BODY_PX, int(row_h * 0.28)), min_size=12,
                           max_w=label_col["w"] - 24, max_h=row_h - 14, line_ratio=1.24)
            drawn = draw_block(d, lb, x=label_col["x"] + 12, y=y0 + 7,
                               w=label_col["w"] - 24, h=row_h - 14, fill=ink,
                               align="left", valign="middle")
            records.append(_block_record(f"row{i}.label", drawn, label_col,
                                         worst_contrast(bg, label_col, ink)))
        values = list(rule.get("values") or [])[:2]
        for ci, col in enumerate(cols):
            val = str(values[ci] if ci < len(values) else "")
            if not val:
                continue
            if val.lower() in ("yes", "y", "true", "1"):
                _check(d, col, y0, row_h, accent, brand)
                continue
            if val.lower() in ("no", "n", "false", "0"):
                _cross(d, col, y0, row_h, (150, 146, 138), brand)
                continue
            vb = fit_block(d, val, name=brand["body_font"], axes=BODY_AXES,
                           size=max(MIN_BODY_PX, int(row_h * 0.28)), min_size=12,
                           max_w=col["w"] - 24, max_h=row_h - 14, line_ratio=1.24)
            drawn = draw_block(d, vb, x=col["x"] + 12, y=y0 + 7, w=col["w"] - 24,
                               h=row_h - 14, fill=ink, align="center", valign="middle")
            records.append(_block_record(f"row{i}.col{ci}", drawn, col,
                                         worst_contrast(bg, col, ink)))

    d.line([(label_col["w"], body_top), (label_col["w"], h - 1)], fill=accent, width=2)
    for col in cols[1:]:
        d.line([(col["x"], body_top), (col["x"], h - 1)], fill=(226, 220, 208), width=1)

    # The header band's own text lives on ink, so it is judged against that fill.
    return {"canvas": canvas, "records": records, "copy_mode": "field",
            "copy_contrast": min([r["contrast"] for r in records], default=21.0),
            "image_scale": 1.0, "layout": plan, "band_variance": 0.0, "notes": []}


def _check(d: ImageDraw.ImageDraw, col: Dict[str, int], y0: int, row_h: int,
           accent, brand: Dict[str, Any]) -> None:
    cx = col["x"] + col["w"] // 2
    cy = y0 + row_h // 2
    r = max(7, int(row_h * 0.16))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent, width=max(2, r // 4))
    d.line([(cx - r * 0.5, cy), (cx - r * 0.08, cy + r * 0.42), (cx + r * 0.55, cy - r * 0.45)],
           fill=accent, width=max(2, r // 3), joint="curve")


def _cross(d: ImageDraw.ImageDraw, col: Dict[str, int], y0: int, row_h: int,
           colour, brand: Dict[str, Any]) -> None:
    cx = col["x"] + col["w"] // 2
    cy = y0 + row_h // 2
    r = max(6, int(row_h * 0.13))
    d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=colour, width=max(2, r // 3))
    d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=colour, width=max(2, r // 3))


def _render_card(kind: str, plan: Dict[str, Any], copy: Dict[str, Any],
                 brand: Dict[str, Any], image: Optional[Any]) -> Dict[str, Any]:
    """sidebar / sidebar_thumb / single.

    ``sidebar`` (300x400) is tall enough for an image plus a copy block beneath
    it. The two short cards are not: type below a 300x300 or 350x175 image would
    fall under the 14 px floor, so their copy rides a measured scrim across the
    bottom of the image instead of being shrunk into illegibility.
    """
    w, h = geo.CANVAS[kind]
    canvas = _field_canvas(w, h, brand)
    ink = brand["ink"]
    notes: List[str] = []
    records: List[Dict[str, Any]] = []

    headline = str(copy.get("headline") or "").strip()
    sub = str(copy.get("sub") or "").strip()
    overlay = kind in ("sidebar_thumb", "single")

    if overlay:
        scale = _paste_cover(canvas, _as_image(image), plan["image"]) if image is not None else 1.0
        band_h = int(h * (0.42 if kind == "single" else 0.36))
        band = {"x": 0, "y": h - band_h, "w": w, "h": band_h}
        canvas, mode, achieved = _settle_copy_background(
            canvas, brand, side="bottom", band=band, ink=ink, target=OVERLAY_MIN_CONTRAST)
        bg = canvas.copy()      # contrast is read off the backdrop, never off the type
        d = ImageDraw.Draw(canvas)
        pad = max(10, int(w * 0.06))
        inner = {"x": pad, "y": band["y"] + 6, "w": w - 2 * pad, "h": band_h - 12}
        y = inner["y"]
        head_room = int(inner["h"] * (0.58 if sub else 1.0))
        if headline:
            hb = fit_block(d, headline, name=brand["head_font"], axes=brand["head_axes"],
                           size=max(MIN_BODY_PX, int(inner["h"] * 0.40)),
                           min_size=MIN_BODY_PX, max_w=inner["w"], max_h=head_room,
                           line_ratio=1.16)
            drawn = draw_block(d, hb, x=inner["x"], y=y, w=inner["w"], h=head_room,
                               fill=ink, align="center", valign="top")
            records.append(_block_record("headline", drawn, band,
                                         worst_contrast(bg, band, ink)))
            y += int(hb["line_h"] * len(hb["lines"])) + 2
        if sub:
            room = inner["y"] + inner["h"] - y
            if room >= MIN_BODY_PX:
                sb = fit_block(d, sub, name=brand["body_font"], axes=brand["body_axes"],
                               size=max(MIN_BODY_PX, int(inner["h"] * 0.24)),
                               min_size=MIN_BODY_PX, max_w=inner["w"], max_h=room,
                               line_ratio=1.26)
                drawn = draw_block(d, sb, x=inner["x"], y=y, w=inner["w"], h=room,
                                   fill=ink, align="center", valign="top")
                records.append(_block_record("sub", drawn, band,
                                             worst_contrast(bg, band, ink)))
            else:
                notes.append("sub omitted: no room above the 14 px floor")
        if not records and image is None:
            raise AplusNotPerfect([f"{kind} needs an image or copy"])
        return {"canvas": canvas, "records": records, "copy_mode": mode,
                "copy_contrast": achieved, "image_scale": scale, "layout": plan,
                "notes": notes}

    img_h = int(h * 0.56)
    image_rect = {"x": 0, "y": 0, "w": w, "h": img_h}
    scale = _paste_cover(canvas, _as_image(image), image_rect) if image is not None else 1.0
    d = ImageDraw.Draw(canvas)
    pad = max(10, int(w * 0.05))
    copy_rect = {"x": pad, "y": img_h + pad, "w": w - 2 * pad, "h": h - img_h - 2 * pad}
    bg = canvas.copy()          # read contrast off the backdrop, never off the type
    y = copy_rect["y"]
    if headline:
        head_room = int(copy_rect["h"] * (0.58 if sub else 0.95))
        hb = fit_block(d, headline, name=brand["head_font"], axes=brand["head_axes"],
                       size=max(MIN_BODY_PX, int(copy_rect["h"] * 0.40)),
                       min_size=MIN_BODY_PX, max_w=copy_rect["w"],
                       max_h=head_room, line_ratio=1.18)
        drawn = draw_block(d, hb, x=copy_rect["x"], y=y, w=copy_rect["w"],
                           h=head_room, fill=ink, align="center", valign="top")
        records.append(_block_record("headline", drawn, copy_rect,
                                     worst_contrast(bg, copy_rect, ink)))
        y += int(hb["line_h"] * len(hb["lines"])) + 4
    if sub:
        room = copy_rect["y"] + copy_rect["h"] - y
        if room >= MIN_BODY_PX:
            sb = fit_block(d, sub, name=brand["body_font"], axes=brand["body_axes"],
                           size=max(MIN_BODY_PX, int(copy_rect["h"] * 0.22)),
                           min_size=MIN_BODY_PX, max_w=copy_rect["w"], max_h=room,
                           line_ratio=1.28)
            drawn = draw_block(d, sb, x=copy_rect["x"], y=y, w=copy_rect["w"],
                               h=room, fill=ink, align="center", valign="top")
            records.append(_block_record("sub", drawn, copy_rect,
                                         worst_contrast(bg, copy_rect, ink)))
        else:
            notes.append("sub omitted: no room above the 14 px floor")
    if not records and image is None:
        raise AplusNotPerfect([f"{kind} needs an image or copy"])
    return {"canvas": canvas, "records": records, "copy_mode": "field",
            "copy_contrast": min([r["contrast"] for r in records], default=21.0),
            "image_scale": scale, "layout": plan, "notes": notes}


# ── QA ──────────────────────────────────────────────────────────────────────

def _qa(kind: str, canvas: Image.Image, records: Sequence[Dict[str, Any]],
        extra: Dict[str, Any], png: bytes) -> Dict[str, Any]:
    problems: List[str] = []
    warnings: List[str] = []
    expect = geo.CANVAS[kind]
    if canvas.size != expect:
        problems.append(f"canvas {canvas.width}x{canvas.height} is not {expect[0]}x{expect[1]}")

    for rec in records:
        box = rec.get("bbox")
        if not box:
            problems.append(f"{rec['id']}: no ink box")
            continue
        x0, y0, x1, y1 = box
        cont = rec.get("container") or {"x": 0, "y": 0, "w": canvas.width, "h": canvas.height}
        if (x0 < cont["x"] - 1 or y0 < cont["y"] - 1
                or x1 > cont["x"] + cont["w"] + 1 or y1 > cont["y"] + cont["h"] + 1):
            problems.append(f"{rec['id']}: text leaves its container")
        if not rec.get("fits", True):
            problems.append(f"{rec['id']}: copy does not fit at the minimum size")
        if rec["size"] and rec["size"] < MIN_BODY_PX:
            problems.append(f"{rec['id']}: {rec['size']}px is below the {MIN_BODY_PX}px floor")
        need = CONTRAST_LARGE if rec["size"] >= LARGE_TEXT_PX else CONTRAST_BODY
        if rec["size"] == 0:
            need = 1.0                      # a pasted mark, not type
        if rec["contrast"] < need:
            problems.append(f"{rec['id']}: contrast {rec['contrast']}:1 below {need}:1")

    scale = float(extra.get("image_scale") or 1.0)
    if scale > MAX_UPSCALE:
        problems.append(f"plate is blown up {scale:.1f}x - too small to place sharply")
    elif scale > 1.02:
        warnings.append(f"plate blown up {scale:.2f}x")
    if extra.get("tiles_reused"):
        warnings.append("one image reused across the tile row")
    for note in extra.get("notes") or []:
        warnings.append(str(note))

    variance = extra.get("band_variance")
    if extra.get("copy_style") == "overlay" and variance is not None:
        if float(variance) > OVERLAY_MAX_VARIANCE:
            problems.append(
                f"type sits on a busy backdrop (variance {float(variance):.3f} > "
                f"{OVERLAY_MAX_VARIANCE}) - use copy_style='panel'")

    if len(png) > MAX_BYTES:
        problems.append(f"{len(png) / 1_048_576:.2f} MB exceeds the 2 MB ceiling")

    return {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "canvas": [canvas.width, canvas.height],
        "bytes": len(png),
        "copy_mode": extra.get("copy_mode"),
        "image_scale": round(scale, 4),
        "texts": len(records),
        "min_contrast": min([r["contrast"] for r in records], default=None),
        "min_text_px": min([r["size"] for r in records if r["size"]] or [0]) or None,
    }


def _encode(canvas: Image.Image) -> Tuple[bytes, str]:
    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    data = buf.getvalue()
    if len(data) <= MAX_BYTES:
        return data, "PNG"
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="JPEG", quality=88, optimize=True)
    return buf.getvalue(), "JPEG"


# ── public API ──────────────────────────────────────────────────────────────

def render_module(kind: str, *, copy: Optional[Dict[str, Any]] = None,
                  brand: Optional[Dict[str, Any]] = None,
                  image: Optional[Any] = None, tiles: Optional[Sequence[Any]] = None,
                  logo: Optional[Any] = None, copy_side: str = "left",
                  copy_style: str = "panel") -> Dict[str, Any]:
    """Render one A+ module. Raises KeyError on an unknown kind.

    ``copy_style``: ``panel`` (default) reserves a clean brand-field column for the
    type, so nothing lands on the photograph's own printing. ``overlay`` sets the
    type on the image behind a measured scrim and is held to a stricter contrast
    and a backdrop-variance ceiling, because 4.5:1 over printed packaging can
    still be unreadable.

    Returns ``{png, format, size, kind, qa, layout, copy_mode}``; the caller
    decides whether to ship it or hand ``qa["problems"]`` back to the operator.
    """
    if kind not in geo.CANVAS:
        raise KeyError(f"unknown A+ module kind: {kind}")
    if copy_style not in COPY_STYLES:
        raise ValueError(f"copy_style must be one of {COPY_STYLES}")
    copy = dict(copy or {})
    brand_v = _brand(brand)
    _screen_copy(copy)
    plan = geo.pixel_plan(kind, copy_side=copy_side)

    if kind in BAND_KINDS:
        out = _render_band(kind, plan, copy, brand_v, image, logo, copy_side, copy_style)
    elif kind in PREMIUM_KINDS:
        out = _render_premium(kind, plan, copy, brand_v, image, logo, copy_style)
    elif kind in TILE_KINDS:
        out = _render_tiles(kind, plan, copy, brand_v, tiles, copy_style)
    elif kind == "comparison":
        out = _render_comparison(plan, copy, brand_v)
    elif kind == "logo":
        out = _render_logo(plan, copy, brand_v, logo)
    else:
        out = _render_card(kind, plan, copy, brand_v, image)

    png, fmt = _encode(out["canvas"])
    out["copy_style"] = copy_style
    qa = _qa(kind, out["canvas"], out["records"], out, png)
    return {"png": png, "format": fmt, "size": [out["canvas"].width, out["canvas"].height],
            "kind": kind, "qa": qa, "layout": plan,
            "copy_mode": out["copy_mode"], "texts": out["records"]}


def assert_perfect(rendered: Dict[str, Any]) -> Dict[str, Any]:
    """Refuse a module that is not upload-ready. Returns it unchanged when it is."""
    qa = rendered.get("qa") or {}
    if not qa.get("ok"):
        raise AplusNotPerfect(qa.get("problems") or ["qa missing"], detail=str(rendered.get("kind")))
    return rendered


def render_page(modules: Sequence[Any], *, brand: Optional[Dict[str, Any]] = None,
                image: Optional[Any] = None, tiles: Optional[Sequence[Any]] = None,
                logo: Optional[Any] = None, out_dir: Optional[Path | str] = None,
                preview: bool = True, contact_gap: int = 24,
                copy_style: str = "panel") -> Dict[str, Any]:
    """Render a whole A+ story in order, optionally writing the files.

    ``modules`` items are either a module id string or ``{kind, copy}``. The
    same plate and logo are reused where a module does not override them, which
    is how a real page is built (one product, one mark, many crops).
    """
    out_path = Path(out_dir) if out_dir else None
    if out_path:
        out_path.mkdir(parents=True, exist_ok=True)

    rendered: List[Dict[str, Any]] = []
    for i, item in enumerate(modules, start=1):
        if isinstance(item, str):
            spec = {"kind": item}
        else:
            spec = dict(item or {})
        kind = str(spec.get("kind") or spec.get("module") or "").strip()
        if not kind:
            raise AplusNotPerfect([f"module {i} has no kind"])
        res = render_module(
            kind, copy=spec.get("copy") or {},
            brand=spec.get("brand") or brand,
            image=spec.get("image", image),
            tiles=spec.get("tiles", tiles),
            logo=spec.get("logo", logo),
            copy_side=str(spec.get("copy_side") or "left"),
            copy_style=str(spec.get("copy_style") or copy_style))
        entry = {"index": i, "kind": kind, "format": res["format"],
                 "size": res["size"], "bytes": len(res["png"]),
                 "qa": res["qa"], "copy_mode": res["copy_mode"],
                 # The strings the renderer actually drew, so a verifier can read
                 # them back out of the pixels instead of trusting the request.
                 "copy_texts": [str(r.get("text")) for r in res.get("texts") or []
                                if r.get("text") and float(r.get("size") or 0) > 0
                                and str(r.get("text")).strip().lower() != "logo"]}
        if out_path:
            ext = "png" if res["format"] == "PNG" else "jpg"
            p = out_path / f"aplus_{i:02d}_{kind}.{ext}"
            p.write_bytes(res["png"])
            entry["path"] = str(p)
        rendered.append({**entry, "png": res["png"], "canvas": None})

    preview_path = None
    if preview and out_path and rendered:
        preview_path = str(_preview(rendered, brand or {}, out_path, gap=contact_gap))

    problems = [f"{r['kind']}: {p}" for r in rendered for p in r["qa"]["problems"]]
    manifest = {
        "ok": not problems,
        "problems": problems,
        "modules": [{k: v for k, v in r.items() if k not in ("png",)} for r in rendered],
        "preview": preview_path,
        "bytes_total": sum(r["bytes"] for r in rendered),
    }
    if out_path:
        (out_path / "aplus_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _preview(rendered: Sequence[Dict[str, Any]], brand: Dict[str, Any], out_path: Path,
             *, gap: int = 24) -> Path:
    width = max(geo.CANVAS[r["kind"]][0] for r in rendered)
    height = sum(geo.CANVAS[r["kind"]][1] for r in rendered) + gap * (len(rendered) + 1)
    b = _brand(brand)
    sheet = Image.new("RGB", (width, height), b["field"])
    y = gap
    for r in rendered:
        img = Image.open(io.BytesIO(r["png"])).convert("RGB")
        sheet.paste(img, ((width - img.width) // 2, y))
        y += img.height + gap
    p = out_path / "aplus_preview.png"
    sheet.save(p, format="PNG", optimize=True)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Render one A+ module to a PNG.")
    ap.add_argument("--kind", required=True, choices=sorted(geo.CANVAS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--headline", default="")
    ap.add_argument("--sub", default="")
    ap.add_argument("--kicker", default="")
    ap.add_argument("--image")
    ap.add_argument("--logo")
    ap.add_argument("--copy-side", default="left", choices=["left", "right"])
    args = ap.parse_args(argv)

    res = render_module(args.kind,
                        copy={"headline": args.headline, "sub": args.sub, "kicker": args.kicker},
                        image=args.image, logo=args.logo, copy_side=args.copy_side)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(res["png"])
    print(json.dumps({"out": str(out), "size": res["size"], "qa": res["qa"]}, indent=2))
    return 0 if res["qa"]["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


__all__ = ["AplusNotPerfect", "render_module", "render_page", "assert_perfect",
           "contrast_ratio", "luminance", "cover", "DEFAULT_BRAND", "MAX_BYTES"]
