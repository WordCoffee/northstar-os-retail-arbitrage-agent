import os
import json
from typing import Dict, Any
from dotenv import load_dotenv
import requests

import live_gate

load_dotenv()

CANOPY_API_KEY = os.getenv("CANOPY_API_KEY")

PRODUCT_URL = "https://rest.canopyapi.co/api/amazon/product"
REQUEST_TIMEOUT_SECONDS = 30


def get_canopy_product(asin: str) -> dict:
    """Fetch product data from Canopy API and return a normalized safe dict.

    Returns the documented normalized shape in all cases (success, missing
    key, HTTP error, timeout, malformed JSON, or missing data.amazonProduct),
    never raising and never exposing the API key.
    """
    result: Dict[str, Any] = {
        "source": "canopy",
        "asin": asin,
        "title": None,
        "brand": None,
        "product_url": None,
        "amazon_price": None,
        "currency": None,
        "is_prime": None,
        "is_new": None,
        "is_in_stock": None,
        "image_url": None,
        "rating": None,
        "reviews_count": None,
        "seller_id": None,
        "seller_name": None,
        "categories": None,
        "technical_specifications": None,
        "coupon": None,
        "seller_count": None,
        "offers_count": None,
        "fulfillment": None,
        "is_fba": None,
        "is_fbm": None,
        "amazon_is_seller": None,
        "buy_box_price": None,
        "buy_box_seller": None,
        "data_gaps": [
            "Canopy product response did not provide seller count.",
            "Canopy product response did not provide offer list.",
            "Canopy product response did not explicitly identify FBA or FBM fulfillment.",
            "Canopy product response did not confirm Amazon as seller or Buy Box owner.",
        ],
    }

    if not live_gate.live_enabled():
        result["data_gaps"].append(live_gate.live_disabled_note())
        return result

    if not CANOPY_API_KEY:
        result["data_gaps"].append("Canopy API key is not configured.")
        return result

    headers = {"API-KEY": CANOPY_API_KEY}
    params = {"asin": asin, "domain": "US"}

    try:
        resp = requests.get(
            PRODUCT_URL,
            headers=headers,
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout:
        result["data_gaps"].append("Canopy request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["data_gaps"].append("Canopy request failed at the network level.")
        return result

    if resp.status_code != 200:
        result["data_gaps"].append(f"Canopy API returned HTTP {resp.status_code}.")
        return result

    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["data_gaps"].append("Canopy response was not valid JSON.")
        return result

    if not isinstance(payload, dict):
        result["data_gaps"].append("Canopy response had an unexpected structure.")
        return result

    data = payload.get("data")
    if not isinstance(data, dict):
        result["data_gaps"].append("Canopy response was missing data.amazonProduct.")
        return result

    amazon = data.get("amazonProduct")
    if not isinstance(amazon, dict):
        result["data_gaps"].append("Canopy response was missing data.amazonProduct.")
        return result

    price = amazon.get("price")
    price = price if isinstance(price, dict) else {}
    seller = amazon.get("seller")
    seller = seller if isinstance(seller, dict) else {}

    result["asin"] = amazon.get("asin") or asin
    result["title"] = amazon.get("title")
    result["brand"] = amazon.get("brand")
    result["product_url"] = amazon.get("url")
    result["amazon_price"] = price.get("value")
    result["currency"] = price.get("currency")
    result["is_prime"] = amazon.get("isPrime")
    result["is_new"] = amazon.get("isNew")
    result["is_in_stock"] = amazon.get("isInStock")
    result["image_url"] = amazon.get("mainImageUrl")
    result["rating"] = amazon.get("rating")
    result["reviews_count"] = amazon.get("ratingsTotal")
    result["seller_id"] = seller.get("sellerId")
    result["seller_name"] = seller.get("name")
    result["categories"] = amazon.get("categories")
    result["technical_specifications"] = amazon.get("technicalSpecifications")
    result["coupon"] = amazon.get("coupon")

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python canopy_client.py <ASIN>")
        sys.exit(1)
    product = get_canopy_product(sys.argv[1])
    print(json.dumps(product, indent=2, default=str))