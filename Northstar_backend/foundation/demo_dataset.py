"""Labeled Demo Dataset (Master Plan P3-T4).

Owner-controlled toggle that loads demonstrably-labeled SAMPLE rows so every room
can be exercised before vendor keys exist. SAMPLE data lives in its own table
(``demo_observations``) and is NEVER written into real observation tables, real
aggregates, qualification, Top-5 selection, customer-tenant views, or exports.

- Hidden by default (no settings row => disabled).
- Toggling on/off never mutates canonical real data.
- Every row carries basis ``SAMPLE``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

TABLE_SETTINGS = "demo_settings"
TABLE_ROWS = "demo_observations"
BASIS = "SAMPLE"

DDL_SETTINGS_POSTGRES = (
    "CREATE TABLE IF NOT EXISTS demo_settings ("
    " organization_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,"
    " updated_at TIMESTAMPTZ NOT NULL DEFAULT now())")
DDL_SETTINGS_SQLITE = (
    "CREATE TABLE IF NOT EXISTS demo_settings ("
    " organization_id TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0,"
    " updated_at TEXT NOT NULL)")
DDL_ROWS_POSTGRES = (
    "CREATE TABLE IF NOT EXISTS demo_observations ("
    " id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, basis TEXT NOT NULL,"
    " is_sample INTEGER NOT NULL DEFAULT 1, payload TEXT NOT NULL,"
    " created_at TIMESTAMPTZ NOT NULL DEFAULT now())")
DDL_ROWS_SQLITE = (
    "CREATE TABLE IF NOT EXISTS demo_observations ("
    " id TEXT PRIMARY KEY, organization_id TEXT NOT NULL, basis TEXT NOT NULL,"
    " is_sample INTEGER NOT NULL DEFAULT 1, payload TEXT NOT NULL,"
    " created_at TEXT NOT NULL)")


def _pg(db) -> bool:
    return getattr(db, "backend", "sqlite") == "postgresql"


def ensure_tables(db) -> None:
    if _pg(db):
        db._raw.execute(DDL_SETTINGS_POSTGRES)
        db._raw.execute(DDL_ROWS_POSTGRES)
        db._raw.commit()
    else:
        db.conn.execute(DDL_SETTINGS_SQLITE)
        db.conn.execute(DDL_ROWS_SQLITE)
        db.conn.commit()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_enabled(db, org_id: str) -> bool:
    ensure_tables(db)
    if _pg(db):
        cur = db._raw.cursor()
        cur.execute("SELECT enabled FROM demo_settings WHERE organization_id = %s", [org_id])
        row = cur.fetchone()
    else:
        row = db.conn.execute("SELECT enabled FROM demo_settings WHERE organization_id = ?",
                              (org_id,)).fetchone()
    return bool(row and int(row[0] if not isinstance(row, dict) else row["enabled"]))


def _set_flag(db, org_id: str, enabled: bool) -> None:
    val = 1 if enabled else 0
    if _pg(db):
        db._raw.execute(
            "INSERT INTO demo_settings (organization_id, enabled, updated_at) "
            "VALUES (%s, %s, %s) ON CONFLICT (organization_id) "
            "DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = EXCLUDED.updated_at",
            [org_id, val, _now()])
        db._raw.commit()
    else:
        db.conn.execute(
            "INSERT INTO demo_settings (organization_id, enabled, updated_at) "
            "VALUES (?, ?, ?) ON CONFLICT(organization_id) "
            "DO UPDATE SET enabled=excluded.enabled, updated_at=excluded.updated_at",
            (org_id, val, _now()))
        db.conn.commit()


def sample_rows(db, org_id: str) -> list:
    ensure_tables(db)
    if _pg(db):
        cur = db._raw.cursor()
        cur.execute("SELECT id, basis, payload, created_at FROM demo_observations "
                    "WHERE organization_id = %s AND is_sample = 1", [org_id])
        rows = cur.fetchall()
    else:
        rows = db.conn.execute(
            "SELECT id, basis, payload, created_at FROM demo_observations "
            "WHERE organization_id = ? AND is_sample = 1", (org_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:  # noqa: BLE001
            pass
        out.append(d)
    return out


def sample_count(db, org_id: str) -> int:
    return len(sample_rows(db, org_id))


def _seed(db, org_id: str) -> None:
    if sample_rows(db, org_id):
        return
    items = [
        {"asin": "SAMPLE-B000000001", "title": "Sample Product One", "net_per_unit": 7.50},
        {"asin": "SAMPLE-B000000002", "title": "Sample Product Two", "net_per_unit": 3.10},
        {"asin": "SAMPLE-B000000003", "title": "Sample Product Three", "net_per_unit": 12.00},
    ]
    for it in items:
        rid = str(uuid4())
        payload = json.dumps(it)
        if _pg(db):
            db._raw.execute(
                "INSERT INTO demo_observations (id, organization_id, basis, is_sample, payload, created_at) "
                "VALUES (%s, %s, %s, 1, %s, %s)", [rid, org_id, BASIS, payload, _now()])
        else:
            db.conn.execute(
                "INSERT INTO demo_observations (id, organization_id, basis, is_sample, payload, created_at) "
                "VALUES (?, ?, ?, 1, ?, ?)", (rid, org_id, BASIS, payload, _now()))
    if _pg(db):
        db._raw.commit()
    else:
        db.conn.commit()


def _clear(db, org_id: str) -> int:
    if _pg(db):
        cur = db._raw.execute("DELETE FROM demo_observations WHERE organization_id = %s "
                              "AND is_sample = 1", [org_id])
        db._raw.commit()
        return cur.rowcount
    cur = db.conn.execute("DELETE FROM demo_observations WHERE organization_id = ? "
                          "AND is_sample = 1", (org_id,))
    db.conn.commit()
    return cur.rowcount


def set_enabled(db, org_id: str, enabled: bool, *, actor_user_id: Optional[str] = None,
                audit=None) -> dict:
    ensure_tables(db)
    _set_flag(db, org_id, enabled)
    if enabled:
        _seed(db, org_id)
    else:
        _clear(db, org_id)
    if audit is not None:
        try:
            audit.record(action="demo_dataset.enabled" if enabled else "demo_dataset.disabled",
                         actor_user_id=actor_user_id, organization_id=org_id,
                         resource_type="demo_dataset", resource_id=org_id,
                         after_meta={"is_sample": True, "enabled": bool(enabled)})
        except Exception:  # noqa: BLE001
            pass
    return {"organization_id": org_id, "enabled": bool(enabled),
            "sample_count": sample_count(db, org_id)}


def status(db, org_id: str) -> dict:
    return {"organization_id": org_id, "enabled": is_enabled(db, org_id),
            "sample_count": sample_count(db, org_id)}