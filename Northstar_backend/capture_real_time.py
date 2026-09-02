"""Single-request capture of real-time-amazon-data raw payload (bounded: 1 request)."""

import json
import os

import requests
from dotenv import load_dotenv

import rapidapi_router as R

load_dotenv()

HOST_ENV = "RAPIDAPI_HOST_REALTIME"
HOST = os.getenv(HOST_ENV)
ASIN = "B00F4MD808"
OUT = "data/probe_real_time_raw.json"

path = R._path_for(HOST_ENV, ASIN)
url = "https://%s%s" % (HOST, path)
headers = {"X-RapidAPI-Key": os.getenv("RAPIDAPI_KEY"), "X-RapidAPI-Host": HOST}

print("=== Capture: real-time-amazon-data ===")
print("URL: %s" % url)
print("Requests made: 1 (bounded)")

resp = requests.get(url, headers=headers, timeout=20)  # THE single request
status = resp.status_code

SENSITIVE = ("key", "authorization", "cookie", "token")
rate = {k: v for k, v in resp.headers.items()
        if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))}

try:
    data = resp.json()
except ValueError:
    data = {"raw_text": resp.text[:500]}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, default=str)

print("HTTP Status : %s" % status)
print("Saved raw   : %s" % OUT)
print("RateLimit   : %s" % rate)

print("\n--- Top-level keys ---")
if isinstance(data, dict):
    for k in data.keys():
        v = data[k]
        t = type(v).__name__
        extra = " len=%d" % len(v) if isinstance(v, (list, dict)) else ""
        print("  %-30s %s%s" % (k, t, extra))
elif isinstance(data, list):
    print("  (top-level list, len=%d)" % len(data))

# Targeted structure: offers / sales_rank / price
def _first_list(d):
    if isinstance(d, dict):
        for v in d.values():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                return v[0]
    return None

print("\n--- offers / product_offers ---")
off = _first_list(data) or _first_list(data.get("product_offers", {})) if isinstance(data, dict) else None
if off is None and isinstance(data, dict):
    for key in ("offers", "product_offers", "deal", "deals"):
        if isinstance(data.get(key), list) and data[key]:
            off = data[key][0]
            break
if isinstance(off, dict):
    print("  first offer keys: %s" % sorted(off.keys()))
else:
    print("  no offer list located at top level")

print("\n--- sales_rank / rank / BSR ---")
for cand in ("sales_rank", "salesRank", "rank", "bsr", "product_information"):
    if isinstance(data, dict) and cand in data:
        val = data[cand]
        print("  %s: %s" % (cand, (str(val)[:120] if not isinstance(val, (list, dict)) else type(val).__name__)))

print("\n--- product_price / original ---")
for cand in ("product_price", "product_original_price", "price", "current_price", "buybox_price"):
    if isinstance(data, dict) and cand in data:
        print("  %s = %s" % (cand, str(data[cand])[:120]))
