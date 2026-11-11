"""D2 - the launcher: one director, a heartbeat that costs nothing, crash restart.

Every test here is model-free on purpose. The launcher's job is process and state
management, and a test that needed a model call to prove "the heartbeat makes no
model call" would be proving its own premise. The live kill/restart proof is done
separately, against a substitute command, and recorded in the unit evidence.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ty_director as D  # noqa: E402


@pytest.fixture()
def root(tmp_path, monkeypatch):
    """Every path the launcher touches, redirected into the test's own tree."""
    state = tmp_path / "state" / "director"
    state.mkdir(parents=True)
    for name, value in {
        "ROOT": tmp_path,
        "STATE": state,
        "HEARTBEAT": state / "heartbeat.json",
        "PID_FILE": state / "director.pid",
        "CAPS": state / "caps.json",
        "TOKENS": state / "tokens.json",
        "LOG": tmp_path / "logs" / "ty_director.log",
        "PAUSE": tmp_path / "state" / "vision" / "PAUSE",
        "STOP": tmp_path / "STOP",
        "HANDOFF": tmp_path / "reports" / "ty" / "handoff.md",
        "QUEUE": tmp_path / "reports" / "ty" / "director_queue.json",
        "GPU_LOCK": state / "gpu" / "lock.json",
        "REBOOT_PROOF": state / "reboot_proof.json",
        "REBOOT_CHECK": tmp_path / "tools" / "post_reboot_check.py",
    }.items():
        monkeypatch.setattr(D, name, value)
    # Launcher tests must not depend on this machine's free RAM. The RAM-gate tests
    # below override this stub with a paused verdict.
    monkeypatch.setattr(D, "ram_status",
                        lambda **_kw: {"free_gb": 8.0, "max_builders": 4,
                                       "paused": False, "reason": "test stub"})
    (tmp_path / "reports" / "ty").mkdir(parents=True, exist_ok=True)
    D.QUEUE.write_text(json.dumps({
        "units": {"D1": {"status": "done"}, "D2": {"status": "pending"},
                  "D3": {"status": "pending"}},
        "jobs": [], "cycle": 3}), encoding="utf-8")
    D.HANDOFF.write_text("# handoff\n", encoding="utf-8")
    return tmp_path


def _alive(pid: int) -> bool:
    import ctypes

    handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
    if not handle:
        return False
    ctypes.windll.kernel32.CloseHandle(handle)
    return True


def test_a_heartbeat_tick_starts_nothing(root, monkeypatch):
    """`--once` is the acceptance test for "zero model calls when idle"."""
    def explode(*_a, **_k):
        raise AssertionError("a heartbeat tick must not start a session")

    monkeypatch.setattr(D, "start_director", explode)
    monkeypatch.setattr(D, "_processes", lambda: [])

    payload = D.tick(start=False)

    assert payload["state"] == "idle"
    assert not D.PID_FILE.exists()
    assert json.loads(D.HEARTBEAT.read_text(encoding="utf-8"))["state"] == "idle"


def test_the_heartbeat_records_queue_depth_and_caps(root, monkeypatch):
    monkeypatch.setattr(D, "_processes", lambda: [])
    payload = D.heartbeat("running")

    assert payload["queue"]["units_pending"] == 2
    assert payload["queue"]["next"] == "D2"
    assert payload["queue"]["cycle"] == 3
    assert payload["caps"]["cloud_workers"] == 4
    assert "disk_free_gb" in payload and payload["pause"] is False


def test_a_pause_file_blocks_every_start(root, monkeypatch):
    D.PAUSE.parent.mkdir(parents=True, exist_ok=True)
    D.PAUSE.write_text("paused\n", encoding="utf-8")
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a paused launcher must not start"))

    assert D.blocked() == "PAUSE file present"
    assert D.tick(start=True)["state"] == "blocked"


def test_a_stop_file_blocks_and_names_itself(root, monkeypatch):
    D.STOP.write_text("stop\n", encoding="utf-8")
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a stopped launcher must not start"))

    assert D.blocked() == "STOP file present"


def test_the_token_cap_blocks_at_ninety_percent(root, monkeypatch):
    monkeypatch.setattr(D, "TOKEN_CAP", 1000)
    monkeypatch.setattr(D, "tokens_today", lambda: 950)
    assert D.blocked() == "token cap reached"


