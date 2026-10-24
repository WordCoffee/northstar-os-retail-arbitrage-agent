"""Durable feedback-loop breaker for the Northstar harness (AgentConnect L1 clone).

This is a pattern port from AgentConnect's loop-safety spec
(docs/designs/loop-breaker-design.md, Apache-2.0), rewritten in Python for our
data layer. It is deliberately wider than rate_limiter.py (HTTP edge buckets):
this is an *incident* mechanism, not a fair scheduler.

Semantics cloned, in their own words where they matter:

* A feedback loop is a causal cycle, not repetition. A rate limiter only slows
  one down; once an incident is confirmed, the breaker stays durably OPEN,
  cancels related execution, and only a trusted human resumes it. **There is no
  cooldown and no automatic expiry of an OPEN latch.**
* Fixed-window counters with strict greater-than thresholds (AgentConnect:
  8 automatic turns, 60 total turns per 60s). A trusted human clears the
  automatic streak but never the total-rate backstop.
* A poison fast path trips the latch immediately instead of counting a
  worthless ninth event.
* Dedup and the breaker answer different questions; a dedup'ed redelivery never
  increments the counter.
* Counting happens at the actual admission seam; callers must pass a counted
  event through here, not increment their own counters.

Scope keys are plain strings, agreed by convention: ``"cie:cycle"`` for the
knowledge cycle, ``"host:<domain>"`` for a host lane, ``"agent:<role>"`` for a
retry-prone agent chain. Scope deliberately excludes fine-grained identities so
one incident is shared, exactly like AgentConnect excludes agentId from scope.

Agent-to-agent chains use :func:`check_hop` — a trusted hop cap, where a
plausible-looking hop count in message *bodies* is never trusted; only caller
supplied metadata is.

Never raises for lifecycle reasons: every answer is a typed result.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("northstar.loop_breaker")

WINDOW_SECONDS = 60
MAX_AUTOMATIC = 8          # strict greater-than: 1-8 admitted, 9 opens the latch
MAX_TOTAL = 60
HOP_LIMIT = 5
FAILURE_LATCH = 8          # consecutive hard failures trip the poison latch

#: Optional host hook; called once on the first OPEN, never on re-checks.
ON_OPEN: Optional[Callable[[str, Dict[str, Any]], None]] = None

_OPEN_SCOPES: List[str] = []   # de-dupes the "warn once" guarantee per process


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure(db: sqlite3.Connection) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS loop_guard (
               scope_key TEXT PRIMARY KEY,
               window_started_at TEXT NOT NULL,
               total_count INTEGER NOT NULL DEFAULT 0,
               automatic_window_started_at TEXT NOT NULL,
               automatic_count INTEGER NOT NULL DEFAULT 0,
               tripped_at TEXT,
               reason TEXT,
               last_dedup TEXT,
               last_dedup_at TEXT,
               consecutive_failures INTEGER NOT NULL DEFAULT 0,
               last_outcome TEXT
           )"""
    )


def _row(db: sqlite3.Connection, scope: str) -> Dict[str, Any]:
    cur = db.execute(
        "SELECT * FROM loop_guard WHERE scope_key = ?", (scope,)
    )
    row = cur.fetchone()
    if row is None:
        cols: Dict[str, Any] = {
            "scope_key": scope, "window_started_at": _now().isoformat(),
            "total_count": 0, "automatic_window_started_at": _now().isoformat(),
            "automatic_count": 0, "tripped_at": None, "reason": None,
            "last_dedup": None, "last_dedup_at": None,
            "consecutive_failures": 0, "last_outcome": None,
        }
        db.execute(
            """INSERT INTO loop_guard (scope_key, window_started_at, total_count,
                   automatic_window_started_at, automatic_count)
               VALUES (?, ?, 0, ?, 0)""",
            (scope, cols["window_started_at"], cols["automatic_window_started_at"]),
        )
        return cols
    keys = [k[0] for k in cur.description]
    return dict(zip(keys, row))


