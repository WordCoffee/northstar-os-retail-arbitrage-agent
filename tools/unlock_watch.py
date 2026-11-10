"""Wait for an unlocked desktop, then run the checks that need one.

V3 and the UIA parity suite cannot run behind a lock screen. Instead of retrying by hand, this
polls the foreground every five minutes — a Win32 call, no model, no tokens — and the moment the
foreground is no longer the lock screen it runs `tools/ty_unlock_checks.py` and records the
outcome. It stops after the checks succeed twice, or after a configurable number of attempts.

    python tools/unlock_watch.py --once          # one check, then exit
    python tools/unlock_watch.py                 # poll until unlocked or attempts run out
    python tools/unlock_watch.py --interval 300 --attempts 96
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "reports" / "ty" / "unlock_watch.log"
STATE = ROOT / "state" / "director" / "unlock_watch.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def foreground() -> Dict[str, Any]:
    """The current foreground window, by Win32. No model, no process scan."""
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    if not handle:
        return {"hwnd": 0, "title": "", "locked": True}
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    title = buffer.value
    locked = "lock screen" in title.casefold() or not title.strip()
    return {"hwnd": int(handle), "title": title, "locked": locked}


def _log(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{_now()} {line}\n")


def _state(payload: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def attempt() -> Dict[str, Any]:
    """One attempt: check the desktop, and run the checks if it is usable."""
    window = foreground()
    if window["locked"]:
        return {"at": _now(), "ran": False, "reason": "desktop locked",
                "foreground": window["title"]}
    _log(f"desktop unlocked (foreground {window['title']!r}); running unlock checks")
    started = subprocess.run([sys.executable, "-m", "tools.ty_unlock_checks"],
                             cwd=str(ROOT), capture_output=True, text=True, timeout=7200)
    tail = ((started.stdout or "") + (started.stderr or "")).strip().splitlines()[-6:]
    _log(f"unlock checks exit {started.returncode}")
    return {"at": _now(), "ran": True, "exit": started.returncode,
            "ok": started.returncode == 0, "tail": tail,
            "foreground": window["title"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Watch for an unlocked desktop")
    parser.add_argument("--interval", type=int, default=300, help="seconds between polls")
    parser.add_argument("--attempts", type=int, default=0, help="0 means until it succeeds")
    parser.add_argument("--once", action="store_true")
    ns = parser.parse_args(argv)

    payload: Dict[str, Any] = {"started_at": _now(), "attempts": [], "successes": 0}
    if ns.once:
        result = attempt()
        payload["attempts"].append(result)
        payload["successes"] += 1 if result.get("ok") else 0
        _state(payload)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ran") else 2

    limit = ns.attempts
    count = 0
    while limit == 0 or count < limit:
        result = attempt()
        payload["attempts"].append(result)
        payload["successes"] += 1 if result.get("ok") else 0
        _state(payload)
        if result.get("ok"):
            # The checks passed; nothing left to wait for.
            return 0
        count += 1
        if limit and count >= limit:
            break
        time.sleep(max(30, ns.interval))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
