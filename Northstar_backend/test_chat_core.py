"""Chat core tests (S1) — SSE event sequences, thinking separation, cancel,
and store CRUD. Offline: no Ollama, no network, no server. The adapter's HTTP
layer is mocked; the store runs on an in-memory SQLite built from the REAL
chat DDL (chat_schema.CHAT_TABLES_SQL — one source of truth with data_layer).
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import threading
from unittest import mock

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_REPO = os.path.dirname(_HERE)
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import chat_schema  # noqa: E402
import chat_adapter  # noqa: E402
import chat_router  # noqa: E402
import data_layer  # noqa: E402
from autothink.backend.llm_adapter import (  # noqa: E402
    UnifiedLLMAdapter,
    iter_ollama_chat_events,
)


# ── Fixtures: in-memory store speaking DataLayer's dialect ──────────────────

class _FakeDataLayer:
    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(chat_schema.CHAT_TABLES_SQL)

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def commit(self):
        self.conn.commit()


class _FakeNorthstarDB:
    def __init__(self):
        self.layer = _FakeDataLayer()
        self.chat = data_layer.ChatContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def _new_session(db, account="acct-1", title="New chat"):
    sid = db.chat.sessions.create({"account_id": account, "title": title})
    return db.chat.sessions.get_by_id(sid, account_id=account)


def _parse_frames(chunks):
    """Decode an SSE stream (list of frame strings) into (event, data) pairs."""
    out = []
    for frame in chunks:
        lines = [ln for ln in frame.split("\n") if ln]
        event = next((ln[7:] for ln in lines if ln.startswith("event: ")), None)
        data_line = next((ln[6:] for ln in lines if ln.startswith("data: ")), "{}")
        out.append((event, json.loads(data_line)))
    return out


# ── Parser: thinking/content separation, usage, cancel, junk tolerance ──────

def _ndjson(*chunks):
    return [json.dumps(c) for c in chunks]


def test_parse_separates_thinking_and_content():
    lines = _ndjson(
        {"message": {"thinking": "weigh "}, "done": False},
        {"message": {"thinking": "options"}, "done": False},
        {"message": {"content": "Hello "}, "done": False},
        {"message": {"content": "there"}, "done": False},
        {"done": True, "prompt_eval_count": 11, "eval_count": 7, "total_duration": 123},
    )
    events = list(iter_ollama_chat_events(lines))
    assert [e["type"] for e in events] == ["thinking", "thinking", "content", "content", "done"]
    assert "".join(e["delta"] for e in events if e["type"] == "thinking") == "weigh options"
    assert "".join(e["delta"] for e in events if e["type"] == "content") == "Hello there"
    done = events[-1]
    assert done["cancelled"] is False
    assert done["usage"]["prompt_tokens"] == 11
    assert done["usage"]["completion_tokens"] == 7


def test_parse_tolerates_keepalive_and_garbage():
    lines = ["", "not json at all", json.dumps({"message": {"content": "ok"}, "done": False}),
             json.dumps({"done": True})]
    events = list(iter_ollama_chat_events(lines))
    assert [e["type"] for e in events] == ["content", "done"]


def test_parse_cancel_yields_cancelled_done():
    lines = _ndjson({"message": {"content": "a"}, "done": False},
                    {"message": {"content": "b"}, "done": False})
    calls = {"n": 0}

    def should_cancel():
        calls["n"] += 1
        return calls["n"] >= 2  # first line passes, cancel trips before the second

    events = list(iter_ollama_chat_events(lines, should_cancel))
    assert events[-1]["type"] == "done"
    assert events[-1]["cancelled"] is True
    assert events[0] == {"type": "content", "delta": "a"}


def test_parse_generate_style_frames_tolerated():
    events = list(iter_ollama_chat_events([json.dumps({"response": "hi", "done": True})]))
    assert [e["type"] for e in events] == ["content", "done"]
    assert events[0]["delta"] == "hi"


# ── Adapter.stream_chat: think fallback + transport error ───────────────────

class _FakeResponse:
    def __init__(self, status_code=200, lines=None, text=""):
        self.status_code = status_code
        self._lines = lines or []
        self.text = text

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)


def test_adaptive_num_predict_caps_short_asks_and_keeps_long_form():
    assert chat_adapter._adaptive_num_predict(
        [{"role": "user", "content": "hi"}]) == chat_adapter.CHAT_NUM_PREDICT_SHORT
    assert chat_adapter._adaptive_num_predict(
        [{"role": "user", "content": "write a detailed report"}]) == \
        chat_adapter.CHAT_NUM_PREDICT_LONG
    assert chat_adapter._adaptive_num_predict(
        [{"role": "user", "content": "x" * 1300}]) == \
        chat_adapter.CHAT_NUM_PREDICT_LONG
    assert chat_adapter._adaptive_num_predict(
        [{"role": "user", "content": "hi"}], default=1024) == 1024


def test_stream_chat_think_fallback_retries_once():
    first = _FakeResponse(status_code=400, text='{"error":"model does not support thinking"}')
    second = _FakeResponse(status_code=200, lines=_ndjson(
        {"message": {"content": "hi"}, "done": True, "prompt_eval_count": 3, "eval_count": 1}))
    with mock.patch("autothink.backend.llm_adapter.requests.post",
                    side_effect=[first, second]) as post:
        events = list(UnifiedLLMAdapter().stream_chat(
            [{"role": "user", "content": "x"}], think=True))
    assert post.call_count == 2
    kinds = [e["type"] for e in events]
    assert kinds[0] == "notice"
    assert events[0]["code"] == "think_unsupported"
    assert "content" in kinds and kinds[-1] == "done"


def test_stream_chat_transport_error_yields_error_event():
    import requests as _requests
    with mock.patch("autothink.backend.llm_adapter.requests.post",
                    side_effect=_requests.RequestException("connection refused")):
        events = list(UnifiedLLMAdapter().stream_chat(
            [{"role": "user", "content": "x"}], think=True))
    assert [e["type"] for e in events] == ["error"]
    assert "connection refused" in events[0]["reason"]


# ── SSE frames + turn stream: sequence, persistence, cancel, error ─────────

def _script(*events):
    def it():
        for ev in events:
            yield ev
    return it()


def test_sse_frame_format():
    frame = chat_router.sse_frame("token", {"delta": "hi"})
    assert frame.startswith("event: token\ndata: ")
    assert frame.endswith("\n\n")
    assert json.loads(frame.split("data: ", 1)[1].strip()) == {"delta": "hi"}


def test_turn_stream_sequence_and_persistence(db):
    session = _new_session(db)
    script = _script(
        {"type": "thinking", "delta": "plan "},
        {"type": "thinking", "delta": "step"},
        {"type": "content", "delta": "Hello "},
        {"type": "content", "delta": "operator"},
        {"type": "done", "cancelled": False,
         "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
    )
    frames = list(chat_router.turn_event_stream(
        db, "acct-1", session, "Draft a pouch concept", events=script))
    pairs = _parse_frames(frames)
    kinds = [k for k, _ in pairs]
    assert kinds == ["start", "thinking", "thinking", "token", "token", "done"]
    assert pairs[0][1]["session_id"] == session["id"]

    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assert [r["role"] for r in rows] == ["assistant"]
    assistant = rows[0]
    assert assistant["content"] == "Hello operator"
    assert assistant["thinking"] == "plan step"
    assert assistant["parts_json"][0]["type"] == "thinking"
    assert assistant["parts_json"][1]["type"] == "text"
    assert assistant["usage_json"]["status"] == "done"
    # First user message auto-titles the session.
    refreshed = db.chat.sessions.get_by_id(session["id"], account_id="acct-1")
    assert refreshed["title"] == "Draft a pouch concept"
    done = pairs[-1][1]
    assert done["status"] == "done"
    assert done["message_id"] == assistant["id"]


def test_turn_stream_cancel_persists_partial(db):
    session = _new_session(db)
    script = _script(
        {"type": "content", "delta": "half an answer"},
        {"type": "done", "cancelled": True, "usage": None},
    )
    pairs = _parse_frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "go", events=script)))
    assert pairs[-1][0] == "done"
    assert pairs[-1][1]["cancelled"] is True
    assert pairs[-1][1]["status"] == "cancelled"
    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assert rows[0]["content"] == "half an answer"
    assert rows[0]["usage_json"]["status"] == "cancelled"


def test_turn_stream_error_persists_notice(db):
    session = _new_session(db)
    script = _script({"type": "error", "reason": "ollama unreachable"})
    pairs = _parse_frames(list(chat_router.turn_event_stream(
        db, "acct-1", session, "go", events=script)))
    kinds = [k for k, _ in pairs]
    assert kinds == ["start", "error", "done"]
    assert pairs[-1][1]["status"] == "error"
    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assert "LOCAL FALLBACK" in rows[0]["content"]


# ── Client-disconnect durability (the honest-partial guarantee) ─────────────

def test_turn_stream_client_disconnect_persists_partial(db):
    session = _new_session(db)
    script = _script(
        {"type": "content", "delta": "partial "},
        {"type": "content", "delta": "answer"},
        {"type": "done", "cancelled": False, "usage": None},
    )
    gen = chat_router.turn_event_stream(db, "acct-1", session, "go", events=script)
    assert "start" in next(gen)
    assert "token" in next(gen)
    gen.close()  # client vanishes mid-stream -> GeneratorExit at the yield
    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assert len(rows) == 1
    assert rows[0]["content"] == "partial "
    assert rows[0]["usage_json"]["status"] == "cancelled"


def test_turn_stream_cut_without_tokens_persists_nothing(db):
    session = _new_session(db)
    script = _script({"type": "thinking", "delta": ""})
    gen = chat_router.turn_event_stream(db, "acct-1", session, "go", events=script)
    next(gen)  # start; close immediately
    gen.close()
    rows = db.chat.messages.list_by_session(session["id"], account_id="acct-1")
    assert rows == []  # a cut turn that produced nothing is not a message


# ── Cancel registry ─────────────────────────────────────────────────────────

def test_cancel_registry_set_and_drain():
    ev = chat_router.register_turn("turn-xyz")
    assert isinstance(ev, threading.Event)
    assert chat_router.cancel_turn("turn-xyz") is True
    assert ev.is_set()
    chat_router._drain_turn("turn-xyz")
    assert chat_router.cancel_turn("turn-xyz") is False


# ── Store CRUD and tenant scoping ───────────────────────────────────────────

def test_store_crud_and_tenant_scoping(db):
    sid = db.chat.sessions.create({"account_id": "acct-1", "title": "Alpha",
                                   "focus_json": {"platform": "Amazon"}})
    other = db.chat.sessions.create({"account_id": "acct-2", "title": "Beta"})
    assert db.chat.sessions.get_by_id(sid, account_id="acct-2") is None
    session = db.chat.sessions.get_by_id(sid, account_id="acct-1")
    assert session["focus_json"] == {"platform": "Amazon"}

    listed = db.chat.sessions.list_by_account("acct-1")
    assert [s["id"] for s in listed] == [sid]
    assert db.chat.sessions.update(sid, {"title": "Alpha 2"}, account_id="acct-1") is True
    assert db.chat.sessions.get_by_id(sid, account_id="acct-1")["title"] == "Alpha 2"

    mid = db.chat.messages.create({"account_id": "acct-1", "session_id": sid,
                                   "role": "user", "content": "one"})
    db.chat.messages.create({"account_id": "acct-1", "session_id": sid,
                             "role": "assistant", "content": "two"})
    msgs = db.chat.messages.list_by_session(sid, account_id="acct-1")
    assert [m["content"] for m in msgs] == ["one", "two"]
    assert db.chat.messages.get_by_id(mid, account_id="acct-2") is None

    # delete cascades session messages within the tenant only
    assert db.chat.sessions.delete(sid, account_id="acct-1") is True
    assert db.chat.messages.list_by_session(sid, account_id="acct-1") == []
    assert db.chat.sessions.get_by_id(other, account_id="acct-2") is not None


def test_build_chat_messages_focus_and_limit():
    history = [
        {"role": "user", "content": "a"},
        {"role": "assistant", "content": ""},   # empty rows are skipped
        {"role": "assistant", "content": "b"},
    ]
    msgs = chat_adapter.build_chat_messages(history, focus={"platform": "Amazon"}, limit=2)
    assert msgs[0]["role"] == "system"
    assert "platform: Amazon" in msgs[0]["content"]
    assert [m["content"] for m in msgs[1:]] == ["a", "b"]
