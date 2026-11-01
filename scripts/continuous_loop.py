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
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
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
CAMPAIGN_HEARTBEAT_PATH = ROOT / "state" / "continuous_loop_campaign.json"
READINESS_PATH = ROOT / "state" / "autonomy_readiness.json"
CHECKPOINT_ROOT = ROOT / "state" / "checkpoints"
AUTONOMY_LOG_DIR = ROOT / "reports"
CAMPAIGN_MANIFEST_DIR = ROOT / "state" / "campaigns"
MIN_FREE_DISK_GB = 10.0
MIN_FREE_RAM_GB = 3.0
#: Pre-load precondition per execution profile. An uncharacterised profile gets the
#: conservative default: never load a model into a host that cannot hold it plus the
#: resident floor. Measured, this box needs ~1.6-2.4 GB for the qwen lane, so 6.0 GB
#: leaves a real margin. Lowering this to make a reading pass is not allowed.
MIN_PRELOAD_RAM_GB_BY_PROFILE = {"qwen2.5-coder:3b": 6.0}
MIN_PRELOAD_RAM_GB_DEFAULT = 6.0
MODEL_RESIDENT_EVIDENCE = ROOT / "state" / "evidence"
RESIDENT_EVIDENCE_MAX_AGE_MIN = 60
MAX_TASK_TIMEOUT_S = 900
MAX_REPAIRS = 1
MAX_IMPLEMENTATION_TASKS = 8
CAMPAIGN_DEADLINE_MIN = 90
MAX_CONSECUTIVE_FAILURES = 2
STALE_LOCK_S = 300
HEARTBEAT_STALE_S = 120
OLLAMA_TAGS_URL = "http://127.0.0.1:11434/api/tags"
POLICY_PATHS = (
    "AGENTS.md",
    "config/continuous_loop_tasks.json",
    "scripts/continuous_loop.py",
    "scripts/ty_task_runner.py",
    "tools/autonomy_patches.py",
)
MODEL_RAM_HEADROOM_GB = 1.0
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _policy_bytes(data: bytes) -> bytes:
    # Windows checkouts may carry CRLF while the git blob carries LF. A policy
    # fingerprint must compare content, not the checkout's line ending.
    return data.replace(b"\r\n", b"\n")


def _sha256_file(path: Path) -> Optional[str]:
    try:
        return _sha256_bytes(_policy_bytes(path.read_bytes()))
    except OSError:
        return None


def _git_show(rel: str, rev: str = "HEAD") -> Optional[bytes]:
    git = shutil.which("git") or "git"
    proc = subprocess.run([git, "show", f"{rev}:{rel}"], cwd=str(ROOT),
                          capture_output=True, timeout=60)
    return proc.stdout if proc.returncode == 0 else None


def policy_fingerprint(paths: Sequence[str] = POLICY_PATHS) -> Dict[str, Any]:
    """Compare the working policy/registry bytes with the committed envelope.

    The approved fingerprint is the committed HEAD copy, never a value the
    running agent writes for itself. A policy or registry edit must be committed
    (and therefore reviewed) before a campaign can start.
    """
    files = []
    match = True
    for rel in paths:
        p = ROOT / rel
        if not p.is_file():
            continue
        working = _sha256_file(p)
        approved_blob = _git_show(rel)
        approved = (_sha256_bytes(_policy_bytes(approved_blob))
                    if approved_blob is not None else None)
        same = bool(working and approved and working == approved)
        match = match and same
        files.append({"path": rel, "working": working, "approved": approved,
                      "match": same})
    if not files:
        match = False
    digest = _sha256_bytes(json.dumps(files, sort_keys=True).encode("utf-8"))
    return {"ok": match, "files": files, "digest": digest}


def _ollama_tags(timeout: float = 5.0) -> Dict[str, Any]:
    """Read the installed model set from the local Ollama daemon only."""
    try:
        with urllib.request.urlopen(OLLAMA_TAGS_URL, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"local Ollama unavailable: {exc}", "models": []}
    models = []
    for row in data.get("models") or []:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        models.append({
            "name": name,
            "size_bytes": int(row.get("size") or 0),
            "size_gb": round(float(row.get("size") or 0) / (1024 ** 3), 2),
            "modified_at": row.get("modified_at"),
        })
    return {"ok": True, "models": models, "error": ""}


def _free_ram_gb() -> Optional[float]:
    try:
        import psutil  # type: ignore
        return round(psutil.virtual_memory().available / (1024 ** 3), 3)
    except Exception:  # noqa: BLE001
        return None


def queue_profiles() -> List[Dict[str, Any]]:
    """Distinct (model, num_ctx) execution profiles the authorized queue will use.

    Readiness must measure the profile a task will actually run, not a different
    default: a 32768-context probe and an 8192-context dispatch are not the same
    memory claim.
    """
    profiles: List[Dict[str, Any]] = []
    try:
        for task in (load_tasks().get("tasks") or []):
            if (task.get("authorized") is True
                    and str(task.get("execution") or "") == "ty"
                    and task.get("model")):
                profile = {"model": str(task["model"]),
                           "num_ctx": int(task.get("num_ctx") or 0)}
                if profile not in profiles:
                    profiles.append(profile)
    except Exception:  # noqa: BLE001 - an unreadable queue is reported by the gate
        pass
    return profiles[:3]


def evaluate_profiles(profiles: List[Dict[str, Any]], *, free_gb: float,
                      measure: Any = None) -> Dict[str, Any]:
    """Pre-load gate then resident measurement, per execution profile.

    A profile whose pre-load precondition is not met is NOT loaded: measuring it
    anyway would be a pointless load on a host that cannot hold it, and a NO-GO
    reading from a starved host proves nothing.
    """
    measure = measure or measure_model_resident
    free_gb = float(free_gb or 0.0)
    preload_ok = True
    details: List[str] = []
    out_profiles: List[Dict[str, Any]] = []
    for profile in profiles:
        need = MIN_PRELOAD_RAM_GB_BY_PROFILE.get(profile["model"],
                                                 MIN_PRELOAD_RAM_GB_DEFAULT)
        entry = dict(profile, preload_min_gb=need)
        if free_gb < need:
            preload_ok = False
            entry["measured"] = {"ok": False, "evidence": "", "record": {
                "model": profile["model"], "num_ctx": profile.get("num_ctx") or None,
                "verdict": "PRELOAD-MISSED", "min_available_gb": None}}
            details.append(f"{profile['model']} ctx{profile.get('num_ctx') or 'default'}: "
                           f"pre-load {free_gb:.2f} GB < {need:.1f} GB required - probe not run")
        else:
            entry["measured"] = measure(profile["model"],
                                        num_ctx=(profile.get("num_ctx") or None))
            rec = entry["measured"].get("record") or {}
            details.append(f"{profile['model']} ctx{profile.get('num_ctx') or 'default'}: "
                           f"min {rec.get('min_available_gb')} GB "
                           f"({rec.get('resident_system_gb')} GB system) {rec.get('verdict')}")
        out_profiles.append(entry)
    resident_ok = preload_ok and all(
        ((p["measured"].get("record") or {}).get("verdict") == "FLOOR-MET")
        for p in out_profiles)
    return {"ok": resident_ok, "preload_ok": preload_ok,
            "profiles": out_profiles, "reason": "; ".join(details)}


