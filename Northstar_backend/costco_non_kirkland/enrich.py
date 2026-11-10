"""Execute enrichment ONLY after explicit operator approval.

Usage:
    python -m costco_non_kirkland.enrich --manifest <manifest.json> --approved --max-items 20 --spend-cap 50 --mock

Fail-closed: without --approved AND the NORTHSTAR_ENRICHMENT_APPROVED env flag, no
provider action executes. `--mock` uses fixture data (no provider calls).
"""
from __future__ import annotations

import os
import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import enrich, ENRICHMENT_APPROVAL_ENV
from .providers import ProviderNotConfigured


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--manifest" not in argv:
        print("error: missing --manifest", file=sys.stderr)
        return 2
    manifest_id = argv[argv.index("--manifest") + 1]
    approved = "--approved" in argv
    mock = "--mock" in argv
    max_items = 0
    if "--max-items" in argv:
        max_items = int(argv[argv.index("--max-items") + 1])
    spend_cap = None
    if "--spend-cap" in argv:
        spend_cap = float(argv[argv.index("--spend-cap") + 1])

    if not approved:
        print("error: this command requires --approved (explicit operator approval).", file=sys.stderr)
        print(f"Also requires {ENRICHMENT_APPROVAL_ENV}=1 in the environment.", file=sys.stderr)
        print("No provider action was executed.", file=sys.stderr)
        return 2

    if (os.getenv(ENRICHMENT_APPROVAL_ENV) or "").strip().lower() not in ("1", "true", "yes", "on"):
        print(f"error: {ENRICHMENT_APPROVAL_ENV} is not set to an explicit opt-in.", file=sys.stderr)
        print("No provider action was executed.", file=sys.stderr)
        return 2

    out = enrich(manifest_id, approved=approved, max_items=max_items,
                 spend_cap=spend_cap, mock=mock)
    print_network_confirmation(0)
    print_json(out)
    return 0 if out.get("approved") else 2


if __name__ == "__main__":
    sys.exit(main())