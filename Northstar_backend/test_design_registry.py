"""Designs are kept and reused on request - never reused by accident."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import design_registry as dr  # noqa: E402


@pytest.fixture()
def reg(tmp_path, monkeypatch):
    # Keep the asset copies inside the temp tree, not the real state/designs.
    monkeypatch.setattr(dr, "DESIGNS", tmp_path / "designs")
    monkeypatch.setattr(dr, "ROOT", tmp_path)
    return dr.DesignRegistry(tmp_path / "designs")


def _png(tmp_path, name):
    p = tmp_path / name
    Image.new("RGB", (32, 32), (200, 180, 150)).save(p)
    return p


def test_two_new_designs_are_never_the_same_record(reg, tmp_path):
    a = reg.create(brand="Mogra", product="Lion's Mane 6 oz", plate=_png(tmp_path, "a.png"))
    b = reg.create(brand="Mogra", product="Lion's Mane 6 oz", plate=_png(tmp_path, "b.png"))
    assert a["id"] != b["id"]
    assert a["version"] == b["version"] == 1


def test_a_design_keeps_its_assets_and_is_self_contained(reg, tmp_path):
    plate = _png(tmp_path, "plate.png")
    d = reg.create(brand="Mogra", product="Lion's Mane 6 oz", plate=plate,
                   palette={"ink": "#1E3A2F"})
    stored = reg.resolve_asset(d["id"], "plate")
    assert stored is not None and stored.is_file()
    assert str(d["id"]) in str(stored)          # copied into the design's own folder
    assert reg.get(d["id"])["palette"]["ink"] == "#1E3A2F"
    plate.unlink()                              # deleting the source must not break it
    assert reg.resolve_asset(d["id"], "plate").is_file()


def test_same_design_is_found_only_when_asked_for(reg, tmp_path):
    d = reg.create(brand="Mogra", product="Lion's Mane 6 oz", plate=_png(tmp_path, "a.png"))
    same = reg.find_same(brand="Mogra", product="lion's mane 6 oz")
    assert same and same["id"] == d["id"]
    assert reg.find_same(brand="Mogra", product="Shiitake 8 oz") is None


def test_a_version_is_recorded_with_its_note(reg, tmp_path):
    d = reg.create(brand="Mogra", product="Lion's Mane", plate=_png(tmp_path, "a.png"))
    v2 = reg.add_version(d["id"], asset=_png(tmp_path, "b.png"), note="new scene")
    assert v2["version"] == 2
    assert len(v2["versions"]) == 2
    assert v2["versions"][-1]["note"] == "new scene"


def test_latest_returns_the_most_recently_touched(reg, tmp_path):
    first = reg.create(brand="Mogra", product="A", plate=_png(tmp_path, "a.png"))
    second = reg.create(brand="Mogra", product="B", plate=_png(tmp_path, "b.png"))
    assert reg.latest("Mogra")["id"] == second["id"]
    reg.add_version(first["id"], note="resumed")
    assert reg.latest("Mogra")["id"] == first["id"]


def test_a_design_needs_a_brand_and_product(reg):
    with pytest.raises(ValueError):
        reg.create(brand="", product="x")
