"""Scout route-correction probe (1 app, up to 2 round-trips within budget).

Uses the confirmed endpoint GET /Amazon-Search-Data. Tries param 'searchTerm'
first; on a 400/422 parameter error, reads the body, extracts the expected
param name, and retries ONCE. Saves the final raw response.
"""

import json
import os
import re
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

KEY = os.getenv("RAPIDAPI_KEY")
HOST = os.getenv("RAPIDAPI_HOST_SCOUT")
ENDPOINT = "/Amazon-Search-Data"
QUERY = "Kirkland Signature"
OUT = "data/catalog/probe_scout_raw_v2.json"

os.makedirs("data/catalog", exist_ok=True)
headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST}

KNOWN_PARAMS = ["searchTerm", "keyword", "query", "q", "search", "term", "text"]


def do_request(param, value):
    url = "https://%s%s?%s=%s" % (HOST, ENDPOINT, param, quote(value))
    print("GET %s" % url)
    resp = requests.get(url, headers=headers, timeout=20)
    return resp


def extract_expected_param(body_text):
    for name in KNOWN_PARAMS:
        if re.search(r"\b%s\b" % re.escape(name), body_text, re.IGNORECASE):
            return name
    return None


print("=== Scout /Amazon-Search-Data probe ===")
param = "searchTerm"
resp = do_request(param, QUERY)  # round-trip 1
status = resp.status_code
rate = {k: v for k, v in resp.headers.items()
        if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))}

final_param = param
if status in (400, 422):
    try:
        body = resp.json()
        body_text = json.dumps(body)
    except ValueError:
        body_text = resp.text
    expected = extract_expected_param(body_text)
    if expected and expected != param:
        print("  param error; retrying with '%s' (round-trip 2)" % expected)
        resp = do_request(expected, QUERY)
        status = resp.status_code
        rate = {k: v for k, v in resp.headers.items()
                if any(t in k.lower() for t in ("rate", "limit", "quota", "remaining", "reset"))}
        final_param = expected

try:
    data = resp.json()
except ValueError:
    data = {"raw_text": resp.text[:500]}

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, default=str)

print("HTTP Status : %s" % status)
print("Param used  : %s" % final_param)
print("Saved raw   : %s" % OUT)
print("RateLimit   : %s" % (rate or "none exposed"))
