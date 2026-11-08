#!/usr/bin/env python3
"""Probe Chocodata Amazon search (1 keyword, 1 page) - free tier, saves Rainforest credits."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("CHOCODATA_API_KEY") or ""
assert KEY, "no CHOCODATA_API_KEY"

r = requests.get("https://api.chocodata.com/api/v1/amazon/search", params={
    "api_key": KEY,
    "query": "organic lion's mane mushroom powder",
    "page": 1,
    "domain": "amazon.com",
}, timeout=60)
print("HTTP", r.status_code)
print(r.text[:600])
if r.status_code == 200:
    d = r.json()
    (ROOT / "out_lions_mane" / "raw_probe_chocodata.json").write_text(json.dumps(d, indent=2), encoding="utf-8")
    items = d if isinstance(d, list) else (d.get("results") or d.get("data") or d.get("products") or [])
    print("count:", len(items))
    if items:
        print("KEYS:", sorted(items[0].keys()))
        print(json.dumps(items[0], indent=2)[:1800])
