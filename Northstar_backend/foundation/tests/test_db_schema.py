"""Schema equivalence tests (amendment 3): SQLite and PostgreSQL DDL are
generated from one SCHEMA spec, so backend divergence is a construction error."""
from __future__ import annotations

import sqlite3

from Northstar_backend.foundation.db import (
    SCHEMA, SQLITE_DDL, postgres_ddl, validate_sqlite_schema,
    schema_equivalence_report,
)


def test_sqlite_ddl_matches_schema_spec():
    report = validate_sqlite_schema()
    assert report["all_match"] is True
    assert report["tables"] == len(SCHEMA)


def test_postgres_ddl_contains_every_table_and_column():
    pg = postgres_ddl()
    for table, cols in SCHEMA.items():
        assert f'"{table}"' in pg, f"missing table {table}"
        for name, _lt in cols:
            assert f'"{name}"' in pg, f"missing column {table}.{name}"


def test_schema_equivalence_report_equivalent():
    rep = schema_equivalence_report()
    assert rep["equivalent"] is True
    assert rep["sqlite_validated"] is True
    assert rep["postgres_missing_items"] == []


def test_postgres_uses_correct_logical_types():
    pg = postgres_ddl()
    # json -> JSONB, bool -> BOOLEAN, ts -> TIMESTAMPTZ, real -> DOUBLE PRECISION
    assert "JSONB" in pg
    assert "BOOLEAN" in pg
    assert "TIMESTAMPTZ" in pg
    assert "DOUBLE PRECISION" in pg


def test_primary_keys_present_in_both():
    pg = postgres_ddl()
    con = sqlite3.connect(":memory:")
    try:
        for stmt in SQLITE_DDL:
            con.execute(stmt)
        for table in SCHEMA:
            info = con.execute(f"PRAGMA table_info({table})").fetchall()
            sqlite_pk = [r[1] for r in info if r[5] > 0]
            assert sqlite_pk, f"no PK on {table}"
        assert pg.count("PRIMARY KEY") == len(SCHEMA)
    finally:
        con.close()


def test_ui_preferences_composite_pk():
    con = sqlite3.connect(":memory:")
    try:
        for stmt in SQLITE_DDL:
            con.execute(stmt)
        info = con.execute("PRAGMA table_info(ui_preferences)").fetchall()
        pk = sorted(r[1] for r in info if r[5] > 0)
        assert pk == ["key", "organization_id", "user_id"]
    finally:
        con.close()