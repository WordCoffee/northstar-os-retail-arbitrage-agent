"""Stock runner — pour live free-tier data into the warehouse (Phase A / A3).

Runs a set of seed queries through the free-tier router and upserts the results
into ProductsDB, recording every pull in ``live_pulls``. Offline by default;
``--live`` fires real (free-tier) calls and requires the §3 envelope
(``GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1``).

Usage:
    python stock_runner.py --live                 # seed queries, live
    python stock_runner.py --query "gift for mom" --live
    python stock_runner.py --wholesale "coffee" --live
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Seed queries for the first stock pass (broad, category-spread).
SEED_QUERIES = [
    "coffee beans",
    "kitchen gadgets",
    "home organization",
    "supplements",
    "pet supplies",
]


def _run_amazon(queries, live, ttl_seconds=None):
    import live_catalog
    out = []
    for q in queries:
        kwargs = {"live": live}
        if ttl_seconds is not None:
            kwargs["ttl_seconds"] = ttl_seconds
        result = live_catalog.stock(q, **kwargs)
        out.append({"query": q, **result})
    return out


def _run_wholesale(query, live):
    import wholesale_catalog
    return wholesale_catalog.stock_wholesale(query, live=live)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Stock live data into the warehouse")
    parser.add_argument("--query", action="append", default=[], help="Amazon search query (repeatable)")
    parser.add_argument("--wholesale", metavar="QUERY", help="Stock a wholesaler catalog (Tundra)")
    parser.add_argument("--live", action="store_true", help="Fire real free-tier calls (§3 gated)")
    parser.add_argument("--ttl-seconds", type=int, default=None, help="Freshness window for stocked rows")
    args = parser.parse_args(argv)

    queries = args.query or SEED_QUERIES
    report = {"live": bool(args.live), "amazon": [], "wholesale": None}

    report["amazon"] = _run_amazon(queries, args.live, args.ttl_seconds)
    if args.wholesale:
        report["wholesale"] = _run_wholesale(args.wholesale, args.live)

    stocked = sum(r.get("stocked", 0) for r in report["amazon"])
    report["total_stocked"] = stocked
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
