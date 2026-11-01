"""Generalized surface measurement for every packaging format.

`pouch_label.measure_face` proved the rule this module exists to enforce: a
label must be warped onto the face the render actually produced, never onto a
nominal quad. This generalises that measurement to box, bottle and tube with one
algorithm and four parameter sets:

    silhouette -> sub-pixel edges -> format-specific fit -> residual gate

    box      four line fits around the visible front face (perspective included)
    bottle   longest near-constant-width band of the silhouette
    tube     the same band, plus a taper test and crimp-boundary detection

Every result carries the measured quad, the residual that gates it and the
method that produced it. Nothing is guessed: when the silhouette cannot support
a fit inside MAX_GEOM_RESIDUAL_PX, `SurfaceNotMeasurable` is raised and the
caller must block rather than print on a nominal quad.

Pure PIL + numpy (+ OpenCV when present). No provider call, no network, no cost.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image

import pouch_label as pl

#: Same gate `pouch_label` already enforces for a pouch face.
MAX_GEOM_RESIDUAL_PX = pl.MAX_GEOM_RESIDUAL_PX
#: RANSAC inlier band for an edge fit, in pixels.
EDGE_INLIER_PX = pl.EDGE_INLIER_PX
#: A face smaller than this share of the silhouette is not a label target.
MIN_FACE_SHARE = 0.15
#: A cylinder band shorter than this share of the silhouette is not printable.
MIN_BAND_SHARE = 0.12
#: A band whose width coefficient of variation exceeds this is not cylindrical.
MAX_BAND_CV = 0.05
#: Boxes are allowed a slight barrel; cylinders are not.
MAX_CYLINDER_TAPER = 0.35


class SurfaceNotMeasurable(ValueError):
    """The plate does not contain a surface that can be measured safely."""


# ── image / mask helpers ────────────────────────────────────────────────────

def _as_image(value: Any) -> Image.Image:
    if isinstance(value, Image.Image):
        return value.convert("RGB")
    if isinstance(value, (bytes, bytearray)):
        from io import BytesIO
        return Image.open(BytesIO(value)).convert("RGB")
    return Image.open(Path(value)).convert("RGB")


def _clamp01(value: float) -> float:
    return float(max(0.0, min(1.0, value)))


def _longest_run(flags: np.ndarray) -> Tuple[int, int]:
    """Inclusive [start, end] of the longest True run, or (-1, -1)."""
    best = (-1, -1)
    start = None
    for i, flag in enumerate(flags):
        if flag and start is None:
            start = i
        elif not flag and start is not None:
            if i - start > best[1] - best[0] + 1:
                best = (start, i - 1)
            start = None
    if start is not None and len(flags) - start > best[1] - best[0] + 1:
        best = (start, len(flags) - 1)
    return best


def _median_filter(values: np.ndarray, window: int = 5) -> np.ndarray:
    """Small median filter that leaves NaN rows alone."""
    if window <= 1 or values.size < window:
        return values.copy()
    pad = window // 2
    out = values.copy()
    for i in range(values.size):
        lo, hi = max(0, i - pad), min(values.size, i + pad + 1)
        chunk = values[lo:hi]
        chunk = chunk[np.isfinite(chunk)]
        if chunk.size:
            out[i] = float(np.median(chunk))
    return out


def _fit_robust(coord: np.ndarray, value: np.ndarray, *, degree: int = 1,
                tol: float = EDGE_INLIER_PX, iters: int = 300,
                seed: int = 7) -> Optional[Tuple[np.ndarray, np.ndarray, float]]:
    """RANSAC + iterated least squares for value(coord).

    Returns (coefficients, inlier mask, mean absolute inlier residual) or None.
    A straight box edge or a cylinder side is a low-degree polynomial; a prop or
    a shadow touching the product is the outlier RANSAC exists to reject.
    """
    coord = np.asarray(coord, dtype=float)
    value = np.asarray(value, dtype=float)
    ok = np.isfinite(coord) & np.isfinite(value)
    c, v = coord[ok], value[ok]
    need = int(degree) + 1
    if c.size < max(16, need * 5):
        return None
    rng = np.random.default_rng(seed)
    best: Optional[Tuple[int, np.ndarray]] = None
    for _ in range(int(iters)):
        idx = rng.choice(c.size, need, replace=False)
        if float(np.ptp(c[idx])) < 8.0:
            continue
        try:
            coef = np.polyfit(c[idx], v[idx], degree)
        except (ValueError, np.linalg.LinAlgError):
            continue
        n = int((np.abs(v - np.polyval(coef, c)) < tol).sum())
        if best is None or n > best[0]:
            best = (n, coef)
    if best is None or best[0] < max(12, need * 4):
        return None
    coef = best[1]
    keep = np.ones(c.size, dtype=bool)
    for _ in range(3):
        res = np.abs(v - np.polyval(coef, c))
        keep = res < tol
        if keep.sum() < max(12, need * 4):
            return None
        coef = np.polyfit(c[keep], v[keep], degree)
    res = np.abs(v - np.polyval(coef, c))
    keep = res < tol
    if keep.sum() < max(12, need * 4):
        return None
    return coef, keep, float(res[keep].mean())


def _fit_edge(coord: np.ndarray, value: np.ndarray, *,
              tol: float = EDGE_INLIER_PX) -> Tuple[np.ndarray, np.ndarray, float, str]:
    """Prefer a line; fall back to a quadratic; refuse when neither fits."""
    fit = _fit_robust(coord, value, degree=1, tol=tol)
    if fit is not None:
        return fit[0], fit[1], fit[2], "linear"
    fit = _fit_robust(coord, value, degree=2, tol=tol)
    if fit is not None:
        return fit[0], fit[1], fit[2], "quadratic"
    raise SurfaceNotMeasurable(
        "the surface edge is not straight or smoothly curved enough to fit "
        f"within {tol:.2f} px")


def _subpixel_col_edges(mask: np.ndarray, blur_radius: int = 2
                        ) -> Tuple[np.ndarray, np.ndarray]:
    """Per-column top/bottom to sub-pixel precision (transpose of the row fit)."""
    return pl._subpixel_row_edges(mask.T, blur_radius=blur_radius)


def _row_band(mask: np.ndarray) -> Tuple[int, int]:
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size < 16:
        raise SurfaceNotMeasurable("no product silhouette found: the plate is background")
    return int(rows[0]), int(rows[-1])


def _validate_quad(quad: Sequence[Sequence[float]], width: int, height: int,
                   *, min_area_share: float = 0.01) -> List[List[float]]:
    """Order, convexity, bounds and minimum area. A bad quad never ships."""
    pts = np.asarray(quad, dtype=float)
    if pts.shape != (4, 2) or not np.isfinite(pts).all():
        raise SurfaceNotMeasurable("the fitted quad is not four finite points")
    if float(pts[:, 0].min()) < -1 or float(pts[:, 0].max()) > width + 1:
        raise SurfaceNotMeasurable("the fitted quad runs outside the plate horizontally")
    if float(pts[:, 1].min()) < -1 or float(pts[:, 1].max()) > height + 1:
        raise SurfaceNotMeasurable("the fitted quad runs outside the plate vertically")
    edges = np.roll(pts, -1, axis=0) - pts
    cross = edges[:, 0] * np.roll(edges[:, 1], -1) - edges[:, 1] * np.roll(edges[:, 0], -1)
    if not (bool((cross > 0).all()) or bool((cross < 0).all())):
        raise SurfaceNotMeasurable("the fitted quad is not convex / is self-intersecting")
    area = 0.5 * abs(float(np.dot(pts[:, 0], np.roll(pts[:, 1], -1))
                           - np.dot(pts[:, 1], np.roll(pts[:, 0], -1))))
    if area < min_area_share * width * height:
        raise SurfaceNotMeasurable("the fitted quad is too small to be a label face")
    return [[round(float(x), 2), round(float(y), 2)] for x, y in pts]


def _inset_quad(quad: Sequence[Sequence[float]], *, fx: float = 0.06,
                ftop: float = 0.06, fbottom: float = 0.06) -> List[List[float]]:
    """Inset a quad along its own edges (bilinear, so perspective is preserved)."""
    tl, tr, br, bl = (np.asarray(p, dtype=float) for p in quad)

    def lerp(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
        return a + (b - a) * float(t)

    top_l, top_r = lerp(tl, tr, fx), lerp(tl, tr, 1.0 - fx)
    bot_l, bot_r = lerp(bl, br, fx), lerp(bl, br, 1.0 - fx)
    return [lerp(top_l, bot_l, ftop).tolist(),
            lerp(top_r, bot_r, ftop).tolist(),
            lerp(top_r, bot_r, 1.0 - fbottom).tolist(),
            lerp(top_l, bot_l, 1.0 - fbottom).tolist()]


def _intersect(top: np.ndarray, side: np.ndarray) -> Tuple[float, float]:
    """Intersect y = a*x + b with x = c*y + d."""
    a, b = float(top[0]), float(top[1])
    c, d = float(side[0]), float(side[1])
    denom = 1.0 - c * a
    if abs(denom) < 1e-9:
        raise SurfaceNotMeasurable("two fitted edges are parallel; no corner exists")
    x = (c * b + d) / denom
    return x, a * x + b


# ── box ─────────────────────────────────────────────────────────────────────

def _box_face(mask: np.ndarray, gray: np.ndarray, *, inset_x: float,
              inset_top: float, inset_bottom: float
              ) -> Dict[str, Any]:
    """Fit the visible front face of a box as four intersecting lines.

    A front-on box has one face: fit its four silhouette edges. A three-quarter
    box has two: find the strong interior vertical edge (the lighting step at
    the front/side corner), split the silhouette there, fit each face, and keep
    the larger one. The front face is the larger face in a product shot; if the
    side is larger, the larger face is still the one worth labelling.
    """
    h, w = mask.shape
    top, bottom = _row_band(mask)
    height = max(1, bottom - top)
    y0, y1 = top + int(height * 0.18), bottom - int(height * 0.18)

    # Interior edge: the strongest vertical gradient away from the silhouette.
    gx = np.abs(np.diff(gray, axis=1))
    body = gx[max(0, y0):max(1, y1), :]
    col = body.sum(axis=0) if body.size else np.zeros(max(1, w - 1))
    xs = np.flatnonzero(mask.any(axis=0))
    if xs.size < 16:
        raise SurfaceNotMeasurable("no box silhouette found")
    left_edge, right_edge = int(xs[0]), int(xs[-1])
    span = max(1, right_edge - left_edge)
    lo = left_edge + int(span * 0.12)
    hi = right_edge - int(span * 0.12)
    x_split = None
    interior = None
    if hi - lo > 8 and col.size:
        central = col[lo:hi]
        med = float(np.median(central)) if central.size else 0.0
        peak = float(central.max()) if central.size else 0.0
        if peak > max(3.5 * med, 1e-6) and peak > 0.01 * float(central.sum() or 1.0):
            x_split = lo + int(np.argmax(central))
            # Refine the interior edge per row: the corner is rarely vertical.
            peaks_y, peaks_x = [], []
            radius = max(4, int(span * 0.05))
            for y in range(y0, y1):
                row = gx[y]
                a, b = max(0, x_split - radius), min(row.size, x_split + radius)
                if b <= a:
                    continue
                j = a + int(np.argmax(row[a:b]))
                if row[j] > 0.20 * peak:
                    peaks_y.append(y)
                    peaks_x.append(j + 1)
            if len(peaks_y) >= 16:
                fit = _fit_robust(np.asarray(peaks_y, float), np.asarray(peaks_x, float))
                if fit is not None:
                    interior = fit[0]

    faces: List[Dict[str, Any]] = []
    splits = [("front-on", mask, None)]
    if x_split is not None:
        left_mask = mask.copy()
        left_mask[:, x_split:] = False
        right_mask = mask.copy()
        right_mask[:, :x_split] = False
        splits = [("left", left_mask, interior), ("right", right_mask, interior)]

    for name, part, inner in splits:
        ys, xcols = np.nonzero(part)
        if ys.size < 400:
            continue
        p_top, p_bottom = int(ys.min()), int(ys.max())
        p_left, p_right = int(xcols.min()), int(xcols.max())
        ph, pw = p_bottom - p_top, p_right - p_left
        if ph < 24 or pw < 24:
            continue
        # Exclude rounded corners from every edge fit.
        my, mx = int(ph * 0.10), int(pw * 0.10)
        cols = np.arange(p_left + mx, p_right - mx + 1)
        rows = np.arange(p_top + my, p_bottom - my + 1)
        if cols.size < 12 or rows.size < 12:
            continue
        tops, bottoms = _subpixel_col_edges(part)
        lefts, rights = pl._subpixel_row_edges(part)
        try:
            tcoef, tkeep, tres, tkind = _fit_edge(cols.astype(float), tops[cols])
            bcoef, bkeep, bres, bkind = _fit_edge(cols.astype(float), bottoms[cols])
            lcoef, lkeep, lres, lkind = _fit_edge(rows.astype(float), lefts[rows])
            if inner is not None:
                rcoef, rkeep, rres, rkind = inner, np.ones(rows.size, bool), 0.0, "interior"
            else:
                rcoef, rkeep, rres, rkind = _fit_edge(rows.astype(float), rights[rows])
        except SurfaceNotMeasurable:
            continue
        try:
            tl = _intersect(tcoef, lcoef)
            tr = _intersect(tcoef, rcoef)
            br = _intersect(bcoef, rcoef)
            bl = _intersect(bcoef, lcoef)
        except SurfaceNotMeasurable:
            continue
        quad = [tl, tr, br, bl]
        try:
            quad = _validate_quad(quad, w, h, min_area_share=0.02)
        except SurfaceNotMeasurable:
            continue
        area = abs((quad[1][0] - quad[0][0]) * (quad[2][1] - quad[0][1])
                   - (quad[2][0] - quad[0][0]) * (quad[1][1] - quad[0][1]))
        residual = float(np.mean([tres, bres, lres, rres]))
        faces.append({
            "name": name, "quad": quad, "area": area, "residual": residual,
            "fits": {"top": tkind, "bottom": bkind, "left": lkind, "right": rkind},
            "residual_by_side": {"top": round(tres, 3), "bottom": round(bres, 3),
                                 "left": round(lres, 3), "right": round(rres, 3)},
            "face": {"top": p_top, "bottom": p_bottom, "left": p_left, "right": p_right},
        })

    if not faces:
        raise SurfaceNotMeasurable("no box face could be fitted from the silhouette")
    face = max(faces, key=lambda f: f["area"])
    silhouette_area = float(mask.sum())
    share = face["area"] / max(1.0, silhouette_area)
    if share < MIN_FACE_SHARE:
        raise SurfaceNotMeasurable(
            f"the fitted box face is only {share:.0%} of the silhouette")
    inset = _inset_quad(face["quad"], fx=inset_x, ftop=inset_top, fbottom=inset_bottom)
    quad = _validate_quad(inset, w, h, min_area_share=0.01)
    warnings = []
    if face["name"] == "front-on":
        warnings.append("no interior corner detected; assumed a front-on face")
    if share < 0.55:
        warnings.append(f"the labelled face is {share:.0%} of the silhouette")
    return {
        "quad": quad,
        "face": face["face"],
        "geom_residual_px": round(face["residual"], 3),
        "geom_residual_by_side": face["residual_by_side"],
        "fit": face["fits"],
        "method": "box-quad" if face["name"] != "front-on" else "box-front",
        "face_share": round(float(share), 4),
        "interior_edge_px": x_split,
        "warnings": warnings,
    }


# ── bottle / tube ───────────────────────────────────────────────────────────

def _horizontal_seams(gray: np.ndarray, mask: np.ndarray,
                      band_top: int, band_bottom: int
                      ) -> Tuple[Optional[int], Optional[int]]:
    """Strong horizontal seams near the ends of a cylinder band.

    A cap or a crimp can have almost the same diameter as the body, so width
    alone cannot find the boundary. The seam is still a horizontal luminance
    step, and it is exactly what must stop the label. Only the outer quarter of
    the band is searched, so a mid-body crease cannot split the printable area.
    """
    height = band_bottom - band_top
    if height < 32:
        return None, None
    gy = np.abs(np.diff(gray, axis=0))
    mid = band_top + height // 2
    xs = np.flatnonzero(mask[mid])
    if xs.size < 20:
        return None, None
    lo = int(xs[0] + 0.20 * (xs[-1] - xs[0]))
    hi = int(xs[-1] - 0.20 * (xs[-1] - xs[0]))
    if hi - lo < 12:
        return None, None
    prof = gy[:, lo:hi].sum(axis=1)
    quarter = max(8, int(height * 0.25))

    def _peak(a: int, b: int) -> Optional[int]:
        a, b = max(0, a), min(prof.size, b)
        if b - a < 8:
            return None
        seg = prof[a:b]
        med = float(np.median(seg))
        peak = float(seg.max())
        if peak < max(4.0 * med, 0.03 * float(seg.sum() or 1.0)):
            return None
        row = a + int(np.argmax(seg))
        # A seam is a line, not a gradual ramp: require separation from the rest.
        rest = np.delete(seg, np.arange(max(0, row - a - 3),
                                        min(seg.size, row - a + 4)))
        if rest.size and peak < 2.0 * float(np.median(rest)):
            return None
        return row

    top = _peak(band_top, band_top + quarter)
    bottom = _peak(band_bottom - quarter, band_bottom)
    return top, bottom


def _cylinder_band(mask: np.ndarray, gray: np.ndarray, kind: str, *, wrap_fraction: float,
                   inset_top: float, inset_bottom: float,
                   band_tol: float = 0.035) -> Dict[str, Any]:
    """Find the longest near-constant-width band of a bottle/tube silhouette.

    A bottle's cap and shoulder change width; a tube's crimps do. The body is
    the one long run where width is stable, so it is the only band a label can
    occupy without climbing onto a shoulder or a seal.
    """
    h, w = mask.shape
    top, bottom = _row_band(mask)
    height = max(1, bottom - top)
    left, right = pl._subpixel_row_edges(mask)
    valid = np.isfinite(left) & np.isfinite(right)
    width = np.where(valid, right - left, np.nan)
    smooth = _median_filter(width, 5)

    central_lo = top + int(height * 0.35)
    central_hi = top + int(height * 0.65)
    central = smooth[central_lo:central_hi]
    central = central[np.isfinite(central)]
    if central.size < 8:
        raise SurfaceNotMeasurable("no cylindrical body found in the silhouette")
    median_w = float(np.median(central))
    if median_w < 8:
        raise SurfaceNotMeasurable("the product silhouette is too narrow to label")
    widest = float(np.nanpercentile(width[valid], 95)) if valid.any() else 0.0
    if widest > 0 and median_w < 0.55 * widest:
        raise SurfaceNotMeasurable(
            f"the cylindrical band is only {median_w / widest:.0%} of the widest "
            "silhouette row; the mask likely missed the body")

    # A bottle's body is near-constant width; a tube's body is a linear taper.
    # Both are measured against their own model, never against a fixed box.
    stable = np.zeros_like(valid)
    rows_all = np.arange(top, bottom + 1)
    tol = band_tol if kind == "bottle" else min(band_tol, 0.025)
    if kind == "bottle":
        stable = valid & (np.abs(smooth - median_w) <= tol * median_w)
    else:
        trend = _fit_robust(rows_all.astype(float), smooth[rows_all], degree=1,
                            tol=max(2.0, tol * median_w))
        if trend is not None:
            predicted = np.polyval(trend[0], np.arange(h, dtype=float))
            stable = valid & (np.abs(smooth - predicted) <= tol * median_w)
        else:
            stable = valid & (np.abs(smooth - median_w) <= tol * median_w)
    run_start, run_end = _longest_run(stable)
    if run_start < 0 or (run_end - run_start + 1) < max(24, int(height * MIN_BAND_SHARE)):
        # Fallback: cut at the strongest width discontinuities and take the
        # longest surviving run. A very noisy render lands here.
        jump = np.abs(np.diff(smooth)) > max(2.0, 0.03 * median_w)
        cuts = [top - 1] + [int(i) + 1 for i in np.flatnonzero(jump)
                            if top < int(i) + 1 <= bottom] + [bottom + 1]
        best = (-1, -1)
        for i in range(len(cuts) - 1):
            s, e = cuts[i] + 1, cuts[i + 1] - 1
            if e - s > best[1] - best[0]:
                best = (s, e)
        run_start, run_end = best
    if run_start < 0 or (run_end - run_start + 1) < max(24, int(height * MIN_BAND_SHARE)):
        raise SurfaceNotMeasurable("no stable cylindrical band long enough to label")

    # A cap or a crimp can sit inside the stable width run when its diameter is
    # close to the body's. A width STEP is still a step: split the run there and
    # keep the longer side, so the label cannot climb onto the cap.
    raw_diff = np.abs(np.diff(width))
    step = np.nan_to_num(raw_diff, nan=0.0)
    inner = [int(j) for j in np.flatnonzero(step > max(2.0, 0.02 * median_w))
             if run_start + 8 < int(j) < run_end - 8]
    if inner:
        cut = max(inner, key=lambda j: float(step[j]))
        left, right = (run_start, cut - 1), (cut, run_end)
        run_start, run_end = max((left, right), key=lambda s: s[1] - s[0])

    if kind == "tube":
        # A tube's cap can share the body's diameter; a bottle's base is part of
        # the printable body, so only tubes get the horizontal-seam trim.
        seam_top, seam_bottom = _horizontal_seams(gray, mask, run_start, run_end)
        if seam_top is not None and seam_top + 8 < run_end:
            run_start = seam_top + 2
        if seam_bottom is not None and seam_bottom - 8 > run_start:
            run_end = seam_bottom - 2

    rows = np.arange(run_start, run_end + 1)
    lfit = _fit_robust(rows.astype(float), left[rows], degree=1)
    rfit = _fit_robust(rows.astype(float), right[rows], degree=1)
    if lfit is None or rfit is None:
        raise SurfaceNotMeasurable("the cylindrical sides are not straight enough to fit")
    lcoef, lres = lfit[0], lfit[2]
    rcoef, rres = rfit[0], rfit[2]
    residual = float(np.mean([lres, rres]))
    fit_kind = "linear"
    if residual > MAX_GEOM_RESIDUAL_PX:
        lfit2 = _fit_robust(rows.astype(float), left[rows], degree=2)
        rfit2 = _fit_robust(rows.astype(float), right[rows], degree=2)
        if lfit2 is not None and rfit2 is not None:
            cand = float(np.mean([lfit2[2], rfit2[2]]))
            if cand < residual:
                lcoef, rcoef = lfit2[0], rfit2[0]
                residual, fit_kind = cand, "quadratic"

    band_h = max(1, run_end - run_start)
    yt = run_start + int(band_h * inset_top)
    yb = run_end - int(band_h * inset_bottom)
    xl_t, xr_t = float(np.polyval(lcoef, yt)), float(np.polyval(rcoef, yt))
    xl_b, xr_b = float(np.polyval(lcoef, yb)), float(np.polyval(rcoef, yb))
    w_t, w_b = xr_t - xl_t, xr_b - xl_b
    if w_t < 8 or w_b < 8:
        raise SurfaceNotMeasurable("the measured label band collapses to nothing")

    # The visible silhouette is the diameter; a printed label must not reach the
    # edge-on surface. wrap_fraction is the share of the diameter the label spans.
    cx_t, cx_b = (xl_t + xr_t) / 2.0, (xl_b + xr_b) / 2.0
    half_t, half_b = (w_t * wrap_fraction) / 2.0, (w_b * wrap_fraction) / 2.0
    quad = _validate_quad(
        [[cx_t - half_t, yt], [cx_t + half_t, yt],
         [cx_b + half_b, yb], [cx_b - half_b, yb]], w, h, min_area_share=0.01)

    taper = 1.0 - (w_t / max(1.0, w_b))
    if kind == "bottle" and abs(taper) > 0.12:
        raise SurfaceNotMeasurable(
            f"the bottle body tapers {taper:.0%}; that is a shoulder, not a label band")
    if kind == "tube" and not (-MAX_CYLINDER_TAPER <= taper <= MAX_CYLINDER_TAPER):
        raise SurfaceNotMeasurable(
            f"the tube taper {taper:.0%} is outside the printable range")

    # Crimp / shoulder boundaries: the sealed zone is the distance from the
    # silhouette end to the printable band, measured rather than assumed. The
    # raw width (not the median-filtered one) carries the step.
    raw_diff = np.abs(np.diff(width))
    jumps = np.flatnonzero(np.nan_to_num(raw_diff, nan=0.0)
                           > max(2.0, 0.02 * median_w))
    above = jumps[jumps < run_start]
    below = jumps[jumps > run_end]
    crimp_top = int(run_start - top) if above.size else None
    crimp_bottom = int(bottom - run_end) if below.size else None

    # Convexity of the band: a cylinder projects to a convex trapezoid.
    try:
        import cv2
        band_mask = (mask[run_start:run_end + 1].astype(np.uint8) * 255)
        cnts, _ = cv2.findContours(band_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            cnt = max(cnts, key=cv2.contourArea)
            area = float(cv2.contourArea(cnt))
            hull = float(cv2.contourArea(cv2.convexHull(cnt)))
            convexity = area / hull if hull > 0 else 0.0
        else:
            convexity = 0.0
    except Exception:  # noqa: BLE001 - convexity is evidence, not a requirement
        convexity = None

    warnings = []
    if residual > MAX_GEOM_RESIDUAL_PX:
        raise SurfaceNotMeasurable(
            f"the cylindrical sides do not fit within {MAX_GEOM_RESIDUAL_PX:.1f} px "
            f"(measured {residual:.2f} px)")
    if convexity is not None and convexity < 0.90:
        warnings.append(f"band convexity {convexity:.2f} is low")
    if kind == "tube" and crimp_top is None and crimp_bottom is None:
        warnings.append("no crimp step detected; band bounded by the silhouette only")

    return {
        "quad": quad,
        "face": {"top": int(yt), "bottom": int(yb),
                 "left": int(round(min(xl_t, xl_b))),
                 "right": int(round(max(xr_t, xr_b)))},
        "geom_residual_px": round(residual, 3),
        "geom_residual_by_side": {"left": round(lres, 3), "right": round(rres, 3)},
        "fit": {"left": fit_kind, "right": fit_kind},
        "method": "bottle-band" if kind == "bottle" else "tube-band",
        "band": {"top": int(run_start), "bottom": int(run_end),
                 "height_px": int(run_end - run_start + 1)},
        "width_px": {"top": round(w_t, 2), "bottom": round(w_b, 2),
                     "median": round(median_w, 2)},
        "taper": round(float(taper), 4),
        "crimp_top_px": crimp_top,
        "crimp_bottom_px": crimp_bottom,
        "convexity": None if convexity is None else round(float(convexity), 3),
        "wrap_fraction": round(float(wrap_fraction), 4),
        "warnings": warnings,
    }


# ── public entry ────────────────────────────────────────────────────────────

def measure_surface(plate: Any, kind: str = "pouch", *,
                    threshold: float = 26.0,
                    max_residual: float = MAX_GEOM_RESIDUAL_PX,
                    inset_x: float = 0.06,
                    inset_top: float = 0.06,
                    inset_bottom: float = 0.06,
                    wrap_fraction: float = 0.92,
                    band_tol: float = 0.035) -> Dict[str, Any]:
    """Measure the printable surface of a rendered plate.

    `kind` is one of pouch, box, bottle, tube. The result is a dict with a
    TL/TR/BR/BL `quad`, the face bbox, the residual that gates it and the
    method that produced it. Raises `SurfaceNotMeasurable` when the plate does
    not support a safe fit; callers must block rather than guess.
    """
    img = _as_image(plate)
    fmt = str(kind or "").strip().lower()
    if fmt not in ("pouch", "box", "bottle", "tube"):
        raise KeyError(f"unknown packaging format {kind!r}; known: pouch, box, bottle, tube")
    if not 0.0 < float(wrap_fraction) <= 1.0:
        raise ValueError("wrap_fraction must be in (0, 1]")

    if fmt == "pouch":
        try:
            measured = pl.measure_face(img, inset_x=inset_x, inset_top=inset_top,
                                       inset_bottom=inset_bottom, threshold=threshold)
        except ValueError as exc:
            raise SurfaceNotMeasurable(str(exc)) from exc
        measured = dict(measured)
        measured.update({"kind": "pouch", "method": "pouch-measure_face",
                         "confidence": _confidence(measured.get("geom_residual_px"),
                                                   max_residual, 1.0),
                         "warnings": []})
        return measured

    mask = pl._foreground_mask(img, threshold=threshold)
    coverage = float(mask.sum()) / float(mask.shape[0] * mask.shape[1])
    if coverage < 0.02:
        raise SurfaceNotMeasurable(
            f"no product silhouette found: foreground covers {coverage:.1%} of the plate")
    # A low-contrast product (light grey on light grey) makes the colour mask
    # absorb the background; its bbox then touches the frame on most sides. A
    # product photographed "fully in frame" cannot legitimately do that, so this
    # is a segmentation failure, not a surface. Refuse rather than print on it.
    ys_m, xs_m = np.nonzero(mask)
    h_m, w_m = mask.shape
    sides = sum((int(xs_m.min()) <= 1, int(xs_m.max()) >= w_m - 2,
                 int(ys_m.min()) <= 1, int(ys_m.max()) >= h_m - 2))
    if sides >= 3:
        raise SurfaceNotMeasurable(
            "silhouette_touches_frame: the colour mask absorbed the background "
            "(low-contrast product). Use a plate whose product is visibly "
            "separated from the background.")
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    if fmt == "box":
        out = _box_face(mask, gray, inset_x=inset_x, inset_top=inset_top,
                        inset_bottom=inset_bottom)
        factor = 0.90 if out["method"] == "box-front" else 1.0
    else:
        out = _cylinder_band(mask, gray, fmt, wrap_fraction=wrap_fraction,
                             inset_top=inset_top, inset_bottom=inset_bottom,
                             band_tol=band_tol)
        factor = 0.95 if out.get("convexity") is None else 1.0
    residual = out.get("geom_residual_px")
    if residual is not None and float(residual) > float(max_residual):
        raise SurfaceNotMeasurable(
            f"the measured surface residual {float(residual):.2f} px exceeds "
            f"{float(max_residual):.1f} px")
    out = dict(out)
    out.update({
        "kind": fmt,
        "background": list(pl._background_colour(img)),
        "coverage": round(coverage, 4),
        "confidence": _confidence(residual, max_residual, factor),
        "plate_size": [int(img.width), int(img.height)],
    })
    return out


def _confidence(residual: Optional[float], max_residual: float, factor: float) -> float:
    if residual is None:
        return round(_clamp01(0.5 * factor), 3)
    return round(_clamp01((1.0 - float(residual) / (2.0 * max_residual)) * factor), 3)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Measure a packaging surface in a plate.")
    ap.add_argument("--plate", required=True, help="plate PNG path")
    ap.add_argument("--kind", default="pouch", choices=["pouch", "box", "bottle", "tube"])
    ap.add_argument("--wrap-fraction", type=float, default=0.92)
    ap.add_argument("--json", action="store_true", help="emit the full measurement")
    args = ap.parse_args(argv)
    try:
        measured = measure_surface(args.plate, args.kind, wrap_fraction=args.wrap_fraction)
    except (SurfaceNotMeasurable, KeyError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    if args.json:
        print(json.dumps({"ok": True, "measurement": measured}, indent=2))
    else:
        print(f"{args.kind}: quad={measured['quad']} residual="
              f"{measured.get('geom_residual_px')} px confidence={measured['confidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["measure_surface", "SurfaceNotMeasurable", "MAX_GEOM_RESIDUAL_PX"]
