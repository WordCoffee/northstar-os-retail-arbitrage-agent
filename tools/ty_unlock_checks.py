"""The checks that need an unlocked desktop, in one command.

Three things can only run with a real, signed-in session in front of the machine:

* the **live vision walk** over every advanced-view route (Ty's Vision, a fresh tab per route);
* **V3**, the ten-task parity suite twice;
* **V9**, the dogfood pass over the improved services.

Each one refuses by name when the desktop is locked, which is correct but tedious to retry by
hand. This runs them in order, stops at the first one that cannot run honestly, and writes what
it found to `reports/ty/unlock_checks_<date>.json`.

    python tools/ty_unlock_checks.py            # run what the session allows
    python tools/ty_unlock_checks.py --status   # just say whether it is possible
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ty"


def session_state() -> Dict[str, Any]:
    """Is there a usable desktop? A locked or absent one is named, not assumed."""
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    if not handle:
        return {"locked": True, "reason": "no foreground window (locked or no interactive desktop)"}
    length = user32.GetWindowTextLengthW(handle)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(handle, buffer, length + 1)
    title = buffer.value
    if "lock screen" in title.casefold() or title.strip() == "":
        return {"locked": True, "reason": f"foreground is {title!r}"}
    return {"locked": False, "reason": "", "foreground": title}


def _run(name: str, argv: List[str], timeout: int = 3600) -> Dict[str, Any]:
    started = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                             timeout=timeout)
    tail = ((started.stdout or "") + (started.stderr or "")).strip().splitlines()[-12:]
    return {"step": name, "argv": argv, "exit": started.returncode,
            "ok": started.returncode == 0, "tail": tail}


def run(*, skip_dogfood: bool = False) -> Dict[str, Any]:
    state = session_state()
    if state["locked"]:
        return {"ok": False, "blocked": True, **state, "steps": []}

    steps: List[Dict[str, Any]] = []
    walk = _run("live walk", [sys.executable, "-m", "tools.registry.vision_walk",
                              "--out", "state/registry/vision_live.json"])
    steps.append(walk)
    if walk["ok"]:
        steps.append(_run("apply vision", [sys.executable, "-m", "tools.registry.apply_vision",
                                           "--vision", "state/registry/vision_live.json"]))
        steps.append(_run("build", [sys.executable, "-m", "tools.registry.build"]))
    steps.append(_run("V3 parity", [sys.executable, "-m", "tools.vision.parity", "--twice",
                                    "--base", "http://127.0.0.1:8101/ui/",
                                    "--backends", "uia,chromeconnect"]))
    if not skip_dogfood:
        steps.append(_run("V9 dogfood", [sys.executable, "-m", "tools.vision.dogfood",
                                         "--services",
                                         "design-studio,listings,socialpulse,competitor-monitor"]))

    payload = {"ok": all(step["ok"] for step in steps), "blocked": False, "steps": steps,
               "session": state}
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / f"unlock_checks_{date.today().isoformat()}.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Checks that need an unlocked desktop")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--skip-dogfood", action="store_true")
    ns = parser.parse_args(argv)
    if ns.status:
        print(json.dumps(session_state(), indent=2))
        return 0
    payload = run(skip_dogfood=ns.skip_dogfood)
    print(json.dumps({"ok": payload["ok"], "blocked": payload["blocked"],
                      "reason": payload.get("reason"),
                      "steps": [{k: step.get(k) for k in ("step", "ok", "exit")}
                                for step in payload["steps"]]}, indent=2))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
