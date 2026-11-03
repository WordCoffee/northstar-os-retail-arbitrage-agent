"""L3 + L4 — feather derived from the measured residual, and a per-plate fit cache.

L3 defends the halo finding: feathering does not create a bleed, it only smears
one the geometry already made (reports/rea_probe/warp_probe.json: 0.000 lum at
zero overshoot, 57.013 lum at 1 px). So the feather must follow the residual.

L4 makes the sub-pixel fit reusable without ever letting a new plate inherit an
old one: the cache key is the plate's own content hash.
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest
from PIL import Image, ImageDraw

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import mockup_compositor as mc  # noqa: E402
import pouch_label as pl  # noqa: E402


# ── L3 ──────────────────────────────────────────────────────────────────────

def test_feather_follows_the_residual_and_clamps():
    assert mc.feather_sigma(0.2) == 1.0            # clean fit: no softening
    assert mc.feather_sigma(1.5) == pytest.approx(3.75)
    assert mc.feather_sigma(10.0) == 12.0          # hi clamp: beyond this we refuse
    assert mc.feather_sigma(0) == 1.0
    assert mc.feather_sigma(None) == 1.0
    # A non-finite residual is a FAILED fit, not a default: t9 pins the refusal.
    with pytest.raises(ValueError):
        mc.feather_sigma(float("nan"))


def _hard_panel():
    panel = Image.new("RGBA", (120, 180), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 0, 119, 179], fill=(250, 250, 245, 255))
    return panel


def test_edge_feather_softens_the_edge_without_a_grey_fringe():
    plate = Image.new("RGB", (300, 340), (30, 30, 30))
    quad = [(60, 60), (240, 55), (245, 280), (55, 285)]
    hard = np.array(mc.warp_panel(plate, _hard_panel(), quad)).astype(int)
    soft = np.array(mc.warp_panel(plate, _hard_panel(), quad, edge_feather=6.0)).astype(int)

    row = 170
    hard_line, soft_line = hard[row].mean(axis=1), soft[row].mean(axis=1)
    # count pixels that are neither the panel nor the background: the edge ramp
    hard_mid = ((hard_line > 45) & (hard_line < 235)).sum()
    soft_mid = ((soft_line > 45) & (soft_line < 235)).sum()
    assert soft_mid > hard_mid + 2, (hard_mid, soft_mid)

    # the blur must not drag transparent black into the print (no dark fringe):
    # every pixel between background and panel must sit ABOVE the background.
    band = (soft_line > 40) & (soft_line < 235)
    assert band.any()
    assert soft_line[band].min() > 40, soft_line[band].min()


# ── L4 ──────────────────────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path, monkeypatch):
    path = tmp_path / "plate_geometry.json"
    monkeypatch.setattr(pl, "PLATE_GEOMETRY_PATH", path)
    return path


def _plate(tmp_path, name="p.png", shade=32):
    img = Image.new("RGB", (200, 260), (232, 226, 216))
    d = ImageDraw.Draw(img)
    d.polygon([(50, 30), (150, 30), (140, 220), (60, 220)], fill=(shade, 74, 52))
    path = tmp_path / name
    img.save(path)
    return path


def test_a_good_fit_round_trips(tmp_path, store):
    plate = _plate(tmp_path)
    measured = pl.measure_face(Image.open(plate))
    assert pl.save_plate_geometry(plate, measured) is True
    assert store.is_file()
    cached = pl.load_plate_geometry(plate)
    assert cached is not None
    assert [list(p) for p in cached["quad"]] == [list(p) for p in measured["quad"]]


def test_a_bad_fit_is_never_cached(tmp_path, store):
    plate = _plate(tmp_path)
    measured = pl.measure_face(Image.open(plate))
    measured["geom_residual_px"] = pl.MAX_GEOM_RESIDUAL_PX + 1.0
    assert pl.save_plate_geometry(plate, measured) is False
    assert not store.is_file()


def test_a_different_plate_never_inherits_a_fit(tmp_path, store):
    one = _plate(tmp_path, "one.png")
    two = _plate(tmp_path, "two.png", shade=80)
    pl.save_plate_geometry(one, pl.measure_face(Image.open(one)))
    assert pl.load_plate_geometry(one) is not None
    assert pl.load_plate_geometry(two) is None


def test_compose_reuses_the_stored_fit(tmp_path, store, monkeypatch):
    plate = _plate(tmp_path)
    calls = {"n": 0}
    real = pl.measure_face

    def counting(img, **kw):
        calls["n"] += 1
        return real(img, **kw)

    monkeypatch.setattr(pl, "measure_face", counting)

    first = pl.compose(plate, title="TEST")
    assert first["geometry_reused"] is False
    assert calls["n"] == 1

    second = pl.compose(plate, title="TEST")
    assert second["geometry_reused"] is True
    assert calls["n"] == 1, "the stored fit should mean no second measurement"
    assert second["quad"] == first["quad"]
    assert second["edge_feather_px"] == first["edge_feather_px"]


def test_compose_ignores_the_cache_when_asked(tmp_path, store):
    plate = _plate(tmp_path)
    pl.compose(plate, title="TEST")
    again = pl.compose(plate, title="TEST", reuse_geometry=False)
    assert again["geometry_reused"] is False
