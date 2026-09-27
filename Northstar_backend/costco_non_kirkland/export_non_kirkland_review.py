"""Export the non-Kirkland review queue.

Usage:
    python -m costco_non_kirkland.export_non_kirkland_review --run-id <run-id> --format csv
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import export_review


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if "--run-id" not in argv:
        print("error: missing --run-id", file=sys.stderr)
        return 2
    run_id = argv[argv.index("--run-id") + 1]
    fmt = "csv"
    if "--format" in argv:
        fmt = argv[argv.index("--format") + 1]
    out = export_review(run_id, fmt=fmt)
    print_network_confirmation(0)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())