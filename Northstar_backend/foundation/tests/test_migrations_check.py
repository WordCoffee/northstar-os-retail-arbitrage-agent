"""Offline tests for the P2-T4 startup migration posture (no database)."""
from __future__ import annotations

from pathlib import Path

import pytest

from Northstar_backend.foundation import migrations_check as mc
from Northstar_backend.foundation.migrate import MigrationRefused
from Northstar_backend.foundation.migrations_check import (
    forward_migration_files, compare_applied, _HOSTED_ENVIRONMENTS,
)

MIGRATIONS_DIR = str(Path(__file__).resolve().parents[2] / "migrations_foundation")


def test_forward_migration_files_excludes_rollbacks_and_is_sorted():
    files = forward_migration_files(MIGRATIONS_DIR)
    names = [n for n, _ in files]
    assert names, "expected forward migrations on disk"
    assert all("rollback" not in n.lower() for n in names)
    assert names == sorted(names)
    assert all(len(c) == 64 for _, c in files)  # sha256 hex


def test_compare_applied_reports_missing_and_drifted():
    expected = [("001_foundation.sql", "aaa"), ("002_jobs_durable.sql", "bbb")]
    status = compare_applied(expected, {"001_foundation.sql": "aaa"})
    assert status["current"] is False
    assert status["missing"] == ["002_jobs_durable.sql"]
    assert status["drifted"] == []
    assert status["expected_count"] == 2
    assert status["applied_count"] == 1


def test_compare_applied_detects_drift():
    expected = [("001_foundation.sql", "aaa")]
    status = compare_applied(expected, {"001_foundation.sql": "zzz"})
    assert status["current"] is False
    assert status["drifted"] == ["001_foundation.sql"]
    assert status["missing"] == []


def test_compare_applied_current_when_all_match():
    expected = [("001_foundation.sql", "aaa"), ("002_jobs_durable.sql", "bbb")]
    status = compare_applied(expected, {"001_foundation.sql": "aaa", "002_jobs_durable.sql": "bbb"})
    assert status["current"] is True


def test_hosted_environments_set():
    assert "production" in _HOSTED_ENVIRONMENTS
    assert "staging" in _HOSTED_ENVIRONMENTS
    assert "development" not in _HOSTED_ENVIRONMENTS


def test_assert_fails_closed_in_hosted_when_behind(monkeypatch):
    monkeypatch.setattr(mc, "forward_migration_files",
                        lambda d: [("001_foundation.sql", "aaa")])
    monkeypatch.setattr(mc, "_read_applied", lambda db: {})
    with pytest.raises(MigrationRefused):
        mc.assert_migrations_current(object(), environment="production",
                                     migrations_dir="ignored")


def test_assert_does_not_block_in_development(monkeypatch):
    monkeypatch.setattr(mc, "forward_migration_files",
                        lambda d: [("001_foundation.sql", "aaa")])
    monkeypatch.setattr(mc, "_read_applied", lambda db: {})
    status = mc.assert_migrations_current(object(), environment="development",
                                          migrations_dir="ignored")
    assert status["current"] is False
    assert status["required"] is False