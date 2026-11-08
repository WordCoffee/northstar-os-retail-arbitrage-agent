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

TOKEN_CAP = int(os.environ.get("TY_TOKEN_CAP_PER_DAY", "3000000"))
CAP_FRACTION = 0.90
HEARTBEAT_S = int(os.environ.get("TY_HEARTBEAT_S", "300"))
FAST_EXIT_S = 90
BACKOFF_S = int(os.environ.get("TY_DIRECTOR_BACKOFF_S", "300"))

RESUME = (
    "Hi, I'd like to give a work order to Ty. Resume the director program. Read "
    "reports/ty/director_work_order.md, ty/MANDATE.md, reports/ty/director_queue.json, "
    "and reports/ty/handoff.md, then continue from the first unfinished unit. "
    "No questions, no reports between cycles. Idle means re-plan."
)


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


def find_director() -> Optional[Dict[str, Any]]:
    """The one live director session, matched by command line."""
    for row in _processes():
        cmd = str(row.get("CommandLine") or "")
        if "opencode" in cmd.lower() and "--agent director" in cmd:
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


def queue_depth() -> Dict[str, Any]:
    data = _read(QUEUE, {})
    units = data.get("units") or {}
    pending = [name for name, row in units.items()
               if isinstance(row, dict) and row.get("status") == "pending"]
    return {"units_pending": len(pending), "next": pending[0] if pending else None,
            "jobs": len(data.get("jobs") or []),
            "cycle": data.get("cycle")}


def heartbeat(state: str, **extra: Any) -> Dict[str, Any]:
    payload = {
        "at": _now(), "state": state, "pid": os.getpid(),
        "tokens_today": tokens_today(), "token_cap": TOKEN_CAP,
        "cap_reached": tokens_today() >= TOKEN_CAP * CAP_FRACTION,
        "cloud_workers": count_workers(), "caps": caps(),
        "disk_free_gb": disk_free_gb(), "queue": queue_depth(),
        "gpu_lock": _read(GPU_LOCK, {}), "pause": PAUSE.exists(), "stop": STOP.exists(),
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
    exe = shutil.which("opencode") or os.environ.get("TY_OPENCODE_EXE", "")
    if not exe:
        log("cannot start director: opencode not found")
        return None
    lane = os.environ.get("TY_DIRECTOR_AGENT", "director")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    stream = LOG.parent / "ty_director_stream.jsonl"
    handle = stream.open("a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [exe, "run", "--agent", lane, "--format", "json", "--auto"],
            cwd=str(ROOT), stdin=subprocess.PIPE, stdout=handle,
            stderr=subprocess.STDOUT, text=True)
        proc.stdin.write(RESUME + "\n")
        proc.stdin.close()
    except OSError as exc:
        handle.close()
        log(f"cannot start director: {exc}")
        return None
    _write(PID_FILE, {"pid": proc.pid, "started_at": _now(), "lane": lane})
    log(f"started director pid={proc.pid}")
    return proc.pid


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
    started = start_director()
    if started is None:
        return heartbeat("error", reason="opencode_not_found")
    return heartbeat("starting", director_pid=started)


def status() -> int:
    live = find_director()
    payload = {
        "director": live.get("ProcessId") if live else None,
        "workers": count_workers(), "caps": caps(),
        "tokens_today": tokens_today(), "cap_reached": tokens_today() >= TOKEN_CAP * CAP_FRACTION,
        "disk_free_gb": disk_free_gb(), "queue": queue_depth(),
        "pause": PAUSE.exists(), "stop": STOP.exists(),
        "heartbeat": _read(HEARTBEAT, {}),
    }
    print(json.dumps(payload, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Ty Director launcher")
    parser.add_argument("--once", action="store_true", help="one heartbeat tick")
    parser.add_argument("--status", action="store_true", help="read-only status")
    parser.add_argument("--interval", type=int, default=HEARTBEAT_S)
    ns = parser.parse_args(argv)

    if ns.status:
        return status()
    if ns.once:
        print(json.dumps(tick(start=False), indent=2))
        return 0

    log(f"launcher starting (heartbeat={ns.interval}s cap={TOKEN_CAP})")
    last_start = 0.0
    noted_dead = False
    while True:
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
            now = time.time()
            if not noted_dead:
                record = _read(PID_FILE, {})
                if record.get("pid"):
                    crash_note(f"session {record.get('pid')} gone; launcher restarting")
                noted_dead = True
            if last_start and now - last_start < FAST_EXIT_S:
                heartbeat("backoff", reason="fast_exit", seconds=BACKOFF_S)
                log(f"director exited within {FAST_EXIT_S}s; backing off {BACKOFF_S}s")
                time.sleep(BACKOFF_S)
                continue
            started = start_director()
            if started:
                last_start = time.time()
                noted_dead = False
        time.sleep(ns.interval)


if __name__ == "__main__":
    raise SystemExit(main())
