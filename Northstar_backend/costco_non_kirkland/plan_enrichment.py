"""Generate an enrichment manifest (dry-run by default; no provider action).

Usage:
    python -m costco_non_kirkland.plan_enrichment --run-id <run-id> --source selleramp --max-items 20 --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import plan_enrichment


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--run-id" not in argv:
        print("error: missing --run-id", file=sys.stderr)
        return 2
    run_id = argv[argv.index("--run-id") + 1]
    provider = "selleramp"
    if "--source" in argv:
        provider = argv[argv.index("--source") + 1]
    max_items = 20
    if "--max-items" in argv:
        max_items = int(argv[argv.index("--max-items") + 1])
    spend_cap = None
    if "--spend-cap" in argv:
        spend_cap = float(argv[argv.index("--spend-cap") + 1])
    dry_run = "--dry-run" in argv
    out = plan_enrichment(run_id, provider=provider, max_items=max_items,
                          spend_cap=spend_cap, dry_run=dry_run)
    print_network_confirmation(0)
    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())