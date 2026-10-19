"""compositor_realism — surface-realism passes for the deterministic compositor.

This module implements the "printed-on-the-surface" recipe verified across the
2026-10 deep dive (research/packify_quality_deep_dive_20261016/
COMPOSITOR_REALISM_AND_PACKIFY.md, §2-§3): displacement-warp the print by the
surface's own blurred luminance, blend it through the surface with a soft-light
operator instead of an opaque paste, screen a capped specular pass over the ink,
sync the print's grain to the plate's measured grain, and (opt-in) ground the
print with a junction AO/seam, fold shadows, print-process simulation and a
scene-level tonal match.

Everything is deterministic, local, PIL + numpy only. Nothing here calls a
model or a network. All knobs live in ``DEFAULTS`` and are recorded verbatim in
the compose sidecar so an output is reproducible from its parameters.

Pass order (per face):
  1. luminance displacement (broad field)          -> ink rides folds
  2. ink-alpha softening (print-scale dot edge)
  3. soft-light shading through the surface        -> ink takes the shading
  4. capped specular screen over the ink           -> film sheen lies OVER print
  5. fold-shadow multiply (opt-in)                 -> creases darken the ink
  6. print-process show-through (opt-in)           -> dark-film ink physics
  7. grain sync keyed to ink alpha                 -> kills the "clean vector" read
  8. junction AO rim + seam (opt-in)               -> grounds a printed PATCH
  9. scene tonal match (on)                        -> composite follows plate curve
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

# ── tunables ────────────────────────────────────────────────────────────────
# Conservative defaults: 1-5 on, 6-9 opt-in. Every value ships in the sidecar.
DEFAULTS: Dict[str, float] = {
    # 1. displacement
    "displacement_k": 3.0,          # max shift in PLATE px at full shading
    "displacement_v_ratio": 0.35,   # vertical component relative to horizontal
    # 2. ink edge
    "ink_soften_px": 0.25,          # plate-px alpha softening of the print
    # 3. soft-light
    "softlight_strength": 0.9,      # 0..1  (0.9 = research recommendation)
    "shade_clip_lo": 0.28,          # s01 floor (deep shadow keeps ink readable)
    # 4. specular
    "specular_cap": 0.32,
    "specular_threshold": 1.35,     # multiples of the local median luminance
    # 5. fold shadow (opt-in)
    "fold_shadow": 0.0,             # 0 = off, 0.35 = subtle, 0.6 = strong
    "fold_threshold": 0.06,         # surface darkening vs median that counts
    # 6. print-process simulation (opt-in)
    "print_showthrough": 0.0,       # dark-film ink show-through, 0..0.06 sane
    "dot_gain": 0.0,                # alpha gamma nudge, 0..0.05 sane
    # 7. grain
    "grain_sync": 1.0,              # multiplies the measured high-pass grain
    # 8. junction grounding (opt-in; scattered designs should leave 0)
    "ao_rim_px": 0,                 # plate-px inner AO rim
    "ao_strength": 0.05,            # 0..0.06 sane
    "seam_px": 0,                   # plate-px outer seam
    "seam_strength": 0.10,
    # 9. tonal match
    "tonal_match": 1.0,             # 0/1 — match composite endpoints to plate
}


@dataclass
class SurfaceMaps:
    """Per-plate fields, computed once and sliced per face."""
    broad: np.ndarray               # heavily blurred luminance (folds/shading)
    sharp: np.ndarray               # lightly blurred luminance (specular)
    grain: np.ndarray               # high-pass luminance (measured grain)
    lum: np.ndarray                 # raw luminance
    median: float                   # global median of broad
    grad_x: np.ndarray = field(default=None, repr=False)
    grad_y: np.ndarray = field(default=None, repr=False)

    def slice(self, x0: int, x1: int, y0: int, y1: int) -> "SurfaceMaps":
        return SurfaceMaps(
            broad=self.broad[y0:y1, x0:x1],
            sharp=self.sharp[y0:y1, x0:x1],
            grain=self.grain[y0:y1, x0:x1],
            lum=self.lum[y0:y1, x0:x1],
            median=self.median,
            grad_x=None if self.grad_x is None else self.grad_x[y0:y1, x0:x1],
            grad_y=None if self.grad_y is None else self.grad_y[y0:y1, x0:x1],
        )


# ── helpers ─────────────────────────────────────────────────────────────────

def luminance(rgb: np.ndarray) -> np.ndarray:
    """Rec.601 luma of a float RGB array (H,W,3) or (H,W,4)."""
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]).astype(np.float32)


def _blur(a: np.ndarray, radius: float) -> np.ndarray:
    if radius <= 0:
        return a.astype(np.float32)
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(float(radius))), dtype=np.float32)


def softlight(x: np.ndarray, s: np.ndarray) -> np.ndarray:
    """W3C soft-light on normalized arrays (broadcastable)."""
    return x + (2.0 * s - 1.0) * x * (1.0 - x)


def build_surface_maps(plate: Image.Image,
                       broad_radius: float = 6.0,
                       sharp_radius: float = 2.5,
                       grain_radius: float = 1.5) -> SurfaceMaps:
    """Measure the plate's shading + grain fields once per plate."""
    arr = np.asarray(plate.convert("RGB"), dtype=np.float32)
    lum = luminance(arr)
    broad = _blur(lum, broad_radius)
    sharp = _blur(lum, sharp_radius)
    grain = lum - _blur(lum, grain_radius)
    gy, gx = np.gradient(broad)
    return SurfaceMaps(broad=broad, sharp=sharp, grain=grain, lum=lum,
                       median=float(np.median(broad)) or 1.0,
                       grad_x=gx, grad_y=gy)


