"""Ty Director launcher - the part that fixes "it stopped again".

A chat turn ends when the model writes a final message, so the loop cannot live in
the chat. This process keeps exactly one director session alive, heartbeats without
calling a model, restarts a dead session with the resume line and a one-line crash
note, and stops only at the token cap, the PAUSE file, or the end state.

    python scripts/ty_director.py --status     # one look, no model call, no writes
    python scripts/ty_director.py --once       # one heartbeat tick, then exit
    python scripts/ty_director.py              # the loop

The heartbeat is deliberately model-free: it reads files and process tables only.
A heartbeat that spends tokens to say "nothing changed" is a leak.

Nothing here starts a second director. `find_director` matches the process command
line (the hazard learned on this box: match CommandLine, not the exe name, and never
trust stdout text to tell you a process is alive).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "director"
HEARTBEAT = STATE / "heartbeat.json"
PID_FILE = STATE / "director.pid"
CAPS = STATE / "caps.json"
TOKENS = STATE / "tokens.json"
LOG = ROOT / "logs" / "ty_director.log"
PAUSE = ROOT / "state" / "vision" / "PAUSE"
STOP = ROOT / "STOP"
HANDOFF = ROOT / "reports" / "ty" / "handoff.md"
QUEUE = ROOT / "reports" / "ty" / "director_queue.json"
GPU_LOCK = ROOT / "state" / "gpu" / "lock.json"
REBOOT_PROOF = STATE / "reboot_proof.json"
REBOOT_CHECK = ROOT / "tools" / "post_reboot_check.py"

TOKEN_CAP = int(os.environ.get("TY_TOKEN_CAP_PER_DAY", "3000000"))
CAP_FRACTION = 0.90
HEARTBEAT_S = int(os.environ.get("TY_HEARTBEAT_S", "300"))
FAST_EXIT_S = 30
BACKOFF_S = int(os.environ.get("TY_DIRECTOR_BACKOFF_S", "300"))

RESUME = (
    "Hi, I'd like to give a work order to Ty. Resume the director program. Read "
    "reports/ty/director_work_order.md, ty/MANDATE.md, reports/ty/director_queue.json, "
    "and reports/ty/handoff.md, then continue from the first unfinished unit. "
    "No questions, no reports between cycles. Idle means re-plan."
)

#: How a live director session is recognised by its command line. Overridable so the
#: crash/restart behaviour can be proven without spending a model call (D2).
DIRECTOR_MARKER = os.environ.get("TY_DIRECTOR_MARKER", "--agent director")

#: A JSON argv list that replaces `opencode run ...`. The resume line is still
#: written to stdin, so a substitute process proves the launcher, not the model.
DIRECTOR_CMD = os.environ.get("TY_DIRECTOR_CMD", "")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{_now()} {message}\n")


#: Test seam: a callable that replaces the detached spawn, so "ran / did not run"
#: can be proven without starting a child process.
REBOOT_CHECK_RUNNER: Optional[Any] = None


def boot_epoch() -> Optional[float]:
    """This boot's instant, without a subprocess.

    On Windows `time.monotonic()` counts from boot, so `time.time() - monotonic()`
    is the boot second. It costs nothing, which is what lets the launcher ask the
    question on every start.
    """
    try:
        return time.time() - time.monotonic()
    except (OSError, ValueError):
        return None


def reboot_check_needed() -> bool:
    """True when the recorded proof predates this boot, or was never written."""
    boot = boot_epoch()
    if boot is None:
        return False
    record = _read(REBOOT_PROOF, {})
    if not isinstance(record, dict) or not record:
        return True
    try:
        written = float(record.get("checked_epoch") or 0)
    except (TypeError, ValueError):
        return True
    return written < boot


def run_reboot_check_once() -> Optional[int]:
    """Record the post-reboot proof, at most once per boot.

    Runs on the launcher's own start, before the first director session, because the
    proof is about *this* boot and a session that already began has nothing to add to
    it. The check is spawned detached and never waited on: it costs a few milliseconds
    and cannot hold the session, which is the requirement that matters. A check that
    fails writes nothing, is reported in one log line, and the launcher carries on -
    the proof is nice to have, the loop is not.
    """
    try:
        if not reboot_check_needed():
            return None
        if REBOOT_CHECK_RUNNER is not None:
            return REBOOT_CHECK_RUNNER()
        if not REBOOT_CHECK.exists():
            log("reboot check: tools/post_reboot_check.py missing; skipped")
            return None
        creationflags = 0
        if os.name == "nt":
            creationflags = (getattr(subprocess, "DETACHED_PROCESS", 0)
                             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        proc = subprocess.Popen(
            [sys.executable, str(REBOOT_CHECK), "--quiet"],
            cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, creationflags=creationflags, close_fds=True)
        log(f"reboot check: no proof for this boot; started pid={proc.pid}")
        return proc.pid
    except Exception as exc:  # noqa: BLE001 - a proof must never stop the launcher
        try:
            log(f"reboot check skipped: {type(exc).__name__}: {exc}")
        except OSError:
            pass
        return None


def caps() -> Dict[str, Any]:
    """The measured caps. D1 writes this; the defaults are the work order's."""
    data = _read(CAPS, {})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("cloud_workers", 4)
    data.setdefault("local_heavy", 1)
    data.setdefault("source", "default (D1 has not measured a lower ceiling)")
    return data


