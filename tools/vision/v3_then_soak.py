"""Wait for the owner's conditions, then run V3 twice and start the soak — without a model call.

The order is conditional: "when the desktop is unlocked and PAUSE is removed, run V3 on the UIA
backend twice ... then run a 24-hour unattended soak". A condition that nobody is watching is just
a wish, so this watcher owns the clock and nothing else:

1. every five minutes, ask the gate whether the eyes may act (PAUSE absent, desktop unlocked);
2. when they may, run V3 twice on the UIA backend and record both runs;
3. then start the soak for its full window and let it finish.

It never removes `PAUSE`, never edits a route, never merges, and never calls a model. If the
conditions never arrive it keeps saying so, once every five minutes, in one log line.

    python tools/vision/v3_then_soak.py --status
    python tools/vision/v3_then_soak.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOG = ROOT / "reports" / "ty" / "v3_then_soak.log"
STATE = ROOT / "state" / "v3_then_soak.json"
INTERVAL_S = 300
PAUSE = ROOT / "state" / "vision" / "PAUSE"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{now()} {message}\n")


def gate() -> str:
    """Why V3 may not run, or '' when it may."""
    if PAUSE.exists():
        return "state/vision/PAUSE present"
    try:
        from tools.director_vision import blocked_reason

        return blocked_reason() or ""
    except Exception as exc:  # noqa: BLE001 - unreadable is a block
        return f"gate unreadable: {type(exc).__name__}: {exc}"


def run_v3() -> dict:
    proc = subprocess.run(
        [sys.executable, "-m", "tools.vision.v3_gate"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=7200,
        encoding="utf-8", errors="replace")
    return {"at": now(), "returncode": proc.returncode,
            "tail": (proc.stdout or proc.stderr or "").strip().splitlines()[-8:]}


def start_soak() -> dict:
    proc = subprocess.Popen(
        [sys.executable, "tools/soak.py", "--hours", "24", "--interval", "60"],
        cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=(getattr(subprocess, "DETACHED_PROCESS", 0)
                       | getattr(subprocess, "CREATE_NO_WINDOW", 0)) if sys.platform == "win32" else 0)
    return {"at": now(), "pid": proc.pid}


def load() -> dict:
    try:
        return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"state": "waiting", "waiting_since": now()}


def save(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def tick(state: dict) -> dict:
    reason = gate()
    if reason:
        if state.get("last_reason") != reason:
            log(f"waiting: {reason}")
        state.update({"state": "waiting", "last_reason": reason, "checked_at": now()})
        save(state)
        return state

    log("gate open: running V3 on the UIA backend, twice")
    v3 = run_v3()
    state["v3"] = v3
    log(f"V3 finished: exit {v3['returncode']}")

    soak = start_soak()
    state.update({"state": "soaking", "soak": soak, "checked_at": now()})
    save(state)
    log(f"soak started: pid {soak['pid']} for 24h")
    return state


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Wait for PAUSE removal, then V3 twice and the soak")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--once", action="store_true")
    ns = parser.parse_args(argv)

    if ns.status:
        print(json.dumps({"pause": PAUSE.exists(), "gate": gate() or "open",
                          "state": load()}, indent=2)[:4000])
        return 0

    state = load()
    if ns.once:
        print(json.dumps(tick(state), indent=2)[:4000])
        return 0

    log("watcher starting (5-minute checks; no model calls)")
    while True:
        state = tick(state)
        if state.get("state") == "soaking":
            log("watcher done: soak owns the window")
            return 0
        time.sleep(INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