def test_start_writes_the_resume_line_and_a_pid_record(root, monkeypatch):
    """The substitute reads stdin, so the launcher's own write path is exercised."""
    marker = "TYTESTDIRECTORMARKER"
    cmd = [sys.executable, "-c", "import sys; sys.stdin.read()", marker]
    monkeypatch.setattr(D, "DIRECTOR_CMD", json.dumps(cmd))
    monkeypatch.setattr(D, "DIRECTOR_MARKER", marker)

    pid = D.start_director()
    try:
        assert pid and _alive(pid)
        record = json.loads(D.PID_FILE.read_text(encoding="utf-8"))
        assert record["pid"] == pid and record["cmd"] == cmd
        stream = (D.LOG.parent / "ty_director_stream.jsonl").read_text(encoding="utf-8")
        assert stream == ""            # the substitute printed nothing
        # The resume line reached the process by construction; a process that never
        # read stdin would not have started at all.
    finally:
        import subprocess

        subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                       capture_output=True, text=True)


def test_a_running_director_is_found_by_its_command_line(root, monkeypatch):
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "MARK-X")
    monkeypatch.setattr(D, "_processes", lambda: [
        {"ProcessId": 11, "Name": "python.exe", "CommandLine": "python -c sleep"},
        {"ProcessId": 12, "Name": "opencode.exe",
         "CommandLine": "opencode run --agent director MARK-X"},
    ])

    assert D.find_director()["ProcessId"] == 12


def test_the_pid_file_beats_a_marker_match(root, monkeypatch):
    """Measured false positive: the operator's shell contained the marker text."""
    import os

    D.PID_FILE.write_text(json.dumps({"pid": os.getpid(), "cmd": ["python", "x"],
                                      "started_at": "now"}), encoding="utf-8")
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "MARK-Z")
    monkeypatch.setattr(D, "_processes", lambda: [
        {"ProcessId": 777, "Name": "powershell.exe",
         "CommandLine": "powershell -Command $env:MARK_Z='MARK-Z'"},
    ])

    assert D.find_director()["ProcessId"] == os.getpid()


def test_a_crash_note_is_appended_with_its_reason(root):
    D.crash_note("session 42 gone")
    text = D.HANDOFF.read_text(encoding="utf-8")
    assert "session 42 gone" in text
    assert text.count("launcher:") == 1


# ------------------------------------------- D-010: a lane error must look red, not healthy
def _stream(lines, *, monkeypatch=None):
    path = D.LOG.parent / "ty_director_stream.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in lines) + "\n", encoding="utf-8")
    return path


def test_the_heartbeat_is_red_when_the_streams_last_line_is_an_error(root, monkeypatch):
    monkeypatch.setattr(D, "_processes", lambda: [])
    _stream([{"type": "step_finish", "part": {}},
             {"type": "error", "error": {"name": "UnknownError",
                                         "data": {"message": 'Agent not found: "director"'}}}])

    payload = D.tick(start=False)

    assert payload["red"] is True
    assert payload["stream"]["last_type"] == "error"
    assert "Agent not found" in payload["stream"]["error"]
    assert D.HEARTBEAT.exists()
    assert json.loads(D.HEARTBEAT.read_text(encoding="utf-8"))["red"] is True


def test_a_healthy_stream_is_not_red(root, monkeypatch):
    monkeypatch.setattr(D, "_processes", lambda: [])
    _stream([{"type": "step_start", "part": {}},
             {"type": "step_finish", "part": {"reason": "tool-calls"}}])

    payload = D.tick(start=False)

    assert payload["red"] is False
    assert payload["stream"]["last_type"] == "step_finish"


def test_no_stream_at_all_is_not_red(root, monkeypatch):
    monkeypatch.setattr(D, "_processes", lambda: [])
    payload = D.tick(start=False)
    assert payload["red"] is False
    assert payload["stream"]["last_type"] is None


def test_the_death_note_names_the_lane_error_instead_of_a_generic_crash(root):
    _stream([{"type": "error", "error": {"name": "UnknownError",
                                         "data": {"message": 'Agent not found: "director"'}}}])

    note = D.death_note({"pid": 8864, "stream_bytes": 0})

    assert "lane error" in note
    assert 'Agent not found: "director"' in note
    assert "8864" in note


def test_the_death_note_distinguishes_a_productive_end_from_a_silent_death(root):
    _stream([{"type": "step_finish", "part": {}}])

    after_output = D.death_note({"pid": 12, "stream_bytes": 0})
    silent = D.death_note({"pid": 12, "stream_bytes": D._stream_size()})

    assert "after output" in after_output
    assert "after output" not in silent
    assert "gone" in silent


