"""Mockup compositor tests — homography, erase, panels, icons, service endpoint.

Offline: pure PIL/numpy. The endpoint happy-path uses the REAL dev plate file
(read-only) with a synthetic logo supplied as a data-url; its output file is
cleaned up after the assertion.
"""

from __future__ import annotations

import base64
import io
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mockup_compositor as mc  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
import design_studio_api  # noqa: E402
import design_studio_compose as dsc  # noqa: E402
from main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent
DEV_PLATE = ROOT / "data" / "studio_generated" / "44318b36606f4c859487c250d5a0a671.png"


# ── primitives ──────────────────────────────────────────────────────────────

def test_homography_maps_panel_corners_to_quad():
    plate = Image.new("RGB", (400, 400), (255, 255, 255))
    panel = Image.new("RGBA", (100, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 0, 14, 14], fill=(255, 0, 0, 255))
    d.rectangle([85, 0, 99, 14], fill=(0, 0, 255, 255))
    d.rectangle([85, 185, 99, 199], fill=(0, 255, 0, 255))
    d.rectangle([0, 185, 14, 199], fill=(255, 255, 0, 255))
    quad = [(40, 60), (360, 50), (370, 350), (30, 360)]
    out = np.array(mc.warp_panel(plate, panel, quad))
    # sample 12px inside each quad corner
    checks = [((52, 72), (255, 0, 0)), ((348, 62), (0, 0, 255)),
              ((358, 338), (0, 255, 0)), ((42, 348), (255, 255, 0))]
    for (x, y), (r, g, b) in checks:
        px = out[y, x].astype(int)
        assert abs(px[0] - r) < 45 and abs(px[1] - g) < 45 and abs(px[2] - b) < 45, (x, y, px)


def test_erase_circle_removes_disk_and_keeps_surroundings():
    plate = Image.new("RGB", (600, 600), (120, 150, 130))
    d = ImageDraw.Draw(plate)
    d.ellipse([250, 200, 450, 400], fill=(220, 40, 40))
    out = mc.erase_circle(plate, (350, 300), r=110)
    arr = np.array(out).astype(int)
    cx = arr[300, 350]
    assert abs(cx[0] - 120) < 40 and abs(cx[1] - 150) < 40, f"center not recoloured: {cx}"
    assert not (cx[0] > 180 and cx[1] < 90), "red disk survived"
    far = arr[40, 40]
    assert abs(far[0] - 120) < 10 and abs(far[1] - 150) < 10, "surroundings changed"
    # disk edges are gone: sample just inside old radius
    edge = arr[300, 462]
    assert not (edge[0] > 190 and edge[1] < 90), f"red ring survived: {edge}"


def test_render_panel_badge_title_icons_footer():
    logo = Image.new("RGBA", (200, 160), (252, 252, 252, 255))
    ImageDraw.Draw(logo).rectangle([60, 70, 140, 100], fill=(60, 40, 30, 255))
    tpl = mc.DEFAULT_TEMPLATES["mogra-forest-dusk"]
    panel = mc.render_panel(
        size=tpl["panel"]["size"], badge=tpl["badge"],
        title={**tpl["title"], "text": "ORGANIC LION'S MANE"},
        subtitle=tpl["subtitle"], glyph=None,
        icons=tpl["icons"], footer={**tpl["footer"], "text": "6 oz (170 g)"},
        logo=logo, glyph_img=None, gold=(196, 160, 74), field_color=(252, 252, 252),
    )
    a = np.array(panel)
    assert a[300, 350, 3] == 255, "badge centre not painted"
    assert tuple(int(v) for v in a[300, 350, :3]) == (60, 40, 30), "logo ink missing at badge centre"
    assert tuple(int(v) for v in a[160, 350, :3]) == (252, 252, 252), "badge field colour mismatch"
    title_row = a[560, 100:600, :]
    assert (title_row[:, 3] > 0).sum() > 20, "title pixels missing"
    footer_row = a[942, 130:260, :]
    assert (footer_row[:, 3] > 0).sum() > 5, "footer rule missing"
    icon_row = a[872, 200:500, :]
    assert (icon_row[:, 3] > 0).sum() > 20, "icons missing"


