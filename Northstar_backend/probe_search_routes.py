"""Route-verification probe for BDC + Scout keyword search (2 live requests).

Exactly 2 requests total (1 per app). Saves raw JSON. Does NOT run discovery.
Does NOT touch enrichment/DataForSEO.
"""

import json
import os
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY")
HOST_BDC = os.getenv("RAPIDAPI_HOST_BDC")
HOST_SCOUT = os.getenv("RAPIDAPI_HOST_SCOUT")
QUERY = "Kirkland Signature"

os.makedirs("data/catalog", exist_ok=True)


def probe(host, label, out_path):
    path = "/search/%s" % quote(QUERY)
    url = "https://%s%s" % (host, path)
    headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": host}
    print("=== %s ===" % label)
    print("URL: %s" % url)
    resp = requests.get(url, headers=headers, timeout=20)  # 1 request
    status = resp.status_code
    try:
        data = resp.json()
    except ValueError:
        data = {"raw_text": resp.text[:500]}
    rate = {k: v for k, v in resp.headers.items()
            if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    print("HTTP Status : %s" % status)
    print("Saved raw   : %s" % out_path)
    print("RateLimit   : %s" % (rate or "none exposed"))
    return status, data, rate


bdc_status, bdc_data, bdc_rate = probe(HOST_BDC, "BDC Amazon Data Scraper", "data/catalog/probe_bdc_raw.json")
scout_status, scout_data, scout_rate = probe(HOST_SCOUT, "Scout Amazon Data", "data/catalog/probe_scout_raw.json")
print("\nRequests made: 2 (bounded). Probe complete.")
