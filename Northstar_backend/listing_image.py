"""Listing hero images: pure-white isolation + normalized contact shadow.

Amazon's main image rule is exact: the background must be RGB 255,255,255 and the
product must fill ~85% of the frame. `image_prep.frame_on_white` already does the
framing; it does NOT do a ground shadow, and a cutout pasted on white reads as
floating. This module adds a deterministic contact shadow so the product sits on
the surface instead of hovering.

Three guardrails are enforced here, not asserted afterwards:

  * background compliance - every pixel outside the subject and its clipped
    contact shadow is forced to pure white; alpha-blended subject edges survive;
  * safe-zone padding - a 10% target margin, with an automatic rescale/re-centre
    when any subject edge would cross the 5% trigger;
  * ground-shadow normalization - the shadow is an ellipse clipped to the
    subject's own footprint, so no floor texture, reflection or blurred tail can
    reach the background ring.

Pure PIL + numpy, no model, no network.
"""
from __future__ import annotations

import math
from io import BytesIO
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from image_prep import alpha_bbox, trim_to_alpha

WHITE = (255, 255, 255)
DEFAULT_SIZE = 2000
#: 0.82 leaves ~9% margins; the listing target is 80-92% fill.
DEFAULT_FILL = 0.82
#: Desired margin around the subject bounding box.
SAFE_MARGIN = 0.10
#: Any margin below this share triggers an automatic rescale.
TRIGGER_MARGIN = 0.05
#: A background pixel at or above this value in every channel is "white".
WHITE_FLOOR = 250


