#!/usr/bin/env python3
"""Step 0 probe: Rainforest 1 keyword, 1 page. Dump full raw records + key inventory."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("RAINFOREST_API_KEY") or ""
assert KEY, "no RAINFOREST_API_KEY"
OUT = ROOT / "out_lions_mane"
OUT.mkdir(exist_ok=True)

r = requests.get("https://api.rainforestapi.com/request", params={
    "api_key": KEY, "type": "search",
    "search_term": "organic lion's mane mushroom powder",
    "amazon_domain": "amazon.com", "max_page": 1, "page": 1,
}, timeout=60)
r.raise_for_status()
data = r.json()
(OUT / "raw_probe.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
ri = data.get("request_info", {})
print("credits_used:", ri.get("credits_used"), "credits_remaining:", ri.get("credits_remaining"))
sr = data.get("search_results", [])
print("results:", len(sr))
print("pagination:", json.dumps(data.get("pagination", {}))[:300])
if sr:
    print("SEARCH RESULT KEYS:", sorted(sr[0].keys()))
    print(json.dumps(sr[0], indent=2)[:2500])

# also one product probe for field names
r2 = requests.get("https://api.rainforestapi.com/request", params={
    "api_key": KEY, "type": "product",
    "asin": sr[0]["asin"],
    "amazon_domain": "amazon.com",
}, timeout=60)
r2.raise_for_status()
d2 = r2.json()
(OUT / "raw_probe_product.json").write_text(json.dumps(d2, indent=2), encoding="utf-8")
print("product credits_remaining:", d2.get("request_info", {}).get("credits_remaining"))
p = d2.get("product", {})
print("PRODUCT KEYS:", sorted(p.keys()))