def ram_floor_breached(free_gb: Optional[float], consecutive: int, *,
                       floor: float = MIN_FREE_RAM_GB, needed: int = 2) -> bool:
    """Two consecutive sub-floor samples end a model task; one is not enough."""
    return bool(free_gb is not None and free_gb < floor
                and (consecutive + 1) >= max(1, int(needed)))


def model_slug(model: str) -> str:
    """A filesystem-safe fragment of a model id (`bojo:gpu-orig` -> `bojo_gpu_orig`)."""
    out = "".join(ch if ch.isalnum() else "_" for ch in str(model or ""))
    return out.strip("_") or "model"


def measure_model_resident(model: str, *, floor: Optional[float] = None,
                           timeout: float = 300.0,
                           num_ctx: Optional[int] = None) -> Dict[str, Any]:
    """Load the lane, generate, and record the LOWEST free RAM while it was resident.

    The gate must never decide from pre-load RAM: `bojo:gpu-orig` is 2.25 GB on
    disk and, when the backend runs it on the CPU, it takes 2.7 GB of system RAM
    with it. Only a measurement during generation answers the question.
    """
    floor = MIN_FREE_RAM_GB if floor is None else float(floor)
    MODEL_RESIDENT_EVIDENCE.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ctx_tag = f"ctx{int(num_ctx)}" if num_ctx else "ctxdefault"
    out_path = MODEL_RESIDENT_EVIDENCE / (
        f"model_resident_{model_slug(model)}_{ctx_tag}_{stamp}.json")
    cmd = ["python", str(ROOT / "tools" / "measure_model_resident.py"),
           "--model", str(model), "--floor", f"{floor}", "--json", "--out", str(out_path)]
    if num_ctx:
        cmd.extend(["--num-ctx", str(int(num_ctx))])
    res = run_command(cmd, timeout=timeout)
    text = str(res.get("output") or "")
    record: Dict[str, Any] = {}
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            record = json.loads(text[start:end + 1])
        except ValueError:
            record = {}
    ok = bool(record.get("verdict") == "FLOOR-MET"
              and float(record.get("min_available_gb") or 0.0) >= floor
              and int(record.get("tokens") or 0) > 0)
    return {"ok": ok, "record": record, "evidence": str(out_path),
            "floor_gb": floor, "command": cmd, "raw_output": text[-600:]}


def resident_evidence(model: str, *, max_age_min: float = RESIDENT_EVIDENCE_MAX_AGE_MIN,
                      num_ctx: Optional[int] = None) -> Dict[str, Any]:
    """The newest measured residency record for `model` (and context), fresh or not."""
    if not model:
        return {"ok": False, "reason": "no model lane resolved", "age_min": None}
    newest: Optional[Path] = None
    newest_mtime = 0.0
    newest_record: Dict[str, Any] = {}
    if MODEL_RESIDENT_EVIDENCE.is_dir():
        for path in MODEL_RESIDENT_EVIDENCE.glob("model_resident_*.json"):
            try:
                mtime = path.stat().st_mtime
                if mtime <= newest_mtime:
                    continue
                record = _load_json(path, None) or {}
            except OSError:
                continue
            if str(record.get("model") or "") != str(model):
                continue
            if num_ctx is not None and int(record.get("num_ctx") or 0) != int(num_ctx):
                continue
            newest, newest_mtime, newest_record = path, mtime, record
    if newest is None:
        return {"ok": False, "reason": "no measured residency on record",
                "age_min": None}
    age_min = round((time.time() - newest_mtime) / 60.0, 1)
    verdict = str(newest_record.get("verdict") or "")
    ok = (verdict == "FLOOR-MET"
          and float(newest_record.get("min_available_gb") or 0.0) >= MIN_FREE_RAM_GB
          and age_min <= float(max_age_min))
    reason = (f"measured {verdict}: min free {newest_record.get('min_available_gb')} GB "
              f"(floor {MIN_FREE_RAM_GB}), resident {newest_record.get('resident_total_gb')} GB "
              f"({newest_record.get('resident_system_gb')} GB system), ctx "
              f"{newest_record.get('num_ctx') or 'default'}, {age_min} min old")
    return {"ok": ok, "reason": reason, "age_min": age_min,
            "path": str(newest), "record": newest_record}


def resolve_lane(task: Optional[Dict[str, Any]] = None, *,                 tags: Optional[Dict[str, Any]] = None,
                 free_ram_gb: Optional[float] = None) -> Dict[str, Any]:
    """Pick the best installed chat lane that fits, re-checked at dispatch.

    `bojo` is the proven Ty tool-loop lane and the smallest chat model present;
    larger vision/7B lanes are not selected while they would crowd the RAM
    floor. The model is never downloaded and no paid provider is considered.
    """
    task = task or {}
    if str(task.get("execution") or "prebuilt") != "ty":
        return {"ok": True, "provider": "prebuilt", "model": "", "reason":
                "prebuilt task; no model call", "free_ram_gb": free_ram_gb,
                "installed": []}
    tags = tags if tags is not None else _ollama_tags()
    if not tags.get("ok"):
        return {"ok": False, "reason": tags.get("error") or "no local model lane",
                "free_ram_gb": free_ram_gb, "installed": []}
    free = float(free_ram_gb if free_ram_gb is not None else (_free_ram_gb() or 0.0))
    installed = {m["name"]: m for m in tags.get("models") or []}
    requested = str(task.get("model") or "").strip()
    # Capability rank, not disk order. Bojo is the proven JSON/tool-call lane.
    rank = {"bojo": 30, "bojo:gpu-orig": 28, "qwen3.5:2b": 22,
            "qwen2.5vl:7b": 10}
    candidates = []
    for name, info in installed.items():
        if name not in rank and not requested:
            continue
        estimate = max(0.1, float(info.get("size_gb") or 0) * 0.9)
        fits = estimate <= max(0.0, free - MODEL_RAM_HEADROOM_GB)
        candidates.append({"model": name, "rank": rank.get(name, 1),
                           "estimated_ram_gb": round(estimate, 2),
                           "fits": fits})
    candidates.sort(key=lambda c: (c["rank"], -c["estimated_ram_gb"]), reverse=True)
    chosen = next((c for c in candidates if c["fits"] and (not requested or c["model"] == requested)), None)
    if chosen is None and requested:
        chosen = next((c for c in candidates if c["fits"]), None)
    if chosen is None:
        return {"ok": False,
                "reason": (f"no installed chat lane fits: free RAM {free:.2f} GB, "
                           f"headroom {MODEL_RAM_HEADROOM_GB:.2f} GB"),
                "free_ram_gb": free, "installed": candidates}
    post_headroom = round(free - float(chosen["estimated_ram_gb"]), 2)
    return {"ok": True, "provider": "ollama", "model": chosen["model"],
            "reason": (f"{chosen['model']} is installed and proven for the Ty tool loop; "
                       f"free RAM {free:.2f} GB at dispatch; the {chosen['estimated_ram_gb']:.2f} GB "
                       f"figure is a PRE-LOAD estimate only - residency is gated by the "
                       f"measured `model-resident` check, not by this number"),
            "free_ram_gb": free, "post_load_headroom_gb": post_headroom,
            "estimate_not_measurement": True,
            "installed": candidates}


