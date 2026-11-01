"""Pouch label lane — put the operator's logo + copy ON a rendered pouch.

Why this exists (2026-10-23): the image model is forbidden from painting text,
logos or legal copy, so a `generate_image` of a stand-up pouch correctly comes
back as a blank bag. Until now the operator was told "that is by design" and had
to leave the chat to finish the label somewhere else — the render read as half a
deliverable. This module closes the loop with the SAME deterministic compositor
the Design Studio already uses: real logo pixels, real fonts, warped onto the
pouch face with a measured 4-point homography. Nothing here is generated, so
spelling and the logo are exact by construction.

The one thing the studio could not do for an arbitrary plate was GEOMETRY: its
presets carry hand-measured quads for one known plate. This lane measures the
face from the render itself:

  1. the background is the median colour of the image's outer ring;
  2. the pouch is the largest region that differs from it;
  3. the left/right edges are fitted per side, so a doypack's widening base
     becomes a trapezoid instead of a rectangle;
  4. the quad is inset so the print stops short of the weld/seal.

That is real measurement, not an invented number — and it is reported back with
the result so the operator can see what was fitted. It is a MOCKUP fit: good for
a product shot, never a substitute for the converter's die drawing.

Pure PIL + numpy. No provider call, no network, no cost.
"""

from __future__ import annotations

import io
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import mockup_compositor as mc

# ── palette defaults (overridable per call) ─────────────────────────────────

FIELD = (247, 243, 236)     # cream label stock
INK = (28, 46, 38)          # pine forest ink
ACCENT = (176, 141, 69)     # engraved gold

PANEL_SIZE = (900, 1200)

#: A gusset narrower than this cannot carry legible copy (lesson L5).
MIN_LEGIBLE_GUSSET_PX = 220

#: Mesh density for a measured face. 5x9 costs nothing, and the sine-bow fit
#: lands inside a fraction of a pixel on a real plate (REA L2).
MESH_NX = 5
MESH_NY = 9
#: A composite is refused when the measured edge and the mesh disagree by more
#: than this. Printing on a guessed quad is worse than stopping.
MAX_GEOM_RESIDUAL_PX = 1.5
#: Below this the bow is measurement noise; the homography stays in place.
MIN_BOW_PX = 0.25
#: RANSAC inlier band for the side-edge quadratic, in pixels.
EDGE_INLIER_PX = 0.75


# ── image helpers ───────────────────────────────────────────────────────────

def _background_colour(img: Image.Image) -> Tuple[int, int, int]:
    """Median colour of the outer 6% ring — the scene the pouch sits in."""
    rgb = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w = rgb.shape[:2]
    b = max(2, int(min(h, w) * 0.06))
    ring = np.concatenate([
        rgb[:b].reshape(-1, 3), rgb[-b:].reshape(-1, 3),
        rgb[:, :b].reshape(-1, 3), rgb[:, -b:].reshape(-1, 3),
    ])
    med = np.median(ring, axis=0)
    return tuple(int(c) for c in med)