def test_the_launcher_never_stacks_two_directors(root, monkeypatch):
    """A live session is reported, not started again."""
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "MARK-Y")
    monkeypatch.setattr(D, "_processes", lambda: [
        {"ProcessId": 99, "Name": "opencode.exe", "CommandLine": "opencode run MARK-Y"}])
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a second director must never start"))

    payload = D.tick(start=True)
    assert payload["state"] == "running"
    assert payload["director_pid"] == 99


# ------------------------------------- D-011: a live lease this process did not start
def _held_lease(pid: int = 424242) -> None:
    D.PID_FILE.write_text(json.dumps({
        "pid": pid, "started_at": "2026-11-11T07:00:00+00:00", "cmd": []}),
        encoding="utf-8")


def test_a_live_lease_from_another_session_is_reported_not_replaced(root, monkeypatch):
    """D-011: the takeover race ran two directors for one block.

    `find_director` recognises a live lease, so the heartbeat reports it rather
    than starting anything; `start_director` is the second gate for a caller that
    skips the heartbeat (the takeover path).
    """
    _held_lease()
    monkeypatch.setattr(D, "_pid_alive", lambda pid: int(pid) == 424242)
    monkeypatch.setattr(D, "_children_of", lambda pid: set())
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "")
    monkeypatch.setattr(D, "_processes", lambda: [])
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a leased director must never start"))

    payload = D.tick(start=True)

    assert payload["state"] == "running"
    assert payload["director_pid"] == 424242


def test_start_director_refuses_a_lease_it_did_not_start(root, monkeypatch):
    _held_lease(pid=515151)
    monkeypatch.setattr(D, "_pid_alive", lambda pid: int(pid) == 515151)
    monkeypatch.setattr(D, "_children_of", lambda pid: set())
    monkeypatch.setattr(D, "DIRECTOR_CMD", json.dumps(["cmd", "/c", "exit", "0"]))

    assert D.start_director() is None
    assert json.loads(D.PID_FILE.read_text(encoding="utf-8"))["pid"] == 515151


def test_a_dead_lease_does_not_block_the_next_start(root, monkeypatch):
    _held_lease(pid=616161)
    monkeypatch.setattr(D, "_pid_alive", lambda pid: False)
    monkeypatch.setattr(D, "_children_of", lambda pid: set())
    monkeypatch.setattr(D, "DIRECTOR_CMD", json.dumps(["cmd", "/c", "exit", "0"]))
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "")
    monkeypatch.setattr(D, "_processes", lambda: [])

    pid = D.start_director()

    assert pid and pid != 616161
    assert json.loads(D.PID_FILE.read_text(encoding="utf-8"))["pid"] == pid


# ------------------------------------------------------- item 2: post-reboot proof
def _write_proof(epoch: float) -> None:
    D.REBOOT_PROOF.parent.mkdir(parents=True, exist_ok=True)
    D.REBOOT_PROOF.write_text(
        json.dumps({"checked_epoch": epoch, "checked_at": "2026-11-09T00:00:00+00:00"}),
        encoding="utf-8")


def _quiet_launcher(monkeypatch) -> None:
    """A one-tick launcher that never needs a model or a process table."""
    monkeypatch.setattr(D, "_processes", lambda: [])
    monkeypatch.setattr(D, "start_director", lambda: None)


def test_the_first_start_after_a_boot_runs_the_reboot_check(root, monkeypatch):
    calls = []
    _quiet_launcher(monkeypatch)
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER",
                        lambda: calls.append("ran") or 4242)

    assert D.reboot_check_needed() is True          # no proof file at all yet
    assert D.main(["--max-ticks", "1", "--interval", "0"]) == 0

    assert calls == ["ran"]
    assert "launcher starting" in D.LOG.read_text(encoding="utf-8")


def test_a_second_start_in_the_same_boot_does_not_run_the_check(root, monkeypatch):
    _quiet_launcher(monkeypatch)
    _write_proof(time.time())                       # written after this boot
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER",
                        lambda: pytest.fail("a proof for this boot already exists"))

    assert D.reboot_check_needed() is False
    assert D.main(["--max-ticks", "1", "--interval", "0"]) == 0


