"""Offline portfolio report CLI (read-only on all data files).

Runs the exact cache-only scanner pipeline used by the Scout
(SCANNER_OFFER_ENRICHMENT=OFF + SCANNER_LOCAL_SNAPSHOT_MERGE=1, both
forced in-process; zero network possible) and aggregates the portfolio
planning fields (readiness, next step, category recommendation, risk
flags, estimated monthly revenue and profit pools) into a JSON report.
Writes ONLY to the explicitly supplied --output path.

Rules of honesty:
  - Pool/revenue sums are computed only over rows that actually carry
    the value, and the contributing row count is reported beside every
    sum. Unknown rows never contribute 0 to a total.
  - Unknown seller data never improves readiness, category, or score.
  - The cache, snapshot store, Costco data and run reports are never
    written, moved, or deleted.

Usage:
  python portfolio_report.py --input data/scanner-search-cache.json --output data/batch/portfolio-report.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import amazon_search
import portfolio_analytics
import product_analysis

MODELED_DISCLAIMER = portfolio_analytics.MODELED_DISCLAIMER


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _sum_field(rows: List[Dict], key: str) -> Dict:
    values = [r[key] for r in rows if _number(r.get(key))]
    return {
        "sum": round(sum(values), 2) if values else None,
        "rows_with_value": len(values),
    }


def build_report(analysis: Dict) -> Dict:
    rows = list(analysis.get("all_results") or [])
    by_readiness: Dict[str, int] = {}
    by_category: Dict[str, int] = {}
    risk_counts: Dict[str, int] = {}
    for r in rows:
        readiness = r.get("portfolio_readiness") or "unknown"
        by_readiness[readiness] = by_readiness.get(readiness, 0) + 1
        category = r.get("portfolio_category") or "unknown"
        by_category[category] = by_category.get(category, 0) + 1
        for flag in r.get("risk_flags") or []:
            risk_counts[flag] = risk_counts.get(flag, 0) + 1

    results: List[Dict] = []
    for r in rows:
        results.append(
            {
                "asin": r.get("asin"),
                "title": r.get("name"),
                "portfolio_readiness": r.get("portfolio_readiness"),
                "portfolio_next_step": r.get("portfolio_next_step"),
                "portfolio_category": r.get("portfolio_category"),
                "risk_flags": r.get("risk_flags") or [],
                "total_completeness_score": r.get("total_completeness_score"),
                "opportunity_score": r.get("opportunity_score"),
                "estimated_monthly_sales": r.get("estimated_monthly_sales"),
                "estimated_monthly_revenue": r.get("estimated_monthly_revenue"),
                "monthly_revenue_basis": r.get("monthly_revenue_basis"),
                "estimated_monthly_profit_pool": r.get("estimated_monthly_profit_pool"),
                "estimated_fba_seller_monthly_profit": r.get("estimated_fba_seller_monthly_profit"),
                "estimated_fbm_seller_monthly_profit": r.get("estimated_fbm_seller_monthly_profit"),
                "estimated_observed_seller_monthly_profit": r.get("estimated_observed_seller_monthly_profit"),
                "seller_share_confidence": r.get("seller_share_confidence"),
                "seller_share_basis": r.get("seller_share_basis"),
            }
        )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "row_count": len(rows),
        "summary": {
            "by_readiness": dict(sorted(by_readiness.items())),
            "by_category": dict(sorted(by_category.items())),
            "risk_flag_counts": dict(sorted(risk_counts.items())),
            "estimated_monthly_revenue": _sum_field(rows, "estimated_monthly_revenue"),
            "estimated_monthly_profit_pool": _sum_field(rows, "estimated_monthly_profit_pool"),
            "estimated_fba_seller_monthly_profit": _sum_field(rows, "estimated_fba_seller_monthly_profit"),
            "estimated_fbm_seller_monthly_profit": _sum_field(rows, "estimated_fbm_seller_monthly_profit"),
            "estimated_observed_seller_monthly_profit": _sum_field(rows, "estimated_observed_seller_monthly_profit"),
        },
        "results": results,
        "disclaimer": MODELED_DISCLAIMER,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline portfolio planning report")
    parser.add_argument("--input", help="candidate cache JSON (default: SCANNER_SEARCH_CACHE_PATH)")
    parser.add_argument("--output", required=True, help="JSON report output path")
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
    report = build_report(analysis)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(
        "Wrote portfolio report for %d rows to %s"
        % (len(report["results"]), args.output)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())