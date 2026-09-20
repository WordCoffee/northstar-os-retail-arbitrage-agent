"""Phase F/S2 — auth/session schema migration tests (local SQLite).

Verifies the `role` column, the `sessions` table, owner-default role on
registration, and session-row creation on login — all against an isolated
SQLite DB. No live DB, no credentials.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import data_layer  # noqa: E402


@pytest.fixture()
def authdb(tmp_path, monkeypatch):
    monkeypatch.setattr(data_layer, "_SQLITE_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(data_layer, "_db_instance", None)
    import auth
    auth._ensure_user_table()
    yield auth
    if data_layer._db_instance is not None:
        data_layer._db_instance.close()
        data_layer._db_instance = None


def test_ensure_schema_is_idempotent(authdb):
    authdb._ensure_user_table()
    authdb._ensure_user_table()  # no error on second run
    cols = {r[1] for r in authdb._db().execute("PRAGMA table_info(users)").fetchall()}
    assert "role" in cols
    tables = {r[0] for r in authdb._db().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "sessions" in tables


def test_sessions_table_shape(authdb):
    cols = {r[1] for r in authdb._db().execute("PRAGMA table_info(sessions)").fetchall()}
    assert {"token_id", "user_id", "created_at", "expires_at", "revoked"} <= cols


def test_register_sets_owner_role(authdb):
    user = authdb.register_user("owner@x.com", "password123", plan="scout")
    assert "error" not in user
    stored = authdb.get_user(user["id"])
    assert stored["role"] == "owner"


def test_login_creates_session_row(authdb):
    authdb.register_user("sess@x.com", "password123", plan="autothink")
    login = authdb.login_user("sess@x.com", "password123")
    user = authdb.login_user("sess@x.com", "password123")
    assert "access_token" in login and "access_token" in user
    db = authdb._db()
    rows = db.execute("SELECT token_id, user_id, expires_at FROM sessions").fetchall()
    assert len(rows) == 2                       # one session row per login
    token_id, user_id, expires_at = rows[0]
    assert token_id.startswith("sess_")
    # the session's user corresponds to the registered user id
    from auth import decode_token
    payload = decode_token(login["access_token"])
    assert user_id == payload["sub"]
    assert expires_at and expires_at > "2000"


def test_login_failure_creates_no_session(authdb):
    authdb.register_user("bad@x.com", "password123")
    login = authdb.login_user("bad@x.com", "WRONGWRONG")
    assert "error" in login
    count = authdb._db().execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    assert count == 0