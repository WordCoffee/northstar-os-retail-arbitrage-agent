"""Regression: a concurrent writer must WAIT for the SQLite lock, never 500.

Defect found 2026-10-28 during the MOGRA T3 acceptance run. A chat turn holds the
SQLite write lock while it runs (it writes the user message, then tool calls and
asset rows, then the assistant message — with a multi-minute render in between).
`data_layer` opened its connection with the stdlib default timeout (5 s) and no
`busy_timeout`, so a second writer — including POST /api/chat/sessions when the
operator starts a new chat — raised

    sqlite3.OperationalError: database is locked

and the route returned HTTP 500. That made "New chat" fail intermittently, which
in turn left the browser with no session pointer, so a reload resumed an
unrelated session instead of the one that carried the turn.

These tests pin the contract: the connection waits, and a competing writer
succeeds once the lock is released.
"""

import sqlite3
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

pytest.importorskip("data_layer")


def _db_at(tmp_path, monkeypatch):
    import data_layer

    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "locktest.db")
    return data_layer.DataLayer()


def test_connection_sets_a_busy_timeout(tmp_path, monkeypatch):
    db = _db_at(tmp_path, monkeypatch)
    busy = db._conn.execute("PRAGMA busy_timeout").fetchone()[0]
    # The stdlib default is 5 s, which is what produced the 500: a chat turn can
    # hold the write lock for far longer than that. The contract is a real budget.
    assert busy >= 30000, f"busy_timeout is {busy} ms; a turn can hold the lock for minutes"


def test_a_competing_writer_waits_instead_of_failing(tmp_path, monkeypatch):
    """Hold the write lock past the old 5 s default; the app's writer must wait."""
    db = _db_at(tmp_path, monkeypatch)
    other = sqlite3.connect(str(tmp_path / "locktest.db"),
                            timeout=30.0, check_same_thread=False)
    holding = threading.Event()
    released = threading.Event()

    def hold_then_release():
        other.execute("PRAGMA busy_timeout=30000")
        other.execute("BEGIN IMMEDIATE")
        holding.set()
        time.sleep(7.0)                 # longer than the old 5 s budget
        other.execute("COMMIT")
        released.set()

    t = threading.Thread(target=hold_then_release)
    t.start()
    try:
        assert holding.wait(5), "competing writer never took the lock"
        started = time.time()
        db.execute(
            "INSERT INTO chat_sessions (id, account_id, title, mode, model, created_at,"
            " updated_at) VALUES ('wait-probe', 'org-t', 'waited', 'simple', 'bojo',"
            " '2026-10-28T00:00:00', '2026-10-28T00:00:00')"
        )
        db.commit()
        waited = time.time() - started
        assert released.is_set(), "competing writer never committed"
        assert waited >= 5.0, f"writer returned after {waited:.1f}s without contending"
        assert db.execute(
            "SELECT id FROM chat_sessions WHERE id='wait-probe'").fetchone() is not None
    finally:
        t.join(15)
        other.close()
