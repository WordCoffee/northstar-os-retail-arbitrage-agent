"""Golden Goose reliability toolkit (Phase F/S11 — robustness subset).

Offline, pure unless marked: implements
  #1 retries with backoff      #2 circuit breaker
  #3 idempotency keys          #4 dead-letter queue
  #6 graceful degradation (seller identity UNKNOWN tier)
No provider calls are made by this module; callers decide how to use it.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Deque, Dict, Iterable, List, Optional

# --- #3 idempotency ----------------------------------------------------------

def idempotency_key(*parts: str) -> str:
    """Deterministic key for a mutation/request (retries never double-charge)."""
    raw = "|".join("" if p is None else str(p) for p in parts)
    return "idem_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


# --- #1 retries with backoff --------------------------------------------------

@dataclass
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 8.0
    backoff_factor: float = 2.0


def retryable(fn: Callable[[], Any], policy: RetryPolicy = RetryPolicy(),
              on_retry: Optional[Callable[[int, Exception], None]] = None) -> Any:
    """Call fn with exponential backoff; raise the last error after attempts."""
    attempt = 0
    delay = policy.base_delay
    last_error: Optional[Exception] = None
    while attempt < policy.max_attempts:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - caller decides retryability
            last_error = exc
            attempt += 1
            if on_retry:
                on_retry(attempt, exc)
            if attempt >= policy.max_attempts:
                break
            time.sleep(min(delay, policy.max_delay))
            delay *= policy.backoff_factor
    assert last_error is not None
    raise last_error


# --- #2 circuit breaker --------------------------------------------------------

class CircuitOpenError(RuntimeError):
    """The circuit is open (tripped) — failing fast without a call."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_seconds: float = 60.0
    _failures: int = 0
    _opened_at: Optional[float] = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        return (time.time() - self._opened_at) < self.reset_seconds

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.time()

    def __call__(self, fn: Callable[[], Any]) -> Any:
        if self.is_open:
            raise CircuitOpenError("circuit open — failing fast, no call made")
        try:
            result = fn()
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise


# --- #4 dead-letter queue -------------------------------------------------------

@dataclass
class DeadLetterQueue:
    path: Optional[Path] = None
    _entries: Deque[Dict[str, Any]] = field(default_factory=deque)

    def put(self, *, topic: str, payload: Any, error: str) -> None:
        entry = {
            "id": "dlq_" + secrets.token_hex(10),
            "topic": topic,
            "payload": payload,
            "error": error,
            "queued_at": time.time(),
        }
        self._entries.append(entry)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")
        return entry

    def drain(self) -> List[Dict[str, Any]]:
        out = list(self._entries)
        self._entries.clear()
        return out

    def __len__(self) -> int:
        return len(self._entries)


# --- #6 graceful degradation -------------------------------------------------

UNKNOWN_SELLER_TIER = "seller_identity_unknown"


def graceful_unknown(status: Optional[str]) -> str:
    """Map a missing/unknown seller verification to the UNKNOWN tier."""
    return status if status else UNKNOWN_SELLER_TIER