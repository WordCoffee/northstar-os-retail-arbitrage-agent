"""Image prep — deterministic Amazon MAIN framing + compliance checks.

The listing-image rules the studio has to satisfy are mechanical, so they get
mechanical code, not a model:

  * `main-white-bg`   - the MAIN image sits on pure white
  * `main-fill`       - the product fills at least 85% of the frame
  * `main-min-side`   - the long side is at least 2000 px (and square-ish)

`frame_on_white` takes a BiRefNet cutout (RGBA), trims to the alpha bounding box
and re-centres it on white so the product fills the frame, at any output size.
`check_main_compliance` measures what the file actually is - background
whiteness sampled on the border, fill ratio measured two ways (longest side and
area), and pixel size - and returns blockers rather than an opinion.

Pure PIL + numpy. Local, deterministic, no network.
"""

from __future__ import annotations

import io
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

#: Amazon's published minimum for the long side of a listing image.
MAIN_MIN_SIDE = 2000
#: The product-fills-the-frame rule.
MAIN_MIN_FILL = 0.85
#: A border pixel at or above this value in every channel counts as white.
WHITE_THRESHOLD = 245


def alpha_bbox(rgba: Image.Image, threshold: int = 8) -> Optional[Tuple[int, int, int, int]]:
    """Bounding box of pixels whose alpha exceeds ``threshold`` (None if empty)."""
    a = np.asarray(rgba.convert("RGBA"))[..., 3]
    ys, xs = np.where(a > threshold)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def trim_to_alpha(rgba: Image.Image, pad: int = 0) -> Image.Image:
    """Crop to the visible content (plus optional padding), preserving alpha."""
    rgba = rgba.convert("RGBA")
    box = alpha_bbox(rgba)
    if box is None:
        return rgba
    x0, y0, x1, y1 = box
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(rgba.width, x1 + pad), min(rgba.height, y1 + pad)
    return rgba.crop((x0, y0, x1, y1))


