"""tys_generator - the T0..T5 ladder: the queue never runs empty *without saying why*.

"Never empty" is not the same as "always busy". A generator that can always find
something to do will eventually invent busywork, so this module is allowed to
return nothing - but only with a reason, and with the numbers that justify it:

    STOP / busy / deferred_budget / supply_capped / gate_closed
    duplicate / starvation / no_source

The ladder is strict, not round-robin. Tiers are tried T0 -> T5 and the **first
tier that yields a candidate wins**, so a scan finding can never displace a red
check:

    T0 incident   1300-1399   an incident probe, or a shipped item whose check regressed
    T1 red check   900- 999   a red check (a proposal's failing run, a red test probe)
    T2 scan        700- 799   production_readiness_scan findings (never dispatchable)
    T3 backlog     500- 599   improvement_backlog items that already name scope + checks
    T4 intel       300- 399   intel gaps that name a falsifiable argv
    T5 maintenance 100- 139   probes, the backlog check, the regression baseline

Within a band the priority is ``base + min(span, days_first_seen)`` so age can
break a tie but cannot lift work out of its band. ``span`` is the width of the
band (99 for T0..T4, 39 for T5), which is what makes the stated band edges and
the stated formula agree.

Two brakes, both deliberate:

    MAX_GENERATED_ACTIVE = 12   the generator's own items currently in flight
    MAX_GENERATED_PER_DAY = 24  emissions recorded in state/tys_generator/emitted.jsonl

Over either one the answer is ``supply_capped`` and nothing is added. The launcher
halts at 40 consecutive skips, so a discovery bug that floods the queue with
unrunnable items stops the loop rather than degrading it.

Dedupe is by ``dedupe_key``, indexed across *every* status, not just the active
ones: pending/in_progress/partial are skipped, ``needs_author`` is promoted in
place (same id, attempts untouched), a ``done`` item is reopened at most twice and
then escalated, and a key that was removed from the queue gets exactly one re-emit
from the append-only ``emitted.jsonl`` before it is escalated as "deleted twice".

A key that keeps failing four times is not work, it is a wall: three consecutive
reverts escalate the item to ``needs_author``. The count comes from
``tys_evaluator.rejection_streak`` when A13 has landed, and from the item's own
``attempts``/``last_result`` until then.

Everything dangerous is capped by construction: no probe runs anything that is
not in ``tys_probes``'s table, no generated argv is accepted without passing
``continuous_loop.check_command``, and this module never contacts a network
service or spends money.

Usage::

    python tools/tys_generator.py --json                 # one item, or a reason
    python tools/tys_generator.py --tier T3 --dry-run    # what would T3 give?
    python tools/tys_generator.py --needs-forward        # dispatchable active items
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

TOOLS = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT") or TOOLS.parent).resolve()
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

QUEUE = ROOT / "reports" / "ty" / "autonomy_queue.json"
STATE = ROOT / "state" / "tys_generator"
EMITTED = STATE / "emitted.jsonl"
LOCK = STATE / "lock.json"
PROPOSALS = ROOT / "state" / "backlog" / "proposals.json"
IMPROVEMENTS = ROOT / "state" / "backlog" / "improvements.json"
GAPS = ROOT / "state" / "intel" / "gaps.json"
REGRESSIONS = ROOT / "state" / "probes" / "regressions.json"
NEEDS_YOU = ROOT / "reports" / "ty" / "needs_you.md"
STOP = ROOT / "STOP"

SCAN_ARGV = ["python", "tools/production_readiness_scan.py", "--json"]
BACKLOG_CHECK_ARGV = ["python", "tools/improvement_backlog.py", "--check"]

#: ``tys_runner.ACTIVE`` spelled out: importing the runner to read a tuple would
#: make this module unusable when the runner is being repaired.
ACTIVE = ("pending", "in_progress", "partial")

#: The gate every product tier waits on. T2/T3/T4 work is blocked by dependency,
#: not by intent: a scan finding has no check and no derivable scope, so it must
#: never run before the generator exists.
GATE_DEP = "M2-work-generator"
PRODUCT_TIERS = ("T2", "T3", "T4")

BANDS = {"T0": 1300, "T1": 900, "T2": 700, "T3": 500, "T4": 300, "T5": 100}
BAND_TOP = {"T0": 1399, "T1": 999, "T2": 799, "T3": 599, "T4": 399, "T5": 139}
TIERS = ("T0", "T1", "T2", "T3", "T4", "T5")

MAX_GENERATED_ACTIVE = 12
MAX_GENERATED_PER_DAY = 24
MAX_REOPENS = 2
MAX_REVERTS = 3

MARK = "tys_generator"
CAP_FRACTION = 0.90
DEFAULT_PROBE_TIMEOUT_S = 300


# ---------------------------------------------------------------- lazy imports
def _import(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except Exception:  # noqa: BLE001 - a missing collaborator is reported by the caller
        return None


def _probes() -> Any:
    return _import("tys_probes")


def _runner() -> Any:
    module = _import("tys_runner")
    if module is None:
        raise RuntimeError("tys_runner is not importable")
    return module


def _launcher() -> Any:
    module = _import("tys_launcher")
    if module is None:
        raise RuntimeError("tys_launcher is not importable")
    return module


# --------------------------------------------------------------------- helpers
def _as_dt(value: Any) -> datetime:
    """A UTC datetime from a datetime, a date or an ISO string; now() when unusable."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if text:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _now_iso(now: Any = None) -> str:
    return _as_dt(now).isoformat(timespec="seconds")


def _today(now: Any = None) -> str:
    return _as_dt(now).strftime("%Y-%m-%d")


