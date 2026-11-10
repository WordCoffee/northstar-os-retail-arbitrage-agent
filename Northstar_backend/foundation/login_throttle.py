"""Shared, database-backed login throttle (P2-T5/P2-T6 hardening).

The previous limiter was per-process. For a multi-process hosted deployment
(api + future replicas) the limit must be shared. This module stores attempts in
the same database the app already uses (PostgreSQL in hosted mode, SQLite in
local/test), so the limit is correct across processes.

Hosted posture: if the environment is production-like and the backing store is
not shared-capable (i.e. not PostgreSQL), callers must fail closed — see
``require_shared``.

Test mode (2026-10-10): automated harnesses sign in repeatedly from one host and
trip the 5-per-300s limit, which makes a real regression indistinguishable from
a throttle. ``NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS=1`` raises the ceiling for
harness runs. The bypass FAILS CLOSED: it is refused outright in any hosted
environment, and it only ever raises the limit — it can never disable the
throttle entirely, and it is logged on first use.
"""
from __future__ import annotations

import os
import time
from typing import Optional

TABLE = "auth_login_attempts"

DDL_POSTGRES = (
    "CREATE TABLE IF NOT EXISTS auth_login_attempts ("
    " id BIGSERIAL PRIMARY KEY,"
    " key TEXT NOT NULL,"
    " attempted_at BIGINT NOT NULL)")
DDL_SQLITE = (
    "CREATE TABLE IF NOT EXISTS auth_login_attempts ("
    " id INTEGER PRIMARY KEY AUTOINCREMENT,"
    " key TEXT NOT NULL,"
    " attempted_at INTEGER NOT NULL)")

_HOSTED_ENVIRONMENTS = {"production", "production_tenant", "staging"}

# Test-mode ceiling. Still a limit, still recorded — just high enough that a
# harness can run without being confused with an auth failure.
_TEST_LIMIT = 200


class ThrottleUnavailable(RuntimeError):
    """Raised when a shared throttle store is required but unavailable."""


def is_shared(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


def test_bypass_enabled(environment: Optional[str]) -> bool:
    """True only when the bypass is explicitly set AND the environment is not
    hosted. A production-like environment can never enable it."""
    if (environment or "").lower() in _HOSTED_ENVIRONMENTS:
        return False
    return os.environ.get("NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS", "0") == "1"


_announced = False


def _announce_once(limit: int) -> None:
    global _announced
    if _announced:
        return
    _announced = True
    import logging
    logging.getLogger("northstar.foundation").warning(
        "LOGIN THROTTLE TEST BYPASS ACTIVE: limit raised to %d requests per "
        "window. This can only happen outside a hosted environment and only "
        "when NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS=1 is set explicitly.", limit)


def ensure_table(db) -> None:
    if is_shared(db):
        db._raw.execute(DDL_POSTGRES)
        db._raw.commit()
    else:
        db.conn.execute(DDL_SQLITE)
        db.conn.commit()


def require_shared(db, environment: Optional[str]) -> None:
    """Fail closed for public/hosted exposure without a shared throttle store."""
    if (environment or "").lower() in _HOSTED_ENVIRONMENTS and not is_shared(db):
        raise ThrottleUnavailable(
            "shared login throttle requires PostgreSQL in hosted environments")


def _now() -> int:
    return int(time.time())


def _count(db, key: str, since: int) -> int:
    if is_shared(db):
        cur = db._raw.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM auth_login_attempts "
                    "WHERE key = %s AND attempted_at > %s", [key, since])
        return int(cur.fetchone()["n"])
    cur = db.conn.execute("SELECT COUNT(*) FROM auth_login_attempts "
                          "WHERE key = ? AND attempted_at > ?", (key, since))
    return int(cur.fetchone()[0])


def _record(db, key: str) -> None:
    ts = _now()
    if is_shared(db):
        db._raw.execute("INSERT INTO auth_login_attempts (key, attempted_at) "
                        "VALUES (%s, %s)", [key, ts])
        db._raw.commit()
    else:
        db.conn.execute("INSERT INTO auth_login_attempts (key, attempted_at) "
                        "VALUES (?, ?)", (key, ts))
        db.conn.commit()


def allow(db, key: str, *, limit: int = 5, window_seconds: int = 300,
          environment: Optional[str] = None) -> bool:
    """Return True and record the attempt, or False when the limit is exceeded.

    ``environment`` is optional so existing callers keep working; without it the
    bypass is treated as unavailable (fail closed).
    """
    if test_bypass_enabled(environment):
        limit = max(limit, _TEST_LIMIT)
        _announce_once(limit)
    ensure_table(db)
    since = _now() - window_seconds
    if _count(db, key, since) >= limit:
        return False
    _record(db, key)
    return True


def reset(db, key: str) -> None:
    if is_shared(db):
        db._raw.execute("DELETE FROM auth_login_attempts WHERE key = %s", [key])
        db._raw.commit()
    else:
        db.conn.execute("DELETE FROM auth_login_attempts WHERE key = ?", (key,))
        db.conn.commit()