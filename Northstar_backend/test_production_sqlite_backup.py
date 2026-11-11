"""The SQLite backup/restore path is real: snapshot, verify, restore, refuse.

Every test builds its own store in a temp directory and drives the public
functions in ``Northstar_backend/sqlite_backup.py``. No live store is written:
the module opens sources read-only, and one test asserts exactly that.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite_backup as sb


def _make_store(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT);
            CREATE TABLE runs (id INTEGER PRIMARY KEY, note TEXT);
            INSERT INTO users VALUES ('u1', 'ROWTOKEN-ada'), ('u2', 'grace');
            INSERT INTO runs (note) VALUES ('ROWTOKEN-one'), ('two'), ('three');
            PRAGMA user_version = 7;
            """
        )
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _make_store(root / "Northstar_backend" / "data" / "foundation.db")
    return root


@pytest.fixture
def manifest(temp_root: Path, tmp_path: Path) -> dict:
    return sb.backup_store("foundation", tmp_path / "backups", root=temp_root)


def _row_dump(path: Path) -> dict:
    conn = sqlite3.connect(path)
    try:
        return {
            table: conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid').fetchall()
            for table in ("users", "runs")
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def test_backup_writes_a_manifest_with_hash_counts_and_version(manifest, tmp_path):
    data = Path(manifest["manifest_path"]).parent / manifest["file"]
    assert data.is_file()
    assert manifest["schema"] == sb.SCHEMA
    assert manifest["store"] == "foundation"
    assert len(manifest["sha256"]) == 64
    assert manifest["bytes"] == data.stat().st_size
    assert manifest["tables"] == {"runs": 3, "users": 2}
    assert manifest["row_total"] == 5
    assert manifest["user_version"] == 7
    assert manifest["integrity_ok"] is True
    assert manifest["extensions"] == [] or "sqlite_vec" in manifest["extensions"]

    on_disk = json.loads(Path(manifest["manifest_path"]).read_text(encoding="utf-8"))
    assert on_disk["sha256"] == manifest["sha256"]
    # A manifest names paths and counts only: no row content is copied into it.
    assert "ROWTOKEN" not in json.dumps(on_disk)


def test_backup_never_writes_to_the_live_store(temp_root, tmp_path):
    source = temp_root / "Northstar_backend" / "data" / "foundation.db"
    before = source.read_bytes()
    before_stat = source.stat()
    sb.backup_store("foundation", tmp_path / "backups", root=temp_root)
    assert source.read_bytes() == before
    after_stat = source.stat()
    assert after_stat.st_size == before_stat.st_size
    assert after_stat.st_mtime == before_stat.st_mtime


def test_backup_refuses_a_missing_store(temp_root, tmp_path):
    with pytest.raises(sb.BackupError, match="not present"):
        sb.backup_store("northstar", tmp_path / "backups", root=temp_root)


def test_backup_all_skips_absent_stores(tmp_path):
    results = sb.backup_all(tmp_path / "backups", root=tmp_path / "empty")
    assert results
    assert {row["status"] for row in results} == {"skipped"}


def test_inventory_reports_presence(temp_root):
    rows = {row["id"]: row for row in sb.describe_stores(root=temp_root)}
    assert rows["foundation"]["exists"] is True
    assert rows["foundation"]["bytes"] > 0
    assert rows["northstar"]["exists"] is False


# ---------------------------------------------------------------------------
# Verify refuses a damaged backup
# ---------------------------------------------------------------------------

def test_verify_accepts_an_intact_backup(manifest):
    result = sb.verify_backup(Path(manifest["manifest_path"]))
    assert result["verified"] is True
    assert result["store"] == "foundation"
    assert result["row_total"] == 5


def test_verify_accepts_the_data_file_path(manifest):
    data = Path(manifest["manifest_path"]).parent / manifest["file"]
    assert sb.verify_backup(data)["verified"] is True


def test_verify_rejects_a_modified_byte(manifest):
    data = Path(manifest["manifest_path"]).parent / manifest["file"]
    raw = bytearray(data.read_bytes())
    raw[len(raw) // 2] ^= 0xFF
    data.write_bytes(bytes(raw))
    with pytest.raises(sb.BackupError, match="sha256 mismatch"):
        sb.verify_backup(Path(manifest["manifest_path"]))


def test_verify_rejects_count_drift(manifest):
    manifest_path = Path(manifest["manifest_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["tables"]["runs"] = 4
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(sb.BackupError, match="row counts"):
        sb.verify_backup(manifest_path)


def test_verify_rejects_an_unknown_manifest_schema(manifest):
    manifest_path = Path(manifest["manifest_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["schema"] = "northstar.sqlite_backup.v0"
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(sb.BackupError, match="schema"):
        sb.verify_backup(manifest_path)


def test_verify_rejects_a_missing_backup_file(manifest):
    data = Path(manifest["manifest_path"]).parent / manifest["file"]
    data.unlink()
    with pytest.raises(sb.BackupError, match="backup file missing"):
        sb.verify_backup(Path(manifest["manifest_path"]))


# ---------------------------------------------------------------------------
# Restore round-trips, and refuses to clobber
# ---------------------------------------------------------------------------

def test_restore_round_trips_every_row(manifest, temp_root, tmp_path):
    source = temp_root / "Northstar_backend" / "data" / "foundation.db"
    target = tmp_path / "restored.db"
    result = sb.restore_backup(Path(manifest["manifest_path"]), target)

    assert result["integrity_ok"] is True
    assert result["row_total"] == 5
    assert result["restored_to"] == str(target)
    assert _row_dump(target) == _row_dump(source)


def test_restore_refuses_an_existing_target_without_force(manifest, tmp_path):
    target = tmp_path / "restored.db"
    target.write_bytes(b"do not clobber me")
    with pytest.raises(sb.BackupError, match="target exists"):
        sb.restore_backup(Path(manifest["manifest_path"]), target)
    assert target.read_bytes() == b"do not clobber me"


def test_restore_replaces_an_existing_target_with_force(manifest, tmp_path):
    target = tmp_path / "restored.db"
    target.write_bytes(b"stale bytes")
    result = sb.restore_backup(Path(manifest["manifest_path"]), target, force=True)
    assert result["row_total"] == 5
    conn = sqlite3.connect(target)
    try:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
    finally:
        conn.close()


def test_restore_writes_a_receipt(manifest, tmp_path):
    receipt = tmp_path / "receipts" / "restore.json"
    sb.restore_backup(Path(manifest["manifest_path"]), tmp_path / "restored.db",
                      receipt=receipt)
    payload = json.loads(receipt.read_text(encoding="utf-8"))
    assert payload["integrity_ok"] is True
    assert payload["store"] == "foundation"
    assert payload["row_total"] == 5


def test_restore_refuses_a_backup_that_no_longer_verifies(manifest, tmp_path):
    data = Path(manifest["manifest_path"]).parent / manifest["file"]
    raw = bytearray(data.read_bytes())
    raw[100] ^= 0xFF
    data.write_bytes(bytes(raw))
    target = tmp_path / "restored.db"
    with pytest.raises(sb.BackupError):
        sb.restore_backup(Path(manifest["manifest_path"]), target)
    assert not target.exists()


def test_cli_backup_verify_restore(temp_root, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(temp_root)
    dest = tmp_path / "cli-backups"
    # The CLI resolves the store relative to the module's repo root, so point it
    # at the temp layout explicitly instead of relying on CWD.
    env = {"NORTHSTAR_BACKUP_ROOT": str(temp_root)}
    monkeypatch.setattr(sb, "REPO_ROOT", Path(env["NORTHSTAR_BACKUP_ROOT"]))

    assert sb.main(["--json", "backup", "--dest", str(dest), "--store", "foundation"]) == 0
    payload = json.loads(capsys.readouterr().out)
    manifest_path = payload[0]["manifest_path"]

    assert sb.main(["--json", "verify", "--manifest", manifest_path]) == 0
    capsys.readouterr()

    assert sb.main(["--json", "restore", "--manifest", manifest_path,
                    "--target", str(tmp_path / "cli-restored.db")]) == 0
    assert (tmp_path / "cli-restored.db").is_file()


def test_cli_reports_a_refusal_as_exit_1(temp_root, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sb, "REPO_ROOT", temp_root)
    code = sb.main(["verify", "--manifest", str(tmp_path / "no-such-manifest.json")])
    assert code == 1
    assert "REFUSED" in capsys.readouterr().err
