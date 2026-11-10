"""Migration control & staging guardrails (Phase 1C-02, offline-safe parts).

This module implements everything about the staging migration that does NOT
require a live PostgreSQL connection: identity guardrails, SQL checksums, a
migration-ledger record, drift detection, and rollback-SQL generation.

It does NOT open a database connection and does NOT apply anything.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Optional

from .db import SCHEMA

FOUNDATION_TABLES = list(SCHEMA.keys())
MIGRATION_ID = "foundation-001"

DEFAULT_PRODUCTION_DENYLIST = ("prod", "production", "live", "primary")


class MigrationRefused(RuntimeError):
    pass


def _redact(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    v = str(value)
    if len(v) <= 2:
        return "*" * len(v)
    return v[0] + "*" * (len(v) - 2) + v[-1]


def production_denylist() -> list[str]:
    raw = os.environ.get("NORTHSTAR_PRODUCTION_DENYLIST") or ""
    tokens = [t.strip().lower() for t in raw.split(",") if t.strip()]
    return list(DEFAULT_PRODUCTION_DENYLIST) + tokens


def sql_checksum(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def assert_staging_identity(*, environment: str, host: Optional[str],
                           database: Optional[str], allow_flag: Optional[bool] = None,
                           denylist: Optional[list[str]] = None) -> dict:
    """Refuse to proceed unless the target is provably staging. Never displays
    secrets; host/database are returned redacted."""
    allow = (os.environ.get("NORTHSTAR_ALLOW_STAGING_MIGRATION", "") == "1") \
        if allow_flag is None else bool(allow_flag)
    denylist = production_denylist() if denylist is None else denylist
    problems: list[str] = []
    if (environment or "").lower() != "staging":
        problems.append("environment_not_staging")
    if not allow:
        problems.append("missing_NORTHSTAR_ALLOW_STAGING_MIGRATION")
    if not host or not database:
        problems.append("missing_target_identity")
    low = f"{(host or '').lower()} {(database or '').lower()}"
    for token in denylist:
        if token and token in low:
            problems.append(f"denylisted_identifier:{token}")
    if problems:
        raise MigrationRefused("; ".join(problems))
    return {"environment": "staging", "host": _redact(host), "database": _redact(database),
            "migration_id": MIGRATION_ID}


def detect_sql_drift(migration_path: str) -> dict:
    """Compare the on-disk migration file against the SCHEMA-derived generation."""
    from .db import postgres_ddl
    expected = postgres_ddl()
    if not os.path.exists(migration_path):
        return {"exists": False, "in_sync": False}
    disk = open(migration_path, encoding="utf-8").read()
    return {"exists": True, "in_sync": disk.strip() == expected.strip(),
            "disk_checksum": hashlib.sha256(disk.encode()).hexdigest(),
            "expected_checksum": hashlib.sha256(expected.encode()).hexdigest()}


def generate_rollback_sql(tables: Optional[list[str]] = None) -> str:
    """Compensating rollback: drop the foundation tables (additive; no legacy
    table is referenced). Rows written after migration are removed with them."""
    tables = tables or FOUNDATION_TABLES
    lines = ["-- Northstar OS Foundation rollback (compensating)",
             "-- Drops ONLY foundation tables. Legacy tables are never touched.",
             "-- NOT EXECUTED here; run only in a controlled rollback.",
             "BEGIN;"]
    for t in reversed(tables):
        lines.append(f'DROP TABLE IF EXISTS "{t}";')
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def migration_ledger_entry(*, checksum: str, environment: str,
                           applied_by: str = "unknown", success: bool = False,
                           duration_ms: Optional[int] = None,
                           error_summary: Optional[str] = None,
                           transaction_boundary: str = "single-transaction") -> dict:
    return {
        "migration_id": MIGRATION_ID,
        "checksum": checksum,
        "environment": environment,
        "applied_at": datetime.now(timezone.utc).isoformat() if success else None,
        "applied_by": applied_by,
        "duration_ms": duration_ms,
        "success": success,
        "error_summary": _redact(error_summary) if error_summary else None,
        "transaction_boundary": transaction_boundary,
        "idempotence": "IF NOT EXISTS (reapply-safe)",
        "tables": len(FOUNDATION_TABLES),
    }


def preflight(migration_path: str, *, environment: str, host: Optional[str] = None,
              database: Optional[str] = None, allow_flag: Optional[bool] = None,
              denylist: Optional[list[str]] = None) -> dict:
    """Offline preflight package. Raises MigrationRefused on a guardrail breach.
    Does NOT connect to a database."""
    identity = assert_staging_identity(environment=environment, host=host,
                                       database=database, allow_flag=allow_flag,
                                       denylist=denylist)
    drift = detect_sql_drift(migration_path)
    checksum = sql_checksum(migration_path) if os.path.exists(migration_path) else None
    return {
        "migration_id": MIGRATION_ID,
        "identity": identity,
        "checksum": checksum,
        "drift": drift,
        "table_count": len(FOUNDATION_TABLES),
        "tables": FOUNDATION_TABLES,
        "rollback_sql_available": True,
        "applied": False,
        "note": "preflight only; no database connection opened",
    }