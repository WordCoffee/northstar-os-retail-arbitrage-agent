"""Deterministic text-safe zone detection.

The image model draws a blank label panel; the deterministic compositor should
place the exact-text panel *on that panel*, not on a fixed guess. This module
finds the blank panel in a generated scene and returns it as a normalized quad.

It is pure image analysis — no model, no network, no randomness — so the same
scene always yields the same zone. If nothing panel-like is found it returns
``None`` and the caller falls back to the preset quad (and says so).

Heuristic: a label panel is a smooth, bright, low-saturation region that does
*not* touch the image border (the border region is the studio background). The
mask is dilated slightly first so a thin outline or specular seam does not split
one panel into fragments; the winning region's bounding box is then measured
against the *original* mask so it stays tight.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

Quad = List[List[float]]


def _dilate(mask: Any, iterations: int = 2) -> Any:
    """4-connected binary dilation by N steps (bridges thin seams)."""
    m = mask
    for _ in range(max(0, iterations)):
        m2 = m.copy()
        m2[1:, :] |= m[:-1, :]
        m2[:-1, :] |= m[1:, :]
        m2[:, 1:] |= m[:, :-1]
        m2[:, :-1] |= m[:, 1:]
        m = m2
    return m


def _label_components(mask: Any) -> Tuple[List[Dict[str, Any]], List[List[int]]]:
    """4-connected components of a boolean mask (small images only)."""
    h, w = mask.shape
    labels = [[0] * w for _ in range(h)]
    comps: List[Dict[str, Any]] = []
    nxt = 0
    for y0 in range(h):
        row = mask[y0]
        for x0 in range(w):
            if not row[x0] or labels[y0][x0]:
                continue
            nxt += 1
            labels[y0][x0] = nxt
            q = deque([(y0, x0)])
            area = 0
            minx = maxx = x0
            miny = maxy = y0
            border = False
            while q:
                cy, cx = q.popleft()
                area += 1
                if cy == 0 or cx == 0 or cy == h - 1 or cx == w - 1:
                    border = True
                if cx < minx:
                    minx = cx
                if cx > maxx:
                    maxx = cx
                if cy < miny:
                    miny = cy
                if cy > maxy:
                    maxy = cy
                for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                    if 0 <= ny < h and 0 <= nx < w and mask[ny][nx] and not labels[ny][nx]:
                        labels[ny][nx] = nxt
                        q.append((ny, nx))
            comps.append({"id": nxt, "area": area, "bbox": (minx, miny, maxx, maxy),
                          "border": border})
    return comps, labels


def detect_label_zone(image: Image.Image, *, max_side: int = 192,
                      val_min: float = 0.62, sat_max: float = 0.20,
                      min_area_frac: float = 0.02, max_area_frac: float = 0.5,
                      min_rectangularity: float = 0.55,
                      aspect_range: Tuple[float, float] = (0.25, 3.2),
                      pad_frac: float = 0.01, dilate_iters: int = 2,
                      min_confidence: float = 0.25,
                      ) -> Optional[Dict[str, Any]]:
    """Return ``{"quad_norm": [...], "confidence": float, "bbox_px": [...]}`` or None."""
    try:
        import numpy as np
    except Exception:  # pragma: no cover
        return None

    im = image.convert("RGB")
    w0, h0 = im.size
    if w0 < 8 or h0 < 8:
        return None
    scale = max_side / float(max(w0, h0))
    if scale < 1.0:
        im = im.resize((max(8, int(w0 * scale)), max(8, int(h0 * scale))), Image.BILINEAR)
    arr = np.asarray(im, dtype=np.float32) / 255.0
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    mask = (mx >= val_min) & (sat <= sat_max)

    dil = _dilate(mask, dilate_iters)
    comps, labels = _label_components(dil)
    h, w = mask.shape
    total = float(h * w)

    best: Optional[Dict[str, Any]] = None
    for c in comps:
        if c["border"]:
            continue
        minx, miny, maxx, maxy = c["bbox"]
        bw = maxx - minx + 1
        bh = maxy - miny + 1
        if bw < 4 or bh < 4:
            continue
        area_frac = c["area"] / total
        if not (min_area_frac <= area_frac <= max_area_frac):
            continue
        rect = c["area"] / float(bw * bh)
        if rect < min_rectangularity:
            continue
        aspect = bw / float(bh)
        if not (aspect_range[0] <= aspect <= aspect_range[1]):
            continue
        if best is None or c["area"] > best["area"]:
            best = c

    if best is None:
        return None

    # Tighten the box against the ORIGINAL (undilated) mask for this component.
    labels_np = np.asarray(labels)
    sel = (labels_np == best["id"]) & mask
    if sel.any():
        ys, xs = np.where(sel)
        minx, maxx = int(xs.min()), int(xs.max())
        miny, maxy = int(ys.min()), int(ys.max())
        area = int(sel.sum())
    else:  # pragma: no cover - defensive
        minx, miny, maxx, maxy = best["bbox"]
        area = best["area"]
    bw = maxx - minx + 1
    bh = maxy - miny + 1
    rect = area / float(bw * bh)

    SX = w0 / float(w)
    SY = h0 / float(h)
    x0 = max(0.0, (minx - pad_frac * bw) * SX)
    y0 = max(0.0, (miny - pad_frac * bh) * SY)
    x1 = min(float(w0), (maxx + 1 + pad_frac * bw) * SX)
    y1 = min(float(h0), (maxy + 1 + pad_frac * bh) * SY)
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None

    quad: Quad = [[x0 / w0, y0 / h0], [x1 / w0, y0 / h0],
                  [x1 / w0, y1 / h0], [x0 / w0, y1 / h0]]
    area_frac = area / total
    confidence = round(min(1.0, rect * min(1.0, area_frac / 0.10)), 3)
    if confidence < min_confidence:
        # Too weak to trust — better to use the preset quad than a bad guess.
        return None
    return {
        "quad_norm": [[round(px, 5), round(py, 5)] for px, py in quad],
        "confidence": confidence,
        "area_frac": round(area_frac, 4),
        "rectangularity": round(rect, 3),
        "bbox_px": [round(x0), round(y0), round(x1), round(y1)],
    }


def detect_label_zone_file(path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    with Image.open(path) as im:
        return detect_label_zone(im, **kwargs)
