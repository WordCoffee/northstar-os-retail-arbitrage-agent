"""Apply the disallowed product-class filter to a run (offline, marks-not-deletes).

Usage:
    python -m costco_non_kirkland.apply_disallowed_filter --run-id <run-id> --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .store import PipelineStore
from .disallowed import audit_disallowed, evaluate_disallowed


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--run-id" not in argv:
        print("error: missing --run-id", file=sys.stderr)
        return 2
    run_id = argv[argv.index("--run-id") + 1]
    dry_run = "--dry-run" in argv

    store = PipelineStore()
    records = store.list_source_products(run_id=run_id, limit=1_000_000)
    audit = audit_disallowed(records)
    out = {"run_id": run_id, "dry_run": dry_run, "audit": audit.to_dict()}
    if not dry_run:
        for rec in records:
            res = evaluate_disallowed(rec)
            marked = res.to_record(rec)
            # Kirkland reason takes precedence in reporting.
            if marked.get("exclusion_reason") == "disallowed_product_class" and \
               rec.get("exclusion_reason") == "kirkland_signature_out_of_scope":
                marked["exclusion_reason"] = "kirkland_signature_out_of_scope"
            store.upsert_source_product(marked, run_id=run_id)
    print_network_confirmation(0)
    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
