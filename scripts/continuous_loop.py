#!/usr/bin/env python3
"""Autonomous continuous-loop supervisor for Northstar OS.

This is a SUPERVISOR, not a model: it reads a task registry, runs the task's
allowlisted verification commands, commits only the paths the task names, appends
an evidence record to the evaluation ledger, and moves to the next task.

Safety rules encoded here:

  * `git add .` is never used. A task can commit only its own relative paths,
    validated against a root allowlist and a protected-name denylist.
  * Task commands are argv lists, never shell strings. Amazon / Chrome / paid
    provider tokens are refused before execution.
  * A `STOP` file, a protected branch (main/release/hotfix), less than 10 GB free
    disk, or less than 3 GB free RAM stops the loop.
  * A failed check stops the cycle; nothing is committed. There is no auto-retry
    (an operator can fix and rerun, or pass an explicit repair command later).
  * The ledger is append-only JSONL with the real commands, return codes and
    durations. It never records a credential value.
  * The loop never writes `00_STATE.json`; that file is operator-apply only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = ROOT / "config" / "continuous_loop_tasks.json"
STATE_PATH = ROOT / "state" / "continuous_loop_state.json"
LEDGER_PATH = ROOT / "reports" / "evaluation_ledger.jsonl"
STOP_PATH = ROOT / "STOP"
MIN_FREE_DISK_GB = 10.0
MIN_FREE_RAM_GB = 3.0
PROTECTED_BRANCHES = {"main", "master", "release", "hotfix"}
ALLOWED_COMMIT_ROOTS = (
    "scripts/", "config/", "docs/", "reports/", "tools/",
    "Northstar_backend/", "northstar-os-ui/src/", "northstar-os-ui/scripts/",
    "state/fragments/",
)
DENIED_COMMIT_NAMES = (".env", "northstar.db", "northstar.db-wal", "northstar.db-shm")
DENIED_COMMIT_PARTS = {".env", "exports", "screenshots", "__pycache__", "node_modules"}
FORBIDDEN_COMMAND_TOKENS = (
    "amazon", "chromeconnect", "chrome-connect", "openrouter", "dataforseo",
    "unwrangle", "brightdata", "bright_data", "costco.com", "walmart.com",
    "curl ", "wget ",
)
_SECRET_RE = re.compile(
    r"(?i)(sk-[a-z0-9_-]{8,}|bearer\s+[a-z0-9._-]+|"
    r"(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+)")


def _scrub(text: str) -> str:
    return _SECRET_RE.sub("<redacted>", str(text or ""))[-6000:]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_tasks(path: Path = TASKS_PATH) -> Dict[str, Any]:
    data = _load_json(path, None)
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise ValueError(f"task registry is missing or invalid: {path}")
    return data


def save_tasks(data: Dict[str, Any], path: Path = TASKS_PATH) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_state(path: Path = STATE_PATH) -> Dict[str, Any]:
    state = _load_json(path, {"completed": {}})
    if not isinstance(state, dict):
        state = {"completed": {}}
    state.setdefault("completed", {})
    return state


def save_state(state: Dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def select_task(tasks: Dict[str, Any], state: Optional[Dict[str, Any]] = None,
                task_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    rows = tasks.get("tasks") or []
    completed = (state or {}).get("completed") or {}
    if task_id:
        for task in rows:
            if task.get("id") == task_id and task.get("id") not in completed \
                    and not task.get("blocked"):
                return task
        return None
    for task in rows:
        if task.get("id") not in completed and not task.get("blocked"):
            return task
    return None


def _branch() -> str:
    git = shutil.which("git")
    if not git:
        return ""
    proc = subprocess.run([git, "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=30)
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def guardrails(root: Path = ROOT) -> Dict[str, Any]:
    problems: List[str] = []
    if (root / "STOP").is_file():
        problems.append("STOP file present")
    branch = _branch()
    if branch in PROTECTED_BRANCHES or branch.startswith("release/"):
        problems.append(f"protected branch: {branch}")
    try:
        free_gb = shutil.disk_usage(root).free / (1024 ** 3)
        if free_gb < MIN_FREE_DISK_GB:
            problems.append(f"free disk {free_gb:.1f} GB < {MIN_FREE_DISK_GB} GB")
    except OSError as exc:
        problems.append(f"disk probe failed: {exc}")
    try:
        import psutil  # type: ignore
        free_ram = psutil.virtual_memory().available / (1024 ** 3)
        if free_ram < MIN_FREE_RAM_GB:
            problems.append(f"free RAM {free_ram:.1f} GB < {MIN_FREE_RAM_GB} GB")
    except Exception:  # noqa: BLE001 - RAM is best-effort, disk is mandatory
        pass
    if not shutil.which("git"):
        problems.append("git not found")
    return {"ok": not problems, "problems": problems, "branch": branch}


def check_command(cmd: Sequence[str]) -> Optional[str]:
    text = " ".join(str(c) for c in cmd).lower()
    for token in FORBIDDEN_COMMAND_TOKENS:
        if token in text:
            return f"forbidden command token: {token!r}"
    return None


def validate_commit_paths(paths: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Return (allowed relative paths, refused paths with reasons)."""
    allowed: List[str] = []
    refused: List[str] = []
    for raw in paths or []:
        text = str(raw or "").replace("\\", "/").strip()
        if not text or text.startswith("/") or ".." in text.split("/"):
            refused.append(f"{raw!r}: absolute/empty/escape path")
            continue
        name = text.rsplit("/", 1)[-1]
        parts = set(text.split("/"))
        if name in DENIED_COMMIT_NAMES or parts & DENIED_COMMIT_PARTS:
            refused.append(f"{text}: protected path")
            continue
        if not any(text.startswith(prefix) for prefix in ALLOWED_COMMIT_ROOTS):
            refused.append(f"{text}: outside the commit allowlist")
            continue
        allowed.append(text)
    return allowed, refused


