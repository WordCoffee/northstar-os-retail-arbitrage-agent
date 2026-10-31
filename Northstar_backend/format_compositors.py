"""Format compositors for box, bottle and tube (pouch lives in pouch_label).

Each function takes a rendered PLATE and a flat LABEL panel and returns the
composited PNG bytes plus what it did. The transforms are the point:

    box     perspective warp onto a measured quad (PIL QUAD transform)
    bottle  cylindrical column resample (sinusoidal gain toward the silhouette)
    tube    trapezoid taper + crimp-zone masking

Pure PIL/numpy, no GPU, no model. The pouch compositor already proved the
`neutralize -> warp -> realism` order; these follow the same order.
"""
from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageFilter

Quad = Sequence[Sequence[float]]


def _as_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    return Image.open(BytesIO(value)).convert("RGB")


def _feather_mask(size: Tuple[int, int], quad: Quad, feather: int = 2) -> Image.Image:
    from PIL import ImageDraw
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).polygon([(float(x), float(y)) for x, y in quad], fill=255)
    return mask.filter(ImageFilter.GaussianBlur(max(0, int(feather))))


def _homography(src: Sequence[Sequence[float]],
                dst: Sequence[Sequence[float]]) -> np.ndarray:
    """3x3 homography mapping src -> dst (four point correspondences)."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    h = np.linalg.solve(np.asarray(a, dtype=float), np.asarray(b, dtype=float))
    return np.append(h, 1.0).reshape(3, 3)


def _warp_to_quad(src: Image.Image, quad: Quad, size: Tuple[int, int]) -> Image.Image:
    """Map the whole label rectangle onto the measured quad (perspective).

    PIL's PERSPECTIVE transform samples the source through an OUTPUT -> INPUT
    homography, so the inverse of the label -> quad mapping is what it wants.
    The earlier QUAD call passed the source corners in the wrong winding and
    stretched the label to the plate instead of warping it onto the face.
    """
    w, h = size
    src_pts = [(0.0, 0.0), (float(src.width), 0.0),
               (float(src.width), float(src.height)), (0.0, float(src.height))]
    forward = _homography(src_pts, [(float(x), float(y)) for x, y in quad])
    try:
        inverse = np.linalg.inv(forward)
    except np.linalg.LinAlgError as exc:
        raise ValueError("degenerate quad: the four corners are collinear") from exc
    inverse = inverse / inverse[2, 2]
    coeffs = tuple(float(c) for c in inverse.flatten()[:8])
    return src.transform((w, h), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC)


def box_composite(plate: Any, label: Any, quad: Quad, *,
                  feather: int = 2, shade: float = 0.18) -> Dict[str, Any]:
    """Perspective-warp the label onto four measured corners of a box face."""
    base = _as_image(plate)
    src = _as_image(label)
    w, h = base.size
    pts = [(float(p[0]), float(p[1])) for p in quad]
    if len(pts) != 4:
        raise ValueError("box_composite needs exactly 4 corner points (TL, TR, BR, BL)")

    warped = _warp_to_quad(src, pts, (w, h))
    mask = _feather_mask((w, h), pts, feather)
    base.paste(warped, (0, 0), mask)

    if shade:
        # The face darkens away from the light: a linear ramp across the quad.
        # The ramp is masked to the quad, so background above/below the box is
        # never darkened (a full-height ramp was the first version's defect).
        xs = [p[0] for p in pts]
        x0, x1 = max(0, int(min(xs))), min(w, int(max(xs)))
        arr = np.zeros((h, w), dtype=np.uint8)
        if x1 > x0:
            row = np.linspace(0, int(255 * shade), x1 - x0).astype(np.uint8)
            arr[:, x0:x1] = row
        ramp = Image.fromarray(arr, mode="L").filter(ImageFilter.GaussianBlur(2))
        ramp = Image.composite(ramp, Image.new("L", (w, h), 0),
                               _feather_mask((w, h), pts, feather))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        base = Image.composite(dark, base, ramp.point(lambda v: int(v * 0.5)))

    buf = BytesIO()
    base.save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "size": list(base.size),
            "warp": "perspective-quad", "corners": [[round(x, 2), round(y, 2)] for x, y in pts]}


def bottle_composite(plate: Any, label: Any, quad: Quad, *,
                     wrap_fraction: float = 0.92, seam_gap_px: int = 6,
                     shade: float = 0.22) -> Dict[str, Any]:
    """Cylindrical resample: vertical strips compress toward the silhouette."""
    base = _as_image(plate)
    src = _as_image(label).resize((max(2, int((quad[1][0] - quad[0][0]))),
                                   max(2, int((quad[2][1] - quad[0][1])))), Image.LANCZOS)
    w, h = base.size

    cols = src.width
    out = Image.new("RGB", src.size, (255, 255, 255))
    src_a = np.asarray(src, dtype=np.float32)
    res = np.zeros_like(src_a)
    for x in range(cols):
        theta = (x / max(1, cols - 1)) * np.pi * wrap_fraction
        # gain = sin(theta): full width at the centre of the arc, zero at the edge
        sx = int(round((1 - np.sin(theta)) * 0.5 * (cols - 1)))
        res[:, x] = src_a[:, sx]
    out = Image.fromarray(res.clip(0, 255).astype(np.uint8))

    x0, y0 = int(quad[0][0]), int(quad[0][1])
    mask = Image.new("L", src.size, 255)
    if seam_gap_px > 0:
        from PIL import ImageDraw
        d = ImageDraw.Draw(mask)
        d.rectangle((0, 0, seam_gap_px, src.height), fill=0)
        d.rectangle((src.width - seam_gap_px, 0, src.width, src.height), fill=0)
    base.paste(out, (x0, y0), mask)

    if shade:
        # Shade the label's own left/right edges, never the plate around it and
        # never the seam gap (the gap must keep the plate's own colour).
        arr = np.asarray(base, dtype=np.float32)
        x1 = min(w, x0 + src.width)
        y1 = min(h, y0 + src.height)
        edge = max(1, src.width // 5)
        ramp = np.linspace(1.0, 1.0 - shade, edge)
        gap = max(0, int(seam_gap_px))
        left_start, left_end = x0 + gap, min(x1, x0 + gap + edge)
        right_end, right_start = x1 - gap, max(x0, x1 - gap - edge)
        if left_end > left_start and y1 > y0:
            width_l = left_end - left_start
            arr[y0:y1, left_start:left_end] *= ramp[::-1][:width_l][None, :, None]
        if right_end > right_start and y1 > y0:
            width_r = right_end - right_start
            arr[y0:y1, right_start:right_end] *= ramp[:width_r][None, :, None]
        base = Image.fromarray(arr.clip(0, 255).astype(np.uint8))

    buf = BytesIO()
    base.save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "size": list(base.size),
            "warp": "cylindrical", "wrap_fraction": round(float(wrap_fraction), 4),
            "seam_gap_px": int(seam_gap_px)}


def tube_composite(plate: Any, label: Any, quad: Quad, *,
                   crimp_top: int = 8, crimp_bottom: int = 8,
                   taper: float = 0.06, shade: float = 0.16) -> Dict[str, Any]:
    """Trapezoid taper (tubes narrow toward the crimp) + crimp-zone masking."""
    base = _as_image(plate)
    src = _as_image(label)
    w, h = base.size
    x0, y0 = int(quad[0][0]), int(quad[0][1])
    x1, y1 = int(quad[1][0]), int(quad[2][1])
    tw, th = max(2, x1 - x0), max(2, y1 - y0)

    inset = int(tw * max(0.0, min(0.4, taper)))
    warped = src.resize((tw, th), Image.LANCZOS)
    warped = warped.transform((tw, th), Image.QUAD,
                              (inset, 0, tw - inset, 0, tw, th, 0, th),
                              resample=Image.BICUBIC)

    mask = Image.new("L", (tw, th), 255)
    from PIL import ImageDraw
    d = ImageDraw.Draw(mask)
    if crimp_top > 0:
        d.rectangle((0, 0, tw, min(crimp_top, th)), fill=0)
    if crimp_bottom > 0:
        d.rectangle((0, max(0, th - crimp_bottom), tw, th), fill=0)
    mask = mask.filter(ImageFilter.GaussianBlur(1))

    base.paste(warped, (x0, y0), mask)
    if shade:
        arr = np.asarray(base, dtype=np.float32)
        ramp = np.linspace(1.0, 1.0 - shade, max(1, tw // 3)) if tw > 3 else np.array([1.0])
        arr[y0:y0 + th, x0:x0 + len(ramp)] *= ramp[None, :, None]
        base = Image.fromarray(arr.clip(0, 255).astype(np.uint8))

    buf = BytesIO()
    base.save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "size": list(base.size), "warp": "taper+quad",
            "taper": round(float(taper), 3),
            "crimp_masked_px": int(crimp_top + crimp_bottom)}


COMPOSITORS = {"box": box_composite, "bottle": bottle_composite, "tube": tube_composite}


def composite(kind: str, plate: Any, label: Any, quad: Quad, **kw) -> Dict[str, Any]:
    fn = COMPOSITORS.get(str(kind or "").strip().lower())
    if fn is None:
        raise KeyError(f"no compositor for {kind!r}; known: {sorted(COMPOSITORS)}")
    return fn(plate, label, quad, **kw)


__all__ = ["box_composite", "bottle_composite", "tube_composite", "composite", "COMPOSITORS"]
