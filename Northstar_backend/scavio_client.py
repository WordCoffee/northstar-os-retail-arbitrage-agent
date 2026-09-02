import os
from typing import List, Dict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

SCAVIO_API_KEY = os.getenv("SCAVIO_API_KEY")
SEARCH_KEYWORDS = os.getenv("SEARCH_KEYWORDS", "")
PAGES_TO_SEARCH = int(os.getenv("PAGES_TO_SEARCH", "1"))
DEFAULT_MARKETPLACE = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com")

# Set whenever the upstream could not be reached or returned an unusable
# response; cleared after any successful HTTP response is parsed. Lets the
# scanner endpoint distinguish "no candidates" from "upstream unavailable".
LAST_SEARCH_ERROR = None

if not SCAVIO_API_KEY:
    print("[Scavio] SCAVIO_API_KEY not set; search will be skipped")

AMAZON_SEARCH_URL = "https://api.scavio.dev/api/v1/amazon/search"


def search_kirkland_products(
    keywords: Optional[List[str]] = None,
    pages: Optional[int] = None,
) -> List[Dict]:
    global LAST_SEARCH_ERROR

    if not keywords:
        keywords = [kw.strip() for kw in SEARCH_KEYWORDS.split(",") if kw.strip()]
    if not pages or pages <= 0:
        pages = PAGES_TO_SEARCH

    if not SCAVIO_API_KEY:
        LAST_SEARCH_ERROR = "SCAVIO_API_KEY not set"
        print("[Scavio] SCAVIO_API_KEY not set; skipping search")
        return []

    results = []
    headers = {
        "Authorization": f"Bearer {SCAVIO_API_KEY}",
        "Content-Type": "application/json",
    }

    for keyword in keywords:
        try:
            payload = {
                "query": keyword,
                "domain": "com",
                "pages": pages,
            }

            response = requests.post(AMAZON_SEARCH_URL, json=payload, headers=headers, timeout=30)
            if response.status_code != 200:
                LAST_SEARCH_ERROR = f"HTTP {response.status_code}"
                print(f"[Scavio] {response.status_code} {response.text}")
                continue

            data = response.json()
            LAST_SEARCH_ERROR = None
            products = data.get("data", {}).get("products") or data.get("products") or data.get("results") or []

            for item in products:
                asin = item.get("asin") or item.get("id")
                name = item.get("title") or item.get("name")
                price_raw = item.get("price")
                if isinstance(price_raw, dict):
                    price_val = price_raw.get("value") or price_raw.get("current") or 0
                else:
                    price_val = price_raw or 0
                url = item.get("url") or item.get("link")

                results.append({
                        "asin": asin,
                        "name": name,
                        "amazon_price": float(price_val) if price_val else None,
                        "product_url": url,
                    })

        except requests.exceptions.RequestException as exc:
            # Typed transport failure: an auth/timeout/connection problem is
            # NEVER reported the same way as "no data found" — it is recorded
            # as transport_error and surfaced through LAST_SEARCH_ERROR.
            LAST_SEARCH_ERROR = "transport_error: %s" % exc
            print(f"[Scavio] transport_error: {exc}")
            continue

    return results