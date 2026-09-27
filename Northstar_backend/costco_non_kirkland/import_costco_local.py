"""Import local Costco records into the canonical DB (offline).

Usage:
    python -m costco_non_kirkland.import_costco_local --source costco-discovery-catalog.json --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .pipeline import import_costco_local


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    source_name = None
    dry_run = "--dry-run" in argv
    if "--source" in argv:
        source_name = argv[argv.index("--source") + 1]
    result = import_costco_local(source_name=source_name, dry_run=dry_run)
    print_network_confirmation(0)
    print_json(result.to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())