def _copy_sqlite(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src), timeout=30)
    try:
        dst_conn = sqlite3.connect(str(dest))
        try:
            src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _checkpoint_targets() -> List[Path]:
    out: List[Path] = []
    for pattern in ("Northstar_backend/data/*.db", "data/*.db"):
        out.extend(sorted(ROOT.glob(pattern)))
    out.extend(sorted((ROOT / "config").glob("*.json")))
    return [p for p in out if p.is_file()]


def create_rollback_checkpoint(label: str = "ready") -> Dict[str, Any]:
    """Fresh checkpoint from the current working tree, DBs, configs and models."""
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    from snapshot import snapshot  # noqa: E402
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = CHECKPOINT_ROOT / f"{stamp}-{label}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rec = snapshot(ROOT, f"ready-{stamp}")
    git = shutil.which("git") or "git"
    head = subprocess.run([git, "rev-parse", "HEAD"], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=60).stdout.strip()
    branch = _branch()
    status = subprocess.run([git, "status", "--porcelain=v1", "--untracked-files=all"],
                            cwd=str(ROOT), capture_output=True, text=True, timeout=60)
    staged = subprocess.run([git, "diff", "--cached", "--name-only"], cwd=str(ROOT),
                            capture_output=True, text=True, timeout=60)
    patch = subprocess.run([git, "diff", "--binary", "HEAD"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=120)
    (out_dir / "working_tree.txt").write_text(status.stdout or "", encoding="utf-8")
    (out_dir / "staged_paths.txt").write_text(staged.stdout or "", encoding="utf-8")
    (out_dir / "uncommitted.patch").write_text(patch.stdout or "", encoding="utf-8")
    files = {}
    errors = []
    for target in _checkpoint_targets():
        rel = target.relative_to(ROOT).as_posix()
        dest = out_dir / "files" / rel
        try:
            if target.suffix.lower() == ".db":
                _copy_sqlite(target, dest)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, dest)
            files[rel] = _sha256_file(dest)
        except (OSError, sqlite3.Error) as exc:
            errors.append({"path": rel, "error": str(exc)[:300]})
    tags = _ollama_tags()
    (out_dir / "model_manifest.json").write_text(json.dumps(tags, indent=2), encoding="utf-8")
    record = {
        "schema": "northstar.rollback_checkpoint.v1",
        "label": label, "created_at": _now(), "dir": str(out_dir.relative_to(ROOT)),
        "head": head, "branch": branch, "snapshot_sha": rec.get("sha"),
        "snapshot_clean": rec.get("clean_tree"), "files": files, "errors": errors,
        "model_manifest": {"ok": tags.get("ok"), "models": tags.get("models") or [],
                           "error": tags.get("error") or ""},
        "uncommitted_patch_bytes": len((out_dir / "uncommitted.patch").read_bytes()),
        "staged_paths": [x for x in (staged.stdout or "").splitlines() if x.strip()],
    }
    _save_json(out_dir / "checkpoint.json", record)
    return record


def sandbox_restore_demo() -> Dict[str, Any]:
    """Disposable git repo: modify/delete/create, restore, compare bytes."""
    sys.path.insert(0, str(ROOT / "Northstar_backend"))
    from snapshot import restore, snapshot  # noqa: E402
    with tempfile.TemporaryDirectory(prefix="northstar-loop-ready-") as tmp:
        root = Path(tmp)
        git = shutil.which("git") or "git"
        def g(*args: str) -> subprocess.CompletedProcess:
            return subprocess.run([git, "-c", "core.autocrlf=false", *args], cwd=str(root),
                                  capture_output=True, text=True, timeout=60)
        if g("init", "-q").returncode != 0:
            return {"ok": False, "error": "git init failed"}
        g("config", "user.email", "loop@northstar.invalid")
        g("config", "user.name", "loop readiness")
        (root / "keep.txt").write_text("keep-original\n", encoding="utf-8")
        (root / "gone.txt").write_text("gone-original\n", encoding="utf-8")
        g("add", "keep.txt", "gone.txt")
        if g("commit", "-m", "base").returncode != 0:
            return {"ok": False, "error": "git commit failed"}
        sha = snapshot(root, "ready-sandbox")["sha"]
        before = {p.name: p.read_bytes() for p in (root / "keep.txt", root / "gone.txt")}
        (root / "keep.txt").write_text("broken\n", encoding="utf-8")
        (root / "gone.txt").unlink()
        (root / "created.txt").write_text("new\n", encoding="utf-8")
        restore(root, sha, ["keep.txt", "gone.txt"], remove_created=["created.txt"])
        after = {p.name: p.read_bytes() for p in (root / "keep.txt", root / "gone.txt")}
        return {"ok": before == after and not (root / "created.txt").exists(),
                "bytes_match": before == after,
                "created_removed": not (root / "created.txt").exists(),
                "sha": sha}

def _stop_probe() -> Dict[str, Any]:
    """Prove the STOP file actually blocks dispatch, without touching the real STOP."""
    global STOP_PATH
    old = STOP_PATH
    try:
        with tempfile.TemporaryDirectory(prefix="northstar-stop-") as tmp:
            STOP_PATH = Path(tmp) / "STOP"
            STOP_PATH.write_text("stop", encoding="utf-8")
            try:
                execute_task({"id": "stop-probe", "execution": "prebuilt",
                              "authorized": True, "risk": "low",
                              "commit_paths": [], "checks": []},
                             {"completed": {}, "tasks": {}})
            except LoopError as exc:
                return {"ok": "STOP" in str(exc),
                        "detail": "STOP blocked dispatch in isolated probe"}
            return {"ok": False, "detail": "STOP did not block dispatch"}
    finally:
        STOP_PATH = old


def _probe_writable(path: Path) -> Dict[str, Any]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".autonomy_ready_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"ok": True, "detail": str(path)}
    except OSError as exc:
        return {"ok": False, "detail": str(exc)[:300]}


