"""tys_runner - the part of the loop that cannot run out of context.

The autonomy programme's rule is that the loop must survive a session dying, a
context filling up, a rate limit or a crash. That is impossible if the loop lives
inside the model. So this process owns the durable state and the agent session is
only a worker:

    next      reserve the highest-priority item, write the cycle brief, take the lock
    complete  validate the worker's result, record the cycle, decide rotation
    status    what is reserved, how many tokens today, what is next
    rotate    force a session rotation at the next boundary (or now, if idle)
    stop      create the STOP marker and release the lock
    dry-run   simulate N cycles and K rotations without touching real state

State lives in ``state/tys_runner/``:

    ledger.json      tokens and cycles per day (the 3M/day cap is enforced here)
    lease.json       the one cycle currently reserved (a second reservation is refused)
    checkpoint.json  last completed cycle and the next item (crash resume)
    sessions.jsonl   one line per worker session: start, cycles, end reason

The queue stays where it already is: ``reports/ty/autonomy_queue.json``.

Usage:
    python tools/tys_runner.py status
    python tools/tys_runner.py next
    python tools/tys_runner.py complete --result state/tys_runner/result.json
    python tools/tys_runner.py rotate --reason "context heavy"
    python tools/tys_runner.py dry-run --cycles 9 --per-session 3
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()

# ``check_command`` is the supervisor's own command policy. A contract is only
# dispatchable if it would also pass that policy, so the same module is imported
# here rather than a second, drifting copy of the token list.
sys.path.insert(0, str(ROOT / "scripts"))

QUEUE = ROOT / "reports" / "ty" / "autonomy_queue.json"
STATE_DIR = ROOT / "state" / "tys_runner"
LEDGER = STATE_DIR / "ledger.json"
LEASE = STATE_DIR / "lease.json"
CHECKPOINT = STATE_DIR / "checkpoint.json"
SESSIONS = STATE_DIR / "sessions.jsonl"
HANDOFF = ROOT / "reports" / "ty" / "cycle_handoff.json"
STOP = ROOT / "STOP"

TOKEN_CAP_PER_DAY = int(os.environ.get("TY_TOKEN_CAP_PER_DAY", "3000000"))
CAP_FRACTION = 0.90
CYCLES_PER_SESSION = int(os.environ.get("TY_CYCLES_PER_SESSION", "3"))
LEASE_TTL_S = int(os.environ.get("TY_LEASE_TTL_S", str(6 * 3600)))

ACTIVE = ("pending", "in_progress", "partial")


# --------------------------------------------------------------------- helpers
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


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


def _append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _ledger() -> Dict[str, Any]:
    return _read(LEDGER, {})


def _tokens_today() -> int:
    return int((_ledger().get(_today()) or {}).get("tokens") or 0)


def _cycles_today() -> int:
    return int((_ledger().get(_today()) or {}).get("cycles") or 0)


def _add_tokens(n: int) -> None:
    data = _ledger()
    day = data.setdefault(_today(), {"tokens": 0, "cycles": 0})
    day["tokens"] = int(day.get("tokens") or 0) + max(0, int(n))
    _write(LEDGER, data)


def _add_cycle() -> None:
    data = _ledger()
    day = data.setdefault(_today(), {"tokens": 0, "cycles": 0})
    day["cycles"] = int(day.get("cycles") or 0) + 1
    _write(LEDGER, data)


# ------------------------------------------------------------------- queue ops
def load_queue() -> Dict[str, Any]:
    data = _read(QUEUE, {})
    if not isinstance(data, dict) or "items" not in data:
        raise SystemExit(f"queue_unreadable: {QUEUE}")
    return data


def select_next(queue: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Highest priority item whose declared dependencies are all done.

    `depends_on` is enforced, not advisory: "work in order, no skipping" has to be
    a property of the selector, because a queue that merely *lists* an order is an
    order the loop can ignore. A reverted item is also deferred for two cycles so
    the same wall is not retried three times in a row.
    """
    queue = queue or load_queue()
    cycle = int(queue.get("cycle") or 0)
    items = queue.get("items", [])
    done = {str(i.get("id")) for i in items if str(i.get("status")) == "done"}
    rows = [i for i in items if str(i.get("status")) in ACTIVE]
    if not rows:
        return None
    unblocked = [i for i in rows
                 if all(str(dep) in done for dep in (i.get("depends_on") or []))]
    if not unblocked:
        return None
    ready = [i for i in unblocked if int(i.get("defer_until_cycle") or 0) <= cycle]
    pool = ready or unblocked
    pool.sort(key=lambda i: (-(int(i.get("priority") or 0)),
                             int(i.get("attempts") or 0),
                             str(i.get("id"))))
    return pool[0]


