"""Resource and budget throttling, hyperparameter tuning, feedback routing.

The rule: **a cap that cannot refuse is not a cap.** Every limit in this module
raises a stable code instead of degrading silently, and every refusal names the
budget and the numbers involved.

Contents
--------
``TokenBucket``     classic refillable bucket, injectable clock, no sleeping.
``BudgetGuard``     per-task and per-day token caps, persisted, fail-closed.
``VramBudget``      reservation against the single 16 GB card; refuses rather
                    than queues, because queueing hides the contention.
``Complexity``      deterministic classification used by the tuner.
``Tuner``           UCB1 over a small, fixed set of parameter choices per
                    complexity bucket. Deterministic seed, bounded exploration.
``FeedbackRouter``  lane weights updated by ratings and corrections with decay.
"""

from __future__ import annotations

import json
import math
import os
import random
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

DEFAULT_TASK_CAP = 20000
DEFAULT_DAILY_CAP = 250000


class BudgetExceeded(RuntimeError):
    def __init__(self, code: str, detail: str = "", **extra: Any):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail
        self.extra = extra

    def as_dict(self) -> Dict[str, Any]:
        out = {"code": self.code, "detail": self.detail}
        out.update(self.extra)
        return out


def _atomic_json(path: str, payload: Dict[str, Any]) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".budget-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