def readiness_gate(*, make_checkpoint: bool = True,
                   run_tests: bool = True) -> Dict[str, Any]:
    """Full GO/NO-GO preflight. Every failure names its remediation."""
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, remediation: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail,
                       "remediation": "" if ok else remediation})

    stop_absent = not (ROOT / "STOP").is_file()
    add("stop-file", stop_absent, "STOP absent" if stop_absent else "STOP present",
        "remove STOP only when you intend to allow dispatch")
    stop = _stop_probe()
    add("stop-mechanism", stop["ok"], stop.get("detail") or "",
        "restore the STOP check in execute_task before launching")

    disk = shutil.disk_usage(ROOT).free / (1024 ** 3)
    add("disk-floor", disk >= MIN_FREE_DISK_GB, f"{disk:.2f} GB free",
        f"free at least {MIN_FREE_DISK_GB:.0f} GB on the repo volume")
    ram = _free_ram_gb()
    add("ram-floor", ram is not None and ram >= MIN_FREE_RAM_GB,
        f"{ram:.2f} GB free" if ram is not None else "RAM probe unavailable",
        f"free at least {MIN_FREE_RAM_GB:.0f} GB RAM (stop background models/apps)")
    state_probe = _probe_writable(ROOT / "state")
    add("state-writable", state_probe["ok"], state_probe.get("detail") or "",
        "grant write access to state/")
    reports_probe = _probe_writable(ROOT / "reports")
    add("reports-writable", reports_probe["ok"], reports_probe.get("detail") or "",
        "grant write access to reports/")
    ledger_ok = True
    try:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LEDGER_PATH, "a", encoding="utf-8") as fh:
            fh.write("")
    except OSError:
        ledger_ok = False
    add("ledger-writable", ledger_ok, str(LEDGER_PATH),
        "make reports/evaluation_ledger.jsonl writable")

    fp = policy_fingerprint()
    add("policy-fingerprint", fp["ok"],
        f"{sum(1 for f in fp['files'] if f['match'])}/{len(fp['files'])} policy files match HEAD",
        "commit the reviewed policy/registry/code envelope first (working copy must equal HEAD)")
    add("git-present", bool(shutil.which("git")),
        "git executable found" if shutil.which("git") else "git missing",
        "install git and retry")

    branch = _branch()
    add("branch", branch not in PROTECTED_BRANCHES and not branch.startswith("release/"),
        branch or "(unknown branch)", "switch to a dev/feature branch; protected branches are refused")

    status_probe = _git(["status", "--porcelain=v1", "--untracked-files=all"])
    add("working-tree-recorded", status_probe.get("ok", False),
        "git status captured" if status_probe.get("ok") else status_probe.get("output", "")[:300],
        "make git status work in this repository")

    lock = _read_lock()
    lock_ok = True
    lock_detail = "no lock"
    if lock:
        pid = int(lock.get("pid") or 0)
        if _is_pid_alive(pid):
            lock_ok = False
            lock_detail = f"live supervisor pid {pid}"
        else:
            lock_detail = f"stale lock from dead pid {pid}; reclaimable"
    add("lock", lock_ok, lock_detail,
        "wait for the live supervisor or remove only a proven-stale lock")
    add("stale-lock-recovery", True,
        "stale lock reclaim is covered by test_lock_refuses_a_live_owner_and_reclaims_a_dead_one",
        "")

    checkpoint = None
    if make_checkpoint:
        try:
            checkpoint = create_rollback_checkpoint("ready")
            cp_ok = not checkpoint.get("errors")
            add("rollback-checkpoint", cp_ok,
                f"{checkpoint['dir']} ({len(checkpoint.get('files') or {})} files)",
                "close DB handles and fix checkpoint copy errors: " +
                json.dumps(checkpoint.get("errors"))[:300])
        except Exception as exc:  # noqa: BLE001
            add("rollback-checkpoint", False, str(exc)[:300],
                "ensure .git and state/checkpoints are writable")
    demo = sandbox_restore_demo()
    add("sandbox-restore", demo.get("ok", False), json.dumps(demo)[:300],
        "repair snapshot/restore before campaign")

    tags = _ollama_tags()
    # The lane that matters is the one the authorized queue will actually run, not
    # a default the campaign never dispatches.
    profiles = queue_profiles()
    queue_models = [p["model"] for p in profiles]
    lane = resolve_lane({"execution": "ty", "model": (queue_models[0] if queue_models else "")},
                        tags=tags, free_ram_gb=ram)
    add("model-lane", lane.get("ok", False),
        lane.get("reason", "") + (f" | {lane.get('model')}" if lane.get("model") else ""),
        "start local Ollama (`ollama serve`) and keep a chat lane installed; no downloads are allowed")

    # Residency is measured, never inferred. The lane above is chosen from
    # pre-load free RAM and a disk-size estimate; that is exactly how a 2.09 GB
    # "post-load headroom" was reported while the measured figure was 1.19 GB.
    # EVERY model the authorized queue names is measured: a campaign dispatches
    # tasks, not a default lane.
    resident: Dict[str, Any] = {"ok": False, "reason": "no lane to measure", "profiles": []}
    if profiles:
        free_now = float(ram if ram is not None else (_free_ram_gb() or 0.0))
        resident = evaluate_profiles(profiles, free_gb=free_now)
        add("model-preload", resident["preload_ok"],
            f"free {free_now:.2f} GB; " + "; ".join(
                f"{p['model']} needs {p['preload_min_gb']:.1f}"
                for p in resident["profiles"]),
            "close the interactive session or free RAM before loading a model; "
            "the precondition is not lowered to make a reading pass")
        add("model-resident", resident["ok"], resident["reason"],
            (f"the {MIN_FREE_RAM_GB:.0f} GB floor is not lowered: free RAM, run the lane on "
             f"the GPU, or install a smaller lane, then re-run --ready"))
    else:
        add("model-preload", False, resident.get("reason", "no ollama lane resolved"),
            "resolve a model lane first")
        add("model-resident", False, resident.get("reason", "no ollama lane resolved"),
            "resolve a model lane first; a Ty campaign cannot start without measured residency")

    tests_ok = True
    test_detail = "not run"
    if run_tests:
        test_cmd = ["python", "-m", "pytest",
                    "Northstar_backend/test_continuous_loop.py::test_commit_paths_allowlist_and_denylist",
                    "Northstar_backend/test_continuous_loop.py::test_scrub_redacts_secret_shaped_text",
                    "Northstar_backend/test_continuous_loop.py::test_commit_task_preserves_pre_existing_staged_work",
                    "-q"]
        res = run_command(test_cmd, timeout=180)
        tests_ok = bool(res.get("ok"))
        test_detail = (res.get("output") or "")[-500:]
    add("commit-and-redaction-tests", tests_ok, test_detail,
        "fix the failing commit-path or secret-redaction test before launch")

    result = {
        "schema": "northstar.autonomy_readiness.v1",
        "verdict": "GO" if all(c["ok"] for c in checks) else "NO-GO",
        "ok": all(c["ok"] for c in checks),
        "checked_at": _now(), "branch": branch,
        "checkpoint": checkpoint, "model_lane": lane, "model_tags": tags,
        "model_resident": resident,
        "policy_fingerprint": fp, "checks": checks,
        "failures": [c for c in checks if not c["ok"]],
    }
    _save_json(READINESS_PATH, result)
    return result


def render_readiness(result: Dict[str, Any], as_json: bool = False) -> str:
    if as_json:
        return json.dumps(result, indent=2)
    lines = [f"{result.get('verdict', 'NO-GO')} — autonomy readiness"]
    for c in result.get("checks") or []:
        lines.append(f"  [{'PASS' if c['ok'] else 'FAIL'}] {c['name']}: {c['detail']}")
        if not c["ok"]:
            lines.append(f"         remediation: {c.get('remediation') or 'none given'}")
    cp = result.get("checkpoint") or {}
    lines.append(f"checkpoint: {cp.get('dir') or 'none'}")
    lane = result.get("model_lane") or {}
    lines.append(f"lane: {lane.get('provider')}/{lane.get('model') or '-'} — {lane.get('reason')}")
    return "\n".join(lines)


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