def _foreground_mask(img: Image.Image, threshold: float = 26.0) -> np.ndarray:
    """Boolean mask of the POUCH, not of "everything unlike one colour".

    The original implementation compared every pixel to a single median taken
    from the outer ring. That is only correct for a one-backdrop scene. A real
    product plate has two or more (here: a grey wall plus a bright marble table),
    so the table and any prop were classified as "foreground", the silhouette
    grew to the whole frame, and the label was warped onto a quad that ran off
    the bottom of the bag onto the table. That is the T2 visual failure.

    The pouch is the tallest coloured object in a product plate, so:
      1. chroma (saturation) separates coloured stock from neutral scenery;
      2. morphology closes print grain and shadows;
      3. the component with the greatest HEIGHT wins - not the greatest area,
         so an olive sprig or a shadow that touches the bag cannot outvote it;
      4. interior holes are filled so the label area is solid.

    A low-chroma pack (an ivory or white stock on white seamless) yields nothing
    here, so the colour-distance method remains as the fallback. Both paths are
    deterministic; nothing is guessed.
    """
    rgb = np.asarray(img.convert("RGB"))
    h, w = rgb.shape[:2]
    try:
        import cv2
    except Exception:  # noqa: BLE001 - fall back to pure numpy
        cv2 = None

    if cv2 is not None:
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        cand = ((sat > 40) & (val > 25)).astype(np.uint8)
        if int(cand.sum()) >= int(h * w * 0.03):
            k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
            k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            m = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, k_close)
            m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k_open)
            n, labels, stats, _ = cv2.connectedComponentsWithStats(m, 8)
            best, best_h = 0, 0
            for i in range(1, n):
                area = stats[i, cv2.CC_STAT_AREA]
                height = stats[i, cv2.CC_STAT_HEIGHT]
                if area < h * w * 0.02:
                    continue
                if height > best_h:          # tallest, not widest: props lose
                    best, best_h = i, height
            if best and best_h >= h * 0.35:
                m = (labels == best).astype(np.uint8)
                # fill interior holes (print detail punched through the mask)
                ff = m.copy()
                flood = np.zeros((h + 2, w + 2), np.uint8)
                cv2.floodFill(ff, flood, (0, 0), 1)
                filled = (m.astype(bool) | (ff == 0))

                # Trim thin appendages. A prop that touches the bag (here an
                # olive sprig) joins the component and flares the measured face
                # out to the frame edge, which drags the label quad sideways and
                # below the pouch base. The bag is a solid block: keep only the
                # longest contiguous band of columns (and of rows) that carry a
                # real share of the mask. Deterministic, and it cannot invent
                # pixels - it only subtracts.
                def _longest_run(counts: np.ndarray, share: float) -> Tuple[int, int]:
                    peak = float(counts.max()) if counts.size else 0.0
                    if peak <= 0:
                        return 0, len(counts) - 1
                    keep = counts >= peak * share
                    best_s, best_len, s = 0, 0, None
                    for i, k in enumerate(keep):
                        if k and s is None:
                            s = i
                        elif not k and s is not None:
                            if i - s > best_len:
                                best_s, best_len = s, i - s
                            s = None
                    if s is not None and len(keep) - s > best_len:
                        best_s, best_len = s, len(keep) - s
                    return best_s, max(best_s, best_s + best_len - 1)

                col_counts = filled.sum(axis=0)
                c0, c1 = _longest_run(col_counts, 0.35)
                row_counts = filled.sum(axis=1)
                r0, r1 = _longest_run(row_counts, 0.35)
                trimmed = np.zeros_like(filled)
                trimmed[r0:r1 + 1, c0:c1 + 1] = filled[r0:r1 + 1, c0:c1 + 1]
                if trimmed.sum() >= filled.sum() * 0.5:
                    return trimmed
                return filled

    # Fallback: the original colour-distance method, still fail-closed.
    rgbf = rgb.astype(np.float32)
    bg = np.array(_background_colour(img), dtype=np.float32)
    dist = np.max(np.abs(rgbf - bg), axis=2)
    mask = dist > threshold
    blurred = np.asarray(
        Image.fromarray((mask * 255).astype("uint8")).filter(ImageFilter.BoxBlur(2))
    ).astype(np.float32)
    return blurred > 110


