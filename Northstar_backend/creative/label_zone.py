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


def _snap_to_edges(x0: int, y0: int, x1: int, y1: int, gx: Any, gy: Any,
                   w: int, h: int, *, margin: int = 16,
                   v_thresh: float = 0.020, h_thresh: float = 0.020) -> Tuple[int, int, int, int]:
    """Extend a bright core to the nearest strong straight edge on each side.

    Printed labels are bounded by crisp edges; shading (glass, folds) can push
    part of the panel below the brightness threshold. Snapping recovers the true
    extent without inventing one, because it only moves to a real edge nearby.
    """
    try:
        import numpy as np
    except Exception:  # pragma: no cover
        return x0, y0, x1, y1

    yspan = slice(max(0, y0), min(h, y1 + 1))
    xspan = slice(max(0, x0), min(w, x1 + 1))
    vprof = gx[yspan, :].mean(axis=0) if yspan.stop > yspan.start else None
    hprof = gy[:, xspan].mean(axis=1) if xspan.stop > xspan.start else None

    def first_above(prof, start, stop, step, thresh):
        i = start
        while (i - stop) * step <= 0:
            if 0 <= i < len(prof) and prof[i] >= thresh:
                return i
            i += step
        return None

    if vprof is not None:
        r = first_above(vprof, x1 + 1, min(w - 1, x1 + margin), 1, v_thresh)
        if r is not None:
            x1 = r
        l = first_above(vprof, x0 - 1, max(0, x0 - margin), -1, v_thresh)
        if l is not None:
            x0 = l
    if hprof is not None:
        d = first_above(hprof, y1 + 1, min(h - 1, y1 + margin), 1, h_thresh)
        if d is not None:
            y1 = d
        t = first_above(hprof, y0 - 1, max(0, y0 - margin), -1, h_thresh)
        if t is not None:
            y0 = t
    return x0, y0, x1, y1


def _runs(flags: Any) -> List[Tuple[int, int]]:
    """Maximal runs of True in a 1-D boolean array-like."""
    out: List[Tuple[int, int]] = []
    start = None
    for i, v in enumerate(flags):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - 1))
            start = None
    if start is not None:
        out.append((start, len(flags) - 1))
    return out


def _split_rows_gap(sub: Any) -> List[Tuple[int, int]]:
    return _runs(sub.any(axis=1))


def _split_rows_edges(sub: Any, grad_band: Any, *, edge_thresh: float = 0.03,
                      min_h: int = 12, depth: int = 3) -> List[Tuple[int, int]]:
    """Split a row band at the strongest internal horizontal edge.

    A printed label is bounded by crisp straight edges; a bright product window
    continuous with the label usually is not. Only splits when both sides stay
    tall enough, so well-behaved single panels are left untouched.
    """
    try:
        import numpy as np
    except Exception:  # pragma: no cover
        return [(0, sub.shape[0] - 1)]
    if depth <= 0 or sub.shape[0] < 2 * min_h:
        return [(0, sub.shape[0] - 1)]
    col_any = sub.any(axis=0)
    if not col_any.any():
        return [(0, sub.shape[0] - 1)]
    x0, x1 = int(np.argmax(col_any)), int(len(col_any) - 1 - np.argmax(col_any[::-1]))
    band = grad_band[:, x0:x1 + 1]
    row_edge = band.mean(axis=1)
    # ignore the outer 1px so the region's own boundary is not chosen
    inner = row_edge[min_h:sub.shape[0] - min_h]
    if inner.size == 0:
        return [(0, sub.shape[0] - 1)]
    k = int(np.argmax(inner)) + min_h
    if row_edge[k] < edge_thresh:
        return [(0, sub.shape[0] - 1)]
    top = _split_rows_edges(sub[:k, :], grad_band[:k, :], edge_thresh=edge_thresh,
                            min_h=min_h, depth=depth - 1)
    bot = _split_rows_edges(sub[k:, :], grad_band[k:, :], edge_thresh=edge_thresh,
                            min_h=min_h, depth=depth - 1)
    return top + [(a + k, b + k) for a, b in bot]