def _terminate_pid(pid: int) -> None:
    if pid <= 0 or not _is_pid_alive(pid):
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                       capture_output=True, text=True, timeout=30)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


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
        worker_pid = 0
        run_id = str(record.get("run_id") or "")
        if run_id:
            worker = _load_json(RUN_DIR / run_id / "worker.json", {}) or {}
            apply_worker = _load_json(RUN_DIR / run_id / "apply_worker.json", {}) or {}
            worker_pid = int(worker.get("pid") or apply_worker.get("pid") or 0)
        was_alive = bool(worker_pid and _is_pid_alive(worker_pid))
        if was_alive:
            _terminate_pid(worker_pid)
        record["status"] = "interrupted"
        record["reason"] = "stale heartbeat or dead owner process"
        record["interrupted_at"] = _now()
        record["orphan_worker_pid"] = worker_pid
        recovered.append({"task": task_id, "pid": pid, "heartbeat_age": age,
                          "worker_pid": worker_pid,
                          "worker_terminated": was_alive})
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
    apply_commands = task.get("apply_commands") or []
    precheck_commands = task.get("precheck_commands") or []
    if apply_commands and not task.get("write_paths"):
        errors.append("an apply task needs write_paths")
    if apply_commands and not precheck_commands:
        errors.append("an apply task needs at least one precheck_commands (fails before the fix)")
    for cmd in apply_commands:
        reason = check_command(cmd)
        if reason:
            errors.append(f"apply command: {reason}")
    for cmd in precheck_commands:
        reason = check_command(cmd)
        if reason:
            errors.append(f"precheck command: {reason}")
    if int(task.get("schema_version") or 1) >= 2:
        if not str(task.get("authorization_note") or "").strip():
            errors.append("v2 task needs an authorization_note")
        if not str(task.get("objective") or "").strip():
            errors.append("v2 task needs an objective")
        if not str(task.get("risk_class") or task.get("risk") or "").strip():
            errors.append("v2 task needs a risk class")
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
        try:
            backups[rel] = str(dest.relative_to(ROOT))
        except ValueError:
            backups[rel] = str(dest)
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
        backup_path = Path(backup) if backup else None
        if backup_path is not None and not backup_path.is_absolute():
            backup_path = ROOT / backup_path
        if backup_path is not None and backup_path.is_file():
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(backup_path, dest)
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
                timeout_s: int, runner_script: Optional[Path] = None) -> Dict[str, Any]:
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
        "max_protocol_errors": task.get("max_protocol_errors") or 3,
        "num_ctx": task.get("num_ctx") or 0,
        "native_tools": bool(task.get("native_tools")),
        "allowed_tools": task.get("allowed_tools") or [],
        "model": task.get("model") or "",
        "provider": task.get("provider") or "",
    })
    log = open(run_dir / "ty.log", "w", encoding="utf-8")
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    runner = Path(runner_script) if runner_script else (ROOT / "scripts" / "ty_task_runner.py")
    proc = subprocess.Popen(
        [sys.executable, str(runner),
         "--task", str(task_path), "--result", str(result_path),
         "--heartbeat", str(heartbeat_path), "--root", str(ROOT)],
        cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, text=True,
        creationflags=flags)
    _save_json(run_dir / "worker.json", {"pid": proc.pid, "task": task.get("id"),
                                         "started_at": _now()})
    deadline = time.time() + timeout_s
    stopped = ""
    ram_breaches = 0
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
            if str(task.get("execution") or "") == "ty":
                # Keep the resident floor active during model work. Two consecutive
                # one-second samples are required so a single noisy reading does not
                # kill a healthy task; the threshold itself is unchanged.
                free = _free_ram_gb()
                if ram_floor_breached(free, ram_breaches):
                    ram_breaches += 1
                    write_heartbeat(run_id, str(task.get("id")),
                                    f"ram_floor_watch:{free:.2f}GB")
                    stopped = (f"ram_floor_breach: {free:.2f} GB free "
                               f"< {MIN_FREE_RAM_GB:.1f} GB floor")
                    _terminate_tree(proc)
                    break
                if free is not None and free < MIN_FREE_RAM_GB:
                    ram_breaches += 1          # one sample: warn, do not kill
                else:
                    ram_breaches = 0
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


