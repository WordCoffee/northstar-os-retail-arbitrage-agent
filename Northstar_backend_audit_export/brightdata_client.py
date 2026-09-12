import os
import time
import json
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv
import requests

load_dotenv()

BRIGHTDATA_API_KEY = os.getenv("BRIGHTDATA_API_KEY")
BRIGHTDATA_DATASET_ID = os.getenv("BRIGHTDATA_DATASET_ID")

_CACHE: Dict[str, Dict] = {}
_CACHE_LOCK = Lock()
TTL_SECONDS = 15 * 60


def validate_credentials() -> bool:
    """Check if required Bright Data credentials are present without revealing values."""
    if not BRIGHTDATA_API_KEY:
        print("[BrightData] Missing BRIGHTDATA_API_KEY in environment")
        return False
    if not BRIGHTDATA_DATASET_ID:
        print("[BrightData] Missing BRIGHTDATA_DATASET_ID in environment")
        return False
    print("[BrightData] Credentials configured: API_KEY present, DATASET_ID present")
    return True


def _normalize_result(asin_or_url: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize Bright Data response into consistent internal dict."""
    def _safe_int(val, default=None):
        if val is None:
            return default
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _safe_float(val, default=None):
        if val is None:
            return default
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    def _safe_bool(val, default=None):
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes", "fba")
        return bool(val)

    sellers = []
    seller_names = []
    seller_ids = []
    fulfillment_types = []
    is_fba_list = []
    is_fbm_list = []

    offers = result.get("offers") or result.get("offer_data") or []
    if isinstance(offers, list):
        for offer in offers:
            if isinstance(offer, dict):
                sellers.append(offer)
                seller_names.append(offer.get("seller_name") or offer.get("name"))
                seller_ids.append(offer.get("seller_id") or offer.get("id"))
                fulfillment = offer.get("fulfillment") or offer.get("fulfillment_type") or offer.get("fulfillment_method")
                fulfillment_types.append(fulfillment)
                if fulfillment:
                    is_fba_list.append("fba" in str(fulfillment).lower() or "fulfilled by amazon" in str(fulfillment).lower())
                    is_fbm_list.append("fbm" in str(fulfillment).lower() or "merchant" in str(fulfillment).lower() or "seller fulfilled" in str(fulfillment).lower())
                else:
                    is_fba_list.append(None)
                    is_fbm_list.append(None)

    lowest_price = _safe_float(result.get("lowest_price") or result.get("min_price"))
    highest_price = _safe_float(result.get("highest_price") or result.get("max_price"))
    buy_box_price = _safe_float(result.get("buy_box_price") or result.get("final_price") or result.get("current_price"))
    amazon_price = buy_box_price if buy_box_price is not None else lowest_price

    total_offers = _safe_int(result.get("total_offer_count") or result.get("offers_count") or result.get("total_sellers"))
    fba_offers = _safe_int(result.get("fba_offer_count") or result.get("fba_count"))
    fbm_offers = _safe_int(result.get("fbm_offer_count") or result.get("fbm_count"))

    amazon_is_seller = result.get("amazon_is_seller") or result.get("is_amazon_seller")
    if amazon_is_seller is None and offers:
        for offer in offers:
            name = offer.get("seller_name", "").lower()
            if "amazon" in name:
                amazon_is_seller = True
                break
        else:
            amazon_is_seller = False

    buy_box_seller = result.get("buy_box_seller") or result.get("buy_box_owner")
    availability = result.get("availability") or result.get("stock_status") or result.get("in_stock")
    fba_fee = _safe_float(
        result.get("fba_fee")
        or result.get("fulfillment_fee")
        or result.get("estimated_fba_fee")
        or result.get("fba_fulfillment_fee")
    )
    monthly_sales_estimate = _safe_float(
        result.get("monthly_sales")
        or result.get("monthly_sold")
        or result.get("sales_last_month")
    )

    normalized = {
        "asin": asin_or_url,
        "title": result.get("title") or result.get("product_title") or result.get("name"),
        "amazon_price": amazon_price,
        "buy_box_price": buy_box_price,
        "seller_count": total_offers,
        "offers_count": total_offers,
        "fba_sellers": fba_offers,
        "sellers": sellers,
        "seller_name": seller_names[0] if seller_names else None,
        "seller_id": seller_ids[0] if seller_ids else None,
        "fulfillment": fulfillment_types[0] if fulfillment_types else None,
        "is_fba": is_fba_list[0] if is_fba_list else None,
        "is_fbm": is_fbm_list[0] if is_fbm_list else None,
        "amazon_is_seller": amazon_is_seller,
        "buy_box_seller": buy_box_seller,
        "availability": availability,
        "fba_fee": fba_fee,
        "monthly_sales_estimate": monthly_sales_estimate,
        "monthly_sales_estimated": monthly_sales_estimate is not None,
        "product_url": result.get("url") or result.get("product_url") or (f"https://www.amazon.com/dp/{asin_or_url}" if len(asin_or_url) == 10 else asin_or_url),
        "raw_source": result,
    }

    return normalized


def enrich_product(asin_or_url: str) -> Optional[Dict[str, Any]]:
    """Submit an Amazon ASIN or URL to Bright Data dataset and return normalized result."""
    if not validate_credentials():
        return None

    key = asin_or_url.lower().strip()
    now = datetime.now()

    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and (now - cached["ts"]) < timedelta(seconds=TTL_SECONDS):
            print(f"[BrightData] Cache hit for {asin_or_url}")
            return cached["data"]

    headers = {
        "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
        "Content-Type": "application/json",
    }

    trigger_url = (
        f"https://api.brightdata.com/datasets/v3/trigger"
        f"?dataset_id={BRIGHTDATA_DATASET_ID}&format=json"
    )
    if "amazon.com" in asin_or_url or "amzn.com" in asin_or_url:
        payload = {"keyword": asin_or_url, "url": asin_or_url}
    else:
        payload = {"keyword": asin_or_url, "url": f"https://www.amazon.com/dp/{asin_or_url}"}

    try:
        print(f"[BrightData] Triggering job for {asin_or_url}")
        resp = requests.post(trigger_url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 401:
            print("[BrightData] Unauthorized - check API key")
            return None
        if resp.status_code == 404:
            print("[BrightData] Dataset not found - check DATASET_ID")
            return None
        if resp.status_code != 200:
            print(f"[BrightData trigger] {resp.status_code} {resp.text[:200]}")
            return None

        job_data = resp.json()
        snapshot_id = job_data.get("snapshot_id")
        job_id = job_data.get("job_id") or job_data.get("id")
        if not snapshot_id and not job_id:
            print(f"[BrightData] No snapshot_id/job_id in response: {job_data}")
            return None

        if snapshot_id:
            poll_url = f"https://api.brightdata.com/datasets/v3/progress/{snapshot_id}?format=json"
            download_url = f"https://api.brightdata.com/datasets/v3/snapshot/{snapshot_id}?format=json"
        else:
            poll_url = f"https://api.brightdata.com/datasets/v3/jobs/{job_id}?format=json"
            download_url = None

        for attempt in range(30):
            try:
                poll_resp = requests.get(poll_url, headers=headers, timeout=30)
                if poll_resp.status_code != 200:
                    print(f"[BrightData poll] {poll_resp.status_code} {poll_resp.text[:200]}")
                    time.sleep(2)
                    continue

                jd = poll_resp.json()
                status = jd.get("status") or jd.get("state")

                if status in ("completed", "success", "done", "ready"):
                    if download_url:
                        dl_resp = requests.get(download_url, headers=headers, timeout=30)
                        if dl_resp.status_code != 200:
                            print(f"[BrightData download] {dl_resp.status_code} {dl_resp.text[:200]}")
                            time.sleep(2)
                            continue
                        dl = dl_resp.json()
                        if isinstance(dl, list):
                            results = dl
                        elif isinstance(dl, dict):
                            results = dl.get("results") or dl.get("data") or dl.get("items") or [dl]
                        else:
                            results = []
                    else:
                        results = jd.get("results") or jd.get("data") or jd.get("items") or []
                    if not results:
                        print("[BrightData] Job completed but no results returned")
                        normalized = _normalize_result(asin_or_url, {})
                        normalized["raw_source"] = jd
                    else:
                        result = results[0] if isinstance(results, list) else results
                        normalized = _normalize_result(asin_or_url, result)

                    with _CACHE_LOCK:
                        _CACHE[key] = {"ts": now, "data": normalized}
                    return normalized

                if status in ("failed", "error", "cancelled"):
                    print(f"[BrightData] Job failed: {jd.get('error') or jd.get('message') or jd}")
                    return None

                print(f"[BrightData] Job status: {status}, waiting... (attempt {attempt + 1}/30)")
                time.sleep(2)

            except requests.exceptions.Timeout:
                print(f"[BrightData] Poll timeout, retrying...")
                continue
            except requests.exceptions.RequestException as e:
                print(f"[BrightData] Poll request error: {e}")
                time.sleep(2)
                continue
            except json.JSONDecodeError as e:
                print(f"[BrightData] Invalid JSON in poll response: {e}")
                time.sleep(2)
                continue

        print("[BrightData] Job did not complete in time (60s timeout)")
        return None

    except requests.exceptions.Timeout:
        print("[BrightData] Trigger request timeout")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[BrightData] Trigger request error: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[BrightData] Invalid JSON in trigger response: {e}")
        return None
    except Exception as e:
        print(f"[BrightData] Unexpected error: {type(e).__name__}: {e}")
        return None


def get_offer_data(identifier):
    """Safe offline compatibility wrapper for product_analysis.get_offer_data().

    Performs zero Bright Data network calls and never calls enrich_product().
    Returns a truthy placeholder dict in the exact shape analyze_kirkland_products()
    expects: amazon_price=0 makes product_analysis fall back to the candidate's
    own price from the Scavio search, so discovery keeps working when Bright
    Data enrichment is unavailable.
    """
    return {
        "amazon_price": 0,
        "buy_box_price": None,
        "lowest_price": None,
        "highest_price": None,
        "total_sellers": None,
        "fba_sellers": None,
        "fba_sellers_estimated": False,
        "lowest_price_seller_type": "unknown",
        "highest_price_seller_type": "unknown",
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
        "fba_fee": None,
        "amazon_category": None,
        "browse_node_id": None,
        "breadcrumb": None,
        "category_source_hint": None,
    }


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python brightdata_client.py <ASIN or Amazon URL>")
        sys.exit(1)
    result = enrich_product(sys.argv[1])
    if result:
        print(json.dumps(result, indent=2, default=str))
    else:
        print("No result returned")