#!/usr/bin/env python3
"""Bounded autonomous engineering supervisor for Northstar OS.

The supervisor is the operator: it selects an explicitly authorized task, takes
a rollback baseline, dispatches Ty (the existing bounded coding agent) or runs a
prebuilt task, verifies the real acceptance checks, restores task-owned changes
on failure, commits only the task's paths, records evidence, and advances.

It is deliberately not a model and never grants itself permission:

  * a task must be `authorized: true`, low/medium risk, with a scope and checks;
  * a Ty task gets a Workspace restricted to its write paths and a run allowlist
    made only from its acceptance commands;
  * a task can commit only validated relative paths, and `git commit --only`
    keeps pre-existing staged work untouched;
  * out-of-scope edits are refused and restored from the task baseline;
  * a failed acceptance restores the task-owned paths, verifies the bytes, and
    leaves the task failed — never completed;
  * STOP, a protected branch, low disk/RAM, a stale lock or an interrupted run
    stops the campaign. No automatic retry; at most one explicit repair is
    allowed only when the contract says so.

Commands are argv lists, never shell strings. The ledger is scrubbed and capped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

ROOT = Path(os.environ.get("NORTHSTAR_LOOP_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()
TASKS_PATH = ROOT / "config" / "continuous_loop_tasks.json"
STATE_PATH = ROOT / "state" / "continuous_loop_state.json"
LEDGER_PATH = ROOT / "reports" / "evaluation_ledger.jsonl"
LOCK_PATH = ROOT / "state" / "continuous_loop.lock"
HEARTBEAT_PATH = ROOT / "state" / "continuous_loop_heartbeat.json"
RUN_DIR = ROOT / "state" / "runs"
STOP_PATH = ROOT / "STOP"
MIN_FREE_DISK_GB = 10.0
MIN_FREE_RAM_GB = 3.0
MAX_TASK_TIMEOUT_S = 900
MAX_REPAIRS = 1
MAX_IMPLEMENTATION_TASKS = 3
CAMPAIGN_DEADLINE_MIN = 90
STALE_LOCK_S = 300
HEARTBEAT_STALE_S = 120
PROTECTED_BRANCHES = {"main", "master", "release", "hotfix"}
ALLOWED_RISK = {"low", "medium"}
ALLOWED_EXECUTABLES = {"python", "python3", "pytest", "npm", "npx", "node"}
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
SUPERVISOR_STATE_PREFIXES = ("state/",)
_SECRET_RE = re.compile(
    r"(?i)(sk-[a-z0-9_-]{8,}|bearer\s+[a-z0-9._-]+|"
    r"(?:password|passwd|secret|token|api[_-]?key)\s*[=:]\s*\S+)")


class LoopError(RuntimeError):
    """A supervisor-level refusal or unrecoverable failure."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _scrub(text: str) -> str:
    return _SECRET_RE.sub("<redacted>", str(text or ""))[-1200:]


def _is_supervisor_path(path: str) -> bool:
    rel = str(path or "").replace("\\", "/")
    return any(rel.startswith(prefix) for prefix in SUPERVISOR_STATE_PREFIXES)


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_tasks(path: Path = TASKS_PATH) -> Dict[str, Any]:
    data = _load_json(path, None)
    if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
        raise LoopError(f"task registry is missing or invalid: {path}")
    return data


def load_state(path: Path = STATE_PATH) -> Dict[str, Any]:
    state = _load_json(path, {"completed": {}, "tasks": {}})
    if not isinstance(state, dict):
        state = {"completed": {}, "tasks": {}}
    state.setdefault("completed", {})
    state.setdefault("tasks", {})
    for task_id, record in (state.get("completed") or {}).items():
        state["tasks"].setdefault(task_id, {
            "status": "completed",
            "completed_at": record.get("completed_at"),
            "commit": record.get("commit"),
        })
    return state


def task_status(state: Dict[str, Any], task_id: str) -> str:
    record = (state.get("tasks") or {}).get(task_id) or {}
    return str(record.get("status") or
               ("completed" if task_id in (state.get("completed") or {}) else "pending"))


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import psutil  # type: ignore
        return bool(psutil.pid_exists(pid))
    except Exception:
        pass
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _read_lock() -> Optional[Dict[str, Any]]:
    if not LOCK_PATH.is_file():
        return None
    return _load_json(LOCK_PATH, None)


