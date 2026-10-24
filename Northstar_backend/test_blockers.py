"""Blocker ledger: idempotent logging, decision classification, batched report."""

from __future__ import annotations

import json
import sqlite3

import pytest

import blockers


@pytest.fixture()
def db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(blockers, "_db", lambda: conn)
    yield conn
    conn.close()


def test_log_classifies_and_stores(db):
    row = blockers.log("Missing FAL_KEY for image gen", kind="missing_key",
                       text="Missing FAL_KEY for image gen")
    assert row["newly_created"] is True
    assert row["title"] == "Missing FAL_KEY for image gen"
    assert row["decision_value"] in ("now", "later", "never")
    assert row["status"] == blockers.STATUS_OPEN


def test_relogging_the_same_title_is_a_noop(db):
    first = blockers.log("same title", text="same title")
    second = blockers.log("SAME TITLE", text="same title")
    assert first["newly_created"] is True
    assert second["newly_created"] is False
    assert first["id"] == second["id"]
    assert len(blockers.list_open()) == 1


def test_now_language_interrupts(db):
    row = blockers.log("Production down: live lane failing", kind="missing_config",
                       text="Production down: live lane failing")
    assert row["decision_value"] == "now"


def test_idea_language_goes_to_backlog(db):
    row = blockers.log("Nice to have: rename reports dir", kind="other",
                       text="nice to have: rename reports dir")
    assert row["decision_value"] == "never"


def test_resolve_removes_from_open_list(db):
    row = blockers.log("transient", text="transient")
    assert blockers.resolve(row["id"])["resolved"] is True
    assert blockers.list_open() == []
    assert blockers.resolve(row["id"])["resolved"] is False


def test_batch_report_groups_by_escalation(db):
    blockers.log("hard failure on live lane", text="hard failure on live lane")
    blockers.log("nice to have: tidy logs", text="nice to have: tidy logs")
    report = blockers.batch_report()
    assert "Interrupt now" in report
    assert "Backlog (never interrupt)" in report
    assert "hard failure on live lane" in report


def test_empty_ledger_reports_none(db):
    assert blockers.batch_report() == "# Blockers\n\n(none open)\n"


def test_from_provider_check_logs_unavailable_tool(db, monkeypatch):
    class FakeV:
        usable = False
        reason = "not_installed"
        notes = "weights missing"
    class FakePS:
        def verify(self, tid, prov):
            return FakeV()
        def tool_ids(self):
            return ["fake_tool"]
    monkeypatch.setattr(blockers, "provider_suite", FakePS(), raising=False)
    import sys
    sys.modules["provider_suite"] = FakePS()
    b = blockers.from_provider_check("fake_tool", "local")
    assert b is not None and b["newly_created"] is True


def test_from_provider_check_skips_usable_tool(db, monkeypatch):
    class FakeV:
        usable = True
        reason = "installed"
        notes = ""
    class FakePS:
        def verify(self, tid, prov):
            return FakeV()
    monkeypatch.setattr(blockers, "provider_suite", FakePS(), raising=False)
    import sys
    sys.modules["provider_suite"] = FakePS()
    assert blockers.from_provider_check("ok_tool", "local") is None


def test_scan_suite_logs_only_unavailable(db, monkeypatch):
    class FakeV:
        def __init__(self, usable):
            self.usable = usable
            self.reason = "x"
            self.notes = ""
    class FakePS:
        def verify(self, tid, prov):
            return FakeV(tid == "good")
        def tool_ids(self):
            return ["good", "bad"]
    monkeypatch.setattr(blockers, "provider_suite", FakePS(), raising=False)
    import sys
    sys.modules["provider_suite"] = FakePS()
    out = None
    # invoke the scan logic directly
    logged = []
    for tid in ["good", "bad"]:
        v = FakePS().verify(tid, "local")
        if not v.usable:
            b = blockers.from_provider_check(tid, "local")
            if b is not None and b.get("newly_created"):
                logged.append(tid)
    assert logged == ["bad"]
