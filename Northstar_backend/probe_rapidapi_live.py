"""Standalone, single-request RapidAPI viability probe (Northstar safety model).

- Exactly ONE outbound request.
- Reads RAPIDAPI_KEY / RAPIDAPI_HOST from the environment.
- Masks the key in all output.
- Does NOT write any snapshot, DB, or cache file.
"""

import json
import os
import re
import sys

import requests
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

ASIN = sys.argv[1] if len(sys.argv) > 1 else "B00F4MD808"
SUFFIX = sys.argv[2] if len(sys.argv) > 2 else ""
HOST = os.getenv("RAPIDAPI_HOST") or "amazon-product-data4.p.rapidapi.com"
KEY = os.getenv("RAPIDAPI_KEY") or ""
TIMEOUT = 20


def mask(text: str) -> str:
    if not KEY:
        return text
    return text.replace(KEY, "****")


def main():
    has_key = bool(KEY)
    print("=== RapidAPI Single Probe ===")
    print("ASIN            : %s" % ASIN)
    print("HOST            : %s" % HOST)
    print("Key configured  : %s" % ("YES" if has_key else "NO"))
    if not has_key:
        print("NOTE: no RAPIDAPI_KEY configured; firing one unauthenticated "
              "request to observe gateway/auth behavior.")

    path = "/products/%s%s" % (ASIN, ("/" + SUFFIX) if SUFFIX else "")
    url = "https://%s%s" % (HOST, path)
    headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST}
    print("URL             : %s" % url)
    print("Requests made   : 1 (bounded)")

    try:
        resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.exceptions.Timeout:
        print("RESULT: TIMEOUT after %ss" % TIMEOUT)
        return
    except requests.exceptions.RequestException as exc:
        print("RESULT: CONNECTION ERROR -> %s" % mask(str(exc)))
        return

    raw = resp.text or ""
    ct = resp.headers.get("Content-Type", "")
    print("HTTP Status     : %s" % resp.status_code)
    print("Content-Type    : %s" % ct)

    preview = mask(raw)[:500]
    print("--- Raw preview (first 500 chars, key masked) ---")
    print(preview)

    # Payload classification
    payload_kind = "unknown"
    data = None
    if "json" in ct.lower():
        try:
            data = resp.json()
            payload_kind = "valid_json"
        except ValueError:
            payload_kind = "json_content_type_but_invalid"
    elif "html" in ct.lower():
        payload_kind = "html_error_page"
    print("Payload status  : %s" % payload_kind)

    if isinstance(data, dict):
        # Field inventory
        def has_path(*keys):
            cur = data
            for k in keys:
                if isinstance(cur, dict) and k in cur:
                    cur = cur[k]
                else:
                    return False
            return True

        title = data.get("title") or (data.get("product") or {}).get("title")
        price = data.get("price") or (data.get("product") or {}).get("price") \
            or (data.get("product") or {}).get("buybox_price")
        offers = data.get("offers") or (data.get("product") or {}).get("offers") \
            or (data.get("product") or {}).get("sellers")
        bsr = data.get("bsr") or data.get("sales_rank") or data.get("salesRank") \
            or (data.get("product") or {}).get("bsr")
        buybox = data.get("buybox_winner") or (data.get("product") or {}).get("buybox_winner")

        print("--- Field inventory ---")
        print("title present        : %s" % ("YES" if title else "NO"))
        print("price/buybox present : %s" % ("YES" if price is not None else "NO"))
        print("BSR/ranks present    : %s" % ("YES" if bsr else "NO"))
        print("buybox_winner present: %s" % ("YES" if buybox else "NO"))
        print("offer roster present : %s (count=%s)" % (
            "YES" if isinstance(offers, list) and offers else "NO",
            len(offers) if isinstance(offers, list) else 0))

        # Dump top-level keys for schema inspection
        prod = data.get("product") if isinstance(data.get("product"), dict) else data
        print("top-level keys       : %s" % ", ".join(sorted(prod.keys()))[:300])

    # Technical verdict
    viable = (
        resp.status_code == 200
        and payload_kind == "valid_json"
        and isinstance(data, dict)
        and (data.get("title") or (data.get("product") or {}).get("title"))
    )
    print("=== VERDICT ===")
    if viable:
        print("RapidAPI VIABLE as a live provider for this ASIN.")
    else:
        print("RapidAPI NOT VIABLE (status=%s, payload=%s). "
              "Proceed with DataForSEO as the primary provider." % (
                  resp.status_code, payload_kind))


if __name__ == "__main__":
    main()