def append_ledger(record: Dict[str, Any], path: Path = LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())


def run_command(cmd: Sequence[str], *, cwd: Path = ROOT, timeout: float = 900.0,
                dry_run: bool = False) -> Dict[str, Any]:
    reason = check_command(cmd)
    if reason:
        return {"ok": False, "argv": list(cmd), "cwd": str(cwd), "exit": None,
                "duration_s": 0.0, "error": reason, "output": ""}
    exe = shutil.which(str(cmd[0]))
    argv = [exe or str(cmd[0])] + [str(c) for c in cmd[1:]]
    started = time.time()
    if dry_run:
        return {"ok": True, "argv": argv, "cwd": str(cwd), "exit": 0,
                "duration_s": 0.0, "error": "", "output": "[dry-run]"}
    try:
        proc = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        return {"ok": False, "argv": argv, "cwd": str(cwd), "exit": None,
                "duration_s": round(time.time() - started, 3),
                "error": f"timeout after {timeout}s", "output": ""}
    except OSError as exc:
        return {"ok": False, "argv": argv, "cwd": str(cwd), "exit": None,
                "duration_s": round(time.time() - started, 3),
                "error": str(exc)[:300], "output": ""}
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""))[-6000:]
    return {"ok": proc.returncode == 0, "argv": argv, "cwd": str(cwd),
            "exit": proc.returncode, "duration_s": round(time.time() - started, 3),
            "error": "" if proc.returncode == 0 else f"exit {proc.returncode}",
            "output": _scrub(output)}


def _git(args: Sequence[str], *, cwd: Path = ROOT) -> Dict[str, Any]:
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, *args], cwd=str(cwd), capture_output=True,
                          text=True, timeout=120)
    return {"ok": proc.returncode == 0, "exit": proc.returncode,
            "output": ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""))[-4000:]}


def commit_paths(task: Dict[str, Any], *, dry_run: bool = False) -> Dict[str, Any]:
    allowed, refused = validate_commit_paths(task.get("commit_paths") or [])
    existing = [p for p in allowed if (ROOT / p).exists()]
    if refused:
        return {"ok": False, "error": "refused commit paths: " + "; ".join(refused),
                "allowed": allowed, "refused": refused}
    if not existing:
        return {"ok": True, "committed": False, "reason": "no commit paths exist",
                "allowed": allowed, "refused": refused}
    status = _git(["status", "--porcelain", "--", *existing])
    if not status["ok"]:
        return {"ok": False, "error": status["output"][:500], "allowed": allowed}
    if not status["output"].strip():
        return {"ok": True, "committed": False, "reason": "no changes in commit paths",
                "allowed": allowed, "refused": refused}
    if dry_run:
        return {"ok": True, "committed": False, "dry_run": True,
                "would_add": existing, "status": status["output"][:1000]}
    added = _git(["add", "--", *existing])
    if not added["ok"]:
        return {"ok": False, "error": added["output"][:500], "allowed": allowed}
    staged = _git(["diff", "--cached", "--check"])
    if not staged["ok"]:
        return {"ok": False, "error": "whitespace/conflict check failed: " + staged["output"][:500]}
    message = str(task.get("commit_message") or f"cycle: {task.get('name') or task.get('id')}")
    commit = _git(["commit", "-m", message])
    if not commit["ok"]:
        return {"ok": False, "error": commit["output"][:500], "allowed": allowed}
    head = _git(["rev-parse", "HEAD"])
    sha = head["output"].strip() if head["ok"] else ""
    return {"ok": True, "committed": True, "sha": sha[:12], "allowed": allowed,
            "refused": refused, "output": commit["output"][:1000]}


