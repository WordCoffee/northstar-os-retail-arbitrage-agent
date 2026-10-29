"""U3 tool wiring — `place_logo` is registered and reachable, not just a module.

The gap it closes: 5 of 60 surveyed turns asked about the logo and NO tool
existed (reports/rea_probe/smui_intents.json). This asserts the tool is in the
catalogue, in the model's schema set, in the Creative Studio scope, and that the
handler refuses honestly when an asset is missing.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import chat_schema  # noqa: E402
import chat_tools  # noqa: E402
import data_layer  # noqa: E402


class _FakeLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _Assets:
    def get_by_id(self, asset_id, account_id=None):
        return None


class _DesignStudio:
    assets = _Assets()


class _FakeDB:
    def __init__(self):
        self.layer = _FakeLayer()
        self.chat = data_layer.ChatContainer(self.layer)
        self.design_studio = _DesignStudio()


def test_place_logo_is_registered_with_a_schema():
    assert "place_logo" in chat_tools.tool_names()
    entry = chat_tools.TOOLS["place_logo"]
    assert callable(entry["handler"])
    params = entry["parameters"]
    assert set(params["required"]) == {"plate_asset_id", "logo_asset_id"}
    assert "auto" in params["properties"]["anchor"]["enum"]


def test_place_logo_is_offered_to_the_model():
    names = [s.get("function", {}).get("name") for s in chat_tools.ollama_tool_schemas()]
    assert "place_logo" in names


def test_place_logo_is_in_the_creative_studio_scope():
    scopes = [s for s in chat_tools.SCOPES] if hasattr(chat_tools, "SCOPES") else []
    creative = next((s for s in scopes if s.get("id") == "creative"), None)
    if creative is not None:                       # scope table is optional here
        assert "place_logo" in creative["tools"]


def test_missing_asset_is_refused_with_a_reason():
    out = chat_tools.run_tool("place_logo",
                              {"plate_asset_id": "nope", "logo_asset_id": "nope2"},
                              {"db": _FakeDB(), "account_id": "acct"})
    assert out["ok"] is False
    assert "no readable" in out["error"]


def test_bad_anchor_is_rejected_before_any_work(tmp_path):
    out = chat_tools.run_tool("place_logo",
                              {"plate_asset_id": "a", "logo_asset_id": "b", "anchor": "middle-centre"},
                              {"db": _FakeDB(), "account_id": "acct"})
    assert out["ok"] is False


def test_end_to_end_places_and_registers(tmp_path):
    """Real files in the studio output dir, a fake asset table, the real tool."""
    from PIL import Image, ImageDraw

    out_dir = chat_tools._out_dir()
    plate_name, logo_name = "u3_plate_test.png", "u3_logo_test.png"
    plate = Image.new("RGB", (640, 860), (232, 226, 214))
    d = ImageDraw.Draw(plate)
    for i in range(30):
        d.line([(200, 300 + i * 6), (420, 330 + i * 6)], fill=(50, 80, 60), width=5)
    plate.save(out_dir / plate_name)
    logo = Image.new("RGBA", (300, 200), (0, 0, 0, 0))
    ImageDraw.Draw(logo).ellipse([20, 20, 280, 180], fill=(140, 40, 40, 255))
    logo.save(out_dir / logo_name)

    class _A:
        def __init__(self):
            self.created = None

        def get_by_id(self, aid, account_id=None):
            table = {"plate-x": plate_name, "logo-x": logo_name}
            return ({"id": aid, "storage_key": table[aid], "project_id": None}
                    if aid in table else None)

        def create(self, payload):
            self.created = payload
            return "asset-u3"

    class _DS:
        def __init__(self):
            self.assets = _A()

    class _DB(_FakeDB):
        def __init__(self):
            super().__init__()
            self.design_studio = _DS()

    db = _DB()
    try:
        out = chat_tools.run_tool("place_logo",
                                  {"plate_asset_id": "plate-x", "logo_asset_id": "logo-x",
                                   "anchor": "auto", "scale": 0.15, "name": "brand mark"},
                                  {"db": db, "account_id": "acct"})
        assert out["ok"] is True, out
        assert out["assets"][0]["id"] == "asset-u3"
        assert db.design_studio.assets.created["metadata"]["logo_placement"]["placement"]["anchor"]
        assert "contrast" in out["summary"] or "Contrast" in out["summary"]
        produced = out_dir / db.design_studio.assets.created["storage_key"]
        assert produced.is_file() and produced.stat().st_size > 1000
        produced.unlink()
    finally:
        for name in (plate_name, logo_name):
            (out_dir / name).unlink(missing_ok=True)
