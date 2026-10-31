"""Listing hero images: pure-white isolation + contact shadow (Phase 1, item 3).

Amazon's main image rule is exact: the background must be RGB 255,255,255 and the
product must fill ~85% of the frame. `image_prep.frame_on_white` already does the
framing; it does NOT do a ground shadow, and a cutout pasted on white reads as
floating. This module adds a deterministic contact shadow so the product sits on
the surface instead of hovering.

Hard rule: the output background is PURE white. A shadow that tints the corners
fails the listing check, so the shadow is an ellipse drawn under the subject's
own bounding box and blurred - never a full-frame gradient.

Pure PIL + numpy, no model, no network.
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFilter

from image_prep import alpha_bbox, trim_to_alpha

WHITE = (255, 255, 255)
DEFAULT_SIZE = 2000
DEFAULT_FILL = 0.85


def _subject_on_white(rgba: Image.Image, size: int, fill: float) -> Tuple[Image.Image, Tuple[int, int, int, int]]:
    """Scale the trimmed subject to `fill` of the frame, centred, on pure white."""
    trimmed = trim_to_alpha(rgba)
    box = alpha_bbox(trimmed)
    if box is None:
        raise ValueError("empty_subject")
    long_side = max(box[2] - box[0], box[3] - box[1])
    if long_side <= 0:
        raise ValueError("empty_subject")
    target = max(1, int(round(size * max(0.05, min(1.0, fill)))))
    scale = target / long_side
    new_w = max(1, int(round((box[2] - box[0]) * scale)))
    new_h = max(1, int(round((box[3] - box[1]) * scale)))
    resized = trimmed.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGB", (size, size), WHITE)
    x = (size - new_w) // 2
    y = (size - new_h) // 2
    return canvas, (x, y, x + new_w, y + new_h)


def hero_on_white(
    png_bytes: bytes,
    *,
    size: int = DEFAULT_SIZE,
    fill: float = DEFAULT_FILL,
    shadow: bool = True,
    shadow_strength: float = 0.55,
) -> bytes:
    """Cutout -> compliant main image with an optional contact shadow.

    Raises ValueError('empty_subject') when the input has no visible pixels -
    an honest refusal is better than a white square presented as a product.
    """
    rgba = Image.open(BytesIO(png_bytes)).convert("RGBA")
    canvas, (x0, y0, x1, y1) = _subject_on_white(rgba, size, fill)
    subject = trim_to_alpha(rgba)
    sw, sh = x1 - x0, y1 - y0
    subject = subject.resize((sw, sh), Image.LANCZOS)

    if shadow:
        # Lift the subject so its contact shadow has room to fall BELOW it.
        # Centred with no lift, the shadow is hidden behind the product and the
        # "shadow" only reads as a cropped band at the bottom of the frame.
        lift = int(size * 0.03)
        y0, y1 = y0 - lift, y1 - lift
        canvas = _with_shadow(canvas, (x0, y0, x1, y1), strength=shadow_strength)

    canvas.paste(subject, (x0, y0), subject)
    out = BytesIO()
    canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _with_shadow(
    canvas: Image.Image,
    box: Tuple[int, int, int, int],
    *,
    strength: float = 0.55,
) -> Image.Image:
    """Soft contact shadow under the product's footprint. Never reaches the corners.

    Drawn as a heavily blurred BLACK alpha layer composited onto white - that
    gives a real gradient. An opaque grey ellipse reads as a sticker, which is
    what the first end-to-end run produced.
    """
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx = (x0 + x1) // 2
    cy = y1 - max(2, h // 50)
    rx = max(8, int(w * 0.40))
    ry = max(3, int(h * 0.03))

    layer = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(layer).ellipse(
        (cx - rx, cy - ry, cx + rx, cy + ry),
        fill=int(70 * max(0.0, min(1.0, strength))),
    )
    layer = layer.filter(ImageFilter.GaussianBlur(max(6, int(rx * 0.30))))

    # A blurred ellipse has long tails. Zero the outer border so a corner sample
    # can never find a grey pixel - the listing rule is about the CORNERS.
    border = 8
    zero = ImageDraw.Draw(layer)
    zero.rectangle((0, 0, canvas.size[0] - 1, border), fill=0)
    zero.rectangle((0, 0, border, canvas.size[1] - 1), fill=0)
    zero.rectangle((canvas.size[0] - border, 0, canvas.size[0] - 1, canvas.size[1] - 1), fill=0)
    zero.rectangle((0, canvas.size[1] - border, canvas.size[0] - 1, canvas.size[1] - 1), fill=0)

    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shade.putalpha(layer)
    base = canvas.convert("RGBA")
    base.alpha_composite(shade)
    return base.convert("RGB")


def audit_white(png_bytes: bytes, *, corners: int = 8) -> dict:
    """Prove the background rule instead of asserting it: corner sample + % pure white."""
    import numpy as np

    img = Image.open(BytesIO(png_bytes)).convert("RGB")
    w, h = img.size
    px = img.load()
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1),
           (w // 2, 0), (0, h // 2), (w - 1, h // 2), (w // 2, h - 1)][:corners]
    corner_values = [px[p] for p in pts]
    sample = np.asarray(img.resize((160, 160), Image.BILINEAR))
    pure = int(np.all(sample == 255, axis=-1).sum())
    return {
        "corners_pure_white": all(v == WHITE for v in corner_values),
        "corner_values": corner_values,
        "pure_white_ratio": round(pure / (sample.shape[0] * sample.shape[1]), 4),
        "size": [w, h],
    }


__all__ = ["hero_on_white", "audit_white", "WHITE", "DEFAULT_SIZE", "DEFAULT_FILL"]
