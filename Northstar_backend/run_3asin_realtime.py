"""Controlled 3-ASIN live comparison run against real-time-amazon-data.

Exactly 3 requests total (1 per ASIN), no loops beyond the 3, no retries.
Uses normalize_real_time + to_intel_market_real_time. Compares against the
Easyparser baseline in data/amazon-market-snapshots.json.
"""

import datetime
import json
import os

import requests
from dotenv import load_dotenv

import rapidapi_router as R
from intel_schema import fixture_minimal, snapshot_from_fixture, validate_snapshot

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY")
HOST = os.getenv("RAPIDAPI_HOST_REALTIME")
ASINS = ["B00F4MD808", "B0BMX67KY7", "B0CHTNWWLJ"]

os.makedirs("data/snapshots", exist_ok=True)
os.makedirs("data/cache", exist_ok=True)

# ---- Baseline (Easyparser) ----
with open("data/amazon-market-snapshots.json", "r", encoding="utf-8") as f:
    base = json.load(f)["asins"]

def benchmark(asin):
    r = base.get(asin, {})
    bb = r.get("buy_box") if isinstance(r.get("buy_box"), dict) else {}
    sc = r.get("seller_counts") if isinstance(r.get("seller_counts"), dict) else {}
    return {
        "title": r.get("title"),
        "price": bb.get("price"),
        "bsr": r.get("bsr") if r.get("bsr") is not None else None,
        "bb_seller": bb.get("seller_name"),
        "claimed": sc.get("claimed_total"),
        "returned": sc.get("observed_total"),
    }

ts = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
out_path = "data/snapshots/live_3asin_realtime_%s.json" % ts

snapshots = {}
summary = []
quota = None

print("=== 3-ASIN Live Comparison: real-time-amazon-data ===")
print("Requests: exactly 3 (no retries)\n")

for asin in ASINS:
    cache_path = "data/cache/realtime_%s.json" % asin
    if os.path.exists(cache_path):
        # Reuse cached raw (no new request) for idempotent re-runs.
        with open(cache_path, "r", encoding="utf-8") as cf:
            raw = json.load(cf)
        status = 200
        rate_rem = "(cached)"
        print("[%s] loaded from cache (no request)" % asin)
    else:
        path = R._path_for("RAPIDAPI_HOST_REALTIME", asin)
        url = "https://%s%s" % (HOST, path)
        headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST}
        resp = requests.get(url, headers=headers, timeout=20)  # THE single request for this ASIN
        status = resp.status_code
        try:
            raw = resp.json()
        except ValueError:
            raw = {}
        quota = resp.headers.get("X-RateLimit-Requests-Remaining", quota)
        rate_rem = resp.headers.get("X-RateLimit-Requests-Remaining", "?")
        with open(cache_path, "w", encoding="utf-8") as cf:
            json.dump(raw, cf, default=str)

    uni = R.normalize_real_time(asin, raw)
    market = R.to_intel_market_real_time(asin, raw)

    snap = snapshot_from_fixture(fixture_minimal())
    snap["asin"] = asin
    snap["facts"]["market"] = market
    snap["facts"]["provenance"]["market.amazon_price"] = "rapidapi_realtime"
    errs = validate_snapshot(snap)
    val = "valid" if not errs else "errors:%d" % len(errs)
    if errs:
        snap["validation_errors"] = errs[:10]

    snapshots[asin] = snap
    summary.append((asin, status, rate_rem, uni, market, val, benchmark(asin)))
    print("[%s] HTTP %s | quota_rem=%s | price=%s | offers=%d | valid=%s"
          % (asin, status, rate_rem, market["amazon_price"],
             market["seller_counts"]["total_observed"], val))

# ---- Save normalized snapshots ----
artifact = {
    "provider": "real-time-amazon-data",
    "generated_at": datetime.datetime.now().isoformat(),
    "asins": snapshots,
}
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(artifact, f, indent=2, default=str)

print("\nSaved snapshot artifact: %s" % out_path)

# ---- Comparison & Drift Table ----
print("\n=== Comparison & Drift Table ===")
hdr = "%-12s | %-34s | %-22s | %-20s | %-30s | %s"
print(hdr % ("ASIN", "Product Title (live)", "Price L/B (drift)", "BSR L/B", "BuyBox seller (claim/ret) L|B", "Schema"))
print("-" * 170)
for asin, status, rate_rem, uni, market, val, bm in summary:
    title = (market.get("amazon_price") and uni.get("title")) or ""
    title = (uni.get("title") or "")[:34]
    lp = market["amazon_price"]
    bp = bm["price"]
    drift = ("%.2f" % (lp - bp)) if (lp is not None and bp is not None) else "n/a"
    price_cell = "%s / %s (%s)" % (lp, bp, drift)
    lb = market["bsr"]
    lrank = lb.get("bsr_primary_rank") if isinstance(lb, dict) else None
    lcat = lb.get("bsr_primary_category") if isinstance(lb, dict) else None
    lbsr = ("%s" % lrank) if lrank else "none"
    bbsr = "none" if bm["bsr"] in (None, "none", "") else str(bm["bsr"])
    bsr_cell = "%s / %s" % (lbsr, bbsr)
    sc = market["seller_counts"]
    lbb = market["buy_box"].get("seller_name") or "?"
    live_bb = "%s (%s/%s)" % (lbb, sc["claimed_total"], sc["total_observed"])
    bbb = "%s (%s/%s)" % (bm["bb_seller"] or "?", bm["claimed"], bm["returned"])
    bb_cell = "%s | %s" % (live_bb, bbb)
    print(hdr % (asin, title, price_cell, bsr_cell, bb_cell, val))

print("\n=== Quota status ===")
print("X-RateLimit-Requests-Remaining (after 3 requests): %s" % quota)
print("Expected: ~95 (100 tier - 2 prior probes - 3 this run)")