def test_cert_icons_draw_ink():
    for kind in mc._ICON_SPECS:
        img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
        mc.draw_cert_icon(ImageDraw.Draw(img), kind, 40, 40, 30,
                          ink=(196, 160, 74), ring=(196, 160, 74), disc=(245, 238, 226))
        a = np.array(img)
        assert a[..., 3].max() > 0, f"{kind}: nothing drawn"


def test_prepare_logo_crops_inside_frame():
    raw = Image.new("RGB", (500, 400), (240, 236, 220))  # cream frame band
    ImageDraw.Draw(raw).rectangle([60, 55, 440, 345], fill=(255, 255, 255))
    p = ROOT / "data" / "compose_tmp"
    p.mkdir(parents=True, exist_ok=True)
    f = p / "_test_logo.png"
    raw.save(f)
    try:
        inner, field = mc.prepare_logo(f, frame_crop=52)
        assert inner.width < raw.width and inner.height < raw.height
        assert all(c > 200 for c in field), f"field colour not light: {field}"
    finally:
        f.unlink(missing_ok=True)


def test_compose_mockup_synthetic_plate(tmp_path):
    plate = Image.new("RGB", (800, 500), (245, 245, 245))
    d = ImageDraw.Draw(plate)
    d.rounded_rectangle([80, 120, 340, 460], radius=24, fill=(40, 60, 45))
    d.rounded_rectangle([420, 120, 700, 460], radius=24, fill=(40, 40, 42))
    plate_p = tmp_path / "plate.png"
    plate.save(plate_p)
    logo = Image.new("RGBA", (200, 160), (252, 252, 252, 255))
    ImageDraw.Draw(logo).rectangle([70, 75, 130, 95], fill=(60, 40, 30, 255))
    logo_p = tmp_path / "logo.png"
    logo.save(logo_p)
    out = tmp_path / "out.png"
    res = mc.compose_mockup(
        template_id="mogra-forest-dusk", plate_path=plate_p, logo_path=logo_p, out_path=out,
        quads=[[[90, 130], [330, 128], [336, 450], [84, 452]],
               [[430, 128], [690, 130], [694, 452], [426, 450]]],
        skus=[{"title": "ORGANIC LION'S MANE", "weight": "6 oz (170 g)", "gold": [196, 160, 74]},
              {"title": "ORGANIC SHIITAKE", "weight": "8 oz (227 g)", "gold": [214, 158, 62]}],
        erases=[], glyph_box=None, shading=0.5,
    )
    assert out.is_file() and res["quads"] == 2
    a = np.array(Image.open(out)).astype(int)
    before = np.array(plate).astype(int)
    # text block changed pixels on both faces
    assert np.abs(a[300:320, 120:300] - before[300:320, 120:300]).mean() > 2, "face 1 unchanged"
    assert np.abs(a[300:320, 460:640] - before[300:320, 460:640]).mean() > 2, "face 2 unchanged"


def test_erase_rect_clears_strip_and_keeps_surroundings():
    plate = Image.new("RGB", (600, 400), (110, 140, 120))
    d = ImageDraw.Draw(plate)
    d.rectangle([180, 170, 420, 230], fill=(230, 60, 60))
    out = np.array(mc.erase_rect(plate, [180, 170, 420, 230]))
    inner = out[200, 300].astype(int)
    assert abs(inner[0] - 110) < 40 and abs(inner[1] - 140) < 40, f"strip not cleared: {inner}"
    far = out[20, 20].astype(int)
    assert abs(far[0] - 110) < 10 and abs(far[1] - 140) < 10, "surroundings changed"


# ── service endpoint ────────────────────────────────────────────────────────

class _Assets:
    def __init__(self):
        self.created = None

    def get_by_id(self, aid, account_id=None):
        if aid == "plate-dev":
            return {"id": aid, "storage_key": DEV_PLATE.name, "project_id": None}
        return None

    def create(self, data):
        self.created = data
        return "aid-test"


