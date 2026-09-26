#!/usr/bin/env python
"""Regenerate the foundation Postgres migration from the single SCHEMA source.

Usage:
  python -m Northstar_backend.tools.foundation_generate_sql
  python -m Northstar_backend.tools.foundation_generate_sql --out <path>

This is a codegen step only. It does NOT apply the migration.
"""
from __future__ import annotations

import argparse
import os
import sys

from Northstar_backend.foundation.db import postgres_ddl, schema_equivalence_report
from Northstar_backend.foundation.api.state import FoundationState  # noqa: F401 (path check)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Regenerate foundation SQL (no apply).")
    ap.add_argument("--out", default=os.path.join(
        "Northstar_backend", "migrations_foundation", "001_foundation.sql"))
    args = ap.parse_args(argv)

    rep = schema_equivalence_report()
    if not rep["equivalent"]:
        print("REFUSING: schema not equivalent:", rep["postgres_missing_items"])
        return 2
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(postgres_ddl())
    print(f"wrote {args.out} (equivalent={rep['equivalent']}, "
          f"sqlite_validated={rep['sqlite_validated']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())