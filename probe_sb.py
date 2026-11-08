#!/usr/bin/env python3
"""Probe ScrapingBee Amazon endpoints in detail. Prints field names + credit headers."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("SCRAPINGBEE_API_KEY")
assert KEY

def show_headers(r):
    for h in ("x-ratelimit-limit", "x-ratelimit-remaining", "x-ratelimit-reset", "x-cost", "x-credits"):
        v = r.headers.get(h)
        if v: print(f"  header {h}: {v}")
    print("  all rate headers:", {k: v for k, v in r.headers.items() if "rat" in k.lower() or "credit" in k.lower() or "cost" in k.lower()})

# Search
r = requests.get("https://app.scrapingbee.com/api/v1/amazon/search",
                 params={"api_key": KEY, "query": "organic lions mane powder", "domain": "com"}, timeout=120)
print("[search] HTTP", r.status_code)
show_headers(r)
d = r.json()
(ROOT / "out_lions_mane" / "raw_probe_sb_search.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
prods = d.get("products") or []
print("[search] n products:", len(prods))
if prods:
    print("[search] product keys:", sorted(prods[0].keys()))
    print(json.dumps(prods[0], indent=2)[:1200])
    print("[search] n second:", len(prods[1]) if len(prods) > 1 else 0)
    print(json.dumps(prods[1], indent=2)[:800])

# Product
r2 = requests.get("https://app.scrapingbee.com/api/v1/amazon/product",
                  params={"api_key": KEY, "asin": "B07W8W2PS6", "domain": "com"}, timeout=120)
print("[product] HTTP", r2.status_code)
show_headers(r2)
d2 = r2.json()
(ROOT / "out_lions_mane" / "raw_probe_sb_product.json").write_text(json.dumps(d2, indent=2), encoding="utf-8")
p = d2.get("product") or d2
print("[product] keys:", sorted(p.keys()) if isinstance(p, dict) else type(p))
if isinstance(p, dict):
    for k in ("title", "brand", "rating", "reviews_count", "price", "features", "images", "main_image",
              "specifications", "bestsellers_rank", "weight", "ingredients", "description"):
        v = p.get(k)
        if v not in (None, [], {}, ""):
            print(f"  {k}: {json.dumps(v)[:220]}")