def tokens_today() -> int:
    data = _read(TOKENS, {})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        return int((data.get(day) or {}).get("tokens") or 0)
    except (TypeError, ValueError):
        return 0


def add_tokens(count: int) -> None:
    data = _read(TOKENS, {})
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = data.setdefault(day, {"tokens": 0, "turns": 0})
    entry["tokens"] = int(entry.get("tokens") or 0) + max(0, int(count))
    entry["turns"] = int(entry.get("turns") or 0) + 1
    _write(TOKENS, data)


def _processes() -> List[Dict[str, Any]]:
    """Every python/opencode process with its command line. Read-only."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,"
             "Name,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30)
        data = json.loads(out.stdout or "[]")
        return data if isinstance(data, list) else [data]
    except (OSError, ValueError, subprocess.SubprocessError):
        return []


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:  # noqa: BLE001 - unknown means "do not assume alive"
        return False


def find_director() -> Optional[Dict[str, Any]]:
    """The one live director session.

    The pid file is authoritative. Scanning for a command-line marker alone produced
    a false positive on the first live test: the operator's own shell contained the
    marker text because it had set it as an environment variable, so the launcher
    decided a director was already running and never started one. The scan is kept
    only as a fallback for a lost pid file, and it requires a plausible process name.
    """
    record = _read(PID_FILE, {})
    pid = int(record.get("pid") or 0)
    if pid and _pid_alive(pid):
        return {"ProcessId": pid, "CommandLine": " ".join(str(p) for p in
                                                          (record.get("cmd") or []))}
    marker = DIRECTOR_MARKER
    if not marker:
        return None
    for row in _processes():
        cmd = str(row.get("CommandLine") or "")
        name = str(row.get("Name") or "").lower()
        if marker in cmd and name in ("opencode.exe", "python.exe", "python", "python3.exe"):
            return row
    return None


def count_workers() -> int:
    total = 0
    for row in _processes():
        cmd = str(row.get("CommandLine") or "")
        if "opencode" in cmd.lower() and "--agent builder" in cmd:
            total += 1
    return total


def disk_free_gb() -> Optional[float]:
    try:
        return round(shutil.disk_usage(str(ROOT)).free / 1024 ** 3, 2)
    except OSError:
        return None


def ram_status(*, record: bool = False, who: str = "ty_director") -> Dict[str, Any]:
    """The free-RAM governor's verdict. Never raises: a probe must not stop the loop.

    ``record`` journals the decision; heartbeats pass False because an observation is
    not a start decision and would otherwise write a line every interval.
    """
    try:
        for base in (ROOT, Path(__file__).resolve().parents[1]):
            tools_dir = str(base / "tools")
            if tools_dir not in sys.path:
                sys.path.insert(0, tools_dir)
        import ram_governor  # noqa: PLC0415 - local tool, loaded on demand

        return ram_governor.status(who=who, record=record)
    except Exception as exc:  # noqa: BLE001 - an unavailable probe must not stall starts
        return {"error": f"{type(exc).__name__}: {exc}", "paused": False,
                "free_gb": None, "max_builders": None,
                "reason": "ram governor unavailable; start allowed"}


def queue_depth() -> Dict[str, Any]:
    data = _read(QUEUE, {})
    units = data.get("units") or {}
    pending = [name for name, row in units.items()
               if isinstance(row, dict) and row.get("status") == "pending"]
    return {"units_pending": len(pending), "next": pending[0] if pending else None,
            "jobs": len(data.get("jobs") or []),
            "cycle": data.get("cycle")}


def _stream_path() -> Path:
    return LOG.parent / "ty_director_stream.jsonl"


def _error_text(node: Any) -> Optional[str]:
    """The readable message out of an opencode error part, whatever shape it arrived in."""
    seen = 0
    while isinstance(node, dict) and seen < 4:
        for key in ("message", "data", "error", "name"):
            if key not in node:
                continue
            value = node[key]
            if isinstance(value, str) and value.strip():
                if key == "name" and isinstance(node.get("data"), dict):
                    continue
                return value.strip()[:300]
            if isinstance(value, dict):
                node = value
                break
        else:
            break
        seen += 1
    return None


def stream_health(tail_bytes: int = 65536) -> Dict[str, Any]:
    """The last thing the lane said. An error line is a red heartbeat, not a short turn.

    D-010: `opencode run --agent director` failed 73 times in a row with
    ``Agent not found: "director"`` and nothing read the stream, so the scheduled task
    reported ``Running`` and the heartbeat said ``ram_paused`` for a day while no
    director lane existed at all. This is a file read: it spends no tokens.
    """
    path = _stream_path()
    try:
        size = path.stat().st_size
    except OSError:
        return {"last_type": None, "error": None, "bytes": 0, "lines": 0}
    try:
        with path.open("rb") as handle:
            if size > tail_bytes:
                handle.seek(size - tail_bytes)
            chunk = handle.read().decode("utf-8", errors="replace")
    except OSError as exc:  # noqa: BLE001 - a probe must not stop the loop
        return {"last_type": None, "error": f"{type(exc).__name__}: {exc}", "bytes": size,
                "lines": 0}
    lines = [line for line in chunk.splitlines() if line.strip()]
    last_type: Optional[str] = None
    last_error: Optional[str] = None
    for line in reversed(lines):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        last_type = str(row.get("type") or "") or None
        if last_type == "error":
            blob = row.get("error") or row.get("part") or row
            last_error = (_error_text(blob) if isinstance(blob, (dict, str))
                          else None) or json.dumps(blob, ensure_ascii=False)[:300]
        break
    return {"last_type": last_type, "error": last_error, "bytes": size,
            "lines": len(lines)}


def death_note(record: Dict[str, Any]) -> str:
    """Why the last session ended, in the launcher's own words.

    A lane that cannot start is not a short productive turn. Reading the stream is the
    difference between "the session ended" (true, uninformative, looked healthy for a
    day) and "the session died on a lane error: Agent not found: director".
    """
    health = stream_health()
    pid = record.get("pid")
    if health.get("last_type") == "error":
        return f"session {pid} died on a lane error: {health.get('error')}"
    if _stream_size() > int(record.get("stream_bytes") or 0):
        return f"session {pid} ended after output; launcher restarting"
    return f"session {pid} gone; launcher restarting"


def heartbeat(state: str, **extra: Any) -> Dict[str, Any]:
    stream = stream_health()
    red = bool(state == "error" or stream.get("last_type") == "error")
    payload = {
        "at": _now(), "state": state, "pid": os.getpid(), "red": red,
        "tokens_today": tokens_today(), "token_cap": TOKEN_CAP,
        "cap_reached": tokens_today() >= TOKEN_CAP * CAP_FRACTION,
        "cloud_workers": count_workers(), "caps": caps(),
        "disk_free_gb": disk_free_gb(), "queue": queue_depth(),
        "ram": ram_status(who="ty_director:heartbeat"),
        "gpu_lock": _read(GPU_LOCK, {}), "pause": PAUSE.exists(), "stop": STOP.exists(),
        "replan": replan_signal(), "stream": stream,
        **extra,
    }
    _write(HEARTBEAT, payload)
    return payload


def crash_note(reason: str) -> None:
    """One line, appended, so the next session knows why it is here."""
    try:
        with HANDOFF.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- {_now()} launcher: director session ended ({reason}).\n")
    except OSError:
        pass


def start_director() -> Optional[int]:
    cmd: List[str]
    if DIRECTOR_CMD:
        try:
            cmd = [str(part) for part in json.loads(DIRECTOR_CMD)]
        except ValueError:
            log("TY_DIRECTOR_CMD is not a JSON argv list; falling back to opencode")
            cmd = []
    else:
        cmd = []
    if not cmd:
        exe = shutil.which("opencode") or os.environ.get("TY_OPENCODE_EXE", "")
        if not exe:
            log("cannot start director: opencode not found")
            return None
        lane = os.environ.get("TY_DIRECTOR_AGENT", "director")
        cmd = [exe, "run", "--agent", lane, "--format", "json", "--auto"]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stream = _stream_path()
    handle = stream.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(cmd, cwd=str(ROOT), stdin=subprocess.PIPE,
                                stdout=handle, stderr=subprocess.STDOUT, text=True)
        # Every start carries the resume line: that is what makes a restart a
        # resumption rather than a fresh, context-free agent.
        proc.stdin.write(RESUME + "\n")
        proc.stdin.close()
    except OSError as exc:
        handle.close()
        log(f"cannot start director: {exc}")
        return None
    _write(PID_FILE, {"pid": proc.pid, "started_at": _now(), "cmd": cmd,
                      "stream_bytes": _stream_size()})
    log(f"started director pid={proc.pid}")
    return proc.pid


def _stream_size() -> int:
    path = _stream_path()
    try:
        return path.stat().st_size
    except OSError:
        return 0


def replan_signal() -> Dict[str, Any]:
    """Would an empty queue be idle, or a re-plan?

    The launcher does not re-plan (that is the Director's judgement); it decides
    whether the next session must be *told* to. An empty queue while services are
    below the bar is the defect the work order names, so the note goes in the handoff
    the next session reads.
    """
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import director_gaps as gaps  # noqa: PLC0415

        open_rows = gaps.open_jobs()
        if open_rows:
            return {"needed": False, "open_jobs": len(open_rows)}
        ranked = gaps.rank()
        if not ranked:
            return {"needed": False, "reason": "no_gaps"}
        return {"needed": True, "gaps": len(ranked),
                "top": ranked[0]["id"], "top_gap": ranked[0]["gap"]}
    except Exception as exc:  # noqa: BLE001 - a signal must never stop the launcher
        return {"needed": False, "error": f"{type(exc).__name__}: {exc}"}


def _note_replan(signal: Dict[str, Any]) -> None:
    if not signal.get("needed"):
        return
    try:
        with HANDOFF.open("a", encoding="utf-8") as handle:
            handle.write(f"\n- {_now()} queue empty while {signal.get('gaps')} service(s) "
                         f"are below the bar (worst: {signal.get('top')}); re-plan, do "
                         "not idle.\n")
    except OSError:
        pass


def blocked() -> Optional[str]:
    if PAUSE.exists():
        return "PAUSE file present"
    if STOP.exists():
        return "STOP file present"
    if tokens_today() >= TOKEN_CAP * CAP_FRACTION:
        return "token cap reached"
    return None


def tick(start: bool = False) -> Dict[str, Any]:
    """One heartbeat: read state, and only start a session when ``start`` is set.

    ``--once`` passes ``start=False``, which is what makes D2's acceptance testable:
    a heartbeat that never starts anything cannot have made a model call.
    """
    reason = blocked()
    if reason:
        return heartbeat("blocked", reason=reason)
    live = find_director()
    if live:
        return heartbeat("running", director_pid=live.get("ProcessId"))
    if not start:
        return heartbeat("idle", reason="no director session (not started by --once)")
    ram = ram_status(record=True, who="ty_director:start")
    if ram.get("paused"):
        log(f"ram gate: paused, free RAM {ram.get('free_gb')} GB "
            "(max_builders=0); not starting a session")
        return heartbeat("ram_paused", reason=ram.get("reason"), ram=ram)
    started = start_director()
    if started is None:
        return heartbeat("error", reason="opencode_not_found")
    return heartbeat("starting", director_pid=started)


def status() -> int:
    live = find_director()
    stream = stream_health()
    payload = {
        "director": live.get("ProcessId") if live else None,
        "workers": count_workers(), "caps": caps(),
        "tokens_today": tokens_today(), "cap_reached": tokens_today() >= TOKEN_CAP * CAP_FRACTION,
        "disk_free_gb": disk_free_gb(), "queue": queue_depth(),
        "pause": PAUSE.exists(), "stop": STOP.exists(),
        "ram": ram_status(who="ty_director:status"),
        "stream": stream, "red": stream.get("last_type") == "error",
        "heartbeat": _read(HEARTBEAT, {}),
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ty Director launcher")
    parser.add_argument("--once", action="store_true", help="one heartbeat tick")
    parser.add_argument("--status", action="store_true", help="read-only status")
    parser.add_argument("--interval", type=int, default=HEARTBEAT_S)
    parser.add_argument("--max-ticks", type=int, default=0,
                        help="stop after this many heartbeat ticks (0 = forever)")
    ns = parser.parse_args(argv)

    if ns.status:
        return status()
    if ns.once:
        print(json.dumps(tick(start=False), indent=2))
        return 0

    log(f"launcher starting (heartbeat={ns.interval}s cap={TOKEN_CAP})")
    run_reboot_check_once()
    last_start = 0.0
    noted_dead = False
    ticks = 0
    while True:
        if ns.max_ticks and ticks >= ns.max_ticks:
            heartbeat("stopped", reason="max_ticks")
            log(f"stopping after {ticks} tick(s)")
            return 0
        ticks += 1
        reason = blocked()
        if reason in ("PAUSE file present", "STOP file present"):
            heartbeat("stopped", reason=reason)
            log(f"stopping: {reason}")
            return 0
        if reason:
            heartbeat("blocked", reason=reason)
            time.sleep(ns.interval)
            continue
        live = find_director()
        if live:
            heartbeat("running", director_pid=live.get("ProcessId"))
            noted_dead = False
        else:
            # The RAM gate is consulted only here - after "no session is running" -
            # so a paused governor can never stop a session that is already alive.
            ram = ram_status(record=True, who="ty_director:loop")
            if ram.get("paused"):
                heartbeat("ram_paused", reason=ram.get("reason"), ram=ram)
                log(f"ram gate: paused, free RAM {ram.get('free_gb')} GB "
                    "(max_builders=0); not starting a session")
                time.sleep(ns.interval)
                continue
            now = time.time()
            record = _read(PID_FILE, {})
            if not noted_dead:
                if record.get("pid"):
                    reason_text = death_note(record)
                    crash_note(reason_text)
                    if stream_health().get("last_type") == "error":
                        log(f"lane error: {stream_health().get('error')}")
                noted_dead = True
            # A crash is a short life **with no output**. A turn that did anything at
            # all wrote to the stream, and a short productive turn must not be
            # punished with a five-minute backoff - that would throttle the loop for
            # being efficient. The old rule (time alone) backed off for ever because
            # it never cleared last_start.
            grew = _stream_size() > int(record.get("stream_bytes") or 0)
            fast = bool(last_start) and (now - last_start) < FAST_EXIT_S and not grew
            if fast:
                heartbeat("backoff", reason="fast_exit_no_output", seconds=BACKOFF_S)
                log(f"director died in {int(now - last_start)}s with no output; "
                    f"backing off {BACKOFF_S}s")
                time.sleep(BACKOFF_S)
                last_start = 0.0
                continue
            started = start_director()
            if started:
                last_start = time.time()
                noted_dead = False
                _note_replan(replan_signal())
        time.sleep(ns.interval)


if __name__ == "__main__":
    raise SystemExit(main())
