"""V3 S5 AutothinK surface tests: plan graph, artifact browser, run registry.

Offline: in-memory SQLite, no server, no network.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_plan  # noqa: E402
import chat_router  # noqa: E402
import chat_schema  # noqa: E402
import data_layer  # noqa: E402

DS_ASSETS_SQL = """
CREATE TABLE IF NOT EXISTS ds_assets (
    id TEXT PRIMARY KEY, account_id TEXT NOT NULL, project_id TEXT,
    name TEXT, asset_type TEXT, mime_type TEXT, storage_key TEXT,
    data_url TEXT, width INTEGER, height INTEGER, duration_seconds REAL,
    size_bytes INTEGER, metadata TEXT, created_at TEXT DEFAULT (datetime('now'))
);
"""


class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)
        self.conn.executescript(DS_ASSETS_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.chat = data_layer.ChatContainer(self.layer)
        self.design_studio = data_layer.DesignStudioContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _seed(db, account="acct-1"):
    sid = db.chat.sessions.create({"account_id": account, "title": "Plan test", "model": "qwen3:14b"})
    m1 = db.chat.messages.create({"account_id": account, "session_id": sid,
                                  "role": "user", "content": "SEO-check my listing"})
    m2 = db.chat.messages.create({
        "account_id": account, "session_id": sid, "role": "assistant",
        "content": "Here is the result.", "usage_json": {"status": "done"}})
    db.chat.tool_calls.create({"account_id": account, "session_id": sid, "message_id": m2,
                               "name": "seo_profile", "status": "done", "step_index": 1,
                               "result_json": {"ok": True, "summary": "profile shown"},
                               "started_at": "2026-10-18T00:00:00+00:00",
                               "ended_at": "2026-10-18T00:00:00.250+00:00"})
    db.chat.tool_calls.create({"account_id": account, "session_id": sid, "message_id": m2,
                               "name": "seo_check", "status": "error", "step_index": 0,
                               "result_json": {"ok": False, "summary": "no revision"},
                               "started_at": "2026-10-18T00:00:00+00:00",
                               "ended_at": "2026-10-18T00:00:01+00:00"})
    return sid, [m1, m2]


# ── Pure plan builder ───────────────────────────────────────────────────────

def test_plan_is_a_chain_prompt_steps_answer(db):
    sid, ids = _seed(db)
    msgs = db.chat.messages.list_by_session(sid, account_id="acct-1")
    calls = db.chat.tool_calls.list_by_session(sid, account_id="acct-1")
    plan = chat_plan.build_plan(msgs, calls)
    kinds = [n["kind"] for n in plan["nodes"]]
    assert kinds == ["prompt", "tool", "tool", "answer"]
    assert plan["step_count"] == 2


def test_plan_steps_follow_step_index_not_insert_order(db):
    sid, _ = _seed(db)
    msgs = db.chat.messages.list_by_session(sid, account_id="acct-1")
    calls = db.chat.tool_calls.list_by_session(sid, account_id="acct-1")
    plan = chat_plan.build_plan(msgs, calls)
    tool_names = [n["name"] for n in plan["nodes"] if n["kind"] == "tool"]
    assert tool_names == ["seo_check", "seo_profile"]     # step_index 0 then 1


def test_plan_edges_connect_the_chain(db):
    sid, _ = _seed(db)
    msgs = db.chat.messages.list_by_session(sid, account_id="acct-1")
    calls = db.chat.tool_calls.list_by_session(sid, account_id="acct-1")
    plan = chat_plan.build_plan(msgs, calls)
    node_ids = [n["id"] for n in plan["nodes"]]
    assert plan["edges"] == [[node_ids[i], node_ids[i + 1]] for i in range(len(node_ids) - 1)]


def test_plan_records_elapsed_and_ok():
    msgs = [{"id": "a", "role": "assistant", "content": "x", "created_at": "2026-10-18T00:00:00+00:00"}]
    calls = [{"id": "c", "message_id": "a", "name": "t", "step_index": 0, "status": "done",
              "result_json": {"ok": True, "summary": "fine"},
              "started_at": "2026-10-18T00:00:00+00:00",
              "ended_at": "2026-10-18T00:00:00.500+00:00"}]
    plan = chat_plan.build_plan(msgs, calls)
    tool = next(n for n in plan["nodes"] if n["kind"] == "tool")
    assert tool["elapsed_ms"] == 500 and tool["ok"] is True


def test_plan_without_tools_is_prompt_then_answer():
    msgs = [{"id": "u", "role": "user", "content": "hi", "created_at": "1"},
            {"id": "a", "role": "assistant", "content": "hello", "created_at": "2"}]
    plan = chat_plan.build_plan(msgs, [])
    assert [n["kind"] for n in plan["nodes"]] == ["prompt", "answer"]
    assert plan["caveats"]


# ── Plan endpoint ───────────────────────────────────────────────────────────

def test_plan_endpoint_returns_graph(db):
    sid, _ = _seed(db)
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        plan = chat_router.session_plan(sid, acct="acct-1")
    assert plan["session_id"] == sid and plan["step_count"] == 2


def test_plan_endpoint_404_unknown_session(db):
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            chat_router.session_plan("ghost", acct="acct-1")
    assert "404" in str(getattr(ei.value, "status_code", "")) + str(ei.value)


# ── Artifact browser ────────────────────────────────────────────────────────

def test_artifacts_lists_session_assets_with_metadata(db):
    sid, ids = _seed(db)
    db.design_studio.assets.create({"id": "asset-1", "account_id": "acct-1", "name": "Dieline",
                                    "asset_type": "image", "mime_type": "image/svg+xml",
                                    "size_bytes": 2048, "width": 800, "height": 600})
    db.chat.attachments.create({"account_id": "acct-1", "message_id": ids[1], "asset_id": "asset-1",
                                "kind": "image", "url": "/api/design-studio/assets/asset-1/file",
                                "provenance_json": {"tool": "create_dieline"}})
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.session_artifacts(sid, acct="acct-1")
    assert len(out["artifacts"]) == 1
    a = out["artifacts"][0]
    assert a["name"] == "Dieline" and a["mime_type"] == "image/svg+xml"
    assert a["present"] is True and a["provenance"] == {"tool": "create_dieline"}


def test_artifacts_marks_missing_asset_honestly(db):
    sid, ids = _seed(db)
    db.chat.attachments.create({"account_id": "acct-1", "message_id": ids[1],
                                "asset_id": "gone", "kind": "image",
                                "url": "/api/design-studio/assets/gone/file"})
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.session_artifacts(sid, acct="acct-1")
    assert out["artifacts"][0]["present"] is False


def test_artifacts_are_session_scoped(db):
    sid, ids = _seed(db)
    other = db.chat.sessions.create({"account_id": "acct-1", "title": "other"})
    m = db.chat.messages.create({"account_id": "acct-1", "session_id": other, "role": "assistant"})
    db.chat.attachments.create({"account_id": "acct-1", "message_id": m, "asset_id": "x", "kind": "image"})
    db.chat.attachments.create({"account_id": "acct-1", "message_id": ids[1], "asset_id": "y", "kind": "image"})
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.session_artifacts(sid, acct="acct-1")
    assert [a["asset_id"] for a in out["artifacts"]] == ["y"]


# ── Run registry ────────────────────────────────────────────────────────────

def test_runs_create_finish_and_list(db):
    rid = db.chat.runs.create({"account_id": "acct-1", "session_id": "s1", "kind": "chat_turn",
                               "label": "do a thing", "ref": "turn-1", "status": "running"})
    assert db.chat.runs.get(rid, account_id="acct-1")["status"] == "running"
    db.chat.runs.finish(rid, "done", account_id="acct-1")
    run = db.chat.runs.get(rid, account_id="acct-1")
    assert run["status"] == "done" and run["ended_at"]


def test_runs_are_tenant_scoped(db):
    db.chat.runs.create({"account_id": "acct-1", "label": "mine"})
    assert db.chat.runs.list_by_account("acct-2") == []
    assert db.chat.runs.get("nope", account_id="acct-1") is None


def test_runs_list_filters_by_status(db):
    db.chat.runs.create({"account_id": "acct-1", "label": "a", "status": "done"})
    db.chat.runs.create({"account_id": "acct-1", "label": "b", "status": "running"})
    only_running = db.chat.runs.list_by_account("acct-1", status="running")
    assert [r["label"] for r in only_running] == ["b"]


def test_runs_endpoint_lists(db):
    db.chat.runs.create({"account_id": "acct-1", "label": "a"})
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.list_runs(acct="acct-1")
    assert len(out["runs"]) == 1


def test_run_cancel_is_honest_for_finished_run(db):
    rid = db.chat.runs.create({"account_id": "acct-1", "kind": "chat_turn", "ref": "turn-x",
                               "status": "done"})
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.cancel_run(rid, acct="acct-1")
    assert out["cancelled"] is False     # a finished run is not pretend-cancelled


def test_run_cancel_404_unknown(db):
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            chat_router.cancel_run("ghost", acct="acct-1")
    assert "404" in str(getattr(ei.value, "status_code", "")) + str(ei.value)
