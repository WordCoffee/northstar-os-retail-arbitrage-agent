"""Tests for the creative asset registry + export bundles (Batch B).

Offline and deterministic: isolated media root via NORTHSTAR_MOCKUP_OUT, so the
registry index and files live in a temp dir and never touch the repo.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from PIL import Image

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from creative import assets, bundles, mogra_mockup, storage  # noqa: E402
from creative.routes import router as creative_router  # noqa: E402
from creative.service_routes import assets_router  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_root(tmp_path, monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MOCKUP_OUT", str(tmp_path))
    monkeypatch.delenv("NORTHSTAR_MEDIA_DIR", raising=False)
    monkeypatch.delenv("NORTHSTAR_ASSET_INDEX", raising=False)
    monkeypatch.delenv("NORTHSTAR_MEDIA_STORAGE", raising=False)
    return tmp_path


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(creative_router)   # provides /api/creative/file/{name}
    app.include_router(assets_router)
    return TestClient(app)


def _png(path, color=(220, 220, 210)):
    Image.new("RGB", (64, 64), color).save(path)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_register_list_get():
    a = assets.register(key="a.png", kind="mockup", product="turmeric",
                        container="jar", meta={"lane": "x"})
    assert a["id"].startswith("AS-") and a["url"].endswith("a.png")
    listed = assets.list_assets()
    assert any(x["key"] == "a.png" for x in listed)
    assert assets.get(a["id"])["key"] == "a.png"


def test_register_is_idempotent_on_key():
    assets.register(key="dup.png", product="p1")
    assets.register(key="dup.png", product="p2", meta={"note": "updated"})
    rows = [x for x in assets.list_assets() if x["key"] == "dup.png"]
    assert len(rows) == 1
    assert rows[0]["product"] == "p2"
    assert rows[0]["meta"]["note"] == "updated"


def test_sets_group_by_product_container():
    assets.register(key="t1.png", product="turmeric", container="jar")
    assets.register(key="t2.png", product="turmeric", container="jar")
    assets.register(key="o1.png", product="onion", container="pouch")
    sets = assets.sets()
    top = sets[0]
    assert top["count"] == 2 and "turmeric" in top["set"]


def test_scan_registers_files_on_disk(tmp_path):
    _png(tmp_path / "scene_one.png")
    _png(tmp_path / "scene_two.png")
    res = assets.scan()
    assert res["added"] == 2
    keys = {a["key"] for a in assets.list_assets()}
    assert {"scene_one.png", "scene_two.png"} <= keys
    # second scan adds nothing
    assert assets.scan()["added"] == 0


# ---------------------------------------------------------------------------
# Bundles
# ---------------------------------------------------------------------------

def test_create_bundle_packages_assets(tmp_path):
    _png(tmp_path / "one.png", (200, 10, 10))
    _png(tmp_path / "two.png", (10, 200, 10))
    assets.scan()
    ids = [a["id"] for a in assets.list_assets() if a["kind"] == "image"]
    assert len(ids) == 2

    out = bundles.create_bundle(ids, name="mogra set")
    assert out["ok"] is True
    assert out["included"] == 2
    assert out["bundle"]["kind"] == "bundle"

    data = storage.get_backend().get(out["bundle"]["key"])
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
        assert "manifest.json" in names
        assert any(n.startswith("assets/one.png") for n in names)
        assert any(n.startswith("assets/two.png") for n in names)
        import json
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["asset_count"] == 2


def test_create_bundle_ignores_unknown_ids(tmp_path):
    _png(tmp_path / "one.png")
    assets.scan()
    good = assets.list_assets()[0]["id"]
    out = bundles.create_bundle([good, "AS-NOPE"], name="partial")
    assert out["included"] == 1 and out["requested"] == 2


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def test_assets_routes(client, tmp_path):
    _png(tmp_path / "r1.png")
    s = client.post("/api/creative/assets/scan")
    assert s.status_code == 200 and s.json()["added"] == 1

    lst = client.get("/api/creative/assets")
    assert lst.status_code == 200
    body = lst.json()
    assert any(a["key"] == "r1.png" for a in body["assets"])
    assert "sets" in body

    reg = client.post("/api/creative/assets/register", json={"key": "manual.png", "product": "x"})
    assert reg.status_code == 200 and reg.json()["asset"]["key"] == "manual.png"


def test_bundle_route(client, tmp_path):
    _png(tmp_path / "b1.png")
    _png(tmp_path / "b2.png")
    client.post("/api/creative/assets/scan")
    ids = [a["id"] for a in client.get("/api/creative/assets").json()["assets"]]
    r = client.post("/api/creative/bundles", json={"asset_ids": ids, "name": "route bundle"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["bundle"]["url"].endswith(".zip")
    listed = client.get("/api/creative/bundles").json()["bundles"]
    assert any(b["id"] == j["bundle"]["id"] for b in listed)


def test_bundle_route_requires_ids(client):
    r = client.post("/api/creative/bundles", json={})
    assert r.status_code == 400


def test_bundle_file_served_as_zip(client, tmp_path):
    _png(tmp_path / "z1.png")
    client.post("/api/creative/assets/scan")
    ids = [a["id"] for a in client.get("/api/creative/assets").json()["assets"]]
    j = client.post("/api/creative/bundles", json={"asset_ids": ids, "name": "zipcheck"}).json()
    name = j["bundle"]["url"].rsplit("/", 1)[-1]
    fr = client.get(f"/api/creative/file/{name}")
    assert fr.status_code == 200
    assert "zip" in fr.headers["content-type"].lower()


# ---------------------------------------------------------------------------
# Lane -> registry tie-in
# ---------------------------------------------------------------------------

def test_mockup_auto_registers_asset(tmp_path, monkeypatch):
    src = tmp_path / "base.png"
    Image.new("RGB", (300, 300), (240, 235, 228)).save(src)
    res = mogra_mockup.build_mockup(
        product="organic_turmeric_powder",
        container="mogra_5lb_clear_handled_pet_jar",
        source_image=src, align="preset", out_path=tmp_path / "final.png")
    assert res["asset"] and res["asset"]["kind"] == "mockup"
    assert any(a["key"] == "final.png" for a in assets.list_assets())
