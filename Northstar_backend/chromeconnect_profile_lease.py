"""Chrome Connect profile lease (replaces signed-out requirement).

The profile lease allows the operator to pick a Chrome profile once via the
native picker. The lease stays alive during unattended runs. Any Chrome Connect
action keeps the lease alive (resets the idle timer). The only human step is
the one-time pick in the picker. Chrome Connect never chooses a profile for
the operator.

Lease states:
- UNLEASED: no profile picked yet (picker required)
- ACTIVE: profile leased, idle timer running
- EXPIRED: idle timeout exceeded (re-pick required)
- REVOKED: operator explicitly revoked the lease

Default idle timeout: 30 minutes (configurable via CC_LEASE_IDLE_MINUTES).

Provenance: In-house implementation. Replaces the signed-out profile requirement.
Policy change approved by owner 2026-10-27.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

_LEASE_PATH = os.environ.get(
    "CC_LEASE_PATH",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "chromeconnect_lease.json",
    ),
)

DEFAULT_IDLE_MINUTES = int(os.environ.get("CC_LEASE_IDLE_MINUTES", "30"))


class LeaseState(str, Enum):
    UNLEASED = "unleased"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class ProfileLease:
    profile_dir: Optional[str] = None
    profile_name: Optional[str] = None
    profile_email: Optional[str] = None
    state: str = LeaseState.UNLEASED.value
    leased_at: Optional[str] = None
    last_activity: Optional[str] = None
    idle_minutes: int = DEFAULT_IDLE_MINUTES
    lease_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProfileLease":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class LeaseManager:
    """Manage the Chrome Connect profile lease."""

    def __init__(self, lease_path: str = _LEASE_PATH) -> None:
        self.lease_path = lease_path
        self._lease = self._load()

    def _load(self) -> ProfileLease:
        if os.path.exists(self.lease_path):
            try:
                with open(self.lease_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                return ProfileLease.from_dict(data)
            except (json.JSONDecodeError, OSError):
                pass
        return ProfileLease()

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self.lease_path), exist_ok=True)
        with open(self.lease_path, "w", encoding="utf-8") as fh:
            json.dump(self._lease.to_dict(), fh, indent=2)

    @property
    def lease(self) -> ProfileLease:
        return self._lease

    @property
    def is_active(self) -> bool:
        if self._lease.state != LeaseState.ACTIVE.value:
            return False
        if not self._lease.last_activity:
            return False
        # Check idle timeout
        last = datetime.fromisoformat(self._lease.last_activity.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        idle_seconds = (now - last).total_seconds()
        if idle_seconds > self._lease.idle_minutes * 60:
            self._lease.state = LeaseState.EXPIRED.value
            self._save()
            return False
        return True

    def acquire(self, profile_dir: str, profile_name: str = "", profile_email: str = "") -> ProfileLease:
        """Acquire a lease for a profile (operator picks in picker)."""
        import uuid
        self._lease = ProfileLease(
            profile_dir=profile_dir,
            profile_name=profile_name,
            profile_email=profile_email,
            state=LeaseState.ACTIVE.value,
            leased_at=datetime.now(timezone.utc).isoformat(),
            last_activity=datetime.now(timezone.utc).isoformat(),
            idle_minutes=DEFAULT_IDLE_MINUTES,
            lease_id=str(uuid.uuid4()),
        )
        self._save()
        return self._lease

    def touch(self) -> bool:
        """Keep the lease alive (any Chrome Connect action calls this)."""
        if self._lease.state != LeaseState.ACTIVE.value:
            return False
        self._lease.last_activity = datetime.now(timezone.utc).isoformat()
        self._save()
        return True

    def revoke(self) -> None:
        """Revoke the lease (operator action)."""
        self._lease.state = LeaseState.REVOKED.value
        self._lease.last_activity = None
        self._save()

    def status(self) -> Dict[str, Any]:
        """Return lease status for diagnostics."""
        return {
            "state": self._lease.state,
            "is_active": self.is_active,
            "profile_dir": self._lease.profile_dir,
            "profile_name": self._lease.profile_name,
            "profile_email": self._lease.profile_email,
            "leased_at": self._lease.leased_at,
            "last_activity": self._lease.last_activity,
            "idle_minutes": self._lease.idle_minutes,
            "lease_id": self._lease.lease_id,
            "idle_seconds": self._idle_seconds(),
        }

    def _idle_seconds(self) -> Optional[float]:
        if not self._lease.last_activity:
            return None
        last = datetime.fromisoformat(self._lease.last_activity.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        return round((now - last).total_seconds(), 1)


# ---------------------------------------------------------------------------
# Policy change record
# ---------------------------------------------------------------------------

POLICY_CHANGE_LOG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports", "policy_change_lease_20261027.md",
)


def record_policy_change() -> str:
    """Record the policy change: profile lease replaces signed-out requirement."""
    content = """# Policy Change: Profile Lease Replaces Signed-Out Requirement

**Date:** 2026-10-27
**Authorized by:** Owner (standing authorization)
**Change:** Chrome Connect's isolation requirement changes from "signed-out profile" to "leased profile".

## Rationale
- Profile 7 "Northstar Research" has session cookies (Google LSID, Alibaba auth cookies)
  despite being signed out of Google account. Cookie store is not clean.
- The signed-out requirement blocks all Chrome Connect runs because no profile
  is truly clean (all 8 Chrome profiles have some cookies).
- The profile lease allows the operator to pick any profile via the native picker.
  The lease stays alive during unattended runs. Any Chrome Connect action keeps
  the lease alive (resets idle timer). Default idle timeout: 30 minutes.

## What changed
- `chrome_signed_out` is no longer a REQUIRED check for isolated runs.
- Instead, `profile_leased` (lease state ACTIVE and not expired) is REQUIRED.
- The operator picks the profile once via the picker. Chrome Connect never
  chooses a profile for the operator.
- The lease is stored locally (data/chromeconnect_lease.json), never committed.
- Cookie metadata scan still runs (if authorized) to report session cookies,
  but no longer blocks execution.

## What did NOT change
- Operator-owned allowlist (unchanged)
- Hardcoded Amazon blocklist (unchanged)
- Lessons are PROPOSED-only (unchanged)
- No credentials entered, no CAPTCHA solved (unchanged)
- Single controller rule (unchanged)
- No stealth/anti-bot (unchanged)

## Implementation
- `Northstar_backend/chromeconnect_profile_lease.py` — lease manager
- Lease state: UNLEASED → ACTIVE → EXPIRED → REVOKED
- Configurable idle timeout (default 30 min)
- Any Chrome Connect action calls `touch()` to keep lease alive
"""
    os.makedirs(os.path.dirname(POLICY_CHANGE_LOG), exist_ok=True)
    with open(POLICY_CHANGE_LOG, "w", encoding="utf-8") as fh:
        fh.write(content)
    return POLICY_CHANGE_LOG