def detect_label_zone(image: Image.Image, *, max_side: int = 192,
                      val_min: float = 0.62, sat_max: float = 0.20,
                      min_area_frac: float = 0.02, max_area_frac: float = 0.5,
                      min_rectangularity: float = 0.55,
                      aspect_range: Tuple[float, float] = (0.25, 3.2),
                      pad_frac: float = 0.01, dilate_iters: int = 2,
                      min_confidence: float = 0.25,
                      ) -> Optional[Dict[str, Any]]:
    """Return ``{"quad_norm": [...], "confidence": float, "bbox_px": [...]}`` or None.

    Dilation is only used to *find* the candidate panel. The candidate is then
    split back on the undilated mask wherever a full-width/height gap exists, so
    a bright product window next to the label cannot be fused into it. Panels are
    flat and smooth, so among plausible sub-regions the smoothest wins.
    """
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
    h, w = mask.shape
    total = float(h * w)

    # Local gradient magnitude (blank panels are much smoother than product fill).
    gray = arr.mean(axis=2)
    gy = np.zeros_like(gray)
    gx = np.zeros_like(gray)
    gy[1:, :] = np.abs(gray[1:, :] - gray[:-1, :])
    gx[:, 1:] = np.abs(gray[:, 1:] - gray[:, :-1])
    grad = gx + gy

    dil = _dilate(mask, dilate_iters)
    comps, labels = _label_components(dil)
    labels_np = np.asarray(labels)

    regions: List[Dict[str, Any]] = []
    for c in comps:
        if c["border"]:
            continue
        minx, miny, maxx, maxy = c["bbox"]
        sub = mask[miny:maxy + 1, minx:maxx + 1]
        if sub.size == 0:
            continue
        # Split the candidate on the RAW mask: row gaps, then horizontal edges,
        # then column gaps.
        for ry0, ry1 in _split_rows_gap(sub):
            band_mask = sub[ry0:ry1 + 1, :]
            band_grad = grad[miny + ry0:miny + ry1 + 1, minx:maxx + 1]
            for by0, by1 in _split_rows_edges(band_mask, band_grad):
                band = band_mask[by0:by1 + 1, :]
                for rx0, rx1 in _runs(band.any(axis=0)):
                    box = band[:, rx0:rx1 + 1]
                    area = int(box.sum())
                    bw, bh = box.shape[1], box.shape[0]
                    if bw < 4 or bh < 4:
                        continue
                    area_frac = area / total
                    if not (min_area_frac <= area_frac <= max_area_frac):
                        continue
                    rect = area / float(bw * bh)
                    if rect < min_rectangularity:
                        continue
                    aspect = bw / float(bh)
                    if not (aspect_range[0] <= aspect <= aspect_range[1]):
                        continue
                    gy0, gy1 = miny + ry0 + by0, miny + ry0 + by1
                    g = float(band_grad[by0:by1 + 1, rx0:rx1 + 1][box].mean())
                    regions.append({
                        "bbox": (minx + rx0, gy0, minx + rx1, gy1),
                        "area": area, "bw": bw, "bh": bh, "rect": rect,
                        "area_frac": area_frac, "grad": g,
                        "score": area_frac * rect * (1.0 / (1.0 + 25.0 * g)),
                    })

    if not regions:
        return None
    best = max(regions, key=lambda r: r["score"])

    minx, miny, maxx, maxy = best["bbox"]
    minx, miny, maxx, maxy = _snap_to_edges(minx, miny, maxx, maxy, gx, gy, w, h,
                                            margin=max(4, int(0.09 * w)))
    bw, bh = maxx - minx + 1, maxy - miny + 1
    if bw < 4 or bh < 4:
        minx, miny, maxx, maxy = best["bbox"]
        bw, bh = best["bw"], best["bh"]
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
    confidence = round(min(1.0, best["rect"] * min(1.0, best["area_frac"] / 0.10)), 3)
    if confidence < min_confidence:
        # Too weak to trust — better to use the preset quad than a bad guess.
        return None
    return {
        "quad_norm": [[round(px, 5), round(py, 5)] for px, py in quad],
        "confidence": confidence,
        "area_frac": round(best["area_frac"], 4),
        "rectangularity": round(best["rect"], 3),
        "smoothness": round(best["grad"], 4),
        "bbox_px": [round(x0), round(y0), round(x1), round(y1)],
    }


def detect_label_zone_file(path: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    with Image.open(path) as im:
        return detect_label_zone(im, **kwargs)
