"""Layer 1 triage + shortlist + bounded live DataForSEO enrichment (Tasks A-E).

Run: $env:NS_ALLOW_NETWORK="1"; python run_enrichment_pipeline.py
Order: A offline triage -> B shortlist -> C cost gate -> D live enrich -> E report.
Never prints secrets. DataForSEO adapter is the sole enrichment provider.
"""

import json
import math
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

try:
    from dataforseo_adapter import get_dataforseo_offers
    from proof_batch_contracts import ESTIMATED_CREDITS_PER_REQUEST
except Exception as exc:  # pragma: no cover
    print("IMPORT ERROR: %s" % exc)
    raise

load_dotenv()

MANIFEST = "data/catalog/layer1_discovery_manifest_20260825T033418Z.json"
CATALOG = "data/catalog"
TS = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

# DataForSEO documented standard rate (assumption, flagged in output):
# $2 per 1,000 credits => $0.002 / credit. Task E reconciles vs real cost_usd.
USD_PER_CREDIT = 0.002
MAX_ASINS = 20
PER_CATEGORY_CAP = int(MAX_ASINS * 0.40)  # 8 (40% of 20)


def _to_float(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _to_int(v):
    f = _to_float(v)
    return int(f) if f is not None else None


# ---------------------------------------------------------------------------
# Task A - offline triage
# ---------------------------------------------------------------------------
def parse_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        m = json.load(f)
    return m["asins"]


def triage(rows):
    max_demand = 0.0
    parsed = []
    for r in rows:
        nr = _to_int(r.get("product_num_ratings")) or 0
        demand = math.log10(1 + max(nr, 0))
        max_demand = max(max_demand, demand)
        price = _to_float(r.get("product_price"))
        rating = _to_float(r.get("product_star_rating"))
        offers = _to_int(r.get("product_num_offers")) or 0
        parsed.append({
            "asin": r.get("asin"),
            "product_title": r.get("product_title") or r.get("title"),
            "source_query": r.get("source_query"),
            "price": price,
            "rating": rating,
            "num_ratings": nr,
            "num_offers": offers,
            "demand": demand,
            "price_band_fit": "core" if (price is not None and 15 <= price <= 50)
            else "review",
            "comp_flag_single": (offers == 1),
        })
    max_demand = max_demand or 1.0
    for p in parsed:
        d_norm = p["demand"] / max_demand
        pf = 1.0 if p["price_band_fit"] == "core" else 0.3
        o = p["num_offers"]
        if o == 1:
            cs = 0.6
        elif 2 <= o <= 25:
            cs = 1.0
        elif o > 25:
            cs = 0.8
        else:
            cs = 0.4
        rs = 1.0 if (p["rating"] is not None and p["rating"] >= 4.0) else 0.3
        p["rating_quality_flag"] = (p["rating"] is not None and p["rating"] < 4.0)
        # composite weights: demand 0.50, price 0.20, competition 0.15, rating 0.15
        p["composite_score"] = round(
            100 * (0.50 * d_norm + 0.20 * pf + 0.15 * cs + 0.15 * rs), 4)
    parsed.sort(key=lambda x: x["composite_score"], reverse=True)
    for i, p in enumerate(parsed, 1):
        p["rank"] = i
    return parsed


def write_triage_csv(parsed, path):
    cols = ["asin", "product_title", "source_query", "price", "rating",
            "num_ratings", "num_offers", "price_band_fit", "composite_score", "rank"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(",".join(cols) + "\n")
        for p in parsed:
            row = [str(p.get(c, "")) for c in cols]
            row = ['"%s"' % c.replace('"', '""') if ("," in c or '"' in c) else c
                   for c in row]
            f.write(",".join(row) + "\n")


# ---------------------------------------------------------------------------
# Task B - shortlist selection (40% per-category cap)
# ---------------------------------------------------------------------------
def select_shortlist(parsed, max_asins=MAX_ASINS, cap=PER_CATEGORY_CAP):
    picks = []
    cat_count = {}
    for p in parsed:
        if len(picks) >= max_asins:
            break
        c = p["source_query"]
        if cat_count.get(c, 0) >= cap:
            continue
        picks.append(p)
        cat_count[c] = cat_count.get(c, 0) + 1
    return picks, cat_count


def write_shortlist(picks, path):
    out = []
    for p in picks:
        out.append({
            "asin": p["asin"],
            "product_title": p["product_title"],
            "source_query": p["source_query"],
            "price": p["price"],
            "rating": p["rating"],
            "num_ratings": p["num_ratings"],
            "num_offers": p["num_offers"],
            "price_band_fit": p["price_band_fit"],
            "comp_flag_single": p["comp_flag_single"],
            "rating_quality_flag": p["rating_quality_flag"],
            "composite_score": p["composite_score"],
            "rank": p["rank"],
            # enrichment placeholders (null until Task D)
            "bsr": None,
            "buy_box_price": None,
            "buy_box_seller": None,
            "offers": [],
            "credits_used": None,
            "cost_usd": None,
            "data_gaps": [],
        })
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "schema_version": 1,
            "kind": "enrichment_shortlist",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(out),
            "asins": out,
        }, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Task C - pre-spend cost estimate (gate)
# ---------------------------------------------------------------------------
def cost_estimate(asin_count, tasks_per_asin=2):
    tasks = asin_count * tasks_per_asin
    credits = tasks * ESTIMATED_CREDITS_PER_REQUEST
    usd = credits * USD_PER_CREDIT
    return tasks, credits, round(usd, 4)


# ---------------------------------------------------------------------------
# Task D - bounded live enrichment (sequential, 1 retry on transport/guard)
# ---------------------------------------------------------------------------
def enrich_one(asin):
    last = get_dataforseo_offers(asin)
    gaps = last.get("data_gaps") or []
    transient = any(("transport error" in g or "guard error" in g) for g in gaps)
    if transient:
        time.sleep(2)
        last = get_dataforseo_offers(asin)
    return last


def run_enrichment(picks, out_path):
    results = []
    for p in picks:
        asin = p["asin"]
        res = enrich_one(asin)
        rec = {
            "asin": asin,
            "source_query": p["source_query"],
            "discovery_price": p["price"],
            "bsr": res.get("bsr"),
            "buy_box_price": res.get("buy_box_price"),
            "buy_box_seller": res.get("buy_box_seller"),
            "offers_returned_count": res.get("offers_returned_count"),
            "offers": res.get("offers"),
            "credits_used": res.get("credits_used"),
            "cost_usd": res.get("cost_usd"),
            "data_gaps": res.get("data_gaps"),
            "accepted": (res.get("data_gaps") == [] or
                         not any("not enabled" in g or "not armed" in g
                                 for g in (res.get("data_gaps") or []))),
        }
        results.append(rec)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump({
                "schema_version": 1,
                "kind": "enrichment_results",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "count": len(results),
                "results": results,
            }, f, indent=2, default=str)
        status = "OK" if rec["buy_box_price"] is not None else "GAP"
        print("  [%2d/%2d] %s -> %s buy_box=$%s offers=%s cost=$%s"
              % (len(results), len(picks), asin, status,
                 rec["buy_box_price"], rec["offers_returned_count"], rec["cost_usd"]))
    return results


# ---------------------------------------------------------------------------
# Task E - reconciliation & report
# ---------------------------------------------------------------------------
def reconcile(results, est_usd):
    actual = sum((float(r["cost_usd"]) if isinstance(r["cost_usd"], (int, float)) else 0)
                 for r in results)
    return round(actual, 4), round(actual - est_usd, 4)


def main():
    os.makedirs(CATALOG, exist_ok=True)
    print("=== TASK A: OFFLINE TRIAGE ===")
    rows = parse_manifest(MANIFEST)
    print("Loaded %d manifest rows." % len(rows))
    parsed = triage(rows)
    triage_path = "%s/layer1_triage_scored_%s.csv" % (CATALOG, TS)
    write_triage_csv(parsed, triage_path)
    print("Triage CSV written: %s" % triage_path)

    print("\n=== TASK B: SHORTLIST SELECTION ===")
    picks, cat_count = select_shortlist(parsed)
    shortlist_path = "%s/enrichment_shortlist_%s.json" % (CATALOG, TS)
    write_shortlist(picks, shortlist_path)
    print("Shortlist written: %s (%d ASINs)" % (shortlist_path, len(picks)))
    print("Per-category counts (cap=%d): %s" % (PER_CATEGORY_CAP, cat_count))
    print("\nFull 20-ASIN shortlist:")
    print("  %-12s %-8s %-9s %-6s %-7s %-7s %s"
          % ("ASIN", "price", "rating", "rates", "offers", "score", "title"))
    for p in picks:
        print("  %-12s %-8s %-9s %-6s %-7s %-7s %s"
              % (p["asin"], p["price"], p["rating"], p["num_ratings"],
                 p["num_offers"], p["composite_score"],
                 (p["product_title"] or "")[:48]))

    print("\n=== TASK C: PRE-SPEND COST ESTIMATE (GATE) ===")
    tasks, credits, est_usd = cost_estimate(len(picks))
    print("Estimated live enrichment cost: $%s for %d ASINs (%d tasks)."
          % ("%.2f" % est_usd, len(picks), tasks))
    print("  (credits=%s @ ESTIMATED_CREDITS_PER_REQUEST=%s; USD_PER_CREDIT=$%s assumed)"
          % (credits, ESTIMATED_CREDITS_PER_REQUEST, USD_PER_CREDIT))
    if est_usd > 5.00:
        print("OVERAGE: estimate $%s exceeds $5.00 cap. HALTING at Task C. "
              "Request explicit operator confirmation to proceed." % ("%.2f" % est_usd))
        return
    print("Gate passed (<= $5.00). Proceeding to Task D under blanket approval.")

    print("\n=== TASK D: BOUNDED LIVE DATAFORSEO ENRICHMENT ===")
    enrich_path = "%s/enrichment_results_%s.json" % (CATALOG, TS)
    results = run_enrichment(picks, enrich_path)
    print("Enrichment results written: %s" % enrich_path)

    print("\n=== TASK E: RECONCILIATION & REPORT ===")
    actual, variance = reconcile(results, est_usd)
    print("Cost: estimate=$%s  actual=$%s  variance=$%s"
          % ("%.2f" % est_usd, "%.2f" % actual, "%.2f" % variance))

    print("\nPrice-drift flags (discovery vs live buy_box, >15%):")
    drift = 0
    for r in results:
        dp = r["discovery_price"]
        lp = r["buy_box_price"]
        if isinstance(dp, (int, float)) and isinstance(lp, (int, float)) and dp:
            pct = (lp - dp) / dp * 100.0
            if abs(pct) > 15:
                drift += 1
                print("  %s drift %+.1f%% (disc=$%s live=$%s)"
                      % (r["asin"], pct, dp, lp))
    if drift == 0:
        print("  none")

    print("\nReadiness table (decision-ready = BSR + buy_box_price + >=2 offers):")
    ready = 0
    for r in results:
        bsr_rank = (r["bsr"] or {}).get("bsr_primary_rank")
        bb = r["buy_box_price"]
        oc = r["offers_returned_count"] or 0
        is_ready = (bsr_rank is not None) and (bb is not None) and oc >= 2
        if is_ready:
            ready += 1
        flag = "READY" if is_ready else "GAPPED"
        print("  %s %-7s bsr=%s bb=$%s offers=%s"
              % (r["asin"], flag, bsr_rank, bb, oc))

    print("\nPortfolio diversification check:")
    for c, n in cat_count.items():
        pct = n / len(picks) * 100
        ok = "OK" if n <= PER_CATEGORY_CAP else "OVER CAP"
        print("  %-45s %d (%.0f%%) %s" % (c, n, pct, ok))
    print("40%%-cap respected: %s"
          % ("YES" if all(n <= PER_CATEGORY_CAP for n in cat_count.values()) else "NO"))

    print("\nSingle-provider dependency note:")
    print("  Discovery relies on Real-Time Amazon Data alone; enrichment relies")
    print("  on DataForSEO alone. Either provider outage halts the pipeline.")
    print("  Next resilience gap: stand up Scout/BDC (discovery) and a second")
    print("  enrichment provider as backups before scaling volume.")

    print("\n=== STOP STATEMENT ===")
    print("Run ends at Task E. Enrichment data is NOT a buy signal. Any actual")
    print("purchase requires separate invoice-legitimacy + wholesale-sourcing")
    print("verification. No inventory decisions taken here.")


if __name__ == "__main__":
    main()
