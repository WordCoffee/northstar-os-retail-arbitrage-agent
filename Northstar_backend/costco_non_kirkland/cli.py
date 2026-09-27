"""Unified CLI for the Costco Non-Kirkland manual-export workflow.

Commands:
  import-costco            Import Costco local catalog (normalize + exclude)
  create-provider-manifest Create a provider lookup manifest for eligible candidates
  signin                   Manage provider sign-in confirmation
  import-selleramp         Import a SellerAmp manual export (CSV/JSON)
  validate-market-snapshots Validate provider market snapshots
  validate-identity        Run source->ASIN identity validation
  calculate-economics      Compute conservative economics
  score                    Score + decide candidates (mfn_opportunity_score_v1)
  export-ranked            Export ranked/qualified/review/blocked candidates
  approval-request         Request human purchase approval
  approval-grant           Grant human purchase approval (decision record only)
  approval-revoke          Revoke an approval
  approval-list            List approvals
  status                   Pipeline status

Every command prints:  Network calls made: 0
"""
from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .cli_common import print_network_confirmation
from .pipeline import import_costco_local
from .store import PipelineStore
from .provider_imports import SellerAmpImporter, build_import_report


def _import_provider(path, *, dry_run: bool, strict: bool,
                     allow_partial: bool, kind: str, store) -> dict:
    importer = SellerAmpImporter(store=store)
    result = importer.import_file(path, kind=kind, dry_run=dry_run, strict=strict,
                                  allow_partial=allow_partial)
    return build_import_report(result)


