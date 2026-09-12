"""Offline demand report CLI (read-only on all data files).

Estimates monthly demand for every cached candidate using the same
offline demand model the Scout uses (demand_estimator), driven only by
candidate-record signals (provider monthly-sales estimate, BSR, and the
listing's own category when present). Writes a JSON report ONLY to the
explicitly supplied --output path.

Rules of honesty:
  - Never estimates from price, title, reviews, seller counts, Costco
    cost, weight, or an assumed category. Missing signals -> Unknown.
  - Writes go only to --output; the cache, snapshots, Costco data and
    run reports are never modified.

Usage:
  python demand_report.py --input data/scanner-search-cache.json --output data/batch/demand-report.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import amazon_search
import demand_estimator

load_dotenv()

DISCLAIMER = (
    "Estimated from listing-published or provider signals and the BSR/"
    "category calibration model; ranges reflect confidence. Not a "
    "forecast."
)


def build_report(candidates: List[Dict], input_path: str) -> Dict:
    meta = amazon_search.cache_meta() or {}
    observed_at = meta.get("fetched_at")
    results: List[Dict] = []
    for c in candidates:
        estimate = demand_estimator.estimate_demand(
            listing_bought_past_month=c.get("listing_bought_past_month"),
            provider_monthly_sales_estimate=c.get("monthly_sales_estimate"),
            bsr=c.get("sales_rank"),
            bsr_category=c.get("amazon_category"),
            bsr_observed_at=observed_at,
        )
        results.append(
            {
                "asin": c.get("asin"),
                "title": c.get("name"),
                "provider_monthly_sales_estimate": c.get("monthly_sales_estimate"),
                "bsr": estimate["bsr"],
                "bsr_category": estimate["bsr_category"],
                "estimated_monthly_sales": estimate["estimated_monthly_sales"],
                "sales_estimate_low": estimate["sales_estimate_low"],
                "sales_estimate_high": estimate["sales_estimate_high"],
                "sales_estimation_method": estimate["sales_estimation_method"],
                "sales_estimation_source": estimate["sales_estimation_source"],
                "sales_estimation_confidence": estimate["sales_estimation_confidence"],
                "monthly_sales_estimated": estimate["monthly_sales_estimated"],
                "calibration_model_name": estimate["calibration_model_name"],
                "calibration_model_version": estimate["calibration_model_version"],
            }
        )

    by_confidence: Dict[str, int] = {}
    by_method: Dict[str, int] = {}
    estimated = 0
    unknown = 0
    for r in results:
        confidence = r["sales_estimation_confidence"]
        by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        by_method[r["sales_estimation_method"]] = by_method.get(r["sales_estimation_method"], 0) + 1
        if r["estimated_monthly_sales"] is not None:
            estimated += 1
        else:
            unknown += 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": input_path,
        "model": {
            "name": demand_estimator.CALIBRATION_MODEL_NAME,
            "version": demand_estimator.CALIBRATION_MODEL_VERSION,
            "supported_categories": list(demand_estimator.SUPPORTED_CATEGORIES),
            "confidence_ranges": demand_estimator.CONFIDENCE_RANGES,
        },
        "candidate_count": len(results),
        "summary": {
            "estimated": estimated,
            "unknown": unknown,
            "by_confidence": dict(sorted(by_confidence.items())),
            "by_method": dict(sorted(by_method.items())),
        },
        "results": results,
        "disclaimer": DISCLAIMER,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline demand report")
    parser.add_argument("--input", help="candidate cache JSON (default: SCANNER_SEARCH_CACHE_PATH)")
    parser.add_argument("--output", required=True, help="JSON report output path")
    args = parser.parse_args(argv)

    if args.input:
        os.environ["SCANNER_SEARCH_CACHE_PATH"] = args.input
    candidates = amazon_search.load_cached_candidates()
    if not candidates:
        print("No cached candidates found at %s" % (args.input or "SCANNER_SEARCH_CACHE_PATH"))
        return 1
    report = build_report(candidates, args.input or os.environ.get("SCANNER_SEARCH_CACHE_PATH", ""))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(
        "Wrote demand report for %d candidates to %s (estimated=%d, unknown=%d)"
        % (len(candidates), args.output, report["summary"]["estimated"], report["summary"]["unknown"])
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())