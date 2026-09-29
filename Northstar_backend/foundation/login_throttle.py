"""Shared, database-backed login throttle (P2-T5/P2-T6 hardening).

The previous limiter was per-process. For a multi-process hosted deployment
(api + future replicas) the limit must be shared. This module stores attempts in
the same database the app already uses (PostgreSQL in hosted mode, SQLite in
local/test), so the limit is correct across processes.

Hosted posture: if the environment is production-like and the backing store is
not shared-capable (i.e. not PostgreSQL), callers must fail closed — see
``require_shared``.
"""
from __future__ import annotations

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


class ThrottleUnavailable(RuntimeError):
    """Raised when a shared throttle store is required but unavailable."""


def is_shared(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


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


def allow(db, key: str, *, limit: int = 5, window_seconds: int = 300) -> bool:
    """Return True and record the attempt, or False when the limit is exceeded."""
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