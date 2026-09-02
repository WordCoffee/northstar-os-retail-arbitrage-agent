"""Task D/E rerun: live DataForSEO enrichment for the frozen 20-ASIN shortlist.

Uses the patched adapter (polling + float cost). Loads the EXISTING shortlist so
the ASIN set is byte-identical to the first run, then writes
data/catalog/enrichment_results_v2_<TS>.json and prints the Task E report.

Run (live, approved):  $env:NS_ALLOW_NETWORK="1"; python rerun_enrichment_v2.py
"""

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("NS_ALLOW_NETWORK", "1")

import dataforseo_adapter as dfa
import run_enrichment_pipeline as rep

SHORTLIST = "data/catalog/enrichment_shortlist_20260825T061558Z.json"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = "data/catalog/enrichment_results_v2_%s.json" % TS

# Poll budget for the live run: DataForSEO merchant tasks queue ~30-60s; keep
# checking every 5s, allow up to 5 min per task in case the queue is slow.
dfa.POLL_INTERVAL_SECONDS = 5
dfa.MAX_POLL_SECONDS = 300


def main():
    with open(SHORTLIST, "r", encoding="utf-8") as f:
        picks = json.load(f)["asins"]
    print("Rerunning enrichment for %d ASINs (patched adapter) -> %s"
          % (len(picks), OUT))

    results = rep.run_enrichment(picks, OUT)

    est_tasks, est_credits, est_usd = rep.cost_estimate(len(picks))
    actual, variance = rep.reconcile(results, est_usd)

    print("\n=== TASK E (v2) ===")
    print("Cost: estimate=$%.4f  actual=$%.4f  variance=$%.4f"
          % (est_usd, actual, variance))

    print("\nPrice-drift (discovery vs live buy_box, >15%):")
    drift = 0
    for r in results:
        dp, lp = r["discovery_price"], r["buy_box_price"]
        if isinstance(dp, (int, float)) and isinstance(lp, (int, float)) and dp:
            pct = (lp - dp) / dp * 100.0
            if abs(pct) > 15:
                drift += 1
                print("  %s drift %+.1f%% (disc=$%s live=$%s)"
                      % (r["asin"], pct, dp, lp))
    if drift == 0:
        print("  none")

    print("\nReadiness (BSR present + buy_box_price + >=2 offers):")
    ready = 0
    for r in results:
        bsr = (r["bsr"] or {}).get("bsr_primary_rank")
        bb, oc = r["buy_box_price"], r["offers_returned_count"] or 0
        is_ready = bsr is not None and bb is not None and oc >= 2
        if is_ready:
            ready += 1
        print("  %s %-7s bsr=%s bb=$%s offers=%s gaps=%s"
              % (r["asin"], "READY" if is_ready else "GAPPED",
                 bsr, bb, oc, r["data_gaps"]))
    print("  ready: %d / %d" % (ready, len(results)))

    print("\nSellers first-row all-None pattern check:")
    allnone = 0
    for r in results:
        offers = r["offers"] or []
        if offers and (offers[0].get("seller_name") is None
                       and offers[0].get("seller_url") is None
                       and offers[0].get("price") is None):
            allnone += 1
    print("  ASINs whose first returned offer is all-None: %d / %d"
          % (allnone, len(results)))
    if allnone and allnone < len(results):
        print("  NOTE: all-None header rows still appear on some ASINs; the "
              "adapter now filters them, but confirm the pattern is not hiding "
              "real first offers.")

    print("\n=== STOP === enrichment data is NOT a buy signal; no inventory "
          "decisions taken.")


if __name__ == "__main__":
    main()
