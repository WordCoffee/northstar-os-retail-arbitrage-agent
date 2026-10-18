"""mockup_engine.py — photographic print integration (v2).

Prints flat artwork ONTO a studio plate photo so the design reads as PRINTED on
the package, not placed on it as a decal.

Mechanisms
----------
1. Calibrated silhouette geometry (``data/mockup_plates.json`` — one-time
   visual verification per plate) + per-row gradient edge-snap: every plate row
   finds the package's true left/right edge near the calibrated box, so the
   print reaches the real package edges on every row (no pasted rectangle).
2. Silhouette-following mapping: each row maps the art across that row's true
   package width — linear for pouches, cylindrical arcsin for tubes — so the
   print wraps the physical surface and stays attached at every edge.
3. Baked lighting: the photo's own luminance (large-scale shading + fine
   surface texture) is multiplied into the print, so highlights, cylinder
   shading, lid shadows and wrinkles continue THROUGH the design.
4. Edge feathering: mask dilate + ~2 px blur, so the print dissolves into the
   package edge with no hard outline.

Pure PIL + numpy, deterministic. No provider calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import numpy as np
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent
PLATES_JSON = ROOT / "data" / "mockup_plates.json"


# ── small helpers ───────────────────────────────────────────────────────────

def _smooth(lum: np.ndarray, r: float) -> np.ndarray:
    """Large-radius smoothing via down/up-scale (fast, dependency-free)."""
    im = Image.fromarray(np.clip(lum, 0, 255).astype(np.uint8), "L")
    k = max(2, int(r))
    small = im.resize((max(1, im.width // k), max(1, im.height // k)), Image.BILINEAR)
    return np.asarray(small.resize(im.size, Image.BICUBIC), dtype=np.float32)


def _feather(mask: np.ndarray, r: float) -> np.ndarray:
    m = Image.fromarray((np.clip(mask, 0, 1) * 255).astype(np.uint8), "L")
    m = m.filter(ImageFilter.MaxFilter(3))          # dilate 1 px: tuck under edge
    m = m.filter(ImageFilter.GaussianBlur(r))
    return np.asarray(m, dtype=np.float32) / 255.0


def _bilinear(pa: np.ndarray, u: np.ndarray, v: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    PH, PW = pa.shape[:2]
    valid = (u >= 0) & (u <= PW - 1.0001) & (v >= 0) & (v <= PH - 1.0001)
    uc = np.clip(u, 0, PW - 1.0001)
    vc = np.clip(v, 0, PH - 1.0001)
    u0 = np.floor(uc).astype(int)
    v0 = np.floor(vc).astype(int)
    u1 = np.minimum(u0 + 1, PW - 1)
    v1 = np.minimum(v0 + 1, PH - 1)
    wu = (uc - u0)[..., None]
    wv = (vc - v0)[..., None]
    samp = (pa[v0, u0] * (1 - wu) * (1 - wv) + pa[v0, u1] * wu * (1 - wv)
            + pa[v1, u0] * (1 - wu) * wv + pa[v1, u1] * wu * wv)
    return samp, valid


def load_plate_config() -> Dict[str, Dict]:
    if PLATES_JSON.is_file():
        try:
            return json.loads(PLATES_JSON.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


# ── segmentation: calibrated box + gradient edge-snap ───────────────────────

def segment_package(plate: Image.Image, cfg: Dict, *, v_span: int = 14,
                    snap_span: int = 7) -> Dict[str, np.ndarray]:
    """Silhouette from calibrated anchors (data/mockup_plates.json) + a small
    clamped gradient snap per row: the anchors are the ground truth envelope,
    the snap only fine-tunes each row within ±snap_span px, so no heuristic can
    wander onto the backdrop or the cast shadow."""
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    lum = a.mean(axis=2)
    H, W = lum.shape
    ys = np.arange(H)

    def snap_v(guess: int, lo: int, hi: int) -> int:
        yy = np.arange(max(2, lo), min(H - 3, hi))
        if not len(yy):
            return guess
        cols = np.arange(int(np.interp(guess, [p[0] for p in cfg["L"]], [p[1] for p in cfg["L"]]) + 8),
                         int(np.interp(guess, [p[0] for p in cfg["R"]], [p[1] for p in cfg["R"]]) - 8), 4)
        if not len(cols):
            return guess
        g = np.abs(lum[np.clip(yy + 2, 0, H - 1)][:, cols]
                   - lum[np.clip(yy - 2, 0, H - 1)][:, cols]).mean(axis=1)
        return int(yy[int(np.argmax(g))]) if float(g.max()) > 1.2 else guess

    top = snap_v(int(cfg["y0"]), int(cfg["y0"]) - v_span, int(cfg["y0"]) + v_span)
    bot = snap_v(int(cfg["y1"]), int(cfg["y1"]) - v_span, int(cfg["y1"]) + v_span)
    if bot <= top + 8:
        top, bot = int(cfg["y0"]), int(cfg["y1"])

    L = np.interp(ys, [p[0] for p in cfg["L"]], [p[1] for p in cfg["L"]])
    R = np.interp(ys, [p[0] for p in cfg["R"]], [p[1] for p in cfg["R"]])
    for y in range(top, bot + 1):
        for side, base in (("L", L[y]), ("R", R[y])):
            xs = np.arange(max(1, int(base) - snap_span), min(W - 1, int(base) + snap_span))
            if not len(xs):
                continue
            g = np.abs(lum[y, xs + 1] - lum[y, xs - 1])
            if float(g.max()) > 1.6:
                cand = float(xs[int(np.argmax(g))])
                if side == "L":
                    L[y] = cand
                else:
                    R[y] = cand
    R = np.maximum(R, L + 4.0)

    # column-wise bottom curve: clip rows that spill past the base silhouette.
    mid = (top + bot) // 2
    c0, c1 = int(L[mid]) + 6, int(R[mid]) - 6
    B = np.full(W, float(bot))
    for x in range(max(2, c0), min(W - 2, c1), 2):
        yy = np.arange(max(2, bot - 30), min(H - 3, bot + 20))
        if not len(yy):
            continue
        col = lum[:, max(0, x - 2):x + 3].mean(axis=1)
        g = np.abs(col[np.clip(yy + 2, 0, H - 1)] - col[np.clip(yy - 2, 0, H - 1)])
        g = g - 0.08 * np.abs(yy - bot)
        if float(g.max()) > 1.2:
            B[x] = float(yy[int(np.argmax(g))])
    for x in range(max(2, c0), min(W - 2, c1), 2):
        B[x] = np.median(B[max(0, x - 8):x + 9])

    ygrid = np.arange(H)[:, None]
    xgrid = np.arange(W)[None, :]
    mask = ((xgrid >= L[:, None]) & (xgrid <= R[:, None]) & (ygrid >= top) & (ygrid <= bot)
            & (ygrid <= B[None, :]))
    return {"mask": mask, "l": L, "r": R, "y0": int(top), "y1": int(bot)}


def detect_lid_bottom(plate: Image.Image, seg: Dict) -> int:
    """Row where the lid meets the tube body: strongest horizontal edge in the
    upper part of the package (the lid's shadow line). Falls back to a fraction."""
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    lum = a.mean(axis=2)
    mid = (seg["y0"] + seg["y1"]) // 2
    c0 = int(seg["l"][mid]) + 10
    c1 = int(seg["r"][mid]) - 10
    cols = np.arange(max(2, c0), min(lum.shape[1] - 2, c1), 4)
    lo = seg["y0"] + 6
    hi = seg["y0"] + int(0.45 * (seg["y1"] - seg["y0"]))
    fallback = seg["y0"] + int(0.14 * (seg["y1"] - seg["y0"]))
    if not len(cols) or hi <= lo:
        return fallback
    ys = np.arange(lo, hi)
    H = lum.shape[0]
    g = np.abs(lum[np.clip(ys + 2, 0, H - 1)][:, cols]
               - lum[np.clip(ys - 2, 0, H - 1)][:, cols]).mean(axis=1)
    if float(g.max()) < 1.2:
        return fallback
    return int(ys[int(np.argmax(g))]) + 2


# ── surface fields (baked lighting) ─────────────────────────────────────────

def surface_fields(plate: Image.Image, mask: np.ndarray):
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    lum = a.mean(axis=2)
    ref = float(np.median(lum[mask])) + 1e-6
    base = _smooth(lum, 48)
    detail = lum - base
    shade = np.clip(lum / ref, 0.48, 1.12)
    dn = np.clip(detail / 22.0, -1.0, 1.0)
    return shade, dn


def _composite(plate: Image.Image, mask: np.ndarray, ink: np.ndarray, valid: np.ndarray,
               shade: np.ndarray, dn: np.ndarray, y_off: int, *, bake: float,
               emboss: float, feather: float) -> Image.Image:
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    h = ink.shape[0]
    y1 = y_off + h
    base = a[y_off:y1]
    mslice = mask[y_off:y1]
    factor = (shade[y_off:y1] ** bake) * (1.0 + emboss * dn[y_off:y1])
    lit = ink * factor[..., None]
    alpha = _feather(mslice.astype(np.float32), feather) * valid.astype(np.float32)
    out = lit * alpha[..., None] + base * (1.0 - alpha[..., None])
    a[y_off:y1] = out
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "RGB")


