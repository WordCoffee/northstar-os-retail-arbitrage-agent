"""API readiness snapshot for ``GET /readyz`` (P1-05 parity for the API).

The worker and the scheduler each expose ``/healthz`` + ``/readyz`` through
``foundation.ops_health``: a polling loop that is merely *running* can be
wedged, so the probe reports real progress. The API needs the same distinction:

- ``GET /health``     liveness: the process is up and serving.
- ``GET /readyz``     readiness: the posture checks below pass, so the process
                      should be sent traffic. Returns **503** when any
                      critical check fails, so an orchestrator drains it.

Everything here is local and side-effect free: no network, no credentials, no
writes. The checks are the production-shaped invariants that a misconfigured
deploy would otherwise only reveal at first request.

Usage::

    from production_health import readiness_snapshot
    snapshot = readiness_snapshot()          # dict, JSON-serialisable
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

# The redaction module lives in the repo-root `northstar.security` package.
# Make it importable regardless of the process CWD (mirrors logging_config).
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Set by the app at import time; the endpoint reports uptime from it.
_PROCESS_STARTED_AT = datetime.now(timezone.utc)
_PROCESS_STARTED_MONOTONIC = time.monotonic()

_PRODUCTION_LIKE = {"production", "staging", "beta"}


def _environment() -> str:
    return (os.environ.get("ENVIRONMENT") or "").strip().lower()


def _check_rate_limit_posture() -> Dict[str, Any]:
    try:
        from rate_limiter import prod_posture_ok

        ok = bool(prod_posture_ok())
        reason = "" if ok else (
            "NORTHSTAR_DISABLE_RATE_LIMIT=1 while ENVIRONMENT is "
            f"{_environment() or 'unset'}"
        )
    except Exception as exc:  # noqa: BLE001 - a missing limiter is a posture failure
        ok, reason = False, f"rate limiter unavailable: {exc}"
    return {"ok": ok, "critical": True, "reason": reason}


def _check_redaction() -> Dict[str, Any]:
    """Log/error redaction must be wired, not merely installed."""
    try:
        from northstar.security.redaction import redact_text

        sample = "token sk-live-0123456789abcdefghij leaked"
        redacted = redact_text(sample)
        ok = "[REDACTED]" in redacted and "sk-live-0123456789" not in redacted
        reason = "" if ok else "redaction did not redact a token-shaped value"
        if ok:
            try:
                import logging_config

                ok = bool(getattr(logging_config, "_REDACTION_AVAILABLE", False))
                reason = "" if ok else "logging_config did not import the redaction filter"
            except Exception:
                ok, reason = False, "logging_config unavailable"
    except Exception as exc:  # noqa: BLE001
        ok, reason = False, f"redaction module unavailable: {exc}"
    return {"ok": ok, "critical": True, "reason": reason}


def _check_data_dir() -> Dict[str, Any]:
    data_dir = BACKEND_DIR / "data"
    ok = data_dir.is_dir() and os.access(data_dir, os.W_OK)
    return {
        "ok": ok,
        "critical": True,
        "reason": "" if ok else f"data directory is not writable: {data_dir}",
    }


def _check_ui_build() -> Dict[str, Any]:
    """The hosted image serves the SPA from the API, so a missing build is fatal."""
    dist = REPO_ROOT / "northstar-os-ui" / "dist"
    present = (dist / "index.html").is_file() and (dist / "assets").is_dir()
    production_like = _environment() in _PRODUCTION_LIKE
    return {
        "ok": present or not production_like,
        "critical": production_like,
        "present": present,
        "reason": "" if present else (
            f"no UI production build at {dist}"
            + ("" if production_like else " (non-critical outside production-like envs)")
        ),
    }


def _check_foundation_store() -> Dict[str, Any]:
    """Readiness for the store backing this process, without assuming a backend."""
    configured_url = (os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL") or "").strip()
    if configured_url.startswith("postgres"):
        return {
            "ok": True,
            "critical": False,
            "backend": "postgres",
            "checked": False,
            "reason": "postgres readiness is covered by the compose dependency + migrate gate",
        }

    path = Path(os.environ.get("FOUNDATION_DB_PATH") or (BACKEND_DIR / "data" / "foundation.db"))
    if not path.is_file():
        return {
            "ok": False,
            "critical": True,
            "backend": "sqlite",
            "checked": False,
            "reason": f"foundation store missing: {path}",
        }
    try:
        conn = sqlite3.connect("file:" + path.resolve().as_posix() + "?mode=ro", uri=True, timeout=5)
        try:
            conn.execute("SELECT 1").fetchone()
            quick = [row[0] for row in conn.execute("PRAGMA quick_check").fetchall()]
        finally:
            conn.close()
        ok = quick == ["ok"]
        return {
            "ok": ok,
            "critical": True,
            "backend": "sqlite",
            "checked": True,
            "reason": "" if ok else f"quick_check failed: {quick[:3]}",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "critical": True,
            "backend": "sqlite",
            "checked": True,
            "reason": f"store unreadable: {exc}",
        }


def _check_live_posture() -> Dict[str, Any]:
    """An armed-but-unbounded live mode is a posture violation, not a feature."""
    try:
        import live_gate

        problems = list(live_gate.live_posture_problems() or [])
    except Exception as exc:  # noqa: BLE001
        problems = [f"live posture could not be evaluated: {exc}"]
    return {"ok": not problems, "critical": True, "problems": problems}


def readiness_snapshot() -> Dict[str, Any]:
    """Compute the readiness payload returned by ``GET /readyz``."""
    checks = {
        "rate_limit_posture": _check_rate_limit_posture(),
        "redaction": _check_redaction(),
        "data_dir_writable": _check_data_dir(),
        "ui_build": _check_ui_build(),
        "foundation_store": _check_foundation_store(),
        "live_posture": _check_live_posture(),
    }
    failures = [
        name for name, check in checks.items()
        if check.get("critical", True) and not check.get("ok", False)
    ]
    return {
        "status": "ready" if not failures else "not-ready",
        "service": "northstar-backend",
        "environment": _environment() or "unset",
        "started_at": _PROCESS_STARTED_AT.isoformat(),
        "uptime_seconds": round(time.monotonic() - _PROCESS_STARTED_MONOTONIC, 3),
        "failed_checks": failures,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def probe_local(url: Optional[str] = None, timeout: float = 4.0) -> Dict[str, Any]:
    """HTTP probe used by scripts/monitoring; returns the parsed payload."""
    import json
    import urllib.request

    target = url or "http://127.0.0.1:8000/readyz"
    with urllib.request.urlopen(target, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return {"status_code": int(response.status), "body": json.loads(body)}


if __name__ == "__main__":  # pragma: no cover - operator convenience
    import json

    payload = readiness_snapshot()
    print(json.dumps(payload, indent=2, sort_keys=True))
    sys.exit(0 if payload["status"] == "ready" else 1)
