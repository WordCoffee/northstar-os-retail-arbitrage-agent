"""Operational status — the read-only trust surface (N-2).

Answers three operator questions without opening a log:

  1. **Is the machine healthy?**  disk headroom, database integrity, WAL size
  2. **What is the brain doing?**  measured lanes, resident local models
  3. **Is anything unknown?**  every unavailable value is an explicit ``None``
     with a ``reason`` — never a fabricated zero

Honesty contract
----------------
* Every number is MEASURED at call time by a probe. Anything a probe cannot
  determine is ``None`` plus a ``reason`` (this repository's null-not-zero rule).
* Probes are injectable, so the tests need no GPU, no Ollama and no network.
* This module **writes nothing** and never imports the app.
* GPU telemetry is deliberately NOT duplicated here: the shell already exposes
  ``/api/shell/hardware``. This module reports it as unknown-with-a-pointer
  rather than growing a second source of truth.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

DISK_WARN_GB = 5.0
DISK_CRIT_GB = 1.0
OLLAMA_PS = "http://127.0.0.1:11434/api/ps"


def _gb(n: Optional[float]) -> Optional[float]:
    return None if n is None else round(n / (1024 ** 3), 2)


# ── disk ─────────────────────────────────────────────────────────────────────

def disk_status(path: str = ".", probe: Optional[Callable[[str], Any]] = None) -> Dict[str, Any]:
    """Free space with an explicit headroom verdict. Measured, never assumed."""
    fn = probe or shutil.disk_usage
    try:
        usage = fn(path)
        total, free = int(usage.total), int(usage.free)
    except Exception as exc:  # noqa: BLE001 - reported, never hidden
        return {"available": False, "path": path, "free_gb": None, "total_gb": None,
                "verdict": "unknown", "reason": f"{type(exc).__name__}: {exc}"[:200]}
    free_gb = _gb(free)
    if free_gb < DISK_CRIT_GB:
        verdict = "critical"
    elif free_gb < DISK_WARN_GB:
        verdict = "warn"
    else:
        verdict = "ok"
    return {
        "available": True,
        "path": os.path.abspath(path),
        "free_gb": free_gb,
        "total_gb": _gb(total),
        "used_pct": round(100.0 * (total - free) / total, 1) if total else None,
        "verdict": verdict,
        "thresholds": {"warn_gb": DISK_WARN_GB, "crit_gb": DISK_CRIT_GB},
        "reason": None,
    }


# ── database ─────────────────────────────────────────────────────────────────

def db_status(db_path: Optional[str] = None,
              integrity_probe: Optional[Callable[[str], str]] = None) -> Dict[str, Any]:
    """Existence, size, table count, WAL size and integrity of the product store."""
    path = db_path or _default_db_path()
    if not path:
        return {"available": False, "path": None, "reason": "no database path resolved"}
    if not os.path.exists(path):
        return {"available": False, "path": os.path.abspath(path), "reason": "database file absent"}

    size_bytes = os.path.getsize(path)
    size_mb = round(size_bytes / (1024 ** 2), 1)
    wal = path + "-wal"
    wal_mb = round(os.path.getsize(wal) / (1024 ** 2), 2) if os.path.exists(wal) else 0.0

    tables: Optional[int] = None
    integrity: Optional[str] = None
    reason: Optional[str] = None
    try:
        if integrity_probe:
            integrity = integrity_probe(path)
        else:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            try:
                tables = int(conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
                integrity = str(conn.execute("PRAGMA integrity_check").fetchone()[0])
            finally:
                conn.close()
    except Exception as exc:  # noqa: BLE001
        reason = f"{type(exc).__name__}: {exc}"[:200]

    ok = (integrity == "ok")
    return {
        "available": True,
        "path": os.path.abspath(path),
        "size_bytes": size_bytes,
        "size_mb": size_mb,
        "wal_mb": wal_mb,
        "tables": tables,
        "integrity": integrity,
        "verdict": "ok" if ok else ("warn" if integrity is None else "critical"),
        "reason": reason,
    }


def _default_db_path() -> Optional[str]:
    try:
        import data_layer
        return str(getattr(data_layer, "_SQLITE_PATH", "") or "") or None
    except Exception:  # noqa: BLE001
        return None


# ── lanes (measured runs) ────────────────────────────────────────────────────

def lane_status(db=None, *, window: int = 500) -> Dict[str, Any]:
    """Measured lane aggregates, reusing the ONE telemetry store."""
    try:
        import lane_telemetry
        handle = db if db is not None else lane_telemetry._db()
        out = lane_telemetry.summary(handle, window=window)
        if out.get("error"):
            # An unusable handle is an unknown, not an empty-but-healthy lane set.
            return {"available": False, "lanes": out.get("lanes") or {},
                    "reason": out["error"]}
        return {"available": True, **out}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "lanes": {},
                "reason": f"{type(exc).__name__}: {exc}"[:200]}


# ── render lock (B5) ─────────────────────────────────────────────────────────

def render_lock_status() -> Dict[str, Any]:
    """How long renders waited on the cross-process lock, and how often they gave up.

    A serialised render previously looked identical to a slow one. These counters
    are process-local and reset on restart; they are a live signal, not history.
    """
    try:
        import studio_generation as sg
        stats = sg.render_lock_stats()
        return {"available": True, **stats}
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"[:200]}


# ── local models ─────────────────────────────────────────────────────────────

def model_status(ps_probe: Optional[Callable[[], Any]] = None) -> Dict[str, Any]:
    """Resident Ollama models. Absent/unreachable is reported, never guessed."""
    fn = ps_probe or _ollama_ps
    try:
        payload = fn()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "resident": [], "reason": f"{type(exc).__name__}: {exc}"[:200]}

    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return {"available": False, "resident": [], "reason": "unexpected /api/ps payload"}
    resident: List[Dict[str, Any]] = []
    total_mb = 0
    for m in models:
        size = m.get("size_vram") or m.get("size")
        if isinstance(size, (int, float)):
            total_mb += int(size / (1024 ** 2))
        resident.append({"name": m.get("name") or m.get("model"),
                         "size_mb": int(size / (1024 ** 2)) if isinstance(size, (int, float)) else None})
    return {"available": True, "resident": resident, "vram_used_mb": total_mb or None,
            "reason": None if resident else "no model is currently resident"}


def _ollama_ps() -> Dict[str, Any]:
    with urllib.request.urlopen(OLLAMA_PS, timeout=2) as r:
        return json.loads(r.read().decode("utf-8"))


# ── verdict + aggregate ──────────────────────────────────────────────────────

def verdict(components: Dict[str, Any]) -> Dict[str, Any]:
    """Roll component verdicts into one status. Unknown never becomes 'healthy'."""
    reasons: List[str] = []
    level = 0                                     # 0 ok, 1 warn, 2 critical
    for name, comp in components.items():
        if comp.get("delegated"):
            continue                              # reported elsewhere by design, not unknown
        v = comp.get("verdict")
        if v == "critical":
            level = max(level, 2)
            reasons.append(f"{name}: critical — {comp.get('reason') or 'see component'}")
        elif v == "warn":
            level = max(level, 1)
            reasons.append(f"{name}: warn — {comp.get('reason') or 'see component'}")
        elif v in (None, "unknown") and not comp.get("available", True):
            # Not being able to measure something is worth surfacing, not hiding.
            reasons.append(f"{name}: unknown — {comp.get('reason') or 'unavailable'}")
    status = ("critical" if level == 2 else "degraded" if level == 1
              else "healthy" if not reasons else "degraded")
    return {"status": status, "reasons": reasons}


def collect(db_path: Optional[str] = None, *, disk_path: str = ".",
            db=None, ps_probe=None, disk_probe=None,
            gpu: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The whole trust surface in one payload. Injectable for tests."""
    components = {
        "disk": disk_status(disk_path, probe=disk_probe),
        "database": db_status(db_path),
        "lanes": lane_status(db),
        "models": model_status(ps_probe),
    }
    if gpu is None:
        components["gpu"] = {
            "available": False,
            "delegated": True,
            "reason": "not duplicated here - /api/shell/hardware is the source of truth",
        }
    else:
        components["gpu"] = gpu
    v = verdict(components)
    return {
        "ok": True,
        "at": datetime.now(timezone.utc).isoformat(),
        "status": v["status"],
        "reasons": v["reasons"],
        "components": components,
        "note": ("Every value is measured at call time. A null is an explicit 'could not "
                 "measure', never a zero."),
    }