# ── package-specific print passes ───────────────────────────────────────────

def print_pouch(plate: Image.Image, art: Image.Image, cfg: Dict, *, bake: float = 0.75,
                emboss: float = 0.34, feather: float = 2.4, disp: float = 2.0,
                top_inset: int = 1, bot_inset: int = 3) -> Image.Image:
    """Full-bleed print across the pouch silhouette (linear per-row mapping),
    displaced by the plate's folds, lit by the plate's light."""
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    H, W = a.shape[:2]
    seg = segment_package(plate, cfg)
    mask = seg["mask"]
    l, r = seg["l"], seg["r"]
    y0, y1 = seg["y0"] + top_inset, seg["y1"] - bot_inset
    pa = np.asarray(art.convert("RGB"), dtype=np.float32)
    PW, PH = art.size

    yy, xx = np.mgrid[y0:y1 + 1, 0:W]
    Ly = l[y0:y1 + 1][:, None]
    Ry = r[y0:y1 + 1][:, None]
    u = (xx - Ly) / np.maximum(1.0, Ry - Ly) * (PW - 1)
    v = (yy - y0) / max(1.0, (y1 - y0)) * (PH - 1)

    # wrinkle displacement: gentle, smoothed, damped toward the gusset/base
    lum = a.mean(axis=2)
    gxs = _smooth(lum, 22)
    gx = _smooth(np.gradient(gxs, axis=1)[y0:y1 + 1], 9)
    gy = _smooth(np.gradient(gxs, axis=0)[y0:y1 + 1], 9)
    hh = max(1.0, float(y1 - y0))
    yy_rel = (yy - y0) / hh
    damp = np.clip(1.0 - (np.clip(yy_rel - 0.70, 0.0, None) / 0.30) * 0.9, 0.10, 1.0)
    damp = damp * np.clip(yy_rel / 0.05, 0.25, 1.0)
    u = u + damp * np.clip(gx / 12.0, -disp, disp)
    v = v + damp * np.clip(gy / 18.0, -disp * 0.5, disp * 0.5)

    ink, valid = _bilinear(pa, u, v)
    shade, dn = surface_fields(plate, mask)
    return _composite(plate, mask, ink, valid, shade, dn, y0,
                      bake=bake, emboss=emboss, feather=feather)


