"""D10 identity-migration fixtures (Phase 7 item 1).

Throwaway SQLite file; never touches the operator's northstar.db. Exercises the
planner and the apply path across: single-org, multi-org, no-org, unknown-bucket
and empty-bucket cases; proves idempotency and that nothing is deleted.

Run:  python tools/test_d10_identity_migration.py
Exit: 0 = contract holds, 1 = a failure.
"""
from __future__ import annotations

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Northstar_backend"))

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


ORG_A = "org-aaaa"
ORG_B = "org-bbbb"


def _insert(db, table, account_id, n, prefix):
    for i in range(n):
        rid = f"{prefix}-{i}"
        if table == "ds_projects":
            db.execute("INSERT INTO ds_projects (id, account_id, name, section) VALUES (?,?,?,?)", (rid, account_id, f"p{i}", "listing-images"))
        elif table == "ds_assets":
            db.execute("INSERT INTO ds_assets (id, account_id, name, asset_type) VALUES (?,?,?,?)", (rid, account_id, f"a{i}", "image"))
        elif table == "ds_jobs":
            db.execute("INSERT INTO ds_jobs (id, account_id, job_type) VALUES (?,?,?)", (rid, account_id, "generate"))
        elif table == "ds_rechecks":
            db.execute("INSERT INTO ds_rechecks (id, account_id, checked_at, verdict) VALUES (?,?,?,?)", (rid, account_id, "2026-10-01T00:00:00Z", "marker-present"))
        elif table == "ds_imports":
            db.execute("INSERT INTO ds_imports (id, account_id, kind, source_label, fingerprint, imported_at) VALUES (?,?,?,?,?,?)", (rid, account_id, "sp_search_terms", "lbl", f"fp-{prefix}-{i}", "2026-10-01T00:00:00Z"))
        elif table == "ds_search_terms":
            db.execute("INSERT INTO ds_search_terms (id, account_id, import_id, kind, term) VALUES (?,?,?,?,?)", (rid, account_id, "imp", "sp_search_terms", f"term{i}"))
        elif table == "ds_variants":
            db.execute("INSERT INTO ds_variants (id, account_id, name) VALUES (?,?,?)", (rid, account_id, f"v{i}"))
        elif table == "ds_variant_metrics":
            db.execute("INSERT INTO ds_variant_metrics (id, account_id, variant_id, source) VALUES (?,?,?,?)", (rid, account_id, "var", "user"))
    db.commit()


def _buckets(db, table):
    rows = db.execute(f"SELECT COALESCE(account_id,'') AS b, COUNT(*) AS n FROM {table} GROUP BY 1").fetchall()
    return {str(r["b"]): int(r["n"]) for r in rows}


def _total(db, table):
    return db.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]


def fresh_db():
    import data_layer
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="ns_d10_")
    tmp.close()
    data_layer._SQLITE_PATH = __import__("pathlib").Path(tmp.name)
    layer = data_layer.DataLayer()
    return layer, tmp.name


