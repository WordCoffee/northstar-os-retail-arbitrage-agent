"""Discover local Costco data sources (offline, dry-run friendly).

Usage:
    python -m costco_non_kirkland.discover_costco_sources --dry-run
"""
from __future__ import annotations

import sys
from .cli_common import print_json, print_network_confirmation
from .sources import discover_summary


def main(argv=None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    summary = discover_summary()
    print_network_confirmation(0)
    print_json(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())