def acquire_lock(run_id: str) -> Dict[str, Any]:
    """One supervisor at a time; a dead owner's lock is reclaimed as stale."""
    existing = _read_lock()
    if existing:
        pid = int(existing.get("pid") or 0)
        age = time.time() - float(existing.get("created_ts") or 0)
        if _is_pid_alive(pid) and age < STALE_LOCK_S:
            raise LoopError(f"another supervisor owns the lock (pid {pid})")
        if _is_pid_alive(pid):
            raise LoopError(f"lock owner pid {pid} is alive but older than {STALE_LOCK_S}s; refusing")
        LOCK_PATH.unlink(missing_ok=True)
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {"run_id": run_id, "pid": os.getpid(), "created_at": _now(),
              "created_ts": time.time()}
    fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, json.dumps(record).encode("utf-8"))
    finally:
        os.close(fd)
    return record


def release_lock() -> None:
    try:
        LOCK_PATH.unlink()
    except OSError:
        pass


def write_heartbeat(run_id: str, task_id: str, stage: str) -> None:
    _save_json(HEARTBEAT_PATH, {
        "run_id": run_id, "task": task_id, "pid": os.getpid(),
        "stage": stage, "last_seen": _now(), "last_seen_ts": time.time(),
    })


def heartbeat_age() -> Optional[float]:
    data = _load_json(HEARTBEAT_PATH, None)
    if not isinstance(data, dict) or not data.get("last_seen_ts"):
        return None
    return time.time() - float(data["last_seen_ts"])