def pseudo_normals(maps: SurfaceMaps, strength: float = 1.0) -> np.ndarray:
    """Pseudo-normal field from the shading gradient (N=-dL/dx, -dL/dy, k).

    Mirrors the ``depthData``/``lumin_url`` vocabulary of the commercial mockup
    engines with zero model dependencies. Returns (H,W,3) unit vectors."""
    gx = maps.grad_x if maps.grad_x is not None else np.gradient(maps.broad)[1]
    gy = maps.grad_y if maps.grad_y is not None else np.gradient(maps.broad)[0]
    nz = np.full_like(gx, 12.0 / max(1e-6, strength))
    n = np.stack([-gx, -gy, nz], axis=-1)
    norm = np.linalg.norm(n, axis=-1, keepdims=True) + 1e-6
    return n / norm


def tile_to(grain: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """Tile a measured grain patch to an arbitrary (H,W) shape."""
    h, w = shape
    gh, gw = grain.shape[:2]
    if gh == 0 or gw == 0:
        return np.zeros(shape, dtype=np.float32)
    reps_y = int(np.ceil(h / gh))
    reps_x = int(np.ceil(w / gw))
    return np.tile(grain, (reps_y, reps_x))[:h, :w]


# ── the composite ───────────────────────────────────────────────────────────

def displacement_shift(maps: SurfaceMaps, scale_u: float, scale_v: float,
                       params: Dict[str, float]) -> Tuple[np.ndarray, np.ndarray]:
    """Per-pixel sampling offset in PANEL space from the surface luminance.

    ``scale_u``/``scale_v`` convert plate-px to panel-px for the face.
    Returns (du, dv) float arrays shaped like the sliced maps."""
    med = maps.median or 1.0
    d = np.clip((maps.broad - med) / (med * 0.55), -1.0, 1.0)
    k = params.get("displacement_k", DEFAULTS["displacement_k"])
    dv_ratio = params.get("displacement_v_ratio", DEFAULTS["displacement_v_ratio"])
    du = d * k * scale_u
    dv = d * k * scale_v * dv_ratio
    return du.astype(np.float32), dv.astype(np.float32)


def fold_mask(maps: SurfaceMaps, params: Dict[str, float]) -> np.ndarray:
    """Regions where the surface darkens relative to the broad field (creases)."""
    med = maps.median or 1.0
    dark = np.clip((med - maps.broad) / med, 0.0, 1.0) / max(1e-6, params.get("fold_threshold", 0.06))
    return np.clip(dark, 0.0, 1.0).astype(np.float32)


def composite_panel(region: np.ndarray, samp: np.ndarray, maps: SurfaceMaps,
                    params: Optional[Dict[str, float]] = None,
                    shading: float = 0.5) -> Tuple[np.ndarray, Dict[str, float]]:
    """Blend a sampled panel RGBA (float, 0..255) into a plate region in place.

    ``shading`` is the master dial (0 = flat paste, 0.5 = research default,
    1.0 = full). It scales passes 1/3/4 linearly (soft-light reaches its 0.9
    recommendation at shading=0.5). ``params`` overrides individual knobs.

    Returns (modified region, metrics dict)."""
    p = dict(DEFAULTS)
    for k, v in (params or {}).items():
        if k in p:
            p[k] = v
    dial = float(np.clip(shading * 2.0, 0.0, 1.0))

    if maps.broad.shape[:2] != region.shape[:2]:
        raise ValueError(
            f"surface maps {maps.broad.shape[:2]} do not match region "
            f"{region.shape[:2]}; slice the maps to the region first "
            "(warp_panel does this).")

    alpha = samp[..., 3:4] / 255.0
    rgb = samp[..., :3] / 255.0
    metrics: Dict[str, float] = {}

    # 2. ink-edge softening (print-scale dot edge)
    soften = p["ink_soften_px"] * dial
    if soften > 0.01:
        a_img = Image.fromarray((alpha[..., 0] * 255).astype(np.uint8), "L")
        alpha = (np.asarray(a_img.filter(ImageFilter.GaussianBlur(soften)),
                            dtype=np.float32) / 255.0)[..., None]
        metrics["ink_soften_px"] = float(soften)

    # 3. soft-light shading through the surface
    med = maps.median or 1.0
    s01 = np.clip(0.5 + (maps.broad - med) / (med * 1.1),
                  p["shade_clip_lo"], 1.0)[..., None]
    strength = float(np.clip(p["softlight_strength"] * dial, 0.0, 1.0))
    if strength > 0.0:
        sl = softlight(rgb, s01)
        rgb = rgb * (1.0 - strength) + sl * strength
    metrics["softlight_strength"] = strength

    # 4. capped specular screen (the film's sheen sits OVER the ink)
    if p["specular_cap"] > 0 and dial > 0:
        msharp = float(np.median(maps.sharp)) or 1.0
        hi = np.clip((maps.sharp - msharp * p["specular_threshold"])
                     / (msharp * 0.9), 0.0, p["specular_cap"] * dial)[..., None]
        rgb = rgb + (1.0 - rgb) * hi
        metrics["specular_coverage"] = float((hi > 0.01).mean())

    # 5. fold shadows (opt-in)
    if p["fold_shadow"] > 0:
        fm = fold_mask(maps, p)[..., None] * float(p["fold_shadow"]) * dial
        rgb = rgb * (1.0 - fm)
        metrics["fold_shadow"] = float(p["fold_shadow"])

    # 6. print-process show-through (opt-in): surface luminance bleeds into ink
    if p["print_showthrough"] > 0:
        st = float(p["print_showthrough"])
        rgb = rgb * (1.0 - st) + (maps.lum / 255.0)[..., None] * st
        metrics["print_showthrough"] = st

    # 6b. dot gain (opt-in): slight alpha dilation via gamma
    if p["dot_gain"] > 0:
        alpha = np.clip(alpha ** (1.0 - float(p["dot_gain"])), 0.0, 1.0)
        metrics["dot_gain"] = float(p["dot_gain"])

    # 7. grain sync keyed to ink alpha (print takes the plate's own grain)
    if p["grain_sync"] > 0:
        g = (tile_to(maps.grain, region.shape[:2]) / 255.0)[..., None]
        rgb = rgb + (g * alpha) * float(p["grain_sync"]) * (0.5 + 0.5 * dial)
        metrics["grain_sync"] = float(p["grain_sync"])

    rgb = np.clip(rgb, 0.0, 1.0) * 255.0
    out = rgb * alpha + region * (1.0 - alpha)

    # 8. junction grounding (opt-in; scattered designs must leave py = 0)
    ao_px = int(p["ao_rim_px"])
    seam_px = int(p["seam_px"])
    if ao_px > 0 or seam_px > 0:
        out, ground = _ground_junctions(out, alpha, ao_px, seam_px,
                                        float(p["ao_strength"]),
                                        float(p["seam_strength"]))
        metrics.update(ground)

    # 9. scene tonal match — pull the composite's endpoints toward the plate's
    if p["tonal_match"] > 0 and dial > 0:
        out, tm = _tonal_match(out, region, alpha, float(p["tonal_match"]) * dial)
        metrics["tonal_match"] = tm

    region[:] = out
    return region, metrics


def _ground_junctions(out: np.ndarray, alpha: np.ndarray, ao_px: int, seam_px: int,
                      ao_strength: float, seam_strength: float
                      ) -> Tuple[np.ndarray, Dict[str, float]]:
    """Darken inside the print boundary (AO rim) and just outside it (seam)."""
    mask = (alpha[..., 0] > 0.35).astype(np.uint8) * 255
    img = Image.fromarray(mask, "L")
    if ao_px > 0:
        inner = np.asarray(img.filter(ImageFilter.MinFilter(2 * ao_px + 1)),
                           dtype=np.float32) / 255.0
        # rim = mask eroded, subtracted from mask, softened
        rim = np.clip(alpha[..., 0] - inner, 0.0, 1.0)
        rim = _blur(rim * 255.0, max(1.0, ao_px * 0.6)) / 255.0
        out = out * (1.0 - rim[..., None] * ao_strength)
    else:
        rim = np.zeros_like(alpha[..., 0])

    seam = np.zeros_like(rim)
    if seam_px > 0:
        outer = np.asarray(img.filter(ImageFilter.MaxFilter(2 * seam_px + 1)), dtype=np.float32) / 255.0
        seam = np.clip(outer - alpha[..., 0], 0.0, 1.0)
        seam = _blur(seam * 255.0, max(1.0, seam_px * 0.6)) / 255.0
        out = out * (1.0 - seam[..., None] * seam_strength)
    return out, {"ao_rim_px": float(ao_px), "seam_px": float(seam_px)}


def _tonal_match(out: np.ndarray, region: np.ndarray, alpha: np.ndarray,
                 strength: float) -> Tuple[np.ndarray, float]:
    """Gentle illumination harmonization.

    Gains the INK toward the plate's local mean illumination, clamped to +-6%
    so brand colours and cream ink keep their read while a print that is
    obviously hotter or colder than its surface comes back onto the plate's
    curve. This is the deterministic "poor-man's harmonize" — image
    harmonization research (iHarmony4) shows tonal mismatch, not geometry, is
    the dominant composite tell.
    """
    ink = alpha[..., 0] > 0.5
    if ink.sum() < 50:
        return out, 1.0
    plate_mean = float(np.mean(luminance(region)))
    ink_mean = float(np.mean(luminance(out)[ink]))
    if ink_mean < 1e-3:
        return out, 1.0
    gain = float(np.clip(plate_mean / ink_mean, 0.94, 1.06))
    eff = 1.0 + strength * (gain - 1.0)
    adj = np.clip(out * eff, 0, 255)
    # only the ink is regraded; the plate stays untouched
    return np.where(alpha > 0.02, adj, out), round(eff, 4)