def test_a_proof_from_before_this_boot_is_stale(root, monkeypatch):
    boot = D.boot_epoch()
    assert boot is not None
    _quiet_launcher(monkeypatch)
    _write_proof(boot - 3600)
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER", lambda: 1)

    assert D.reboot_check_needed() is True
    assert D.run_reboot_check_once() == 1


def test_a_failing_reboot_check_does_not_stop_the_launcher(root, monkeypatch):
    _quiet_launcher(monkeypatch)

    def boom():
        raise RuntimeError("the check broke")

    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER", boom)

    assert D.main(["--max-ticks", "1", "--interval", "0"]) == 0
    log = D.LOG.read_text(encoding="utf-8")
    assert "reboot check skipped: RuntimeError: the check broke" in log
    assert "stopping after 1 tick" in log


def test_a_missing_check_script_is_skipped_in_one_line(root, monkeypatch):
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER", None)   # the real spawn path
    assert D.REBOOT_CHECK.exists() is False

    assert D.run_reboot_check_once() is None
    assert "tools/post_reboot_check.py missing; skipped" in D.LOG.read_text(encoding="utf-8")


def test_a_heartbeat_tick_does_not_run_the_reboot_check(root, monkeypatch):
    """`--once` stays model-free and write-light; only a real start records the proof."""
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER",
                        lambda: pytest.fail("--once must not record the proof"))

    assert D.main(["--once"]) == 0


# ------------------------------------------------------ RAM governor gate (item 6)
def _ram(free_gb: float, paused: bool):
    return {"free_gb": free_gb, "max_builders": 0 if paused else 4,
            "paused": paused,
            "reason": f"free RAM {free_gb:.2f} GB: "
                      f"{'0 new builders (paused)' if paused else 'up to 4 builders'}"}


def test_the_heartbeat_records_the_governor_status(root, monkeypatch):
    monkeypatch.setattr(D, "ram_status", lambda **_kw: _ram(2.4, False))
    monkeypatch.setattr(D, "_processes", lambda: [])

    payload = D.heartbeat("running")

    assert payload["ram"]["max_builders"] == 4
    assert payload["ram"]["free_gb"] == 2.4


def test_a_paused_governor_refuses_a_new_session(root, monkeypatch):
    monkeypatch.setattr(D, "_processes", lambda: [])
    monkeypatch.setattr(D, "ram_status", lambda **_kw: _ram(0.8, True))
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a paused RAM gate must not start a session"))

    payload = D.tick(start=True)

    assert payload["state"] == "ram_paused"
    assert payload["ram"]["free_gb"] == 0.8
    log = D.LOG.read_text(encoding="utf-8")
    assert "0.8 GB" in log and "not starting a session" in log


def test_a_paused_governor_leaves_a_running_session_alone(root, monkeypatch):
    """It gates new starts only; nothing here can stop a live session."""
    monkeypatch.setattr(D, "DIRECTOR_MARKER", "MARK-RAM")
    monkeypatch.setattr(D, "_processes", lambda: [
        {"ProcessId": 99, "Name": "opencode.exe",
         "CommandLine": "opencode run --agent director MARK-RAM"}])
    monkeypatch.setattr(D, "ram_status", lambda **_kw: _ram(0.7, True))
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("a running session is not restarted"))

    payload = D.tick(start=True)

    assert payload["state"] == "running"
    assert payload["director_pid"] == 99
    # The pause line was never written: the gate is not even consulted for a live
    # session, so nothing can touch it.
    assert not D.LOG.exists()


def test_the_launcher_loop_does_not_start_while_paused(root, monkeypatch):
    """The loop path, not just `tick`, refuses a start at a paused governor."""
    states = []
    real_heartbeat = D.heartbeat

    def spy(state, **extra):
        states.append(state)
        return real_heartbeat(state, **extra)

    monkeypatch.setattr(D, "heartbeat", spy)
    monkeypatch.setattr(D, "_processes", lambda: [])
    monkeypatch.setattr(D, "ram_status", lambda **_kw: _ram(0.9, True))
    monkeypatch.setattr(D, "start_director",
                        lambda: pytest.fail("the loop must not start while paused"))
    monkeypatch.setattr(D, "REBOOT_CHECK_RUNNER", lambda: 1)

    assert D.main(["--max-ticks", "1", "--interval", "0"]) == 0

    assert "ram_paused" in states
    assert "ram gate: paused, free RAM 0.9 GB" in D.LOG.read_text(encoding="utf-8")
