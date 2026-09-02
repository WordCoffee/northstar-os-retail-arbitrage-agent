"""Offline verification of the real-time mapper (NO network)."""

import json

import rapidapi_router as R
from intel_schema import fixture_minimal, snapshot_from_fixture, validate_snapshot

with open("data/probe_real_time_raw.json", "r", encoding="utf-8") as f:
    raw = json.load(f)

ASIN = raw.get("data", {}).get("asin", "B00F4MD808")

print("=== normalized (unified) ===")
uni = R.normalize_real_time(ASIN, raw)
for k in ("title", "price", "original_price", "reviews", "star_rating",
          "bsr", "is_prime", "is_amazon_choice", "is_best_seller",
          "prime_fba_status", "buy_box_status", "num_offers",
          "seller_data"):
    v = uni.get(k)
    if k == "seller_data":
        print("  %-18s : list len=%d" % (k, len(v) if v else 0))
    elif k == "buy_box_status":
        print("  %-18s : %s" % (k, (v or {}).get("price") if isinstance(v, dict) else v))
    else:
        print("  %-18s : %s" % (k, str(v)[:90]))

print("\n=== intel_schema market ===")
market = R.to_intel_market_real_time(ASIN, raw)
print(json.dumps(market, indent=2, default=str))

snap = snapshot_from_fixture(fixture_minimal())
snap["asin"] = ASIN
snap["facts"]["market"] = market
snap["facts"]["provenance"]["market.amazon_price"] = "rapidapi_realtime"
errs = validate_snapshot(snap)
print("\nintel_schema validation errors: %s" % (errs if errs else "NONE (valid)"))