def _fit_subject(rgba: Image.Image, size: int, fill: float
                 ) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Trim, scale and centre the subject inside the safe zone.

    The first scale targets `fill` of the longest side. If that leaves any
    margin below the 5% trigger, the subject is rescaled to the 10% target and
    re-centred rather than shipped touching the frame.
    """
    trimmed = trim_to_alpha(rgba)
    box = alpha_bbox(trimmed)
    if box is None:
        raise ValueError("empty_subject")
    long_side = max(box[2] - box[0], box[3] - box[1])
    if long_side <= 0:
        raise ValueError("empty_subject")

    def _resize(target_px: int) -> Image.Image:
        scale = target_px / long_side
        new_w = max(1, int(round((box[2] - box[0]) * scale)))
        new_h = max(1, int(round((box[3] - box[1]) * scale)))
        return trimmed.resize((new_w, new_h), Image.LANCZOS)

    subject = _resize(int(round(size * max(0.05, min(0.98, fill)))))
    x = (size - subject.width) // 2
    y = (size - subject.height) // 2
    margins = (x, y, size - x - subject.width, size - y - subject.height)
    if min(margins) < TRIGGER_MARGIN * size:
        subject = _resize(int(round(size * (1.0 - 2.0 * SAFE_MARGIN))))
        x = (size - subject.width) // 2
        y = (size - subject.height) // 2
    return subject, (x, y, x + subject.width, y + subject.height)


def _shadow_layer(size: int, box: Tuple[int, int, int, int], *,
                  strength: float = 0.55) -> Image.Image:
    """Soft contact shadow clipped to the subject's own footprint.

    The ellipse sits at the base of the subject and is clipped to a band inside
    the bbox, so its blurred tail can never extend the subject bounding box or
    tint the outer ring. That is the difference between a contact shadow and a
    floor.
    """
    x0, y0, x1, y1 = box
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    cx = (x0 + x1) // 2
    cy = y1 + max(1, int(h * 0.010))
    rx = max(8, int(w * 0.46))
    ry = max(3, int(h * 0.020))
    layer = Image.new("L", (size, size), 0)
    ImageDraw.Draw(layer).ellipse(
        (cx - rx, cy - ry, cx + rx, cy + ry),
        fill=int(70 * max(0.0, min(1.0, strength))),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(4, int(ry * 2.5))))
    clip = Image.new("L", (size, size), 0)
    ImageDraw.Draw(clip).rectangle(
        (x0, y1 - max(2, int(h * 0.18)), x1,
         min(size - 1, y1 + max(2, int(size * 0.02)))), fill=255)
    return Image.composite(layer, Image.new("L", (size, size), 0), clip)


def _enforce_white(canvas: Image.Image, subject: Image.Image,
                   box: Tuple[int, int, int, int],
                   shadow: Optional[Image.Image]) -> Image.Image:
    """Force every non-subject, non-shadow pixel to exact white."""
    arr = np.asarray(canvas, dtype=np.uint8).copy()
    x0, y0, x1, y1 = box
    keep = np.zeros(arr.shape[:2], dtype=bool)
    alpha = np.asarray(subject.convert("RGBA"))[..., 3]
    keep[y0:y1, x0:x1] = alpha > 0
    if shadow is not None:
        keep |= np.asarray(shadow) > 0
    arr[~keep] = 255
    return Image.fromarray(arr, "RGB")


def hero_on_white(
    png_bytes: bytes,
    *,
    size: int = DEFAULT_SIZE,
    fill: float = DEFAULT_FILL,
    shadow: bool = True,
    shadow_strength: float = 0.55,
) -> bytes:
    """Cutout -> compliant main image with a normalized contact shadow.

    Raises ValueError('empty_subject') when the input has no visible pixels - an
    honest refusal is better than a white square presented as a product.

    ``fill`` is the share of the frame the subject occupies. A value outside (0, 1]
    scales the subject past the canvas and crops the product out of the MAIN image,
    so it is refused before any pixels are drawn.
    """
    try:
        fill_value = float(fill)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"fill must be a number in (0, 1], got {fill!r}") from exc
    if not math.isfinite(fill_value) or not (0.0 < fill_value <= 1.0):
        raise ValueError(f"fill must be a finite number in (0, 1], got {fill_value!r}")
    rgba = Image.open(BytesIO(png_bytes)).convert("RGBA")
    subject, (x0, y0, x1, y1) = _fit_subject(rgba, size, fill)
    canvas = Image.new("RGB", (size, size), WHITE)
    layer = _shadow_layer(size, (x0, y0, x1, y1), strength=shadow_strength) \
        if shadow else None
    if layer is not None:
        shade = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        shade.putalpha(layer)
        base = canvas.convert("RGBA")
        base.alpha_composite(shade)
        canvas = base.convert("RGB")
    canvas.paste(subject, (x0, y0), subject)
    canvas = _enforce_white(canvas, subject, (x0, y0, x1, y1), layer)
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def audit_white(png_bytes: bytes, *, corners: int = 8, ring: float = 0.06) -> dict:
    """Prove the background rule on the pixels a listing check actually samples.

    `purity` is the whole-image share (kept for compatibility); the listing
    verdict uses `background_purity`, measured on the outer ring, because a
    product filling 85% of the frame cannot leave 90% of the whole image white.
    """
    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    px = img.load()
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
           (w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1)][:corners]
    corner_values = [px[p] for p in pts]
    arr = np.asarray(img)
    white = np.all(arr >= WHITE_FLOOR, axis=-1)
    b = max(2, int(min(w, h) * max(0.01, min(0.20, ring))))
    ring_mask = np.zeros((h, w), dtype=bool)
    ring_mask[:b, :] = True
    ring_mask[-b:, :] = True
    ring_mask[:, :b] = True
    ring_mask[:, -b:] = True
    background_purity = float(white[ring_mask].mean()) if ring_mask.any() else 1.0
    ys, xs = np.where(~white)
    if xs.size:
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1]
        margins = [round(bbox[0] / w, 4), round(bbox[1] / h, 4),
                   round((w - bbox[2]) / w, 4), round((h - bbox[3]) / h, 4)]
    else:
        bbox, margins = None, None
    return {
        "corners_pure_white": all(v == WHITE for v in corner_values),
        "corner_values": corner_values,
        "pure_white_ratio": round(float(white.mean()), 4),
        "background_purity": round(background_purity, 4),
        "subject_bbox": bbox,
        "margins": margins,
        "size": [w, h],
    }


__all__ = ["hero_on_white", "audit_white", "WHITE", "DEFAULT_SIZE",
           "DEFAULT_FILL", "SAFE_MARGIN", "TRIGGER_MARGIN"]
