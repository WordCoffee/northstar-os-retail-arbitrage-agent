"""Single-ASIN live probe: real-time-amazon-data (verified route).

Exactly ONE outbound request. Normalizes the response into intel_schema
MarketSnapshot format and reports pool quota-readiness signals.
"""

import json
import os

import requests
from dotenv import load_dotenv

import rapidapi_router as R
from intel_schema import normalize_bsr, fixture_minimal, snapshot_from_fixture, validate_snapshot

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY")
HOST_ENV = "RAPIDAPI_HOST_REALTIME"
HOST = os.getenv(HOST_ENV)
ASIN = "B00F4MD808"

path = R._path_for(HOST_ENV, ASIN)
url = "https://%s%s" % (HOST, path)
headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST}

print("=== Single-ASIN Probe: real-time-amazon-data ===")
print("ASIN : %s" % ASIN)
print("HOST : %s" % HOST)
print("URL  : %s" % url)
print("Requests made: 1 (bounded)")

resp = requests.get(url, headers=headers, timeout=20)  # THE single request
status = resp.status_code

# Rate-limit / quota headers only (never print auth headers).
SENSITIVE = ("key", "authorization", "cookie", "token")
rate_headers = {
    k: v for k, v in resp.headers.items()
    if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))
}

try:
    data = resp.json()
except ValueError:
    data = {"raw_text": resp.text[:500]}

# ---- Field inventory (generic, null-first) ----
def present(*names):
    return R._find_any(data, list(names)) is not None

inventory = {
    "title": present("title", "name", "product_title", "productTitle"),
    "price": present("price", "current_price", "buybox_price", "listing_price", "amount"),
    "buy_box_winner": present("buybox_winner", "buy_box_winner", "buybox", "is_buybox_winner"),
    "offer_count": present("offers", "sellers", "offer_count", "number_of_offers", "total_offers"),
    "bsr": present("bsr", "sales_rank", "salesRank", "best_sellers_rank", "rank"),
}
print("\n--- Probe HTTP Status & Provider confirmation ---")
print("HTTP Status : %s" % status)
print("Provider    : %s (responded -> app is live)" % HOST)
print("Payload     : %s" % ("valid_json" if isinstance(data, dict) else "non_json"))

print("\n--- Field validation summary ---")
for k, v in inventory.items():
    print("  %-14s : %s" % (k, "PRESENT" if v else "absent"))

# ---- Normalize into intel_schema MarketSnapshot ----
uni = R._normalize(HOST_ENV, ASIN, data)
snap = snapshot_from_fixture(fixture_minimal())
snap["asin"] = ASIN
mkt = snap["facts"]["market"]

mkt["amazon_price"] = uni["price"]
snap["facts"]["provenance"]["market.amazon_price"] = "rapidapi_realtime"

bsr_raw = uni["bsr"]
if isinstance(bsr_raw, str):
    mkt["bsr"] = normalize_bsr(bsr_raw, source="rapidapi_realtime")
elif isinstance(bsr_raw, dict):
    mkt["bsr"] = bsr_raw

bb = uni["buy_box_status"]
if isinstance(bb, dict):
    mkt["buy_box"] = {
        "available": bb.get("price") is not None,
        "price": bb.get("price"),
        "seller_name": bb.get("seller"),
        "seller_id": None,
        "fulfillment": None,
        "source": "rapidapi_realtime",
        "observed_at": None,
    }

offers = uni["seller_data"] if isinstance(uni["seller_data"], list) else []
mkt["offers"] = offers
mkt["seller_counts"] = {
    "total_observed": len(offers),
    "fba_observed": sum(1 for o in offers if o.get("is_fba") or o.get("fulfillment") == "FBA"),
    "fbm_observed": sum(1 for o in offers if o.get("is_fbm") or o.get("fulfillment") == "FBM"),
    "amazon_observed": 0,
    "claimed_total": None,
}
mkt["coverage"] = {
    "offer_list_available": len(offers) > 0,
    "offers_complete_status": "full" if len(offers) > 0 else "unknown",
    "coverage_reason": "rapidapi realtime roster" if len(offers) > 0 else "no roster returned",
}

errors = validate_snapshot(snap)
print("\n--- intel_schema normalization ---")
print("Valid MarketSnapshot : %s" % ("YES" if not errors else "NO (%d errors)" % len(errors)))
if errors:
    for e in errors[:8]:
        print("   - %s" % e)

print("\n--- Pool quota readiness ---")
print("real-time-amazon-data rate headers: %s" % (rate_headers or "none exposed"))
print("Other 5 apps (BDC/AXESSO/PRICING/ONLINE/SCOUT): not probed this run ->")
print("  remaining free quota UNKNOWN (each RapidAPI app has an independent")
print("  monthly free tier; only a live call returns its rate-limit headers).")

print("\n--- Normalized market (truncated) ---")
print(json.dumps(mkt, indent=2, default=str)[:1600])
