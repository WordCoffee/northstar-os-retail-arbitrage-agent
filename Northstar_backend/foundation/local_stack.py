"""Loopback-only local production candidate stack (1C-LC / Workstream E).

Assembles PostgreSQL 15, production-mode authentication (temporary local
signing material, local issuer/audience), a real local organization and
membership, the backend, the worker, the persisted scheduler, and the React
production build — all on loopback, with fake/local handlers only.

Temporary secrets are generated at runtime, never printed, and cleaned up on
shutdown. No external provider is ever contacted.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Optional

from .db_postgres import PostgresFoundationDB


class LocalProductionCandidate:
    def __init__(self, *, db_url: str, issuer: str, audience: str,
                 org_name: str = "Local Production", user_email: str = "owner@local.test") -> None:
        self.db_url = db_url
        self.issuer = issuer
        self.audience = audience
        self.org_name = org_name
        self.user_email = user_email
        self.state = None
        self.worker_thread: Optional[threading.Thread] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def check_target(self) -> None:
        """Refuse anything but a loopback disposable target (no staging/prod)."""
        from urllib.parse import urlparse
        u = urlparse(self.db_url)
        assert u.hostname == "127.0.0.1", f"host must be loopback, got {u.hostname}"
        assert u.port in (55432, 55433, 55434), \
            f"port must be a disposable loopback PG, got {u.port}"
        assert "northstar" in (u.path or "").lower(), "non-local database name"

    def build_state(self) -> "FoundationState":
        from .api.state import FoundationState
        self.check_target()
        self.state = FoundationState.build()
        return self.state

    def bootstrap_owner(self, token_path: Optional[str] = None) -> dict:
        """Create the local owner + membership and issue a JWT."""
        from .bootstrap import bootstrap_owner
        from .authn import jwt_secret, jwt_issuer, jwt_audience
        res = bootstrap_owner(self.state, org_name=self.org_name,
                              user_email=self.user_email, recover=True)
        user_id = res["user_id"]
        org_id = res["organization_id"]
        token = self._issue_token(user_id, org_id, res["role"])
        if token_path:
            with open(token_path, "w", encoding="utf-8") as fh:
                fh.write(token)
        return {"organization_id": org_id, "user_id": user_id,
                "role": res["role"], "token_path": token_path,
                "issuer": jwt_issuer(), "audience": jwt_audience()}

    def _issue_token(self, user_id: str, org_id: str, role: str) -> str:
        import jwt as pyjwt
        from datetime import datetime, timedelta, timezone
        from .authn import jwt_secret
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_id, "type": "access",
            "iat": now, "exp": now + timedelta(hours=1),
            "jti": f"local-prod-{org_id[:8]}",
            "tenant_id": org_id, "role": role,
            "iss": self.issuer, "aud": self.audience,
        }
        return pyjwt.encode(payload, jwt_secret(), algorithm="HS256")

    def start_worker(self, *, poll_interval: float = 0.05) -> None:
        from .jobs_worker import JobWorker
        org_id = self._org_id()
        worker = JobWorker(self.state.jobs_durable, worker_id="local-worker",
                           organization_id=org_id, poll_interval=poll_interval)

        def _loop():
            while not self._stop.is_set():
                try:
                    worker.run_once()
                except Exception:  # noqa: BLE001 - worker keeps the loop alive
                    pass
                time.sleep(poll_interval)

        self.worker_thread = threading.Thread(target=_loop, daemon=True)
        self.worker_thread.start()

    def start_scheduler(self, *, interval: float = 1.0) -> None:
        org_id = self._org_id()

        def _loop():
            while not self._stop.is_set():
                try:
                    self.state.scheduler.tick()
                except Exception:  # noqa: BLE001 - scheduler keeps the loop alive
                    pass
                time.sleep(interval)

        self.scheduler_thread = threading.Thread(target=_loop, daemon=True)
        self.scheduler_thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self.state is not None:
            self.state.close()

    def _org_id(self) -> str:
        from .models import Organization
        org = self.state.repos.organizations.list(limit=1)
        return org[0]["id"] if org else ""


def resolve_db_url() -> Optional[str]:
    """Disposable loopback PG URL from env, or None."""
    return os.environ.get("FOUNDATION_DB_URL")