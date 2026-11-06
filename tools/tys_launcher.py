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


def _opencode_exe() -> str:
    """CreateProcess cannot run the .ps1 shim that `which` prefers on Windows."""
    import shutil

    exe = shutil.which("opencode") or shutil.which("opencode.cmd") or "opencode"
    if str(exe).lower().endswith(".ps1"):
        candidate = Path(str(exe)[:-4] + ".cmd")
        if candidate.is_file():
            return str(candidate)
    return str(exe)


def _session_model(session_id: str) -> Optional[Dict[str, Any]]:
    """Which model actually answered? Read the session store, never assume."""
    db = Path(os.environ.get("USERPROFILE", "")) / ".local" / "share" / "opencode" / "opencode.db"
    if not session_id or not db.is_file():
        return None
    try:
        import sqlite3

        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT agent, model, cost FROM session_v2 WHERE id=?", (session_id,)).fetchone()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - provenance is best effort, absence is reported
        return None
    if not row:
        return None
    try:
        model = json.loads(row[1]) if row[1] else {}
    except (TypeError, ValueError):
        model = {}
    return {"agent": row[0], "model_id": model.get("id"),
            "provider": model.get("providerID"), "variant": model.get("variant"),
            "cost": row[2]}


def deepseek_worker(task_path: Path, result_path: Path) -> int:
    """The owner's coding model (DeepSeek V4.1 Flash on OpenCode), via `run`.

    Measured 2026-11-06 on opencode v2.2.5: the TUI flag `--prompt` cannot select
    an agent and does not return usable output, so the worker uses
    `opencode run --agent <lane> --format json` and sends the prompt on **stdin**
    (a 16 KB contract exceeds the Windows command line).

    The model is told what to change and which files it may touch. The launcher
    runs the acceptance commands afterwards; the worker never grades itself.
    """
    import shutil

    task = json.loads(task_path.read_text(encoding="utf-8"))
    lane = os.environ.get("TY_WORKER_AGENT", "tys")
    allowed = ", ".join(task.get("write_paths") or []) or "(none - refuse)"
    checks = "; ".join(" ".join(c) for c in (task.get("acceptance_commands") or []))
    prompt = (
        "You are the Northstar OS autonomy worker. Work only in this repository. "
        f"You may modify ONLY: {allowed}. Do not touch any other file, do not edit tests, "
        "do not commit, and do not grade your own work.\n\n"
        f"TASK: {task.get('objective')}\n\n"
        f"ACCEPTANCE (the launcher runs this afterwards): {checks}\n\n"
        "Make the smallest correct change that satisfies the check. If it cannot pass "
        "without touching a file outside the allowlist, change nothing and say why in one "
        "line. When finished, stop."
    )
    exe = _opencode_exe()
    cmd = [exe, "run", "--agent", lane, "--format", "json", "--auto"]
    started = time.time()
    events: List[Dict[str, Any]] = []
    text: List[str] = []
    session_id = ""
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), timeout=WORKER_TIMEOUT_S,
                              capture_output=True, text=True, input=prompt)
        code = proc.returncode
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            events.append(event)
            session_id = str(event.get("sessionID") or session_id)
            if event.get("type") == "text":
                chunk = event.get("text") or event.get("content") or ""
                if isinstance(chunk, str):
                    text.append(chunk)
        stderr_tail = (proc.stderr or "")[-800:]
    except subprocess.TimeoutExpired:
        code, stderr_tail = 124, "worker timeout"
    except OSError as exc:
        code, stderr_tail = 127, f"opencode_not_runnable: {exc}"

    errors = [e.get("error") for e in events if e.get("type") == "error"]
    provenance = _session_model(session_id)
    ok = code == 0 and not errors
    result_path.write_text(json.dumps({
        "ok": ok,
        "steps": 1,
        "worker": "opencode/run",
        "lane": lane,
        "session_id": session_id,
        "model": provenance,
        "seconds": round(time.time() - started, 1),
        "events": len(events),
        "errors": errors[:3],
        "text": "".join(text)[:4000],
        "stderr": stderr_tail,
        "objective": task.get("objective"),
    }, indent=2), encoding="utf-8")
    _append(JOURNAL, {"event": "deepseek_worker", "code": code, "lane": lane,
                      "session": session_id,
                      "model": (provenance or {}).get("model_id"),
                      "seconds": round(time.time() - started, 1),
                      "errors": errors[:2]})
    return code


