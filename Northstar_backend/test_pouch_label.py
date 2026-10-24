"""Render sizing + the deterministic label lane.

Two operator-visible defects are locked down here:

  1. `generate_image` rejected a perfectly ordinary portrait request with
     "height is above the maximum (1216)". The engine's real limit is its long
     edge, so a request is now FITTED into that box with the aspect ratio kept,
     and the true size is reported back.
  2. A rendered pouch came back as a blank bag — correct for the image model
     (it may never paint text), useless as a deliverable. `apply_label` now
     composites the operator's real logo and real copy onto the render.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

import chat_tools
import pouch_label
import studio_generation as sg


# ── 1. fitting a requested size into the engine box ─────────────────────────

@pytest.mark.parametrize("req,expected", [
    ((832, 1216), (832, 1216)),     # already inside the box: untouched
    ((896, 1344), (816, 1216)),     # 2:3 portrait, long edge capped
    ((1024, 1536), (816, 1216)),    # same ratio stated differently
    ((1536, 1024), (1216, 816)),    # landscape keeps its ratio
    ((1024, 1024), (1024, 1024)),
    ((2048, 2048), (1216, 1216)),
])
def test_fit_box_keeps_the_aspect_ratio(req, expected):
    assert sg._fit_box(*req) == expected


def test_fit_box_never_exceeds_the_engine_edge_and_stays_on_the_latent_grid():
    for w, h in [(4000, 3000), (3000, 4000), (64, 64), (900, 100), (100, 900)]:
        fw, fh = sg._fit_box(w, h)
        assert max(fw, fh) <= 1216
        assert fw % 16 == 0 and fh % 16 == 0


def test_fit_box_preserves_ratio_within_one_step():
    fw, fh = sg._fit_box(896, 1344)
    assert abs((fw / fh) - (896 / 1344)) < 0.03


def test_generate_image_reports_the_size_it_actually_used(monkeypatch, tmp_path):
    monkeypatch.setattr(sg, "media_live_armed", lambda: True)
    monkeypatch.setattr(sg, "unload_brain", lambda: True)
    monkeypatch.setattr(sg, "release_models", lambda: True)
    monkeypatch.setattr(sg, "_run_graph_guarded",
                        lambda graph, timeout_s=None, on_progress=None:
                        [{"filename": "x.png"}])
    monkeypatch.setattr(sg, "_fetch_output", lambda img: b"pngbytes")
    out = sg.generate_image("a kraft pouch", width=896, height=1344)
    assert (out["width"], out["height"]) == (816, 1216)
    assert out["fitted"] is True
    assert out["requested"] == {"width": 896, "height": 1344}


# ── 2. the label lane ───────────────────────────────────────────────────────

def _pouch_plate(path: Path, size=(768, 1216)) -> Path:
    """A stand-in plate: a tapered pouch on a plain background."""
    img = Image.new("RGB", size, (235, 228, 218))
    d = ImageDraw.Draw(img)
    w, h = size
    d.polygon([(w * 0.18, h * 0.16), (w * 0.82, h * 0.16),
               (w * 0.76, h * 0.86), (w * 0.24, h * 0.86)], fill=(32, 74, 52))
    img.save(path)
    return path


def _logo(path: Path) -> Path:
    img = Image.new("RGBA", (400, 300), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse([120, 60, 280, 220], outline=(150, 40, 40, 255), width=12)
    img.save(path)
    return path


def test_measure_face_finds_a_tapered_quad(tmp_path):
    plate = Image.open(_pouch_plate(tmp_path / "plate.png"))
    m = pouch_label.measure_face(plate)
    tl, tr, br, bl = m["quad"]
    # top edge is horizontal and narrower at the top of a tapered pouch
    assert tl[1] == tr[1] and bl[1] == br[1]
    assert (tr[0] - tl[0]) > (br[0] - bl[0])
    assert m["face"]["top"] < m["face"]["bottom"]


def test_measure_face_refuses_a_blank_image(tmp_path):
    p = tmp_path / "blank.png"
    Image.new("RGB", (400, 400), (255, 255, 255)).save(p)
    with pytest.raises(ValueError):
        pouch_label.measure_face(Image.open(p))


def test_compose_writes_a_png_and_reports_the_fit(tmp_path):
    plate = _pouch_plate(tmp_path / "plate.png")
    logo = _logo(tmp_path / "logo.png")
    out = pouch_label.compose(
        plate, title="Lion's Mane", subtitle="Organic Mushroom Powder",
        weight="NET WT 6 OZ (170 g)", logo_path=logo,
        icons=["organic_sprout", "non_gmo"],
    )
    assert out["bytes"][:8] == b"\x89PNG\r\n\x1a\n"
    assert out["size"] == [768, 1216]
    assert out["has_logo"] is True
    assert len(out["quad"]) == 4
    assert "mockup fit" in out["note"].lower()


def test_compose_requires_a_title(tmp_path):
    plate = _pouch_plate(tmp_path / "plate.png")
    with pytest.raises(ValueError):
        pouch_label.compose(plate, title="   ")


def test_a_white_background_logo_is_keyed_not_left_as_a_blue_box(tmp_path):
    logo = _logo(tmp_path / "logo.png")
    img = pouch_label.load_logo(logo)
    assert img.mode == "RGBA"
    corner = img.getpixel((0, 0))
    assert corner[3] == 0, "the white field must be transparent, not opaque"


# ── 3. the chat tool ────────────────────────────────────────────────────────

class _Assets:
    def __init__(self, store):
        self.store = store

    def get_by_id(self, aid, account_id=None):
        for rec in self.store:
            if rec["id"] == aid:
                return dict(rec)
        return None

    def create(self, rec):
        aid = f"asset-{len(self.store) + 1}"
        self.store.append({"id": aid, **rec})
        return aid


class _DS:
    def __init__(self, store):
        self.assets = _Assets(store)


class _DB:
    def __init__(self, store):
        self.design_studio = _DS(store)


def _wire(tmp_path, monkeypatch):
    out_dir = tmp_path / "generated"
    out_dir.mkdir()
    monkeypatch.setattr(chat_tools, "_out_dir", lambda: out_dir)
    (out_dir / "plate.png").write_bytes(
        _pouch_plate(tmp_path / "p.png").read_bytes())
    (out_dir / "logo.png").write_bytes(_logo(tmp_path / "l.png").read_bytes())
    store = [
        {"id": "plate-1", "storage_key": "plate.png", "name": "kraft render",
         "asset_type": "generated-image", "width": 768, "height": 1216},
        {"id": "logo-1", "storage_key": "logo.png", "name": "logo.png",
         "asset_type": "uploaded", "width": 400, "height": 300},
    ]
    return _DB(store), out_dir


def test_apply_label_produces_a_new_asset(tmp_path, monkeypatch):
    db, out_dir = _wire(tmp_path, monkeypatch)
    ctx = {"db": db, "account_id": "acct-1"}
    res = chat_tools.run_tool("apply_label", {
        "plate_asset_id": "plate-1", "logo_asset_id": "logo-1",
        "title": "Lion's Mane", "subtitle": "Organic Mushroom Powder",
        "weight": "NET WT 6 OZ (170 g)",
        "icons": ["organic_sprout"],
    }, ctx)
    assert res["ok"] is True, res.get("error")
    assert res["assets"][0]["kind"] == "image"
    assert "logo" in res["summary"].lower()
    created = db.design_studio.assets.store[-1]
    assert created["asset_type"] == "composite"
    assert (out_dir / created["storage_key"]).is_file()
    assert created["metadata"]["label"]["plate_asset_id"] == "plate-1"


def test_apply_label_is_honest_about_a_missing_plate(tmp_path, monkeypatch):
    db, _ = _wire(tmp_path, monkeypatch)
    res = chat_tools.run_tool("apply_label", {
        "plate_asset_id": "nope", "title": "x"}, {"db": db, "account_id": "acct-1"})
    assert res["ok"] is False
    assert "not found" in res["summary"].lower()
    assert "nope" in res["error"]


def test_apply_label_is_honest_about_a_missing_logo(tmp_path, monkeypatch):
    db, _ = _wire(tmp_path, monkeypatch)
    res = chat_tools.run_tool("apply_label", {
        "plate_asset_id": "plate-1", "logo_asset_id": "nope",
        "title": "x"}, {"db": db, "account_id": "acct-1"})
    assert res["ok"] is False
    assert "logo" in res["summary"].lower()


def test_apply_label_is_registered_and_offered():
    assert "apply_label" in chat_tools.tool_names()
    names = [t["function"]["name"] for t in chat_tools.ollama_tool_schemas()]
    assert "apply_label" in names
    creative = next(s for s in chat_tools.SERVICES if s["id"] == "creative")
    assert "apply_label" in creative["tools"]


def test_generate_image_accepts_a_portrait_request_at_the_schema_level():
    props = chat_tools.TOOLS["generate_image"]["parameters"]["properties"]
    assert props["height"]["maximum"] >= 1344
    # a 2:3 portrait now validates instead of raising "above the maximum"
    out = chat_tools.validate_tool_arguments(
        chat_tools.TOOLS["generate_image"],
        {"prompt": "pouch", "width": 896, "height": 1344})
    assert out["height"] == 1344