def state(scope: str, db: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Read-only latch/counter view. Never mutates."""
    handle = db if db is not None else _default_db()
    _ensure(handle)
    row = _row(handle, scope)
    return {
        "scope": scope,
        "state": "open" if row["tripped_at"] else "closed",
        "tripped_at": row["tripped_at"],
        "reason": row["reason"],
        "total_count": row["total_count"],
        "automatic_count": row["automatic_count"],
        "consecutive_failures": row["consecutive_failures"],
    }


def _default_db() -> sqlite3.Connection:
    from data_layer import get_db
    return get_db()


def _trip(row: Dict[str, Any], reason: str, handle: sqlite3.Connection,
          now_value: datetime) -> Dict[str, Any]:
    row["tripped_at"] = now_value.isoformat()
    row["reason"] = reason
    handle.execute(
        "UPDATE loop_guard SET tripped_at = ?, reason = ? WHERE scope_key = ?",
        (row["tripped_at"], reason, row["scope_key"]),
    )
    if ON_OPEN is not None and row["scope_key"] not in _OPEN_SCOPES:
        _OPEN_SCOPES.append(row["scope_key"])
        try:
            ON_OPEN(row["scope_key"], state(row["scope_key"], handle))
        except Exception:  # noqa: BLE001 - the latch itself must never fail to warn
            logger.exception("loop breaker on_open hook failed")
    logger.warning("loop breaker OPEN: scope=%s reason=%s", row["scope_key"], reason)
    return {"admitted": False, "state": "open", "reason": reason,
            "tripped_at": row["tripped_at"], "deduplicated": False}


def admit(scope: str, *, trusted_human: bool = False, poisoned: bool = False,
          dedup_key: Optional[str] = None, failed_outcome: Optional[str] = None,
          db: Optional[sqlite3.Connection] = None,
          now_fn: Optional[Callable[[], datetime]] = None) -> Dict[str, Any]:
    """Admission seam. Count the event, then decide, in the breaker's own terms.

    ``failed_outcome``: a short code recording a hard failure for this scope.
    A run of :data:`FAILURE_LATCH` consecutive hard failures trips the latch
    (the poison path for harness stages that crash rather than spew events).
    """
    handle = db if db is not None else _default_db()
    now = (now_fn or _now)()
    _ensure(handle)
    row = _row(handle, scope)

    # O(1) latch check first: after OPEN each event costs one query, not a scan.
    if row["tripped_at"]:
        return {"admitted": False, "state": "open", "reason": row["reason"],
                "tripped_at": row["tripped_at"], "deduplicated": False}

    if poisoned:
        return _trip(row, "malformed_signal", handle, now)

    # Dedup before counting: a redelivery is not a new event.
    if dedup_key is not None and row["last_dedup"] == dedup_key \
            and row["last_dedup_at"]:
        age = (now - datetime.fromisoformat(row["last_dedup_at"])).total_seconds()
        if age <= WINDOW_SECONDS:
            return {"admitted": False, "state": "closed",
                    "reason": "redelivery_deduplicated", "deduplicated": True}

    # Fixed windows refresh independently.
    if row["window_started_at"]:
        started = datetime.fromisoformat(row["window_started_at"])
        if (now - started).total_seconds() > WINDOW_SECONDS:
            row["window_started_at"] = now.isoformat()
            row["total_count"] = 0
    if row["automatic_window_started_at"]:
        started = datetime.fromisoformat(row["automatic_window_started_at"])
        if (now - started).total_seconds() > WINDOW_SECONDS:
            row["automatic_window_started_at"] = now.isoformat()
            row["automatic_count"] = 0

    # A trusted human clears the automatic streak but never the total backstop.
    if trusted_human:
        row["automatic_window_started_at"] = now.isoformat()
        row["automatic_count"] = 0
    else:
        row["automatic_count"] += 1
    row["total_count"] += 1

    outcome_code: Optional[str] = None
    if failed_outcome:
        row["consecutive_failures"] = int(row["consecutive_failures"]) + 1
        outcome_code = str(failed_outcome)[:40]
    else:
        row["consecutive_failures"] = 0

    if row["consecutive_failures"] >= FAILURE_LATCH:
        _persist(row, handle)
        return _trip(row, "failure_burst", handle, now)
    if row["automatic_count"] > MAX_AUTOMATIC:
        _persist(row, handle)
        return _trip(row, "automatic_burst", handle, now)
    if row["total_count"] > MAX_TOTAL:
        _persist(row, handle)
        return _trip(row, "rate_burst", handle, now)

    _persist(row, handle, dedup_key=dedup_key, now_value=now,
             outcome=outcome_code)
    return {"admitted": True, "state": "closed", "reason": None,
            "tripped_at": None, "deduplicated": False,
            "total_count": row["total_count"],
            "automatic_count": row["automatic_count"]}


def _persist(row: Dict[str, Any], handle: sqlite3.Connection,
             dedup_key: Optional[str] = None,
             now_value: Optional[datetime] = None,
             outcome: Optional[str] = None) -> None:
    if dedup_key is not None and now_value is not None:
        row["last_dedup"] = dedup_key
        row["last_dedup_at"] = now_value.isoformat()
    if outcome is not None:
        row["last_outcome"] = outcome
    handle.execute(
        """UPDATE loop_guard SET window_started_at = ?, total_count = ?,
               automatic_window_started_at = ?, automatic_count = ?,
               last_dedup = ?, last_dedup_at = ?,
               consecutive_failures = ?, last_outcome = ?
           WHERE scope_key = ?""",
        (row["window_started_at"], row["total_count"],
         row["automatic_window_started_at"], row["automatic_count"],
         row["last_dedup"], row["last_dedup_at"],
         row["consecutive_failures"], row["last_outcome"], row["scope_key"]),
    )


def note(scope: str, *, ok: bool, failure_code: str = "hard_failure",
         db: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Record an outcome WITHOUT counting another event.

    A cycle is admitted once at its seam (``admit``); its result arrives here.
    Consecutive hard failures across sparse, in-budget runs are exactly the
    poison case ``failure_burst`` exists for.
    """
    handle = db if db is not None else _default_db()
    now = _now()
    _ensure(handle)
    row = _row(handle, scope)

    if row["tripped_at"]:
        return {"noted": False, "state": "open", "reason": row["reason"]}

    if ok:
        row["consecutive_failures"] = 0
        row["last_outcome"] = None
    else:
        row["consecutive_failures"] = int(row["consecutive_failures"]) + 1
        row["last_outcome"] = str(failure_code)[:40]
        if row["consecutive_failures"] >= FAILURE_LATCH:
            handle.execute(
                "UPDATE loop_guard SET consecutive_failures = ?, last_outcome = ? WHERE scope_key = ?",
                (row["consecutive_failures"], row["last_outcome"], scope))
            return _trip(row, "failure_burst", handle, now)

    handle.execute(
        "UPDATE loop_guard SET consecutive_failures = ?, last_outcome = ? WHERE scope_key = ?",
        (row["consecutive_failures"], row["last_outcome"], scope))
    return {"noted": True, "state": "closed",
            "consecutive_failures": row["consecutive_failures"]}


def reset(scope: str, *, actor: str = "agent", confirmed: bool = False,
          db: Optional[sqlite3.Connection] = None) -> Dict[str, Any]:
    """Explicit resume. Only a trusted operator, with an explicit confirmation.

    Deleting the latch never revives purged work - callers own that rule.
    """
    if actor != "operator" or not confirmed:
        return {"reset": False,
                "reason": "only an operator with confirmed=True resumes a scope"}
    handle = db if db is not None else _default_db()
    _ensure(handle)
    cur = handle.execute("DELETE FROM loop_guard WHERE scope_key = ?", (scope,))
    if scope in _OPEN_SCOPES:
        _OPEN_SCOPES.remove(scope)
    return {"reset": True, "had_latch": cur.rowcount > 0}


def check_hop(*, hop_count: int = 0, self_call: bool = False) -> Dict[str, Any]:
    """L2 trusted agent-call guard: exact hop accounting or an explicit NAK.

    Callers pass trusted chain metadata they computed themselves. A hop count
    read out of some message body is NOT trusted metadata and must never reach
    this function as evidence.
    """
    if self_call:
        return {"admitted": False, "code": "self", "reason": "an agent cannot wake itself"}
    if hop_count > HOP_LIMIT:
        return {"admitted": False, "code": "hop_limit",
                "reason": f"chain exceeded {HOP_LIMIT} trusted hops"}
    return {"admitted": True, "code": None, "reason": None}
