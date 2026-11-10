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
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()

#: Where this file's own code lives. ``ROOT`` is the state root and is redirected
#: by tests and campaigns; the command policy is code and must not move with it.
CODE_ROOT = Path(__file__).resolve().parents[1]

#: Loaded policy modules, keyed by code root.
_POLICY: Dict[str, Any] = {}

# ``check_command`` is the supervisor's own command policy. A contract is only
# dispatchable if it would also pass that policy, so the same module is imported
# here rather than a second, drifting copy of the token list.
sys.path.insert(0, str(CODE_ROOT / "scripts"))

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


def _dispatchable(item: Dict[str, Any]) -> bool:
    """Would ``validate_contract`` accept this item right now?

    Cheap enough to ask per selection (it is a string policy, not a subprocess), and
    the answer is what keeps a queue full of ``needs_author`` rows from starving the
    launcher: a non-dispatchable item is chosen last, not one-at-a-time-forever.
    """
    try:
        return not validate_contract(item)
    except Exception:  # noqa: BLE001 - an item that cannot be judged is not dispatchable
        return False


def select_next(queue: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Highest priority item whose declared dependencies are all done.

    `depends_on` is enforced, not advisory: "work in order, no skipping" has to be
    a property of the selector, because a queue that merely *lists* an order is an
    order the loop can ignore. A reverted item is also deferred for two cycles so
    the same wall is not retried three times in a row.

    Dispatchable items come first. Without that, forty ``needs_author`` rows at the
    top of the queue are walked one per cycle and the launcher ends the run at
    ``no_runnable_items`` while real work sits below them. ``pool = ready or
    unblocked`` is kept on purpose: the stall is still journalled, not hidden.
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
    pool.sort(key=lambda i: (not _dispatchable(i),
                             -(int(i.get("priority") or 0)),
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


def reconcile_parks(queue: Optional[Dict[str, Any]] = None, *, apply: bool = False,
                    repo: Optional[Path] = None) -> Dict[str, Any]:
    """Park items whose material contract has earned three rejections; revive the changed.

    Strikes are read from the append-only ledger, never from a stored counter, so a
    hand-edited queue cannot un-park itself. Revival is a **signature change only**:
    rewriting the identical contract (or bumping ``contract_written_at``) must not
    un-park an item, or the loop's answer to a wall becomes "try the same thing".

    Called twice on purpose: eagerly in ``cmd_complete`` and repaired at the top of
    ``cmd_next``. A crash between evaluation and completion still parks, because the
    ledger is already durable and this function only has to re-read it.
    """
    import tys_evaluator as evaluator  # noqa: PLC0415 - the evaluator imports nothing here

    root = Path(repo or ROOT)
    ledger_path = evaluator.rejections_path(root)
    target = queue if queue is not None else load_queue()
    cycle = int(target.get("cycle") or 0)
    parked: List[Dict[str, Any]] = []
    revived: List[Dict[str, Any]] = []
    checked = 0
    changed = False

    for item in target.get("items", []):
        status = str(item.get("status"))
        if status in ACTIVE:
            if not (item.get("write_paths") and item.get("acceptance_commands")):
                continue
            checked += 1
            signature = evaluator.attempt_signature(item)
            streak = evaluator.rejection_streak(str(item.get("id")), signature,
                                                path=ledger_path)
            if streak < evaluator.STRIKE_LIMIT:
                continue
            newest = evaluator.latest_rejection(str(item.get("id")), signature,
                                                path=ledger_path)
            gate = str(newest.get("gate") or "unknown")
            parked.append({"id": item.get("id"), "gate": gate, "streak": streak})
            if apply:
                item["status"] = "needs_author"
                item["needs_author"] = f"rejection_cap:{gate} x{streak}"
                item["parked_signature"] = signature
                item["parked_cycle"] = cycle
                item["defer_until_cycle"] = None
                item["updated_at"] = _now()
                changed = True
        elif status == "needs_author" and item.get("parked_signature"):
            signature = evaluator.attempt_signature(item)
            if signature == str(item.get("parked_signature")):
                continue
            revived.append({"id": item.get("id"), "signature": signature})
            if apply:
                item["status"] = "pending"
                item.pop("needs_author", None)
                item.pop("parked_signature", None)
                item.pop("parked_cycle", None)
                item["defer_until_cycle"] = None
                item["updated_at"] = _now()
                changed = True

    if apply and changed:
        target["updated_at"] = _now()
        _write(QUEUE, target)
    return {"parked": parked, "revived": revived, "checked": checked,
            "ledger": str(ledger_path), "applied": bool(apply and changed)}


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


def _take_lease(cycle: int, item_id: str) -> str:
    """Reserve one cycle and return the token that proves the reservation.

    The pid answers "is the holder alive?" and that is the right question for
    ``next``. It is the wrong question for ``complete``: a worker that runs as a
    separate process from the one that reserved has a different pid, and a dead
    launcher's reservation must still be completable by the worker it already
    dispatched. The token is the authorisation; the pid stays the liveness test.
    """
    token = secrets.token_hex(8)
    _write(LEASE, {"cycle": cycle, "item": item_id, "taken_at": _now(),
                   "taken_ts": time.time(), "pid": os.getpid(), "token": token})
    return token


# -------------------------------------------------------------------- commands
def cmd_status() -> int:
    queue = load_queue()
    nxt = select_next(queue)
    lease = _lease()
    try:
        parks = reconcile_parks(queue, apply=False)
    except (OSError, ValueError) as exc:  # a broken ledger must not hide the status
        parks = {"error": str(exc)}
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
        "parks": parks,
        "tokens_today": int(ledger.get("tokens") or 0),
        "token_cap": TOKEN_CAP_PER_DAY,
        "cycles_today": int(ledger.get("cycles") or 0),
        "cap_reached": int(ledger.get("tokens") or 0) >= TOKEN_CAP_PER_DAY * CAP_FRACTION,
        "checkpoint": _read(CHECKPOINT, {}),
    }, indent=2))
    return 0