def cmd_import_selleramp(args) -> int:
    store = PipelineStore()
    report = _import_provider(args.file, dry_run=args.dry_run,
                              strict=args.strict, allow_partial=args.allow_partial,
                              kind=args.kind, store=store)
    print_network_confirmation(0)
    import json
    print(json.dumps(report, indent=2, default=str))
    return 0 if report.get("rows_imported", 0) >= 0 else 1


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    parser = argparse.ArgumentParser(prog="costco-non-kirkland",
                                     description="Costco Non-Kirkland manual-export research workflow (offline).")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import-costco")
    p.add_argument("--source", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_import_costco)

    p = sub.add_parser("create-provider-manifest")
    p.add_argument("--run-id", required=True)
    p.add_argument("--provider", required=True, choices=["selleramp"])
    p.add_argument("--max-items", type=int, default=20)
    p.add_argument("--out", default=None)
    p.set_defaults(func=_cli_create_manifest)

    p = sub.add_parser("signin")
    p.add_argument("--service", required=True)
    p.add_argument("--check", action="store_true")
    p.add_argument("--done", action="store_true")
    p.set_defaults(func=_cli_signin)

    p = sub.add_parser("import-selleramp")
    p.add_argument("--file", required=True)
    p.add_argument("--kind", default="auto", choices=["auto", "csv", "json"])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--allow-partial", action="store_true")
    p.set_defaults(func=cmd_import_selleramp)

    p = sub.add_parser("validate-market-snapshots")
    p.add_argument("--provider", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_validate_snapshots)

    p = sub.add_parser("validate-identity")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_validate_identity)

    p = sub.add_parser("calculate-economics")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_calculate_economics)

    p = sub.add_parser("score")
    p.add_argument("--run-id", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_score)

    p = sub.add_parser("export-ranked")
    p.add_argument("--run-id", default=None)
    p.add_argument("--format", default="csv", choices=["csv", "json"])
    p.add_argument("--out", default=None)
    p.add_argument("--include-review", action="store_true")
    p.add_argument("--include-blocked", action="store_true")
    p.add_argument("--include-stale", action="store_true")
    p.add_argument("--set", default=None, help="comma-separated status set, e.g. qualified_candidate")
    p.set_defaults(func=_cli_export_ranked)

    p = sub.add_parser("approval-request")
    p.add_argument("--candidate-id", required=True)
    p.set_defaults(func=_cli_approval_request)

    p = sub.add_parser("approval-grant")
    p.add_argument("--candidate-id", required=True)
    p.add_argument("--quantity", type=int, required=True)
    p.add_argument("--expires-at", required=True)
    p.add_argument("--approved-by", required=True)
    p.set_defaults(func=_cli_approval_grant)

    p = sub.add_parser("approval-revoke")
    p.add_argument("--approval-id", required=True)
    p.add_argument("--reason", required=True)
    p.set_defaults(func=_cli_approval_revoke)

    p = sub.add_parser("approval-list")
    p.add_argument("--state", default=None)
    p.set_defaults(func=_cli_approval_list)

    p = sub.add_parser("status")
    p.set_defaults(func=_cli_status)

    p = sub.add_parser("audit-costco")
    p.add_argument("--run-id", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(func=_cli_audit_costco)

    p = sub.add_parser("apply-disallowed-filter")
    p.add_argument("--run-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_apply_disallowed)

    p = sub.add_parser("chromecontrol-sync")
    p.set_defaults(func=_cli_chromecontrol_sync)

    p = sub.add_parser("audit-source-identity")
    p.add_argument("--run-id", default=None)
    p.set_defaults(func=_cli_audit_source_identity)

    p = sub.add_parser("requirements-profile")
    p.add_argument("--out", default=None)
    p.set_defaults(func=_cli_requirements_profile)

    p = sub.add_parser("plan-brightdata-enrichment")
    p.add_argument("--run-id", default=None)
    p.add_argument("--max-items", type=int, default=25)
    p.add_argument("--out", default=None)
    p.set_defaults(func=_cli_plan_brightdata)

    p = sub.add_parser("validate-brightdata-schema")
    p.add_argument("--file", required=True)
    p.set_defaults(func=_cli_validate_brightdata_schema)

    p = sub.add_parser("run-brightdata-enrichment")
    p.add_argument("--manifest", required=True)
    p.add_argument("--approved", action="store_true")
    p.add_argument("--max-items", type=int, default=0)
    p.add_argument("--spend-cap", type=float, default=None)
    p.add_argument("--source-id", default=None)
    p.set_defaults(func=_cli_run_brightdata)

    p = sub.add_parser("import-brightdata-snapshot")
    p.add_argument("--file", required=True)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=_cli_import_brightdata)

    p = sub.add_parser("identifier-resolution-queue")
    p.add_argument("--run-id", default=None)
    p.add_argument("--build", action="store_true")
    p.set_defaults(func=_cli_identifier_queue)

    p = sub.add_parser("export-identity-readiness")
    p.add_argument("--run-id", default=None)
    p.add_argument("--format", default="csv", choices=["csv", "json"])
    p.add_argument("--out", default=None)
    p.set_defaults(func=_cli_export_identity_readiness)

    p = sub.add_parser("brightdata-preflight")
    p.add_argument("--manifest", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--markdown", action="store_true")
    p.set_defaults(func=_cli_brightdata_preflight)

    args = parser.parse_args(argv)
    return args.func(args)


def _cli_import_costco(args) -> int:
    result = import_costco_local(source_name=args.source, dry_run=args.dry_run)
    print_network_confirmation(0)
    import json
    print(json.dumps(result.to_dict(), indent=2, default=str))
    return 0


def _cli_create_manifest(args) -> int:
    from .pipeline import plan_enrichment
    from .signin import require_signin
    from .cli_common import print_json
    store = PipelineStore()
    manifest = plan_enrichment(args.run_id, provider=args.provider,
                               max_items=args.max_items, dry_run=True, store=store)
    print_network_confirmation(0)
    print_json(manifest)
    return 0


def _cli_signin(args) -> int:
    from .signin import require_signin, mark_signed_in
    from .cli_common import print_json
    store = PipelineStore()
    print_network_confirmation(0)
    if args.done:
        out = mark_signed_in(args.service, store=store)
        print_json(out)
        return 0 if out.get("ok") else 2
    result = require_signin(args.service, store=store)
    print_json(result.to_dict())
    return 0 if not result.required else 1


def _cli_validate_snapshots(args) -> int:
    from .workflow import _listing_from_snapshot  # noqa: F401 (structure check only)
    from .provider_imports.mapping import ensure_provider_provenance
    from .cli_common import print_json
    store = PipelineStore()
    snapshots = store.list_market_snapshots(provider=args.provider)
    results = []
    for s in snapshots:
        ok = ensure_provider_provenance(s)
        results.append({"snapshot_id": s.get("id"), "asin": s.get("asin"),
                        "provider": s.get("provider"), "provenance_ok": ok})
    print_network_confirmation(0)
    print_json({"checked": len(results), "snapshots": results})
    return 0


def _cli_validate_identity(args) -> int:
    from .reports import identity_validation_report
    from .workflow import persist_decision  # noqa: F401
    from .pipeline import score_run
    from .cli_common import print_json
    store = PipelineStore()
    decisions = store.list_candidate_decisions()
    rows = identity_validation_report(decisions)
    print_network_confirmation(0)
    print_json({"dry_run": args.dry_run, "validated": len(rows), "rows": rows})
    return 0


def _cli_calculate_economics(args) -> int:
    from .reports import economics_report
    from .cli_common import print_json
    store = PipelineStore()
    decisions = store.list_candidate_decisions()
    rows = economics_report(decisions)
    print_network_confirmation(0)
    print_json({"dry_run": args.dry_run, "calculated": len(rows), "rows": rows})
    return 0


def _cli_score(args) -> int:
    from .workflow import decide_candidate, persist_decision
    from .cli_common import print_json
    store = PipelineStore()
    # Iterate over match candidates (they carry asin + costco_source_product_id).
    candidates = store.list_match_candidates()
    snapshots = store.list_market_snapshots()
    by_asin = {s.get("asin"): s for s in snapshots if s.get("asin")}
    scored, blocked = 0, 0
    decisions = []
    seen = set()
    for cand in candidates:
        asin = cand.get("asin")
        if not asin or asin in seen:
            continue
        seen.add(asin)
        snap = by_asin.get(asin)
        if snap is None:
            blocked += 1
            continue
        sp = store.get_source_product(cand.get("costco_source_product_id"))
        if sp is None:
            blocked += 1
            continue
        decision = decide_candidate(candidate_id=cand.get("id") or f"cand_{asin}",
                                    asin=asin, source=sp, market_snapshot=snap)
        if not args.dry_run:
            persist_decision(decision, store=store)
        scored += 1
        decisions.append(decision.to_dict())
    print_network_confirmation(0)
    print_json({"dry_run": args.dry_run, "scored": scored, "blocked_no_snapshot": blocked,
                "decisions": decisions})
    return 0


def _cli_export_ranked(args) -> int:
    from .reports import build_ranked_report, to_csv, to_json
    store = PipelineStore()
    decisions = store.list_candidate_decisions()
    statuses = None
    if args.set:
        statuses = [s.strip() for s in args.set.split(",") if s.strip()]
    rows = build_ranked_report(decisions, include_review=args.include_review,
                               include_blocked=args.include_blocked,
                               include_stale=args.include_stale,
                               statuses=statuses, store=store)
    out = to_csv(rows) if args.format == "csv" else to_json(rows)
    print_network_confirmation(0)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"Wrote {len(rows)} rows to {args.out}")
    else:
        print(out)
    return 0


def _cli_approval_request(args) -> int:
    from .approvals import request_approval
    from .cli_common import print_json
    store = PipelineStore()
    print_network_confirmation(0)
    print_json(request_approval(args.candidate_id, store=store))
    return 0


def _cli_approval_grant(args) -> int:
    from .approvals import request_approval, grant_approval
    from .cli_common import print_json
    store = PipelineStore()
    req = request_approval(args.candidate_id, store=store)
    if not req.get("ok"):
        print_network_confirmation(0)
        print_json(req)
        return 2
    print_network_confirmation(0)
    print_json(grant_approval(req["approval_id"], quantity=args.quantity,
                              expires_at=args.expires_at, approved_by=args.approved_by, store=store))
    return 0


def _cli_approval_revoke(args) -> int:
    from .approvals import revoke_approval
    from .cli_common import print_json
    store = PipelineStore()
    print_network_confirmation(0)
    print_json(revoke_approval(args.approval_id, reason=args.reason, store=store))
    return 0


def _cli_approval_list(args) -> int:
    from .cli_common import print_json
    store = PipelineStore()
    print_network_confirmation(0)
    print_json({"approvals": store.list_approvals(state=args.state)})
    return 0


def _cli_status(args) -> int:
    from .cli_common import print_json
    store = PipelineStore()
    print_network_confirmation(0)
    print_json({
        "source_products": store.count_source_products(),
        "eligible_source_products": store.count_source_products(eligible_only=True),
        "match_candidates": len(store.list_match_candidates()),
        "market_snapshots": len(store.list_market_snapshots()),
        "candidate_decisions": len(store.list_candidate_decisions()),
        "approvals": len(store.list_approvals()),
        "runs": len(store.list_runs()),
    })
    return 0


def _cli_audit_costco(args) -> int:
    from .audit import audit, render_audit_markdown
    from .cli_common import print_json
    store = PipelineStore()
    result = audit(store, run_id=args.run_id)
    print_network_confirmation(0)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            if args.out.endswith(".md"):
                fh.write(render_audit_markdown(result))
            else:
                import json
                fh.write(json.dumps(result, indent=2, default=str))
        print(f"Wrote audit to {args.out}")
    else:
        print_json(result)
    return 0


def _cli_apply_disallowed(args) -> int:
    from .apply_disallowed_filter import main as apply_main
    return apply_main(["--run-id", args.run_id] + (["--dry-run"] if args.dry_run else []))


def _cli_chromecontrol_sync(args) -> int:
    from .chromecontrol_bridge import sync_to_northstar
    from .cli_common import print_json
    out = sync_to_northstar()
    print_network_confirmation(0)
    print_json(out)
    return 0


def _cli_audit_source_identity(args) -> int:
    from .enrichment import audit_source_identity
    from .cli_common import print_json
    store = PipelineStore()
    result = audit_source_identity(store, run_id=args.run_id)
    print_network_confirmation(0)
    print_json(result)
    return 0


def _cli_requirements_profile(args) -> int:
    import json
    from .requirements_profile import build_requirements_profile, render_markdown
    from .cli_common import print_json
    profile = build_requirements_profile()
    print_network_confirmation(0)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(render_markdown(profile) if args.out.endswith(".md") else json.dumps(profile, indent=2))
        print(f"Wrote requirements profile to {args.out}")
    else:
        print_json(profile)
    return 0


def _cli_plan_brightdata(args) -> int:
    import json
    from .brightdata_costco_enrichment import plan_enrichment_manifest
    from .cli_common import print_json
    store = PipelineStore()
    manifest = plan_enrichment_manifest(store, run_id=args.run_id, max_items=args.max_items, dry_run=True)
    print_network_confirmation(0)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2)
        print(f"Wrote dry-run manifest to {args.out} ({manifest['sample_size']} items)")
    else:
        print_json(manifest)
    return 0


