#!/usr/bin/env python3
"""Probe free-tier-capable APIs for Amazon structured data. Prints status only, no secrets."""
import json
from pathlib import Path
import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
env = dotenv_values(ROOT / ".env")

def try_req(name, method, url, **kw):
    try:
        r = requests.request(method, url, timeout=60, **kw)
        body = r.text[:300].replace("\n", " ")
        print(f"[{name}] HTTP {r.status_code} | {body}")
        return r
    except Exception as e:
        print(f"[{name}] EXC {type(e).__name__}: {str(e)[:200]}")
        return None

# 1) ScrapingDog Amazon search
key = env.get("SCRAPINGDOG_API_KEY")
if key:
    r = try_req("scrapingdog", "GET", "https://api.scrapingdog.com/amazon/search",
                params={"api_key": key, "query": "organic lions mane powder", "domain": "com", "page": 1})
    if r and r.status_code == 200:
        try:
            d = r.json()
            (ROOT / "out_lions_mane" / "raw_probe_scrapingdog.json").write_text(json.dumps(d, indent=2)[:200000], encoding="utf-8")
            items = d.get("results") or d.get("organic_results") or []
            print(f"  scrapingdog results: {len(items)}")
            if items:
                print("  keys:", sorted(items[0].keys()))
        except Exception as e:
            print("  json error:", e)

# 2) ScrapingBee Amazon search
key = env.get("SCRAPINGBEE_API_KEY")
if key:
    r = try_req("scrapingbee", "GET", "https://app.scrapingbee.com/api/v1/amazon/search",
                params={"api_key": key, "query": "organic lions mane powder", "domain": "com"})
    if r and r.status_code == 200:
        try:
            d = r.json()
            (ROOT / "out_lions_mane" / "raw_probe_scrapingbee.json").write_text(json.dumps(d, indent=2)[:200000], encoding="utf-8")
            items = d.get("results") or d.get("organic_results") or []
            print(f"  scrapingbee results: {len(items)}")
            if items:
                print("  keys:", sorted(items[0].keys()))
        except Exception as e:
            print("  json error:", e)

# 3) Karenable / Keenable
key = env.get("KEENABLE_API_KEY")
if key:
    r = try_req("keenable", "GET", "https://api.keenable.ai/v1/scrape",
                params={"api_key": key, "url": "https://www.amazon.com/dp/B07W8W2PS6"},
                headers={"Authorization": f"Bearer {key}"})

# 4) Firecrawl
key = env.get("FIRECRAWL_API_KEY")
if key:
    r = try_req("firecrawl", "POST", "https://api.firecrawl.dev/v1/scrape",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"url": "https://www.amazon.com/dp/B07W8W2PS6", "formats": ["markdown"]})

# 5) Browserbase (probably just a browser API, needs project)
key = env.get("BROWSERBASE_API_KEY")
if key:
    try_req("browserbase", "GET", "https://api.browserbase.com/v1/projects",
            headers={"X-BB-API-Key": key})
