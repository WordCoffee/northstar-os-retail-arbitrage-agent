import os
import re
import json
from typing import Dict, Any, List
from dotenv import load_dotenv
import requests

load_dotenv()

EASYPARSER_API_KEY = os.getenv("EASYPARSER_API_KEY")

EASYPARSER_URL = "https://realtime.easyparser.com/v1/request"
REQUEST_TIMEOUT_SECONDS = 60

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")


def _safe_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    seller = offer.get("seller")
    seller = seller if isinstance(seller, dict) else {}
    seller_type = offer.get("seller_type")
    seller_type = seller_type if isinstance(seller_type, dict) else {}
    delivery = offer.get("delivery")
    delivery = delivery if isinstance(delivery, dict) else {}
    delivery_price = delivery.get("price")
    delivery_price = delivery_price if isinstance(delivery_price, dict) else {}
    price = offer.get("price")

    return {
        "position": offer.get("position"),
        "buybox_winner": offer.get("buybox_winner"),
        "price": price,
        "condition": offer.get("condition"),
        "seller_id": seller.get("id"),
        "seller_name": seller.get("name"),
        "seller_rating": seller.get("rating"),
        "seller_positive_percentage": seller.get("ratings_percentage_positive"),
        "seller_ratings_total": seller.get("ratings_total"),
        "is_prime": offer.get("is_prime"),
        "is_fba": seller_type.get("fba"),
        "is_fbm": seller_type.get("fbm"),
        "is_sba": seller_type.get("sba"),
        "fulfilled_by_amazon": delivery.get("fulfilled_by_amazon"),
        "shipping_text": delivery.get("text"),
        "shipping_is_free": delivery_price.get("is_free"),
        "ships_from": offer.get("ships_from"),
        "minimum_order_quantity": offer.get("minimum_order_quantity"),
        "maximum_order_quantity": offer.get("maximum_order_quantity"),
    }