def run_acceptance(commands: List[List[str]]) -> Dict[str, Any]:
    """The launcher's own verdict. The model never grades its own patch."""
    results = []
    ok = True
    for cmd in commands:
        if not cmd:
            continue
        started = time.time()
        try:
            proc = subprocess.run([str(c) for c in cmd], cwd=str(ROOT),
                                  timeout=WORKER_TIMEOUT_S, capture_output=True, text=True)
            passed = proc.returncode == 0
            detail = ((proc.stdout or "") + (proc.stderr or ""))[-1200:]
        except subprocess.TimeoutExpired:
            passed, detail = False, "acceptance timeout"
        ok = ok and passed
        results.append({"cmd": " ".join(str(c) for c in cmd), "passed": passed,
                        "seconds": round(time.time() - started, 1),
                        "detail": detail})
    return {"ok": ok, "checks": results}


Worker = Callable[[Path, Path], int]

MODEL_BASE_URL = os.environ.get("TY_WORKER_BASE_URL", "http://127.0.0.1:8080")#: The worker can speak to llama.cpp (OpenAI-compatible, 8080) or to Ollama's
#: native adapter (11434). The preflight must check the one the worker will use,
#: otherwise a healthy Ollama lane is reported as "down".
MODEL_PROVIDER = os.environ.get("TYS_CODING_PROVIDER", "compat").lower()
OLLAMA_BASE_URL = os.environ.get("TYS_CODING_URL", "http://127.0.0.1:11434")


def model_up(timeout_s: float = 3.0) -> bool:
    """Is the lane the worker will actually use reachable?"""
    import urllib.error
    import urllib.request

    if MODEL_PROVIDER == "ollama":
        url = OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    else:
        url = MODEL_BASE_URL.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def start_model(wait_s: float = 240.0) -> bool:
    """Start the local LLM lane and wait for its health endpoint."""
    script = ROOT / "scripts" / "start-northstar-llm.ps1"
    if not script.is_file():
        return False
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", str(script)], cwd=str(ROOT),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if model_up():
            return True
        time.sleep(5)
    return False


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


def _dirty(paths: List[str]) -> List[str]:
    """Declared paths that already differ from HEAD. A dirty target is refused."""
    if not paths:
        return []
    out = _git("status", "--porcelain", "--", *paths)
    return [line[3:].strip() for line in (out.stdout or "").splitlines() if line.strip()]


def _tracked() -> set:
    out = _git("ls-tree", "-r", "--name-only", "HEAD")
    return {line.strip() for line in (out.stdout or "").splitlines() if line.strip()}


