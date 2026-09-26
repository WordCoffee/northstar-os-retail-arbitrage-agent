"""Migration control & staging guardrail tests (Phase 1C-02 offline parts)."""
from __future__ import annotations

import os

import pytest

from Northstar_backend.foundation.migrate import (
    MigrationRefused, assert_staging_identity, sql_checksum, detect_sql_drift,
    generate_rollback_sql, migration_ledger_entry, preflight, FOUNDATION_TABLES, MIGRATION_ID,
)

_MIG = os.path.join("Northstar_backend", "migrations_foundation", "001_foundation.sql")


def test_staging_identity_requires_staging_env(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_ALLOW_STAGING_MIGRATION", "1")
    with pytest.raises(MigrationRefused) as e:
        assert_staging_identity(environment="production", host="db.staging.example",
                                database="northstar_staging")
    assert "environment_not_staging" in str(e.value)


def test_staging_identity_requires_explicit_flag(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_ALLOW_STAGING_MIGRATION", raising=False)
    with pytest.raises(MigrationRefused) as e:
        assert_staging_identity(environment="staging", host="db.staging.example",
                                database="northstar_staging", allow_flag=False)
    assert "missing_NORTHSTAR_ALLOW_STAGING_MIGRATION" in str(e.value)


def test_staging_identity_denylist_blocks_production_names():
    with pytest.raises(MigrationRefused) as e:
        assert_staging_identity(environment="staging", host="db.prod.example",
                                database="northstar_production", allow_flag=True)
    assert "denylisted_identifier" in str(e.value)


def test_staging_identity_ok_and_redacted():
    res = assert_staging_identity(environment="staging", host="db.staging.example",
                                  database="northstar_staging", allow_flag=True)
    assert res["migration_id"] == MIGRATION_ID
    assert "*" in res["host"] and res["host"] != "db.staging.example"
    assert "*" in res["database"]


def test_checksum_is_stable():
    if not os.path.exists(_MIG):
        pytest.skip("migration file absent")
    a = sql_checksum(_MIG)
    b = sql_checksum(_MIG)
    assert a == b and len(a) == 64


def test_migration_in_sync_with_schema():
    if not os.path.exists(_MIG):
        pytest.skip("migration file absent")
    d = detect_sql_drift(_MIG)
    assert d["exists"] is True
    assert d["in_sync"] is True


def test_rollback_sql_drops_only_foundation_tables():
    sql = generate_rollback_sql()
    assert sql.startswith("--")
    assert "BEGIN;" in sql and "COMMIT;" in sql
    for t in FOUNDATION_TABLES:
        assert f'DROP TABLE IF EXISTS "{t}";' in sql
    # never drops legacy tables (keywords is now a FOUNDATION table)
    for legacy in ("products", "users_legacy", "transactions", "campaigns_legacy",
                   "ad_groups_legacy", "legacy_keywords"):
        assert f'"{legacy}"' not in sql


def test_ledger_entry_shape():
    e = migration_ledger_entry(checksum="abc", environment="staging", success=False)
    assert e["migration_id"] == MIGRATION_ID
    assert e["applied_at"] is None
    assert e["success"] is False
    assert e["tables"] == len(FOUNDATION_TABLES)


def test_preflight_does_not_apply():
    if not os.path.exists(_MIG):
        pytest.skip("migration file absent")
    p = preflight(_MIG, environment="staging", host="db.staging.example",
                  database="ns_staging", allow_flag=True)
    assert p["applied"] is False
    assert "no database connection opened" in p["note"]
    assert p["table_count"] == len(FOUNDATION_TABLES)