def get_easyparser_offers(asin: str) -> dict:
    """Fetch Amazon offer data from Easyparser and return a normalized safe dict.

    Makes one GET request only when explicitly called. Returns the documented
    normalized shape for every outcome (missing key, invalid ASIN, timeout,
    network/HTTP failure, invalid JSON, request_info.success false, or missing
    result data) and never raises.
    """
    result: Dict[str, Any] = {
        "source": "easyparser",
        "asin": None,
        "provider_asin": None,
        "request_id": None,
        "title": None,
        "offer_count": None,
        "offers_returned_count": 0,
        "buy_box_price": None,
        "buy_box_price_raw": None,
        "buy_box_seller": None,
        "buy_box_seller_id": None,
        "buy_box_is_fba": None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 0,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 0,
        "offers": [],
        "request_zip_code": None,
        "observed_at": None,
        "credits_used": None,
        "credits_remaining": None,
        "data_gaps": [
            "Returned offers may be a subset of the total offer_count; pagination and completeness are not verified.",
            "Results are ZIP-code and time specific.",
        ],
    }

    if not EASYPARSER_API_KEY:
        result["data_gaps"].append("Easyparser API key is not configured.")
        return result

    if not asin or not ASIN_PATTERN.fullmatch(asin):
        result["data_gaps"].append("Invalid ASIN. Expected exactly 10 alphanumeric characters.")
        return result

    params = {
        "api_key": EASYPARSER_API_KEY,
        "platform": "AMZ",
        "operation": "OFFER",
        "domain": ".com",
        "asin": asin,
    }

    try:
        resp = requests.get(EASYPARSER_URL, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        result["data_gaps"].append("Easyparser request timed out.")
        return result
    except requests.exceptions.RequestException:
        result["data_gaps"].append("Easyparser request failed at the network level.")
        return result

    if resp.status_code != 200:
        result["data_gaps"].append(f"Easyparser API returned HTTP {resp.status_code}.")
        return result

    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        result["data_gaps"].append("Easyparser response was not valid JSON.")
        return result

    if not isinstance(payload, dict):
        result["data_gaps"].append("Easyparser response had an unexpected structure.")
        return result

    request_info = payload.get("request_info")
    request_info = request_info if isinstance(request_info, dict) else {}
    request_metadata = payload.get("request_metadata")
    request_metadata = request_metadata if isinstance(request_metadata, dict) else {}

    if request_info.get("success") is False:
        result["data_gaps"].append("Easyparser reported request failure (request_info.success is false).")
        return result

    address = request_info.get("address")
    address = address if isinstance(address, dict) else {}
    zip_code = address.get("zipCode")
    if isinstance(zip_code, list):
        zip_code = zip_code[0] if zip_code and isinstance(zip_code[0], str) else None
    elif zip_code is not None and not isinstance(zip_code, str):
        zip_code = str(zip_code)
    result["request_zip_code"] = zip_code
    result["observed_at"] = request_metadata.get("processed_at") or request_metadata.get("created_at")
    result["request_id"] = request_info.get("request_id")
    result["credits_used"] = request_info.get("credits_used")
    result["credits_remaining"] = request_info.get("credits_remaining")

    result_data = payload.get("result")
    if not isinstance(result_data, dict):
        result["data_gaps"].append("Easyparser response was missing result data.")
        return result

    product = result_data.get("product")
    if not isinstance(product, dict):
        result["data_gaps"].append("Easyparser response was missing result.product.")
        return result

    result["provider_asin"] = product.get("asin")
    result["asin"] = product.get("asin") or asin
    result["title"] = product.get("title")
    result["offer_count"] = product.get("offer_count")

    offer_block = result_data.get("offer")
    offer_results = offer_block.get("offer_results") if isinstance(offer_block, dict) else None
    if not isinstance(offer_results, list):
        result["data_gaps"].append("Easyparser response was missing result.offer.offer_results.")
        return result

    result["offers_returned_count"] = len(offer_results)

    fba_count = 0
    fbm_count = 0
    amazon_count = 0
    buy_box = None
    for offer in offer_results:
        if not isinstance(offer, dict):
            continue
        normalized = _safe_offer(offer)
        seller_type = offer.get("seller_type")
        seller_type = seller_type if isinstance(seller_type, dict) else {}
        if seller_type.get("fba") is True:
            fba_count += 1
        if seller_type.get("fbm") is True:
            fbm_count += 1
        seller_name = normalized["seller_name"]
        if isinstance(seller_name, str) and seller_name.strip() == "Amazon.com":
            amazon_count += 1
        result["offers"].append(normalized)
        if offer.get("buybox_winner") is True and buy_box is None:
            buy_box = normalized

    result["observed_fba_offer_count"] = fba_count
    result["observed_fbm_offer_count"] = fbm_count
    result["observed_amazon_offer_count"] = amazon_count

    if buy_box is not None:
        price_obj = buy_box["price"]
        price_value = None
        if isinstance(price_obj, dict):
            raw_value = price_obj.get("value")
            if isinstance(raw_value, bool):
                price_value = None
            elif isinstance(raw_value, (int, float)):
                price_value = float(raw_value)
            elif isinstance(raw_value, str):
                try:
                    price_value = float(raw_value)
                except ValueError:
                    price_value = None
        elif isinstance(price_obj, bool):
            price_value = None
        elif isinstance(price_obj, (int, float)):
            price_value = float(price_obj)
        result["buy_box_price"] = price_value
        result["buy_box_price_raw"] = price_obj
        result["buy_box_seller"] = buy_box["seller_name"]
        result["buy_box_seller_id"] = buy_box["seller_id"]
        result["buy_box_is_fba"] = buy_box["is_fba"]
        result["buy_box_is_fbm"] = buy_box["is_fbm"]
        result["buy_box_is_prime"] = buy_box["is_prime"]
        result["buy_box_condition"] = buy_box["condition"]

    return result


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python easyparser_client.py <ASIN>")
        sys.exit(1)
    data = get_easyparser_offers(sys.argv[1])
    print(json.dumps(data, indent=2, default=str))