def run_command_tracked(cmd: Sequence[str], *, cwd: Path = ROOT, timeout: float = 900.0,
                        pid_path: Optional[Path] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Run an apply command and record its PID so a crashed supervisor can kill it."""
    reason = check_command(cmd)
    if reason:
        return {"ok": False, "argv": list(cmd), "cwd": str(cwd), "exit": None,
                "duration_s": 0.0, "error": reason, "output": ""}
    exe = shutil.which(str(cmd[0]))
    argv = [exe or str(cmd[0])] + [str(c) for c in cmd[1:]]
    if dry_run:
        return {"ok": True, "argv": argv, "cwd": str(cwd), "exit": 0,
                "duration_s": 0.0, "error": "", "output": "[dry-run]"}
    started = time.time()
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(argv, cwd=str(cwd), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, shell=False,
                            creationflags=flags)
    if pid_path is not None:
        _save_json(pid_path, {"pid": proc.pid, "started_at": _now(),
                              "argv": list(cmd)})
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_tree(proc)
        return {"ok": False, "argv": argv, "cwd": str(cwd), "exit": None,
                "duration_s": round(time.time() - started, 3),
                "error": f"timeout after {timeout}s", "output": ""}
    finally:
        if pid_path is not None:
            pid_path.unlink(missing_ok=True)
    return {"ok": proc.returncode == 0, "argv": argv, "cwd": str(cwd),
            "exit": proc.returncode, "duration_s": round(time.time() - started, 3),
            "error": "" if proc.returncode == 0 else f"exit {proc.returncode}",
            "output": _scrub(output or "")}


def run_task_commands(task: Dict[str, Any], key: str, *,
                      dry_run: bool = False,
                      pid_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for cmd in task.get(key) or []:
        if key == "apply_commands" and pid_path is not None:
            res = run_command_tracked(cmd, timeout=float(task.get("timeout_seconds") or 600),
                                      pid_path=pid_path, dry_run=dry_run)
        else:
            res = run_command(cmd, timeout=float(task.get("timeout_seconds") or 600),
                              dry_run=dry_run)
        out.append({"cmd": list(cmd), "ok": res.get("ok"), "exit": res.get("exit"),
                    "duration_s": res.get("duration_s"), "error": res.get("error"),
                    "output": (res.get("output") or "")[-800:]})
        if not dry_run and key == "apply_commands" and not res.get("ok"):
            break
    return out


def run_prechecks(task: Dict[str, Any], *, dry_run: bool = False) -> Dict[str, Any]:
    """A precheck must FAIL before the fix. An always-green precheck is refused."""
    commands = task.get("precheck_commands") or []
    if not commands:
        return {"ok": True, "commands": [], "expected": "none"}
    results = run_task_commands(task, "precheck_commands", dry_run=dry_run)
    if dry_run:
        return {"ok": True, "commands": results, "expected": "fail"}
    all_failed = bool(results) and all(not r["ok"] for r in results)
    return {"ok": all_failed, "commands": results, "expected": "fail",
            "detail": ("all prechecks failed as required" if all_failed
                       else "a precheck passed before the fix; task is a no-op")}


def execute_task(task: Dict[str, Any], state: Dict[str, Any], *,
                 dry_run: bool = False, no_commit: bool = False,
                 lane: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    task_id = str(task.get("id"))
    if STOP_PATH.is_file():
        raise LoopError("STOP present before dispatch")
    if dry_run:
        return {"status": "dry_run", "checks": run_checks(task, dry_run=True),
                "prechecks": run_prechecks(task, dry_run=True),
                "commit": None, "changed": [], "lane": lane or resolve_lane(task)}
    started = time.time()
    run_id = f"{task_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    run_dir = RUN_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    record = state["tasks"].setdefault(task_id, {})
    lane = lane or resolve_lane(task)
    record.update({"status": "running", "run_id": run_id, "pid": os.getpid(),
                   "started_at": _now(), "reason": "", "lane": lane})
    _save_json(STATE_PATH, state)
    write_heartbeat(run_id, task_id, "dispatch")
    baseline = None
    changed: Set[str] = set()
    checks: List[Dict[str, Any]] = []
    prechecks: Dict[str, Any] = {"ok": True, "commands": [], "expected": "none"}
    applied: List[Dict[str, Any]] = []
    result: Dict[str, Any] = {"ok": False, "error": "not run"}
    try:
        if task.get("write_paths") or task.get("apply_commands") or task.get("execution") == "ty":
            baseline = take_baseline(task, run_id)
            record["baseline"] = baseline
            _save_json(STATE_PATH, state)
        prechecks = run_prechecks(task)
        record["prechecks"] = prechecks
        _save_json(STATE_PATH, state)
        if not prechecks.get("ok"):
            raise LoopError("precheck failed: " + str(prechecks.get("detail")))
        if task.get("apply_commands"):
            write_heartbeat(run_id, task_id, "apply")
            applied = run_task_commands(task, "apply_commands",
                                        pid_path=run_dir / "apply_worker.json")
            if not all(r["ok"] for r in applied):
                failed = next(r for r in applied if not r["ok"])
                raise LoopError(f"apply command failed: {failed.get('error')}")
        if task.get("execution") == "ty":
            if not lane.get("ok"):
                raise LoopError("model lane unavailable: " + str(lane.get("reason")))
            worker_task = dict(task)
            worker_task["model"] = lane.get("model") or ""
            worker_task["provider"] = lane.get("provider") or ""
            write_heartbeat(run_id, task_id, "ty")
            result = run_ty_task(worker_task, run_id, run_dir,
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
        write_heartbeat(run_id, task_id, "checks")
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
        duration = round(time.time() - started, 3)
        record.update({"status": "completed", "finished_at": _now(),
                       "commit": commit.get("sha") or "", "reason": "",
                       "duration_s": duration, "lane": lane,
                       "prechecks": prechecks, "apply": applied})
        _save_json(STATE_PATH, state)
        return {"status": "completed", "checks": checks, "commit": commit,
                "changed": sorted(changed), "ty": result, "lane": lane,
                "prechecks": prechecks, "apply": applied, "duration_s": duration}
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
                               "reason": reason, "restoration": "failed",
                               "duration_s": round(time.time() - started, 3),
                               "lane": lane, "prechecks": prechecks, "apply": applied})
                _save_json(STATE_PATH, state)
                return {"status": "failed", "error": reason, "checks": checks,
                        "prechecks": prechecks, "apply": applied, "lane": lane,
                        "restoration": "failed"}
        record.update({"status": "failed", "finished_at": _now(),
                       "reason": reason, "restoration": "ok" if restoration else "not-needed",
                       "duration_s": round(time.time() - started, 3),
                       "lane": lane, "prechecks": prechecks, "apply": applied})
        _save_json(STATE_PATH, state)
        return {"status": "failed", "error": reason, "checks": checks,
                "prechecks": prechecks, "apply": applied, "lane": lane,
                "restoration": restoration, "ty": result}
    finally:
        write_heartbeat(run_id, task_id, "finished")
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


def autonomy_log_path(day: Optional[str] = None) -> Path:
    stamp = day or datetime.now(timezone.utc).strftime("%Y%m%d")
    return AUTONOMY_LOG_DIR / f"autonomy_log_{stamp}.log"


def log_event(run_id: str, message: str) -> None:
    path = autonomy_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{_now()} [{run_id}] {_scrub(message)}\n")
        fh.flush()
        os.fsync(fh.fileno())


def write_campaign_heartbeat(*, run_id: str, status: str, started_at: str,
                             deadline_at: str, current_task: str = "",
                             phase: str = "", attempted: int = 0,
                             completed: int = 0, failed: int = 0,
                             blocked: int = 0, remaining: int = 0,
                             consecutive_failures: int = 0,
                             active_lane: Optional[Dict[str, Any]] = None,
                             stop_reason: str = "") -> None:
    _save_json(CAMPAIGN_HEARTBEAT_PATH, {
        "schema": "northstar.campaign_heartbeat.v1",
        "run_id": run_id, "status": status, "started_at": started_at,
        "deadline_at": deadline_at, "updated_at": _now(),
        "updated_ts": time.time(), "current_task": current_task,
        "phase": phase, "attempted": attempted, "completed": completed,
        "failed": failed, "blocked": blocked, "remaining": remaining,
        "consecutive_failures": consecutive_failures,
        "active_lane": active_lane or {}, "stop_reason": stop_reason,
        "ram_free_gb": _free_ram_gb(),
        "disk_free_gb": round(shutil.disk_usage(ROOT).free / (1024 ** 3), 3),
    })


def write_campaign_manifest(*, run_id: str, started_at: str, finished_at: str,
                            stop_reason: str, results: List[Dict[str, Any]],
                            readiness: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    CAMPAIGN_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    counts = {"completed": 0, "failed": 0, "dry_run": 0}
    for row in results:
        counts[row.get("status", "failed")] = counts.get(row.get("status", "failed"), 0) + 1
    manifest = {
        "schema": "northstar.campaign_manifest.v1",
        "run_id": run_id, "started_at": started_at, "finished_at": finished_at,
        "stop_reason": stop_reason, "counts": counts,
        "readiness": {k: readiness.get(k) for k in ("verdict", "ok", "checked_at",
                                                    "model_lane", "branch")}
        if readiness else None,
        "tasks": results,
    }
    path = CAMPAIGN_MANIFEST_DIR / f"{run_id}.json"
    _save_json(path, manifest)
    try:
        report = AUTONOMY_LOG_DIR / f"campaign_{run_id}.json"
        _save_json(report, manifest)
        manifest["report_path"] = str(report)
    except OSError:
        pass
    return manifest


def _remaining_count(tasks: Dict[str, Any], state: Dict[str, Any]) -> int:
    return sum(1 for t in tasks.get("tasks") or []
               if task_status(state, str(t.get("id"))) == "pending")


def run_campaign(tasks: Dict[str, Any], state: Dict[str, Any], *,
                 max_tasks: int = MAX_IMPLEMENTATION_TASKS,
                 deadline_minutes: float = CAMPAIGN_DEADLINE_MIN,
                 max_cycles: int = 0,
                 max_consecutive_failures: int = MAX_CONSECUTIVE_FAILURES,
                 dry_run: bool = False, no_commit: bool = False,
                 task_id: str = "", readiness: Optional[Dict[str, Any]] = None,
                 execute: Any = None) -> Dict[str, Any]:
    """Bounded foreground campaign; both task and time limits are mandatory."""
    started = time.time()
    started_at = _now()
    deadline_s = max(0.0, float(deadline_minutes) * 60.0)
    deadline_at = datetime.fromtimestamp(started + deadline_s, timezone.utc).isoformat(timespec="seconds")
    max_tasks = max(0, int(max_tasks))
    max_consecutive = max(1, int(max_consecutive_failures))
    run_id = f"campaign-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    execute = execute or execute_task
    readiness = readiness if readiness is not None else (
        {"ok": True, "verdict": "SKIPPED", "checks": []} if dry_run else readiness_gate())
    results: List[Dict[str, Any]] = []
    attempted = completed = failed = consecutive = implementation = 0
    stop_reason = ""
    lock = None
    active_lane: Dict[str, Any] = {}
    try:
        if not dry_run and not readiness.get("ok"):
            stop_reason = "readiness_no_go"
            log_event(run_id, "refused launch: readiness NO-GO")
            manifest = write_campaign_manifest(
                run_id=run_id, started_at=started_at, finished_at=_now(),
                stop_reason=stop_reason, results=results, readiness=readiness)
            return {"ok": False, "run_id": run_id, "stop_reason": stop_reason,
                    "readiness": readiness, "results": results, "manifest": manifest}
        if not dry_run:
            lock = acquire_lock(run_id)
        log_event(run_id, f"campaign start max_tasks={max_tasks} "
                          f"deadline_minutes={deadline_minutes} "
                          f"max_consecutive_failures={max_consecutive}")
        while True:
            if time.time() - started >= deadline_s:
                stop_reason = "deadline_minutes"
                break
            remaining = _remaining_count(tasks, state)
            write_campaign_heartbeat(
                run_id=run_id, status="running", started_at=started_at,
                deadline_at=deadline_at, attempted=attempted, completed=completed,
                failed=failed, blocked=sum(1 for t in tasks.get("tasks") or []
                                           if blocked_reason(t, state)),
                remaining=remaining, consecutive_failures=consecutive,
                active_lane=active_lane)
            if time.time() - started > deadline_s:
                stop_reason = "deadline_minutes"
                break
            if attempted >= max_tasks:
                stop_reason = "max_tasks"
                break
            if max_cycles and attempted >= max_cycles:
                stop_reason = "max_cycles"
                break
            if STOP_PATH.is_file():
                stop_reason = "stop_file"
                break
            task = select_task(tasks, state, task_id or None)
            if task is None:
                stop_reason = "queue_exhausted" if remaining == 0 else "queue_blocked"
                break
            active_lane = resolve_lane(task)
            tid = str(task.get("id"))
            # A Ty task spends RAM on a resident model. The dispatch gate uses the
            # MEASURED residency, refreshing it when the evidence is stale, and
            # stops the campaign rather than falling back to a pre-load guess.
            if str(task.get("execution") or "prebuilt") == "ty" and not dry_run:
                want_model = str(task.get("model") or active_lane.get("model") or "")
                want_ctx = int(task.get("num_ctx") or 0)
                if active_lane.get("model") and want_model != str(active_lane["model"]):
                    stop_reason = "profile_mismatch"
                    log_event(run_id, f"refused dispatch task={tid} reason=profile_mismatch "
                                      f"lane={active_lane.get('model')} task={want_model}")
                    break
                evidence = resident_evidence(want_model, num_ctx=(want_ctx or None))
                if not evidence.get("ok"):
                    refreshed = measure_model_resident(
                        want_model, num_ctx=(want_ctx or None))
                    evidence = resident_evidence(
                        want_model, num_ctx=(want_ctx or None)) if refreshed["ok"] \
                        else {"ok": False, "reason": (refreshed.get("record") or {}).get(
                            "verdict") or refreshed.get("raw_output") or "measurement failed"}
                if not evidence.get("ok"):
                    stop_reason = "model_resident_no_go"
                    log_event(run_id, f"refused dispatch task={tid} reason=model_resident_no_go "
                                      f"detail={str(evidence.get('reason'))[:160]}")
                    write_campaign_heartbeat(
                        run_id=run_id, status="stopped", started_at=started_at,
                        deadline_at=deadline_at, attempted=attempted, completed=completed,
                        failed=failed, remaining=remaining,
                        consecutive_failures=consecutive, active_lane=active_lane,
                        stop_reason=stop_reason)
                    break
            log_event(run_id, f"dispatch task={tid} lane={active_lane.get('model') or 'prebuilt'} "
                              f"phase=precheck")
            write_campaign_heartbeat(
                run_id=run_id, status="running", started_at=started_at,
                deadline_at=deadline_at, current_task=tid, phase="precheck",
                attempted=attempted, completed=completed, failed=failed,
                remaining=remaining, consecutive_failures=consecutive,
                active_lane=active_lane)
            result = execute(task, state, dry_run=dry_run, no_commit=no_commit,
                             lane=active_lane)
            attempted += 1
            status = str(result.get("status") or "failed")
            results.append({"task": tid, "name": task.get("name"), "status": status,
                            "commit": (result.get("commit") or {}).get("sha") or "",
                            "duration_s": result.get("duration_s"),
                            "lane": result.get("lane") or active_lane,
                            "prechecks": result.get("prechecks"),
                            "apply": result.get("apply"),
                            "error": _scrub(str(result.get("error") or "")),
                            "restoration": result.get("restoration")})
            log_event(run_id, f"{status} task={tid} commit="
                              f"{(result.get('commit') or {}).get('sha') or '-'} "
                              f"duration={result.get('duration_s')}")
            if dry_run:
                stop_reason = "dry_run"
                break
            try:
                append_ledger({
                    "run_id": run_id, "task": tid, "name": task.get("name"),
                    "status": status, "started_at": _now(), "finished_at": _now(),
                    "duration_s": result.get("duration_s"),
                    "lane": result.get("lane") or active_lane,
                    "checks": result.get("checks"),
                    "prechecks": result.get("prechecks"),
                    "apply": result.get("apply"),
                    "commit": result.get("commit"),
                    "changed": result.get("changed"),
                    "restoration": result.get("restoration"),
                    "error": _scrub(str(result.get("error") or "")),
                })
            except OSError as exc:
                log_event(run_id, f"ledger write failed: {exc}")
            if status == "completed":
                completed += 1
                consecutive = 0
                if task.get("execution") == "ty":
                    implementation += 1
            else:
                failed += 1
                consecutive += 1
                if consecutive >= max_consecutive:
                    stop_reason = "max_consecutive_failures"
                    log_event(run_id, f"halt: {consecutive} consecutive failures")
                    break
            if task_id:
                stop_reason = "single_task"
                break
        if not stop_reason:
            stop_reason = "queue_exhausted"
        write_campaign_heartbeat(
            run_id=run_id, status="finished", started_at=started_at,
            deadline_at=deadline_at, attempted=attempted, completed=completed,
            failed=failed, remaining=_remaining_count(tasks, state),
            consecutive_failures=consecutive, active_lane=active_lane,
            stop_reason=stop_reason)
        log_event(run_id, f"campaign stop reason={stop_reason} attempted={attempted} "
                          f"completed={completed} failed={failed}")
        manifest = write_campaign_manifest(
            run_id=run_id, started_at=started_at, finished_at=_now(),
            stop_reason=stop_reason, results=results, readiness=readiness)
        return {"ok": (dry_run or failed == 0) and stop_reason not in ("readiness_no_go",),
                "run_id": run_id, "stop_reason": stop_reason,
                "attempted": attempted, "completed": completed, "failed": failed,
                "implementation_tasks": implementation,
                "manifest": manifest, "results": results,
                "readiness": readiness}
    except LoopError as exc:
        stop_reason = f"loop_error: {exc}"
        log_event(run_id, f"halt: {stop_reason}")
        return {"ok": False, "run_id": run_id, "stop_reason": stop_reason,
                "error": str(exc), "results": results, "readiness": readiness}
    finally:
        if lock is not None:
            release_lock()
        try:
            write_campaign_heartbeat(
                run_id=run_id, status="finished", started_at=started_at,
                deadline_at=deadline_at, attempted=attempted, completed=completed,
                failed=failed, remaining=_remaining_count(tasks, state),
                consecutive_failures=consecutive, active_lane=active_lane,
                stop_reason=stop_reason or "unknown")
        except OSError:
            pass


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
    campaign = _load_json(CAMPAIGN_HEARTBEAT_PATH, {}) or {}
    if not isinstance(campaign, dict):
        campaign = {}
    running = campaign.get("status") == "running"
    current = campaign.get("current_task") or ""
    remaining = list(buckets["eligible"])
    return {
        "running": running,
        "campaign": campaign,
        "current": current,
        "phase": campaign.get("phase") or "",
        "finished": buckets["completed"],
        "failed": buckets["failed"],
        "interrupted": buckets["interrupted"],
        "remaining": remaining,
        "blocked": buckets["blocked"],
        "tasks": [{"id": t.get("id"), "status": task_status(state, str(t.get("id"))),
                   "reason": blocked_reason(t, state)} for t in tasks.get("tasks") or []],
        "buckets": buckets, "last_cycles": rows,
    }


def render_status(report: Dict[str, Any]) -> str:
    camp = report.get("campaign") or {}
    lines = [
        f"RUNNING: {'yes' if report.get('running') else 'no'}  "
        f"run={camp.get('run_id') or '-'}  stop={camp.get('stop_reason') or '-'}",
        f"NOW: {report.get('current') or '-'}  phase={report.get('phase') or '-'}  "
        f"lane={(camp.get('active_lane') or {}).get('model') or '-'}",
        f"COUNTS: completed={len(report.get('finished') or [])} "
        f"failed={len(report.get('failed') or [])} "
        f"interrupted={len(report.get('interrupted') or [])} "
        f"remaining={len(report.get('remaining') or [])} "
        f"blocked={len(report.get('blocked') or [])}",
        f"RAM={camp.get('ram_free_gb') or '?'}GB DISK={camp.get('disk_free_gb') or '?'}GB "
        f"updated={camp.get('updated_at') or '-'}",
    ]
    for row in report.get("failed") or []:
        lines.append(f"FAILED {row.get('id')}: {row.get('reason') or ''}")
    for row in report.get("blocked") or []:
        lines.append(f"BLOCKED {row.get('id')}: {row.get('reason') or ''}")
    return "\n".join(lines)


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
    ap.add_argument("--ready", action="store_true", help="run the full GO/NO-GO preflight")
    ap.add_argument("--status", action="store_true", help="one-screen campaign/task status")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--task", default="", help="run one task id")
    ap.add_argument("--once", action="store_true", help="run at most one task")
    ap.add_argument("--max-cycles", type=int, default=0,
                    help="0 = all eligible (still bounded by --max-tasks/deadline)")
    ap.add_argument("--max-tasks", type=int, default=MAX_IMPLEMENTATION_TASKS,
                    help="maximum tasks attempted in this campaign (default 8)")
    ap.add_argument("--deadline-minutes", type=float, default=CAMPAIGN_DEADLINE_MIN)
    ap.add_argument("--max-consecutive-failures", type=int,
                    default=MAX_CONSECUTIVE_FAILURES,
                    help="halt after N consecutive failed tasks (default 2)")
    ap.add_argument("--dry-run", action="store_true", help="print commands, write nothing")
    ap.add_argument("--no-commit", action="store_true", help="verify only")
    ap.add_argument("--resume", default="", help="explicitly resume a failed/interrupted task id")
    ap.add_argument("--stop", action="store_true", help="create STOP for a safe stop")
    args = ap.parse_args(argv)

    if args.ready:
        result = readiness_gate()
        print(render_readiness(result, as_json=args.json))
        return 0 if result.get("ok") else 2
    if args.stop:
        STOP_PATH.write_text(f"operator stop {_now()}\n", encoding="utf-8")
        print(f"STOP created at {STOP_PATH}")
        return 0

    tasks = load_tasks()
    state = load_state()
    recover_interrupted(state)
    if args.status:
        report = status_report(tasks, state)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(render_status(report))
        return 0
    if args.resume:
        try:
            resume_task(args.resume, tasks, state)
        except LoopError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}))
            return 2
        # An explicit resume REPAIRS state; it must not silently start an
        # unattended campaign over whatever else happens to be queued. That is
        # how `--resume ty-dpi-image-guard` once dispatched an unrelated task.
        print(json.dumps({"ok": True, "resumed": args.resume,
                          "next": "start a campaign explicitly (--task/--once/--max-tasks)"}))
        return 0

    max_tasks = 1 if args.once else max(0, int(args.max_tasks))
    max_cycles = 1 if args.once else max(0, int(args.max_cycles))
    result = run_campaign(
        tasks, state, max_tasks=max_tasks,
        deadline_minutes=args.deadline_minutes, max_cycles=max_cycles,
        max_consecutive_failures=max(1, int(args.max_consecutive_failures)),
        dry_run=args.dry_run, no_commit=args.no_commit,
        task_id=args.task)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(render_status(status_report(tasks, state)))
        print(json.dumps({"ok": result.get("ok"), "run_id": result.get("run_id"),
                          "stop_reason": result.get("stop_reason"),
                          "attempted": result.get("attempted"),
                          "completed": result.get("completed"),
                          "failed": result.get("failed"),
                          "manifest": (result.get("manifest") or {}).get("run_id")}, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