def print_tube(plate: Image.Image, art: Image.Image, cfg: Dict, *, bake: float = 0.9,
               emboss: float = 0.45, feather: float = 2.2,
               lid_skip: bool = True) -> Image.Image:
    """Full wrap across the tube body: every row maps the half-wrap art over the
    visible 180° arc (arcsin compression at the silhouette), lit + embossed."""
    a = np.asarray(plate.convert("RGB"), dtype=np.float32)
    H, W = a.shape[:2]
    seg = segment_package(plate, cfg)
    mask = seg["mask"]
    l, r = seg["l"], seg["r"]
    top = detect_lid_bottom(plate, seg) if lid_skip else seg["y0"] + 2
    top = max(top, seg["y0"] + 2)
    bot = seg["y1"] - 2
    pa = np.asarray(art.convert("RGB"), dtype=np.float32)
    PW, PH = art.size

    yy, xx = np.mgrid[top:bot + 1, 0:W]
    Ly = l[top:bot + 1][:, None]
    Ry = r[top:bot + 1][:, None]
    cx = (Ly + Ry) / 2.0
    Rr = np.maximum(1.0, (Ry - Ly) / 2.0)
    d = np.clip((xx - cx) / Rr, -1.0, 1.0)
    theta = np.arcsin(d)
    u = (theta / np.pi + 0.5) * (PW - 1)
    v = (yy - top) / max(1.0, (bot - top)) * (PH - 1)

    ink, valid = _bilinear(pa, u, v)
    shade, dn = surface_fields(plate, mask)
    return _composite(plate, mask, ink, valid, shade, dn, top,
                      bake=bake, emboss=emboss, feather=feather)


def print_package(plate: Image.Image, art: Image.Image, kind: str, cfg: Dict, **kw) -> Image.Image:
    if kind == "tube":
        return print_tube(plate, art, cfg, **kw)
    return print_pouch(plate, art, cfg, **kw)


# ── diagnostics ─────────────────────────────────────────────────────────────

def mask_preview(plate: Image.Image, cfg: Dict, out_path: Path) -> Dict[str, object]:
    """Save a red-tinted mask overlay + report the snapped geometry."""
    seg = segment_package(plate, cfg)
    a = np.asarray(plate.convert("RGB")).astype(np.float32)
    m = seg["mask"]
    a[m] = a[m] * 0.4 + np.array([255, 40, 40], dtype=np.float32) * 0.6
    Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).save(out_path)
    mid = (seg["y0"] + seg["y1"]) // 2
    return {"y0": seg["y0"], "y1": seg["y1"],
            "l_mid": float(seg["l"][mid]), "r_mid": float(seg["r"][mid])}
