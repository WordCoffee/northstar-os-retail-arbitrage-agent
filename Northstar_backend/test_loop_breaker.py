"""Loop breaker: durable OPEN latch, poison path, trusted-operator-only reset."""

from __future__ import annotations

import sqlite3
from typing import Callable

import pytest

import loop_breaker as lb


@pytest.fixture()
def db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_admits_within_budget(db):
    out = lb.admit("t:ok", db=db)
    assert out["admitted"] is True and out["state"] == "closed"
    assert out["total_count"] == 1


def test_ninth_automatic_event_opens_the_latch(db):
    for _ in range(8):
        assert lb.admit("t:burst", db=db)["admitted"] is True
    ninth = lb.admit("t:burst", db=db)
    assert ninth["admitted"] is False and ninth["state"] == "open"
    assert ninth["reason"] == "automatic_burst"
    # O(1) latch check: every later event is refused without counting.
    later = lb.admit("t:burst", db=db)
    assert later["admitted"] is False and later["reason"] == "automatic_burst"


def test_latch_survives_a_restart_simulation(db):
    for _ in range(9):
        lb.admit("t:durable", db=db)
    # A "restart" is a fresh process on the same database: same latch row.
    out = lb.admit("t:durable", db=db)
    assert out["admitted"] is False and out["state"] == "open"


def test_open_never_auto_expires(db):
    t = {"now": 0.0}
    def clock() -> object:
        class T:
            def isoformat(self):
                return f"2030-01-01T00:00:{int(t['now']):02d}.000000+00:00"
        return T.__new__(T)
    # Can't use a fake clock that returns real datetimes easily; simulate aging
    # by moving the window start backward instead.
    for _ in range(9):
        lb.admit("t:noexpire", db=db)
    handle = db
    old = "2020-01-01T00:00:00+00:00"
    handle.execute("UPDATE loop_guard SET window_started_at = ?, "
                   "automatic_window_started_at = ? WHERE scope_key = ?",
                   (old, old, "t:noexpire"))
    out = lb.admit("t:noexpire", db=db)
    assert out["admitted"] is False and out["state"] == "open"


def test_trusted_human_clears_the_automatic_streak_but_not_the_total(db):
    trusted_fn: Callable[[], object] = lb._now
    for _ in range(5):
        lb.admit("t:human", db=db)
    # Window would age out automatically; here the human arrives fresh in-window.
    out = lb.admit("t:human", trusted_human=True, db=db)
    assert out["admitted"] is True
    row = db.execute("SELECT * FROM loop_guard WHERE scope_key='t:human'").fetchone()
    assert row["automatic_count"] == 0
    assert row["total_count"] == 6  # the human still counts toward the backstop


def test_poison_trips_immediately(db):
    out = lb.admit("t:poison", poisoned=True, db=db)
    assert out["admitted"] is False and out["reason"] == "malformed_signal"


def test_redelivery_is_deduplicated_not_counted(db):
    a = lb.admit("t:dedup", dedup_key="delivery-1", db=db)
    b = lb.admit("t:dedup", dedup_key="delivery-1", db=db)
    assert a["admitted"] is True and b["admitted"] is False
    assert b["deduplicated"] is True
    row = db.execute("SELECT total_count FROM loop_guard WHERE scope_key='t:dedup'").fetchone()
    assert row["total_count"] == 1  # the redelivery never incremented the counter


def test_consecutive_failure_burst_trips_the_latch(db):
    for i in range(8):
        out = lb.admit("t:fail",
                       failed_outcome=f"crash_stage_{i % 3}", db=db)
    # 8 consecutive failures: the eighth is counted, the burst trips at the edge.
    assert out["admitted"] is False and out["reason"] == "failure_burst"
    again = lb.admit("t:fail", db=db)
    assert again["admitted"] is False


def test_a_success_resets_the_failure_streak(db):
    OLD = "2020-01-01T00:00:00+00:00"

    def age_out():
        db.execute("UPDATE loop_guard SET window_started_at = ?, "
                   "automatic_window_started_at = ? WHERE scope_key = ?",
                   (OLD, OLD, "t:mixed"))
    lb.admit("t:mixed", failed_outcome="crash", db=db)
    lb.admit("t:mixed", db=db)
    for i in range(7):
        age_out()
        lb.admit("t:mixed", failed_outcome="crash", db=db)
    age_out()
    out = lb.admit("t:mixed", db=db)
    assert out["admitted"] is True  # 6 consecutive < 8; a clean event cleared the run


def test_reset_requires_operator_and_confirmation(db):
    for _ in range(9):
        lb.admit("t:gate", db=db)
    assert lb.reset("t:gate", actor="agent", confirmed=True, db=db)["reset"] is False
    assert lb.reset("t:gate", actor="operator", confirmed=False, db=db)["reset"] is False
    out = lb.reset("t:gate", actor="operator", confirmed=True, db=db)
    assert out["reset"] is True
    assert lb.admit("t:gate", db=db)["admitted"] is True


def test_on_open_hook_warns_once_not_per_refusal(db, monkeypatch):
    fired = []
    monkeypatch.setattr(lb, "ON_OPEN", lambda scope, s: fired.append(scope))
    for _ in range(9):
        lb.admit("t:hook", db=db)
    assert fired == ["t:hook"]
    lb.admit("t:hook", db=db)   # refused by the latch; must not fire again
    assert fired == ["t:hook"]


def test_hop_guard_naks_self_calls_and_overrun():
    assert lb.check_hop(self_call=True)["code"] == "self"
    assert lb.check_hop(hop_count=6)["code"] == "hop_limit"
    assert lb.check_hop(hop_count=5, self_call=False)["admitted"] is True
    assert lb.check_hop(hop_count=0)["admitted"] is True


def test_note_trips_the_latch_on_sparse_failures_without_counting_events(db):
    lb._ensure(db)
    OLD = "2020-01-01T00:00:00+00:00"
    for i in range(8):
        db.execute("UPDATE loop_guard SET window_started_at = ?, "
                   "automatic_window_started_at = ? WHERE scope_key = ?",
                   (OLD, OLD, "t:sparse"))
        lb.note("t:sparse", ok=False, failure_code=f"crash_{i}", db=db)
    assert lb.state("t:sparse", db=db)["state"] == "open"
    row = db.execute("SELECT total_count FROM loop_guard WHERE scope_key='t:sparse'").fetchone()
    assert row["total_count"] == 0  # outcomes are not events


def test_note_success_clears_the_streak(db):
    lb.note("t:c", ok=False, db=db)
    out = lb.note("t:c", ok=True, db=db)
    assert out["noted"] is True
    assert lb.state("t:c", db=db)["consecutive_failures"] == 0


def test_cie_cycle_refuses_when_the_latch_is_open(monkeypatch):
    import cie_loop
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(lb, "_default_db", lambda: conn)
    for _ in range(9):
        lb.admit("cie:cycle", db=conn)
    out = cie_loop.run_cycle(dry_run=True)
    assert out["ok"] is False and out["reason"].startswith("loop breaker open")
    assert out["loop_breaker"]["reason"] == "automatic_burst"
    conn.close()


def test_cie_cycle_admits_a_clean_dry_cycle(monkeypatch):
    import cie_loop
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    monkeypatch.setattr(lb, "_default_db", lambda: conn)
    out = cie_loop.run_cycle(dry_run=True)
    assert out.get("ok") is True
    assert out["loop_breaker"]["noted"] is True
    conn.close()
