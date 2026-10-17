"""Chat tool-registry tests (S2) — validation, merging, execution, tool loop.

Offline: no Ollama, no ComfyUI, no network. The loop tests inject scripted
adapter streams into chat_router.turn_event_stream (the same seam used by
test_chat_core); tool persistence runs on an in-memory SQLite built from the
REAL chat DDL.
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
import chat_router  # noqa: E402
import data_layer  # noqa: E402


# ── Fake store (chat DDL only) ───────────────────────────────────────────────

class _FakeDB:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)
        self.chat = data_layer.ChatContainer(_FakeLayer(self.conn))


class _FakeLayer:
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


@pytest.fixture()
def db():
    return _FakeDB()


def _session(db, account="acct-1"):
    sid = db.chat.sessions.create({"account_id": account, "title": "New chat"})
    return db.chat.sessions.get_by_id(sid, account_id=account)


def _frames(chunks):
    out = []
    for frame in chunks:
        lines = [ln for ln in frame.split("\n") if ln]
        event = next((ln[7:] for ln in lines if ln.startswith("event: ")), None)
        data_line = next((ln[6:] for ln in lines if ln.startswith("data: ")), "{}")
        out.append((event, json.loads(data_line)))
    return out


# ── parse_arguments / validation / normalize ─────────────────────────────────

def test_parse_arguments_accepts_dict_fences_and_trailing_comma():
    assert chat_tools.parse_arguments({"a": 1}) == {"a": 1}
    assert chat_tools.parse_arguments('```json\n{"a": 1}\n```') == {"a": 1}
    assert chat_tools.parse_arguments('{"a": 1,}') == {"a": 1}
    assert chat_tools.parse_arguments("") == {}
    with pytest.raises(chat_tools.ToolValidationError):
        chat_tools.parse_arguments("[1,2]")
    with pytest.raises(chat_tools.ToolValidationError):
        chat_tools.parse_arguments("{broken")


def test_validate_tool_arguments_required_types_bounds_enum_defaults():
    spec = {"parameters": {
        "type": "object",
        "properties": {
            "prompt": {"type": "string"},
            "width": {"type": "integer", "minimum": 512, "maximum": 1216},
            "tier": {"type": "string", "enum": ["draft", "final"], "default": "draft"},
        },
        "required": ["prompt"],
    }}
    with pytest.raises(chat_tools.ToolValidationError):
        chat_tools.validate_tool_arguments(spec, {})
    with pytest.raises(chat_tools.ToolValidationError):
        chat_tools.validate_tool_arguments(spec, {"prompt": "x", "width": 128})
    with pytest.raises(chat_tools.ToolValidationError):
        chat_tools.validate_tool_arguments(spec, {"prompt": "x", "tier": "ultra"})
    out = chat_tools.validate_tool_arguments(
        spec, {"prompt": "x", "width": "1024", "extra": "dropped"})
    assert out == {"prompt": "x", "width": 1024, "tier": "draft"}


def test_normalize_tool_calls_merges_fragments_and_splits_repeats():
    merged = chat_tools.normalize_tool_calls([
        {"index": 0, "function": {"name": "create_dieline", "arguments": '{"templ'}},
        {"index": 0, "function": {"arguments": 'ate_id": "rsc_box"}'}},
    ])
    assert merged == [{"name": "create_dieline", "raw_args": '{"template_id": "rsc_box"}', "obj_args": None}]

    dict_arg = chat_tools.normalize_tool_calls([
        {"function": {"name": "system_status", "arguments": {}}}])
    assert dict_arg[0]["name"] == "system_status" and dict_arg[0]["obj_args"] == {}

    repeated = chat_tools.normalize_tool_calls([
        {"index": 0, "function": {"name": "a", "arguments": "{}"}},
        {"index": 1, "function": {"name": "a", "arguments": "{}"}},
    ])
    assert len(repeated) == 2


# ── run_tool ─────────────────────────────────────────────────────────────────

def test_run_tool_unknown_and_invalid_args_are_honest_results():
    res = chat_tools.run_tool("nope", {}, {})
    assert res["ok"] is False and "Unknown tool" in res["summary"]
    res = chat_tools.run_tool("generate_image", {}, {})
    assert res["ok"] is False and "missing required" in res["error"]


def test_run_tool_list_templates_real_catalog():
    res = chat_tools.run_tool("list_templates", {}, {})
    assert res["ok"] is True
    ids = {t["id"] for t in res["data"]["templates"]}
    assert {"label_rounded_rectangle", "rsc_box", "tuck_end"} <= ids


def test_run_tool_design_brief_real_builder():
    res = chat_tools.run_tool("design_brief", {"message": "eco pouch for mushroom powder"}, {})
    assert res["ok"] is True
    assert res["data"]["palette"]["name"]
    assert res["data"]["format"]["suggested_templates"]


def test_run_tool_create_dieline_builds_without_persist():
    res = chat_tools.run_tool(
        "create_dieline", {"template_id": "label_circle", "params": {"width_mm": 50, "height_mm": 50}, "persist": False}, {})
    assert res["ok"] is True and "mm" in res["summary"]
    assert res["assets"] == []
    # bad params surface as an honest rejection the model can react to
    bad = chat_tools.run_tool("create_dieline", {"template_id": "label_circle", "params": {"width_mm": 9999}}, {})
    assert bad["ok"] is False and "range" in (bad["error"] or "")


def test_run_tool_generate_image_unarmed_is_honest(monkeypatch):
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    res = chat_tools.run_tool("generate_image", {"prompt": "warm linen backdrop"}, {})
    assert res["ok"] is False
    assert "not armed" in res["summary"].lower() or "not armed" in (res["error"] or "").lower()


# ── Tool loop through turn_event_stream (scripted streams) ──────────────────

def _provider(script_rounds):
    """events provider: round index -> scripted adapter events."""
    def _p(round_idx, _messages):
        return iter(script_rounds[round_idx] if round_idx < len(script_rounds) else [])
    return _p


def test_tool_loop_executes_and_persists(db):
    session = _session(db)
    rounds = [
        [{"type": "tool_call", "call": {"index": 0, "function": {"name": "list_templates", "arguments": "{}"}}},
         {"type": "done", "cancelled": False, "usage": {"prompt_tokens": 4, "completion_tokens": 2}}],
        [{"type": "content", "delta": "There are templates. "},
         {"type": "done", "cancelled": False, "usage": {"prompt_tokens": 8, "completion_tokens": 6}}],
    ]
    frames = list(chat_router.turn_event_stream(
        db, "acct-1", session, "list the dieline templates", events=_provider(rounds), tools_enabled=True))
    pairs = _frames(frames)
    kinds = [k for k, _ in pairs]
    assert "tool-start" in kinds and "tool-end" in kinds and "token" in kinds
    start_idx = kinds.index("tool-start")
    end_idx = kinds.index("tool-end")
    assert pairs[start_idx][1]["name"] == "list_templates"
    assert pairs[end_idx][1]["ok"] is True
    direct = chat_tools.run_tool("list_templates", {}, {})
    expected = f"{len(direct['data']['templates'])} parametric dieline templates available."
    assert pairs[end_idx][1]["summary"] == expected

    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assistant = rows[0]
    assert any(p["type"] == "tool" and p["name"] == "list_templates" for p in assistant["parts_json"])
    calls = db.chat.tool_calls.list_by_session(session["id"], account_id="acct-1")
    assert len(calls) == 1
    assert calls[0]["name"] == "list_templates" and calls[0]["status"] == "done"
    assert calls[0]["message_id"] == assistant["id"]


def test_tool_loop_validation_error_reaches_model_then_finishes(db):
    session = _session(db)
    rounds = [
        [{"type": "tool_call", "call": {"index": 0, "function": {"name": "generate_image", "arguments": "{}"}}},
         {"type": "done", "cancelled": False, "usage": None}],
        [{"type": "content", "delta": "I need a prompt first."},
         {"type": "done", "cancelled": False, "usage": None}],
    ]
    pairs = _frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "make a picture", events=_provider(rounds), tools_enabled=True)))
    end = next(d for k, d in pairs if k == "tool-end")
    assert end["ok"] is False and "missing required" in (end["error"] or "")
    assert any(k == "token" for k, _ in pairs)


def test_tool_loop_bounded_by_max_steps(db):
    session = _session(db)
    tool_round = [{"type": "tool_call", "call": {"index": 0, "function": {"name": "system_status", "arguments": "{}"}}},
                  {"type": "done", "cancelled": False, "usage": None}]
    rounds = [list(tool_round) for _ in range(chat_tools.MAX_TOOL_STEPS + 2)]
    pairs = _frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "loop forever", events=_provider(rounds), tools_enabled=True)))
    kinds = [k for k, _ in pairs]
    assert kinds.count("tool-start") == chat_tools.MAX_TOOL_STEPS
    notice = next(d for k, d in pairs if k == "notice")
    assert notice["code"] == "max_tool_steps"
    assert kinds[-1] == "done"


def test_tool_progress_frames_stream_from_worker(db, monkeypatch):
    def fake_handler(args, ctx):
        ctx["progress"](50, "halfway")
        ctx["progress"](100, "almost done")
        return {"ok": True, "summary": "fake render complete", "assets":
                [{"id": "asset-x", "kind": "image", "url": "/x", "name": "img"}]}

    monkeypatch.setitem(chat_tools.TOOLS, "generate_image",
                        {**chat_tools.TOOLS["generate_image"], "handler": fake_handler})
    session = _session(db)
    rounds = [
        [{"type": "tool_call", "call": {"index": 0, "function": {"name": "generate_image", "arguments": "{\"prompt\": \"x\"}"}}},
         {"type": "done", "cancelled": False, "usage": None}],
        [{"type": "content", "delta": "done"}, {"type": "done", "cancelled": False, "usage": None}],
    ]
    pairs = _frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "render", events=_provider(rounds), tools_enabled=True)))
    progress = [d for k, d in pairs if k == "tool-progress"]
    assert any(p.get("pct") == 50 and p.get("label") == "halfway" for p in progress)
    asset = next(d for k, d in pairs if k == "asset")
    assert asset["id"] == "asset-x"
    attachments = db.chat.attachments.list_by_message(
        db.chat.messages.list_by_session(session["id"], account_id="acct-1")[0]["id"], account_id="acct-1")
    assert any(a["asset_id"] == "asset-x" for a in attachments)


def test_tools_disabled_skips_loop(db):
    session = _session(db)
    rounds = [
        [{"type": "tool_call", "call": {"index": 0, "function": {"name": "system_status", "arguments": "{}"}}},
         {"type": "done", "cancelled": False, "usage": None}],
    ]
    pairs = _frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "hi", events=_provider(rounds), tools_enabled=False)))
    kinds = [k for k, _ in pairs]
    assert "tool-start" not in kinds
    assert kinds[-1] == "done"
