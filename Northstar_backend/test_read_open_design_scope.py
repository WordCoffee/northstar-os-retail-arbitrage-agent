"""`read_open_design` is scoped to the caller's org and the open tab's project.

Two ways a tool like this leaks: it reads the newest row in the database regardless of who is
asking, or it trusts a `project_id` argument from the model. Both are pinned here — the store is
called with the session's account, a project from another account answers "not in this
organisation", and the chat surface injects the account from the verified session rather than from
the tool call.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

import data_layer  # noqa: E402
from bojo_tools import design as design_tools  # noqa: E402

DESIGN = {"v": 1, "savedAt": 1,
          "doc": {"name": "Pouch front", "width": 1080, "height": 1080,
                  "layers": [{"id": "l1", "type": "text", "text": "LION'S MANE"}]},
          "assets": []}


class _Projects:
    def __init__(self, rows_by_org):
        self.rows_by_org = rows_by_org
        self.calls = []

    def list_by_section(self, section=None, account_id=None, limit=200):
        self.calls.append(("list", account_id, section))
        return (self.rows_by_org.get(account_id) or [])[:limit]

    def get_by_id(self, pid, account_id=None):
        self.calls.append(("get", account_id, pid))
        for org, rows in self.rows_by_org.items():
            if account_id is not None and org != account_id:
                continue
            for row in rows:
                if row["id"] == pid:
                    return row
        return None


class _DB:
    def __init__(self, rows_by_org):
        class Studio:
            pass

        studio = Studio()
        studio.projects = _Projects(rows_by_org)
        self.design_studio = studio


def _project(pid, org, name="Pouch front"):
    return {"id": pid, "account_id": org, "name": name, "section": "canvas",
            "metadata": json.dumps({"design": DESIGN}),
            "updated_at": "2026-11-13T06:00:00+00:00"}


def test_the_store_is_asked_for_the_callers_org_only(monkeypatch):
    db = _DB({"org-a": [_project("p-a", "org-a")], "org-b": [_project("p-b", "org-b")]})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: db)
    out = design_tools.read_open_design(account_id="org-a")
    assert out["ok"] is True
    assert out["data"]["project_id"] == "p-a"
    assert ("list", "org-a", "canvas") in db.design_studio.projects.calls


def test_without_an_org_it_refuses_instead_of_reading_the_newest_row(monkeypatch):
    db = _DB({"org-a": [_project("p-a", "org-a")]})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: db)
    out = design_tools.read_open_design()
    assert out["ok"] is False
    assert "organisation" in out["reason"]
    assert db.design_studio.projects.calls == []


def test_a_project_from_another_org_is_not_readable(monkeypatch):
    db = _DB({"org-a": [_project("p-a", "org-a")], "org-b": [_project("p-b", "org-b")]})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: db)
    out = design_tools.read_open_design(account_id="org-a", project_id="p-b")
    assert out["ok"] is False
    assert "organisation" in out["reason"]


def test_the_named_project_wins_over_the_newest(monkeypatch):
    older = _project("p-old", "org-a", "Older")
    newer = _project("p-new", "org-a", "Newer")
    db = _DB({"org-a": [newer, older]})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: db)
    out = design_tools.read_open_design(account_id="org-a", project_id="p-old")
    assert out["ok"] is True
    assert out["data"]["project_id"] == "p-old"
    assert out["data"]["name"] == "Older"


def test_the_chat_surface_injects_the_session_account_not_the_tool_argument(monkeypatch):
    db = _DB({"org-a": [_project("p-a", "org-a")]})
    monkeypatch.setattr(data_layer, "get_northstar_db", lambda: db)
    import chat_tools

    handler = chat_tools.TOOLS["read_open_design"]["handler"]
    # The model tries to name another org; the handler must still read the session's.
    result = handler({"project_id": "p-a", "account_id": "org-b"}, {"account_id": "org-a"})
    assert result["ok"] is True
    assert db.design_studio.projects.calls[-1][1] == "org-a"
