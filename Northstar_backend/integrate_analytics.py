"""Offline integration: feed DataForSEO enrichment_results_v2 into the
analytics pipeline (fee_engine + demand + competition + portfolio) with NO
live calls. Builds the two input files the CLIs expect, then runs them.

Run:  python integrate_analytics.py
(No NS_ALLOW_NETWORK needed; the CLIs force SCANNER_OFFER_ENRICHMENT=OFF +
SCANNER_LOCAL_SNAPSHOT_MERGE=1, and Costco cost is absent offline -> economics
are honestly flagged 'unavailable'.)
"""

import json
import os
from datetime import datetime, timezone

import market_snapshot_store

BACKEND = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(BACKEND, "data", "catalog")
V2 = os.path.join(CATALOG, "enrichment_results_v2_20260825T065610Z.json")

CANDIDATES_PATH = os.path.join(CATALOG, "analytics-candidates.json")
SNAPSHOTS_PATH = os.path.join(CATALOG, "analytics-snapshots.json")

# demand_estimator only supports these 6 BSR curves (exact match required).
SUPPORTED_CATEGORIES = {
    "Home & Kitchen", "Beauty & Personal Care", "Health & Household",
    "Toys & Games", "Electronics", "Books",
}


def _clean_category(cat):
    if not cat:
        return None
    base = str(cat).split("(")[0].strip()
    return base or None


def build_inputs():
    with open(V2, "r", encoding="utf-8") as f:
        v2 = json.load(f)
    recs = v2["results"]

    products = []
    snapshot_asins = {}
    now = datetime.now(timezone.utc).isoformat()

    for rec in recs:
        asin = rec["asin"]
        cat = _clean_category((rec.get("bsr") or {}).get("bsr_primary_category"))
        sales_rank = (rec.get("bsr") or {}).get("bsr_primary_rank")
        offers = rec.get("offers") or []
        fba = sum(1 for o in offers if o.get("is_fba") is True)
        fbm = sum(1 for o in offers if o.get("is_fbm") is True)
        amazon = sum(1 for o in offers if o.get("seller_name") == "Amazon")
        returned = rec.get("offers_returned_count") or 0

        # ---- candidate cache product (product_analysis reads these) ----
        products.append({
            "name": "%s :: %s" % (rec.get("source_query") or "kirkland", asin),
            "asin": asin,
            "product_url": "https://www.amazon.com/dp/%s" % asin,
            "amazon_price": rec.get("discovery_price"),
            "sales_rank": sales_rank,
            "amazon_category": cat,
            "monthly_sales_estimate": None,
            "monthly_sales_estimated": False,
            "upc": None, "ean": None, "brand": None,
            "imported_at": now,
            "observed_at": now,
        })

        # ---- snapshot store record (via build_snapshot) ----
        result = {
            "title": rec.get("source_query") or asin,
            "source": "dataforseo",
            "observed_at": now,
            "offers": offers,
            "offer_count": returned,
            "offers_returned_count": returned,
            "buy_box_price": rec.get("buy_box_price"),
            "buy_box_seller": rec.get("buy_box_seller"),
            "observed_fba_offer_count": fba,
            "observed_fbm_offer_count": fbm,
            "observed_amazon_offer_count": amazon,
            "data_gaps": [],
            "credits_used": rec.get("credits_used"),
            "credits_remaining": None,
        }
        snap = market_snapshot_store.build_snapshot(asin, result)
        snapshot_asins[asin] = snap

    candidates = {
        "schema_version": 1,
        "fetched_at": now,
        "source": "dataforseo",
        "search_terms": ["kirkland"],
        "candidate_count": len(products),
        "products": products,
    }
    snapshots = {
        "schema_version": 1,
        "generated_at": now,
        "asins": snapshot_asins,
    }
    with open(CANDIDATES_PATH, "w", encoding="utf-8") as f:
        json.dump(candidates, f, indent=2, default=str)
    with open(SNAPSHOTS_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2, default=str)
    print("Wrote candidates: %s (%d products)" % (CANDIDATES_PATH, len(products)))
    print("Wrote snapshots:  %s (%d ASINs)" % (SNAPSHOTS_PATH, len(snapshot_asins)))
    return CANDIDATES_PATH, SNAPSHOTS_PATH


def run_analytics(candidates_path, snapshots_path):
    import opportunity_export
    import portfolio_report
    import demand_report
    import competition_report

    # Snapshot store is read by analyze_kirkland_products() via this env var.
    os.environ["SCANNER_MARKET_SNAPSHOT_PATH"] = snapshots_path

    opp_csv = os.path.join(CATALOG, "analytics-top-opportunities.csv")
    port_json = os.path.join(CATALOG, "analytics-portfolio.json")
    dem_json = os.path.join(CATALOG, "analytics-demand.json")
    comp_json = os.path.join(CATALOG, "analytics-competition.json")

    print("\n--- opportunity_export (scored CSV) ---")
    opportunity_export.main(["--input", candidates_path,
                             "--output", opp_csv, "--top", "50"])
    print("\n--- portfolio_report ---")
    portfolio_report.main(["--input", candidates_path, "--output", port_json])
    print("\n--- demand_report ---")
    demand_report.main(["--input", candidates_path, "--output", dem_json])
    print("\n--- competition_report ---")
    competition_report.main(["--input", snapshots_path, "--output", comp_json])

    return opp_csv, port_json, dem_json, comp_json


def main():
    candidates_path, snapshots_path = build_inputs()
    run_analytics(candidates_path, snapshots_path)
    print("\n=== INTEGRATION COMPLETE (offline, no live calls) ===")


if __name__ == "__main__":
    main()
