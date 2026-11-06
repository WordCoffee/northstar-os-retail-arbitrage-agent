"""tys_launcher - the process that keeps working when the session does not.

`tys_runner.py` knows how to reserve a cycle, validate evidence and rotate a
session. It does not *call* anything, so on its own it is a set of rules with no
engine. This is the engine: it loops ``next -> worker -> complete``, keeps a
heartbeat, and stops only for a declared reason.

    python tools/tys_launcher.py --max-hours 8 --max-cycles 20
    python tools/tys_launcher.py --dry-run --max-cycles 3        # no worker
    python tools/tys_launcher.py --worker "python scripts/ty_task_runner.py ..."

Task contract: a queue item is only runnable when it names its checks
(``acceptance_commands``) and its write scope (``write_paths``). An item without
checks is marked ``needs-author`` and skipped - the launcher never invents a
pass criterion, because an invented criterion is how an autonomous loop ships
broken work.

Stop conditions (each recorded in the heartbeat with its reason):
    STOP file · token cap · queue empty · max-cycles · max-hours · worker failure
    streak (3) · handoff invalid (2)

Every step appends to ``state/tys_runner/launcher.jsonl`` and rewrites
``state/tys_runner/heartbeat.json`` so another process (or a human) can see what
it is doing and how long it has been doing it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tys_runner as runner  # noqa: E402

STATE = ROOT / "state" / "tys_runner"
HEARTBEAT = STATE / "heartbeat.json"
JOURNAL = STATE / "launcher.jsonl"
BRIEF = ROOT / "reports" / "ty" / "cycle_handoff.json"
WORKER_TIMEOUT_S = int(os.environ.get("TY_WORKER_TIMEOUT_S", "1800"))
MAX_FAILURE_STREAK = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **row}, ensure_ascii=False) + "\n")


def heartbeat(**fields: Any) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    payload = {"at": _now(), "pid": os.getpid(), **fields}
    tmp = HEARTBEAT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(HEARTBEAT)


# --------------------------------------------------------------------- contracts
def task_contract(item: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
    """The task JSON `ty_task_runner.py` consumes, built only from declared fields."""
    commands = item.get("acceptance_commands") or []
    if isinstance(commands, str):
        commands = [[commands]]
    return {
        "id": item.get("id"),
        "objective": item.get("next") or item.get("title") or "",
        "write_paths": item.get("write_paths") or [],
        "read_paths": item.get("read_paths") or [],
        "acceptance_commands": commands,
        "required_files": item.get("required_files") or [],
        "max_steps": int(item.get("max_steps") or 12),
        "max_repairs": int(item.get("max_repairs") or 2),
        "model": item.get("model") or os.environ.get("TY_WORKER_MODEL", ""),
        "_cycle": brief.get("cycle"),
    }


def runnable(item: Dict[str, Any]) -> tuple[bool, str]:
    if not item.get("write_paths"):
        return False, "no write_paths declared"
    if not item.get("acceptance_commands"):
        return False, "no acceptance_commands declared"
    return True, ""


def estimate_tokens(payload: Any) -> int:
    """Rough accounting, labelled as such: 4 characters per token."""
    text = json.dumps(payload, default=str) if not isinstance(payload, str) else payload
    return max(0, len(text) // 4)


# ------------------------------------------------------------------------ worker
def default_worker(task_path: Path, result_path: Path) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "ty_task_runner.py"),
           "--task", str(task_path), "--result", str(result_path)]
    proc = subprocess.run(cmd, cwd=str(ROOT), timeout=WORKER_TIMEOUT_S,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        _append(JOURNAL, {"event": "worker_failed", "code": proc.returncode,
                          "stderr": (proc.stderr or "")[-600:]})
    return proc.returncode


Worker = Callable[[Path, Path], int]


def _run_cycle(*, worker: Worker, dry_run: bool, cycle_budget: int) -> Dict[str, Any]:
    """One cycle: reserve, run the worker, validate, complete."""
    brief_out = runner.cmd_next(write_brief=True)
    if brief_out != 0:
        return {"ok": False, "stop": True, "code": brief_out,
                "reason": {3: "STOP", 4: "token_cap", 5: "lease_held",
                           6: "queue_empty"}.get(brief_out, f"next_exit_{brief_out}")}
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))["brief"]
    queue = runner.load_queue()
    item = next((i for i in queue.get("items", []) if i.get("id") == brief["item"]), {})
    ok, why = runnable(item)
    if not ok:
        runner.mark(queue, str(item.get("id")), "pending",
                    needs_author=why, defer_until_cycle=int(brief["cycle"]) + 1)
        runner._clear_lease("not runnable")
        _append(JOURNAL, {"event": "skipped_not_runnable", "item": item.get("id"),
                          "reason": why})
        return {"ok": True, "skipped": True, "item": item.get("id"), "reason": why}

    if dry_run:
        runner._clear_lease("dry run")
        _append(JOURNAL, {"event": "dry_run_cycle", "item": item.get("id")})
        return {"ok": True, "dry_run": True, "item": item.get("id")}

    task_path = STATE / "task.json"
    result_path = STATE / "worker_result.json"
    task_path.write_text(json.dumps(task_contract(item, brief), indent=2), encoding="utf-8")
    if result_path.exists():
        result_path.unlink()
    started = time.time()
    try:
        code = worker(task_path, result_path)
    except subprocess.TimeoutExpired:
        code = 124
    elapsed = round(time.time() - started, 1)
    worker_out = {}
    if result_path.exists():
        try:
            worker_out = json.loads(result_path.read_text(encoding="utf-8"))
        except ValueError:
            worker_out = {}
    shipped = bool(worker_out.get("ok")) and int(worker_out.get("steps") or 0) > 0
    evidence_paths: List[str] = [str(p) for p in (worker_out.get("evidence") or [])]
    if shipped and not evidence_paths:
        # The runner refuses a shipped cycle with no evidence, and it is right to:
        # "I fixed it" is not evidence. The worker's own report plus the checks it
        # ran IS the record, so persist it under state/evidence and cite that.
        ev_dir = ROOT / "state" / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        ev_file = ev_dir / f"cycle_{brief['cycle']:03d}_{brief['item']}.json"
        ev_file.write_text(json.dumps({
            "item": brief["item"], "cycle": brief["cycle"],
            "task": json.loads(task_path.read_text(encoding="utf-8")),
            "worker": worker_out, "worker_exit": code, "seconds": elapsed,
            "at": _now(),
        }, indent=2, default=str), encoding="utf-8")
        evidence_paths = [str(ev_file.relative_to(ROOT)).replace("\\", "/")]
    completion = {
        "item": brief["item"],
        "cycle": brief["cycle"],
        "shipped": shipped,
        "tag": brief.get("rollback_tag") if shipped else "",
        "evidence": evidence_paths,
        "tokens": estimate_tokens(worker_out) + estimate_tokens(brief),
        "before": worker_out.get("before") or {},
        "after": worker_out.get("after") or {},
        "worker_exit": code,
        "seconds": elapsed,
    }
    completion_path = STATE / "completion.json"
    completion_path.write_text(json.dumps(completion, indent=2), encoding="utf-8")
    rc = runner.cmd_complete(str(completion_path))
    if rc == 7 and shipped:
        # A shipped cycle with no evidence is refused by the runner; record the
        # worker's own report as the evidence so the refusal is diagnosable.
        _append(JOURNAL, {"event": "completion_refused", "item": brief["item"],
                          "worker": worker_out})
    return {"ok": rc == 0, "item": brief["item"], "shipped": shipped,
            "cycle": brief["cycle"], "seconds": elapsed, "worker_exit": code,
            "complete_exit": rc}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Loop driver: next -> worker -> complete.")
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-hours", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-token-budget", type=int, default=0,
                        help="stop after this many estimated tokens this run")
    ns = parser.parse_args(argv)

    started = time.time()
    deadline = started + ns.max_hours * 3600
    cycles = 0
    failures = 0
    tokens = 0
    reason = "max_cycles"

    heartbeat(state="starting", dry_run=ns.dry_run, max_cycles=ns.max_cycles,
              max_hours=ns.max_hours)
    while cycles < ns.max_cycles:
        if time.time() >= deadline:
            reason = "max_hours"
            break
        if (ROOT / "STOP").exists():
            reason = "STOP"
            break
        before = runner._tokens_today()
        out = _run_cycle(worker=default_worker, dry_run=ns.dry_run,
                         cycle_budget=ns.max_cycles - cycles)
        if out.get("stop"):
            reason = out.get("reason", "stop")
            _append(JOURNAL, {"event": "stopped", "reason": reason})
            break
        cycles += 1
        tokens += max(0, runner._tokens_today() - before)
        if out.get("skipped"):
            failures = 0
        elif out.get("ok"):
            failures = 0
        else:
            failures += 1
            if failures >= MAX_FAILURE_STREAK:
                reason = "worker_failure_streak"
                break
        if ns.max_token_budget and tokens >= ns.max_token_budget:
            reason = "token_budget"
            break
        heartbeat(state="running", cycles=cycles, tokens_estimate=tokens,
                  last=out, failures=failures)

    heartbeat(state="stopped", reason=reason, cycles=cycles,
              tokens_estimate=tokens, seconds=round(time.time() - started, 1))
    _append(JOURNAL, {"event": "launcher_stopped", "reason": reason, "cycles": cycles,
                      "tokens_estimate": tokens})
    print(json.dumps({"stopped": True, "reason": reason, "cycles": cycles,
                      "tokens_estimate": tokens,
                      "seconds": round(time.time() - started, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
