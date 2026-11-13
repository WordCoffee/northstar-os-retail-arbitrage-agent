"""Stray geometry in a generated scene: find it, and fill it deterministically.

D-019: after the cutout cleanup and the label clip, the vision judge still found objects the model
had drawn into the **scene** — a wire above the pouch, a dashed rule line, a floating ring. On a
flat brief the background is a white canvas and nothing survives; on a free/scene brief the scene is
kept, so whatever the model painted stays in the frame beside the product.

The rule this module implements is the one the defect entry asks for: a free background must be
filled around the placed product, or the scene is rejected. Filling is a **median-of-ring** inpaint
— deterministic, no model, no GPU: a stray component is replaced by the median colour of the pixels
inside a band around it. That is right for a flat or softly graded field (a white studio, a wall,
a table) and honest about its limit: on a busy photographic background it would smear, so a
component whose ring is not uniform enough is left alone and recorded, never painted over badly.
"""
from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

import numpy as np


def _decode(image_bytes: bytes) -> Tuple[np.ndarray, str]:
    from PIL import Image  # noqa: PLC0415

    with Image.open(io.BytesIO(image_bytes)) as opened:
        mode = opened.mode
        array = np.asarray(opened.convert("RGB"), dtype=np.uint8).copy()
    return array, mode


def _encode(array: np.ndarray) -> bytes:
    from PIL import Image  # noqa: PLC0415

    buffer = io.BytesIO()
    Image.fromarray(array.astype(np.uint8), "RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _background_level(array: np.ndarray) -> np.ndarray:
    """The field's colour: the median of the outer frame, which the product never covers."""
    h, w = array.shape[:2]
    band = max(2, min(h, w) // 12)
    frame = np.concatenate([
        array[:band, :, :].reshape(-1, 3), array[-band:, :, :].reshape(-1, 3),
        array[:, :band, :].reshape(-1, 3), array[:, -band:, :].reshape(-1, 3)])
    return np.median(frame, axis=0)


def stray_mask(array: np.ndarray, product_box: Tuple[int, int, int, int], *,
               distance: int = 24, margin: int = 6) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Pixels that are 'ink' against the field AND outside the product's box.

    `product_box` is (left, top, right, bottom) — the same convention `place_product` records.
    """
    left, top, right, bottom = (int(v) for v in product_box)
    height, width = array.shape[:2]
    left, right = max(0, left - margin), min(width, right + margin)
    top, bottom = max(0, top - margin), min(height, bottom + margin)

    inside = np.zeros((height, width), dtype=bool)
    inside[top:bottom, left:right] = True
    level = _background_level(array)
    delta = np.abs(array.astype(np.int16) - level.astype(np.int16)).max(axis=2)
    ink = delta > int(distance)
    stray = ink & ~inside
    pixels = int(stray.sum())
    return stray, {"pixels": pixels, "fraction": round(pixels / (height * width), 6),
                   "background": [int(round(float(c))) for c in level]}


def _components(mask: np.ndarray) -> List[Tuple[int, int, int, int, int]]:
    """Connected boxes of a boolean mask, as (left, top, right, bottom, area). 4-connectivity."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    out: List[Tuple[int, int, int, int, int]] = []
    for y in range(height):
        row = mask[y]
        for x in range(width):
            if not row[x] or seen[y, x]:
                continue
            stack = [(y, x)]
            seen[y, x] = True
            min_y = max_y = y
            min_x = max_x = x
            area = 0
            while stack:
                cy, cx = stack.pop()
                area += 1
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
            out.append((min_x, min_y, max_x + 1, max_y + 1, area))
    return out


def fill_stray(png: bytes, product_box: Tuple[int, int, int, int], *,
               max_fraction: float = 0.03, uniformity: float = 18.0) -> Tuple[bytes, Dict[str, Any]]:
    """Fill stray components with the median of their ring. Returns (png, report).

    A component is filled only when its surrounding ring is uniform within `uniformity` levels: on a
    textured photograph the ring is not uniform and the component is left in place and reported.
    """
    array, _ = _decode(png)
    mask, stats = stray_mask(array, product_box)
    report: Dict[str, Any] = {"found_pixels": stats["pixels"],
                              "fraction": stats["fraction"], "filled": 0, "kept": 0,
                              "skipped": [], "filled_components": 0}
    if stats["fraction"] <= 0.0:
        return png, report
    if stats["fraction"] > max_fraction:
        report["skipped"].append(
            f"{stats['fraction']:.3%} of the frame is stray, above the {max_fraction:.0%} fill "
            "limit; the scene is kept and reported rather than repainted")
        report["kept"] = stats["pixels"]
        return png, report

    height, width = array.shape[:2]
    working = array.copy()
    for (left, top, right, bottom, area) in _components(mask):
        pad = max(3, int(max(right - left, bottom - top) * 0.35))
        ring_l, ring_t = max(0, left - pad), max(0, top - pad)
        ring_r, ring_b = min(width, right + pad), min(height, bottom + pad)
        ring = working[ring_t:ring_b, ring_l:ring_r]
        ring_mask = np.ones(ring.shape[:2], dtype=bool)
        ring_mask[top - ring_t:bottom - ring_t, left - ring_l:right - ring_l] = False
        values = ring[ring_mask]
        if values.size == 0:
            report["kept"] += area
            continue
        spread = float(np.abs(values.astype(np.int16)
                              - np.median(values, axis=0).astype(np.int16)).max())
        if spread > uniformity:
            report["skipped"].append(
                f"a {area}px component sits on a textured background (ring spread {spread:.0f})")
            report["kept"] += area
            continue
        fill = np.median(values, axis=0).astype(np.uint8)
        working[top:bottom, left:right][mask[top:bottom, left:right]] = fill
        report["filled"] += area
        report["filled_components"] += 1

    report["ok"] = report["filled"] > 0 and report["kept"] == 0
    return (png if report["filled"] == 0 else _encode(working)), report


__all__ = ["fill_stray", "stray_mask"]
