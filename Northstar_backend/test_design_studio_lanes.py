"""Design Studio lanes tests — endpoints, gating, and asset registration.

The cutout lane needs the live local engine, so its GPU call is monkeypatched:
tests assert the ENDPOINT contract (auth, 404, asset registration, metadata),
never a real render.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_api  # noqa: E402
import design_studio_lanes as dsl  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402


def _png_bytes(size=(400, 400), box=(150, 100, 250, 300), bg=(245, 245, 245)) -> bytes:
    img = Image.new("RGB", size, bg)
    ImageDraw.Draw(img).rectangle(box, fill=(30, 60, 45))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _cutout_bytes(size=(400, 400), box=(150, 100, 250, 300)) -> bytes:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle(box, fill=(30, 60, 45, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _Assets:
    def __init__(self, files: dict):
        self.files = files
        self.created = []

    def get_by_id(self, aid, account_id=None):
        name = self.files.get(aid)
        if not name:
            return None
        return {"id": aid, "storage_key": name, "project_id": "p1", "name": "render"}

    def create(self, data):
        self.created.append(data)
        return f"aid-{len(self.created)}"


class _DB:
    def __init__(self, files):
        class _DS:
            def __init__(self):
                self.assets = _Assets(files)
        self.design_studio = _DS()


@pytest.fixture()
def wired(monkeypatch, tmp_path):
    """A real PNG on disk plus a fake asset store that resolves to it."""
    name = "_lane_test_src.png"
    (dsl._OUT_DIR / name).write_bytes(_png_bytes())
    db = _DB({"src": name})
    monkeypatch.setattr(dsl, "get_northstar_db", lambda: db)
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-lanes"
    try:
        yield db, name
    finally:
        app.dependency_overrides = {}
        (dsl._OUT_DIR / name).unlink(missing_ok=True)
        for a in db.design_studio.assets.created:
            (dsl._OUT_DIR / a["storage_key"]).unlink(missing_ok=True)


def test_lanes_require_auth():
    c = TestClient(app)
    assert c.get("/api/design-studio/lanes/status").status_code == 401
    assert c.post("/api/design-studio/lanes/upscale",
                  json={"asset_id": "src"}).status_code == 401


def test_status_reports_each_lane_honestly(wired):
    r = TestClient(app).get("/api/design-studio/lanes/status")
    assert r.status_code == 200, r.text
    lanes = r.json()["lanes"]
    assert set(lanes) >= {"cutout", "upscale", "main_check", "prepress"}
    assert lanes["upscale"]["available"] is True
    assert lanes["upscale"]["gpu"] is False
    assert lanes["main_check"]["available"] is True
    assert lanes["cutout"]["model"].endswith(".safetensors")


def test_upscale_lane_creates_an_asset(wired):
    db, _name = wired
    r = TestClient(app).post("/api/design-studio/lanes/upscale",
                             json={"asset_id": "src", "factor": 2.0})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["asset_id"] == "aid-1"
    created = db.design_studio.assets.created[0]
    lane = created["metadata"]["lane"]
    assert lane["name"] == "upscale" and lane["factor"] == 2.0
    assert lane["size"] == [800, 800] and lane["gpu"] is False
    assert (dsl._OUT_DIR / created["storage_key"]).is_file()


def test_upscale_lane_rejects_a_bad_factor(wired):
    r = TestClient(app).post("/api/design-studio/lanes/upscale",
                             json={"asset_id": "src", "factor": 1.0})
    assert r.status_code == 422


def test_main_check_lane_reports_blockers_on_a_raw_render(wired, monkeypatch):
    # a distinctly non-white background: 200,200,200 is nowhere near the 245 bar
    name = "_lane_test_grey.png"
    (dsl._OUT_DIR / name).write_bytes(_png_bytes(bg=(200, 200, 200)))
    monkeypatch.setattr(dsl, "get_northstar_db",
                        lambda: _DB({"grey": name}))
    try:
        r = TestClient(app).post("/api/design-studio/lanes/main-check",
                                 json={"asset_id": "grey"})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verdict"] == "blocked"
        assert any("not pure white" in b for b in body["blockers"]), body["blockers"]
    finally:
        (dsl._OUT_DIR / name).unlink(missing_ok=True)


def test_main_check_lane_passes_a_framed_main(wired, monkeypatch):
    import image_prep as ip
    framed = ip.frame_on_white_bytes(_cutout_bytes(), fill=0.88, size=2000)
    name = "_lane_test_main.png"
    (dsl._OUT_DIR / name).write_bytes(framed["bytes"])
    db = _DB({"main": name})
    monkeypatch.setattr(dsl, "get_northstar_db", lambda: db)
    try:
        r = TestClient(app).post("/api/design-studio/lanes/main-check",
                                 json={"asset_id": "main"})
        assert r.status_code == 200
        body = r.json()
        assert body["verdict"] == "compliant", body["blockers"]
        assert body["fill_longest_side"] > 0.85
    finally:
        (dsl._OUT_DIR / name).unlink(missing_ok=True)


def test_cutout_lane_registers_cutout_and_main_and_records_compliance(wired, monkeypatch):
    import studio_generation as sg

    def fake_cutout(image_bytes, **_kw):
        # a real RGBA cutout, produced without the GPU
        from PIL import Image
        img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
        ImageDraw.Draw(img).rectangle([150, 100, 250, 300], fill=(30, 60, 45, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return {"bytes": buf.getvalue(), "model": "birefnet.safetensors",
                "provider": "comfyui", "ext": "png", "mime": "image/png"}

    monkeypatch.setattr(sg, "generate_cutout", fake_cutout)
    db, _name = wired
    r = TestClient(app).post("/api/design-studio/lanes/cutout",
                             json={"asset_id": "src", "fill": 0.88, "size": 2000})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cutout"]["asset_id"] == "aid-1"
    assert body["framed"]["asset_id"] == "aid-2"
    assert body["compliance"]["verdict"] == "compliant", body["compliance"]
    roles = [a["asset_type"] for a in db.design_studio.assets.created]
    assert roles == ["cutout", "listing_image"]


def test_cutout_lane_surfaces_an_unarmed_engine(wired, monkeypatch):
    import studio_generation as sg

    def disarmed(image_bytes, **_kw):
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")

    monkeypatch.setattr(sg, "generate_cutout", disarmed)
    r = TestClient(app).post("/api/design-studio/lanes/cutout",
                             json={"asset_id": "src"})
    assert r.status_code == 409
    assert "disarmed" in r.text


def test_lane_404s_on_an_unknown_asset(wired):
    r = TestClient(app).post("/api/design-studio/lanes/main-check",
                             json={"asset_id": "nope"})
    assert r.status_code == 404
