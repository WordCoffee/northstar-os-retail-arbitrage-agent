"""Container entrypoint: apply forward foundation migrations and record the ledger.

Applies ``Northstar_backend/migrations_foundation/*.sql`` in filename order
(skipping ``*rollback*``). Records each applied (filename, sha256) in
``schema_migrations`` and refuses on checksum drift. No-op without a DB URL.
Run from the Northstar_backend dir.
"""
from __future__ import annotations

import glob
import hashlib
import os
import sys


def _checksum(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def main() -> int:
    url = os.environ.get("DB_URL") or os.environ.get("FOUNDATION_DB_URL")
    if not url:
        print("DB_URL/FOUNDATION_DB_URL not set; SQLite mode, nothing to migrate.")
        return 0
    from foundation.db_postgres import PostgresFoundationDB

    db = PostgresFoundationDB(url)
    raw = db._raw
    raw.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " filename text PRIMARY KEY,"
        " checksum text NOT NULL,"
        " applied_at timestamptz NOT NULL DEFAULT now())")
    raw.commit()
    cur = raw.cursor()
    cur.execute("SELECT filename, checksum FROM schema_migrations")
    applied = {r["filename"]: r["checksum"] for r in cur.fetchall()}

    files = sorted(p for p in glob.glob("migrations_foundation/*.sql")
                   if "rollback" not in os.path.basename(p).lower())
    newly_applied = 0
    for path in files:
        name = os.path.basename(path)
        checksum = _checksum(path)
        if name in applied:
            if applied[name] != checksum:
                print(f"DRIFT: {name} checksum changed since it was applied; refusing.")
                return 2
            continue
        db.apply_sql_file(path)
        raw.execute("INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                    [name, checksum])
        raw.commit()
        newly_applied += 1
        print(f"applied {name}")
    print(f"migrations complete: {newly_applied} newly applied, {len(files)} total")
    return 0


if __name__ == "__main__":
    sys.exit(main())