def blocked_by_dependencies(queue: Optional[Dict[str, Any]] = None) -> list:
    """Active items that cannot run yet, with the dependency that holds them."""
    queue = queue or load_queue()
    items = queue.get("items", [])
    done = {str(i.get("id")) for i in items if str(i.get("status")) == "done"}
    out = []
    for item in items:
        if str(item.get("status")) not in ACTIVE:
            continue
        missing = [str(d) for d in (item.get("depends_on") or []) if str(d) not in done]
        if missing:
            out.append({"id": item.get("id"), "waiting_on": missing})
    return out


def mark(queue: Dict[str, Any], item_id: str, status: str, **extra: Any) -> None:
    for item in queue.get("items", []):
        if item.get("id") == item_id:
            item["status"] = status
            item["updated_at"] = _now()
            item.update(extra)
            break
    queue["updated_at"] = _now()
    _write(QUEUE, queue)


# ------------------------------------------------------------------- lease/lock
def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:  # noqa: BLE001 - unknown means "do not assume alive"
        return False


def _lease() -> Optional[Dict[str, Any]]:
    lease = _read(LEASE, None)
    if not lease:
        return None
    # A TTL alone leaves a dead session's lease blocking the queue for hours
    # (measured: a killed launcher held cycle 21 for 6 h). The holder's pid is the
    # honest liveness test; the TTL is the backstop for a stuck-but-alive holder.
    holder = int(lease.get("pid") or 0)
    if not holder:
        # A lease written before the pid field existed cannot prove who holds it,
        # so it is unverifiable and therefore reclaimed rather than obeyed.
        _clear_lease("legacy_lease_no_pid")
        return None
    if not _pid_alive(holder):
        _clear_lease("holder_pid_dead")
        return None
    if time.time() - float(lease.get("taken_ts") or 0) > LEASE_TTL_S:
        _clear_lease("expired")
        return None
    return lease


def _clear_lease(reason: str = "") -> None:
    if LEASE.exists():
        try:
            LEASE.unlink()
        except OSError:
            pass
    if reason:
        _append(SESSIONS, {"at": _now(), "event": "lease_released", "reason": reason})


def _take_lease(cycle: int, item_id: str) -> None:
    _write(LEASE, {"cycle": cycle, "item": item_id, "taken_at": _now(),
                   "taken_ts": time.time(), "pid": os.getpid()})


# -------------------------------------------------------------------- commands
def cmd_status() -> int:
    queue = load_queue()
    nxt = select_next(queue)
    lease = _lease()
    ledger = _ledger().get(_today()) or {}
    counts: Dict[str, int] = {}
    for item in queue.get("items", []):
        counts[str(item.get("status"))] = counts.get(str(item.get("status")), 0) + 1
    print(json.dumps({
        "stop": STOP.exists(),
        "phase": queue.get("phase"),
        "cycle": queue.get("cycle"),
        "queue": counts,
        "next": (nxt or {}).get("id"),
        "next_title": (nxt or {}).get("title"),
        "lease": lease,
        "tokens_today": int(ledger.get("tokens") or 0),
        "token_cap": TOKEN_CAP_PER_DAY,
        "cycles_today": int(ledger.get("cycles") or 0),
        "cap_reached": int(ledger.get("tokens") or 0) >= TOKEN_CAP_PER_DAY * CAP_FRACTION,
        "checkpoint": _read(CHECKPOINT, {}),
    }, indent=2))
    return 0


def cmd_next(*, write_brief: bool = True) -> int:
    if STOP.exists():
        print(json.dumps({"ok": False, "stop": True,
                          "reason": "STOP marker present"}))
        return 3
    if _tokens_today() >= TOKEN_CAP_PER_DAY * CAP_FRACTION:
        print(json.dumps({"ok": False, "cap_reached": True,
                          "tokens_today": _tokens_today(),
                          "cap": TOKEN_CAP_PER_DAY,
                          "action": "checkpoint and stop until tomorrow"}))
        return 4
    existing = _lease()
    if existing:
        print(json.dumps({"ok": False, "lease_held": existing,
                          "reason": "a cycle is already reserved; complete or release it"}))
        return 5

    queue = load_queue()
    item = select_next(queue)
    if item is None:
        print(json.dumps({"ok": False, "queue_empty": True,
                          "action": "generate work (tier T3/T4) before continuing"}))
        return 6

    cycle = int(queue.get("cycle") or 0) + 1
    queue["cycle"] = cycle
    mark(queue, str(item["id"]), "in_progress")
    _take_lease(cycle, str(item["id"]))

    brief = {
        "cycle": cycle,
        "item": item.get("id"),
        "title": item.get("title"),
        "workstream": item.get("workstream"),
        "priority": item.get("priority"),
        "write_paths": item.get("write_paths") or [],
        "acceptance": item.get("acceptance") or "",
        "next_action": item.get("next") or item.get("title"),
        "rollback_tag": f"autonomy-cycle-{cycle:02d}",
        "tokens_today": _tokens_today(),
        "cycle_of_session": (_read(SESSIONS, []) or []) and _cycles_in_session(),
        "cycles_per_session": CYCLES_PER_SESSION,
    }
    if write_brief:
        _write(HANDOFF, {"at": _now(), "brief": brief,
                         "open_blockers": item.get("blocked_by") or []})
    print(json.dumps({"ok": True, "brief": brief}, indent=2))
    return 0


