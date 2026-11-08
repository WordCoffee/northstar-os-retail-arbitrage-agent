#!/usr/bin/env python3
"""Probe ScrapingBee Amazon product endpoint with the 'query' parameter."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("SCRAPINGBEE_API_KEY")
assert KEY

for params in [
    {"query": "B07W8W2PS6"},
    {"query": "https://www.amazon.com/dp/B07W8W2PS6"},
]:
    r = requests.get("https://app.scrapingbee.com/api/v1/amazon/product",
                     params={"api_key": KEY, "domain": "com", **params}, timeout=120)
    print("params:", params, "-> HTTP", r.status_code, "| spb-cost:", r.headers.get("spb-cost"))
    try:
        d = r.json()
        if r.status_code == 200:
            (ROOT / "out_lions_mane" / "raw_probe_sb_product.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
            p = d.get("product") or d
            print("  keys:", sorted(p.keys()) if isinstance(p, dict) else type(p))
            if isinstance(p, dict):
                for k in ("title", "brand", "rating", "reviews_count", "price", "features", "images", "main_image",
                          "specifications", "bestsellers_rank", "weight", "ingredients", "description", "variations", "sales_volume"):
                    v = p.get(k)
                    if v not in (None, [], {}, ""):
                        print(f"    {k}: {json.dumps(v)[:200]}")
            break
        else:
            print("  body:", r.text[:300])
    except Exception as e:
        print("  json error:", e)