def _row_extents(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Per-row (left, right, width) of the mask; NaN where the row is empty."""
    h, w = mask.shape
    left = np.full(h, np.nan)
    right = np.full(h, np.nan)
    for y in range(h):
        xs = np.flatnonzero(mask[y])
        if xs.size:
            left[y] = xs[0]
            right[y] = xs[-1]
    width = right - left
    return left, right, width


def _fit_line(y: np.ndarray, x: np.ndarray) -> Tuple[float, float]:
    """Least-squares x = a*y + b over the rows that actually had a mask."""
    ok = np.isfinite(x)
    if ok.sum() < 8:
        raise ValueError("the pouch face could not be measured (no foreground)")
    a, b = np.polyfit(y[ok], x[ok], 1)
    return float(a), float(b)


def _subpixel_row_edges(mask: np.ndarray, blur_radius: int = 2
                        ) -> Tuple[np.ndarray, np.ndarray]:
    """Per-row edge positions to sub-pixel precision.

    The mask is binary, so its 0.5 level set is interpolated on a slightly
    blurred copy. A hard threshold can only return an integer column; the
    interpolated crossing is what the mesh fit needs, because half a pixel is
    the difference between a print that sits on the pack and one that floats.
    """
    soft = np.asarray(
        Image.fromarray((mask.astype(np.uint8) * 255)).filter(
            ImageFilter.BoxBlur(blur_radius))
    ).astype(np.float32) / 255.0
    h, w = soft.shape
    left = np.full(h, np.nan)
    right = np.full(h, np.nan)
    for y in range(h):
        row = soft[y]
        inside = np.flatnonzero(row >= 0.5)
        if inside.size < 2:
            continue
        l, r = int(inside[0]), int(inside[-1])
        if l > 0 and row[l] != row[l - 1]:
            left[y] = (l - 1) + (0.5 - row[l - 1]) / (row[l] - row[l - 1])
        if r < w - 1 and row[r] != row[r + 1]:
            right[y] = r + (row[r] - 0.5) / (row[r] - row[r + 1])
    return left, right


def _ransac_quadratic(y: np.ndarray, x: np.ndarray, *, tol: float = EDGE_INLIER_PX,
                      iters: int = 400, seed: int = 7
                      ) -> Optional[Tuple[np.ndarray, np.ndarray, float]]:
    """Robust quadratic x(y) for one side of a pouch.

    A lifestyle plate puts a prop, a shadow or a second pack within a few pixels
    of the true edge. Iterative least squares follows that contamination because
    it is smooth; RANSAC finds the edge that most rows actually agree on. The
    returned tuple is (coeffs, inlier mask, mean absolute inlier residual).
    """
    ok = np.isfinite(x)
    yy, xx = y[ok].astype(float), x[ok].astype(float)
    if yy.size < 16:
        return None
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(int(iters)):
        idx = rng.choice(yy.size, 3, replace=False)
        if float(np.ptp(yy[idx])) < 8.0:
            continue
        c = np.polyfit(yy[idx], xx[idx], 2)
        n = int((np.abs(xx - np.polyval(c, yy)) < tol).sum())
        if best is None or n > best[0]:
            best = (n, c)
    if best is None or best[0] < 16:
        return None
    c = best[1]
    keep = np.ones_like(xx, dtype=bool)
    for _ in range(3):
        res = np.abs(xx - np.polyval(c, yy))
        keep = res < tol
        if keep.sum() < 16:
            return None
        c = np.polyfit(yy[keep], xx[keep], 2)
    res = xx - np.polyval(c, yy)
    keep = np.abs(res) < tol
    if keep.sum() < 16:
        return None
    return c, keep, float(np.mean(np.abs(res[keep])))


def _panel_residual(grid: np.ndarray, left: np.ndarray, right: np.ndarray,
                    yt: float, yb: float, pad_t: float, pad_b: float,
                    inliers: Optional[Dict[str, np.ndarray]] = None
                    ) -> Tuple[Optional[float], Dict[str, float]]:
    """Mean distance (px) between the fitted panel edges and the mesh boundary.

    Only the rows the side fit trusted are compared. A prop or a shadow touching
    the pack is rejected by the RANSAC fit; including it here would report the
    prop's distance as if it were geometry error.
    """
    ys = np.arange(int(np.ceil(yt)), int(np.floor(yb)) + 1)
    if ys.size < 8:
        return None, {}
    gy = np.asarray(grid[:, 0, 1], dtype=float)
    gx_l = np.asarray(grid[:, 0, 0], dtype=float)
    gx_r = np.asarray(grid[:, -1, 0], dtype=float)
    order = np.argsort(gy)
    if order.size < 2:
        return None, {}
    gy, gx_l, gx_r = gy[order], gx_l[order], gx_r[order]
    out: Dict[str, float] = {}
    all_res = []
    for name, xs, sign in (("left", left, +1.0), ("right", right, -1.0)):
        rows = ys if inliers is None else np.intersect1d(ys, inliers[name])
        rows = rows.astype(int)
        ok = np.isfinite(xs[rows])
        rows = rows[ok]
        if rows.size < 8:
            continue
        t = (rows.astype(float) - yt) / max(1e-6, (yb - yt))
        pad = pad_t + (pad_b - pad_t) * t
        meas = xs[rows] + sign * pad
        pred = np.interp(rows.astype(float), gy, gx_l if name == "left" else gx_r)
        res = meas - pred
        out[name] = round(float(np.mean(np.abs(res))), 3)
        all_res.append(np.abs(res))
    if not all_res:
        return None, out
    return round(float(np.mean(np.concatenate(all_res))), 3), out


def _bow_coeff(coeffs: np.ndarray, yt: float, yb: float) -> float:
    """Sine coefficient of the edge's departure from its own chord.

    The chord is the straight line between the two panel corners. A real pouch
    leaves it at mid-height; `sin(pi t)` is the shape the compositor's mesh
    moves, so the coefficient is measured in that basis rather than at one row
    where a crease could bias it.
    """
    ys = np.linspace(float(yt), float(yb), 64)
    t = (ys - yt) / max(1e-6, (yb - yt))
    chord = float(np.polyval(coeffs, yt)) + (
        float(np.polyval(coeffs, yb)) - float(np.polyval(coeffs, yt))) * t
    dep = np.polyval(coeffs, ys) - chord
    basis = np.sin(np.pi * t)
    denom = float((basis * basis).sum())
    return float((dep * basis).sum() / denom) if denom > 1e-9 else 0.0


def measure_face(img: Image.Image, *, inset_x: float = 0.075,
                 inset_top: float = 0.20, inset_bottom: float = 0.10,
                 threshold: float = 26.0) -> Dict[str, Any]:
    """Measure the PRINTED FRONT PANEL of a pouch render.

    Returns {quad, face, background, coverage, geom_residual_px, bow_x_px}
    where quad is [TL, TR, BR, BL] in pixel coordinates and face is the
    measured bbox.

    The insets are not cosmetic. A stand-up pouch has a top weld / zipper header
    and a bottom gusset that are NOT printable label area, so a label warped to
    the raw silhouette covers the zipper and runs past the base - which is what
    the first T2 output did. 0.20 top / 0.10 bottom lands the panel under the
    zipper and above the base curve on a standard 6 oz pouch. Override per plate
    when a different stock dictates otherwise.

    The sides are fitted with a robust quadratic (not a straight line), because
    a real pouch bows outward at mid-height. The fit yields a bow measurement
    the compositor turns into a mesh, plus a residual: when the measured edge
    and the mesh disagree by more than MAX_GEOM_RESIDUAL_PX the caller refuses
    rather than printing on a guess.
    """
    mask = _foreground_mask(img, threshold=threshold)
    h, w = mask.shape
    coverage = mask.sum(axis=1) / float(w)
    rows = np.flatnonzero(coverage >= 0.06)
    if rows.size < 16:
        raise ValueError("no pouch face found: the render is nearly all background")
    top = int(rows[0])
    bottom = int(rows[-1])

    # Ignore the extreme top/bottom bands when fitting the side edges: the top
    # weld tapers in and the base shadow flares out, so a fit through them would
    # tilt the label. Fit the body, then extrapolate to the face bounds.
    body_top = top + int((bottom - top) * 0.14)
    body_bottom = top + int((bottom - top) * 0.86)
    body = np.arange(max(body_top, top + 1), max(body_bottom, body_top + 2))
    left, right = _subpixel_row_edges(mask)

    fits: Dict[str, Tuple[np.ndarray, str]] = {}
    residuals: Dict[str, Optional[float]] = {}
    inlier_rows: Dict[str, np.ndarray] = {}
    for name, xs in (("left", left), ("right", right)):
        fit = _ransac_quadratic(body.astype(float), xs[body])
        if fit is not None:
            fits[name] = (fit[0], "quadratic")
            residuals[name] = round(fit[2], 3)
            inlier_rows[name] = body[fit[1]]
        else:
            a, b = _fit_line(body.astype(float), xs[body])
            fits[name] = (np.array([0.0, a, b]), "linear")
            residuals[name] = None
            inlier_rows[name] = body

    lf = fits["left"][0]
    rf = fits["right"][0]

    yt = top + int((bottom - top) * inset_top)
    yb = bottom - int((bottom - top) * inset_bottom)
    xt_l, xt_r = float(np.polyval(lf, yt)), float(np.polyval(rf, yt))
    xb_l, xb_r = float(np.polyval(lf, yb)), float(np.polyval(rf, yb))
    pad_t = (xt_r - xt_l) * inset_x
    pad_b = (xb_r - xb_l) * inset_x

    # A render whose pouch fills the frame measured a face equal to the whole
    # silhouette, so a 3.5% inset let the label cover the pack edge to edge and
    # the pouch stopped reading as a pouch. Never let the printed panel exceed
    # this share of the measured face, whatever the inset asks for.
    max_share = 0.86
    ft, fb = (xt_r - xt_l), (xb_r - xb_l)
    pad_t = max(pad_t, ft * (1 - max_share) / 2)
    pad_b = max(pad_b, fb * (1 - max_share) / 2)

    quad = [
        [round(xt_l + pad_t, 1), float(yt)],
        [round(xt_r - pad_t, 1), float(yt)],
        [round(xb_r - pad_b, 1), float(yb)],
        [round(xb_l + pad_b, 1), float(yb)],
    ]

    # The bow is the sine-fit departure from each side's own chord. Left bows
    # outward in -x, right in +x, so the left coefficient is negated.
    bow_l = -_bow_coeff(lf, yt, yb)
    bow_r = _bow_coeff(rf, yt, yb)
    bow = (bow_l + bow_r) / 2.0

    mesh = mc.mesh_grid(quad, nx=MESH_NX, ny=MESH_NY, bow_x=(bow_l, bow_r))
    geom_residual, by_side = _panel_residual(
        mesh, left, right, yt, yb, pad_t, pad_b, inlier_rows)
    return {
        "quad": quad,
        "face": {"top": top, "bottom": bottom,
                 "left": int(np.nanmin(left[top:bottom + 1])),
                 "right": int(np.nanmax(right[top:bottom + 1]))},
        "background": list(_background_colour(img)),
        "coverage": round(float(mask.sum()) / float(h * w), 4),
        "geom_residual_px": geom_residual,
        "geom_residual_by_side": by_side,
        "bow_x_px": round(float(bow), 3),
        "bow_left_px": round(float(bow_l), 3),
        "bow_right_px": round(float(bow_r), 3),
        "fit": {name: fits[name][1] for name in fits},
        "fit_residual_px": residuals,
    }


# ── logo handling ───────────────────────────────────────────────────────────

def load_logo(path: Path, *, key_threshold: float = 232.0) -> Image.Image:
    """Open a logo as RGBA, keying a flat light background to transparent.

    Operator logos arrive either as a transparent PNG or as artwork sitting on a
    white/cream field. Both must place cleanly on the label, so a light, nearly
    neutral field is keyed out (cream and off-white included, since a cream
    plaque would otherwise sit as a grey square on cream stock) and the result is
    trimmed to its content.
    """
    raw = Image.open(path).convert("RGBA")
    arr = np.asarray(raw).astype(np.int16)
    alpha = arr[..., 3]

    # If the file already carries meaningful transparency, trust it.
    if (alpha < 250).mean() > 0.02:
        out = raw
    else:
        rgb = arr[..., :3]
        mn = rgb.min(axis=2)
        chroma = rgb.max(axis=2) - mn
        # light AND near-neutral == paper. Ink stays opaque because it is either
        # darker than the threshold or carries real colour.
        paper = (mn > key_threshold) & (chroma < 30)
        soft = np.where(paper, np.clip((255 - mn) * 9.0, 0, 255), 255)
        out = arr.copy()
        out[..., 3] = np.minimum(alpha, soft.astype(np.int16))
        out = Image.fromarray(out.astype("uint8"), "RGBA")

    box = out.split()[3].getbbox()
    return out.crop(box) if box else out


def _fitted_font(name: str, size: int, axes, text: str, max_w: float,
                 d: ImageDraw.ImageDraw):
    return mc.fit_font(name, size, axes, text, max_w, d)


def _tracked(d: ImageDraw.ImageDraw, cx: float, y: float, text: str, font,
             fill, tracking: float = 0.0) -> None:
    mc.centered(d, cx, y, text, font, fill, tracking=tracking)


# ── label panel ─────────────────────────────────────────────────────────────

def render_label(*, size: Sequence[int] = PANEL_SIZE, title: str, subtitle: str = "",
                 weight: str = "", bullets: Optional[Sequence[str]] = None,
                 logo: Optional[Image.Image] = None,
                 icons: Optional[Sequence[str]] = None,
                 field: Sequence[int] = FIELD, ink: Sequence[int] = INK,
                 accent: Sequence[int] = ACCENT,
                 field_alpha: int = 250) -> Image.Image:
    """Render the flat label. Text is drawn, never generated."""
    W, H = int(size[0]), int(size[1])
    panel = Image.new("RGBA", (W, H), tuple(field) + (field_alpha,))
    d = ImageDraw.Draw(panel)
    ink_c = tuple(ink) + (255,)
    acc_c = tuple(accent) + (255,)

    # hairline frame — reads as a printed keyline once warped
    m = int(W * 0.055)
    d.rectangle([m, m, W - m, H - m], outline=acc_c, width=max(2, W // 300))

    y = int(H * 0.10)
    if logo is not None:
        lw = int(W * 0.46)
        lh = max(1, int(lw * logo.height / max(1, logo.width)))
        if lh > H * 0.22:                       # keep a tall mark from eating the panel
            lh = int(H * 0.22)
            lw = max(1, int(lh * logo.width / max(1, logo.height)))
        lock = logo.resize((lw, lh), Image.LANCZOS)
        panel.paste(lock, ((W - lw) // 2, y), lock)
        y += lh + int(H * 0.055)
    else:
        y += int(H * 0.04)

    # product name
    f_title = _fitted_font("PlayfairDisplay.ttf", int(H * 0.085), [700],
                           title, W * 0.80, d)
    _tracked(d, W / 2, y, title, f_title, ink_c)
    y += int(H * 0.085)

    if subtitle:
        f_sub = mc.load_font("Inter.ttf", max(16, int(H * 0.030)), [14, 620])
        _tracked(d, W / 2, y, subtitle.upper(), f_sub, ink_c,
                 tracking=max(4.0, W * 0.010))
        y += int(H * 0.045)

    # rule
    d.line([(W / 2 - W * 0.16, y), (W / 2 + W * 0.16, y)], fill=acc_c,
           width=max(2, H // 400))
    y += int(H * 0.045)

    if bullets:
        f_b = mc.load_font("Inter.ttf", max(15, int(H * 0.026)), [14, 480])
        for line in list(bullets)[:5]:
            _tracked(d, W / 2, y, line, f_b, ink_c)
            y += int(H * 0.040)

    if icons:
        kinds = [k for k in icons if k in mc._ICON_SPECS][:5]
        if kinds:
            r = int(W * 0.035)
            gap = int(W * 0.115)
            iy = H - int(H * 0.20)
            for i, kind in enumerate(kinds):
                cx = W / 2 + (i - (len(kinds) - 1) / 2.0) * gap
                mc.draw_cert_icon(d, kind, cx, iy, r, ink=accent, ring=accent,
                                  disc=tuple(field), width=max(2, W // 400))

    if weight:
        f_w = mc.load_font("Inter.ttf", max(16, int(H * 0.028)), [14, 560])
        _tracked(d, W / 2, H - int(H * 0.11), weight, f_w, ink_c)
    return panel


# ── public entry ────────────────────────────────────────────────────────────

def _side_for(*, title: str, subtitle: str, weight: str,
              claims: Optional[Sequence[str]], icons: Optional[Sequence[str]],
              field: Optional[Sequence[int]]) -> Optional[Image.Image]:
    """Render the gusset artwork (lesson L4). None means 'fall back to field'."""
    try:
        from specialists import panels as pnl
        return pnl.render_side_panel(
            title=title, subtitle=subtitle, weight=weight,
            claims=list(claims or [])[:4], icons=list(icons or [])[:3],
            field=tuple(field) if field else FIELD, ink=INK, accent=ACCENT)
    except Exception:  # noqa: BLE001 - a missing side panel must not break the mockup
        return None


def _wrap_panel(panel: Image.Image, surfaces: Sequence[Dict[str, Any]],
                field: Sequence[int] = FIELD,
                side_panel: Optional[Image.Image] = None) -> Image.Image:
    """Compose [gusset][front][gusset] into one artwork wider than the label.

    A gusset carries the SIDE PANEL when one is supplied (weight, claims, cert
    marks) — that is lesson L4 from the real build. Without it, the strip falls
    back to shaded field colour so the pack still reads.
    """
    front = panel
    H = front.height
    total_w = 0
    widths: List[tuple] = []
    front_share = _front_share(surfaces)
    for part in surfaces:
        if part["surface"] == "front":
            widths.append((part, front.width))
        else:
            widths.append((part, max(10, int(front.width * part["share"] / max(1e-6, front_share)))))
        total_w += widths[-1][1]
    canvas = Image.new("RGBA", (max(1, total_w), H), tuple(field) + (250,))
    for part, w in widths:
        x = sum(width for _p, width in widths[:widths.index((part, w))])
        if part["surface"] == "front":
            canvas.paste(front, (x, 0), front)
            continue
        strip = _gusset_strip(w, H, side_panel, part["surface"], field)
        canvas.paste(strip, (x, 0), strip)
    return canvas


def _gusset_strip(width: int, height: int, side_panel: Optional[Image.Image],
                  surface: str, field: Sequence[int]) -> Image.Image:
    """One gusset column.

    L5 (learned by building): a gusset that is only ~19 % of the face is ~130 px
    wide — side-panel copy cannot be legible there, and cropping a 420 px side
    panel into a 130 px column sliced the words ("Lio…", "…ne", "NET", "D g)").
    So side artwork is used ONLY when the strip is wide enough to hold it;
    otherwise the gusset is shaded field colour, which is what the first good
    build did.
    """
    if side_panel is not None and width >= MIN_LEGIBLE_GUSSET_PX:
        # fit the WHOLE side panel into the strip, never a crop
        scale = width / max(1, side_panel.width)
        fitted = side_panel.resize((width, max(1, int(side_panel.height * scale))),
                                   Image.LANCZOS)
        canvas = Image.new("RGBA", (width, height), tuple(field) + (250,))
        canvas.paste(fitted, (0, max(0, (height - fitted.height) // 2)), fitted)
        return canvas
    strip = Image.new("RGBA", (width, height), tuple(field) + (250,))
    d = ImageDraw.Draw(strip)
    for col in range(width):
        t = col / max(1, width - 1)
        shade = 0.90 + 0.10 * (1.0 - t if surface == "gusset_left" else t)
        colour = tuple(int(min(255, c * shade)) for c in field)
        d.line([(col, 0), (col, height)], fill=colour + (255,))
    return strip


def _front_share(surfaces: Sequence[Dict[str, Any]]) -> float:
    for part in surfaces:
        if part["surface"] == "front":
            return float(part["share"])
    return 1.0


def _panel_slice(panel: Image.Image, surface: str,
                 field: Sequence[int] = FIELD) -> Image.Image:
    """Artwork for one visible surface.

    The front gets the whole label. A gusset gets a plain field-coloured strip
    with a darker outer edge, because a real gusset carries its own panel — not a
    squeezed copy of the front. Slicing the front's edge here made the subtitle
    bleed off both sides and turned the keyline into a pair of vertical flaps.
    """
    if surface == "front":
        return panel
    W, H = panel.size
    strip = Image.new("RGBA", (max(8, int(W * 0.18)), H), tuple(field) + (250,))
    d = ImageDraw.Draw(strip)
    w = strip.width
    # outer edge shading so the side of the pack reads as turned away
    for x in range(w):
        t = x / max(1, w - 1)
        shade = 0.90 + 0.10 * (t if surface == "gusset_left" else 1.0 - t)
        col = tuple(int(min(255, c * shade)) for c in field)
        d.line([(x, 0), (x, H)], fill=col + (255,))
    return strip


PLATE_GEOMETRY_PATH = Path(__file__).resolve().parent / "data" / "plate_geometry.json"
# Only a fit that would pass the compose guard is worth remembering.
CACHE_KEYS = ("quad", "face", "background", "coverage", "geom_residual_px",
              "geom_residual_by_side", "bow_left_px", "bow_right_px", "fit",
              "fit_residual_px")


def plate_key(path: Path) -> str:
    """Content hash of the plate. A different render must never inherit a fit."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:32]


def load_plate_geometry(path: Path) -> Optional[Dict[str, Any]]:
    """The stored fit for exactly this plate, or None."""
    if not PLATE_GEOMETRY_PATH.is_file():
        return None
    try:
        store = json.loads(PLATE_GEOMETRY_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - a corrupt cache is a miss, never a crash
        return None
    entry = store.get(plate_key(path))
    if not isinstance(entry, dict):
        return None
    geometry = entry.get("geometry")
    return geometry if isinstance(geometry, dict) else None


def save_plate_geometry(path: Path, measured: Dict[str, Any]) -> bool:
    """Remember a good fit for this exact plate. Refuses to cache a bad one."""
    residual = measured.get("geom_residual_px")
    if residual is None or float(residual) > MAX_GEOM_RESIDUAL_PX:
        return False
    store: Dict[str, Any] = {}
    if PLATE_GEOMETRY_PATH.is_file():
        try:
            store = json.loads(PLATE_GEOMETRY_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            store = {}
    store[plate_key(path)] = {
        "plate_name": Path(path).name,
        "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "geometry": {k: measured.get(k) for k in CACHE_KEYS if k in measured},
    }
    PLATE_GEOMETRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLATE_GEOMETRY_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    return True


def compose(plate_path: Path, *, title: str, subtitle: str = "", weight: str = "",
            bullets: Optional[Sequence[str]] = None,
            logo_path: Optional[Path] = None,
            icons: Optional[Sequence[str]] = None,
            field: Optional[Sequence[int]] = None, ink: Optional[Sequence[int]] = None,
            accent: Optional[Sequence[int]] = None,
            field_alpha: int = 250,
            shading: float = 0.28,
            quad: Optional[Sequence] = None,
            panels: Optional[Dict[str, Any]] = None,
            panel_split: bool = True,
            label_panel: Optional[Image.Image] = None,
            mesh: bool = True,
            reuse_geometry: bool = True) -> Dict[str, Any]:
    """Composite a label onto a rendered pouch. Returns PNG bytes + what was fitted."""
    if not title.strip():
        raise ValueError("a product title is required to compose a label")
    plate = Image.open(plate_path).convert("RGB")

    geometry_reused = False
    if quad:
        measured = {"quad": [list(p) for p in quad], "face": None, "background": None,
                    "coverage": None}
    else:
        measured = load_plate_geometry(plate_path) if reuse_geometry else None
        if measured:
            geometry_reused = True
        else:
            measured = measure_face(plate)
    q = measured["quad"]

    residual = measured.get("geom_residual_px")
    if residual is not None and float(residual) > MAX_GEOM_RESIDUAL_PX:
        raise ValueError(
            f"the pouch face is not consistent enough to label: measured edge vs mesh "
            f"residual {float(residual):.2f} px exceeds {MAX_GEOM_RESIDUAL_PX:.1f} px. "
            "Supply an operator quad for a lifestyle plate, or use a cleaner render.")
    bow_l = float(measured.get("bow_left_px") or 0.0)
    bow_r = float(measured.get("bow_right_px") or 0.0)
    bow = (bow_l + bow_r) / 2.0
    edge_feather = mc.feather_sigma(residual) if residual is not None else None
    if not geometry_reused and not quad and residual is not None:
        # A fit good enough to compose is good enough to remember, keyed by the
        # plate's own hash so a new render can never inherit it.
        save_plate_geometry(plate_path, measured)
    grid = (mc.mesh_grid(q, nx=MESH_NX, ny=MESH_NY, bow_x=(bow_l, bow_r))
            if mesh and max(abs(bow_l), abs(bow_r)) >= MIN_BOW_PX else None)

    logo = load_logo(Path(logo_path)) if logo_path else None
    panel = label_panel if label_panel is not None else render_label(
        title=title, subtitle=subtitle, weight=weight, bullets=bullets,
        logo=logo, icons=icons,
        field=tuple(field) if field else FIELD,
        ink=tuple(ink) if ink else INK,
        accent=tuple(accent) if accent else ACCENT,
        field_alpha=int(field_alpha),
    )
    if panel.width < 2 or panel.height < 2:
        raise ValueError("label_panel must be a non-empty image")

    try:
        import compositor_realism as cr
        # Blank-plate architecture: flatten the label target BEFORE the realism
        # pass. The realism pass modulates print with the plate's luminance (so a
        # label inherits creases) - which also let burned-in plate text ghost
        # through the label. After this the region has no edges to re-introduce.
        plate, _neutralized = mc.neutralize_quad(plate, q, feather=10)
        maps = cr.build_surface_maps(plate)
        # Packaging-grade integration. The earlier recipe was tuned too low: the
        # print landed as a flat opaque card because soft-light (0.30) and tonal
        # match (0.40) barely modulated it, and the fold shadow / AO rim - the two
        # knobs that make a print look like it belongs to the surface - were left
        # at their off defaults. The pouch's own creases and shading now come
        # through the ink, and a slight inner AO seats the panel edge.
        realism = {"displacement_k": 1.8, "softlight_strength": 0.26,
                   "specular_cap": 0.02, "grain_sync": 0.30, "tonal_match": 0.12,
                   "fold_shadow": 0.35, "fold_threshold": 0.05,
                   "ao_rim_px": 5, "ao_strength": 0.04}
        surfaces = None
        if panel_split and panels:
            try:
                from specialists import panel_map
                surfaces = panel_map.panel_quads(q, panels)
            except Exception:  # noqa: BLE001 - splitting is an upgrade, not a requirement
                surfaces = None
        if surfaces and len(surfaces) > 1:
            # One WRAPPED artwork, warped ONCE. Warping each surface separately
            # left hard seams where the strips met the front (found by building),
            # because every warp carried its own surface maps. Composing the
            # strips into a single panel keeps one homography and one shading
            # pass, and still gives the gussets their own width.
            wrapped = _wrap_panel(panel, surfaces, field=tuple(field) if field else FIELD,
                                  side_panel=_side_for(title=title, subtitle=subtitle,
                                                       weight=weight, claims=bullets,
                                                       icons=icons, field=field))
            out = mc.warp_panel(plate, wrapped, q, shading=shading, maps=maps,
                                realism=realism, grid=grid, edge_feather=edge_feather)
        else:
            out = mc.warp_panel(plate, panel, q, shading=shading, maps=maps,
                                realism=realism, grid=grid, edge_feather=edge_feather)
    except Exception:  # noqa: BLE001 - realism is an upgrade, not a requirement
        out = mc.warp_panel(plate, panel, q, shading=shading, grid=grid,
                            edge_feather=edge_feather)

    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return {
        "bytes": buf.getvalue(),
        "size": list(out.size),
        "quad": q,
        "measured": measured,
        "neutralized": _neutralized,
        "geom_residual_px": residual,
        "bow_x_px": round(bow, 3),
        "bow_left_px": round(bow_l, 3),
        "bow_right_px": round(bow_r, 3),
        "mesh": [MESH_NX, MESH_NY] if grid is not None else None,
        "geometry_reused": geometry_reused,
        "plate_sha256": None if quad else plate_key(plate_path),
        "edge_feather_px": round(float(edge_feather), 3) if edge_feather else None,
        "title": title,
        "has_logo": logo is not None,
        "icons": list(icons or []),
        "note": ("Label composited deterministically: real logo pixels and real fonts "
                 "warped onto the measured pouch face. The fit is a MOCKUP fit taken "
                 "from the render, not a die drawing — confirm panel geometry with the "
                 "pouch converter before print."),
    }
