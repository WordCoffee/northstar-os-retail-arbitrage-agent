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