class TokenBucket:
    """Refillable bucket with an injectable clock (no test sleeps)."""

    def __init__(self, rate_per_s: float, burst: int):
        if rate_per_s <= 0 or burst <= 0:
            raise ValueError("rate and burst must be positive")
        self.rate = float(rate_per_s)
        self.burst = int(burst)
        self._tokens = float(burst)
        self._stamp: Optional[float] = None

    def allow(self, cost: float = 1.0, now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else float(now)
        if self._stamp is None:
            self._stamp = stamp
        elapsed = max(0.0, stamp - self._stamp)
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._stamp = stamp
        if self._tokens >= cost:
            self._tokens -= cost
            return {"allowed": True, "tokens": round(self._tokens, 3),
                    "retry_after_s": 0.0}
        deficit = cost - self._tokens
        return {"allowed": False, "tokens": round(self._tokens, 3),
                "retry_after_s": round(deficit / self.rate, 3)}


class BudgetGuard:
    """Per-task and per-day token caps, persisted and fail-closed."""

    SCHEMA = "tys.budget.v1"

    def __init__(self, path: str, *, task_cap: int = DEFAULT_TASK_CAP,
                 daily_cap: int = DEFAULT_DAILY_CAP):
        self.path = path
        self.task_cap = int(task_cap)
        self.daily_cap = int(daily_cap)
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {"schema": self.SCHEMA, "profiles": {}}
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("profiles", {})
        return data

    def _save(self) -> None:
        _atomic_json(self.path, self._state)

    def _slot(self, profile: str, now: float) -> Dict[str, Any]:
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        slot = self._state["profiles"].setdefault(
            profile, {"day": day, "day_tokens": 0, "task_id": None,
                      "task_tokens": 0, "refusals": 0})
        if slot.get("day") != day:
            slot.update({"day": day, "day_tokens": 0})
        return slot

    def start_task(self, profile: str, task_id: str, *,
                   cap: Optional[int] = None, now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else now
        with self._lock:
            slot = self._slot(profile, stamp)
            slot["task_id"] = task_id
            slot["task_tokens"] = 0
            slot["task_cap"] = int(cap or self.task_cap)
            self._save()
            return {"profile": profile, "task_id": task_id,
                    "task_cap": slot["task_cap"]}

    def consume(self, profile: str, tokens: int, *,
                now: Optional[float] = None) -> Dict[str, Any]:
        tokens = int(tokens)
        if tokens < 0:
            raise ValueError("tokens must be >= 0")
        stamp = time.time() if now is None else now
        with self._lock:
            slot = self._slot(profile, stamp)
            task_cap = int(slot.get("task_cap") or self.task_cap)
            task_after = int(slot.get("task_tokens") or 0) + tokens
            day_after = int(slot.get("day_tokens") or 0) + tokens
            if task_after > task_cap:
                slot["refusals"] = int(slot.get("refusals") or 0) + 1
                self._save()
                raise BudgetExceeded(
                    "task_budget_exceeded",
                    f"task would reach {task_after} tokens, cap {task_cap}",
                    profile=profile, requested=tokens,
                    used=int(slot.get("task_tokens") or 0), cap=task_cap)
            if day_after > self.daily_cap:
                slot["refusals"] = int(slot.get("refusals") or 0) + 1
                self._save()
                raise BudgetExceeded(
                    "daily_budget_exceeded",
                    f"day would reach {day_after} tokens, cap {self.daily_cap}",
                    profile=profile, requested=tokens,
                    used=int(slot.get("day_tokens") or 0), cap=self.daily_cap)
            slot["task_tokens"] = task_after
            slot["day_tokens"] = day_after
            self._save()
            return {"profile": profile, "task_tokens": task_after,
                    "task_cap": task_cap, "day_tokens": day_after,
                    "day_cap": self.daily_cap,
                    "remaining_task": task_cap - task_after,
                    "remaining_day": self.daily_cap - day_after}

    def status(self, profile: str, now: Optional[float] = None) -> Dict[str, Any]:
        stamp = time.time() if now is None else now
        with self._lock:
            slot = self._slot(profile, stamp)
            task_cap = int(slot.get("task_cap") or self.task_cap)
            return {
                "profile": profile,
                "task_id": slot.get("task_id"),
                "task_tokens": int(slot.get("task_tokens") or 0),
                "task_cap": task_cap,
                "day_tokens": int(slot.get("day_tokens") or 0),
                "day_cap": self.daily_cap,
                "refusals": int(slot.get("refusals") or 0),
            }


class VramBudget:
    """Reservation against one card. Refuses when full; never queues."""

    def __init__(self, total_mb: int = 16303):
        self.total_mb = int(total_mb)
        self._used = 0
        self._holders: Dict[str, int] = {}
        self._lock = threading.RLock()

    def reserve(self, lane: str, mb: int) -> Dict[str, Any]:
        mb = int(mb)
        if mb <= 0:
            raise ValueError("mb must be positive")
        with self._lock:
            if mb > self.total_mb:
                raise BudgetExceeded("vram_too_large",
                                     f"{mb} MB exceeds the {self.total_mb} MB card")
            if self._used + mb > self.total_mb:
                raise BudgetExceeded(
                    "vram_busy",
                    f"{lane} needs {mb} MB, {self.total_mb - self._used} MB free",
                    free_mb=self.total_mb - self._used, holders=dict(self._holders))
            self._used += mb
            self._holders[lane] = self._holders.get(lane, 0) + mb
            return {"lane": lane, "reserved_mb": mb, "used_mb": self._used,
                    "free_mb": self.total_mb - self._used}

    def release(self, lane: str) -> Dict[str, Any]:
        with self._lock:
            held = self._holders.pop(lane, 0)
            self._used = max(0, self._used - held)
            return {"lane": lane, "released_mb": held, "used_mb": self._used,
                    "free_mb": self.total_mb - self._used}

    def report(self) -> Dict[str, Any]:
        with self._lock:
            return {"total_mb": self.total_mb, "used_mb": self._used,
                    "free_mb": self.total_mb - self._used,
                    "holders": dict(self._holders)}


# ---------------------------------------------------------------------------
# Complexity + tuning
# ---------------------------------------------------------------------------

_COMPLEX_HINTS = ("refactor", "architect", "migrate", "benchmark", "stress",
                  "multi", "integration", "repair", "rollback")
_SIMPLE_HINTS = ("list", "status", "state", "read", "show", "inspect")


def complexity(objective: str) -> str:
    text = (objective or "").lower()
    words = len(text.split())
    if any(hint in text for hint in _COMPLEX_HINTS) or words > 45:
        return "high"
    if any(hint in text for hint in _SIMPLE_HINTS) and words <= 20:
        return "low"
    return "medium"


CANDIDATES: Dict[str, List[Dict[str, Any]]] = {
    "low": [
        {"id": "l0", "temperature": 0.0, "top_p": 0.8, "context_tokens": 4096},
        {"id": "l1", "temperature": 0.1, "top_p": 0.9, "context_tokens": 8192},
    ],
    "medium": [
        {"id": "m0", "temperature": 0.2, "top_p": 0.9, "context_tokens": 16384},
        {"id": "m1", "temperature": 0.3, "top_p": 0.95, "context_tokens": 32768},
    ],
    "high": [
        {"id": "h0", "temperature": 0.4, "top_p": 0.95, "context_tokens": 65536},
        {"id": "h1", "temperature": 0.2, "top_p": 0.9, "context_tokens": 65536},
    ],
}


class Tuner:
    """UCB1 over a fixed candidate set per complexity bucket.

    Two candidates per bucket keeps exploration honest and bounded: with a
    fixed budget there is no room for a search that never converges.
    """

    SCHEMA = "tys.tuner.v1"

    def __init__(self, path: str, *, seed: int = 7):
        self.path = path
        self._lock = threading.RLock()
        self._random = random.Random(seed)
        self._state = self._load()

    def _load(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            return {"schema": self.SCHEMA, "buckets": {}}
        with open(self.path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        data.setdefault("buckets", {})
        return data

    def _save(self) -> None:
        _atomic_json(self.path, self._state)

    def _bucket(self, name: str) -> Dict[str, Any]:
        return self._state["buckets"].setdefault(name, {"arms": {}, "total": 0})

    def choose(self, bucket: str) -> Dict[str, Any]:
        with self._lock:
            state = self._bucket(bucket)
            arms = CANDIDATES[bucket]
            total = int(state["total"])
            best, best_score = None, -1.0
            for arm in arms:
                record = state["arms"].setdefault(arm["id"], {"n": 0, "mean": 0.0})
                if record["n"] == 0:
                    score = 1e9 + self._random.random()  # explore untouched arms
                else:
                    score = record["mean"] + math.sqrt(
                        2.0 * math.log(total + 1) / record["n"])
                if score > best_score:
                    best, best_score = arm, score
            return {"bucket": bucket, "params": dict(best),
                    "score": round(best_score, 4) if best_score < 1e9 else None}

    def feedback(self, bucket: str, arm_id: str, score: float) -> Dict[str, Any]:
        if not (0.0 <= float(score) <= 1.0):
            raise ValueError("score must be within [0, 1]")
        with self._lock:
            state = self._bucket(bucket)
            record = state["arms"].setdefault(arm_id, {"n": 0, "mean": 0.0})
            record["n"] += 1
            record["mean"] += (float(score) - record["mean"]) / record["n"]
            state["total"] = int(state["total"]) + 1
            self._save()
            return {"bucket": bucket, "arm": arm_id, "n": record["n"],
                    "mean": round(record["mean"], 4)}

    def report(self) -> Dict[str, Any]:
        with self._lock:
            out: Dict[str, Any] = {}
            for bucket, state in self._state["buckets"].items():
                arms = state["arms"]
                leader = max(arms.items(), key=lambda kv: kv[1]["mean"]) \
                    if arms else None
                out[bucket] = {
                    "trials": state["total"],
                    "arms": {k: {"n": v["n"], "mean": round(v["mean"], 4)}
                             for k, v in arms.items()},
                    "leader": leader[0] if leader else None,
                }
            return out


class FeedbackRouter:
    """Lane preference from ratings and corrections, with exponential decay."""

    LANES = ("inspect", "coding", "browser", "creative")

    def __init__(self, decay: float = 0.9):
        self.decay = float(decay)
        self._weights = {lane: 1.0 for lane in self.LANES}
        self._samples = 0
        self._lock = threading.RLock()

    def record(self, lane: str, rating: float, *, corrected: bool = False) -> Dict[str, Any]:
        if lane not in self._weights:
            raise ValueError(f"unknown lane {lane!r}")
        if not (0.0 <= float(rating) <= 1.0):
            raise ValueError("rating must be within [0, 1]")
        with self._lock:
            for key in self._weights:
                self._weights[key] *= self.decay
            signal = float(rating) - (0.5 if corrected else 0.0)
            self._weights[lane] = max(0.05, self._weights[lane] + signal)
            self._samples += 1
            return {"lane": lane, "weight": round(self._weights[lane], 4),
                    "samples": self._samples}

    def rank(self, lanes: Optional[Sequence[str]] = None) -> List[str]:
        pool = list(lanes or self._weights.keys())
        with self._lock:
            return sorted(pool, key=lambda lane: -self._weights.get(lane, 1.0))

    def report(self) -> Dict[str, Any]:
        with self._lock:
            return {"samples": self._samples,
                    "weights": {k: round(v, 4) for k, v in self._weights.items()},
                    "rank": self.rank()}
