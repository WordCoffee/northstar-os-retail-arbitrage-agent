"""Print master: a measured 300 DPI file, or a refusal naming the shortfall."""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import print_master as pm  # noqa: E402


def _png(size=(100, 100)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 190, 170)).save(buf, format="PNG")
    return buf.getvalue()


def _four_x(png: bytes) -> bytes:
    with Image.open(io.BytesIO(png)) as im:
        big = im.resize((im.width * 4, im.height * 4), Image.LANCZOS)
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    return buf.getvalue()


def test_a_large_enough_master_passes_at_the_requested_size():
    report = pm.master_report([4096, 4096], width_mm=300, height_mm=300)
    assert report["ok"] is True
    assert report["worst"] >= 300
    assert report["physical_mm"] == {"width": 300.0, "height": 300.0}


def test_a_small_source_reports_the_real_deficit():
    report = pm.master_report([1024, 1024], width_mm=300, height_mm=300)
    assert report["ok"] is False
    assert report["worst"] < 300
    assert report["deficit_px"]["width"] > 0


def test_make_master_upscales_and_measures():
    out = pm.make_master(_png((200, 200)), width_mm=50, height_mm=50,
                         upscaler=_four_x)
    assert out["size"] == [800, 800]
    assert out["factor"] == 4.0
    assert out["report"]["ok"] is True


def test_make_master_refuses_a_master_that_still_misses_the_target():
    with pytest.raises(pm.PrintMasterShortfall) as caught:
        pm.make_master(_png((100, 100)), width_mm=300, height_mm=300,
                       upscaler=lambda b: b)   # no upscale at all
    assert caught.value.needed_factor > 1
    assert "print_master_shortfall" in str(caught.value)


def test_make_master_refuses_a_zero_physical_size():
    with pytest.raises(ValueError):
        pm.make_master(_png(), width_mm=0, height_mm=50, upscaler=_four_x)


def test_the_package_manifest_holds_no_nulls_and_names_the_face(tmp_path):
    out = pm.make_master(_png((200, 200)), width_mm=50, height_mm=50, upscaler=_four_x)
    packaged = pm.package(out, run_id="print_test", out_root=tmp_path)
    manifest = packaged["manifest"]

    def nulls(obj, path="manifest"):
        found = []
        if obj is None:
            found.append(path)
        elif isinstance(obj, dict):
            for k, v in obj.items():
                found.extend(nulls(v, f"{path}.{k}"))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(nulls(v, f"{path}[{i}]"))
        return found

    assert nulls(manifest) == []
    assert manifest["dieline"]["built"] is True
    assert manifest["dieline"]["face_mm"]["width"] == 50.0
    assert manifest["files"] == ["master.png", "manifest.json"]
    folder = Path(packaged["folder"])
    assert (folder / "master.png").is_file()
    assert json.loads((folder / "manifest.json").read_text(encoding="utf-8"))["kind"] == "print_master"


def test_the_endpoint_rejects_a_zero_size_before_touching_the_gpu():
    from fastapi.testclient import TestClient
    from main import app
    import design_studio_api

    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-print"
    try:
        r = TestClient(app).post("/api/design-studio/print/master",
                                 json={"asset_id": "abc", "width_mm": 0, "height_mm": 50})
        assert r.status_code == 422
        r = TestClient(app).post("/api/design-studio/print/master",
                                 json={"asset_id": "no-such-asset", "width_mm": 50,
                                       "height_mm": 50})
        assert r.status_code == 404
    finally:
        app.dependency_overrides = {}


def test_a_source_above_the_model_ceiling_is_refused_with_the_reason():
    with pytest.raises(ValueError) as caught:
        pm.make_master(_png((1216, 1216)), width_mm=100, height_mm=100, upscaler=_four_x)
    assert "print_master_source_too_large" in str(caught.value)
    assert "1216" in str(caught.value)