class _DS:
    def __init__(self):
        self.assets = _Assets()


class _DB:
    def __init__(self):
        self.design_studio = _DS()


def _as_org():
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-compose"


def _tiny_logo_data_url() -> str:
    img = Image.new("RGB", (300, 240), (240, 236, 220))
    ImageDraw.Draw(img).rectangle([70, 60, 230, 180], fill=(255, 255, 255))
    ImageDraw.Draw(img).rectangle([120, 100, 180, 130], fill=(60, 40, 30))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_compose_endpoints(monkeypatch):
    assert TestClient(app).post("/api/design-studio/compose/mockup",
                                json={"template_id": "mogra-forest-dusk",
                                      "plate_asset_id": "x"}).status_code == 401
    _as_org()
    try:
        c = TestClient(app)
        r = c.get("/api/design-studio/compose/templates")
        assert r.status_code == 200 and r.json()["templates"], r.text
        r = c.get("/api/design-studio/compose/presets")
        assert r.status_code == 200

        db = _DB()
        monkeypatch.setattr(dsc, "get_northstar_db", lambda: db)
        r = c.post("/api/design-studio/compose/mockup",
                   json={"template_id": "mogra-forest-dusk", "plate_asset_id": "missing"})
        assert r.status_code == 404

        if not DEV_PLATE.is_file():
            pytest.skip("dev plate not on disk")
        out_name = "_test_compose_out.png"
        r = c.post("/api/design-studio/compose/mockup",
                   json={"template_id": "mogra-forest-dusk", "plate_asset_id": "plate-dev",
                         "out_name": out_name, "logo_data_url": _tiny_logo_data_url()})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["asset_id"] == "aid-test" and body["file_url"].endswith("/file")
        assert db.design_studio.assets.created["metadata"]["compositor"]["template_id"] == "mogra-forest-dusk"
        produced = ROOT / "data" / "studio_generated" / out_name
        assert produced.is_file()
        produced.unlink()
    finally:
        app.dependency_overrides = {}


# ── mesh warp (REA 1.1 candidate L1) ─────────────────────────────────────────
# The numbers these tests defend: a 4-point homography left 5.413 px of mean
# error on a synthetic curved face, a 5x7 mesh left 0.676 px
# (reports/rea_probe/warp_probe.json).

_PW, _PH = 600, 800
_F, _D, _R, _ARC = 1000.0, 1200.0, 300.0, 0.90
_CW, _CH = 900, 1100
_CX, _CY, _PLANE_H = _CW / 2.0, _CH / 2.0, 760.0


def _cyl_forward(u, v):
    import math
    t = (u - 0.5) * _ARC
    y = (v - 0.5) * _PLANE_H
    z = _D - _R * math.cos(t)
    return _CX + _F * _R * math.sin(t) / z, _CY + _F * y / z


def _cyl_backward(px, py):
    import math
    a, b, c = (px - _CX) * _D, -(px - _CX) * _R, _F * _R
    amp = math.hypot(b, c)
    phi = math.atan2(c, b)
    t = phi - math.acos(max(-1.0, min(1.0, a / amp)))
    z = _D - _R * math.cos(t)
    return (t / _ARC + 0.5) * (_PW - 1), ((py - _CY) * z / _F / _PLANE_H + 0.5) * (_PH - 1)


def _cyl_quad():
    corners = [_cyl_forward(0, 0), _cyl_forward(1, 0), _cyl_forward(1, 1), _cyl_forward(0, 1)]
    return [(x, y) for x, y in corners]


