"""D10 identity migration — move pre-Phase-7 shared-bucket Design Studio records
to their owning organization, or quarantine them.

Background: before Phase 7 every Design Studio route resolved identity through
`get_current_user`, which has no cookie awareness, so every UI caller collapsed
into one shared bucket (`default`). Phase 7 switched all routes to the strict
organization-scoped session; this migration handles the records written before
that switch.

Contract (deterministic, no guessing):
  • A record whose account_id is already a real organization id stays (no-op).
  • A record in a SHARED bucket ("default", "anonymous", or empty) is movable to
    the single organization ONLY when the deployment holds EXACTLY ONE
    organization. Zero or multiple organizations -> the owner is ambiguous ->
    the record is QUARANTINED: left untouched and listed in the report.
  • Any other unknown bucket is ALWAYS quarantined: a bucket that is not a known
    organization and not a known shared bucket may be a real other tenant, and
    moving it would steal data.
  • Nothing is deleted. Apply is an UPDATE of account_id; a second run has no
    moves left (idempotent).

Run (dry-run first, always):
  python migrate_ds_identity.py --dry-run
  python migrate_ds_identity.py --apply
  python migrate_ds_identity.py --dry-run --json     # full report on stdout
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# store key -> table. Order is presentation order in the report.
STORES = (
    ("projects", "ds_projects"),
    ("assets", "ds_assets"),
    ("jobs", "ds_jobs"),
    ("rechecks", "ds_rechecks"),
    ("imports", "ds_imports"),
    ("search_terms", "ds_search_terms"),
    ("variants", "ds_variants"),
    ("variant_metrics", "ds_variant_metrics"),
)

# Buckets that were shared by construction (the pre-Phase-7 collapse).
SHARED_BUCKETS = {"default", "anonymous", ""}

SAMPLE_IDS = 5


def _org_ids() -> list:
    """The deployment's organization ids, read from the foundation store."""
    from foundation.api.state import FoundationState
    st = FoundationState.build()
    return [str(o["id"]) for o in st.repos.organizations.list()]


def plan_migration(db, org_ids) -> dict:
    """Pure planner: returns the full report WITHOUT moving anything."""
    org_set = {str(o) for o in org_ids}
    single = str(org_ids[0]) if len(org_ids) == 1 else None
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "org_count": len(org_ids),
        "orgs": sorted(org_set),
        "target_org": single,
        "rule": "shared buckets move only when exactly one organization exists; unknown buckets always quarantine",
        "stores": {},
        "moves": [],
        "quarantine": [],
    }
    for name, table in STORES:
        rows = db.execute(
            f"SELECT account_id, COUNT(*) AS n FROM {table} GROUP BY account_id"
        ).fetchall()
        buckets = {}
        for r in rows:
            key = str(r["account_id"] if r["account_id"] is not None else "")
            buckets[key] = int(r["n"])
        report["stores"][name] = {"table": table, "buckets": buckets}
        for bucket, n in sorted(buckets.items()):
            if bucket in org_set:
                continue  # already owned by a real organization
            if bucket in SHARED_BUCKETS and single:
                report["moves"].append({
                    "store": name, "table": table,
                    "from": bucket or "(empty)", "to": single, "count": n,
                })
            else:
                reason = (
                    "owner ambiguous: the deployment does not hold exactly one organization"
                    if bucket in SHARED_BUCKETS
                    else "unknown bucket: not a known organization and not a shared bucket - may belong to another tenant"
                )
                sample_rows = db.execute(
                    f"SELECT id FROM {table} WHERE COALESCE(account_id, '') = ? LIMIT {SAMPLE_IDS}",
                    (bucket,),
                ).fetchall()
                report["quarantine"].append({
                    "store": name, "table": table,
                    "bucket": bucket or "(empty)", "count": n,
                    "sample_ids": [str(r["id"]) for r in sample_rows],
                    "reason": reason,
                })
    report["fully_mapped"] = not report["quarantine"]
    return report


def apply_migration(db, plan: dict) -> list:
    """Execute the planned moves. Idempotent: only planned buckets are touched."""
    applied = []
    for mv in plan["moves"]:
        db.execute(
            f"UPDATE {mv['table']} SET account_id = ? WHERE COALESCE(account_id, '') = ?",
            (mv["to"], "" if mv["from"] == "(empty)" else mv["from"]),
        )
        applied.append(mv)
    db.commit()
    return applied


def _summary(report: dict) -> str:
    lines = []
    lines.append(f"organizations: {report['org_count']} {report['orgs']}")
    lines.append(f"target org   : {report['target_org'] or '(none - shared buckets cannot move)'}")
    for name, meta in report["stores"].items():
        lines.append(f"  {name:16s} {meta['buckets']}")
    lines.append(f"moves        : {len(report['moves'])}")
    for mv in report["moves"]:
        lines.append(f"    {mv['store']}: {mv['from']} -> {mv['to']} ({mv['count']} record(s))")
    lines.append(f"quarantine   : {len(report['quarantine'])}")
    for q in report["quarantine"]:
        lines.append(f"    {q['store']} [{q['bucket']}] {q['count']} record(s) :: {q['reason']}")
    lines.append(f"fully mapped : {report['fully_mapped']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="D10 Design Studio identity migration")
    ap.add_argument("--apply", action="store_true", help="perform the planned moves (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", help="explicit dry-run (the default)")
    ap.add_argument("--json", action="store_true", help="print the full JSON report to stdout")
    ap.add_argument("--report", default="", help="also write the JSON report to this path")
    ap.add_argument("--db", default="", help="override the SQLite path (tests only)")
    ap.add_argument("--orgs", default="", help="TEST ONLY: comma-separated organization ids to use instead of the deployment's own list (for demonstrating the move path on synthetic rows)")
    args = ap.parse_args()

    if args.apply and args.dry_run:
        print("choose one of --apply / --dry-run")
        return 2

    if args.db:
        import data_layer
        data_layer._SQLITE_PATH = Path(args.db)
    from data_layer import get_db
    db = get_db()

    if args.orgs:
        org_ids = [o.strip() for o in args.orgs.split(",") if o.strip()]
        print("WARNING: --orgs override in use; the deployment's own organization list was NOT consulted. TEST ONLY.")
    else:
        org_ids = _org_ids()
    report = plan_migration(db, org_ids)
    report["mode"] = "apply" if args.apply else "dry-run"

    print(_summary(report))
    if args.apply:
        applied = apply_migration(db, report)
        report["applied"] = applied
        # Re-plan to prove idempotency in the same run.
        after = plan_migration(db, org_ids)
        report["after_apply"] = {"moves": len(after["moves"]), "quarantine": len(after["quarantine"])}
        print(f"applied      : {len(applied)} move(s); re-plan moves={len(after['moves'])} quarantine={len(after['quarantine'])}")

    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"report       : {args.report}")
    if args.json:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
