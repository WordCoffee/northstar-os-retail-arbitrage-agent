"""Tool Execution Gateway tests (V3 REA inject).

Covers the OpenBot-pattern gateway: deny-list enforcement, audit logging
(allowed + denied + executed), pass-through for registered tools, and honest
denials that never raise. Offline: no VoiceStudio, no network, no server.
"""

from __future__ import annotations

import json
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

import chat_schema  # noqa: E402
import chat_tools  # noqa: E402
import tool_gateway  # noqa: E402


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
        import data_layer
        self.chat = data_layer.ChatContainer(self.layer)


@pytest.fixture()
def db():
    return _FakeNorthstarDB()


def test_deny_list_blocks_shell_and_logs(db):
    out = tool_gateway.run_tool_gated(db.chat, "acct-1", "shell", {})
    assert out["ok"] is False
    assert "deny-list" in out["error"]
    rows = db.chat.tool_audit.list_by_account("acct-1")
    assert len(rows) == 1
    assert rows[0]["decision"] == "denied"
    assert rows[0]["tool"] == "shell"


def test_unknown_tool_denied_and_logged(db):
    out = tool_gateway.run_tool_gated(db.chat, "acct-1", "time_travel", {})
    assert out["ok"] is False
    rows = db.chat.tool_audit.list_by_account("acct-1")
    assert [r["decision"] for r in rows] == ["denied"]


def test_registered_tool_passes_through_and_audits(db):
    # system_status is a registered tool that runs offline.
    out = tool_gateway.run_tool_gated(db.chat, "acct-1", "system_status", {})
    assert out["ok"] is True
    decisions = [r["decision"] for r in db.chat.tool_audit.list_by_account("acct-1")]
    # list_by_account returns newest-first, so the executed row leads.
    assert decisions == ["executed", "allowed"]
    executed = db.chat.tool_audit.list_by_account("acct-1")[0]
    assert "elapsed_ms" in executed["detail"]


def test_gateway_never_raises_on_bad_db(db):
    db.chat.tool_audit = None  # audit must never break the turn
    out = tool_gateway.run_tool_gated(db.chat, "acct-1", "system_status", {})
    assert out["ok"] is True


def test_is_denied_boundary():
    assert tool_gateway.is_denied("shell") is True
    assert tool_gateway.is_denied("credential_read") is True
    assert tool_gateway.is_denied("generate_image") is False
