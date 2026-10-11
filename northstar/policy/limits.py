"""Per-domain rate limits + per-run request/byte/time budgets (Phase 2).

Deterministic: clocks are injected, so every limit is unit-testable without
sleeping.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Mapping

from .errors import PolicyConfigError, PolicyDenied


class RateLimiter:
    """Token bucket per domain (continuous refill; deterministic with a fake clock)."""

    def __init__(
        self,
        *,
        rate_per_minute: float = 60.0,
        burst: float | None = None,
        per_domain: Mapping[str, float] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if rate_per_minute <= 0:
            raise PolicyConfigError("rate must be > 0")
        self.rate = float(rate_per_minute)
        self.burst = float(burst if burst is not None else max(1.0, self.rate))
        self.per_domain = {k.lower(): float(v) for k, v in (per_domain or {}).items()}
        self.clock = clock
        self._state: dict[str, tuple[float, float]] = {}

    def check(self, domain: str) -> None:
        d = domain.lower()
        rate = self.per_domain.get(d, self.rate)
        burst = max(1.0, rate if d in self.per_domain else self.burst)
        now = self.clock()
        tokens, last = self._state.get(d, (burst, now))
        tokens = min(burst, tokens + (now - last) * rate / 60.0)
        if tokens < 1.0:
            raise PolicyDenied("rate_limited", d)
        self._state[d] = (tokens - 1.0, now)


@dataclass
class RunBudget:
    """Per-run caps: requests, total bytes, wall-clock seconds."""

    max_requests: int
    max_bytes: int
    max_seconds: float
    clock: Callable[[], float] = time.monotonic
    _started: float = field(init=False)
    _requests: int = 0
    _bytes: int = 0

    def __post_init__(self) -> None:
        if self.max_requests < 0 or self.max_bytes < 0 or self.max_seconds < 0:
            raise PolicyConfigError("budget limits must be >= 0")
        self._started = self.clock()

    def check_time(self) -> None:
        if self.clock() - self._started > self.max_seconds:
            raise PolicyDenied("budget_time")

    def consume_request(self) -> None:
        self.check_time()
        if self._requests + 1 > self.max_requests:
            raise PolicyDenied("budget_requests")
        self._requests += 1

    def consume_bytes(self, n: int) -> None:
        if n < 0:
            raise PolicyConfigError("negative byte count")
        if self._bytes + n > self.max_bytes:
            raise PolicyDenied("budget_bytes")
        self._bytes += n


def check_response_size(size: int, limit: int) -> None:
    if size > limit:
        raise PolicyDenied("response_too_large", f"{size}>{limit}")
