"""Phase F/S11a — Golden Goose reliability toolkit tests (offline)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.gg_reliability import (  # noqa: E402
    CircuitBreaker,
    CircuitOpenError,
    DeadLetterQueue,
    RetryPolicy,
    UNKNOWN_SELLER_TIER,
    graceful_unknown,
    idempotency_key,
    retryable,
)


# --- idempotency (#3) ---

def test_idempotency_key_deterministic():
    a = idempotency_key("run-1", "B0X", "product")
    b = idempotency_key("run-1", "B0X", "product")
    assert a == b and a.startswith("idem_")
    assert idempotency_key("run-1", "B0X", "product") != idempotency_key("run-1", "B0Y", "product")


# --- retries (#1) ---

def test_retry_succeeds_after_failures():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("boom")
        return "ok"

    assert retryable(flaky, RetryPolicy(max_attempts=4, base_delay=0.01)) == "ok"
    assert calls["n"] == 3


def test_retry_raises_after_exhausted():
    def always_fail():
        raise ValueError("x")

    with pytest.raises(ValueError):
        retryable(always_fail, RetryPolicy(max_attempts=2, base_delay=0.01))


# --- circuit breaker (#2) ---

def test_circuit_breaker_fails_fast_when_open():
    cb = CircuitBreaker(failure_threshold=2, reset_seconds=100)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            cb(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.is_open is True
    with pytest.raises(CircuitOpenError):
        cb(lambda: "never-called")


def test_circuit_breaker_recovery_and_success():
    cb = CircuitBreaker(failure_threshold=1, reset_seconds=100)
    with pytest.raises(RuntimeError):
        cb(lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert cb.is_open is True
    cb.record_success()
    assert cb.is_open is False
    assert cb(lambda: "ok") == "ok"


# --- dead letter (#4) ---

def test_dead_letter_queue(tmp_path):
    dlq = DeadLetterQueue(path=tmp_path / "dlq.jsonl")
    e = dlq.put(topic="enrich", payload={"asin": "B0X"}, error="provider_error")
    assert e["topic"] == "enrich" and len(dlq) == 1
    assert dlq.path.exists() and "provider_error" in dlq.path.read_text(encoding="utf-8")
    assert len(dlq.drain()) == 1 and len(dlq) == 0


# --- graceful degradation (#6) ---

def test_graceful_unknown():
    assert graceful_unknown(None) == UNKNOWN_SELLER_TIER
    assert graceful_unknown("verified") == "verified"