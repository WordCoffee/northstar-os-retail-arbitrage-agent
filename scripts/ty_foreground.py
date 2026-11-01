"""Foreground, resource-gated launcher for Ty campaigns.

The interactive coding session costs ~1.4 GB of a 15.4 GB host. This launcher is
the low-overhead path: it reuses the existing supervisor, registry, lock,
heartbeat, evidence and recovery, and adds the one thing a plain
`continuous_loop.py --max-tasks N` run does not do up front:

* resolve the execution profile the queue will actually use (model + context);
* refuse before LOADING a model when the host cannot hold it plus the 3 GB floor;
* run the full readiness gate (which measures residency for that exact profile);
* only then dispatch.

It installs nothing, starts no service, and runs in a visible terminal. A missing
model, a low-memory host or a NO-GO gate produces a refusal, never a silent run.

    python scripts/ty_foreground.py --check
    python scripts/ty_foreground.py --max-tasks 3 --deadline-minutes 120

Exit codes: 0 campaign ran (or check passed), 2 usage, 3 resource/profile refusal,
4 campaign ran but did not complete cleanly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import continuous_loop as cl  # noqa: E402


def preload_requirement(profiles: List[Dict[str, Any]]) -> float:
    return max([cl.MIN_PRELOAD_RAM_GB_BY_PROFILE.get(p["model"],
                                                     cl.MIN_PRELOAD_RAM_GB_DEFAULT)
                for p in profiles] or [cl.MIN_PRELOAD_RAM_GB_DEFAULT])


def check_resources(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    free = cl._free_ram_gb()
    need = preload_requirement(profiles)
    ok = free is not None and float(free) >= need
    return {"ok": bool(ok), "free_gb": free, "required_gb": need,
            "profiles": profiles,
            "reason": ("" if ok else
                       f"pre-load {free:.2f} GB < {need:.1f} GB required for "
                       f"{', '.join(p['model'] + ' ctx' + str(p.get('num_ctx') or 'default') for p in profiles)}"
                       if free is not None else "RAM probe unavailable")}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="run the resource and readiness gate, then exit without dispatching")
    ap.add_argument("--task", default="", help="one task id")
    ap.add_argument("--max-tasks", type=int, default=3)
    ap.add_argument("--deadline-minutes", type=float, default=120)
    ap.add_argument("--max-consecutive-failures", type=int, default=2)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    profiles = cl.queue_profiles()
    if not profiles:
        print(json.dumps({"ok": False, "reason": "no authorized ty task in the queue",
                          "profiles": []}, indent=2))
        return 3

    pre = check_resources(profiles)
    if not pre["ok"]:
        print(json.dumps({
            "ok": False, "stage": "preload", "reason": pre["reason"],
            "free_gb": pre["free_gb"], "required_gb": pre["required_gb"],
            "profiles": [{"model": p["model"], "num_ctx": p.get("num_ctx")}
                         for p in profiles],
            "next": ("close the interactive session, then run this command in a "
                     "visible terminal")}, indent=2))
        return 3

    readiness = cl.readiness_gate()
    if not readiness.get("ok"):
        print(json.dumps({
            "ok": False, "stage": "readiness", "verdict": readiness.get("verdict"),
            "failures": [{"name": c["name"], "detail": c["detail"]}
                         for c in readiness.get("failures") or []],
            "checked_at": readiness.get("checked_at")}, indent=2))
        return 3
    if args.check:
        print(json.dumps({"ok": True, "verdict": "GO",
                          "free_gb": pre["free_gb"], "required_gb": pre["required_gb"],
                          "profiles": [{"model": p["model"], "num_ctx": p.get("num_ctx")}
                                       for p in profiles],
                          "checked_at": readiness.get("checked_at")}, indent=2))
        return 0

    tasks = cl.load_tasks()
    state = cl.load_state()
    cl.recover_interrupted(state)
    result = cl.run_campaign(
        tasks, state, max_tasks=max(0, args.max_tasks),
        deadline_minutes=float(args.deadline_minutes),
        max_consecutive_failures=max(1, args.max_consecutive_failures),
        task_id=args.task, readiness=readiness)
    print(json.dumps({"ok": result.get("ok"), "run_id": result.get("run_id"),
                      "stop_reason": result.get("stop_reason"),
                      "attempted": result.get("attempted"),
                      "completed": result.get("completed"),
                      "failed": result.get("failed"),
                      "manifest": (result.get("manifest") or {}).get("run_id")},
                     indent=2))
    return 0 if result.get("ok") else 4


if __name__ == "__main__":
    raise SystemExit(main())
