"""Health probes, fault detection and atomic rollback.

Design stance: a repair is only allowed to touch what it can restore. So the
write path here is **snapshot -> verify -> replace -> re-verify**, and any
failure restores the snapshot with ``os.replace`` (atomic on both NTFS and
POSIX). There is no "best effort" branch that leaves a half-written file.

The probes are read-only and cheap; they are meant to run at startup and before
anything destructive. ``diagnose`` returns findings with a stable ``id``,
``severity`` and a concrete ``repair`` label, so the caller never has to parse
prose.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

GB = 1024 ** 3


# ---------------------------------------------------------------------------
# Process checks
# ---------------------------------------------------------------------------

def pid_alive(pid: int) -> bool:
    """Safe liveness check. Never signals the process."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259  # STILL_ACTIVE
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def stale_locks(paths: List[str]) -> List[Dict[str, Any]]:
    """A lock whose owner pid is dead is stale and safe to report."""
    found: List[Dict[str, Any]] = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            pid = payload.get("pid")
        except (OSError, ValueError, json.JSONDecodeError):
            found.append({"path": path, "pid": None, "stale": True,
                          "reason": "unreadable"})
            continue
        alive = pid_alive(pid) if pid else False
        found.append({"path": path, "pid": pid, "stale": not alive,
                      "reason": "dead_pid" if not alive else "held"})
    return found


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------

def _check_state_file(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {"id": "state_missing", "severity": "info",
                "detail": f"{path} not present", "repair": "none"}
    try:
        raw = open(path, "r", encoding="utf-8-sig").read()
        json.loads(raw)
        return {"id": "state_ok", "severity": "ok", "detail": "parses",
                "repair": "none"}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"id": "state_corrupt", "severity": "high",
                "detail": f"{type(exc).__name__}: {exc}",
                "repair": "restore_from_backup"}


def _check_sqlite(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return {"id": "db_missing", "severity": "info",
                "detail": f"{path} not present", "repair": "none"}
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
        ok = bool(row) and str(row[0]).lower() == "ok"
        return {"id": "db_ok" if ok else "db_corrupt",
                "severity": "ok" if ok else "high",
                "detail": str(row[0]) if row else "no result",
                "repair": "none" if ok else "restore_from_backup"}
    except sqlite3.Error as exc:
        return {"id": "db_unreadable", "severity": "high",
                "detail": str(exc), "repair": "restore_from_backup"}


def _check_disk(path: str, min_free_gb: float) -> Dict[str, Any]:
    try:
        free = shutil.disk_usage(path).free / GB
    except OSError as exc:
        return {"id": "disk_unreadable", "severity": "medium",
                "detail": str(exc), "repair": "none"}
    if free < 3:
        severity, repair = "critical", "stop_and_free_space"
    elif free < min_free_gb:
        severity, repair = "high", "pause_gpu_and_downloads"
    else:
        severity, repair = "ok", "none"
    return {"id": "disk_free", "severity": severity,
            "detail": f"{free:.2f} GB free", "repair": repair,
            "free_gb": round(free, 2)}


def _check_running_tasks(db_path: str) -> Dict[str, Any]:
    if not os.path.isfile(db_path):
        return {"id": "tasks_none", "severity": "info", "detail": "no queue db",
                "repair": "none"}
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=5)
        try:
            rows = conn.execute(
                "SELECT id FROM tys_tasks WHERE status='running'").fetchall()
        finally:
            conn.close()
    except sqlite3.Error as exc:
        return {"id": "tasks_unreadable", "severity": "medium",
                "detail": str(exc), "repair": "none"}
    if rows:
        return {"id": "tasks_stuck_running", "severity": "medium",
                "detail": f"{len(rows)} task(s) claim to be running; a dead "
                          "process cannot finish them",
                "repair": "mark_interrupted", "tasks": [r[0] for r in rows]}
    return {"id": "tasks_ok", "severity": "ok", "detail": "no running tasks",
            "repair": "none"}