def test_mesh_grid_with_no_bow_is_the_homography():
    plate = Image.new("RGB", (240, 300), (200, 200, 200))
    panel = Image.new("RGBA", (100, 140), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rectangle([0, 0, 99, 139], fill=(250, 40, 40, 255))
    # a parallelogram: bilinear == projective there, so the two paths must agree
    quad = [(30, 40), (200, 45), (210, 250), (40, 245)]
    flat = np.array(mc.warp_panel(plate, panel, quad)).astype(int)
    meshed = np.array(mc.warp_panel(plate, panel, quad, grid=mc.mesh_grid(quad))).astype(int)
    diff = np.abs(flat - meshed).max(axis=2)
    # only the sub-pixel edge can differ; the body of the panel must be identical
    assert (diff > 2).mean() < 0.01, f"{(diff > 2).mean():.3%} of pixels differ"


def test_mesh_recovers_a_curved_face_to_sub_pixel():
    """Refined panel coords must agree with the analytic inverse of the surface.

    The residual floor is structural: a 9x13 bilinear mesh approximates a true
    cylinder with straight chords, so ~0.4 panel px of error remains no matter how
    many Newton iterations run. That floor is the finding, not a bug.
    """
    quad = _cyl_quad()
    grid = np.array([[_cyl_forward(i / 8.0, j / 12.0) for i in range(9)] for j in range(13)])
    H = mc._homography([(0, 0), (_PW - 1, 0), (_PW - 1, _PH - 1), (0, _PH - 1)], quad)
    Hinv = np.linalg.inv(H)

    truth_uv = [(u, v) for v in np.linspace(0.06, 0.94, 15) for u in np.linspace(0.06, 0.94, 11)]
    dest = np.array([_cyl_forward(u, v) for u, v in truth_uv], float)
    truth = np.array([(u * (_PW - 1), v * (_PH - 1)) for u, v in truth_uv])

    pts = np.stack([dest[:, 0], dest[:, 1], np.ones(len(dest))], axis=-1)
    uv = pts @ Hinv.T
    u0, v0 = uv[..., 0] / uv[..., 2], uv[..., 1] / uv[..., 2]

    u1, v1 = mc._refine_to_mesh(u0.copy(), v0.copy(), dest[:, 0], dest[:, 1],
                                grid, float(_PW), float(_PH))

    raw = np.hypot(u0 - truth[:, 0], v0 - truth[:, 1])
    refined = np.hypot(u1 - truth[:, 0], v1 - truth[:, 1])

    assert raw.mean() > 1.5, f"fixture too easy: homography mean {raw.mean():.3f} panel px"
    assert refined.mean() < 0.5, f"mesh mean {refined.mean():.3f} panel px"
    assert refined.max() < 1.0, f"mesh max {refined.max():.3f} panel px"
    assert refined.mean() < raw.mean() / 4


def test_bowed_mesh_actually_curves_the_edges():
    plate = Image.new("RGB", (400, 420), (210, 210, 210))
    panel = Image.new("RGBA", (120, 200), (0, 0, 0, 0))
    d = ImageDraw.Draw(panel)
    d.rectangle([0, 0, 119, 199], fill=(20, 20, 20, 255))
    d.rectangle([0, 0, 8, 199], fill=(250, 30, 30, 255))     # left marker column
    quad = [(80, 60), (320, 55), (330, 360), (70, 365)]
    flat = np.array(mc.warp_panel(plate, panel, quad))
    bowed = np.array(mc.warp_panel(plate, panel, quad,
                                   grid=mc.mesh_grid(quad, nx=7, ny=9, bow_x=18.0)))
    diff = np.abs(flat.astype(int) - bowed.astype(int)).max(axis=2)
    assert (diff > 40).sum() > 500, "bow produced no visible change"

    def leftmost_red(img, row):
        line = img[row]
        red = (line[:, 0].astype(int) > 170) & (line[:, 1].astype(int) < 90) & (line[:, 2].astype(int) < 90)
        xs = np.where(red)[0]
        return int(xs.min()) if xs.size else None

    top, middle = 120, 210
    ft, fm = leftmost_red(flat, top), leftmost_red(flat, middle)
    bt, bm = leftmost_red(bowed, top), leftmost_red(bowed, middle)
    assert None not in (ft, fm, bt, bm), "marker column missing"
    # a bowed left edge sits further out (smaller x) at mid-height than at the top
    assert (ft - fm) <= 6, "the flat quad should barely change with height"
    assert (bm - bt) <= -8, f"bowed edge did not bow outward: top {bt}, mid {bm}"



