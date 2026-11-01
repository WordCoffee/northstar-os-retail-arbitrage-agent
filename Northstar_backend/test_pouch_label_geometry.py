"""L2 geometry: sub-pixel side fit, measured bow, mesh, and the refusal guard.

The old measurement fitted a straight line to each side. A real pouch bows at
mid-height, so the print sat on a chord while the pack curved away from it. L2
fits a robust quadratic, turns its departure from the chord into a mesh bow, and
refuses to composite when the measured edge and the mesh disagree.

Synthetic plates are used for the hard numbers because their true edge is known.
The operator plate is covered by the acceptance probe, not by a unit test (its
props and shadows are not reproducible in CI).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import mockup_compositor as mc
import pouch_label as pl


def _bowed_plate(path: Path, *, w: int = 600, h: int = 900,
                 top: int = 100, bottom: int = 800,
                 left: int = 150, right: int = 450, bow: float = 6.0) -> Path:
    """A pouch whose sides bow outward by `bow` px at mid-height."""
    img = Image.new("RGB", (w, h), (238, 231, 219))
    d = ImageDraw.Draw(img)
    ys = np.arange(top, bottom + 1)
    t = (ys - top) / float(bottom - top)
    xl = left - bow * np.sin(np.pi * t)
    xr = right + bow * np.sin(np.pi * t)
    pts = [(float(x), float(y)) for x, y in zip(xl, ys)]
    pts += [(float(x), float(y)) for x, y in zip(xr[::-1], ys[::-1])]
    d.polygon(pts, fill=(32, 74, 52))
    img.save(path)
    return path


def _straight_plate(path: Path, **kw) -> Path:
    return _bowed_plate(path, bow=0.0, **kw)


def test_measure_face_recovers_a_known_bow(tmp_path):
    plate = _bowed_plate(tmp_path / "bowed.png", bow=6.0)
    m = pl.measure_face(Image.open(plate))
    assert m["fit"]["left"] == "quadratic"
    assert m["fit"]["right"] == "quadratic"
    # The panel is inset 20% top / 10% bottom, so its mid-height is below the
    # plate's bow peak; the sine coefficient is therefore smaller than the 6 px
    # maximum, but its sign and magnitude are still the measured truth.
    assert 2.0 < m["bow_left_px"] < 5.0, m["bow_left_px"]
    assert 1.5 < m["bow_right_px"] < 5.0, m["bow_right_px"]
    assert m["geom_residual_px"] is not None
    assert m["geom_residual_px"] < 0.5, m["geom_residual_by_side"]


def test_a_straight_plate_reports_no_bow_and_no_mesh(tmp_path):
    plate = _straight_plate(tmp_path / "straight.png")
    m = pl.measure_face(Image.open(plate))
    assert abs(m["bow_left_px"]) < 1.0
    assert abs(m["bow_right_px"]) < 1.0
    assert m["geom_residual_px"] < 0.5

    out = pl.compose(plate, title="TEST", subtitle="STRAIGHT")
    assert out["mesh"] is None, "a straight edge must not be bowed by noise"


def test_mesh_moves_the_mid_edge_by_more_than_a_pixel(tmp_path):
    plate = _bowed_plate(tmp_path / "bowed.png", bow=6.0)
    out = pl.compose(plate, title="TEST", subtitle="BOWED", mesh=True)
    flat = pl.compose(plate, title="TEST", subtitle="BOWED", mesh=False)
    assert out["mesh"] == [pl.MESH_NX, pl.MESH_NY]
    assert flat["mesh"] is None

    a = np.asarray(Image.open(__import__("io").BytesIO(out["bytes"]))).astype(np.int16)
    b = np.asarray(Image.open(__import__("io").BytesIO(flat["bytes"]))).astype(np.int16)
    diff = np.abs(a - b).max(axis=2)
    assert diff.max() >= 16, f"mesh and homography are indistinguishable (max {diff.max()})"
    # the difference must be on the sides, not scattered over the whole plate
    h, w = diff.shape
    assert (diff[:, : int(w * 0.35)] > 8).sum() > 200


def test_compose_refuses_when_the_measured_edge_is_not_consistent(tmp_path, monkeypatch):
    plate = _straight_plate(tmp_path / "straight.png")
    monkeypatch.setattr(pl, "measure_face", lambda img: {
        "quad": [[100, 200], [400, 200], [400, 700], [100, 700]],
        "geom_residual_px": pl.MAX_GEOM_RESIDUAL_PX + 0.5,
        "geom_residual_by_side": {"left": 2.1, "right": 1.9},
        "bow_left_px": 0.0,
        "bow_right_px": 0.0,
        "face": None, "background": None, "coverage": None,
    })
    with pytest.raises(ValueError) as exc:
        # This assertion is about a fresh measurement; a cache entry written by
        # an earlier test with the same fixture image would hide the bad fit.
        pl.compose(plate, title="TEST", reuse_geometry=False)
    assert "residual" in str(exc.value).lower()
    assert "operator quad" in str(exc.value).lower()


def test_mesh_grid_accepts_a_per_side_bow():
    quad = [[0, 0], [100, 0], [100, 100], [0, 100]]
    # positive is outward: left moves to -x, right to +x
    grid = mc.mesh_grid(quad, nx=5, ny=9, bow_x=(6.0, -2.0))
    mid = 4  # ny=9 -> t = 0.5
    assert grid[mid, 0, 0] == pytest.approx(-6.0)
    assert grid[mid, -1, 0] == pytest.approx(98.0)
    # the corners are untouched, which is why the homography stays exact there
    assert grid[0, 0, 0] == pytest.approx(0.0)
    assert grid[-1, -1, 0] == pytest.approx(100.0)