def diagnose(repo_root: str, *, state_path: Optional[str] = None,
             db_path: Optional[str] = None, lock_paths: Optional[List[str]] = None,
             min_free_gb: float = 10.0) -> Dict[str, Any]:
    """Read-only health sweep. Findings carry a concrete repair label."""
    state_path = state_path or os.path.join(repo_root, "00_STATE.json")
    db_path = db_path or os.path.join(repo_root, "Northstar_backend", "data",
                                      "tys_assistant.db")
    findings = [
        _check_state_file(state_path),
        _check_sqlite(db_path),
        _check_disk(repo_root, min_free_gb),
        _check_running_tasks(db_path),
    ]
    for lock in stale_locks(lock_paths or []):
        findings.append({
            "id": "stale_lock" if lock["stale"] else "lock_held",
            "severity": "medium" if lock["stale"] else "ok",
            "detail": f"{lock['path']} pid={lock['pid']} ({lock['reason']})",
            "repair": "ignore_lock" if lock["stale"] else "none",
            "path": lock["path"],
        })
    order = {"critical": 0, "high": 1, "medium": 2, "info": 3, "ok": 4}
    findings.sort(key=lambda f: order.get(f["severity"], 5))
    worst = findings[0]["severity"] if findings else "ok"
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "worst": worst,
        "ok": worst in ("ok", "info"),
        "findings": findings,
        "repairs": [f["repair"] for f in findings if f["repair"] != "none"],
    }


# ---------------------------------------------------------------------------
# Safe writes and rollback
# ---------------------------------------------------------------------------

def snapshot(path: str, backup_dir: Optional[str] = None) -> Dict[str, Any]:
    """Copy a file aside before it is touched. Returns a restorable handle."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    directory = backup_dir or os.path.join(os.path.dirname(path), "backups")
    os.makedirs(directory, exist_ok=True)
    base = os.path.basename(path)
    backup = os.path.join(directory, f"{base}.{stamp}.bak")
    suffix = 1
    while os.path.exists(backup):
        backup = os.path.join(directory, f"{base}.{stamp}.{suffix}.bak")
        suffix += 1
    shutil.copy2(path, backup)
    return {"path": path, "backup": backup,
            "bytes": os.path.getsize(backup), "at": stamp}


def restore(handle: Dict[str, Any]) -> Dict[str, Any]:
    path = handle["path"]
    backup = handle["backup"]
    if not os.path.isfile(backup):
        raise FileNotFoundError(backup)
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".restore-", dir=directory)
    os.close(fd)
    try:
        shutil.copy2(backup, tmp)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return {"status": "restored", "path": path, "backup": backup}


def atomic_write(path: str, content: str, *,
                 verify: Optional[Callable[[str], bool]] = None,
                 backup_dir: Optional[str] = None,
                 encoding: str = "utf-8") -> Dict[str, Any]:
    """Snapshot, write atomically, verify; roll back on any failure."""
    handle = snapshot(path, backup_dir) if os.path.isfile(path) else None
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".atomic-", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        if verify is not None:
            with open(path, "r", encoding=encoding) as stream:
                current = stream.read()
            if not verify(current):
                raise ValueError("verification rejected the written content")
    except BaseException as exc:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass
        rolled_back = False
        if handle:
            restore(handle)
            rolled_back = True
        else:
            try:
                os.remove(path)
            except OSError:
                pass
        return {"status": "rolled_back" if rolled_back else "aborted",
                "path": path, "error": f"{type(exc).__name__}: {exc}",
                "backup": handle["backup"] if handle else None}
    return {"status": "written", "path": path,
            "bytes": os.path.getsize(path),
            "backup": handle["backup"] if handle else None}


def repair_json(text: str) -> Optional[str]:
    """Conservative repair: trailing commas and smart quotes only."""
    candidate = (text.replace("\u201c", '"').replace("\u201d", '"')
                 .replace("\u2018", "'").replace("\u2019", "'"))
    candidate = candidate.replace("\ufeff", "")
    candidate = _strip_trailing_commas(candidate)
    try:
        json.loads(candidate)
        return candidate
    except (ValueError, json.JSONDecodeError):
        return None


def _strip_trailing_commas(text: str) -> str:
    out: List[str] = []
    in_string = False
    escaped = False
    length = len(text)
    for index, char in enumerate(text):
        if in_string:
            out.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            out.append(char)
            continue
        if char == ",":
            look = index + 1
            while look < length and text[look] in " \t\r\n":
                look += 1
            if look < length and text[look] in "]}":
                continue  # drop the comma
        out.append(char)
    return "".join(out)


class RollbackRegistry:
    """In-memory registry of snapshots taken during one execution."""

    def __init__(self):
        self._entries: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def record(self, handle: Dict[str, Any], reason: str = "") -> None:
        with self._lock:
            self._entries.append({**handle, "reason": reason,
                                  "recorded_at": time.time()})

    def latest(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            return dict(self._entries[-1]) if self._entries else None

    def rollback(self, handle: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = handle or self.latest()
        if not entry:
            return {"status": "nothing_to_rollback"}
        result = restore(entry)
        result["reason"] = entry.get("reason", "")
        return result

    def report(self) -> Dict[str, Any]:
        with self._lock:
            return {"snapshots": len(self._entries),
                    "paths": [e["path"] for e in self._entries]}
