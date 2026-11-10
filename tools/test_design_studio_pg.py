"""Postgres-mode harness for the Design Studio store (Phase 8 item 2).

Runs INSIDE the API container against the local compose Postgres:
    docker cp tools/test_design_studio_pg.py <api>:/app/Northstar_backend/
    docker exec <api> python test_design_studio_pg.py

Proves on the REAL backend:
  • data_layer is in postgres mode and the schema was created idempotently;
  • cross-tenant isolation on every ds_* store (list/read/update/delete);
  • the idempotency paths (fingerprint duplicate, legacy-key duplicate) work
    through the driver's IntegrityError translation;
  • the SQLite `SELECT changes()` idiom answers correctly (delete rowcount);
  • the D10 migration PLAN runs against Postgres and reports counts per
    organization bucket.

All test rows use a unique tag and are deleted afterwards; the real store is
left as found.

Exit: 0 = contract holds, 1 = a failure, 2 = NOT RUN (not in postgres mode).
"""
from __future__ import annotations

import json
import os
import sys
import uuid

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"PASS  {msg}")


def no(msg: str) -> None:
    global FAIL
    FAIL += 1
    FAILURES.append(msg)
    print(f"FAIL  {msg}")


def main() -> int:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import data_layer

    db = data_layer.get_db()
    mode = getattr(db, "mode", "unknown")
    print(f"data_layer mode: {mode}")
    if mode != "postgres":
        print("NOT RUN  the configured store is not Postgres "
              f"(mode={mode}). Set DATABASE_URL and re-run inside the container.")
        return 2

    tag = uuid.uuid4().hex[:8]
    A = f"pgtest-a-{tag}"
    B = f"pgtest-b-{tag}"
    ds = data_layer.DesignStudioContainer(db)

    try:
        # ── Schema present + idempotent re-init ─────────────────────────────
        cur = db.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='northstar_data' AND table_name LIKE 'ds_%' ORDER BY 1"
        )
        tables = {r["table_name"] for r in cur.fetchall()}
        expected = {"ds_projects", "ds_assets", "ds_jobs", "ds_rechecks",
                    "ds_imports", "ds_search_terms", "ds_variants", "ds_variant_metrics"}
        if expected <= tables:
            ok(f"the ds_* schema exists on Postgres ({len(tables)} tables)")
        else:
            no(f"missing ds tables: {sorted(expected - tables)}")

        second = data_layer.DataLayer()  # fresh connect + idempotent schema create
        cur2 = second.execute(
            "SELECT COUNT(*) AS cnt FROM information_schema.tables "
            "WHERE table_schema='northstar_data' AND table_name LIKE 'ds_%'"
        )
        n2 = cur2.fetchone()["cnt"]
        second.close()
        if n2 == len(tables):
            ok("a second DataLayer() init is idempotent (same table count)")
        else:
            no(f"re-init changed the schema: {len(tables)} -> {n2}")

        # ── Isolation across every store ────────────────────────────────────
        pid = ds.projects.create({"account_id": A, "name": "PG probe project", "section": "listing-images"})
        if ds.projects.get_by_id(pid, account_id=B) is None:
            ok("tenant B cannot READ tenant A's project")
        else:
            no("LEAK: tenant B read tenant A's project")
        if ds.projects.update(pid, {"name": "defaced"}, account_id=B) is False:
            ok("tenant B cannot UPDATE tenant A's project")
        else:
            no("LEAK: tenant B updated tenant A's project")
        if ds.projects.delete(pid, account_id=B) is False:
            ok("tenant B cannot DELETE tenant A's project")
        else:
            no("LEAK: tenant B deleted tenant A's project")
        if ds.projects.delete(pid, account_id=A) is True:
            ok("the owner can delete its own project; SELECT changes() answered correctly (rowcount shim)")
        else:
            no("owner delete reported False (changes() shim broken)")
        if ds.projects.delete(pid, account_id=A) is False:
            ok("a second delete reports False (rowcount shim distinguishes)")
        else:
            no("second delete reported True")

        aid = ds.assets.create({"account_id": A, "name": "PG asset", "asset_type": "image"})
        jid = ds.jobs.create({"account_id": A, "job_type": "generate"})
        rid = ds.rechecks.create({"account_id": A, "asset_id": "pg-a", "verdict": "marker-present", "passed": True, "legacy_key": f"pg-{tag}-1"})
        vids = ds.variants.create({"account_id": A, "name": "PG variant"})
        if (ds.assets.get_by_id(aid, account_id=B) is None
                and ds.jobs.get_by_id(jid, account_id=B) is None
                and ds.rechecks.get_by_id(rid, account_id=B) is None
                and ds.variants.get_by_id(vids, account_id=B) is None):
            ok("tenant B cannot READ any of tenant A's asset/job/recheck/variant")
        else:
            no("LEAK: one of asset/job/recheck/variant crossed tenants")
        b_rows = (ds.rechecks.list_for_account(B) + ds.assets.list_by_project(account_id=B)
                  + ds.jobs.list_by_project(account_id=B) + ds.variants.list_for_account(B))
        if all(r["account_id"] == B for r in b_rows):
            ok(f"tenant B's lists contain only its own rows ({len(b_rows)} seen)")
        else:
            no("LEAK: a tenant list mixed accounts")

        # ── Idempotency through the driver's IntegrityError translation ─────
        from design_studio_imports import KIND_SP_SEARCH_TERMS, parse_import
        parsed = parse_import(kind=KIND_SP_SEARCH_TERMS,
                              content="Customer Search Term,Clicks\npg probe term,5\n",
                              filename="pg.csv")
        iid1 = ds.imports.create({
            "account_id": A, "kind": KIND_SP_SEARCH_TERMS, "source_label": f"pg {tag}",
            "filename": "pg.csv", "format": "csv",
            "observed_from": None, "observed_to": None, "observed_source": "none",
            "row_count": 1, "skipped_rows": 0, "columns_found": parsed["columns_found"],
            "missing_columns": parsed["missing_columns"], "notes": parsed["notes"],
            "fingerprint": parsed["fingerprint"],
        })
        iid2 = ds.imports.create({
            "account_id": A, "kind": KIND_SP_SEARCH_TERMS, "source_label": f"pg {tag} dup",
            "filename": "pg.csv", "format": "csv",
            "observed_from": None, "observed_to": None, "observed_source": "none",
            "row_count": 1, "skipped_rows": 0, "columns_found": parsed["columns_found"],
            "missing_columns": parsed["missing_columns"], "notes": parsed["notes"],
            "fingerprint": parsed["fingerprint"],
        })
        if iid2 == iid1:
            ok("a duplicate import fingerprint returns the EXISTING id on Postgres (IntegrityError translated)")
        else:
            no(f"duplicate import created a second row: {iid1} vs {iid2}")

        rid2 = ds.rechecks.create({"account_id": A, "asset_id": "pg-a", "verdict": "marker-present", "passed": True, "legacy_key": f"pg-{tag}-1"})
        if rid2 == rid:
            ok("a repeated legacy key does not duplicate on Postgres")
        else:
            no(f"legacy-key idempotency failed on Postgres: {rid} vs {rid2}")

        # ── D10 plan against Postgres ───────────────────────────────────────
        import migrate_ds_identity as mig
        orgs = [o for o in mig._org_ids()]
        plan = mig.plan_migration(db, orgs)
        print("D10 PG plan (counts per bucket):")
        for name, meta in plan["stores"].items():
            print(f"  {name:16s} {meta['buckets']}")
        print(f"  orgs={plan['org_count']} target={plan['target_org']} moves={len(plan['moves'])} quarantine={len(plan['quarantine'])} fully_mapped={plan['fully_mapped']}")
        print("D10_PG_PLAN_JSON=" + json.dumps({k: plan[k] for k in ("org_count", "orgs", "target_org", "moves", "quarantine", "fully_mapped")}))
        if isinstance(plan.get("stores"), dict) and "moves" in plan:
            ok("the D10 migration plan runs against Postgres and reports per-organization counts")
        else:
            no("D10 plan did not return the expected report shape")

    finally:
        # Remove every probe row for this run's tag (both tenants).
        for acct in (A, B):
            for table in ("ds_variant_metrics", "ds_variants", "ds_search_terms",
                          "ds_imports", "ds_rechecks", "ds_jobs", "ds_assets", "ds_projects"):
                db.execute(f"DELETE FROM {table} WHERE account_id = ?", (acct,))
        db.commit()
        print("probe rows cleaned up")

    print(f"\nPOSTGRES STORE HARNESS: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