def frame_on_white(rgba: Image.Image, *, fill: float = MAIN_MIN_FILL,
                   size: int = MAIN_MIN_SIDE, square: bool = True) -> Image.Image:
    """Centre a cutout on white so it fills ``fill`` of the frame.

    ``fill`` is applied to the product's LONGEST side (the conservative reading
    of the rule). The output is square by default, which is what a listing slot
    wants, and the product is never upscaled beyond the source pixels by more
    than necessary - that is the caller's trade-off, surfaced in the return of
    ``frame_on_white_bytes``.

    A fill outside (0, 1] would scale the product past the frame and clip it, and an
    empty cutout would produce a blank white square presented as a product. Both are
    refused here rather than shipped, matching ``listing_image.hero_on_white``.
    """
    try:
        fill_value = float(fill)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"fill must be a number in (0, 1], got {fill!r}") from exc
    if not math.isfinite(fill_value) or not (0.0 < fill_value <= 1.0):
        raise ValueError(f"fill must be a finite number in (0, 1], got {fill_value!r}")
    product = trim_to_alpha(rgba)
    if alpha_bbox(product) is None:
        raise ValueError("empty_subject: the cutout has no visible pixels")
    side = int(size)
    if square:
        canvas_w = canvas_h = side
    else:
        # keep the product's aspect; the LONG side becomes `side`
        if product.width >= product.height:
            canvas_w, canvas_h = side, max(1, int(round(side * product.height / product.width)))
        else:
            canvas_h, canvas_w = side, max(1, int(round(side * product.width / product.height)))

    target = fill * min(canvas_w, canvas_h)
    scale = target / max(1, max(product.width, product.height))
    new_w = max(1, int(round(product.width * scale)))
    new_h = max(1, int(round(product.height * scale)))
    scaled = product.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 255))
    canvas.alpha_composite(scaled, ((canvas_w - new_w) // 2, (canvas_h - new_h) // 2))
    return canvas


def frame_on_white_bytes(rgba_png: bytes, *, fill: float = MAIN_MIN_FILL,
                         size: int = MAIN_MIN_SIDE,
                         background: str = "white") -> Dict[str, Any]:
    """PNG bytes of the framed cutout + an honest record of what happened."""
    src = Image.open(io.BytesIO(rgba_png)).convert("RGBA")
    src_box = alpha_bbox(src)
    framed = frame_on_white(src, fill=fill, size=size)
    out = io.BytesIO()
    framed.convert("RGB").save(out, format="PNG")
    product = trim_to_alpha(src)
    scale = (fill * size) / max(1, max(product.width, product.height))
    return {
        "bytes": out.getvalue(), "size": [framed.width, framed.height],
        "background": background, "fill_target": fill,
        "source_bbox": list(src_box) if src_box else None,
        "scale_applied": round(scale, 4),
        "upscaled": bool(scale > 1.0),
        "note": ("Cutout trimmed to its alpha box and centred on white; fill is "
                 "measured on the product's longest side."),
    }


def check_main_compliance(png: bytes, *, min_fill: float = MAIN_MIN_FILL,
                          min_side: int = MAIN_MIN_SIDE,
                          require_square: bool = False) -> Dict[str, Any]:
    """Measure a listing image against the mechanical MAIN rules.

    Returns the measurements and a blockers list - never a bare pass/fail, so a
    near miss is diagnosable.
    """
    img = Image.open(io.BytesIO(png))
    had_alpha = img.mode in ("RGBA", "LA")
    rgba = img.convert("RGBA")
    rgb = Image.new("RGB", rgba.size, (255, 255, 255))
    rgb.paste(rgba, mask=rgba.split()[3])
    arr = np.asarray(rgb, dtype=np.uint8)

    # background: sample the one-pixel border
    border = np.concatenate([
        arr[0, :, :].reshape(-1, 3), arr[-1, :, :].reshape(-1, 3),
        arr[:, 0, :].reshape(-1, 3), arr[:, -1, :].reshape(-1, 3)])
    white_frac = float((border >= WHITE_THRESHOLD).all(axis=1).mean())

    box = alpha_bbox(rgba) if had_alpha else None
    measurable = True
    fill_reason = None
    if box is None:
        if had_alpha:
            measurable = False
            fill_reason = "alpha_empty"
        elif white_frac >= 0.98:
            # white background: the product is whatever is not white
            mask = ~(arr >= WHITE_THRESHOLD).all(axis=2)
            ys, xs = np.where(mask)
            if xs.size:
                box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1)
            else:
                measurable = False
                fill_reason = "empty"
        else:
            # No alpha AND a non-white background: the product cannot be
            # separated from the background in this file. Report unknown rather
            # than pretending the whole frame is product.
            measurable = False
            fill_reason = "no_alpha_non_white_bg"

    long_side = max(rgba.width, rgba.height)
    if box and measurable:
        bw, bh = box[2] - box[0], box[3] - box[1]
        fill_longest = max(bw, bh) / float(long_side)
        fill_area = (bw * bh) / float(rgba.width * rgba.height)
    else:
        fill_longest = fill_area = None

    blockers: List[str] = []
    if white_frac < 0.98:
        blockers.append(f"background is not pure white ({white_frac:.1%} of border "
                        f"pixels are >= {WHITE_THRESHOLD})")
    if fill_longest is None:
        if fill_reason == "empty":
            blockers.append("no product detected: every sampled pixel is white")
        elif fill_reason == "alpha_empty":
            blockers.append("the alpha channel is empty: the cutout has no visible product")
        else:
            blockers.append("fill could not be measured (no alpha channel and a "
                            "non-white background): supply a cutout or a white-background "
                            "file so the product area is identifiable")
    elif fill_longest < min_fill:
        blockers.append(f"product fills {fill_longest:.1%} of the frame on its "
                        f"longest side (needs >= {min_fill:.0%})")
    if long_side < min_side:
        blockers.append(f"long side is {long_side}px (needs >= {min_side}px)")
    if require_square and rgba.width != rgba.height:
        blockers.append(f"image is {rgba.width}x{rgba.height}; this slot wants square")

    return {
        "status": "ok",
        "pixels": [rgba.width, rgba.height], "had_alpha": had_alpha,
        "background_white_frac": round(white_frac, 4),
        "product_bbox": list(box) if (box and measurable) else None,
        "fill_longest_side": (None if fill_longest is None else round(fill_longest, 4)),
        "fill_area": (None if fill_area is None else round(fill_area, 4)),
        "fill_measurable": measurable,
        "verdict": "compliant" if not blockers else "blocked",
        "blockers": blockers,
        "note": ("Fill is reported both ways: longest side (the conservative "
                 "reading, used for the verdict) and area. Amazon's own policy "
                 "page is the authority."),
    }


def upscale_lanczos(png: bytes, *, factor: float = 2.0,
                    sharpen: bool = True) -> Dict[str, Any]:
    """Deterministic upscale for print / listing sizes — no GPU, no model.

    Model upscaling is deliberately NOT on this path: RealESRGAN x4 aborted the
    ComfyUI server on a 1216x1216 input on this 16 GB box (2026-10-19, fatal
    error inside the RRDB conv; circuit breaker honoured, no auto-retry), and the
    SeedVR2 weights ship only as component nodes in this ComfyUI. LANCZOS plus a
    light unsharp keeps edges honest and cannot take the pipeline down.

    ``factor`` is capped at 4. Upscale a CLEAN PLATE before compositing text:
    any upscaler softens hairlines.
    """
    f = float(factor)
    if f <= 1.0:
        raise ValueError(f"factor must be >1, got {f}")
    f = min(f, 4.0)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    new = (max(1, int(round(img.width * f))), max(1, int(round(img.height * f))))
    big = img.resize(new, Image.LANCZOS)
    if sharpen:
        from PIL import ImageFilter
        big = big.filter(ImageFilter.UnsharpMask(radius=1.6, percent=55, threshold=3))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "size": [big.width, big.height],
            "source_size": [img.width, img.height], "factor": f,
            "method": "lanczos+unsharp", "gpu": False,
            "note": ("Deterministic upscale. Upscale a CLEAN PLATE before the text "
                     "composite: any upscaler softens hairlines.")}
