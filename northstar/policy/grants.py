"""Capability grants (Phase 2).

Each task gets an explicit capability list (e.g. ``fetch:allowed-domain-x``).
Default is NONE; grants expire at task end (``release``) or after a TTL.
Matches are exact for generic capabilities; for fetch grants, a granted parent
domain also covers its subdomains.
"""
from __future__ import annotations

import time
from typing import Callable, Iterable

from .errors import PolicyConfigError, PolicyDenied


def fetch_capability(host: str) -> str:
    return f"fetch:{host.lower().rstrip('.')}"


class GrantSet:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self.clock = clock
        self._grants: dict[str, tuple[tuple[str, ...], float | None]] = {}

    def issue(
        self, task_id: str, capabilities: Iterable[str], ttl_seconds: float | None = None
    ) -> None:
        if not task_id:
            raise PolicyConfigError("task_id required")
        caps = tuple(sorted({c.strip() for c in capabilities if c and c.strip()}))
        deadline = None if ttl_seconds is None else self.clock() + ttl_seconds
        self._grants[task_id] = (caps, deadline)

    def release(self, task_id: str) -> None:
        self._grants.pop(task_id, None)

    def capabilities(self, task_id: str) -> tuple[str, ...]:
        entry = self._grants.get(task_id)
        return entry[0] if entry else ()

    def _live(self, task_id: str) -> tuple[str, ...] | None:
        entry = self._grants.get(task_id)
        if entry is None:
            return None
        caps, deadline = entry
        if deadline is not None and self.clock() >= deadline:
            return None
        return caps

    def _absent_reason(self, task_id: str) -> str:
        return "capability_expired" if task_id in self._grants else "capability_missing"

    def check(self, task_id: str, capability: str) -> None:
        caps = self._live(task_id)
        if caps is None:
            raise PolicyDenied(self._absent_reason(task_id), capability)
        if capability not in caps:
            raise PolicyDenied("capability_missing", capability)

    def check_fetch(self, task_id: str, host: str) -> None:
        caps = self._live(task_id)
        if caps is None:
            raise PolicyDenied(self._absent_reason(task_id), fetch_capability(host))
        h = host.lower().rstrip(".")
        for cap in caps:
            if not cap.startswith("fetch:"):
                continue
            granted = cap[len("fetch:") :]
            if h == granted or h.endswith("." + granted):
                return
        raise PolicyDenied("capability_missing", fetch_capability(h))
