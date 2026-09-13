#!/usr/bin/env python
"""
LIVE Scavio discovery proof (approved: "GO LIVE — Scavio first").
Pulls real Kirkland ASINs from the Scavio Amazon search API (free tier, 0 credits),
saves raw response + prepared manifest for the 470-inventory aggregation.
Writes proof JSON + log for the operator's review; no other live provider touched.
"""
import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv:
    load_dotenv(ROOT / "Northstar_backend" / ".env")
elif os.path.exists(ROOT / "Northstar_backend" / ".env"):
    for line in (ROOT / "Northstar_backend" / ".env").read_text().splitlines():
        if line and not line.strip().startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

import urllib.request
import urllib.error

DATA_CATALOG = ROOT / "Northstar_backend" / "data" / "catalog"
OUTPUT_DIR = ROOT / "generated_images" / "screenshots"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SCAVIO_URL = os.getenv("SCAVIO_API_URL", "https://api.scavio.dev/api/v1")
SCAVIO_KEY = os.getenv("SCAVIO_API_KEY", "")


def api_available() -> bool:
    """True only if URL + key are set (fail-closed)."""
    return bool(SCAVIO_URL and SCAVIO_KEY and SCAVIO_KEY not in ("", "your_key_here"))


def fetch_live(query: str = "Kirkland", pages: int = 3) -> tuple:
    """
    Live Scavio search call. Returns (status_code, response_dict_or_None).
    One request per page — free tier, no credit cost on Scavio.
    """
    # Try both common endpoint shapes defensively
    attempts = [
        f"{SCAVIO_URL}/amazon/search",
        f"{SCAVIO_URL}/scrape/amazon/search",
    ]
    headers = {
        "Authorization": f"Bearer {SCAVIO_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_err = None
    for url in attempts:
        for attempt in range(2):  # one retry per URL
            payload = json.dumps({
                "query": query,
                "pages": pages,
                "marketplace": "com",
            }).encode()
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                    try:
                        data = json.loads(body)
                    except ValueError:
                        data = {"raw_html_prefix": body[:200].decode("utf-8", "replace")}
                    return r.status, data
            except urllib.error.HTTPError as e:
                last_err = f"{url}: HTTP {e.code} {e.reason}"
                # 404/405 -> try next endpoint shape
                if e.code in (404, 405):
                    continue
                try:
                    return e.code, {"error": e.read()[:500].decode("utf-8", "replace")}
                except Exception:
                    return e.code, {"error": str(e)}
            except Exception as e:
                last_err = f"{url}: {e}"
                break  # connection errors -> next URL
    return 0, {"error": last_err or "all endpoints failed"}


def extract_asins(data: dict) -> list:
    """Extract ASIN + enrichment-ready fields from Scavio response (tolerates shapes)."""
    out = []
    # Step down through likely containers
    containers = [
        data.get("data", {}).get("products"),
        data.get("data", {}).get("items"),
        data.get("products"),
        data.get("items"),
        data.get("results"),
    ]
    items = []
    for c in containers:
        if isinstance(c, list):
            items = c
            break
        if isinstance(c, dict) and c.get("products"):
            items = c["products"]
            break
    if not items and isinstance(data.get("data"), list):
        items = data["data"]

    for item in (items or []):
        if not isinstance(item, dict):
            continue
        asin = (
            item.get("asin")
            or (item.get("product", {}) or {}).get("asin")
            or item.get("asin_id")
        )
        if not asin or not (str(asin).startswith("B0")):
            continue
        title = (
            item.get("title")
            or item.get("name")
            or (item.get("product", {}) or {}).get("title")
            or ""
        )
        price = item.get("price") or (item.get("price_info", {}) or {}).get("current")
        price_num = None
        if isinstance(price, dict):
            price_num = price.get("value") or price.get("current")
        elif isinstance(price, (int, float)):
            price_num = price
        out.append({
            "asin": str(asin),
            "title": title,
            "brand": item.get("brand") or "Kirkland Signature",
            "amazon_price": price_num,
            "product_url": item.get("url") or item.get("product_url"),
            "stars": item.get("star_rating") or item.get("rating"),
            "raw": item,
        })
    # de-dup
    uniq = {}
    for o in out:
        uniq[o["asin"]] = o
    return list(uniq.values())


def main():
    print("=== LIVE SCAVIO DISCOVERY — KIRKLAND (free tier, 0 credits) ===\n")

    if not api_available():
        print("ERROR: SCAVIO_API_URL or SCAVIO_API_KEY missing in .env (fail-closed).")
        print(f"  URL set: {bool(SCAVIO_URL)}  Key set: {bool(SCAVIO_KEY)}")
        return 1

    print(f"Endpoint: {SCAVIO_URL.rsplit('/', 1)[-1]}  (URL + key configured)")
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    query = os.getenv("SEARCH_QUERY", "Kirkland")
    pages = 3

    print(f"Firing live search: query='{query}' pages={pages} ...")
    status, data = fetch_live(query, pages)
    print(f"HTTP {status}")

    if status and 200 <= status < 300:
        asins = extract_asins(data)
        print(f"FOUND {len(asins)} real Kirkland ASINs\n")
        for a in asins[:10]:
            print(f"  {a['asin']}  {str(a['title'])[:60]}")

        # Save raw + prepared
        raw_path = DATA_CATALOG / f"scavio_live_raw_{ts}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(data, indent=2, default=str))
        print(f"\nRaw response: {raw_path}")

        prepared = {
            "kind": "scavio_live_discovery",
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "SCAVIO",
            "query": query,
            "pages": pages,
            "count": len(asins),
            "items": [{k: v for k, v in a.items() if k != "raw"} for a in asins],
            "_raw_file": str(raw_path.name),
        }
        prep_path = DATA_CATALOG / f"scavio_live_discovery_{ts}.json"
        prep_path.write_text(json.dumps(prepared, indent=2))

        # Append to aggregator-consumable sidecar manifest (merge on next build)
        sidecar = DATA_CATALOG / "scavio_live_sidecar.json"
        side_data = {"scavio_live_files": []}
        if sidecar.exists():
            try:
                side_data = json.loads(sidecar.read_text())
            except Exception:
                pass
        side_data["scavio_live_files"].append(str(prep_path.name))
        sidecar.write_text(json.dumps(side_data, indent=2))

        print(f"Prepared manifest: {prep_path}")
        print(f"Sidecar updated:   {sidecar.name}")
        return 0
    else:
        print(f"LIVE CALL UNSUCCESSFUL (HTTP {status}):")
        print(json.dumps(data, indent=2)[:2000])
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
