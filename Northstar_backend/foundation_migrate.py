"""Container entrypoint: apply forward foundation migrations (no rollbacks).

Applies ``Northstar_backend/migrations_foundation/*.sql`` in filename order,
skipping any ``*rollback*`` file. No-op when ``FOUNDATION_DB_URL`` is unset
(SQLite dev does not use these migrations). Run from the Northstar_backend dir.
"""
from __future__ import annotations

import glob
import os
import sys


def main() -> int:
    url = os.environ.get("FOUNDATION_DB_URL")
    if not url:
        print("FOUNDATION_DB_URL not set; SQLite mode, nothing to migrate.")
        return 0
    from foundation.db_postgres import PostgresFoundationDB

    files = sorted(p for p in glob.glob("migrations_foundation/*.sql")
                   if "rollback" not in os.path.basename(p).lower())
    if not files:
        print("no forward migrations found")
        return 0
    db = PostgresFoundationDB(url)
    for path in files:
        db.apply_sql_file(path)
        print(f"applied {path}")
    print(f"migrations complete: {len(files)} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())