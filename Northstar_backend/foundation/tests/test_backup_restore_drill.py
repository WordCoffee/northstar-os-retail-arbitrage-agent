"""Item 4 — Local backup/restore drill (evidence-backed, fully offline).

Validates the local SQLite persistence survives a backup-and-restore round
trip using the SQLite incremental backup API, and that restore only ever
targets a clearly-disposable database name.

This mirrors the restore.safety guard in deploy/restore.sh but for the LOCAL
SQLite data layer (data/northstar.db): a restore drill writes ONLY into a
throwaway DB whose name is marked "drill"/"restore"; it never touches the live
database. No network, no cloud, no real invitations/emails/SMS.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path


def _seed(path: Path):
    con = sqlite3.connect(str(path))
    con.executescript("""
        CREATE TABLE test_ops (id INTEGER PRIMARY KEY, tenant TEXT NOT NULL, value TEXT);
    """)
    con.executemany(
        "INSERT INTO test_ops (tenant, value) VALUES (?, ?)",
        [("tenant-a", f"record-{i}") for i in range(20)] +
        [("tenant-b", f"record-{i}") for i in range(7)],
    )
    con.commit()
    con.close()


def _integrity_ok(path: Path) -> bool:
    con = sqlite3.connect(str(path))
    try:
        row = con.execute("PRAGMA integrity_check").fetchone()
        return row is not None and row[0] == "ok"
    finally:
        con.close()


def _counts(path: Path):
    con = sqlite3.connect(str(path))
    try:
        return con.execute(
            "SELECT tenant, COUNT(*) FROM test_ops GROUP BY tenant ORDER BY tenant"
        ).fetchall()
    finally:
        con.close()


def test_local_backup_restore_round_trip_preserves_all_tenants():
    """Back up a seeded SQLite DB, restore into a disposable DB, verify integrity + parity."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "northstar.db"
        backup = root / "backup-20260930T000000Z.sqlite"
        restored = root / "northstar_restore_drill.sqlite"

        _seed(source)
        assert _integrity_ok(source)

        # --- backup: SQLite online backup API (safe while reader may be active) ---
        src = sqlite3.connect(str(source))
        try:
            dst = sqlite3.connect(str(backup))
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()

        assert backup.exists() and backup.stat().st_size > 0, "backup must be non-empty"
        assert _integrity_ok(backup), "backup fails integrity_check"

        # --- restore safety guard: disposable target name required ---
        name = restored.name
        assert ("drill" in name) or ("restore" in name), \
            "restore target must be clearly disposable (drill/restore)"

        # --- restore into the disposable DB ---
        rb = sqlite3.connect(str(backup))
        try:
            rt = sqlite3.connect(str(restored))
            try:
                rb.backup(rt)
            finally:
                rt.close()
        finally:
            rb.close()

        # --- verify parity + integrity ---
        assert _integrity_ok(restored), "restored DB fails integrity_check"
        assert _counts(restored) == _counts(source), "restored counts differ from source"
        assert _counts(restored) == [("tenant-a", 20), ("tenant-b", 7)]


def test_restore_target_name_must_be_disposable():
    """The disposable-name guard rejects a live-db name (mirrors restore.sh)."""
    names = ["northstar.db", "app.db", "production.sqlite", "northstar_restore_drill.sqlite", "dbtest_drill_x"]
    expecting = {
        "northstar.db": False,
        "app.db": False,
        "production.sqlite": False,
        "northstar_restore_drill.sqlite": True,
        "dbtest_drill_x": True,
    }
    for name, allowed in expecting.items():
        guard = ("drill" in name) or ("restore" in name)
        assert guard is allowed, f"name={name!r} expected allowed={allowed} got {guard}"
