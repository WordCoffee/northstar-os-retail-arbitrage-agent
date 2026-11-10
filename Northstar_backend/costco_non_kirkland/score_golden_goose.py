"""Score eligible non-Kirkland candidates with Golden Goose.

Usage:
    python -m costco_non_kirkland.score_golden_goose --run-id <run-id> --score-version v1 --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import score_run


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--run-id" not in argv:
        print("error: missing --run-id", file=sys.stderr)
        return 2
    run_id = argv[argv.index("--run-id") + 1]
    dry_run = "--dry-run" in argv
    out = score_run(run_id, dry_run=dry_run)
    print_network_confirmation(0)
    print_json(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())