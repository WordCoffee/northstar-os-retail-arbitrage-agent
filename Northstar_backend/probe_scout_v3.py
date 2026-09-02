"""Scout single bounded probe v3 (1 request max). No loop, no retry.

Tries /Amazon-Search-Data with searchTerm=Kirkland Signature AND domainCode=com
(fallback per mission step 2). Persists status + rate-limit headers for audit.
"""

import json
import os
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY")
HOST = os.getenv("RAPIDAPI_HOST_SCOUT")
ENDPOINT = "/Amazon-Search-Data"
OUT = "data/catalog/probe_scout_raw_v3.json"

os.makedirs("data/catalog", exist_ok=True)
headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST}
url = "https://%s%s?searchTerm=%s&domainCode=%s" % (
    HOST, ENDPOINT, quote("Kirkland Signature"), "com")

print("GET %s" % url)
resp = requests.get(url, headers=headers, timeout=20)  # exactly 1 request
status = resp.status_code
rate = {k: v for k, v in resp.headers.items()
        if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))}
try:
    body = resp.json()
except ValueError:
    body = {"raw_text": resp.text[:500]}

payload = {"status": status, "rate_limit": rate, "body": body}
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, default=str)

print("HTTP Status : %s" % status)
print("Saved raw   : %s" % OUT)
print("RateLimit   : %s" % (rate or "none exposed"))
print("Body        : %s" % json.dumps(body, default=str)[:600])
