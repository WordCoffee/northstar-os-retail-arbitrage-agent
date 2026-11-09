"""Item 2 - the post-reboot proof.

The check's whole value is that it reports what it *measured*, so the tests measure the
measurement: a boot instant parsed from the scheduler's answer, a start line that is
genuinely after that boot, a pid that is checked rather than assumed, and a queue that
is read through `tools/director_queue.py` instead of by opening sqlite.

Nothing here spawns PowerShell or touches the real repository: the probe payload is
injected, and every path the check writes is redirected into the test's own tree.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import director_queue as Q  # noqa: E402
import post_reboot_check as P  # noqa: E402


@pytest.fixture()
def tree(tmp_path, monkeypatch):
    state = tmp_path / "state" / "director"
    state.mkdir(parents=True)
    (tmp_path / "logs").mkdir()
    (tmp_path / "reports" / "ty").mkdir(parents=True)
    for name, value in {
        "ROOT": tmp_path,
        "STATE": state,
        "PROOF_JSON": state / "reboot_proof.json",
        "PROOF_MD": tmp_path / "reports" / "ty" / "reboot_proof.md",
        "LOG": tmp_path / "logs" / "ty_director.log",
        "HANDOFF": tmp_path / "reports" / "ty" / "handoff.md",
        "PID_FILE": state / "director.pid",
    }.items():
        monkeypatch.setattr(P, name, value)
    P.LOG.write_text(
        "2026-11-08T23:59:00+00:00 started director pid=111\n"
        "2026-11-09T02:00:00+00:00 started director pid=222\n"
        "2026-11-09T02:05:00+00:00 director died in 4s with no output\n"
        "2026-11-09T02:10:00+00:00 started director pid=333\n", encoding="utf-8")
    P.HANDOFF.write_text("# handoff\n", encoding="utf-8")
    return tmp_path


BOOT = "2026-11-09T01:00:00+00:00"
TASK = {
    "name": "NorthstarTyDirector",
    "state": "Ready",
    "last_run_time": "2026-11-09T01:00:20+00:00",
    "last_task_result": 0,
    "missed_runs": 0,
}
PROBE = {"boot_utc": BOOT, "task": TASK}

#: Every log line and the handoff mtime are after this one, so "after boot" is
#: unambiguous without depending on when the test happens to run.
OLD_BOOT = "2020-01-01T00:00:00+00:00"
RUN_PROBE = {"boot_utc": OLD_BOOT, "task": TASK}


def _epoch(text: str) -> float:
    return datetime.fromisoformat(text).timestamp()


def _queue_stub() -> dict:
    return {"ok": True, "total": 3, "open": 2,
            "by_status": {"merged": 1, "queued": 1, "running": 1},
            "open_jobs": [{"id": "b", "unit": "B", "status": "running", "owner": "x"},
                          {"id": "c", "unit": "C", "status": "queued", "owner": ""}]}


def test_boot_time_comes_from_the_scheduler_answer(tree):
    boot = P.boot_time(PROBE)

    assert boot["epoch"] == _epoch(BOOT)
    assert boot["utc"].startswith("2026-11-09T01:00:00")
    assert "LastBootUpTime" in boot["source"]


def test_boot_time_falls_back_to_the_monotonic_offset(tree):
    """An unreadable CIM must not lose the check; the payload says which source ran."""
    boot = P.boot_time({})

    assert boot["epoch"] is not None
    assert "monotonic" in boot["source"]
    assert abs(boot["epoch"] - (time.time() - time.monotonic())) < 5


def test_task_state_reports_last_run_and_result(tree):
    task = P.task_state(PROBE)

    assert task["ok"] is True
    assert task["state"] == "Ready"
    assert task["last_run_time"].startswith("2026-11-09T01:00:20")
    assert task["last_task_result"] == 0
    assert task["missed_runs"] == 0
    assert task["never_run"] is False


def test_task_state_flags_a_task_that_never_ran(tree):
    probe = {"boot_utc": BOOT, "task": {
        "name": "NorthstarTyDirector", "state": "Ready",
        "last_run_time": "1999-11-30T00:00:00-07:00",
        "last_task_result": 267011, "missed_runs": 0}}

    task = P.task_state(probe)

    assert task["never_run"] is True
    assert task["last_run_time"] is None


def test_resume_evidence_picks_the_newest_start_after_the_boot(tree):
    starts = P.read_log_starts(P.LOG)
    resume = P.resume_evidence(starts, _epoch(BOOT))

    assert resume["found"] is True
    assert resume["after_boot"] is True
    assert resume["pid"] == 333
    assert resume["at"].startswith("2026-11-09T02:10:00")
    assert resume["starts_total"] == 3


def test_a_start_before_the_boot_is_not_a_resume(tree):
    """The 23:59 line predates the 01:00 boot, so only 02:00 and 02:10 count."""
    starts = P.read_log_starts(P.LOG)
    resume = P.resume_evidence(starts, _epoch(BOOT))

    assert [row["pid"] for row in starts] == [111, 222, 333]
    assert resume["pid"] != 111
    assert resume["newest_pid"] == 333


def test_no_start_line_at_all_is_reported_as_such(tree):
    P.LOG.write_text("2026-11-09T01:00:00+00:00 launcher starting\n", encoding="utf-8")

    resume = P.resume_evidence(P.read_log_starts(P.LOG), 1.0)

    assert resume["found"] is False
    assert resume["after_boot"] is False
    assert resume["pid"] is None


def test_queue_state_counts_open_jobs_by_status(tree, tmp_path):
    db = tmp_path / "state" / "director" / "queue.sqlite"
    conn = Q._connect(db)
    try:
        for job_id, status in (("a", "merged"), ("b", "running"), ("c", "queued")):
            conn.execute(
                "INSERT INTO jobs(id, unit, title, status, created_at, updated_at)"
                " VALUES (?,?,?,?,?,?)",
                (job_id, job_id.upper(), "t", status, "now", "now"))
    finally:
        conn.close()

    state = P.queue_state(Q, db)

    assert state["ok"] is True
    assert state["open"] == 2
    assert state["by_status"] == {"merged": 1, "queued": 1, "running": 1}
    assert [row["status"] for row in state["open_jobs"]] == ["running", "queued"]


def test_queue_state_without_a_database_creates_nothing(tree, tmp_path):
    db = tmp_path / "state" / "director" / "missing.sqlite"

    state = P.queue_state(Q, db)

    assert state["ok"] is True and state["total"] == 0
    assert "no queue database" in state["note"]
    assert not db.exists()


def test_handoff_mtime_proves_the_session_continued(tree):
    handoff = P.handoff_state(boot_epoch=_epoch(OLD_BOOT))

    assert handoff["exists"] is True
    assert handoff["after_boot"] is True
    assert handoff["mtime"].endswith("+00:00")


def test_run_writes_json_and_appends_a_dated_section(tree, monkeypatch):
    monkeypatch.setattr(P, "queue_state", lambda *a, **k: _queue_stub())

    first = P.run(probe=RUN_PROBE)
    second = P.run(probe=RUN_PROBE)

    record = json.loads(P.PROOF_JSON.read_text(encoding="utf-8"))
    assert record["boot"]["utc"].startswith("2020-01-01")
    assert record["resume"]["pid"] == 333
    assert record["handoff"]["after_boot"] is True
    assert record["verdict"]["task_ran_this_boot"] is True
    assert record["verdict"]["director_resumed_after_boot"] is True
    assert record["verdict"]["handoff_continued_after_boot"] is True
    assert record["queue"]["open"] == 2
    assert first["checked_epoch"] <= second["checked_epoch"]

    text = P.PROOF_MD.read_text(encoding="utf-8")
    assert text.startswith("# Reboot proof")
    assert text.count("— reboot proof") == 2        # appended, never overwritten
    assert "resumed after boot: yes" in text


def test_run_records_a_probe_failure_instead_of_raising(tree, monkeypatch):
    monkeypatch.setattr(P, "queue_state", lambda *a, **k: _queue_stub())

    def explode(*_a, **_k):
        raise RuntimeError("powershell is gone")

    monkeypatch.setattr(P, "_powershell_json", explode)

    payload = P.run()

    assert "powershell is gone" in payload["error"]
    assert json.loads(P.PROOF_JSON.read_text(encoding="utf-8"))["error"]
    assert "verdict" in payload


def test_the_json_is_written_atomically(tree, monkeypatch):
    monkeypatch.setattr(P, "queue_state", lambda *a, **k: _queue_stub())

    P.run(probe=RUN_PROBE)

    assert P.PROOF_JSON.exists()
    assert not list(P.STATE.glob("*.tmp"))


def test_a_director_pid_that_is_not_there_is_reported_as_not_alive(tree):
    P.PID_FILE.write_text(json.dumps({"pid": 999999, "started_at": "x"}),
                          encoding="utf-8")

    state = P.director_state()

    assert state["pid"] == 999999
    assert state["alive"] is False


def test_sqlite_is_never_opened_directly(tree, monkeypatch):
    """The queue has one definition of "open job", and it is not in this file."""
    source = (ROOT / "tools" / "post_reboot_check.py").read_text(encoding="utf-8")
    assert "import sqlite3" not in source


def test_root_rebases_the_reads_and_leaves_the_artefacts_with_the_code(tree, tmp_path):
    live = tmp_path / "live"

    P.configure(str(live))
    try:
        assert P.LOG == live.resolve() / "logs" / "ty_director.log"
        assert P.PID_FILE == live.resolve() / "state" / "director" / "director.pid"
        assert P.HANDOFF == live.resolve() / "reports" / "ty" / "handoff.md"
        # Artefacts stay with the code that produced them, so they can be committed.
        assert P.PROOF_JSON == P.STATE / "reboot_proof.json"
        assert P.PROOF_MD.parent == tree / "reports" / "ty"
    finally:
        P.configure(None)
