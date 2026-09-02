"""Standalone, out-of-pipeline RapidAPI comparison pull for the 10 canonical ASINs.

This is NOT part of the sanctioned Easyparser OFFER pipeline and never touches
data/enrich/easyparser-runs/. It reads RAPIDAPI_KEY / RAPIDAPI_HOST from the
environment (.env, gitignored). The key is never printed. Raw responses are
saved under data/rapidapi-compare/<run_id>/ and a rapidapi-vs-csv-comparison.csv
is emitted for manual review.

Usage:
  python rapidapi_compare.py            # search each ASIN string
  python rapidapi_compare.py --by-title # search each frozen-manifest title
"""

import csv
import json
import os
import sys
import time
import http.client
from datetime import datetime, timezone

from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST = os.path.join(BACKEND_DIR, "data", "enrich", "live-10asin-manifest.json")
OUT_ROOT = os.path.join(BACKEND_DIR, "data", "rapidapi-compare")


def _extract_top(j):
    if not isinstance(j, dict):
        return "", ""
    items = None
    for k in ("results", "data", "products", "items"):
        v = j.get(k)
        if isinstance(v, list) and v:
            items = v
            break
    if items is None and (j.get("title") or j.get("name") or j.get("price") is not None):
        items = [j]
    if not items:
        return "", ""
    top = items[0]
    if not isinstance(top, dict):
        return "", ""
    title = top.get("title") or top.get("name") or top.get("product_title") or ""
    price = (
        top.get("price")
        or top.get("price_lower")
        or top.get("current_price")
        or top.get("buybox_price")
        or ""
    )
    return title, price


def main():
    load_dotenv()
    key = os.getenv("RAPIDAPI_KEY")
    host = os.getenv("RAPIDAPI_HOST", "amazon-product-data4.p.rapidapi.com")
    if not key:
        print("ERROR: RAPIDAPI_KEY not set in environment", file=sys.stderr)
        return 2
    by_title = "--by-title" in sys.argv

    with open(MANIFEST, "r", encoding="utf-8-sig") as f:
        m = json.load(f)
    asins = {x["asin"]: x for x in m["asins"]}
    order = m["canonical_asin_order"]

    run_id = "rapidapi-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = os.path.join(OUT_ROOT, run_id)
    raw_dir = os.path.join(run_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    print("host=%s mode=%s run_id=%s" % (host, "title" if by_title else "asin", run_id))
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}

    rows = []
    for a in order:
        rec = asins.get(a, {})
        csv_title = rec.get("product_title_csv", "")
        csv_price = rec.get("price_csv", "")
        query = csv_title if by_title else a
        path = "/search/" + query
        try:
            conn = http.client.HTTPSConnection(host, timeout=60)
            conn.request("GET", path, headers=headers)
            res = conn.getresponse()
            status = res.status
            body = res.read().decode("utf-8", "replace")
            conn.close()
        except Exception as e:  # network/transport failure
            print("ASIN %s -> request error: %s; stopping" % (a, e), file=sys.stderr)
            break
        with open(os.path.join(raw_dir, a + ".json"), "w", encoding="utf-8") as f:
            f.write(body)
        if status != 200:
            print("ASIN %s -> HTTP %d; stopping (fail-fast)" % (a, status), file=sys.stderr)
            break
        try:
            j = json.loads(body)
        except Exception:
            j = None
        top_title, top_price = _extract_top(j)
        rows.append(
            {
                "asin": a,
                "query": query,
                "csv_title": csv_title,
                "csv_price": csv_price,
                "live_status": status,
                "live_top_title": top_title,
                "live_top_price": top_price,
            }
        )
        print(
            "ASIN %s -> 200 query=%s top=%r price=%r"
            % (a, query, top_title, top_price)
        )
        time.sleep(1.0)  # gentle rate limit, avoid hammering the endpoint

    csv_path = os.path.join(run_dir, "rapidapi-vs-csv-comparison.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "asin",
                "query",
                "csv_title",
                "csv_price",
                "live_status",
                "live_top_title",
                "live_top_price",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("wrote %s" % csv_path)
    print("saved %d raw responses to %s" % (len(rows), raw_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
