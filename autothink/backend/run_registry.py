"""RunRegistry — in-process run tracking so a submitted AutothinK run can be
cancelled mid-flight.

Cancellation is only meaningful while a run is actually executing, so the
registry is deliberately in-process: it does not survive a restart, and it
never claims a run is cancellable after the process is gone. Every state
change is recorded so the audit trail can say what happened.
"""

from __future__ import annotations

import secrets
import threading
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

# Terminal states: a run that reaches one of these can never be cancelled.
TERMINAL = {"completed", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: Dict[str, Dict] = {}

    def create(self, *, org_id: Optional[str], user_id: Optional[str]) -> Dict:
        run_id = "atrun_" + secrets.token_hex(8)
        record = {
            "run_id": run_id,
            "org_id": org_id or "anonymous",
            "user_id": user_id or "unknown",
            "state": "running",
            "created_at": _now(),
            "updated_at": _now(),
            "cancel_requested": False,
        }
        with self._lock:
            self._runs[run_id] = record
        return dict(record)

    def transition(self, run_id: str, state: str) -> Optional[Dict]:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            record["state"] = state
            record["updated_at"] = _now()
            if state in TERMINAL:
                record["cancel_requested"] = False
            return dict(record)

    def request_cancel(self, run_id: str, *, org_id: Optional[str]) -> Optional[Dict]:
        """Ask a run to stop. Tenant-scoped: another org's run is invisible."""
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            if (org_id or "anonymous") != record["org_id"]:
                return None
            if record["state"] in TERMINAL:
                return dict(record)
            record["cancel_requested"] = True
            record["cancel_requested_at"] = _now()
            record["updated_at"] = _now()
            return dict(record)

    def get(self, run_id: str, *, org_id: Optional[str] = None) -> Optional[Dict]:
        with self._lock:
            record = self._runs.get(run_id)
            if record is None:
                return None
            if org_id is not None and (org_id or "anonymous") != record["org_id"]:
                return None
            return dict(record)

    def cancel_probe(self, run_id: str) -> Callable[[], bool]:
        """Return a callback the adapter can poll while streaming."""

        def _probe() -> bool:
            with self._lock:
                record = self._runs.get(run_id)
                return bool(record and record.get("cancel_requested"))

        return _probe

    def sweep(self, max_age_seconds: int = 3600) -> int:
        """Drop finished runs older than max_age_seconds. Returns the count."""
        now = datetime.now(timezone.utc)
        removed = 0
        with self._lock:
            for run_id, record in list(self._runs.items()):
                if record["state"] not in TERMINAL:
                    continue
                try:
                    stamp = datetime.fromisoformat(record["updated_at"])
                except (ValueError, TypeError):
                    continue
                if (now - stamp).total_seconds() > max_age_seconds:
                    self._runs.pop(run_id, None)
                    removed += 1
        return removed
