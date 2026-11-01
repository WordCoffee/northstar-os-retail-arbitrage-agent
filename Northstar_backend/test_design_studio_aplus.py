"""Design Studio A+ service: kinds, render, registration, refusal.

The endpoint is exercised directly with a stub asset store so the test asserts
this service's behaviour (paths, sizes, QA wiring, refusal) and not the shape of
the whole app's router table.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import aplus_render as ar
import design_studio_aplus as svc

ACCT = "acct-test"


class _Assets:
    def __init__(self, files: dict, keys: dict):
        self._files = files      # asset_id -> storage_key
        self._keys = keys
        self.created = []

    def get_by_id(self, asset_id, account_id=None):
        key = self._keys.get(asset_id)
        return {"id": asset_id, "storage_key": key, "project_id": "proj-1"} if key else None

    def create(self, doc):
        self.created.append(doc)
        return f"asset-{len(self.created)}"


def _db(files: dict, keys: dict):
    return SimpleNamespace(design_studio=SimpleNamespace(assets=_Assets(files, keys)))


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Two plates on disk in the service's output dir, and a stub DB."""
    svc._OUT_DIR = tmp_path
    plate = tmp_path / "plate.png"
    Image.new("RGB", (1400, 1400), (246, 242, 234)).save(plate)
    tile = tmp_path / "tile.png"
    Image.new("RGB", (900, 900), (232, 228, 220)).save(tile)
    assets = _db({}, {"plate-1": plate.name, "tile-1": tile.name})
    monkeypatch.setattr(svc, "get_northstar_db", lambda: assets)
    return assets.design_studio.assets, tmp_path


def test_kinds_lists_every_module_at_its_canvas_size():
    out = svc.aplus_kinds()
    kinds = {k["kind"]: k for k in out["kinds"]}
    assert kinds["header"] == {"kind": "header", "width": 970, "height": 600,
                               "tiles": 0, "has_copy_band": True}
    assert kinds["three_tiles"]["tiles"] == 3
    assert kinds["four_tiles"]["tiles"] == 4
    assert kinds["comparison"]["width"] == 970
    assert out["defaults"] == ["header", "three_tiles", "comparison"]
    assert out["max_bytes"] == 2 * 1024 * 1024


def test_render_registers_every_module_and_a_preview(store):
    assets, out_dir = store
    body = svc.AplusRenderIn(plate_asset_id="plate-1", brand={"ink": "#1E3A2F"})
    res = svc.aplus_render_route(body, acct=ACCT)

    assert res["ok"] is True, res["problems"]
    assert [m["kind"] for m in res["modules"]] == ["header", "three_tiles", "comparison"]
    assert all(m["qa"]["ok"] for m in res["modules"])
    assert res["preview_asset_id"] == "asset-4"
    assert res["preview_url"].endswith("/file")

    created = assets.created
    assert [c["asset_type"] for c in created] == ["aplus_module"] * 3 + ["aplus_preview"]
    assert created[0]["width"] == 970 and created[0]["height"] == 600
    assert created[0]["metadata"]["aplus"]["kind"] == "header"
    assert created[0]["metadata"]["aplus"]["plate_asset_id"] == "plate-1"
    # the files really landed under the service's output directory
    for doc in created[:3]:
        assert (out_dir / doc["storage_key"]).is_file()


def test_render_uses_the_supplied_tiles(store):
    body = svc.AplusRenderIn(
        plate_asset_id="plate-1", tile_asset_ids=["tile-1"],
        modules=[svc.ModuleIn(kind="three_tiles",
                              copy={"tiles": ["One", "Two", "Three"]})])
    res = svc.aplus_render_route(body, acct=ACCT)
    assert res["ok"] is True, res["problems"]
    assert res["modules"][0]["qa"]["warnings"] == ["one image reused across the tile row"]


def test_render_refuses_prohibited_copy_before_writing(store):
    body = svc.AplusRenderIn(plate_asset_id="plate-1",
                             modules=[svc.ModuleIn(kind="header",
                                                   copy={"headline": "Only $9.99"})])
    with pytest.raises(Exception) as exc:
        svc.aplus_render_route(body, acct=ACCT)
    assert "prohibited" in str(getattr(exc.value, "detail", exc.value))


def test_render_reports_a_defect_instead_of_hiding_it(store):
    assets, _ = store
    body = svc.AplusRenderIn(plate_asset_id="plate-1",
                             modules=[svc.ModuleIn(kind="header",
                                                   copy={"headline": "Lion's Mane " * 40})])
    res = svc.aplus_render_route(body, acct=ACCT)
    assert res["ok"] is False
    assert any("header:" in p for p in res["problems"])
    assert assets.created[0]["metadata"]["aplus"]["qa"]["ok"] is False


def test_unknown_plate_is_a_404(store):
    body = svc.AplusRenderIn(plate_asset_id="missing")
    with pytest.raises(Exception) as exc:
        svc.aplus_render_route(body, acct=ACCT)
    assert getattr(exc.value, "status_code", None) == 404


def test_unknown_module_kind_is_a_422(store):
    body = svc.AplusRenderIn(plate_asset_id="plate-1",
                             modules=[svc.ModuleIn(kind="hologram")])
    with pytest.raises(Exception) as exc:
        svc.aplus_render_route(body, acct=ACCT)
    assert getattr(exc.value, "status_code", None) == 422


def test_bad_logo_payload_is_a_422(store):
    body = svc.AplusRenderIn(plate_asset_id="plate-1", logo_data_url="data:image/png;base64,!!!")
    with pytest.raises(Exception) as exc:
        svc.aplus_render_route(body, acct=ACCT)
    assert getattr(exc.value, "status_code", None) == 422
