"""Build offline Amazon match queue for a run.

Usage:
    python -m costco_non_kirkland.match_costco_to_amazon --run-id <run-id> --offline-only --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import build_match_queue


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--run-id" not in argv:
        print("error: missing --run-id", file=sys.stderr)
        return 2
    run_id = argv[argv.index("--run-id") + 1]
    dry_run = "--dry-run" in argv
    if "--offline-only" not in argv:
        # Default is offline-only; no live lookups are ever performed here.
        pass
    out = build_match_queue(run_id, dry_run=dry_run)
    print_network_confirmation(0)
    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())