def recover_interrupted(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Mark a stale running/verifying task interrupted. Never auto-replays it."""
    recovered = []
    for task_id, record in (state.get("tasks") or {}).items():
        if record.get("status") not in ("running", "verifying"):
            continue
        pid = int(record.get("pid") or 0)
        age = heartbeat_age()
        if _is_pid_alive(pid) and (age is None or age < HEARTBEAT_STALE_S):
            continue
        record["status"] = "interrupted"
        record["reason"] = "stale heartbeat or dead owner process"
        record["interrupted_at"] = _now()
        recovered.append({"task": task_id, "pid": pid, "heartbeat_age": age})
    if recovered:
        _save_json(STATE_PATH, state)
    return recovered


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
    except Exception:
        pass
    if not shutil.which("git"):
        problems.append("git not found")
    return {"ok": not problems, "problems": problems, "branch": branch}


def _branch() -> str:
    git = shutil.which("git")
    if not git:
        return ""
    proc = subprocess.run([git, "rev-parse", "--abbrev-ref", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=30)
    return (proc.stdout or "").strip() if proc.returncode == 0 else ""


def check_command(cmd: Sequence[str]) -> Optional[str]:
    text = " ".join(str(c) for c in cmd).lower()
    for token in FORBIDDEN_COMMAND_TOKENS:
        if token in text:
            return f"forbidden command token: {token!r}"
    exe = Path(str(cmd[0] if cmd else "")).name.lower()
    if exe not in ALLOWED_EXECUTABLES:
        return f"executable not allowed: {exe or '(empty)'}"
    return None


def validate_commit_paths(paths: Iterable[str]) -> Tuple[List[str], List[str]]:
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


def validate_scope_paths(paths: Iterable[str]) -> Tuple[List[str], List[str]]:
    return validate_commit_paths(paths)


def validate_task(task: Dict[str, Any]) -> List[str]:
    """Return contract errors; an empty list means the task may run."""
    errors: List[str] = []
    task_id = str(task.get("id") or "").strip()
    if not task_id:
        errors.append("missing task id")
    if task.get("authorized") is not True:
        errors.append("task is not explicitly authorized")
    if str(task.get("risk") or "").lower() not in ALLOWED_RISK:
        errors.append(f"risk must be one of {sorted(ALLOWED_RISK)}")
    execution = str(task.get("execution") or "prebuilt")
    if execution not in ("ty", "prebuilt"):
        errors.append("execution must be 'ty' or 'prebuilt'")
    if execution == "ty":
        if not str(task.get("objective") or "").strip():
            errors.append("ty task needs an objective")
        if not task.get("write_paths"):
            errors.append("ty task needs write_paths")
    _, refused = validate_scope_paths(task.get("write_paths") or [])
    if refused:
        errors.append("write_paths refused: " + "; ".join(refused))
    allowed_commit, refused_commit = validate_commit_paths(task.get("commit_paths") or [])
    if refused_commit:
        errors.append("commit_paths refused: " + "; ".join(refused_commit))
    if not allowed_commit and execution != "ty":
        errors.append("task needs commit_paths")
    for spec in task.get("checks") or []:
        reason = check_command(spec.get("cmd") or [])
        if reason:
            errors.append(f"check {spec.get('name')!r}: {reason}")
    for cmd in task.get("acceptance_commands") or []:
        reason = check_command(cmd)
        if reason:
            errors.append(f"acceptance command: {reason}")
    timeout = int(task.get("timeout_seconds") or 600)
    if timeout <= 0 or timeout > MAX_TASK_TIMEOUT_S:
        errors.append(f"timeout_seconds must be 1..{MAX_TASK_TIMEOUT_S}")
    if int(task.get("max_repairs") or 0) > MAX_REPAIRS:
        errors.append(f"max_repairs must be <= {MAX_REPAIRS}")
    return errors


def blocked_reason(task: Dict[str, Any], state: Dict[str, Any]) -> Optional[str]:
    if str(task.get("blocked") or "").strip():
        return str(task.get("blocked"))
    errors = validate_task(task)
    if errors:
        return "; ".join(errors)
    for dep in task.get("dependencies") or []:
        if task_status(state, str(dep)) != "completed":
            return f"dependency {dep!r} is {task_status(state, str(dep))}"
    return None


def select_task(tasks: Dict[str, Any], state: Dict[str, Any],
                task_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    rows = tasks.get("tasks") or []
    if task_id:
        for task in rows:
            if task.get("id") != task_id:
                continue
            if task_status(state, task_id) in ("running", "completed", "failed", "interrupted"):
                return None
            if blocked_reason(task, state):
                return None
            return task
        return None
    for task in rows:
        tid = str(task.get("id") or "")
        if task_status(state, tid) != "pending":
            continue
        if blocked_reason(task, state):
            continue
        return task
    return None


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
    output = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""))
    return {"ok": proc.returncode == 0, "argv": argv, "cwd": str(cwd),
            "exit": proc.returncode, "duration_s": round(time.time() - started, 3),
            "error": "" if proc.returncode == 0 else f"exit {proc.returncode}",
            "output": _scrub(output)}


def _git(args: Sequence[str], *, cwd: Optional[Path] = None) -> Dict[str, Any]:
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, *args], cwd=str(cwd or ROOT), capture_output=True,
                          text=True, timeout=120)
    return {"ok": proc.returncode == 0, "exit": proc.returncode,
            "output": ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else ""))[-1200:]}


def _status_set(paths: Optional[Sequence[str]] = None) -> Set[str]:
    args = ["status", "--porcelain=v1", "-z", "--untracked-files=all"]
    if paths:
        args.extend(["--", *paths])
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, *args], cwd=str(ROOT), capture_output=True,
                          text=True, timeout=60)
    if proc.returncode != 0:
        raise LoopError(f"git status failed: {proc.stderr[:200]}")
    records = (proc.stdout or "").split("\0")
    out: Set[str] = set()
    skip_next = False
    for record in records:
        if not record:
            continue
        if skip_next:
            skip_next = False
            continue
        status = record[:2]
        if status and status[0] in ("R", "C"):
            skip_next = True
        path = record[3:] if len(record) > 3 else ""
        if path:
            out.add(path.replace("\\", "/"))
    return out


def _changed_since(sha: str, baseline_status: Set[str]) -> Set[str]:
    """Tracked diffs since the snapshot plus untracked files created after it."""
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, "diff", "--name-only", sha], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=60)
    tracked = {line.strip().replace("\\", "/") for line in (proc.stdout or "").splitlines()
               if line.strip()}
    after = _status_set()
    untracked = {p for p in after if p not in baseline_status}
    return {p for p in (tracked | untracked) if not _is_supervisor_path(p)}


def _exists_in_snapshot(sha: str, rel: str) -> bool:
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, "cat-file", "-e", f"{sha}:{rel}"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=30)
    return proc.returncode == 0


def take_baseline(task: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    from snapshot import manifest, snapshot  # noqa: E402
    targets = [str(p) for p in (task.get("write_paths") or [])]
    dirty = _status_set(targets)
    if dirty:
        raise LoopError(f"target paths already dirty; refusing to overwrite user work: "
                        f"{sorted(dirty)[:8]}")
    rec = snapshot(ROOT, f"continuous-{run_id}")
    backup_root = RUN_DIR / run_id / "baseline"
    backups: Dict[str, str] = {}
    for rel in targets:
        src = ROOT / rel
        if not src.is_file():
            continue
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        backups[rel] = str(dest.relative_to(ROOT))
    return {
        "sha": rec["sha"],
        "label": rec["label"],
        "write_paths": targets,
        "manifest": manifest(targets, ROOT),
        "byte_backup": backups,
        "status": sorted(_status_set()),
        "created_at": _now(),
    }


def restore_baseline(baseline: Dict[str, Any], paths: Optional[Sequence[str]] = None,
                     *, dry_run: bool = False) -> Dict[str, Any]:
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    from snapshot import manifest, restore  # noqa: E402
    sha = str(baseline.get("sha") or "")
    task_targets = list(baseline.get("write_paths") or [])
    requested = list(paths or task_targets)
    before_status = {p for p in (baseline.get("status") or [])
                     if not _is_supervisor_path(p)}
    current = {p for p in _status_set() if not _is_supervisor_path(p)}
    changed = sorted((current - before_status) | set(requested))
    restored: List[str] = []
    removed: List[str] = []
    byte_backup = dict(baseline.get("byte_backup") or {})
    for rel in task_targets:
        dest = ROOT / rel
        backup = byte_backup.get(rel)
        if backup and (ROOT / backup).is_file():
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / backup, dest)
            restored.append(rel)
        elif dest.exists():
            if not dry_run:
                dest.unlink()
            removed.append(rel)
    extras = [p for p in changed if p not in task_targets]
    tracked = [p for p in extras if _exists_in_snapshot(sha, p)]
    created = [p for p in extras if p not in baseline.get("status", [])]
    preserved = [p for p in extras if p not in tracked and p not in created]
    if preserved:
        raise LoopError("refusing to delete pre-existing untracked out-of-scope path: "
                        + ", ".join(sorted(preserved)[:8]))
    if not dry_run and task_targets:
        # A failed commit may have staged the task paths; unstage them before
        # comparing the working tree to the baseline.
        _git(["reset", "-q", "--", *task_targets])
    if extras and not dry_run:
        restore(ROOT, sha, tracked, remove_created=created)
    if not dry_run:
        after_hashes = manifest(task_targets, ROOT)
        expected = dict(baseline.get("manifest") or {})
        mismatched = [p for p in task_targets if after_hashes.get(p) != expected.get(p)]
        if mismatched:
            raise LoopError(f"restoration verification failed: {mismatched[:8]}")
        after_status = {p for p in _status_set() if not _is_supervisor_path(p)}
        if after_status != before_status:
            raise LoopError("restoration verification failed: working-tree status changed")
    return {"sha": sha, "restored": restored, "removed": removed,
            "dry_run": dry_run, "verified": not dry_run,
            "count": len(restored) + len(removed)}


def commit_task(task: Dict[str, Any], changed: Set[str], baseline: Dict[str, Any],
                *, dry_run: bool = False) -> Dict[str, Any]:
    allowed, refused = validate_commit_paths(task.get("commit_paths") or [])
    if refused:
        return {"ok": False, "error": "refused commit paths: " + "; ".join(refused)}
    outside = sorted(set(changed) - set(allowed))
    if outside:
        return {"ok": False, "error": "task changed paths outside commit_paths: " + ", ".join(outside[:8])}
    existing = [p for p in allowed if (ROOT / p).exists()]
    if not existing:
        return {"ok": True, "committed": False, "reason": "no commit paths exist"}
    if dry_run:
        return {"ok": True, "committed": False, "dry_run": True, "would_add": existing}
    if not _status_set(existing):
        return {"ok": True, "committed": False, "reason": "no changes in commit paths"}
    added = _git(["add", "--", *existing])
    if not added["ok"]:
        return {"ok": False, "error": added["output"][:500]}
    staged = _git(["-c", "core.whitespace=-trailing-space",
                   "diff", "--cached", "--check"])
    if not staged["ok"]:
        return {"ok": False, "error": "whitespace/conflict check failed: " + staged["output"][:500]}
    message = str(task.get("commit_message") or f"cycle: {task.get('name') or task.get('id')}")
    # --only commits exactly these paths; unrelated pre-existing staged work stays staged.
    commit = _git(["commit", "--only", "-m", message, "--", *existing])
    if not commit["ok"]:
        return {"ok": False, "error": commit["output"][:500]}
    head = _git(["rev-parse", "HEAD"])
    sha = head["output"].strip() if head["ok"] else ""
    contents = _git(["show", "--name-only", "--format=", sha])
    committed = {line.strip().replace("\\", "/") for line in contents["output"].splitlines()
                 if line.strip()}
    if committed - set(existing):
        return {"ok": False, "error": "commit contained unexpected paths: " +
                ", ".join(sorted(committed - set(existing))[:8])}
    return {"ok": True, "committed": True, "sha": sha[:12],
            "paths": sorted(committed), "output": commit["output"][:800]}


def _terminate_tree(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       capture_output=True, text=True, timeout=30)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except OSError:
            proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_ty_task(task: Dict[str, Any], run_id: str, run_dir: Path,
                timeout_s: int) -> Dict[str, Any]:
    task_path = run_dir / "task.json"
    result_path = run_dir / "result.json"
    heartbeat_path = run_dir / "heartbeat.json"
    _save_json(task_path, {
        "id": task.get("id"),
        "objective": task.get("objective"),
        "write_paths": task.get("write_paths") or [],
        "read_paths": task.get("read_paths") or [],
        "acceptance_commands": task.get("acceptance_commands") or [],
        "required_files": task.get("required_files") or [],
        "max_steps": task.get("max_steps") or 10,
        "max_repairs": task.get("max_repairs") or 0,
        "required_artifact": task.get("required_artifact") or "",
        "model": task.get("model") or "",
        "provider": task.get("provider") or "",
    })
    log = open(run_dir / "ty.log", "w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "ty_task_runner.py"),
         "--task", str(task_path), "--result", str(result_path),
         "--heartbeat", str(heartbeat_path), "--root", str(ROOT)],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True,
        creationflags=flags)
    deadline = time.time() + timeout_s
    stopped = ""
    try:
        while proc.poll() is None:
            if STOP_PATH.is_file():
                stopped = "STOP requested during execution"
                _terminate_tree(proc)
                break
            if time.time() > deadline:
                stopped = f"task timeout after {timeout_s}s"
                _terminate_tree(proc)
                break
            write_heartbeat(run_id, str(task.get("id")), "ty")
            time.sleep(1)
        if proc.poll() is None:
            _terminate_tree(proc)
    finally:
        log.close()
    result = _load_json(result_path, None)
    if not isinstance(result, dict):
        result = {"ok": False, "error": stopped or f"worker exited {proc.returncode} without result"}
    if stopped:
        result = {"ok": False, "error": stopped, **result}
    result["exit"] = proc.returncode
    return result


def run_checks(task: Dict[str, Any], *, dry_run: bool = False) -> List[Dict[str, Any]]:
    results = []
    for spec in task.get("checks") or []:
        name = str(spec.get("name") or "check")
        cmd = spec.get("cmd") or []
        cwd = (ROOT / str(spec.get("cwd") or ".")).resolve()
        res = run_command(cmd, cwd=cwd,
                          timeout=float(spec.get("timeout") or task.get("timeout_seconds") or 900),
                          dry_run=dry_run)
        results.append({"name": name, **res})
        if not res["ok"]:
            break
    return results


def execute_task(task: Dict[str, Any], state: Dict[str, Any], *,
                 dry_run: bool = False, no_commit: bool = False) -> Dict[str, Any]:
    task_id = str(task.get("id"))
    if STOP_PATH.is_file():
        raise LoopError("STOP present before dispatch")
    if dry_run:
        return {"status": "dry_run", "checks": run_checks(task, dry_run=True),
                "commit": None, "changed": []}
    run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = RUN_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = state["tasks"].setdefault(task_id, {})
    record.update({"status": "running", "run_id": run_id, "pid": os.getpid(),
                   "started_at": _now(), "reason": ""})
    _save_json(STATE_PATH, state)
    write_heartbeat(run_id, task_id, "dispatch")
    baseline = None
    changed: Set[str] = set()
    checks: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {"ok": False, "error": "not run"}
    try:
        if task.get("execution") == "ty":
            baseline = take_baseline(task, run_id)
            record["baseline"] = baseline
            _save_json(STATE_PATH, state)
            result = run_ty_task(task, run_id, run_dir,
                                 int(task.get("timeout_seconds") or 600))
            record["status"] = "verifying"
            _save_json(STATE_PATH, state)
            if not result.get("ok"):
                raise LoopError(str(result.get("error") or "Ty task failed"))
            after_status = _status_set()
            changed = _changed_since(baseline["sha"], set(baseline["status"]))
            out_of_scope = changed - set(baseline["write_paths"])
            if out_of_scope:
                raise LoopError("out-of-scope edits: " + ", ".join(sorted(out_of_scope)[:8]))
        checks = run_checks(task, dry_run=dry_run)
        if not all(c["ok"] for c in checks):
            failed = next(c for c in checks if not c["ok"])
            raise LoopError(f"acceptance failed: {failed['name']}: {failed.get('error')}")
        if baseline is not None:
            changed = _changed_since(baseline["sha"], set(baseline["status"]))
            outside = changed - set(baseline["write_paths"])
            if outside:
                raise LoopError("out-of-scope edits: " + ", ".join(sorted(outside)[:8]))
        if not no_commit:
            commit = commit_task(task, changed, baseline or {}, dry_run=dry_run)
            if not commit.get("ok"):
                raise LoopError("commit failed: " + str(commit.get("error")))
        else:
            commit = {"ok": True, "committed": False, "reason": "no-commit"}
        record.update({"status": "completed", "finished_at": _now(),
                       "commit": commit.get("sha") or "", "reason": ""})
        _save_json(STATE_PATH, state)
        return {"status": "completed", "checks": checks, "commit": commit,
                "changed": sorted(changed), "ty": result}
    except Exception as exc:  # noqa: BLE001 - restore, record, stop
        reason = str(exc)[:1000]
        restoration = None
        if baseline is not None:
            try:
                changed = _changed_since(baseline["sha"], set(baseline["status"]))
                restoration = restore_baseline(
                    baseline, paths=sorted(set(baseline["write_paths"]) | changed))
            except Exception as restore_exc:  # noqa: BLE001
                reason += f"; RESTORATION FAILED: {restore_exc}"
                record.update({"status": "failed", "finished_at": _now(),
                               "reason": reason, "restoration": "failed"})
                _save_json(STATE_PATH, state)
                return {"status": "failed", "error": reason, "checks": checks,
                        "restoration": "failed"}
        record.update({"status": "failed", "finished_at": _now(),
                       "reason": reason, "restoration": "ok" if restoration else "not-needed"})
        _save_json(STATE_PATH, state)
        return {"status": "failed", "error": reason, "checks": checks,
                "restoration": restoration, "ty": result}
    finally:
        write_heartbeat(run_id, task_id, "finished")


def status_report(tasks: Dict[str, Any], state: Dict[str, Any],
                  ledger_path: Path = LEDGER_PATH) -> Dict[str, Any]:
    rows = []
    if ledger_path.is_file():
        for line in ledger_path.read_text(encoding="utf-8").splitlines()[-12:]:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    buckets = {k: [] for k in ("eligible", "blocked", "failed", "interrupted",
                               "running", "completed", "pending")}
    for task in tasks.get("tasks") or []:
        tid = str(task.get("id") or "")
        status = task_status(state, tid)
        reason = blocked_reason(task, state)
        if status == "completed":
            buckets["completed"].append(tid)
        elif status in ("running", "verifying"):
            buckets["running"].append(tid)
        elif status in ("failed", "interrupted"):
            buckets[status].append({"id": tid, "reason": (state["tasks"].get(tid) or {}).get("reason")})
        elif reason:
            buckets["blocked"].append({"id": tid, "reason": reason})
        elif status == "pending":
            buckets["eligible"].append(tid)
            buckets["pending"].append(tid)
        else:
            buckets["pending"].append(tid)
    return {"tasks": [{"id": t.get("id"), "status": task_status(state, str(t.get("id"))),
                       "reason": blocked_reason(t, state)} for t in tasks.get("tasks") or []],
            "buckets": buckets, "last_cycles": rows}


def resume_task(task_id: str, tasks: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    record = (state.get("tasks") or {}).get(task_id)
    if not record or record.get("status") not in ("failed", "interrupted"):
        raise LoopError(f"task {task_id!r} is not failed/interrupted")
    baseline = record.get("baseline")
    if isinstance(baseline, dict) and baseline.get("sha"):
        restore_baseline(baseline)
    record["status"] = "pending"
    record["reason"] = "operator resume"
    _save_json(STATE_PATH, state)
    return record


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", default="", help="run one task id")
    ap.add_argument("--once", action="store_true", help="run at most one task")
    ap.add_argument("--max-cycles", type=int, default=0,
                    help="0 = all eligible (still bounded by --max-tasks/deadline)")
    ap.add_argument("--max-tasks", type=int, default=MAX_IMPLEMENTATION_TASKS,
                    help="maximum Ty implementation tasks (default 3)")
    ap.add_argument("--deadline-minutes", type=float, default=CAMPAIGN_DEADLINE_MIN)
    ap.add_argument("--dry-run", action="store_true", help="print commands, write nothing")
    ap.add_argument("--no-commit", action="store_true", help="verify only")
    ap.add_argument("--resume", default="", help="explicitly resume a failed/interrupted task id")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    tasks = load_tasks()
    state = load_state()
    recover_interrupted(state)
    if args.status:
        print(json.dumps(status_report(tasks, state), indent=2))
        return 0
    guard = guardrails()
    if not guard["ok"] and not args.dry_run:
        print(json.dumps({"ok": False, "guardrails": guard}, indent=2))
        return 2
    if args.resume:
        try:
            resume_task(args.resume, tasks, state)
        except LoopError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2

    started = time.time()
    deadline_s = max(1.0, float(args.deadline_minutes) * 60.0)
    max_tasks = max(1, int(args.max_tasks))
    limit = 1 if args.once else max(0, int(args.max_cycles))
    implementation_done = 0
    completed = 0
    run_id = f"campaign-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    lock = None
    try:
        if not args.dry_run:
            lock = acquire_lock(run_id)
        while True:
            if time.time() - started > deadline_s:
                print(json.dumps({"ok": False, "error": "campaign deadline reached"}))
                break
            if limit and completed >= limit:
                break
            task = select_task(tasks, state, args.task or None)
            if task is None:
                break
            if task.get("execution") == "ty" and implementation_done >= max_tasks:
                print(json.dumps({"ok": False, "error": "implementation task budget reached",
                                  "max_tasks": max_tasks}))
                break
            print(f"[*] cycle {task.get('id')}: {task.get('name')}")
            result = execute_task(task, state, dry_run=args.dry_run,
                                  no_commit=args.no_commit)
            print(f"    {result.get('status')} ({len(result.get('checks') or [])} checks)")
            if args.dry_run:
                print(json.dumps(result, indent=2)[:4000])
                return 0
            if not args.dry_run:
                append_ledger({"run_id": run_id, "task": task.get("id"),
                               "name": task.get("name"), "status": result.get("status"),
                               "started_at": _now(), "finished_at": _now(),
                               "checks": result.get("checks"), "commit": result.get("commit"),
                               "changed": result.get("changed"),
                               "restoration": result.get("restoration"),
                               "error": _scrub(str(result.get("error") or ""))})
            if result.get("status") != "completed":
                print(json.dumps(result, indent=2)[:4000])
                return 1
            if task.get("execution") == "ty":
                implementation_done += 1
            completed += 1
            if args.task:
                break
    except LoopError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    finally:
        if lock is not None and not args.dry_run:
            release_lock()
    report = status_report(tasks, state)
    print(json.dumps({"ok": True, "completed": completed,
                      "implementation_tasks": implementation_done,
                      "buckets": report["buckets"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
