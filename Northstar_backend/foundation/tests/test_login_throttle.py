"""P2-T6 shared login throttle tests (SQLite local; store-agnostic)."""
from __future__ import annotations

import time

import pytest

from Northstar_backend.foundation import login_throttle
from Northstar_backend.foundation.db import FoundationDB


@pytest.fixture()
def db(tmp_path):
    d = FoundationDB(str(tmp_path / "throttle.db"))
    yield d
    d.close()


def test_allow_then_block(db):
    key = "owner@test.test|127.0.0.1"
    for _ in range(5):
        assert login_throttle.allow(db, key, limit=5, window_seconds=300) is True
    assert login_throttle.allow(db, key, limit=5, window_seconds=300) is False


def test_reset_clears(db):
    key = "k"
    for _ in range(5):
        login_throttle.allow(db, key, limit=5, window_seconds=300)
    assert login_throttle.allow(db, key, limit=5, window_seconds=300) is False
    login_throttle.reset(db, key)
    assert login_throttle.allow(db, key, limit=5, window_seconds=300) is True


def test_window_expiry_ignores_old_attempts(db):
    login_throttle.ensure_table(db)
    key = "old"
    old_ts = int(time.time()) - 10_000
    db.conn.execute("INSERT INTO auth_login_attempts (key, attempted_at) VALUES (?, ?)",
                    (key, old_ts))
    db.conn.commit()
    assert login_throttle.allow(db, key, limit=1, window_seconds=300) is True


class _FakeDB:
    def __init__(self, backend):
        self.backend = backend


def test_require_shared_fails_closed_for_hosted_sqlite():
    with pytest.raises(login_throttle.ThrottleUnavailable):
        login_throttle.require_shared(_FakeDB("sqlite"), "production")
    with pytest.raises(login_throttle.ThrottleUnavailable):
        login_throttle.require_shared(_FakeDB("sqlite"), "staging")
    # Development may use the local SQLite store.
    login_throttle.require_shared(_FakeDB("sqlite"), "development")
    # Hosted with PostgreSQL is fine.
    login_throttle.require_shared(_FakeDB("postgresql"), "production")


def test_is_shared_reports_backend():
    assert login_throttle.is_shared(_FakeDB("postgresql")) is True
    assert login_throttle.is_shared(_FakeDB("sqlite")) is False