import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())

BACKUP_DIR = Path("Northstar_backend") / "data" / "staging"
STAGING_USER = "northstar_staging_owner"
STAGING_DB = "northstar_staging"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def main():
    from Northstar_backend.foundation import secrets as vault
    password = vault.get_secret("staging_db_password")
    if not password:
        print("staging_db_password not in vault")
        return 2
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"staging-pre-006-{stamp}.sql"
    env = dict(os.environ)
    env["PGPASSWORD"] = password
    p = subprocess.run(["docker", "exec", "northstar-staging", "pg_dump",
                        "-U", STAGING_USER, "-d", STAGING_DB],
                       capture_output=True, text=True, timeout=120, env=env)
    if p.returncode != 0:
        print("pg_dump failed:", p.stderr[-1200:])
        return 1
    backup.write_text(p.stdout, encoding="utf-8")
    content = backup.read_text(encoding="utf-8")
    if len(content) < 64:
        print("backup too small; ABORT")
        return 1
    print(f"BACKUP verified: {backup.name} ({len(content)} bytes)")

    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    url = (f"postgresql://{STAGING_USER}:{password}@127.0.0.1:55433/{STAGING_DB}")
    db = PostgresFoundationDB(url)
    try:
        t0 = time.perf_counter()
        db.apply_sql_file(os.path.join("Northstar_backend", "migrations_foundation",
                                       "006_private_beta_readiness.sql"))
        ms = int((time.perf_counter() - t0) * 1000)
        fp = db.schema_fingerprint()
        print(f"006 applied ({ms} ms); tables={fp['table_count']} "
              f"columns={fp['column_count']}")
        for t in ("billing_customers", "checkout_sessions", "subscriptions",
                  "billing_events", "invites", "org_entitlements"):
            assert t in fp["tables"], f"missing {t}"
        corr = "private_beta_addendum_version" in fp["tables"].get("account_acceptance", [])
        assert corr, "account_acceptance addendum column missing"
        report = {
            "owner": "Tyrone", "step": "006_private_beta_readiness (staging)",
            "applied_at": now_iso(),
            "backup": {"path": str(backup), "bytes": len(content), "verified": True},
            "migration": "006_private_beta_readiness.sql", "duration_ms": ms,
            "post_apply": {"tables": fp["table_count"], "columns": fp["column_count"],
                           "new_tables": ["billing_customers", "checkout_sessions",
                                          "subscriptions", "billing_events",
                                          "invites", "org_entitlements"]},
            "rollback": "NOT EXECUTED (Tyrone sole rollback authority)",
        }
        out = Path("docs") / "northstar-phase1c" / "staging-006-apply-report.json"
        out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print("evidence:", out)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())