def _restore(paths: List[str]) -> List[str]:
    """Undo a failed attempt with git, not with an in-memory snapshot.

    The snapshot version was dangerous (measured 2026-11-06): a path that was
    absent when the snapshot was taken was *deleted* on restore, which removed a
    committed file that another session had just created. Git knows what belongs
    in the tree; a memory image does not.
    """
    restored: List[str] = []
    if not paths:
        return restored
    tracked = _tracked()
    source = [p for p in paths if p in tracked]
    if source:
        _git("checkout", "--", *source)
        restored.extend(source)
    for rel in paths:
        if rel in tracked:
            continue
        path = ROOT / rel
        if path.is_file():
            try:
                path.unlink()
                restored.append(rel)
            except OSError as exc:
                _append(JOURNAL, {"event": "restore_failed", "path": rel, "error": str(exc)})
    return restored


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
    contract = task_contract(item, brief)
    checks = contract.get("acceptance_commands") or []

    # Pre-run red gate: a check that is already green cannot prove anything a
    # worker did. Without this, a cycle "ships" by running a passing test.
    before = run_acceptance(checks)
    if before.get("ok"):
        runner.mark(runner.load_queue(), str(item.get("id")), "pending",
                    check_already_green=True,
                    defer_until_cycle=int(brief["cycle"]) + 2)
        runner._clear_lease("check already green")
        _append(JOURNAL, {"event": "check_already_green", "item": item.get("id")})
        return {"ok": True, "skipped": True, "item": item.get("id"),
                "reason": "check_already_green"}

    snap = list(contract.get("write_paths") or [])
    dirty = _dirty(snap)
    if dirty:
        # A dirty target means somebody else owns these bytes (an operator edit or
        # a parallel lane). Restore would overwrite their work, so refuse instead.
        runner.mark(runner.load_queue(), str(item.get("id")), "pending",
                    blocked_reason=f"targets_dirty: {', '.join(dirty[:3])}",
                    defer_until_cycle=int(brief["cycle"]) + 1)
        runner._clear_lease("dirty targets")
        _append(JOURNAL, {"event": "targets_dirty", "item": item.get("id"), "paths": dirty[:5]})
        return {"ok": True, "skipped": True, "item": item.get("id"),
                "reason": "targets_dirty"}
    task_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
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
    # The launcher judges the patch by running the declared checks itself. A model
    # that writes and grades is not a verification; ty_task_runner may also report
    # its own acceptance, but the launcher's run is the authority.
    acceptance = run_acceptance(checks)
    shipped = bool(acceptance.get("ok")) and int(code or 0) == 0 \
        and bool(worker_out.get("ok", True))
    worker_out["acceptance"] = acceptance
    worker_out["before_green"] = before.get("ok")
    if not shipped:
        restored = _restore(snap)
        if restored:
            _append(JOURNAL, {"event": "reverted_bytes", "item": item.get("id"),
                              "paths": restored})
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
    parser.add_argument("--start-model", action="store_true",
                        help="start the local LLM lane if its health endpoint is down")
    parser.add_argument("--worker", choices=("ty", "deepseek"), default="ty",
                        help="ty = local coding lane; deepseek = OpenCode CLI (owner's model)")
    ns = parser.parse_args(argv)

    started = time.time()
    deadline = started + ns.max_hours * 3600
    cycles = 0
    failures = 0
    skips = 0
    tokens = 0
    reason = "max_cycles"

    heartbeat(state="starting", dry_run=ns.dry_run, max_cycles=ns.max_cycles,
              max_hours=ns.max_hours)
    if not ns.dry_run and ns.worker == "ty" and not model_up():
        # A dead model lane is not a failed cycle: burning an attempt per cycle
        # against a refused connection teaches nothing and quietly ages the queue.
        _append(JOURNAL, {"event": "model_lane_down", "base_url": MODEL_BASE_URL})
        if ns.start_model and start_model():
            _append(JOURNAL, {"event": "model_lane_started", "base_url": MODEL_BASE_URL})
        else:
            heartbeat(state="stopped", reason="model_lane_down",
                      cycles=0, base_url=MODEL_BASE_URL)
            _append(JOURNAL, {"event": "launcher_stopped",
                              "reason": "model_lane_down", "cycles": 0})
            print(json.dumps({"stopped": True, "reason": "model_lane_down",
                              "base_url": MODEL_BASE_URL,
                              "hint": "run scripts/start-northstar-llm.ps1 or pass --start-model"},
                             indent=2))
            return 0
    while cycles < ns.max_cycles:
        if time.time() >= deadline:
            reason = "max_hours"
            break
        if (ROOT / "STOP").exists():
            reason = "STOP"
            break
        before = runner._tokens_today()
        out = _run_cycle(worker=(deepseek_worker if ns.worker == "deepseek" else default_worker),
                         dry_run=ns.dry_run,
                         cycle_budget=ns.max_cycles - cycles)
        if out.get("stop"):
            reason = out.get("reason", "stop")
            _append(JOURNAL, {"event": "stopped", "reason": reason})
            break
        cycles += 1
        tokens += max(0, runner._tokens_today() - before)
        if out.get("skipped"):
            # A skipped item is not a cycle: it means the queue surfaced work that
            # cannot be dispatched (no checks, no write scope). Counting it as a
            # cycle would let the loop burn its whole budget on unrunnable items.
            cycles -= 1
            skips += 1
            if skips >= 40:
                reason = "no_runnable_items"
                break
            failures = 0
        elif out.get("ok"):
            failures = 0
            skips = 0
        else:
            failures += 1
            if failures >= MAX_FAILURE_STREAK:
                reason = "worker_failure_streak"
                break
        if ns.max_token_budget and tokens >= ns.max_token_budget:
            reason = "token_budget"
            break
        heartbeat(state="running", cycles=cycles, tokens_estimate=tokens,
                  last=out, failures=failures, skips=skips)

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