def run_cycle(task: Dict[str, Any], *, dry_run: bool = False,
              no_commit: bool = False) -> Dict[str, Any]:
    cycle_id = f"{task.get('id') or 'cycle'}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    started = _now()
    checks: List[Dict[str, Any]] = []
    for spec in task.get("checks") or []:
        name = str(spec.get("name") or "check")
        cmd = spec.get("cmd") or []
        cwd = (ROOT / str(spec.get("cwd") or ".")).resolve()
        timeout = float(spec.get("timeout") or 900.0)
        result = run_command(cmd, cwd=cwd, timeout=timeout, dry_run=dry_run)
        checks.append({"name": name, **result})
        if not result["ok"]:
            record = {"cycle": cycle_id, "task": task.get("id"), "name": task.get("name"),
                      "started_at": started, "finished_at": _now(), "status": "failed",
                      "checks": checks, "commit": None}
            if not dry_run:
                append_ledger(record)
            return record
    commit = None
    if not no_commit:
        commit = commit_paths(task, dry_run=dry_run)
        if not commit.get("ok"):
            record = {"cycle": cycle_id, "task": task.get("id"), "name": task.get("name"),
                      "started_at": started, "finished_at": _now(),
                      "status": "commit_failed", "checks": checks, "commit": commit}
            if not dry_run:
                append_ledger(record)
            return record
    record = {"cycle": cycle_id, "task": task.get("id"), "name": task.get("name"),
              "started_at": started, "finished_at": _now(), "status": "ok",
              "checks": checks, "commit": commit}
    if not dry_run:
        append_ledger(record)
    return record


def mark_task(state: Dict[str, Any], task_id: str, *,
              commit: Optional[Dict[str, Any]] = None) -> None:
    completed = state.setdefault("completed", {})
    completed[task_id] = {"completed_at": _now(),
                          "commit": (commit or {}).get("sha") or ""}


def status(tasks: Dict[str, Any], state: Optional[Dict[str, Any]] = None,
           ledger_path: Path = LEDGER_PATH) -> Dict[str, Any]:
    state = state or {"completed": {}}
    completed = state.get("completed") or {}
    rows = []
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines()[-8:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {
        "tasks": [{"id": t.get("id"),
                   "status": ("completed" if t.get("id") in completed
                              else "blocked" if t.get("blocked") else "pending"),
                   "commit": (completed.get(t.get("id")) or {}).get("commit")}
                  for t in tasks.get("tasks") or []],
        "pending": [t.get("id") for t in tasks.get("tasks") or []
                    if t.get("id") not in completed and not t.get("blocked")],
        "last_cycles": rows,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", default="", help="run one task id")
    ap.add_argument("--once", action="store_true", help="run at most one task")
    ap.add_argument("--max-cycles", type=int, default=0,
                    help="0 = all pending tasks (default), N = cap")
    ap.add_argument("--dry-run", action="store_true", help="print commands, write nothing")
    ap.add_argument("--no-commit", action="store_true", help="verify only")
    ap.add_argument("--status", action="store_true", help="show tasks and recent cycles")
    args = ap.parse_args(argv)

    tasks = load_tasks()
    state = load_state()
    if args.status:
        print(json.dumps(status(tasks, state), indent=2))
        return 0
    guard = guardrails()
    if not guard["ok"] and not args.dry_run:
        print(json.dumps({"ok": False, "guardrails": guard}, indent=2))
        return 2

    limit = 1 if args.once else max(0, int(args.max_cycles))
    completed = 0
    while True:
        if limit and completed >= limit:
            break
        task = select_task(tasks, state, args.task or None)
        if task is None:
            break
        print(f"[*] cycle {task.get('id')}: {task.get('name')}")
        record = run_cycle(task, dry_run=args.dry_run, no_commit=args.no_commit)
        print(f"    {record['status']} ({len(record.get('checks') or [])} checks)")
        if record["status"] != "ok":
            print(json.dumps(record, indent=2)[:4000])
            return 1
        if not args.dry_run:
            mark_task(state, task["id"], commit=record.get("commit"))
            save_state(state)
            if record.get("commit", {}).get("sha"):
                print(f"    committed {record['commit']['sha']}")
        completed += 1
        if args.task:
            break
    remaining = [t.get("id") for t in tasks.get("tasks") or []
                 if t.get("id") not in (state.get("completed") or {})
                 and not t.get("blocked")]
    print(json.dumps({"ok": True, "completed": completed, "pending": remaining}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
