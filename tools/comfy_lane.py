"""A render lane owns ComfyUI for its lifetime: start fresh, work, stop, prove it stopped.

Folded fix (WORK ORDER 3 item 3): *ComfyUI starts fresh per render lane and stops after;
stop trusting `free_comfy()`.* The reason is measured: this build answers `/free` with 200
and releases nothing, so an acknowledgement is not a release. A process that exits is.

    from comfy_lane import lane
    result = lane(lambda: render(prompt), vram=free_gb)

    python tools/comfy_lane.py --status
    python tools/comfy_lane.py --stop
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
COMFY_HOME = Path(os.environ.get("COMFY_HOME", r"C:\Users\T2Hol\ComfyUI"))
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
EVIDENCE = ROOT / "state" / "gpu" / "comfy_lanes.jsonl"


def reachable(url: str = COMFY_URL, *, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/system_stats", timeout=timeout):
            return True
    except Exception:  # noqa: BLE001 - unreachable is the normal state between lanes
        return False


def port_open(host: str = "127.0.0.1", port: int = 8188, *, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _log(row: Dict[str, Any]) -> None:
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), **row}) + "\n")


def _start() -> Dict[str, Any]:
    """Start ComfyUI detached, with a cold cache, and return the exact pid it got."""
    python = COMFY_HOME / "venv" / "Scripts" / "python.exe"
    main = COMFY_HOME / "main.py"
    if not python.exists() or not main.exists():
        return {"ok": False, "reason": f"ComfyUI not found under {COMFY_HOME}"}
    creation = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        proc = subprocess.Popen(
            [str(python), str(main), "--listen", "127.0.0.1", "--port", "8188",
             "--cache-none"],
            cwd=str(COMFY_HOME), creationflags=creation,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "pid": proc.pid, "process": proc}


def _wait_ready(*, timeout: float = 180.0) -> Dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if reachable():
            return {"ok": True, "seconds": round(timeout - (deadline - time.time()), 1)}
        time.sleep(1.0)
    return {"ok": False, "reason": f"ComfyUI did not answer within {timeout}s"}


def _stop(pid: Optional[int], *, timeout: float = 30.0) -> Dict[str, Any]:
    """Terminate the lane's process and wait for the port to close. Verification, not hope."""
    if not pid:
        return {"ok": False, "reason": "no pid to stop"}
    try:
        subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", "/F"],
                       capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "pid": pid}
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_open():
            return {"ok": True, "pid": pid, "stopped": True,
                    "seconds": round(timeout - (deadline - time.time()), 1)}
        time.sleep(0.5)
    return {"ok": False, "pid": pid, "reason": "port 8188 still open after taskkill"}


def lane(work: Callable[[], Any], *, start: Callable[[], Dict[str, Any]] = _start,
         ready: Callable[[], Dict[str, Any]] = _wait_ready,
         stop: Callable[[Optional[int]], Dict[str, Any]] = _stop,
         vram: Optional[Callable[[], float]] = None,
         timeout: float = 180.0) -> Dict[str, Any]:
    """Start, work, stop. The stop happens in a `finally`, exactly once."""
    if reachable():
        _log({"event": "refused", "reason": "already_running"})
        return {"ok": False, "refused": True,
                "reason": ("ComfyUI is already running; a lane starts its own instance so "
                           "it can prove it stopped the one it used")}
    before = float(vram() or 0.0) if vram else None
    started = start()
    if not started.get("ok"):
        _log({"event": "start_failed", **started})
        return {"ok": False, "reason": started.get("reason")}
    pid = started.get("pid")
    outcome: Dict[str, Any] = {"ok": False}
    try:
        ready_result = ready()
        if not ready_result.get("ok"):
            outcome = {"ok": False, "reason": ready_result.get("reason")}
            return outcome
        outcome = {"ok": True, "result": work()}
        return outcome
    finally:
        stopped = stop(pid)
        after = float(vram() or 0.0) if vram else None
        freed = None if (before is None or after is None) else round(after - before, 2)
        row = {"event": "lane", "pid": pid, "stopped": stopped,
               "vram_before_gb": before, "vram_after_gb": after, "vram_freed_gb": freed,
               "work_ok": bool(outcome.get("ok"))}
        _log(row)
        outcome["lane"] = row


def status() -> Dict[str, Any]:
    return {"url": COMFY_URL, "reachable": reachable(), "port_open": port_open(),
            "home": str(COMFY_HOME)}


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="ComfyUI render lane")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--pid", type=int, default=0)
    ns = parser.parse_args(argv)

    if ns.stop:
        result = _stop(ns.pid or None)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1
    print(json.dumps(status(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
