"""Free-RAM governor: the gate every builder start goes through.

The box is 16 GB and the render lane refuses below 3 GB free. Builders have been
started at 0.5 GB free, and the resulting failures look like product bugs, so the
decision "may another builder start" is measured here instead of assumed.

Thresholds (free physical RAM):

    >= 2.0 GB   up to 4 builders
    <  2.0 GB   2 builders
    <  1.0 GB   0 new builders (paused); anything already running is left alone

Two readings are taken and cross-checked: `psutil.virtual_memory().available` and
`Win32_OperatingSystem.FreePhysicalMemory`. When they disagree by more than 20 % the
governor reports both and uses the **lower** - a governor that trusts the optimistic
number is not a governor.

`state/director/caps.json` may carry a measured `cloud_workers` concurrency ceiling.
When it does, the governor returns the minimum of its own number and that ceiling.

    python tools/ram_governor.py --status     # one look
    python tools/ram_governor.py --gate 3     # exit 0 if a 4th builder may start

Every decision is one JSON line in `state/director/ram_gate.jsonl`. No model, no
network, no process killing.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "director"
CAPS = STATE / "caps.json"
JOURNAL = STATE / "ram_gate.jsonl"

FULL_FREE_GB = 2.0
FLOOR_FREE_GB = 1.0
MAX_BUILDERS = 4
REDUCED_BUILDERS = 2
DISAGREE_FRACTION = 0.20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _psutil_free_gb() -> Optional[float]:
    """psutil's `available`, which is the number the rest of the stack uses."""
    try:
        import psutil  # noqa: PLC0415 - optional at import time, never fatal

        return round(psutil.virtual_memory().available / 1024 ** 3, 2)
    except Exception:  # noqa: BLE001 - a probe may fail; the other one may not
        return None


def _win32_free_gb() -> Optional[float]:
    """Windows' own FreePhysicalMemory, in KB, converted to GB."""
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
            capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    lines = [line.strip() for line in (out.stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    try:
        return round(int(lines[-1]) / 1024 ** 2, 2)
    except (TypeError, ValueError):
        return None


def measure() -> Dict[str, Optional[float]]:
    """Both readings, named, so a disagreement can be reported in full."""
    return {"psutil_gb": _psutil_free_gb(), "win32_gb": _win32_free_gb()}


def _choose(primary: Optional[float],
            secondary: Optional[float]) -> Dict[str, Any]:
    """Which reading the decision uses, and whether the two disagreed."""
    if primary is None and secondary is None:
        return {"free_gb": None, "disagreement": False, "disagreement_pct": None}
    if primary is None:
        return {"free_gb": secondary, "disagreement": False,
                "disagreement_pct": None}
    if secondary is None:
        return {"free_gb": primary, "disagreement": False,
                "disagreement_pct": None}
    spread = abs(primary - secondary) / max(primary, secondary, 1e-9)
    pct = round(spread * 100, 1)
    # The lower reading always wins, not only when the two disagree wildly. A governor that
    # averages, or that trusts the optimistic number while the pair is "close", is choosing to
    # believe the reading that lets more work start — which is exactly the failure it exists to
    # prevent. The disagreement is still reported, because a 13 % spread is itself information.
    return {"free_gb": min(primary, secondary), "disagreement": spread > DISAGREE_FRACTION,
            "disagreement_pct": pct}


def _cloud_worker_cap() -> Optional[int]:
    """A measured concurrency ceiling, only when caps.json actually states one."""
    try:
        data = json.loads(CAPS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("cloud_workers") is None:
        return None
    try:
        return max(0, int(data["cloud_workers"]))
    except (TypeError, ValueError):
        return None


def decide(reading: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The whole policy in one pure function, so tests need no real machine."""
    measured = reading if reading is not None else measure()
    primary = measured.get("psutil_gb")
    secondary = measured.get("win32_gb")
    chosen = _choose(primary, secondary)
    free = chosen["free_gb"]

    if free is None:
        max_builders, paused = 0, True
        reason = "free RAM unreadable from both probes: 0 new builders (paused)"
    elif free < FLOOR_FREE_GB:
        max_builders, paused = 0, True
        reason = (f"free RAM {free:.2f} GB < 1.0 GB floor: "
                  "0 new builders (paused)")
    elif free < FULL_FREE_GB:
        max_builders, paused = REDUCED_BUILDERS, False
        reason = (f"free RAM {free:.2f} GB < 2.0 GB: {REDUCED_BUILDERS} builders")
    else:
        max_builders, paused = MAX_BUILDERS, False
        reason = (f"free RAM {free:.2f} GB >= 2.0 GB: up to {MAX_BUILDERS} builders")

    if chosen["disagreement"]:
        reason += (f"; probes disagreed by {chosen['disagreement_pct']}% "
                   f"(psutil {primary:.2f} GB vs Win32 {secondary:.2f} GB), "
                   f"using the lower {free:.2f} GB")

    cap = _cloud_worker_cap()
    if cap is not None and cap < max_builders:
        max_builders = cap
        paused = max_builders <= 0
        reason += f"; capped at {cap} by state/director/caps.json cloud_workers"
        if paused:
            reason += " (paused)"

    return {
        "at": _now(),
        "free_gb": free,
        "max_builders": max_builders,
        "paused": paused,
        "reason": reason,
        "readings": {"psutil_gb": primary, "win32_gb": secondary},
        "disagreement": chosen["disagreement"],
        "disagreement_pct": chosen["disagreement_pct"],
    }


def _journal(record: Dict[str, Any]) -> None:
    """One line per decision. A journal that cannot be written never blocks."""
    try:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass


def status(*, who: str = "cli", record: bool = True,
           reading: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The governor's current verdict, optionally journaled as one line."""
    decision = decide(reading)
    decision["who"] = who
    decision["event"] = "status"
    if record:
        _journal(decision)
    return decision


def gate(running: int, *, who: str = "dispatch", record: bool = True,
         reading: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """May one new builder start while ``running`` are already running?"""
    try:
        active = max(0, int(running))
    except (TypeError, ValueError):
        active = 0
    decision = decide(reading)
    decision["allowed"] = (not decision["paused"]
                           and active < int(decision["max_builders"]))
    decision["running"] = active
    decision["who"] = who
    decision["event"] = "gate"
    if record:
        _journal(decision)
    return decision


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Free-RAM builder governor")
    parser.add_argument("--status", action="store_true", help="one look")
    parser.add_argument("--gate", type=int, default=None, metavar="N",
                        help="exit 0 if a new builder may start when N are running")
    parser.add_argument("--who", default="cli", help="who is asking (journaled)")
    parser.add_argument("--no-record", action="store_true",
                        help="do not append to state/director/ram_gate.jsonl")
    ns = parser.parse_args(argv)
    record = not ns.no_record

    if ns.status:
        print(json.dumps(status(who=ns.who, record=record), indent=2))
        return 0
    if ns.gate is not None:
        result = gate(ns.gate, who=ns.who, record=record)
        print(json.dumps(result, indent=2))
        return 0 if result["allowed"] else 1
    parser.error("one of --status or --gate N is required")


if __name__ == "__main__":
    raise SystemExit(main())
