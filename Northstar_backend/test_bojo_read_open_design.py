"""Bojo can read the design the seller has open — and says which project it read.

The canvas autosaves into a project row, so "open" is the newest canvas row for the account. These
tests pin the answer's shape, the honesty when there is nothing saved, and the fact that no design
content is invented.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import data_layer  # noqa: E402
from bojo_tools import design as design_tools  # noqa: E402

DESIGN = {"v": 1, "savedAt": 1, "doc": {"name": "Pouch front", "width": 1080, "height": 1080,
                                        "layers": [
                                            {"id": "l1", "type": "text", "text": "LION'S MANE"},
                                            {"id": "l2", "type": "image", "name": "pack"},
                                        ]},
          "assets": []}


class _Projects:
    def __init__(self, rows):
        self.rows = rows

    def list_by_section(self, section=None, account_id=None, limit=200):
        return self.rows[:limit]


class _Studio:
    def __init__(self, rows):
        self.projects = _Projects(rows)


class _DB:
    def __init__(self, rows):
        self.design_studio = _Studio(rows)


def _project(metadata):
    return {"id": "proj-1", "name": "Pouch front", "section": "canvas",
            "metadata": metadata, "updated_at": "2026-11-13T06:00:00+00:00"}


def test_the_open_design_is_read_with_layers_and_text(monkeypatch):
    row = _project(json.dumps({"design": DESIGN}))
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: _DB([row]))
    out = design_tools.read_open_design(account_id="org-t2")
    assert out["ok"] is True
    assert out["data"]["project_id"] == "proj-1"
    assert out["data"]["size"] == {"width": 1080, "height": 1080}
    assert [layer["id"] for layer in out["data"]["layers"]] == ["l1", "l2"]
    assert out["data"]["layers"][0]["text"] == "LION'S MANE"
    assert "1080x1080" in out["summary"]
    assert "2 layer" in out["summary"]


def test_metadata_may_arrive_as_a_dict(monkeypatch):
    row = _project({"design": DESIGN})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: _DB([row]))
    out = design_tools.read_open_design(account_id="org-t2")
    assert out["ok"] is True
    assert out["data"]["text_count"] == 1


def test_nothing_saved_is_a_named_refusal_not_an_empty_design(monkeypatch):
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: _DB([]))
    out = design_tools.read_open_design(account_id="org-t2")
    assert out["ok"] is False
    assert "no canvas design" in out["reason"]


def test_a_broken_metadata_blob_does_not_raise(monkeypatch):
    row = _project("{not json")
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: _DB([row]))
    out = design_tools.read_open_design(account_id="org-t2")
    assert out["ok"] is True  # the project exists; only the payload was unreadable
    assert out["data"]["layers"] == []


def test_the_tool_is_offered_by_the_chat_surface():
    import chat_tools

    assert chat_tools.is_offered("read_open_design") is True
