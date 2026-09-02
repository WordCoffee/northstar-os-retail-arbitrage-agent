"""Run the approved bounded Layer 1 Kirkland discovery (Real-Time only).

Usage: $env:NS_ALLOW_NETWORK="1"; python run_discovery_layer1.py
Never prints the API key. Honors the 40-request hard cap internally.
"""

import json

import kirkland_discovery as kd


def main():
    # kirkland_discovery now calls load_dotenv(); earlier discovery runs made
    # 0 live requests (host/key were None before the fix). This turn therefore
    # starts at 0 against the hard 40-request cap.
    PRIOR_SPENT = 0
    result = kd.run_layer1_discovery(
        max_queries=5, max_pages=8, max_requests=40, country="US")
    manifest = result["manifest"]
    seen = {r["asin"]: r for r in manifest["asins"]}

    print("=== TASK A/B: LAYER 1 DISCOVERY (Real-Time Amazon Data) ===")
    print("Total unique Kirkland-verified ASINs : %d" % result["seen_count"])
    print("Rejected (non-Kirkland) count        : %d" % result["rejected_count"])
    by_query = {}
    for r in manifest["asins"]:
        by_query.setdefault(r["source_query"], 0)
        by_query[r["source_query"]] += 1
    print("Breakdown by source query:")
    for q, n in by_query.items():
        print("  - %-45s %d" % (q, n))

    print("\n=== TASK B: MANIFEST ===")
    print("Manifest path : %s" % result["path"])
    print("Row count     : %d" % manifest["count"])
    print("Frozen        : %s" % manifest.get("frozen"))
    print("Fingerprint   : %s" % manifest.get("fingerprint"))

    print("\n=== TASK A: REQUEST ACCOUNTING ===")
    print("Requests used this run (Real-Time) : %d" % result["requests_used"])
    print("Prior buggy-run requests           : %d" % PRIOR_SPENT)
    print("TURN TOTAL (Real-Time)             : %d (hard cap 40)"
          % (result["requests_used"] + PRIOR_SPENT))
    print("Quota remaining after run          : %s / %s"
          % (result["quota_remaining"], result["quota_limit"]))

    print("\n=== TASK A: SAMPLE (5 ASINs) ===")
    sample = manifest["asins"][:5]
    for r in sample:
        print(json.dumps({
            "asin": r["asin"],
            "product_title": r.get("product_title"),
            "product_price": r.get("product_price"),
            "product_star_rating": r.get("product_star_rating"),
            "product_num_ratings": r.get("product_num_ratings"),
            "product_num_offers": r.get("product_num_offers"),
            "brand_match_basis": r.get("brand_match_basis"),
            "source_query": r.get("source_query"),
            "page_found": r.get("page_found"),
        }, ensure_ascii=False))

    # --- Task C: redundancy backstop only if Task A left headroom ---
    print("\n=== TASK C: REDUNDANCY BACKSTOP (max 2, separate apps) ===")
    if result["requests_used"] + PRIOR_SPENT >= 40:
        print("Skipped: Task A consumed the full turn request budget "
              "(%d prior + %d now = 40). Task C deferred." % (PRIOR_SPENT, result["requests_used"]))
    else:
        ax = kd.redundancy_probe(
            "RAPIDAPI_HOST_AXESSO", "/amz/amazon-search-by-keyword-asin",
            param_name="keyword")
        on = kd.redundancy_probe(
            "RAPIDAPI_HOST_ONLINE", "/search", param_name="keyword")
        print("Axesso  : %s (http=%s, products=%s)"
              % (ax["status"], ax.get("http_status"), ax.get("product_count")))
        print("Online  : %s (http=%s, products=%s)"
              % (on["status"], on.get("http_status"), on.get("product_count")))
        print("NOTE: results NOT folded into manifest (held separate).")

    print("\n=== SEARCH_ROUTES STATUS TABLE (all 6 apps) ===")
    for app, v in kd.SEARCH_ROUTES.items():
        print("  %-18s %-32s %s" % (app, v["status"], v.get("path")))

    print("\n=== SINGLE-PROVIDER DEPENDENCY RISK ===")
    print("Layer 1 currently relies SOLELY on Real-Time Amazon Data. If that")
    print("provider's free tier (100 req) is exhausted or the host changes,")
    print("discovery halts. Recommend resolving Scout / BDC / Axesso as backup")
    print("search sources BEFORE scaling discovery volume long-term.")

    print("\n=== STOP STATEMENT ===")
    print("Discovery manifest is FROZEN and held at: %s" % result["path"])
    print("Enrichment / DataForSEO / offer-level live calls are NOT performed")
    print("this turn. They require a SEPARATE explicit approval reviewing this")
    print("manifest first. Scout and BDC remained frozen (0 requests).")


if __name__ == "__main__":
    main()
