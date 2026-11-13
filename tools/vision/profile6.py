"""One dedicated Chrome window for vision work, and nothing else.

The 2026-11-11 incident was not a wrong URL — it was a keystroke that landed in a Chrome window
nobody had chosen (Profile 1, then Profile 4). The fix is structural: vision work gets its **own**
window, launched with the quoted profile argument, its HWND is recorded, and keys are refused
unless the foreground HWND is that exact window.

    Chrome:  --profile-directory="Profile 6"      (quoted, as the owner's rule requires)
    record:  state/vision/profile6_window.json    {hwnd, pid, launched_at, argv}
    refusal: "not the recorded Profile 6 window (hwnd 111, this window 222)"

The record is what a decoy window cannot forge: a different Chrome window is a different HWND, and
the guard compares the number, not the title.

    python -m tools.vision.profile6 --status
    python -m tools.vision.profile6 --launch http://127.0.0.1:8101/ui/   (only without PAUSE)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "state" / "vision" / "profile6_window.json"
PAUSE = ROOT / "state" / "vision" / "PAUSE"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE = "Profile 6"
#: The argument exactly as the owner's rule states it: the profile name is quoted.
PROFILE_ARG = f'--profile-directory="{PROFILE}"'


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def recorded() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("hwnd") else None


def record_window(hwnd: int, pid: int, argv: list[str]) -> Dict[str, Any]:
    payload = {"profile": PROFILE, "profile_arg": PROFILE_ARG, "hwnd": int(hwnd),
               "pid": int(pid), "launched_at": _now(), "argv": argv,
               "note": "the only window Ty's Vision may type into"}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def _chrome_windows() -> list[dict]:
    try:
        sys.path.insert(0, str(ROOT))
        from tools.vision.capture import windows  # noqa: PLC0415

        return [w for w in windows() if "chrome" in str(w.get("process") or "").lower()]
    except Exception:  # noqa: BLE001 - a probe must not raise
        return []


def launch(url: str = "http://127.0.0.1:8101/ui/", *, timeout_s: int = 25) -> Dict[str, Any]:
    """Launch the dedicated window and record it. Refuses while PAUSE exists."""
    if PAUSE.exists():
        return {"ok": False, "refused": True,
                "reason": "state/vision/PAUSE is present: not launching a browser window"}
    if not CHROME.is_file():
        return {"ok": False, "reason": f"chrome not found at {CHROME}"}

    argv = [str(CHROME), PROFILE_ARG, url]
    before = {int(w["hwnd"]) for w in _chrome_windows() if w.get("hwnd")}
    try:
        process = subprocess.Popen(argv)  # no window title is read or stored
    except OSError as exc:
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}"}

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for window in _chrome_windows():
            hwnd = int(window.get("hwnd") or 0)
            if hwnd and hwnd not in before:
                record = record_window(hwnd, process.pid, argv)
                return {"ok": True, **record}
        time.sleep(0.5)
    return {"ok": False, "reason": "no new Chrome window appeared; nothing recorded",
            "pid": process.pid}


def check_foreground(window_hwnd: int, foreground: Optional[int] = None) -> tuple[bool, str]:
    """May keys go to `window_hwnd`? Both numbers must be the recorded one."""
    if foreground is None:
        try:
            from tools.vision.chrome_uia import foreground_hwnd  # noqa: PLC0415

            foreground = foreground_hwnd()
        except Exception as exc:  # noqa: BLE001
            return False, f"foreground unreadable: {type(exc).__name__}"
    record = recorded()
    if not record:
        return False, "no Profile 6 window has been recorded; launch one first"
    if int(window_hwnd) != int(record["hwnd"]):
        return False, (f"not the recorded Profile 6 window (recorded {record['hwnd']}, "
                       f"this window {window_hwnd})")
    if int(foreground) != int(record["hwnd"]):
        return False, (f"foreground is not the Profile 6 window (recorded {record['hwnd']}, "
                       f"foreground {foreground})")
    return True, ""


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Dedicated Profile 6 window for vision work")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--launch", nargs="?", const="http://127.0.0.1:8101/ui/", default="")
    ns = parser.parse_args(argv)
    if ns.launch:
        print(json.dumps(launch(ns.launch), indent=2))
        return 0
    record = recorded()
    print(json.dumps({"pause": PAUSE.exists(), "recorded": record,
                      "profile_arg": PROFILE_ARG}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
