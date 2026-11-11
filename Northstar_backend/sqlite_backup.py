"""Backup / verify / restore for the app's SQLite stores.

The Foundation schema can run on PostgreSQL (hosted) or SQLite (local, tests,
single-service installs). ``deploy/backup.sh`` + ``deploy/restore.sh`` cover the
Postgres path; this module is the equivalent for the SQLite lane, and it is the
one ``production_assert.py`` exercises on every run.

Contract:

- **Backup is consistent, not a file copy.** ``VACUUM INTO`` writes a
  transactionally consistent snapshot, so a writer that is mid-transaction
  cannot produce a torn file. The source is opened read-only, so taking a
  backup never changes the live store (not even its mtime).
- **Every backup carries a manifest** next to it: SHA-256, byte size, SQLite
  version, ``PRAGMA user_version``, table list and per-table row counts. A
  backup with no manifest is not a restorable backup.
- **Verify before restore.** The manifest's hash, size, ``integrity_check`` and
  row counts must all match the file. A backup that fails any of them is
  refused, never "restored anyway".
- **Restore is refuse-by-default.** It will not overwrite an existing target
  unless ``force=True`` / ``--force`` is given, and it restores into a temp
  file, re-checks integrity and counts, and only then replaces the target.
- **Names only, never values.** Manifests record paths and counts. No table
  content is copied into a manifest, so a manifest is safe to attach to a
  report.

Usage (repo root, Windows or POSIX)::

    python Northstar_backend/sqlite_backup.py inventory
    python Northstar_backend/sqlite_backup.py backup --dest backups/sqlite
    python Northstar_backend/sqlite_backup.py verify --manifest backups/sqlite/foundation_<ts>.json
    python Northstar_backend/sqlite_backup.py restore --manifest <manifest> --target <path>

Exit codes: 0 = ok, 1 = refused/failed, 2 = usage error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SCHEMA = "northstar.sqlite_backup.v1"
BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent

# The SQLite stores the app writes. Paths are repo-relative so a manifest is
# portable; ``env`` names the override each module already honours, so a
# relocated store is still found (and still backed up) rather than silently
# skipped.
STORE_INVENTORY: Tuple[Dict[str, Any], ...] = (
    {
        "id": "foundation",
        "path": "Northstar_backend/data/foundation.db",
        "env": "FOUNDATION_DB_PATH",
        "purpose": "orgs, users, memberships, sessions, audit (SQLite lane)",
        "critical": True,
    },
    {
        "id": "northstar",
        "path": "Northstar_backend/data/northstar.db",
        "env": "NORTHSTAR_DB_PATH",
        "purpose": "legacy app store (products, deals, runs)",
        "critical": True,
    },
    {
        "id": "references",
        "path": "Northstar_backend/data/references.db",
        "env": None,
        "purpose": "reference library rows used by design + listings",
        "critical": False,
    },
    {
        "id": "tys_assistant",
        "path": "Northstar_backend/data/tys_assistant.db",
        "env": "TYS_DB_PATH",
        "purpose": "Tys Assistant work orders, cursor state, evidence",
        "critical": True,
    },
    {
        "id": "tys_memory",
        "path": "Northstar_backend/data/tys_memory.db",
        "env": "TYS_MEMORY_DB",
        "purpose": "Tys memory bank (facts, revisions, embeddings index)",
        "critical": True,
    },
    {
        "id": "local_screen",
        "path": "Northstar_backend/data/local_screen/memory.db",
        "env": "LOCAL_SCREEN_DB",
        "purpose": "local screen companion capture memory (FTS index)",
        "critical": False,
    },
)


class BackupError(RuntimeError):
    """Raised when a backup, verify or restore step refuses to continue."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _connect_ro(path: Path) -> sqlite3.Connection:
    uri = "file:" + path.resolve().as_posix() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=10)


