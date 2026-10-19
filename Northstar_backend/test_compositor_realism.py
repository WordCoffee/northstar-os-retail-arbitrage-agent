"""compositor_realism tests — the surface-realism passes, offline and synthetic.

Each test isolates ONE mechanism on a synthetic plate so a regression names the
pass it broke:
  displacement direction · soft-light shading · specular screen · grain sync ·
  junction AO rim · scene tonal match · determinism · warp_panel integration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import compositor_realism as cr  # noqa: E402
import mockup_compositor as mc  # noqa: E402


def _ramp_plate(w: int = 200, h: int = 300, lo: int = 60, hi: int = 200) -> Image.Image:
    """Smooth horizontal luminance ramp: dark left -> bright right."""
    x = np.linspace(lo, hi, w, dtype=np.float32)[None, :].repeat(h, axis=0)
    arr = np.stack([x, x, x], axis=-1).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def _flat_plate(w: int = 200, h: int = 300, level: int = 128) -> Image.Image:
    return Image.new("RGB", (w, h), (level, level, level))


def _noise_plate(w: int = 200, h: int = 300, level: int = 128, amp: int = 18) -> Image.Image:
    rng = np.random.default_rng(7)
    base = np.full((h, w, 3), level, dtype=np.float32)
    base += rng.integers(-amp, amp + 1, size=(h, w, 1))
    return Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")


def _solid_panel(w: int = 80, h: int = 120, rgba=(250, 250, 250, 255)) -> Image.Image:
    return Image.new("RGBA", (w, h), rgba)


def _map_region(maps: cr.SurfaceMaps, shape) -> cr.SurfaceMaps:
    h, w = shape[:2]
    return maps.slice(0, min(w, maps.broad.shape[1]), 0, min(h, maps.broad.shape[0]))


# ── 1. displacement ─────────────────────────────────────────────────────────

def test_displacement_shift_follows_luminance_sign():
    plate = _ramp_plate()
    maps = cr.build_surface_maps(plate)
    du, dv = cr.displacement_shift(maps, scale_u=2.0, scale_v=2.0, params=dict(cr.DEFAULTS))
    left = float(du[:, :20].mean())
    right = float(du[:, -20:].mean())
    # bright side (right) shifts one way, dark side (left) the opposite way
    assert left < 0 < right, (left, right)
    assert dv.shape == du.shape
    assert abs(float(dv.mean())) <= abs(float(du.mean())) + 1e-6  # v is the minor axis


def test_displacement_zero_on_flat_plate():
    maps = cr.build_surface_maps(_flat_plate())
    du, dv = cr.displacement_shift(maps, 2.0, 2.0, dict(cr.DEFAULTS))
    assert np.allclose(du, 0.0, atol=1e-6) and np.allclose(dv, 0.0, atol=1e-6)


# ── 2. soft-light shading ───────────────────────────────────────────────────

def test_softlight_darkens_ink_on_dark_regions_and_brightens_on_light():
    # plate: mid field with a dark band and a bright band -> the print over the
    # dark band must darken; over the bright band it must brighten.
    base = np.full((120, 200, 3), 128, dtype=np.uint8)
    base[:, :60] = 60
    base[:, 140:] = 210
    plate = Image.fromarray(base, "RGB")
    maps = cr.build_surface_maps(plate)
    region = np.full((120, 200, 3), 128.0, dtype=np.float32)
    samp = np.full((120, 200, 4), 0.0, dtype=np.float32)
    samp[..., :3] = 200.0
    samp[..., 3] = 255.0

    out, m = cr.composite_panel(region.copy(), samp.copy(), maps,
                                dict(cr.DEFAULTS), shading=0.5)
    assert m["softlight_strength"] > 0.8
    dark_band = float(out[:, 10:50, :].mean())
    bright_band = float(out[:, 150:190, :].mean())
    assert dark_band < 195.0, f"ink did not darken on a dark surface ({dark_band})"
    assert bright_band > 205.0, f"ink did not brighten on a light surface ({bright_band})"


def test_shading_zero_is_flat_paste():
    maps = cr.build_surface_maps(_flat_plate(80, 120, level=70))
    region = np.full((120, 80, 3), 128.0, dtype=np.float32)
    samp = np.full((120, 80, 4), 0.0, dtype=np.float32)
    samp[..., :3] = 200.0
    samp[..., 3] = 255.0
    out, _ = cr.composite_panel(region.copy(), samp.copy(), maps,
                                dict(cr.DEFAULTS), shading=0.0)
    assert np.allclose(out, 200.0, atol=1.0), "shading=0 must not alter the ink"


# ── 3. specular ─────────────────────────────────────────────────────────────

def test_specular_brightens_ink_under_a_highlight():
    base = np.full((300, 200, 3), 120, dtype=np.uint8)
    base[140:160, :, :] = 250          # a bright sheen band
    plate = Image.fromarray(base, "RGB")
    maps = cr.build_surface_maps(plate)
    region = np.full((300, 200, 3), 120.0, dtype=np.float32)
    samp = np.full((300, 200, 4), 0.0, dtype=np.float32)
    samp[..., :3] = 150.0
    samp[..., 3] = 255.0
    out, m = cr.composite_panel(region.copy(), samp.copy(), maps,
                                dict(cr.DEFAULTS), shading=0.5)
    band = float(out[145:155, :, :].mean())
    off = float(out[20:40, :, :].mean())
    assert m.get("specular_coverage", 0) > 0.0
    assert band > off + 2.0, (band, off)


# ── 4. grain sync ───────────────────────────────────────────────────────────

def test_grain_sync_carries_plate_texture_into_the_print():
    smooth = cr.build_surface_maps(_flat_plate())
    noisy = cr.build_surface_maps(_noise_plate())
    region = np.full((300, 200, 3), 128.0, dtype=np.float32)
    samp = np.full((300, 200, 4), 0.0, dtype=np.float32)
    samp[..., :3] = 160.0
    samp[..., 3] = 255.0
    out_s, _ = cr.composite_panel(region.copy(), samp.copy(), smooth,
                                  dict(cr.DEFAULTS), shading=0.5)
    out_n, _ = cr.composite_panel(region.copy(), samp.copy(), noisy,
                                  dict(cr.DEFAULTS), shading=0.5)
    assert float(out_n[:, :, 0].std()) > float(out_s[:, :, 0].std()) + 0.5


# ── 5. junction AO rim ──────────────────────────────────────────────────────

def test_ao_rim_darkens_inside_the_print_edge_only():
    maps = cr.build_surface_maps(_flat_plate(200, 200))
    region = np.full((200, 200, 3), 150.0, dtype=np.float32)
    samp = np.zeros((200, 200, 4), dtype=np.float32)
    samp[40:160, 40:160, :3] = 220.0
    samp[40:160, 40:160, 3] = 255.0
    params = {**cr.DEFAULTS, "ao_rim_px": 4}
    out, m = cr.composite_panel(region.copy(), samp.copy(), maps, params, shading=0.5)
    edge = float(out[60:140, 42:46, :].mean())
    inner = float(out[90:110, 90:110, :].mean())
    assert m["ao_rim_px"] == 4.0
    assert edge < inner - 1.0, (edge, inner)
    # outside the print is untouched by the rim
    assert abs(float(out[10, 10, :].mean()) - 150.0) < 1.0


# ── 6. tonal match ──────────────────────────────────────────────────────────

def test_tonal_match_is_gentle_and_effective():
    base = np.full((240, 240, 3), 90, dtype=np.uint8)
    base[60:180, 60:180, :] = 200     # high-contrast plate patch
    plate = Image.fromarray(base, "RGB")
    maps = cr.build_surface_maps(plate)
    region = np.full((240, 240, 3), 140.0, dtype=np.float32)
    samp = np.zeros((240, 240, 4), dtype=np.float32)
    samp[80:160, 80:160, :3] = 150.0
    samp[80:160, 80:160, 3] = 255.0

    out_off, _ = cr.composite_panel(region.copy(), samp.copy(), maps,
                                    {**cr.DEFAULTS, "tonal_match": 0.0}, shading=0.5)
    out_on, m = cr.composite_panel(region.copy(), samp.copy(), maps,
                                   {**cr.DEFAULTS, "tonal_match": 1.0}, shading=0.5)
    assert m.get("tonal_match") is not None
    ink_slice = (slice(80, 160), slice(80, 160))
    delta = np.abs(out_on[ink_slice] - out_off[ink_slice])
    assert delta.mean() > 0.05, "tonal match had no effect"
    assert delta.max() < 24.0, f"tonal match was not gentle (max {delta.max()})"
    # the plate outside the ink is untouched
    assert np.allclose(out_on[:40, :40], out_off[:40, :40])


# ── 7. determinism ──────────────────────────────────────────────────────────

def test_composite_is_deterministic():
    maps = cr.build_surface_maps(_noise_plate())
    region = np.full((300, 200, 3), 128.0, dtype=np.float32)
    samp = np.full((300, 200, 4), 0.0, dtype=np.float32)
    samp[..., :3] = 170.0
    samp[..., 3] = 255.0
    a, _ = cr.composite_panel(region.copy(), samp.copy(), maps, dict(cr.DEFAULTS), 0.5)
    b, _ = cr.composite_panel(region.copy(), samp.copy(), maps, dict(cr.DEFAULTS), 0.5)
    assert np.array_equal(a, b)


# ── 8. warp_panel integration ───────────────────────────────────────────────

def test_warp_panel_with_maps_uses_realism_and_legacy_still_works():
    plate = _ramp_plate(400, 400)
    panel = _solid_panel(100, 200, (240, 240, 240, 255))
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 20, 99, 40], fill=(30, 30, 30, 255))
    quad = [(40, 60), (360, 50), (370, 350), (30, 360)]

    legacy = mc.warp_panel(plate, panel, quad, shading=0.5)
    maps = cr.build_surface_maps(plate)
    metrics: dict = {}
    modern = mc.warp_panel(plate, panel, quad, shading=0.5, maps=maps,
                           metrics_out=metrics)
    assert legacy.size == modern.size == plate.size
    assert metrics.get("softlight_strength", 0) > 0.5
    assert metrics.get("displacement_max_px", 0) > 0.0
    diff = np.abs(np.asarray(legacy, dtype=int) - np.asarray(modern, dtype=int)).mean()
    assert diff > 0.05, "realism path did not change the output"


def test_pseudo_normals_are_unit_vectors():
    maps = cr.build_surface_maps(_ramp_plate())
    n = cr.pseudo_normals(maps)
    norms = np.linalg.norm(n, axis=-1)
    assert np.allclose(norms, 1.0, atol=1e-5)


def test_tile_to_shapes():
    g = np.arange(12, dtype=np.float32).reshape(3, 4)
    t = cr.tile_to(g, (7, 9))
    assert t.shape == (7, 9)
    assert t[0, 0] == g[0, 0] and t[3, 4] == g[0, 0]