def _read(path: Any, default: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _plain_write(path: Any, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(target)


def _write_queue(path: Any, data: Any) -> None:
    """The runner's own atomic write, so the queue has exactly one writer's shape."""
    try:
        _runner()._write(Path(path), data)
    except Exception:  # noqa: BLE001 - the fallback is the same format, byte for byte
        _plain_write(path, data)


def _append_jsonl(path: Any, row: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _json_from(text: Any) -> Any:
    raw = str(text or "")
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except ValueError:
        return None


def _days_since(stamp: Any, now: Any) -> int:
    text = str(stamp or "").strip()
    if not text:
        return 0
    return max(0, int((_as_dt(now) - _as_dt(text)).total_seconds() // 86400))


def priority_for(tier: str, days: int = 0) -> int:
    """``base + min(band width, days_first_seen)`` - the bands in the spec, exactly."""
    name = str(tier or "").upper()
    if name not in BANDS:
        raise ValueError(f"unknown tier {tier!r}; choose from {', '.join(TIERS)}")
    base = BANDS[name]
    span = min(99, BAND_TOP[name] - base)
    return base + max(0, min(span, int(days or 0)))


def item_id_for(key: str) -> str:
    """A stable id per dedupe key, so a re-emit updates the same item."""
    text = str(key or "")
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48] or "item"
    return f"gen-{slug}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:6]}"


# ------------------------------------------------------------------- dedupe keys
def _first_argv(item: Dict[str, Any]) -> List[str]:
    for candidate in (item.get("acceptance_commands") or [],
                      [c.get("cmd") for c in (item.get("checks") or [])
                       if isinstance(c, dict) and c.get("cmd")]):
        for entry in candidate or []:
            if isinstance(entry, (list, tuple)) and entry:
                return [str(part) for part in entry]
            if isinstance(entry, str) and entry.strip():
                return entry.split()
    return []


def dedupe_key(item: Dict[str, Any]) -> str:
    """The indexing key, in the six shapes the ladder is allowed to use.

    Derived from the item's own fields when the item does not carry one, so a
    hand-written queue entry still participates in dedupe instead of silently
    duplicating a generated one.
    """
    if not isinstance(item, dict):
        return ""
    explicit = str(item.get("dedupe_key") or "").strip()
    if explicit:
        return explicit
    probe_id = str(item.get("probe_id") or "").strip()
    if probe_id:
        return f"probe:{probe_id}"
    regression = str(item.get("regression_of") or "").strip()
    if regression:
        return f"regression:{regression}"
    nodeid = str(item.get("nodeid") or "").strip()
    if nodeid:
        return "pytest:" + nodeid.replace("\\", "/")
    check = str(item.get("scan_check") or "").strip()
    scan_path = str(item.get("scan_path") or "").strip().replace("\\", "/")
    if check and scan_path:
        return f"scan:{check}:{scan_path}"
    backlog_id = str(item.get("backlog_id") or "").strip()
    if backlog_id:
        argv = _first_argv(item)
        digest = hashlib.sha256(" ".join(argv).encode("utf-8")).hexdigest()[:8]
        return f"backlog:{backlog_id}:{digest}"
    gap_id = str(item.get("gap_id") or "").strip()
    if gap_id:
        return f"intel:{gap_id}"
    return ""


def _find(queue: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    if not key:
        return None
    for item in (queue or {}).get("items") or []:
        if isinstance(item, dict) and dedupe_key(item) == key:
            return item
    return None


def _gate_present(queue: Dict[str, Any]) -> bool:
    return any(isinstance(item, dict) and str(item.get("id")) == GATE_DEP
               for item in (queue or {}).get("items") or [])


def _declared_dirty(queue: Dict[str, Any]) -> set:
    """Paths a candidate must not touch, as the queue itself already records them.

    Two sources, both written by the launcher's dispatch path rather than
    recomputed here: ``queue["dirty_targets"]`` (the snapshot an operator or the
    launcher records) and any item whose ``blocked_reason`` starts with
    ``targets_dirty:``. Re-deriving this from ``git status`` inside discovery
    would be a second, slower copy of a decision the launcher already made, and
    the two copies would disagree exactly when it matters.
    """
    dirty = set()
    for entry in (queue or {}).get("dirty_targets") or []:
        text = str(entry or "").replace("\\", "/").strip()
        if text:
            dirty.add(text)
    for item in (queue or {}).get("items") or []:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("blocked_reason") or "")
        if not reason.startswith("targets_dirty:"):
            continue
        for part in reason.split(":", 1)[1].split(","):
            text = part.strip().replace("\\", "/")
            if text:
                dirty.add(text)
    return dirty


def _targets_dirty(queue: Dict[str, Any], paths: Sequence[str]) -> bool:
    dirty = _declared_dirty(queue)
    return any(str(path or "").replace("\\", "/").strip() in dirty for path in paths)


# ----------------------------------------------------------------------- budget
def _tokens_today() -> int:
    try:
        return int(_runner()._tokens_today())
    except Exception:  # noqa: BLE001 - an unreadable ledger must not block a cycle
        return 0


def _token_cap() -> int:
    try:
        return int(_runner().TOKEN_CAP_PER_DAY)
    except Exception:  # noqa: BLE001
        return int(os.environ.get("TY_TOKEN_CAP_PER_DAY", "3000000"))


def _emitted_rows(key: str = "") -> List[Dict[str, Any]]:
    path = Path(EMITTED)
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    rows: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict):
            continue
        if key and str(row.get("key") or "") != key:
            continue
        rows.append(row)
    return rows


def _emitted_today(now: Any) -> int:
    day = _today(now)
    return sum(1 for row in _emitted_rows()
               if str(row.get("at") or "")[:10] == day
               and str(row.get("event") or "") in ("emit", "reemit"))


# ------------------------------------------------------------------------- lock
def _pid_alive(pid: Any) -> bool:
    try:
        return bool(_runner()._pid_alive(int(pid)))
    except Exception:  # noqa: BLE001 - unknown means "do not assume alive"
        return False


def _lock() -> Dict[str, Any]:
    holder = _read(LOCK, None)
    pid = int(holder.get("pid") or 0) if isinstance(holder, dict) else 0
    if pid and pid != os.getpid() and _pid_alive(pid):
        return {"ok": False, "detail": f"pid {pid} is already generating work"}
    _plain_write(LOCK, {"pid": os.getpid(), "at": _now_iso()})
    return {"ok": True, "pid": os.getpid()}


def _unlock(lock: Dict[str, Any]) -> None:
    holder = _read(LOCK, None)
    if not isinstance(holder, dict):
        return
    if int(holder.get("pid") or 0) != int((lock or {}).get("pid") or 0):
        return
    try:
        Path(LOCK).unlink()
    except OSError:
        pass


# ------------------------------------------------------------------- reverts
def _revert_streak(item: Dict[str, Any]) -> int:
    """How many times in a row has this item been reverted?

    A13 owns the rejection ledger. The item's own record is read as well as the
    ledger, because a ledger with no rows for an item cannot contradict an item
    that records three reverts: an empty ledger is *not* evidence of a clean
    history. The larger of the two is the honest count, so a queue that predates
    A13 still escalates instead of being retried forever.
    """
    ledger = 0
    evaluator = _import("tys_evaluator")
    streak = getattr(evaluator, "rejection_streak", None) if evaluator else None
    if callable(streak):
        signature = str(item.get("attempt_signature") or item.get("dedupe_key") or "")
        try:
            value = streak(str(item.get("id") or ""), signature)
        except TypeError:
            try:
                value = streak(str(item.get("id") or ""))
            except Exception:  # noqa: BLE001
                value = None
        except Exception:  # noqa: BLE001
            value = None
        if value is not None:
            try:
                ledger = max(0, int(value))
            except (TypeError, ValueError):
                ledger = 0
    recorded = 0
    if str(item.get("last_result") or "") == "reverted":
        try:
            recorded = max(0, int(item.get("attempts") or 0))
        except (TypeError, ValueError):
            recorded = 0
    return max(ledger, recorded)


# -------------------------------------------------------------------- dispatch
def _dispatchable(item: Dict[str, Any]) -> bool:
    """runnable() *and* validate_contract() - the launcher's definition, asked of it."""
    if not isinstance(item, dict):
        return False
    try:
        ok, _why = _launcher().runnable(item)
        if not ok:
            return False
        return list(_runner().validate_contract(item)) == []
    except Exception:  # noqa: BLE001 - a broken import must not inflate the count
        return bool(item.get("write_paths")) and bool(item.get("acceptance_commands"))


def needs_forward(queue: Optional[Dict[str, Any]] = None) -> int:
    """How much dispatchable work is in flight? The low-water mark A13 tops up from."""
    data = queue if isinstance(queue, dict) else _read(QUEUE, None)
    if not isinstance(data, dict):
        return 0
    return sum(1 for item in (data.get("items") or [])
               if isinstance(item, dict)
               and str(item.get("status")) in ACTIVE
               and _dispatchable(item))


# ------------------------------------------------------------------- execution
def _exec(argv: Sequence[str], *, probe_runner: Callable[..., Any],
          timeout_s: Any = None, cwd: Any = None) -> Dict[str, Any]:
    cmd = [str(part) for part in argv]
    started = time.time()
    try:
        proc = probe_runner(cmd, cwd=str(cwd or ROOT),
                            timeout=float(timeout_s or DEFAULT_PROBE_TIMEOUT_S),
                            capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        return {"exit": 124, "output": "timed out", "proc": None,
                "seconds": round(time.time() - started, 2)}
    except OSError as exc:
        return {"exit": 127, "output": f"could not be started: {exc}", "proc": None,
                "seconds": round(time.time() - started, 2)}
    raw = getattr(proc, "returncode", 1)
    code = int(raw) if isinstance(raw, int) else 1
    output = (getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or "")
    return {"exit": code, "output": output, "proc": proc,
            "seconds": round(time.time() - started, 2)}


class _Replay:
    """A runner that answers with bytes already captured.

    The scope deriver insists on seeing a failing run. The probe has just failed
    for us, so replaying that exact output is the same evidence without running
    the same check twice.
    """

    def __init__(self, argv: Sequence[str], result: Dict[str, Any]) -> None:
        self.argv = [str(part) for part in argv]
        self.code = int((result or {}).get("exit") or 0)
        self.output = str((result or {}).get("output") or "")

    def __call__(self, cmd, cwd=None, timeout=None, capture_output=True,
                 text=True, **kw) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(list(cmd), self.code, self.output, "")


def _command_refusal(argv: Sequence[str]) -> Optional[str]:
    module = _import("continuous_loop")
    check = getattr(module, "check_command", None) if module else None
    if not callable(check):
        return None
    try:
        return check([str(part) for part in argv])
    except Exception:  # noqa: BLE001
        return None


def _commit_refusals(paths: Sequence[str]) -> List[str]:
    module = _import("continuous_loop")
    validate = getattr(module, "validate_commit_paths", None) if module else None
    if not callable(validate):
        return []
    try:
        _allowed, refused = validate([str(p) for p in paths])
        return list(refused)
    except Exception:  # noqa: BLE001
        return []


def _contract_problems(item: Dict[str, Any]) -> List[str]:
    try:
        return list(_runner().validate_contract(item))
    except Exception:  # noqa: BLE001
        problems: List[str] = []
        if not item.get("write_paths"):
            problems.append("no write_paths declared")
        if not item.get("acceptance_commands"):
            problems.append("no acceptance_commands declared")
        return problems


def _derive(item_id: str, argv: Sequence[str], result: Dict[str, Any]) -> Dict[str, Any]:
    author = _import("tys_author")
    derive = getattr(author, "derive", None) if author else None
    if not callable(derive):
        return {"ok": False, "reason": "author_unavailable"}
    try:
        return derive(item_id=str(item_id), acceptance_commands=[list(argv)],
                      run=_Replay(argv, result), repo=ROOT)
    except Exception as exc:  # noqa: BLE001 - a deriver crash is a refusal, not a pass
        return {"ok": False, "reason": f"derive_failed:{exc.__class__.__name__}"}


# ------------------------------------------------------------------- discovery
def _probe_candidate(spec: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(spec.get("tier") or "T5").upper()
    return {
        "tier": tier,
        "kind": "probe",
        "dedupe_key": f"probe:{spec.get('id')}",
        "title": f"Probe red: {spec.get('id')}",
        "source": "tools/tys_probes.py",
        "fixable_by": str(spec.get("fixable_by") or "worker"),
        "why": spec.get("why") or "",
        "payload": {"spec": spec, "result": result},
    }


def _nodeid(commands: Sequence[Any]) -> str:
    """The pytest node id, with '/' separators so a Windows path cannot fork a key."""
    fallback = ""
    for cmd in commands or []:
        parts = cmd if isinstance(cmd, (list, tuple)) else str(cmd or "").split()
        for part in parts:
            if "::" in str(part):
                return str(part).replace("\\", "/")
        for part in parts:
            text = str(part)
            if fallback == "" and text.endswith(".py") and ("/" in text or "\\" in text):
                fallback = text.replace("\\", "/")
    return fallback


def _regression_candidates() -> List[Dict[str, Any]]:
    """Recorded regressions: a shipped item whose check now fails.

    The record is written by the consumer of ``check_regression.py --junit``
    (the regression-baseline probe), because a generator that re-runs every done
    item's check on every call would spend the cycle budget measuring itself.
    """
    data = _read(REGRESSIONS, None)
    rows = data.get("items") if isinstance(data, dict) else None
    candidates: List[Dict[str, Any]] = []
    if not isinstance(rows, list):
        return candidates
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = str(row.get("done_item_id") or "").strip()
        argv = [str(part) for part in (row.get("argv") or [])]
        if not item_id or not argv:
            continue
        candidates.append({
            "tier": "T0",
            "kind": "regression",
            "dedupe_key": f"regression:{item_id}",
            "title": f"Regression: {item_id} shipped and its check is red again",
            "source": str(REGRESSIONS),
            "first_seen": row.get("first_seen"),
            "payload": {"row": row, "argv": argv,
                        "result": {"exit": 1, "output": str(row.get("output") or "")}},
        })
    return candidates


def _discover_incidents(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    probes = _probes()
    table = probes.probe_table() if probes else []
    incident = [spec for spec in table if str(spec.get("severity") or "") == "incident"]
    candidates: List[Dict[str, Any]] = []
    ran = 0
    for spec in incident:
        result = _exec(spec["argv"], probe_runner=probe_runner,
                       timeout_s=spec.get("timeout_s"))
        ran += 1
        if result["exit"] != 0:
            candidates.append(_probe_candidate(spec, result))
    regressions = _regression_candidates()
    candidates.extend(regressions)
    has_regression_source = isinstance(_read(REGRESSIONS, None), dict)
    if not incident and not has_regression_source:
        return {"state": "no_source", "candidates": [],
                "detail": "no incident probe and no regression source"}
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": (f"{ran} incident probe(s), {len(regressions)} recorded regression(s), "
                       f"{len(candidates)} candidate(s)")}


def _discover_red_checks(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    probes = _probes()
    table = probes.probe_table() if probes else []
    candidates: List[Dict[str, Any]] = []
    ran = 0
    for spec in table:
        if str(spec.get("tier") or "") != "T1":
            continue
        result = _exec(spec["argv"], probe_runner=probe_runner,
                       timeout_s=spec.get("timeout_s"))
        ran += 1
        if result["exit"] != 0:
            candidates.append(_probe_candidate(spec, result))

    data = _read(PROPOSALS, None)
    proposals = data.get("proposals") if isinstance(data, dict) else None
    if isinstance(proposals, list):
        for proposal in proposals:
            if not isinstance(proposal, dict):
                continue
            if str(proposal.get("status") or "").lower() in ("done", "resolved", "dropped"):
                continue
            commands = [cmd for cmd in (proposal.get("acceptance_commands") or [])
                        if isinstance(cmd, (list, tuple)) and cmd]
            nodeid = _nodeid(commands)
            if not nodeid:
                continue
            candidates.append({
                "tier": "T1",
                "kind": "proposal",
                "dedupe_key": f"pytest:{nodeid}",
                "title": f"Red check: {proposal.get('name') or nodeid}"[:200],
                "source": str(PROPOSALS),
                "first_seen": proposal.get("first_seen") or proposal.get("created_at"),
                "payload": {"proposal": proposal,
                            "argv": [str(part) for part in commands[0]]},
            })
        source = True
    else:
        source = False
    if not ran and not source:
        return {"state": "no_source", "candidates": [],
                "detail": f"{PROPOSALS} absent and no T1 probe"}
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": (f"{ran} red-check probe(s), "
                       f"{len(proposals) if isinstance(proposals, list) else 0} proposal(s), "
                       f"{len(candidates)} candidate(s)")}


def _discover_scan(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    result = _exec(SCAN_ARGV, probe_runner=probe_runner, timeout_s=600)
    if result["exit"] != 0:
        return {"state": "error", "candidates": [],
                "detail": f"the scan exited {result['exit']}: {result['output'][-300:]}"}
    report = _json_from(result["output"])
    if not isinstance(report, dict):
        return {"state": "error", "candidates": [],
                "detail": "the scan printed no JSON report"}
    findings = [f for f in (report.get("findings") or []) if isinstance(f, dict)]
    total = report.get("total")
    total = int(total) if isinstance(total, int) else len(findings)
    scanned = report.get("files_scanned")
    scanned = int(scanned) if isinstance(scanned, int) else None
    if total == 0 and scanned == 0:
        return {"state": "vacuous", "candidates": [{
            "tier": "T5",
            "kind": "vacuity",
            "dedupe_key": "probe:discovery-vacuous",
            "title": "A scanner that saw no files reported zero findings",
            "source": "tools/production_readiness_scan.py",
            "payload": {"report": report},
        }], "detail": "0 findings from 0 files scanned - the scanner saw nothing"}
    candidates: List[Dict[str, Any]] = []
    for finding in findings:
        check = str(finding.get("check") or "unknown")
        path = str(finding.get("file") or finding.get("path") or "").replace("\\", "/")
        if not path:
            continue
        candidates.append({
            "tier": "T2",
            "kind": "scan",
            "dedupe_key": f"scan:{check}:{path}",
            "title": f"Scan finding: {check} at {path}"[:200],
            "source": "tools/production_readiness_scan.py",
            "payload": {"finding": finding},
        })
    detail = f"{scanned if scanned is not None else 'unknown'} files scanned, {total} finding(s)"
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": detail}


def _improvement_problems(item_id: str) -> List[str]:
    """The backlog's own validator, quoted verbatim - never a second opinion."""
    data = _read(IMPROVEMENTS, None)
    if not isinstance(data, dict):
        return [f"{IMPROVEMENTS} is absent or unreadable"]
    module = _import("improvement_backlog")
    check = getattr(module, "check", None) if module else None
    if not callable(check):
        return []
    try:
        problems = list(check(data))
    except Exception as exc:  # noqa: BLE001
        return [f"improvement_backlog.check failed: {exc}"]
    return [str(p) for p in problems if str(p).startswith(str(item_id))]


def _discover_backlog(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    data = _read(IMPROVEMENTS, None)
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return {"state": "no_source", "candidates": [],
                "detail": f"{IMPROVEMENTS} is absent or unreadable"}
    ready = [i for i in items if isinstance(i, dict) and str(i.get("status")) == "ready"]
    candidates: List[Dict[str, Any]] = []
    for item in ready:
        item_id = str(item.get("id") or "").strip()
        if not item_id:
            continue
        argv = _first_argv(item)
        digest = hashlib.sha256(" ".join(argv).encode("utf-8")).hexdigest()[:8]
        candidates.append({
            "tier": "T3",
            "kind": "backlog",
            "dedupe_key": f"backlog:{item_id}:{digest}",
            "title": str(item.get("title") or item_id)[:200],
            "source": str(IMPROVEMENTS),
            "first_seen": item.get("created_at"),
            "payload": {"item": item},
        })
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": f"{len(ready)} ready of {len(items)} backlog item(s)"}


def _discover_intel(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    data = _read(GAPS, None)
    if not isinstance(data, dict):
        return {"state": "no_source", "candidates": [],
                "detail": f"{GAPS} is absent (A21 owns the intel plane)"}
    rows = data.get("gaps") if isinstance(data.get("gaps"), list) else data.get("items")
    rows = rows if isinstance(rows, list) else []
    candidates: List[Dict[str, Any]] = []
    for gap in rows:
        if not isinstance(gap, dict):
            continue
        argv = gap.get("argv") if isinstance(gap.get("argv"), list) else gap.get("check")
        argv = [str(part) for part in (argv or [])]
        gap_id = str(gap.get("id") or "").strip()
        if not gap_id or not argv:
            continue
        candidates.append({
            "tier": "T4",
            "kind": "intel",
            "dedupe_key": f"intel:{gap_id}",
            "title": str(gap.get("title") or gap_id)[:200],
            "source": str(GAPS),
            "first_seen": gap.get("first_seen"),
            "payload": {"gap": gap, "argv": argv},
        })
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": f"{len(candidates)} falsifiable gap(s) of {len(rows)}"}


def _discover_maintenance(*, probe_runner: Callable[..., Any], now: datetime) -> Dict[str, Any]:
    probes = _probes()
    table = probes.probe_table() if probes else []
    maintenance = [spec for spec in table if str(spec.get("tier") or "") == "T5"]
    candidates: List[Dict[str, Any]] = []
    ran = 0
    for spec in maintenance:
        result = _exec(spec["argv"], probe_runner=probe_runner,
                       timeout_s=spec.get("timeout_s"))
        ran += 1
        if result["exit"] != 0:
            candidates.append(_probe_candidate(spec, result))
    if not maintenance:
        return {"state": "no_source", "candidates": [], "detail": "the probe table is empty"}
    return {"state": "candidates" if candidates else "green", "candidates": candidates,
            "detail": f"{ran} maintenance probe(s), {len(candidates)} candidate(s)"}


def discover(tier: str, *, probe_runner: Callable[..., Any] = subprocess.run,
             now: Any = None) -> Dict[str, Any]:
    """What does this tier's surface report right now?

    ``{state, candidates, detail}`` where ``state`` is one of ``candidates``,
    ``green``, ``vacuous``, ``no_source``, ``error`` or ``unknown_tier``.
    ``no_source`` is the honest answer for a plane that is not built yet, and it
    carries zero candidates rather than an invented one.
    """
    name = str(tier or "").upper()
    current = _as_dt(now)
    if name == "T0":
        return _discover_incidents(probe_runner=probe_runner, now=current)
    if name == "T1":
        return _discover_red_checks(probe_runner=probe_runner, now=current)
    if name == "T2":
        return _discover_scan(probe_runner=probe_runner, now=current)
    if name == "T3":
        return _discover_backlog(probe_runner=probe_runner, now=current)
    if name == "T4":
        return _discover_intel(probe_runner=probe_runner, now=current)
    if name == "T5":
        return _discover_maintenance(probe_runner=probe_runner, now=current)
    return {"state": "unknown_tier", "candidates": [],
            "detail": f"unknown tier {tier!r}; choose from {', '.join(TIERS)}"}


# ------------------------------------------------------------- build a queue item
def _needs_author(doc: Dict[str, Any], reason: str) -> Dict[str, Any]:
    doc["status"] = "needs_author"
    doc["needs_author"] = str(reason)[:600]
    doc.pop("needs_owner", None)
    return doc


def _needs_owner(doc: Dict[str, Any], reason: str) -> Dict[str, Any]:
    doc["status"] = "needs_owner"
    doc["needs_owner"] = str(reason)[:600]
    doc["needs_you"] = f"- {doc.get('title')}: {reason} (source: {doc.get('source')})"
    doc.pop("needs_author", None)
    return doc


def _scope_item(doc: Dict[str, Any], argv: Sequence[str],
                result: Dict[str, Any]) -> Dict[str, Any]:
    """Turn a failing check into a dispatchable contract - or say what is missing."""
    argv = [str(part) for part in argv]
    refusal = _command_refusal(argv)
    if refusal:
        return _needs_author(doc, f"command refused: {refusal}")
    derived = _derive(doc["id"], argv, result)
    if not derived.get("ok"):
        reason = str(derived.get("reason") or "unknown")
        return _needs_author(doc, f"scope not derived ({reason})")
    paths = [str(p).replace("\\", "/").strip() for p in (derived.get("write_paths") or [])
             if str(p).strip()]
    if not paths:
        return _needs_author(doc, "scope not derived (no write_paths)")
    refused = _commit_refusals(paths)
    if refused:
        return _needs_author(doc, "write scope outside the commit allowlist: "
                             + "; ".join(refused))
    doc.update({
        "write_paths": paths,
        "acceptance_commands": [list(argv)],
        "objective": doc.get("objective") or doc.get("title") or "",
        "scope_derivation": str(derived.get("artifact") or ""),
        "check_sha256": derived.get("check_sha256"),
        "forbidden_paths": list(derived.get("forbidden_paths") or []),
    })
    problems = _contract_problems(doc)
    if problems:
        return _needs_author(doc, "contract not dispatchable: " + "; ".join(problems))
    return doc


def _scan_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    finding = doc.get("_finding") or {}
    check = str(finding.get("check") or "unknown")
    path = str(finding.get("file") or finding.get("path") or "").replace("\\", "/")
    line = finding.get("line")
    return _needs_author(
        doc, f"name the check that proves {check} at {path}:{line}")


def _backlog_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    item = doc.get("_backlog") or {}
    item_id = str(item.get("id") or doc["id"])
    problems = _improvement_problems(item_id)
    if problems:
        return _needs_author(doc, "the backlog refuses this item: " + "; ".join(problems))
    paths = [str(p).replace("\\", "/").strip() for p in (item.get("write_paths") or [])
             if str(p).strip()]
    checks = [cmd.get("cmd") for cmd in (item.get("checks") or [])
              if isinstance(cmd, dict) and isinstance(cmd.get("cmd"), (list, tuple))]
    if not paths:
        return _needs_author(doc, "the item names no write_paths")
    if not checks:
        return _needs_author(doc, "the item names no checks")
    for argv in checks:
        refusal = _command_refusal([str(part) for part in argv])
        if refusal:
            return _needs_author(doc, f"command refused: {refusal}")
    doc.update({
        "write_paths": paths,
        "acceptance_commands": [[str(part) for part in argv] for argv in checks],
        "objective": str(item.get("problem") or item.get("title") or ""),
        "verification": str(item.get("verification") or ""),
    })
    problems = _contract_problems(doc)
    if problems:
        return _needs_author(doc, "contract not dispatchable: " + "; ".join(problems))
    return doc


def _build_item(cand: Dict[str, Any], queue: Dict[str, Any], now: Any, *,
                probe_runner: Callable[..., Any] = subprocess.run,
                force_author: str = "") -> Optional[Dict[str, Any]]:
    """The queue item for a candidate, in the state its own evidence supports."""
    tier = str(cand.get("tier") or "T5").upper()
    key = str(cand.get("dedupe_key") or "")
    if not key:
        return None
    doc: Dict[str, Any] = {
        "id": item_id_for(key),
        "kind": "automation",
        "tier": tier,
        "generated_by": MARK,
        "dedupe_key": key,
        "source": str(cand.get("source") or ""),
        "title": str(cand.get("title") or key)[:200],
        "status": "pending",
        "priority": priority_for(tier, _days_since(cand.get("first_seen"), now)),
        "attempts": 0,
        "first_seen": _now_iso(cand.get("first_seen") or now),
        "generated_at": _now_iso(now),
        "depends_on": [GATE_DEP] if tier in PRODUCT_TIERS else [],
        "objective": str(cand.get("title") or key),
    }
    kind = str(cand.get("kind") or "")
    payload = cand.get("payload") or {}
    if force_author:
        doc["_forced_author"] = force_author

    if kind == "probe":
        spec = payload.get("spec") or {}
        result = payload.get("result") or {}
        doc["probe_id"] = str(spec.get("id") or "")
        doc["fixable_by"] = str(spec.get("fixable_by") or "worker")
        doc["why"] = str(spec.get("why") or "")
        if doc["fixable_by"] == "owner":
            tail = str(result.get("output") or "").strip()[-200:]
            detail = (f"owner must clear this: {doc['why']} (probe exit "
                      f"{result.get('exit')}){': ' + tail if tail else ''}")
            return _needs_owner(doc, detail)
        doc = _scope_item(doc, spec.get("argv") or [], result)
    elif kind == "regression":
        doc["regression_of"] = str((payload.get("row") or {}).get("done_item_id") or "")
        doc = _scope_item(doc, payload.get("argv") or [], payload.get("result") or {})
    elif kind == "proposal":
        doc["nodeid"] = str(cand.get("dedupe_key") or "").split("pytest:", 1)[-1]
        doc["fixable_by"] = "worker"
        argv = [str(part) for part in (payload.get("argv") or [])]
        doc = _scope_item(doc, argv, _exec(argv, probe_runner=probe_runner, timeout_s=600))
    elif kind == "intel":
        doc["gap_id"] = str((payload.get("gap") or {}).get("id") or "")
        argv = [str(part) for part in (payload.get("argv") or [])]
        doc = _scope_item(doc, argv, _exec(argv, probe_runner=probe_runner, timeout_s=600))
    elif kind == "scan":
        doc["_finding"] = payload.get("finding") or {}
        finding = doc["_finding"]
        doc["scan_check"] = str(finding.get("check") or "unknown")
        doc["scan_path"] = str(finding.get("file") or finding.get("path") or "").replace("\\", "/")
        doc["scan_line"] = finding.get("line")
        doc = _scan_item(doc)
    elif kind == "backlog":
        doc["_backlog"] = payload.get("item") or {}
        doc["backlog_id"] = str(doc["_backlog"].get("id") or "")
        doc = _backlog_item(doc)
    elif kind == "vacuity":
        doc["fixable_by"] = "worker"
        doc = _needs_author(
            doc, "a scanner that saw 0 files reported 0 findings; fix its file discovery "
                 "or say which paths it should have seen")
    else:
        return None

    doc.pop("_finding", None)
    doc.pop("_backlog", None)
    forced = doc.pop("_forced_author", "")
    if forced:
        return _needs_author(doc, forced)
    return doc


# ------------------------------------------------------------------ decide + apply
def _candidate_reason(cand: Dict[str, Any]) -> str:
    payload = cand.get("payload") or {}
    spec = payload.get("spec") or {}
    if spec:
        return f"probe {spec.get('id')} is still red: {spec.get('why') or ''}".strip()
    return f"{cand.get('kind')} surface still reports {cand.get('dedupe_key')}"


def _decide(cand: Dict[str, Any], queue: Dict[str, Any],
            now: Any = None) -> Dict[str, Any]:
    """What should happen to a candidate whose key may already be in the queue?"""
    key = str(cand.get("dedupe_key") or "")
    found = _find(queue, key)
    if found is None:
        rows = [row for row in _emitted_rows(key)
                if str(row.get("event") or "") in ("emit", "reemit")]
        if not rows:
            return {"action": "new", "why": "generated"}
        if any(str(row.get("event")) == "reemit" for row in rows):
            return {"action": "deleted_twice", "why": "deleted_twice",
                    "reason": "deleted twice"}
        return {"action": "reemit", "why": "reemitted"}

    status = str(found.get("status") or "")
    if status in ("needs_author", "needs_owner"):
        return {"action": "promote", "why": "promoted", "reason": _candidate_reason(cand)}
    streak = _revert_streak(found)
    if streak >= MAX_REVERTS:
        return {"action": "escalate", "why": "reverts",
                "reason": (f"{streak} consecutive reverts with no ledger entry; "
                           "this is a wall, not a task")}
    if status in ACTIVE:
        return {"action": "skip", "why": "exists"}
    if status == "done":
        reopens = int(found.get("reopens") or 0)
        if reopens >= MAX_REOPENS:
            return {"action": "escalate", "why": "reopen_capped",
                    "reason": (f"reopened {reopens} times and the surface still reports it")}
        return {"action": "reopen", "why": "reopened"}
    if status in ("deleted", "dropped", "cancelled"):
        if any(str(row.get("event")) == "reemit" for row in _emitted_rows(key)):
            return {"action": "deleted_twice", "why": "deleted_twice",
                    "reason": "deleted twice"}
        return {"action": "reemit", "why": "reemitted"}
    return {"action": "skip", "why": "exists"}


def _apply_in_place(queue_file: Path, cand: Dict[str, Any],
                    decision: Dict[str, Any], now: Any) -> Dict[str, Any]:
    """Promote / reopen / escalate without touching the id or the attempt count."""
    data = _read(queue_file, None)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"ok": False, "reason": "queue_unreadable"}
    target = _find(data, str(cand.get("dedupe_key") or ""))
    if target is None:
        return {"ok": False, "reason": "item_gone"}
    before = json.loads(json.dumps(data))
    action = str(decision.get("action") or "")
    if action == "promote":
        reason = str(decision.get("reason") or "")
        if str(target.get("status")) == "needs_owner":
            target["needs_owner"] = reason or target.get("needs_owner") or ""
        elif target.get("parked_signature"):
            # A13 parked this item at the strike limit. Its reason
            # ("rejection_cap:<gate> x3") is the escalation a human must read, so a
            # generator note never overwrites it, and the signature is left alone so
            # the park survives - only a changed contract revives it.
            pass
        else:
            target["needs_author"] = reason or target.get("needs_author") or ""
        target["priority"] = priority_for(str(cand.get("tier") or "T5").upper(),
                                          _days_since(target.get("first_seen")
                                                      or cand.get("first_seen"), now))
        target["last_generated_at"] = _now_iso(now)
    elif action == "reopen":
        target["status"] = "pending"
        target["reopens"] = int(target.get("reopens") or 0) + 1
        target["defer_until_cycle"] = 0
        target["reopened_at"] = _now_iso(now)
        target["last_generated_at"] = _now_iso(now)
    elif action == "escalate":
        target["status"] = "needs_author"
        target["needs_author"] = str(decision.get("reason") or "escalated")
        target["last_generated_at"] = _now_iso(now)
    data["updated_at"] = _now_iso(now)
    _write_queue(queue_file, data)

    written = _read(queue_file, None)
    reread = _find(written, str(cand.get("dedupe_key") or "")) if isinstance(written, dict) else None
    problems: List[str] = []
    if not isinstance(written, dict):
        problems.append("the queue is unreadable after the write")
    elif reread is None:
        problems.append("the item disappeared on readback")
    else:
        if str(reread.get("id")) != str(target.get("id")):
            problems.append("the item id changed on readback")
        if str(reread.get("status")) != str(target.get("status")):
            problems.append("the status did not survive the write")
        if int(reread.get("attempts") or 0) != int(target.get("attempts") or 0):
            problems.append("the attempt count changed")
    if problems:
        _plain_write(queue_file, before)
        return {"ok": False, "reason": "readback_tampered", "problems": problems}
    return {"ok": True, "item": reread, "queue_data": written}


# ------------------------------------------------------------------- write path
def _write_needs_you(line: str) -> None:
    text = str(line or "").strip()
    if not text:
        return
    target = Path(NEEDS_YOU)
    existing = ""
    try:
        if target.is_file():
            existing = target.read_text(encoding="utf-8")
    except OSError:
        existing = ""
    if text in existing:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    prefix = "" if existing.endswith("\n") or not existing else "\n"
    with target.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}{text}\n")


def append_item(queue: Dict[str, Any], item: Dict[str, Any], *,
                queue_path: Any = None) -> Dict[str, Any]:
    """Append one item atomically and prove it landed.

    The write is ``tys_runner._write`` so the queue keeps exactly one writer's
    shape. The item is then read back from disk: if the file no longer carries
    what was written, the whole queue is restored to the bytes read before the
    append. A queue that does not survive its own readback is a tampered queue,
    and a tampered queue is never left in place.

    ``queue`` is the caller's view: it is cross-checked first so an obvious
    duplicate costs no write, but the file on disk is authoritative, because
    another writer may have appended while this call was deciding.
    """
    path = Path(queue_path or QUEUE)
    key = dedupe_key(item)
    if not key:
        return {"ok": False, "reason": "item_has_no_key", "queue": str(path)}
    if isinstance(queue, dict) and _find(queue, key) is not None:
        return {"ok": False, "reason": "duplicate", "id": _find(queue, key).get("id"),
                "queue": str(path)}
    data = _read(path, None)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        return {"ok": False, "reason": "queue_unreadable", "queue": str(path)}
    existing = _find(data, key)
    if existing is not None:
        return {"ok": False, "reason": "duplicate", "id": existing.get("id"),
                "queue": str(path)}
    before = json.loads(json.dumps(data))
    doc = dict(data)
    doc["items"] = list(data["items"]) + [item]
    doc["updated_at"] = _now_iso()
    _write_queue(path, doc)

    written = _read(path, None)
    reread = _find(written, key) if isinstance(written, dict) else None
    problems: List[str] = []
    if not isinstance(written, dict):
        problems.append("the queue is unreadable after the write")
    elif reread is None:
        problems.append("the new item is not in the queue on readback")
    else:
        for field in ("id", "dedupe_key", "priority", "status"):
            if reread.get(field) != item.get(field):
                problems.append(f"{field} readback {reread.get(field)!r} != {item.get(field)!r}")
    if problems:
        _plain_write(path, before)
        return {"ok": False, "reason": "readback_tampered", "problems": problems,
                "queue": str(path)}

    event = "emit"
    if str(item.get("status")) == "needs_owner":
        event = "emit-owner"
    elif item.get("reemitted"):
        event = "reemit"
    _append_jsonl(EMITTED, {"at": _now_iso(), "event": event, "key": key,
                            "id": item.get("id"), "tier": item.get("tier")})
    if item.get("needs_you"):
        _write_needs_you(str(item["needs_you"]))
    return {"ok": True, "queue": str(path), "id": item.get("id"),
            "item": reread, "queue_data": written}


# ---------------------------------------------------------------------- generate
def _tier_summary(records: Dict[str, Any]) -> str:
    parts = []
    for name in TIERS:
        record = records.get(name)
        if not record:
            continue
        parts.append(f"{name} {record.get('state')} "
                     f"({record.get('candidates')} candidate(s)): {record.get('detail')}")
    return " | ".join(parts)


def _generate_locked(*, queue_file: Path, tier: Optional[str], max_items: int,
                     dry_run: bool, probe_runner: Callable[..., Any],
                     now: datetime, out: Dict[str, Any]) -> Dict[str, Any]:
    queue = _read(queue_file, None)
    if not isinstance(queue, dict) or not isinstance(queue.get("items"), list):
        out.update(reason="queue_unreadable",
                   detail=f"{queue_file} is not an autonomy queue")
        return out

    spent, cap = _tokens_today(), _token_cap()
    if spent >= int(cap * CAP_FRACTION):
        out.update(reason="deferred_budget", cause="token_cap",
                   detail=(f"{spent} of {cap} tokens spent today; generation defers "
                           "rather than feeding a capped loop"))
        return out

    active = sum(1 for item in queue["items"]
                 if isinstance(item, dict)
                 and str(item.get("generated_by")) == MARK
                 and str(item.get("status")) in ACTIVE)
    emitted = _emitted_today(now)
    if active >= MAX_GENERATED_ACTIVE or emitted >= MAX_GENERATED_PER_DAY:
        out.update(reason="supply_capped",
                   detail=(f"{active}/{MAX_GENERATED_ACTIVE} generated items active, "
                           f"{emitted}/{MAX_GENERATED_PER_DAY} emitted today"))
        return out

    wanted = [str(tier).upper()] if tier else list(TIERS)
    unknown = [name for name in wanted if name not in BANDS]
    if unknown:
        out.update(reason="unknown_tier",
                   detail=f"unknown tier(s) {', '.join(unknown)}; choose from {', '.join(TIERS)}")
        return out

    records = out["tiers"]
    added = out["added"]
    duplicates = 0
    vacuous: List[Dict[str, Any]] = []
    limit = max(1, int(max_items or 1))

    for name in wanted:
        found = discover(name, probe_runner=probe_runner, now=now)
        records[name] = {"state": found.get("state"),
                         "candidates": len(found.get("candidates") or []),
                         "detail": found.get("detail") or ""}
        candidates = list(found.get("candidates") or [])
        if name == "T2" and found.get("state") == "vacuous":
            vacuous = [c for c in candidates if c.get("kind") == "vacuity"]
        candidates = [c for c in candidates if c.get("kind") != "vacuity"]
        if name == "T5":
            candidates = vacuous + candidates

        for cand in candidates:
            decision = _decide(cand, queue, now)
            if decision["action"] == "skip":
                if decision.get("why") == "exists":
                    duplicates += 1
                continue

            if decision["action"] in ("promote", "reopen", "escalate"):
                if dry_run:
                    existing = _find(queue, str(cand.get("dedupe_key") or "")) or {}
                    added.append({"id": existing.get("id"), "tier": name,
                                  "action": decision["action"], "dry_run": True})
                    out.update(ok=True, reason=decision["why"], tier=name,
                               detail=str(decision.get("reason") or ""))
                    return out
                applied = _apply_in_place(queue_file, cand, decision, now)
                if not applied.get("ok"):
                    records[name]["applied"] = applied.get("reason")
                    continue
                queue = applied["queue_data"]
                added.append({"id": (applied.get("item") or {}).get("id"),
                              "tier": name, "action": decision["action"]})
                out.update(ok=True, reason=decision["why"], tier=name,
                           detail=str(decision.get("reason") or ""))
                return out

            item = _build_item(cand, queue, now, probe_runner=probe_runner,
                               force_author=str(decision.get("reason") or "")
                               if decision["action"] == "deleted_twice" else "")
            if item is None:
                continue
            if (str(item.get("status")) == "pending"
                    and _targets_dirty(queue, item.get("write_paths") or [])):
                records[name]["dirty"] = item.get("write_paths") or []
                out.update(reason="targets_dirty", tier=name,
                           detail=("the write target is already dirty in the tree: "
                                   + ", ".join(item.get("write_paths") or [])[:300]))
                return out
            if (str(item.get("status")) == "pending" and name in PRODUCT_TIERS
                    and not _gate_present(queue)):
                records[name]["gated"] = True
                out.update(reason="gate_closed", tier=name,
                           detail=(f"{GATE_DEP} is not in the queue; {name} work would be "
                                   "blocked forever, so nothing was added"))
                return out
            if decision["action"] == "reemit":
                item["reemitted"] = True

            if dry_run:
                added.append({"id": item.get("id"), "tier": name,
                              "status": item.get("status"), "dry_run": True})
            else:
                appended = append_item(queue, item, queue_path=queue_file)
                if not appended.get("ok"):
                    out.update(reason=str(appended.get("reason") or "append_failed"),
                               detail="; ".join(appended.get("problems") or []))
                    return out
                queue = appended["queue_data"]
                added.append({"id": item.get("id"), "tier": name,
                              "status": item.get("status")})
            out.update(ok=True, reason=decision["why"], tier=name,
                       detail=str(item.get("needs_author") or item.get("needs_owner")
                                  or item.get("objective") or ""))
            if len(added) >= limit:
                return out

    if added:
        # Reached only when max_items > 1 and the run ended with items added; the
        # ok/reason of the last one is already recorded above.
        return out

    out.update(ok=False, tier=None)
    if duplicates:
        out.update(reason="duplicate",
                   detail=f"{duplicates} candidate(s) are already in the queue")
    else:
        out.update(reason="starvation",
                   detail=("every tier is green and non-vacuous; nothing was written. "
                           + _tier_summary(records)))
    return out


def generate(*, queue_path: Any = None, tier: Optional[str] = None, max_items: int = 1,
             dry_run: bool = False, probe_runner: Callable[..., Any] = subprocess.run,
             now: Any = None) -> Dict[str, Any]:
    """Add at most ``max_items`` items to the queue, or say exactly why not.

    ``queue_path`` defaults to the module constant QUEUE *looked up at call
    time*, so a test that monkeypatches it cannot reach the real queue by
    forgetting an argument.

    ``probe_runner`` is the only way a subprocess is started: the real one in
    production, a fake in tests. ``dry_run`` never touches the queue or the
    emission log; it still derives scope, because whether an item would be
    dispatchable is the answer being asked for, and the derivation artifact under
    ``state/author/`` is the evidence of that check.
    """
    queue_file = Path(queue_path or QUEUE)
    current = _as_dt(now)
    out: Dict[str, Any] = {
        "ok": False, "reason": "", "tier": None, "added": [],
        "dry_run": bool(dry_run), "queue": str(queue_file), "tiers": {}, "detail": "",
    }

    if Path(STOP).exists():
        out.update(reason="STOP",
                   detail="a STOP marker halts generation as well as the loop")
        return out

    lock = _lock()
    if not lock.get("ok"):
        out.update(reason="busy", detail=str(lock.get("detail") or ""))
        return out
    try:
        return _generate_locked(queue_file=queue_file, tier=tier,
                                max_items=max_items, dry_run=dry_run,
                                probe_runner=probe_runner, now=current, out=out)
    finally:
        _unlock(lock)


# ------------------------------------------------------------------------- cli
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the next unit of work, or say why there is none.")
    parser.add_argument("--tier", default="", help="force one tier (T0..T5)")
    parser.add_argument("--max-items", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true",
                        help="decide and report, but do not write the queue")
    parser.add_argument("--needs-forward", action="store_true",
                        help="print the dispatchable active count and exit")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    if ns.needs_forward:
        count = needs_forward()
        print(count if not ns.json else json.dumps({"needs_forward": count}))
        return 0
    out = generate(tier=ns.tier or None, max_items=ns.max_items, dry_run=ns.dry_run)
    print(json.dumps(out, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