def _generator():
    """The work generator, loaded late: ``tys_generator`` imports this module."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import tys_generator  # noqa: PLC0415 - late import avoids the cycle

    return tys_generator


LOW_WATER = 3


def _top_up(limit: int = LOW_WATER) -> Dict[str, Any]:
    """Refill before the lease is released when the dispatchable shelf is low.

    Only when there is genuinely little work: asking the generator on every cycle
    would make discovery the loop's most frequent action, and discovery is the part
    that can be wrong. One item per call is the contract.
    """
    try:
        generator = _generator()
        # Refill only the real queue. Under a redirected root the generator's probes
        # would run against the code root and report on a tree this cycle never
        # touched - and in a unit test it would start a real pytest inside one.
        if Path(generator.QUEUE).resolve() != Path(QUEUE).resolve():
            return {"skipped": "redirected_root",
                    "generator_queue": str(generator.QUEUE)}
        forward = generator.needs_forward(load_queue())
    except Exception as exc:  # noqa: BLE001 - a refill must never fail a completion
        return {"skipped": "generator_unavailable", "detail": str(exc)}
    if forward >= limit:
        return {"skipped": "above_low_water", "dispatchable": forward}
    try:
        result = generator.generate(max_items=1)
    except Exception as exc:  # noqa: BLE001
        return {"skipped": "generator_error", "detail": str(exc)}
    if isinstance(result, dict):
        result["dispatchable_before"] = forward
    return result


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

    # A13: repair the queue before selecting, so an item that earned its third
    # rejection in a cycle that then crashed is parked rather than retried.
    try:
        parks = reconcile_parks(apply=True)
    except (OSError, ValueError) as exc:
        _append(SESSIONS, {"at": _now(), "event": "reconcile_failed",
                           "reason": str(exc)})
        parks = {"error": str(exc)}

    queue = load_queue()
    item = select_next(queue)
    if item is None:
        # A16: an empty shelf is the generator's cue, not the loop's end. One call,
        # guarded, because a discovery bug must not crash the reservation path.
        generated: Dict[str, Any]
        try:
            generated = _generator().generate()
        except Exception as exc:  # noqa: BLE001 - generation cannot be allowed to kill next
            generated = {"ok": False, "reason": "generator_error", "detail": str(exc)}
        queue = load_queue()
        item = select_next(queue)
        if item is None:
            # Honest starvation: nothing is invented, and the record names every
            # surface's number so the next reader knows what was checked.
            _append(SESSIONS, {"at": _now(), "event": "starvation",
                               "reason": generated.get("reason"),
                               "detail": (generated.get("detail")
                                          or generated.get("tiers")
                                          or generated.get("state"))})
            print(json.dumps({"ok": False, "queue_empty": True, "parks": parks,
                              "starvation": generated,
                              "action": "nothing to do; the starvation record names why"},
                             indent=2))
            return 6

    cycle = int(queue.get("cycle") or 0) + 1
    queue["cycle"] = cycle
    mark(queue, str(item["id"]), "in_progress")
    lease_token = _take_lease(cycle, str(item["id"]))

    brief = {
        "cycle": cycle,
        "item": item.get("id"),
        "title": item.get("title"),
        "workstream": item.get("workstream"),
        "priority": item.get("priority"),
        "write_paths": item.get("write_paths") or [],
        "acceptance": item.get("acceptance") or "",
        "acceptance_commands": item.get("acceptance_commands") or [],
        "next_action": item.get("next") or item.get("title"),
        "rollback_tag": f"autonomy-cycle-{cycle:02d}",
        "lease_token": lease_token,
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


def _command_policy():
    """The supervisor's own command policy, loaded from the *code* root.

    ``ROOT`` is the state root and can be redirected (``NORTHSTAR_TY_ROOT``) at a
    test or a campaign. The policy is code, not state, so it is loaded from the
    directory this file actually lives in. Loading it by ``import`` after a
    module-level ``sys.path`` insert bound it to whichever root happened to be on
    the path at first import; under a redirected root that import failed, the
    selector swallowed the error, and every item silently became non-dispatchable.
    """
    key = str(CODE_ROOT)
    cached = _POLICY.get(key)
    if cached is not None:
        return cached
    import importlib.util  # noqa: PLC0415 - only needed once per process

    path = CODE_ROOT / "scripts" / "continuous_loop.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("continuous_loop_by_path", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _POLICY[key] = module
    return module


def validate_contract(item: Dict[str, Any]) -> List[str]:
    """Every reason this queue item cannot be dispatched as an authored contract.

    ``runnable`` asks only whether the two lists are non-empty. That is
    necessary and not sufficient: the commands must be real argv (a shell string
    re-parses after every allowlist has seen it) and they must survive the
    supervisor's own ``check_command`` policy, so a contract written by the
    author lane cannot dispatch something the loop would refuse.
    """
    if not isinstance(item, dict):
        return ["item is not an object"]
    problems: List[str] = []
    ok, why = _runnable(item)
    if not ok:
        problems.append(why)

    commands = item.get("acceptance_commands")
    if commands is None or isinstance(commands, str):
        # The shape problem is reported even when ``runnable`` already refused the
        # item: relying on the earlier refusal would hide *why* the shape is wrong.
        return problems + [
            "acceptance_commands is a shell string, not argv lists"
            if isinstance(commands, str) else
            "acceptance_commands must be a list of argv lists"]
    if not isinstance(commands, (list, tuple)):
        return problems + ["acceptance_commands must be a list of argv lists"]

    policy = _command_policy()
    if policy is None:
        return problems + ["the command policy scripts/continuous_loop.py is missing "
                           "from the code root, so no command can be judged"]

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
        refusal = policy.check_command(argv)
        if refusal:
            problems.append(f"command[{index}] refused: {refusal}")
    return problems


def validate_result(result: Dict[str, Any], item_id: str,
                    expected_cycle: Any = None) -> List[str]:
    """A completion is only valid with evidence a stranger could check."""
    problems: List[str] = []
    if str(result.get("item")) != str(item_id):
        problems.append(f"item mismatch: {result.get('item')} != {item_id}")
    if not isinstance(result.get("cycle"), int):
        problems.append("cycle missing")
    elif expected_cycle is not None and int(result["cycle"]) != int(expected_cycle):
        # A stale result file must not close a later reservation. The C3 probe
        # completed a cycle reserved at 94 with a result written for cycle 1.
        problems.append(f"cycle mismatch: result says {result['cycle']}, "
                        f"the lease reserved {expected_cycle}")
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


def cmd_complete(result_path: str, token: str = "") -> int:
    result = _read(Path(result_path), None)
    if not isinstance(result, dict):
        print(json.dumps({"ok": False, "error": f"result unreadable: {result_path}"}))
        return 2
    # Read the raw reservation before ``_lease()`` can reclaim it: a worker in a
    # different process is not the holder's pid, and it is still the holder.
    raw_lease = _read(LEASE, None)
    lease = _lease()
    if not lease and token and isinstance(raw_lease, dict) \
            and str(raw_lease.get("token") or "") == str(token):
        lease = raw_lease
    if not lease:
        print(json.dumps({"ok": False, "error": "no lease held; nothing to complete"}))
        return 5
    problems = validate_result(result, str(lease["item"]),
                               expected_cycle=lease.get("cycle"))
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
    # A13: park eagerly, before ``mark`` writes the status, so a third rejection on
    # this gate ends the item here instead of waiting for the next ``next``.
    park: Dict[str, Any] = {}
    try:
        report = reconcile_parks(queue, apply=False)
        park = next((row for row in report.get("parked") or []
                     if str(row.get("id")) == item_id), {})
    except (OSError, ValueError) as exc:
        _append(SESSIONS, {"at": _now(), "event": "reconcile_failed",
                           "reason": str(exc)})
    if park:
        import tys_evaluator as evaluator  # noqa: PLC0415 - late: avoids the cycle
        status = "needs_author"
        extra["needs_author"] = (f"rejection_cap:{park.get('gate')} "
                                 f"x{park.get('streak')}")
        extra["parked_signature"] = evaluator.attempt_signature(current)
        extra["parked_cycle"] = int(result.get("cycle") or 0)
        extra["defer_until_cycle"] = None
    elif not result.get("shipped"):
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
    # A16 delta 2: refill while the lease is still held, so a crash during
    # generation cannot leave a live-pid lease behind. In ``finally`` on purpose.
    try:
        top_up = _top_up()
    finally:
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
                      "top_up": top_up,
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
    """Simulate the loop's bookkeeping. Writes nothing outside the temp state.

    The selector here is the real one: ``depends_on``, ``defer_until_cycle`` and
    dispatchable-first ordering all apply. A trace that ignored them could show nine
    cycles the real selector would have refused, which is worse than no trace.
    """
    queue = load_queue()
    simulated: List[Dict[str, Any]] = []
    rotations = 0
    in_session = 0
    status = {str(i["id"]): str(i.get("status")) for i in queue.get("items", [])}
    cycle = int(queue.get("cycle") or 0)
    for n in range(1, max(1, cycles) + 1):
        cycle += 1
        done = {key for key, value in status.items() if value == "done"}
        rows = [i for i in queue.get("items", [])
                if status.get(str(i["id"])) in ACTIVE]
        if not rows:
            simulated.append({"cycle": n, "stopped": "queue_empty"})
            break
        unblocked = [i for i in rows
                     if all(str(dep) in done for dep in (i.get("depends_on") or []))]
        if not unblocked:
            simulated.append({"cycle": n, "stopped": "no_runnable_items",
                              "blocked": blocked_by_dependencies(queue)})
            break
        ready = [i for i in unblocked if int(i.get("defer_until_cycle") or 0) <= cycle]
        pool = ready or unblocked
        pool.sort(key=lambda i: (not _dispatchable(i),
                                 -(int(i.get("priority") or 0)),
                                 int(i.get("attempts") or 0),
                                 str(i.get("id"))))
        item = pool[0]
        in_session += 1
        status[str(item["id"])] = "done"
        simulated.append({"cycle": n, "item": item["id"],
                          "dispatchable": _dispatchable(item),
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
    p_complete.add_argument("--token", default="",
                            help="the lease token from the cycle brief; lets a worker "
                                 "in a different process complete the reservation")
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
        return cmd_complete(ns.result, ns.token)
    if ns.cmd == "rotate":
        return cmd_rotate(ns.reason)
    if ns.cmd == "stop":
        return cmd_stop()
    if ns.cmd == "dry-run":
        return cmd_dry_run(ns.cycles, ns.per_session)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
