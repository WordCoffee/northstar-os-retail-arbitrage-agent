"""Top-opportunity export CLI (offline, read-only on all data files).

Runs the exact cache-only scanner pipeline used by the Scout
(SCANNER_OFFER_ENRICHMENT=OFF + SCANNER_LOCAL_SNAPSHOT_MERGE=1, both
forced in-process; zero network possible) and exports the top-N
opportunities by opportunity_score as CSV.

Rules of honesty:
  - Writes go ONLY to the explicitly supplied --output path. The
    search cache, snapshot store, Costco catalogs and run reports are
    never written, moved, or deleted.
  - Unknown rows (no score) sort after every scored row — they never
    rank above a complete positive.
  - "est."-style provenance travels with every modeled value; nothing
    is fabricated.

Usage:
  python opportunity_export.py --input data/scanner-search-cache.json --output data/batch/top-opportunities.csv --top 50
"""

import argparse
import csv
import os
import sys
from typing import Any, Dict, List, Optional

import amazon_search
import product_analysis

EXPORT_COLUMNS = [
    "rank",
    "opportunity_score",
    "portfolio_readiness",
    "portfolio_category",
    "portfolio_next_step",
    "risk_flags",
    "portfolio_score_reasons",
    "asin",
    "name",
    "product_url",
    "amazon_price",
    "costco_cost",
    "costco_cost_basis",
    "pack_match",
    "economics_confidence",
    "economics_status",
    "net_profit",
    "roi_pct",
    "fba_fee",
    "monthly_sales_estimate",
    "estimated_monthly_sales",
    "sales_estimate_low",
    "sales_estimate_high",
    "sales_estimation_method",
    "sales_estimation_source",
    "sales_estimation_confidence",
    "estimated_monthly_revenue",
    "monthly_revenue_basis",
    "estimated_monthly_profit_pool",
    "estimated_units_per_observed_seller",
    "observed_total_sellers",
    "observed_fba_sellers",
    "observed_fbm_sellers",
    "observed_amazon_sellers",
    "offer_roster_reason",
    "snapshot_freshness",
    "snapshot_offers_complete",
    "verification_tasks",
    "total_completeness_score",
]


def _cell(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    return value


def export_rows(analysis: Dict, top: int) -> List[Dict]:
    rows = list(analysis.get("all_results") or [])
    rows.sort(
        key=lambda r: (
            0 if isinstance(r.get("opportunity_score"), (int, float)) and not isinstance(r.get("opportunity_score"), bool) else 1,
            -r["opportunity_score"] if isinstance(r["opportunity_score"], (int, float)) and not isinstance(r["opportunity_score"], bool) else 0,
        )
    )
    selected = rows[:top]
    out: List[Dict] = []
    for i, r in enumerate(selected, start=1):
        row = {"rank": i}
        for key in EXPORT_COLUMNS[1:]:
            row[key] = _cell(r.get(key))
        out.append(row)
    return out


def write_export_csv(rows: List[Dict], output_path: str) -> int:
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Top-opportunity CSV export (offline)")
    parser.add_argument("--input", help="candidate cache JSON (default: SCANNER_SEARCH_CACHE_PATH)")
    parser.add_argument("--output", required=True, help="CSV output path")
    parser.add_argument("--top", type=int, default=50, help="max rows to export (default 50)")
    args = parser.parse_args(argv)

    os.environ["SCANNER_OFFER_ENRICHMENT"] = "OFF"
    os.environ["SCANNER_LOCAL_SNAPSHOT_MERGE"] = "1"
    if args.input:
        os.environ["SCANNER_SEARCH_CACHE_PATH"] = args.input
    candidates = amazon_search.load_cached_candidates()
    if not candidates:
        print("No cached candidates found at %s" % (args.input or "SCANNER_SEARCH_CACHE_PATH"))
        return 1

    analysis = product_analysis.analyze_kirkland_products()
    rows = export_rows(analysis, max(1, args.top))
    count = write_export_csv(rows, args.output)
    print("Wrote %d opportunity rows to %s" % (count, args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())