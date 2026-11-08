"""The Profile 6 lease: the only Chrome profile Ty's Vision may drive.

Owner standing rule (2026-10-27): signed-in work uses Chrome profile directory **"Profile
6"** and nothing else. Three profiles on this machine are called "Work", so the match is
on the **directory name**, never the display name, and a near-miss is a refusal.

This module does not choose a profile. It answers one question — "may I attach to this
directory right now?" — and the answer is no unless an owner-acquired lease says exactly
`Profile 6` and has not gone idle.

    from vision.lease import status, gate
    verdict = gate(status())
    if not verdict["allow"]:
        raise RuntimeError(verdict["reason"])
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
LEASE = ROOT / "data" / "chromeconnect_lease.json"

#: The one authorized directory. Compared after casefold because Windows is
#: case-insensitive; a display name such as "Work" never matches.
AUTHORIZED_DIR = "Profile 6"
DEFAULT_IDLE_MINUTES = 30

UNLEASED = "unleased"
ACTIVE = "active"
EXPIRED = "expired"
REVOKED = "revoked"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def load(path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path or LEASE)
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def status(*, path: Optional[Path] = None, now: Optional[float] = None) -> Dict[str, Any]:
    """The lease as it is, with expiry applied rather than assumed."""
    data = load(path)
    directory = str(data.get("profile_dir") or data.get("profile_directory") or "").strip()
    state = str(data.get("state") or UNLEASED).strip().casefold()
    idle_minutes = int(data.get("idle_minutes") or DEFAULT_IDLE_MINUTES)
    last = _parse(data.get("last_activity")) or _parse(data.get("leased_at"))
    current = now if now is not None else time.time()
    idle_seconds = (current - last) if last else None
    if state == ACTIVE and idle_seconds is not None and idle_seconds > idle_minutes * 60:
        state = EXPIRED
    return {"state": state, "directory": directory, "idle_minutes": idle_minutes,
            "idle_seconds": None if idle_seconds is None else round(idle_seconds),
            "profile_name": str(data.get("profile_name") or ""),
            "profile_email": str(data.get("profile_email") or ""),
            "lease_id": str(data.get("lease_id") or "")}


def gate(state: Optional[Dict[str, Any]] = None,
         *, path: Optional[Path] = None) -> Dict[str, Any]:
    """May Ty's Vision attach to a Chrome profile right now? Refusal names why."""
    data = state if state is not None else status(path=path)
    directory = str(data.get("directory") or "").strip()
    if not directory:
        return {"allow": False, "reason": "no profile leased: the owner picks Profile 6",
                "directory": "", "state": data.get("state")}
    if directory.casefold() != AUTHORIZED_DIR.casefold():
        return {"allow": False,
                "reason": (f"leased profile directory is {directory!r}; only "
                           f"{AUTHORIZED_DIR!r} is authorized"),
                "directory": directory, "state": data.get("state")}
    if str(data.get("state") or "").casefold() != ACTIVE:
        return {"allow": False,
                "reason": f"lease is {data.get('state')!r}, not active",
                "directory": directory, "state": data.get("state")}
    return {"allow": True, "reason": "", "directory": directory, "state": ACTIVE}


def acquire(directory: str, *, profile_name: str = "", profile_email: str = "",
            path: Optional[Path] = None, idle_minutes: int = DEFAULT_IDLE_MINUTES
            ) -> Dict[str, Any]:
    """Record an owner pick. A pick for any other directory is refused, not stored."""
    if str(directory or "").strip().casefold() != AUTHORIZED_DIR.casefold():
        return {"ok": False, "reason": f"only {AUTHORIZED_DIR!r} may be leased",
                "directory": str(directory or "")}
    target = Path(path or LEASE)
    payload = {"profile_dir": AUTHORIZED_DIR, "profile_name": profile_name,
               "profile_email": profile_email, "state": ACTIVE,
               "leased_at": _now(), "last_activity": _now(),
               "idle_minutes": int(idle_minutes),
               "lease_id": f"lease-{int(time.time())}"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, **payload}


def touch(*, path: Optional[Path] = None) -> Dict[str, Any]:
    """Any action keeps the lease alive; only the owner or the idle timer ends it."""
    target = Path(path or LEASE)
    data = load(target)
    if not data:
        return {"ok": False, "reason": "no lease to touch"}
    data["last_activity"] = _now()
    data["state"] = ACTIVE
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "at": data["last_activity"]}


def revoke(*, path: Optional[Path] = None) -> Dict[str, Any]:
    target = Path(path or LEASE)
    data = load(target)
    data.update({"state": REVOKED, "revoked_at": _now()})
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "state": REVOKED}


__all__ = ["AUTHORIZED_DIR", "UNLEASED", "ACTIVE", "EXPIRED", "REVOKED",
           "load", "status", "gate", "acquire", "touch", "revoke"]
