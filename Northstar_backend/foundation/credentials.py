"""Owner password credentials for the Foundation app (P2-T5a).

Additive, forward-only store. The credentials live in a dedicated
``owner_credentials`` table (NOT the ``users`` table) so the existing schema and
its drift/equivalence checks are untouched. The table is created by the forward
migration ``migrations_foundation/008_owner_credentials.sql`` on PostgreSQL and
by ``ensure_table`` at runtime on both PostgreSQL and SQLite.

Security posture:
- Passwords are hashed with bcrypt (the same library/algorithm already used by
  ``Northstar_backend/auth.py``); plaintext is never stored or logged.
- This module never prints values; callers must not echo passwords or hashes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import bcrypt

TABLE = "owner_credentials"

DDL_POSTGRES = (
    "CREATE TABLE IF NOT EXISTS owner_credentials ("
    " user_id TEXT PRIMARY KEY,"
    " email TEXT NOT NULL UNIQUE,"
    " password_hash TEXT NOT NULL,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
DDL_SQLITE = (
    "CREATE TABLE IF NOT EXISTS owner_credentials ("
    " user_id TEXT PRIMARY KEY,"
    " email TEXT NOT NULL UNIQUE,"
    " password_hash TEXT NOT NULL,"
    " created_at TEXT NOT NULL)")


def _is_postgres(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


def ensure_table(db) -> None:
    """Create the credentials table if absent (idempotent, both backends)."""
    if _is_postgres(db):
        db._raw.execute(DDL_POSTGRES)
        db._raw.commit()
    else:
        db.conn.execute(DDL_SQLITE)
        db.conn.commit()


def hash_password(password: str) -> str:
    """Bcrypt hash. Matches ``Northstar_backend/auth.py`` (bcrypt.gensalt())."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _row_to_dict(row) -> Optional[dict]:
    if row is None:
        return None
    try:
        return dict(row)
    except Exception:  # noqa: BLE001
        return None


def get_by_email(db, email: str) -> Optional[dict]:
    ensure_table(db)
    email = (email or "").strip().lower()
    if _is_postgres(db):
        cur = db._raw.cursor()
        cur.execute("SELECT user_id, email, password_hash, created_at "
                    "FROM owner_credentials WHERE lower(email) = %s", [email])
        return _row_to_dict(cur.fetchone())
    cur = db.conn.execute(
        "SELECT user_id, email, password_hash, created_at "
        "FROM owner_credentials WHERE lower(email) = ?", (email,))
    return _row_to_dict(cur.fetchone())


def count(db) -> int:
    ensure_table(db)
    if _is_postgres(db):
        cur = db._raw.cursor()
        cur.execute("SELECT COUNT(*) AS n FROM owner_credentials")
        return int(cur.fetchone()["n"])
    cur = db.conn.execute("SELECT COUNT(*) AS n FROM owner_credentials")
    return int(cur.fetchone()[0])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create(db, *, user_id: str, email: str, password: str) -> None:
    """Insert a new credential. Assumes the email is not already present."""
    ensure_table(db)
    hashed = hash_password(password)
    email = email.strip().lower()
    if _is_postgres(db):
        db._raw.execute(
            "INSERT INTO owner_credentials (user_id, email, password_hash, created_at) "
            "VALUES (%s, %s, %s, %s)", [user_id, email, hashed, _now_iso()])
        db._raw.commit()
    else:
        db.conn.execute(
            "INSERT INTO owner_credentials (user_id, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)", (user_id, email, hashed, _now_iso()))
        db.conn.commit()


def rotate(db, *, email: str, password: str) -> None:
    """Explicitly replace the password hash for an existing credential."""
    ensure_table(db)
    hashed = hash_password(password)
    email = email.strip().lower()
    if _is_postgres(db):
        db._raw.execute("UPDATE owner_credentials SET password_hash = %s "
                        "WHERE lower(email) = %s", [hashed, email])
        db._raw.commit()
    else:
        db.conn.execute("UPDATE owner_credentials SET password_hash = ? "
                        "WHERE lower(email) = ?", (hashed, email))
        db.conn.commit()