def _cycles_in_session() -> int:
    n = 0
    for line in reversed(SESSIONS.read_text(encoding="utf-8").splitlines()
                         if SESSIONS.exists() else []):
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("event") == "session_ended":
            break
        if row.get("event") == "cycle_completed":
            n += 1
    return n


# ------------------------------------------------------------------ contracts
# A shell operator inside an argv token means the token is really a command
# line. Nothing here spawns through a shell, so a token like "a; b" is either a
# mistake or an attempt to smuggle a second command past the allowlist.
_SHELL_OPERATORS = (";", "|", "&", ">", "<", "`", "$(")


def _shell_operator(token: str) -> Optional[str]:
    for operator in _SHELL_OPERATORS:
        if operator in str(token):
            return operator
    return None


def _runnable(item: Dict[str, Any]) -> "tuple[bool, str]":
    """tys_launcher owns the definition of dispatchable; ask it, do not copy it.

    The import is late on purpose: ``tys_launcher`` imports this module at
    module level, so importing it at module level here would be circular.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tys_launcher  # noqa: PLC0415 - late import avoids the cycle

    return tys_launcher.runnable(item)


def validate_contract(item: Dict[str, Any]) -> List[str]:
    """Every reason this queue item cannot be dispatched as an authored contract.

    ``runnable`` asks only whether the two lists are non-empty. That is
    necessary and not sufficient: the commands must be real argv (a shell string
    re-parses after every allowlist has seen it) and they must survive the
    supervisor's own ``check_command`` policy, so a contract written by the
    author lane cannot dispatch something the loop would refuse.
    """
    import continuous_loop as cl  # noqa: PLC0415 - ROOT/scripts is on sys.path

    if not isinstance(item, dict):
        return ["item is not an object"]
    problems: List[str] = []
    ok, why = _runnable(item)
    if not ok:
        problems.append(why)

    commands = item.get("acceptance_commands")
    if commands is None:
        return problems
    if isinstance(commands, str):
        return problems + ["acceptance_commands is a shell string, not argv lists"]
    if not isinstance(commands, (list, tuple)):
        return problems + ["acceptance_commands must be a list of argv lists"]

    for index, cmd in enumerate(commands):
        if isinstance(cmd, str):
            problems.append(f"command[{index}] is a shell string, not an argv list")
            continue
        if not isinstance(cmd, (list, tuple)) or not cmd:
            problems.append(f"command[{index}] is not a non-empty argv list")
            continue
        if not all(isinstance(token, str) and token.strip() for token in cmd):
            problems.append(f"command[{index}] has an empty or non-string token")
            continue
        argv = list(cmd)
        operators = [token for token in argv if _shell_operator(token)]
        if operators:
            problems.append(f"command[{index}] carries shell operators: "
                            f"{operators[:3]!r}")
            continue
        refusal = cl.check_command(argv)
        if refusal:
            problems.append(f"command[{index}] refused: {refusal}")
    return problems


def validate_result(result: Dict[str, Any], item_id: str) -> List[str]:
    """A completion is only valid with evidence a stranger could check."""
    problems: List[str] = []
    if str(result.get("item")) != str(item_id):
        problems.append(f"item mismatch: {result.get('item')} != {item_id}")
    if not isinstance(result.get("cycle"), int):
        problems.append("cycle missing")
    if "shipped" not in result:
        problems.append("shipped missing")
    for path in result.get("evidence") or []:
        if not (ROOT / str(path)).exists():
            problems.append(f"evidence missing: {path}")
    if result.get("shipped") and not (result.get("evidence") or []):
        problems.append("a shipped cycle must cite evidence")
    if result.get("shipped") and not result.get("tag"):
        problems.append("a shipped cycle must name its tag")
    for key in ("before", "after"):
        val = result.get(key)
        if val is not None and not isinstance(val, dict):
            problems.append(f"{key} must be an object of measurements")
    return problems


def cmd_complete(result_path: str) -> int:
    result = _read(Path(result_path), None)
    if not isinstance(result, dict):
        print(json.dumps({"ok": False, "error": f"result unreadable: {result_path}"}))
        return 2
    lease = _lease()
    if not lease:
        print(json.dumps({"ok": False, "error": "no lease held; nothing to complete"}))
        return 5
    problems = validate_result(result, str(lease["item"]))
    if problems:
        print(json.dumps({"ok": False, "handoff_invalid": problems}, indent=2))
        return 7

    queue = load_queue()
    item_id = str(lease["item"])
    status = "done" if result.get("shipped") else "pending"
    current = next((i for i in queue.get("items", []) if i.get("id") == item_id), {})
    extra: Dict[str, Any] = {
        "last_cycle": result.get("cycle"),
        "last_result": "shipped" if result.get("shipped") else "reverted",
        "attempts": int(current.get("attempts") or 0) + (0 if result.get("shipped") else 1),
    }
    if not result.get("shipped"):
        extra["defer_until_cycle"] = int(result.get("cycle") or 0) + 2
    if result.get("measurements") or result.get("after"):
        extra["measurements"] = result.get("after") or result.get("measurements")
    mark(queue, item_id, status, **extra)

    _add_tokens(int(result.get("tokens") or 0))
    _add_cycle()
    _append(SESSIONS, {"at": _now(), "event": "cycle_completed",
                       "cycle": result.get("cycle"), "item": item_id,
                       "shipped": bool(result.get("shipped")),
                       "tokens": int(result.get("tokens") or 0)})
    _write(CHECKPOINT, {"cycle": result.get("cycle"), "item": item_id,
                        "shipped": bool(result.get("shipped")),
                        "next": (select_next(queue) or {}).get("id"),
                        "at": _now()})
    _clear_lease("cycle complete")

    cycles = _cycles_in_session()
    rotate = cycles >= CYCLES_PER_SESSION or bool(result.get("context_heavy"))
    if rotate:
        _append(SESSIONS, {"at": _now(), "event": "session_ended",
                           "cycles": cycles,
                           "reason": "context_heavy" if result.get("context_heavy")
                           else "cycles_per_session"})
    print(json.dumps({"ok": True, "item": item_id, "status": status,
                      "cycles_in_session": cycles, "rotate": rotate,
                      "next": (select_next(queue) or {}).get("id")}, indent=2))
    return 0


def cmd_rotate(reason: str) -> int:
    cycles = _cycles_in_session()
    _append(SESSIONS, {"at": _now(), "event": "session_ended", "cycles": cycles,
                       "reason": reason or "manual"})
    _clear_lease("rotation")
    print(json.dumps({"ok": True, "rotated": True, "cycles": cycles,
                      "reason": reason or "manual"}, indent=2))
    return 0


def cmd_stop() -> int:
    STOP.write_text(f"stopped by operator at {_now()}\n", encoding="utf-8")
    _clear_lease("stop")
    _append(SESSIONS, {"at": _now(), "event": "stopped"})
    print(json.dumps({"ok": True, "stop": str(STOP)}, indent=2))
    return 0


def cmd_dry_run(cycles: int, per_session: int) -> int:
    """Simulate the loop's bookkeeping. Writes nothing outside the temp state."""
    queue = load_queue()
    simulated: List[Dict[str, Any]] = []
    rotations = 0
    in_session = 0
    remaining = {str(i["id"]): str(i.get("status")) for i in queue.get("items", [])}
    for n in range(1, max(1, cycles) + 1):
        candidates = [i for i in queue.get("items", [])
                      if remaining.get(str(i["id"])) in ACTIVE]
        if not candidates:
            simulated.append({"cycle": n, "stopped": "queue_empty"})
            break
        candidates.sort(key=lambda i: (-(int(i.get("priority") or 0)), str(i.get("id"))))
        item = candidates[0]
        in_session += 1
        remaining[str(item["id"])] = "done"
        simulated.append({"cycle": n, "item": item["id"],
                          "session_cycle": in_session})
        if in_session >= per_session:
            rotations += 1
            in_session = 0
    print(json.dumps({"cycles": len(simulated), "rotations": rotations,
                      "per_session": per_session,
                      "trace": simulated}, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Northstar autonomy runner")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("next")
    p_complete = sub.add_parser("complete")
    p_complete.add_argument("--result", required=True)
    p_rotate = sub.add_parser("rotate")
    p_rotate.add_argument("--reason", default="")
    sub.add_parser("stop")
    p_dry = sub.add_parser("dry-run")
    p_dry.add_argument("--cycles", type=int, default=9)
    p_dry.add_argument("--per-session", type=int, default=CYCLES_PER_SESSION)
    ns = parser.parse_args(argv)

    if ns.cmd == "status":
        return cmd_status()
    if ns.cmd == "next":
        return cmd_next()
    if ns.cmd == "complete":
        return cmd_complete(ns.result)
    if ns.cmd == "rotate":
        return cmd_rotate(ns.reason)
    if ns.cmd == "stop":
        return cmd_stop()
    if ns.cmd == "dry-run":
        return cmd_dry_run(ns.cycles, ns.per_session)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