def main() -> int:
    import migrate_ds_identity as mig

    # ── Scenario 1: TWO orgs -> shared buckets quarantine, org buckets stay ──
    layer, path1 = fresh_db()
    _insert(layer, "ds_rechecks", "default", 3, "s1-default")
    _insert(layer, "ds_rechecks", ORG_A, 2, "s1-a")
    _insert(layer, "ds_rechecks", ORG_B, 1, "s1-b")
    plan = mig.plan_migration(layer, [ORG_A, ORG_B])
    if plan["moves"] == [] and len(plan["quarantine"]) == 1 and plan["quarantine"][0]["bucket"] == "default" and plan["quarantine"][0]["count"] == 3:
        ok("two orgs: the shared bucket is quarantined and NOT moved")
    else:
        no(f"two-org plan wrong: moves={plan['moves']} quarantine={plan['quarantine']}")
    if not plan["fully_mapped"]:
        ok("two orgs: fully_mapped is False (nothing may be applied)")
    else:
        no("two orgs: fully_mapped reported True")
    before = _buckets(layer, "ds_rechecks")
    mig.apply_migration(layer, plan)
    if _buckets(layer, "ds_rechecks") == before:
        ok("two orgs: apply changed nothing (quarantine is left in place)")
    else:
        no("two orgs: apply moved quarantined records")
    layer.close()
    os.unlink(path1)

    # ── Scenario 2: single org + UNKNOWN bucket -> unknown always quarantines ─
    layer, path2 = fresh_db()
    _insert(layer, "ds_projects", "default", 1, "s2-default")
    _insert(layer, "ds_projects", "ghost-tenant", 2, "s2-ghost")
    _insert(layer, "ds_projects", ORG_A, 1, "s2-a")
    plan = mig.plan_migration(layer, [ORG_A])
    move_froms = {m["from"] for m in plan["moves"]}
    q_buckets = {q["bucket"] for q in plan["quarantine"]}
    if move_froms == {"default"} and q_buckets == {"ghost-tenant"}:
        ok("single org: the shared bucket moves; an unknown bucket quarantines (never stolen)")
    else:
        no(f"single-org mixed plan wrong: moves={move_froms} quarantine={q_buckets}")
    if plan["quarantine"] and plan["quarantine"][0]["sample_ids"] and "may belong to another tenant" in plan["quarantine"][0]["reason"]:
        ok("the quarantine entry lists sample ids and states the reason")
    else:
        no("quarantine entry is missing ids or reason")
    layer.close()
    os.unlink(path2)

    # ── Scenario 3: single org, all shared buckets -> full map, idempotent ──
    layer, path3 = fresh_db()
    for table, prefix in (("ds_projects", "s3-p"), ("ds_rechecks", "s3-r"), ("ds_variants", "s3-v")):
        _insert(layer, table, "default", 2, f"{prefix}-d")
        _insert(layer, table, "anonymous", 1, f"{prefix}-a")
        _insert(layer, table, "", 1, f"{prefix}-e")
        _insert(layer, table, ORG_A, 1, f"{prefix}-own")
    total_before = sum(_total(layer, t) for t in ("ds_projects", "ds_rechecks", "ds_variants"))
    plan = mig.plan_migration(layer, [ORG_A])
    if plan["fully_mapped"] and len(plan["moves"]) == 9:
        ok(f"single org: every shared bucket maps ({len(plan['moves'])} moves), fully_mapped True")
    else:
        no(f"single-org plan wrong: moves={len(plan['moves'])} fully_mapped={plan['fully_mapped']}")
    applied = mig.apply_migration(layer, plan)
    total_after = sum(_total(layer, t) for t in ("ds_projects", "ds_rechecks", "ds_variants"))
    if total_before == total_after == 15:
        ok("apply preserves every record (nothing deleted, nothing duplicated)")
    else:
        no(f"record totals changed: {total_before} -> {total_after}")
    for t in ("ds_projects", "ds_rechecks", "ds_variants"):
        b = _buckets(layer, t)
        if b == {ORG_A: 5}:
            ok(f"{t}: all 5 records now owned by the single org")
        else:
            no(f"{t}: buckets after apply = {b}")
    second = mig.plan_migration(layer, [ORG_A])
    if second["moves"] == [] and second["fully_mapped"]:
        ok("a second run has nothing left to move (idempotent)")
    else:
        no(f"second run planned moves: {second['moves']}")
    layer.close()
    os.unlink(path3)

    # ── Scenario 4: no orgs -> everything quarantines, nothing moves ────────
    layer, path4 = fresh_db()
    _insert(layer, "ds_jobs", "default", 2, "s4-d")
    _insert(layer, "ds_jobs", "", 1, "s4-e")
    plan = mig.plan_migration(layer, [])
    if plan["moves"] == [] and len(plan["quarantine"]) == 2 and plan["target_org"] is None:
        ok("zero orgs: every record quarantines; there is no target")
    else:
        no(f"no-org plan wrong: {plan}")
    layer.close()
    os.unlink(path4)

    print(f"\nD10 IDENTITY MIGRATION FIXTURES: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