def store_path(store: Dict[str, Any], root: Optional[Path] = None,
               environ: Optional[Dict[str, str]] = None) -> Path:
    """Resolve a store's live path, honouring the module's own env override."""
    root = REPO_ROOT if root is None else root
    env = environ if environ is not None else os.environ
    override = env.get(store["env"]) if store.get("env") else None
    if override and str(override).strip():
        return Path(str(override).strip())
    return root / store["path"]


def find_store(store_id: str) -> Dict[str, Any]:
    for store in STORE_INVENTORY:
        if store["id"] == store_id:
            return store
    raise BackupError(f"unknown store: {store_id!r}")


def describe_stores(root: Optional[Path] = None,
                    environ: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Inventory with live presence for each store (no content is read)."""
    root = REPO_ROOT if root is None else root
    rows: List[Dict[str, Any]] = []
    for store in STORE_INVENTORY:
        path = store_path(store, root=root, environ=environ)
        rows.append({
            "id": store["id"],
            "purpose": store["purpose"],
            "critical": store["critical"],
            "path": str(path),
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else 0,
        })
    return rows


# ---------------------------------------------------------------------------
# Inspect a database file
# ---------------------------------------------------------------------------

def _load_optional_extensions(conn: sqlite3.Connection) -> List[str]:
    """Load sqlite-vec when installed, so its virtual tables can be counted.

    ``tys_memory.db`` carries a ``chunk_vec`` vec0 table. Without the extension
    SQLite reports "no such module: vec0" for that table only; the rest of the
    file is readable. Loading the extension when it is available keeps row
    counts exact, and when it is missing the table is recorded as unreadable
    rather than silently counted as zero.
    """
    loaded: List[str] = []
    try:
        import sqlite_vec  # type: ignore[import-not-found]
    except Exception:
        return loaded
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        loaded.append("sqlite_vec")
    except Exception:
        loaded = []
    finally:
        try:
            conn.enable_load_extension(False)
        except Exception:
            pass
    return loaded


def inspect_database(path: Path) -> Dict[str, Any]:
    """Integrity, schema version and per-table row counts for one SQLite file."""
    if not path.is_file():
        raise BackupError(f"not a file: {path}")
    conn = _connect_ro(path)
    try:
        extensions = _load_optional_extensions(conn)
        integrity = [row[0] for row in conn.execute("PRAGMA integrity_check").fetchall()]
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        tables = [
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        counts: Dict[str, int] = {}
        unreadable: Dict[str, str] = {}
        for table in tables:
            quoted = table.replace('"', '""')
            try:
                counts[table] = int(
                    conn.execute(f'SELECT COUNT(*) FROM "{quoted}"').fetchone()[0]
                )
            except sqlite3.Error as exc:
                unreadable[table] = str(exc)
    finally:
        conn.close()
    return {
        "integrity_ok": integrity == ["ok"],
        "integrity": integrity[:5],
        "user_version": user_version,
        "extensions": extensions,
        "tables": counts,
        "unreadable_tables": unreadable,
        "row_total": sum(counts.values()),
    }


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_store(store_id: str, dest_dir: Path, *, root: Optional[Path] = None,
                 environ: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Write a consistent snapshot plus its manifest; return the manifest."""
    root = REPO_ROOT if root is None else root
    store = find_store(store_id)
    source = store_path(store, root=root, environ=environ)
    if not source.is_file():
        raise BackupError(f"store {store_id!r} not present: {source}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()
    target = dest_dir / f"{store_id}_{stamp}.db"
    manifest_path = dest_dir / f"{store_id}_{stamp}.json"
    if target.exists() or manifest_path.exists():
        raise BackupError(f"refusing to overwrite an existing backup: {target}")

    staged = dest_dir / f".{store_id}_{stamp}.partial"
    if staged.exists():
        staged.unlink()

    # VACUUM INTO reads a consistent snapshot and requires the destination to
    # not exist. The source is opened READ-ONLY: a backup must never write to
    # the live store (not even a journal header or an mtime).
    source_conn = _connect_ro(source)
    try:
        source_conn.execute("VACUUM INTO ?", (str(staged),))
    except sqlite3.Error as exc:
        raise BackupError(f"VACUUM INTO failed for {store_id}: {exc}") from exc
    finally:
        source_conn.close()

    try:
        info = inspect_database(staged)
        if not info["integrity_ok"]:
            raise BackupError(
                f"snapshot for {store_id} failed integrity_check: {info['integrity']}"
            )
        staged.replace(target)
    except Exception:
        if staged.exists():
            staged.unlink()
        raise

    manifest = {
        "schema": SCHEMA,
        "store": store_id,
        "source_path": str(source),
        "source_relative": store["path"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "file": target.name,
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
        "sqlite_version": sqlite3.sqlite_version,
        "integrity_ok": info["integrity_ok"],
        "user_version": info["user_version"],
        "extensions": info["extensions"],
        "tables": info["tables"],
        "unreadable_tables": info["unreadable_tables"],
        "row_total": info["row_total"],
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def backup_all(dest_dir: Path, *, root: Optional[Path] = None,
               environ: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Back every store that exists in this tree; absent stores are skipped."""
    root = REPO_ROOT if root is None else root
    results: List[Dict[str, Any]] = []
    for store in STORE_INVENTORY:
        path = store_path(store, root=root, environ=environ)
        if not path.is_file():
            results.append({
                "store": store["id"],
                "status": "skipped",
                "reason": f"store not present: {path}",
            })
            continue
        manifest = backup_store(store["id"], dest_dir, root=root, environ=environ)
        results.append({
            "store": store["id"],
            "status": "backed_up",
            "manifest_path": manifest["manifest_path"],
            "bytes": manifest["bytes"],
            "row_total": manifest["row_total"],
        })
    return results


def _manifest_from(path: Path) -> Tuple[Dict[str, Any], Path]:
    """Accept either a manifest path or its ``.db`` sidecar."""
    manifest_path = path.with_suffix(".json") if path.suffix == ".db" else path
    if not manifest_path.is_file():
        raise BackupError(f"manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BackupError(f"unreadable manifest {manifest_path}: {exc}") from exc
    if manifest.get("schema") != SCHEMA:
        raise BackupError(
            f"manifest schema {manifest.get('schema')!r} is not {SCHEMA!r}"
        )
    return manifest, manifest_path


# ---------------------------------------------------------------------------
# Verify / restore
# ---------------------------------------------------------------------------

def verify_backup(manifest_ref: Path) -> Dict[str, Any]:
    """Re-check hash, size, integrity and row counts; raise on any mismatch."""
    manifest, manifest_path = _manifest_from(manifest_ref)
    data = manifest_path.parent / manifest["file"]
    if not data.is_file():
        raise BackupError(f"backup file missing: {data}")

    problems: List[str] = []
    if data.stat().st_size != manifest["bytes"]:
        problems.append(
            f"size {data.stat().st_size} != manifest {manifest['bytes']}"
        )
    digest = _sha256(data)
    if digest != manifest["sha256"]:
        problems.append("sha256 mismatch")
    if problems:
        # A changed file is not restorable; do not try to read it as SQLite.
        raise BackupError(
            f"backup {manifest_path.name} is not restorable: " + "; ".join(problems)
        )
    try:
        info = inspect_database(data)
    except (BackupError, sqlite3.Error) as exc:
        raise BackupError(
            f"backup {manifest_path.name} is not restorable: unreadable ({exc})"
        ) from exc
    if not info["integrity_ok"]:
        problems.append(f"integrity_check failed: {info['integrity']}")
    if info["tables"] != manifest["tables"]:
        problems.append("table row counts differ from the manifest")
    if info["unreadable_tables"] != manifest.get("unreadable_tables", {}):
        problems.append("unreadable virtual tables differ from the manifest")
    if problems:
        raise BackupError(
            f"backup {manifest_path.name} is not restorable: " + "; ".join(problems)
        )
    return {
        "store": manifest["store"],
        "manifest_path": str(manifest_path),
        "file": str(data),
        "sha256": digest,
        "bytes": manifest["bytes"],
        "row_total": manifest["row_total"],
        "tables": len(manifest["tables"]),
        "verified": True,
    }


def restore_backup(manifest_ref: Path, target: Path, *, force: bool = False,
                   receipt: Optional[Path] = None) -> Dict[str, Any]:
    """Restore a verified backup into ``target``; refuse unless it round-trips."""
    verify_backup(manifest_ref)
    manifest, manifest_path = _manifest_from(manifest_ref)
    if target.exists() and not force:
        raise BackupError(
            f"target exists: {target} (stop the writer and pass --force to replace it)"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".restore-partial")
    if staged.exists():
        staged.unlink()

    source = manifest_path.parent / manifest["file"]
    try:
        shutil.copyfile(source, staged)
        info = inspect_database(staged)
        if not info["integrity_ok"]:
            raise BackupError(f"restored copy failed integrity_check: {info['integrity']}")
        if info["tables"] != manifest["tables"]:
            raise BackupError("restored copy row counts differ from the manifest")
        if info["unreadable_tables"] != manifest.get("unreadable_tables", {}):
            raise BackupError("restored copy unreadable virtual tables differ")
        staged.replace(target)
    except Exception:
        if staged.exists():
            staged.unlink()
        raise

    result = {
        "store": manifest["store"],
        "restored_to": str(target),
        "manifest_path": str(manifest_path),
        "row_total": manifest["row_total"],
        "tables": len(manifest["tables"]),
        "integrity_ok": True,
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }
    if receipt:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print(payload: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    if isinstance(payload, list):
        for row in payload:
            print("  ".join(f"{k}={v}" for k, v in row.items()))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sqlite_backup",
        description="Consistent backup/verify/restore for the SQLite stores.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inventory", help="list the stores and whether they exist")

    sub_backup = sub.add_parser("backup", help="snapshot every present store")
    sub_backup.add_argument("--dest", required=True, help="backup directory")
    sub_backup.add_argument("--store", action="append", default=None,
                            help="store id (repeatable); default: all present")

    sub_verify = sub.add_parser("verify", help="verify one backup manifest")
    sub_verify.add_argument("--manifest", required=True)

    sub_restore = sub.add_parser("restore", help="restore one verified backup")
    sub_restore.add_argument("--manifest", required=True)
    sub_restore.add_argument("--target", required=True)
    sub_restore.add_argument("--force", action="store_true",
                             help="replace an existing target (stop the writer first)")
    sub_restore.add_argument("--receipt", default=None,
                             help="write a restore receipt JSON here")

    args = parser.parse_args(argv)

    try:
        if args.command == "inventory":
            _print(describe_stores(), args.json)
            return 0

        if args.command == "backup":
            dest = Path(args.dest)
            if args.store:
                results = []
                for store_id in args.store:
                    manifest = backup_store(store_id, dest)
                    results.append({
                        "store": store_id,
                        "status": "backed_up",
                        "manifest_path": manifest["manifest_path"],
                        "bytes": manifest["bytes"],
                        "row_total": manifest["row_total"],
                    })
            else:
                results = backup_all(dest)
            _print(results, args.json)
            return 0 if all(r["status"] in ("backed_up", "skipped") for r in results) else 1

        if args.command == "verify":
            _print(verify_backup(Path(args.manifest)), args.json)
            return 0

        if args.command == "restore":
            result = restore_backup(
                Path(args.manifest),
                Path(args.target),
                force=args.force,
                receipt=Path(args.receipt) if args.receipt else None,
            )
            _print(result, args.json)
            return 0

        return 2
    except BackupError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
