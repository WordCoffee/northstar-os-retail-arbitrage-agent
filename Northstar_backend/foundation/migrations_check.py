"""Startup migration posture (P2-T4).

Compares the forward migration files on disk against the applied set recorded in
the PostgreSQL ``schema_migrations`` ledger. In hosted environments the startup
check **fails closed** when any forward migration is missing or drifted; in dev
it reports status without blocking. Pure comparison logic is unit-testable
offline; the ledger read only runs against PostgreSQL.
"""
from __future__ import annotations

import glob
import os
from typing import Optional

from .migrate import MigrationRefused, sql_checksum

_HOSTED_ENVIRONMENTS = {"production", "production_tenant", "staging"}


def forward_migration_files(migrations_dir: str) -> list[tuple[str, str]]:
    """Sorted (filename, sha256) for every forward migration (rollbacks excluded)."""
    files = sorted(p for p in glob.glob(os.path.join(migrations_dir, "*.sql"))
                   if "rollback" not in os.path.basename(p).lower())
    return [(os.path.basename(p), sql_checksum(p)) for p in files]


def compare_applied(expected: list[tuple[str, str]],
                    applied: dict[str, str]) -> dict:
    """Pure comparison: which expected migrations are missing or drifted."""
    missing = [name for name, _ in expected if name not in applied]
    drifted = [name for name, checksum in expected
               if name in applied and applied[name] != checksum]
    return {
        "missing": missing,
        "drifted": drifted,
        "expected_count": len(expected),
        "applied_count": len(applied),
        "current": not missing and not drifted,
    }


def _read_applied(db) -> dict[str, str]:
    """Read the ledger from a PostgresFoundationDB. Empty when the table is absent."""
    try:
        cur = db._raw.cursor()
        cur.execute("SELECT filename, checksum FROM schema_migrations")
        return {r["filename"]: r["checksum"] for r in cur.fetchall()}
    except Exception:  # noqa: BLE001 - absent ledger == nothing applied
        # A failed statement aborts the transaction; roll back so the shared
        # connection stays usable for seeding/queries afterward.
        try:
            db._raw.rollback()
        except Exception:  # noqa: BLE001
            pass
        return {}


def assert_migrations_current(db, *, environment: Optional[str], migrations_dir: str,
                              require: Optional[bool] = None) -> dict:
    """Fail closed on a stale/behind schema in hosted environments.

    ``require`` defaults to True when ``environment`` is production/staging.
    Returns the status dict either way.
    """
    if require is None:
        require = (environment or "").lower() in _HOSTED_ENVIRONMENTS
    expected = forward_migration_files(migrations_dir)
    status = compare_applied(expected, _read_applied(db))
    status["required"] = require
    status["environment"] = environment
    if require and not status["current"]:
        raise MigrationRefused(
            "database migrations are behind: "
            f"missing={status['missing']} drifted={status['drifted']}")
    return status