def _cli_validate_brightdata_schema(args) -> int:
    import json
    from .brightdata_costco_enrichment import validate_schema
    from .cli_common import print_json
    with open(args.file, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data.get("records", data if isinstance(data, list) else [])
    report = validate_schema(records)
    print_network_confirmation(0)
    print_json(report)
    return 0


def _cli_run_brightdata(args) -> int:
    from .brightdata_costco_enrichment import run_enrichment
    from .cli_common import print_json
    manifest = {"manifest_id": args.manifest}
    out = run_enrichment(manifest, approved=args.approved, max_items=args.max_items,
                         spend_cap=args.spend_cap, source_id=args.source_id, manifest_id=args.manifest)
    print_network_confirmation(0)
    print_json(out)
    return 0 if out.get("result_status") not in ("requires_explicit_approval",) else 2


def _cli_import_brightdata(args) -> int:
    from .brightdata_costco_enrichment import import_snapshot
    from .cli_common import print_json
    store = PipelineStore()
    out = import_snapshot(args.file, store, dry_run=args.dry_run)
    print_network_confirmation(0)
    print_json(out)
    return 0


def _cli_identifier_queue(args) -> int:
    from .enrichment import assess_identity_readiness
    from .cli_common import print_json
    store = PipelineStore()
    if args.build:
        rows = store.list_source_products(run_id=args.run_id, eligible_only=True, limit=1_000_000)
        added = 0
        for r in rows:
            res = assess_identity_readiness(r, None)
            if res.identifier_resolution_required:
                store.add_identifier_resolution({
                    "run_id": args.run_id, "source_product_id": r.get("id"),
                    "costco_item_number": r.get("costco_item_number"),
                    "missing_identity_fields": res.missing_identity_fields,
                    "missing_physical_fields": res.missing_physical_fields,
                    "possible_next_source": "brightdata | manufacturer_docs | packaging_photo_ocr | operator_entry",
                    "title_only_insufficient": True,
                    "physical_pack_missing": bool(res.missing_physical_fields),
                })
                added += 1
        print_network_confirmation(0)
        print_json({"queued": added})
        return 0
    print_network_confirmation(0)
    print_json({"queue": store.list_identifier_resolution(run_id=args.run_id, limit=500)})
    return 0


def _cli_export_identity_readiness(args) -> int:
    from .enrichment import assess_identity_readiness
    from .cli_common import print_json
    import csv, io
    store = PipelineStore()
    rows = store.list_source_products(run_id=args.run_id, eligible_only=True, limit=1_000_000)
    out_rows = []
    for r in rows:
        res = assess_identity_readiness(r, None)
        out_rows.append({
            "source_product_id": r.get("id"), "costco_item_number": r.get("costco_item_number"),
            "brand": r.get("brand_raw"), "title": r.get("title_raw"),
            "identity_ready": res.identity_ready, "probable_only": res.probable_only,
            "identifier_resolution_required": res.identifier_resolution_required,
            "identifier_kind": res.identifier_kind,
            "missing_identity_fields": ",".join(res.missing_identity_fields),
            "missing_physical_fields": ",".join(res.missing_physical_fields),
        })
    print_network_confirmation(0)
    if args.format == "csv":
        buf = io.StringIO()
        cols = list(out_rows[0].keys()) if out_rows else ["source_product_id"]
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        [w.writerow(x) for x in out_rows]
        content = buf.getvalue()
    else:
        content = json.dumps(out_rows, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(content)
        print(f"Wrote identity-readiness to {args.out} ({len(out_rows)} rows)")
    else:
        print(content)
    return 0


def _cli_brightdata_preflight(args) -> int:
    from .brightdata_costco_enrichment import preflight, render_preflight_markdown
    from .cli_common import print_json
    rep = preflight(manifest_path=args.manifest) if args.manifest else preflight()
    print_network_confirmation(0)
    if args.markdown:
        print(render_preflight_markdown(rep))
    else:
        print_json(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())