#!/usr/bin/env python3
"""Check ScrapingBee credit balance + inspect product fields needed by the gates."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")
KEY = env.get("SCRAPINGBEE_API_KEY")

# balance endpoints (try a few)
for u in ("https://app.scrapingbee.com/api/v1/usage", "https://app.scrapingbee.com/api/v1/credits",
          "https://app.scrapingbee.com/api/v1/account"):
    try:
        r = requests.get(u, params={"api_key": KEY}, timeout=30)
        print("GET", u, "->", r.status_code, r.text[:200].replace("\n", " "))
    except Exception as e:
        print("GET", u, "EXC", str(e)[:120])

# inspect stored product probe
d = json.loads((ROOT / "out_lions_mane" / "raw_probe_sb_product.json").read_text(encoding="utf-8"))
p = d.get("product") or d
print("\n--- product_details ---")
print(json.dumps(p.get("product_details"), indent=1)[:1500])
print("\n--- sales_rank ---")
print(json.dumps(p.get("sales_rank"), indent=1)[:500])
print("\n--- important_information ---")
print(json.dumps(p.get("important_information"), indent=1)[:600])
print("\n--- bullet_points ---")
print(json.dumps(p.get("bullet_points"), indent=1)[:900])
print("\n--- item_form:", p.get("item_form"))
print("--- category:", json.dumps(p.get("category"))[:300])
print("--- price:", p.get("price"), "| price_buybox:", p.get("price_buybox"))
print("--- buybox:", json.dumps(p.get("buybox"))[:400])
print("--- variations:", json.dumps(p.get("variations"))[:600])
print("--- product_overview:", json.dumps(p.get("product_overview"))[:400])
print("--- technical_details:", json.dumps(p.get("technical_details"))[:400])
