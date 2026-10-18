"""Session fork / rewind tests (V3 S5 — AutothinK premium surface).

Covers the non-destructive rewind pattern: a fork copies a session up to a
chosen message into a NEW session, the parent is never mutated, lineage is
recorded, and tenant scoping holds. Offline: in-memory SQLite, no server.
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

import chat_router  # noqa: E402
import chat_schema  # noqa: E402
import data_layer  # noqa: E402


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


def _seed(db, account="acct-1"):
    sid = db.chat.sessions.create({
        "account_id": account, "title": "Maple syrup launch",
        "mode": "simple", "model": "qwen3:14b",
        "focus_json": {"mode": "grow", "label": "Grow"}})
    m1 = db.chat.messages.create({"account_id": account, "session_id": sid,
                                  "role": "user", "content": "Q1"})
    m2 = db.chat.messages.create({"account_id": account, "session_id": sid,
                                  "role": "assistant", "content": "A1"})
    m3 = db.chat.messages.create({"account_id": account, "session_id": sid,
                                  "role": "user", "content": "Q2"})
    return sid, [m1, m2, m3]


def test_fork_up_to_message_copies_prefix_only(db):
    sid, ids = _seed(db)
    out = db.chat.sessions.fork(sid, "acct-1", upto_message_id=ids[1])
    assert out["copied_messages"] == 2
    assert out["session"]["id"] != sid
    child = db.chat.messages.list_by_session(out["session"]["id"], account_id="acct-1")
    assert [m["content"] for m in child] == ["Q1", "A1"]
    # Parent is untouched.
    parent = db.chat.messages.list_by_session(sid, account_id="acct-1")
    assert [m["content"] for m in parent] == ["Q1", "A1", "Q2"]


def test_fork_without_message_copies_all(db):
    sid, _ = _seed(db)
    out = db.chat.sessions.fork(sid, "acct-1")
    assert out["copied_messages"] == 3
    child = db.chat.messages.list_by_session(out["session"]["id"], account_id="acct-1")
    assert [m["content"] for m in child] == ["Q1", "A1", "Q2"]


def test_fork_preserves_focus_and_titles_child(db):
    sid, _ = _seed(db)
    out = db.chat.sessions.fork(sid, "acct-1")
    assert out["session"]["focus_json"] == {"mode": "grow", "label": "Grow"}
    assert out["session"]["title"].startswith("\u2937")  # ⤷ branch marker
    assert out["session"]["model"] == "qwen3:14b"


def test_fork_copies_get_new_ids(db):
    sid, ids = _seed(db)
    out = db.chat.sessions.fork(sid, "acct-1")
    child = db.chat.messages.list_by_session(out["session"]["id"], account_id="acct-1")
    assert not (set(m["id"] for m in child) & set(ids))


def test_fork_unknown_message_raises(db):
    sid, _ = _seed(db)
    with pytest.raises(ValueError):
        db.chat.sessions.fork(sid, "acct-1", upto_message_id="does-not-exist")


def test_fork_other_account_is_none(db):
    sid, _ = _seed(db, account="acct-1")
    assert db.chat.sessions.fork(sid, "acct-2") is None


def test_fork_never_crosses_tenant_messages(db):
    """A fork from an account only ever copies that account's messages."""
    sid, _ = _seed(db, account="acct-1")
    db.chat.messages.create({"account_id": "acct-2", "session_id": sid,
                             "role": "user", "content": "INTRUDER"})
    out = db.chat.sessions.fork(sid, "acct-1")
    child = db.chat.messages.list_by_session(out["session"]["id"], account_id="acct-1")
    assert "INTRUDER" not in [m["content"] for m in child]


# ── Router endpoint ─────────────────────────────────────────────────────────

def test_fork_endpoint_returns_child_and_records_lineage(db):
    sid, ids = _seed(db)
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        out = chat_router.fork_session(sid, chat_router.ForkIn(upto_message_id=ids[0]), acct="acct-1")
    assert out["copied_messages"] == 1
    lineage = db.chat.forks.get_by_child(out["session"]["id"], account_id="acct-1")
    assert lineage["parent_session_id"] == sid
    assert lineage["forked_from_message_id"] == ids[0]


def test_fork_endpoint_404_unknown_session(db):
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            chat_router.fork_session("nope", chat_router.ForkIn(), acct="acct-1")
    assert "404" in str(getattr(ei.value, "status_code", "")) + str(ei.value)


def test_fork_endpoint_400_unknown_message(db):
    sid, _ = _seed(db)
    with mock.patch.object(chat_router, "get_northstar_db", return_value=db):
        with pytest.raises(Exception) as ei:
            chat_router.fork_session(sid, chat_router.ForkIn(upto_message_id="ghost"), acct="acct-1")
    assert "400" in str(getattr(ei.value, "status_code", "")) + str(ei.value)
