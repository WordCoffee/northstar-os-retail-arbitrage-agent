"""Offline competition report CLI (read-only on all data files).

Summarizes the seller-competition picture from the local Easyparser
market snapshot store using the exact same analytics the Scout renders
(competition_analytics). Writes a JSON report ONLY to the explicitly
supplied --output path.

Rules of honesty:
  - Zero seller counts appear only under explicit complete zero-offer
    evidence; every other empty/partial/failed/unavailable roster is
    Unknown with a roster reason.
  - Seller-share values stay Unknown here: market snapshots do not
    carry a monthly sales estimate, so no denominator is ever assumed.
  - Writes go only to --output; the snapshot store and every other
    data file are never modified.

Usage:
  python competition_report.py --input data/amazon-market-snapshots.json --output data/batch/competition-report.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

import competition_analytics
import market_snapshot_store

load_dotenv()

DISCLAIMER = (
    "Observed-seller competition only. Unknown rosters are never shown "
    "as zero sellers; seller-share is Unknown because snapshots carry "
    "no monthly sales estimate."
)


def build_report(snapshots: Dict[str, Dict]) -> Dict:
    results: List[Dict] = []
    by_status: Dict[str, int] = {}
    roster_states: Dict[str, int] = {}
    for asin, snap in sorted(snapshots.items()):
        fields = competition_analytics.competition_fields(snap)
        status = snap.get("data_status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        observed = fields.get("observed_total_sellers")
        if observed is None:
            state = "unknown_roster"
        elif observed == 0:
            state = "explicit_zero"
        else:
            state = "observed_rows"
        roster_states[state] = roster_states.get(state, 0) + 1
        results.append(
            {
                "asin": asin,
                "title": snap.get("title"),
                "data_status": status,
                "observed_total_sellers": fields.get("observed_total_sellers"),
                "observed_fba_sellers": fields.get("observed_fba_sellers"),
                "observed_fbm_sellers": fields.get("observed_fbm_sellers"),
                "observed_amazon_sellers": fields.get("observed_amazon_sellers"),
                "claimed_offer_count": fields.get("claimed_offer_count"),
                "offers_returned": fields.get("offers_returned"),
                "offers_complete": fields.get("offers_complete"),
                "offer_roster_reason": fields.get("offer_roster_reason"),
                "observed_buy_box_available": fields.get("observed_buy_box_available"),
                "observed_buy_box_price": fields.get("observed_buy_box_price"),
                "observed_buy_box_landed_price": fields.get("observed_buy_box_landed_price"),
                "observed_buy_box_seller": fields.get("observed_buy_box_seller"),
                "observed_buy_box_fulfillment": fields.get("observed_buy_box_fulfillment"),
                "lowest_returned_offer_price": fields.get("lowest_returned_offer_price"),
                "lowest_returned_landed_price": fields.get("lowest_returned_landed_price"),
                "highest_returned_landed_price": fields.get("highest_returned_landed_price"),
                "returned_offer_price_spread": fields.get("returned_offer_price_spread"),
                "prime_offer_count": fields.get("prime_offer_count"),
                "fulfilled_by_amazon_offer_count": fields.get("fulfilled_by_amazon_offer_count"),
                "seller_share_confidence": fields.get("seller_share_confidence"),
                "offer_competition_note": fields.get("offer_competition_note"),
            }
        )

    reasons: Dict[str, int] = {}
    for r in results:
        if r.get("offer_roster_reason"):
            reasons[r["offer_roster_reason"]] = reasons.get(r["offer_roster_reason"], 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_count": len(results),
        "summary": {
            "by_data_status": dict(sorted(by_status.items())),
            "roster_states": dict(sorted(roster_states.items())),
            "roster_reasons": dict(sorted(reasons.items())),
        },
        "results": results,
        "disclaimer": DISCLAIMER,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Offline seller-competition report")
    parser.add_argument("--input", help="market snapshot store JSON (default: SCANNER_MARKET_SNAPSHOT_PATH)")
    parser.add_argument("--output", required=True, help="JSON report output path")
    args = parser.parse_args(argv)

    if args.input:
        os.environ["SCANNER_MARKET_SNAPSHOT_PATH"] = args.input
    snapshots = market_snapshot_store.load_snapshots()
    if not snapshots:
        print("No snapshots found at %s" % (args.input or "SCANNER_MARKET_SNAPSHOT_PATH"))
        return 1
    report = build_report(snapshots)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
    print(
        "Wrote competition report for %d snapshots to %s"
        % (len(snapshots), args.output)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())