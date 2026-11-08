#!/usr/bin/env python3
"""Probe which pagination parameter ScrapingBee's amazon/search accepts."""
import requests
from dotenv import dotenv_values
from pathlib import Path

ENV = dotenv_values(Path(__file__).resolve().parent / ".env")
KEY = ENV.get("SCRAPINGBEE_API_KEY")
for pname in ["page_from", "pagination", "start_page", "page_number", "results_page"]:
    r = requests.get("https://app.scrapingbee.com/api/v1/amazon/search",
                     params={"api_key": KEY, "domain": "com", "query": "organic lions mane powder", pname: 2},
                     timeout=120)
    cost = r.headers.get("spb-cost")
    print(f"{pname}: HTTP {r.status_code} cost={cost} body={r.text[:120] if r.status_code != 200 else 'OK: ' + str(len(r.json().get('products', []))) + ' products'}")
    if r.status_code == 200:
        break
