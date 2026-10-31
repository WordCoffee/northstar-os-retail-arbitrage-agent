"""Generalized surface measurement: box, bottle, tube (and pouch delegation)."""
from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))

import surface_measure as sm

BG = (208, 208, 208)
BODY = (176, 146, 116)
SIDE = (140, 116, 92)


def _canvas(w=512, h=640):
    return Image.new("RGB", (w, h), BG)


def _png(img):
    buf = BytesIO(); img.save(buf, format="PNG"); return buf.getvalue()


def _box_front():
    img = _canvas()
    ImageDraw.Draw(img).rectangle([140, 120, 372, 520], fill=BODY)
    return img


def _box_three_quarter():
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 320, 520], fill=BODY)
    d.polygon([(320, 140), (430, 190), (430, 500), (320, 520)], fill=SIDE)
    return img


def _bottle():
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([230, 80, 282, 140], fill=BODY)
    d.polygon([(230, 140), (200, 190), (200, 540), (312, 540),
               (312, 190), (282, 140)], fill=BODY)
    return img


def _tube():
    img = _canvas()
    d = ImageDraw.Draw(img)
    d.rectangle([210, 70, 302, 90], fill=BODY)
    d.polygon([(220, 90), (292, 90), (300, 520), (212, 520)], fill=BODY)
    d.rectangle([210, 520, 302, 540], fill=BODY)
    return img


def _assert_quad_close(quad, expected, tol=4.0):
    for got, want in zip(quad, expected):
        assert abs(got[0] - want[0]) <= tol, (got, want)
        assert abs(got[1] - want[1]) <= tol, (got, want)


def test_box_front_fits_the_visible_face():
    m = sm.measure_surface(_box_front(), "box")
    assert m["method"] == "box-front"
    assert m["geom_residual_px"] <= sm.MAX_GEOM_RESIDUAL_PX
    _assert_quad_close(m["quad"], [[153.5, 143.6], [358.5, 143.6],
                                   [358.5, 496.4], [153.5, 496.4]])


def test_box_three_quarter_labels_the_larger_front_face():
    m = sm.measure_surface(_box_three_quarter(), "box")
    assert m["method"] == "box-quad"
    assert m["face_share"] > 0.5
    assert m["geom_residual_px"] <= sm.MAX_GEOM_RESIDUAL_PX
    # front face is x=120..320, y=120..520; the side face is not the target.
    _assert_quad_close(m["quad"], [[131.4, 143.6], [306.6, 143.6],
                                   [306.6, 496.4], [131.4, 496.4]])


def test_bottle_band_excludes_cap_and_shoulder():
    m = sm.measure_surface(_bottle(), "bottle")
    assert m["method"] == "bottle-band"
    assert m["band"]["top"] >= 180
    assert m["band"]["bottom"] >= 530
    assert m["geom_residual_px"] <= sm.MAX_GEOM_RESIDUAL_PX
    _assert_quad_close(m["quad"], [[204.0, 208.0], [308.0, 208.0],
                                   [308.0, 519.0], [204.0, 519.0]])


def test_tube_band_excludes_crimps_and_reports_taper():
    m = sm.measure_surface(_tube(), "tube")
    assert m["method"] == "tube-band"
    assert m["band"]["top"] >= 90
    assert m["band"]["bottom"] <= 520
    assert m["crimp_top_px"] and m["crimp_top_px"] >= 15
    assert m["crimp_bottom_px"] and m["crimp_bottom_px"] >= 15
    assert 0.05 <= m["taper"] <= 0.30
    assert m["geom_residual_px"] <= sm.MAX_GEOM_RESIDUAL_PX


def test_pouch_delegates_to_the_proven_measure_face():
    img = _canvas()
    ImageDraw.Draw(img).polygon([(120, 60), (300, 60), (310, 460), (110, 460)],
                                fill=BODY)
    m = sm.measure_surface(img, "pouch")
    assert m["kind"] == "pouch"
    assert m["method"] == "pouch-measure_face"
    assert len(m["quad"]) == 4


def test_blank_plate_is_refused_not_guessed():
    with pytest.raises(sm.SurfaceNotMeasurable):
        sm.measure_surface(_canvas(), "box")


def test_cylinder_band_refuses_a_mask_that_misses_the_body(monkeypatch):
    import numpy as np
    mask = np.zeros((640, 512), dtype=bool)
    mask[100:140, 50:460] = True      # a wide top the mask latched onto
    mask[140:540, 220:290] = True     # the real body, much narrower
    monkeypatch.setattr(sm.pl, "_foreground_mask", lambda *a, **k: mask)
    img = Image.new("RGB", (512, 640), BG)
    with pytest.raises(sm.SurfaceNotMeasurable, match="mask likely missed the body"):
        sm.measure_surface(img, "tube")


def test_unknown_format_is_refused():
    with pytest.raises(KeyError):
        sm.measure_surface(_box_front(), "sachet")


def test_measurement_is_deterministic():
    a = sm.measure_surface(_box_three_quarter(), "box")
    b = sm.measure_surface(_box_three_quarter(), "box")
    assert a["quad"] == b["quad"]
    assert a["geom_residual_px"] == b["geom_residual_px"]


def test_accepts_png_bytes():
    m = sm.measure_surface(_png(_box_front()), "box")
    assert m["method"] == "box-front"
    assert m["plate_size"] == [512, 640]


def test_quad_is_ordered_and_inside_the_plate():
    for kind, img in (("box", _box_three_quarter()), ("bottle", _bottle()),
                      ("tube", _tube())):
        m = sm.measure_surface(img, kind)
        q = m["quad"]
        assert q[0][1] < q[2][1]
        assert q[0][0] < q[1][0]
        assert q[1][0] <= q[2][0]
        for x, y in q:
            assert 0 <= x <= img.width and 0 <= y <= img.height
