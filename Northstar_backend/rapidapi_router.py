"""RapidAPI 6-host pool router with quota-drain failover (Northstar safety model).

Design
------
* One master RAPIDAPI_KEY; six host endpoints loaded from the .env pool.
* For each ASIN, a host is chosen at RANDOM from the still-active `apiPool`.
* HTTP 200 -> normalize + save, advance to next ASIN.
* HTTP 403 / 429 (quota / forbidden / hard rate limit) -> the host is
  DRAINED from the pool permanently for this run; the same ASIN is retried
  on a new random remaining host.
* Terminates when all ASINs are done OR the pool is empty (all 6 drained).

Safety
------
* LIVE is OFF by default. Set RAPIDAPI_POOL_LIVE=1 to actually call the
  network. Without it the script does a dry-run: loads config, prints the
  plan, and validates the normalization middleware against a synthetic
  payload (no network, no credits).
* No secrets are printed. The master key is read from the environment only.
* All normalization is null-first: a field the provider does not return is
  None (never 0, never invented).
"""

import asyncio
import json
import os
import random
import re
import sys

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
KEY = os.getenv("RAPIDAPI_KEY") or ""

# Pool of host env-var names -> resolved host. Only these 6 are active.
HOST_ENV_KEYS = [
    "RAPIDAPI_HOST_BDC",
    "RAPIDAPI_HOST_REALTIME",
    "RAPIDAPI_HOST_AXESSO",
    "RAPIDAPI_HOST_PRICING",
    "RAPIDAPI_HOST_ONLINE",
    "RAPIDAPI_HOST_SCOUT",
]

# Per-host request path. VERIFY these against each provider's real route;
# they are best-effort defaults. Override via RAPIDAPI_PATH_<KEY>.
HOST_PATH_TEMPLATES = {
    "RAPIDAPI_HOST_BDC": "/product/{asin}",
    "RAPIDAPI_HOST_REALTIME": "/product-offers?asin={asin}&country=US",
    "RAPIDAPI_HOST_AXESSO": "/amz/amazon-lookup-product?url=https%3A%2F%2Fwww.amazon.com%2Fdp%2F{asin}",
    "RAPIDAPI_HOST_PRICING": "/?asin={asin}&domain=com",
    "RAPIDAPI_HOST_ONLINE": "/stock?asins={asin}&geo=US",
    "RAPIDAPI_HOST_SCOUT": "/product/{asin}",
}

ASIN_FILE = os.getenv("RAPIDAPI_ASIN_FILE", "data/rapidapi_asin_targets.txt")
RESULTS_PATH = os.getenv("RAPIDAPI_RESULTS_PATH", "data/rapidapi_pool_results.json")
NORMALIZED_PATH = os.getenv("RAPIDAPI_NORMALIZED_PATH", "data/rapidapi_pool_normalized.json")

LIVE = os.getenv("RAPIDAPI_POOL_LIVE") == "1"
REQUEST_TIMEOUT = 20
MAX_ATTEMPTS_PER_ASIN = 8  # hard cap to prevent retry storms


def _path_for(env_key: str, asin: str) -> str:
    tmpl = os.getenv("RAPIDAPI_PATH_%s" % env_key) \
        or HOST_PATH_TEMPLATES.get(env_key, "/products/{asin}")
    return tmpl.format(asin=asin)


def _mask(text: str) -> str:
    return text.replace(KEY, "****") if KEY else text


# ---------------------------------------------------------------------------
# Normalization middleware (null-first; never invents values)
# ---------------------------------------------------------------------------
def _find_any(obj, names, _seen=None):
    """DFS a JSON structure; return the first non-None value whose key matches."""
    if _seen is None:
        _seen = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in names and v is not None:
                return v
            if isinstance(v, (dict, list)):
                r = _find_any(v, names, _seen)
                if r is not None:
                    return r
    elif isinstance(obj, list):
        for it in obj:
            r = _find_any(it, names, _seen)
            if r is not None:
                return r
    return None


_TITLE_KEYS = ["title", "name", "product_title", "item_name", "productTitle"]
_PRICE_KEYS = ["price", "current_price", "buybox_price", "price_current",
               "listing_price", "amount", "currentPrice"]
_REVIEWS_KEYS = ["reviews_count", "review_count", "reviews", "rating_count",
                 "total_reviews", "reviewsCount"]
_BSR_KEYS = ["bsr", "sales_rank", "salesRank", "best_sellers_rank", "rank",
             "bestsellers_rank"]


def _to_float(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    if isinstance(v, str):
        digits = re.sub(r"[^0-9.]", "", v)
        if digits:
            try:
                return float(digits)
            except ValueError:
                return None
    return None


def _to_int(v):
    f = _to_float(v)
    return int(f) if f is not None else None


def normalize_real_time(asin: str, data: dict) -> dict:
    """real-time-amazon-data mapper: extracts the exact observed keys.

    The real product payload is nested under data["data"]: product_title,
    product_price (string), product_offers[] (seller/price/condition/ships_from),
    main_buy_box (price/seller/seller_id), product_information["Best Sellers Rank"]
    (or product_details), is_prime/is_amazon_choice/is_best_seller, product_num_offers.
    Null-first: anything absent stays None.
    """
    product = data.get("data", data) if isinstance(data, dict) else {}

    title = product.get("product_title")
    price = _to_float(product.get("product_price"))
    original = _to_float(product.get("product_original_price"))
    star = _to_float(product.get("product_star_rating"))
    num = _to_int(product.get("product_num_ratings"))

    # BSR string lives in product_information / product_details "Best Sellers Rank".
    bsr_raw = None
    for sec in ("product_information", "product_details"):
        sec_d = product.get(sec)
        if isinstance(sec_d, dict) and sec_d.get("Best Sellers Rank"):
            bsr_raw = sec_d.get("Best Sellers Rank")
            break

    is_prime = product.get("is_prime")
    is_amazon_choice = product.get("is_amazon_choice")
    is_best_seller = product.get("is_best_seller")
    prime_fba_status = "PRIME" if is_prime is True else None

    # Buy Box winner = main_buy_box.
    bb = product.get("main_buy_box")
    buy_box_status = None
    if isinstance(bb, dict) and bb.get("price") is not None:
        seller = bb.get("seller")
        buy_box_status = {
            "available": True,
            "price": _to_float(bb.get("price")),
            "seller": seller,
            "seller_id": bb.get("seller_id"),
            "is_prime": is_prime,
            "fulfillment": "FBA" if (seller and "amazon" in str(seller).lower()) else None,
        }

    # Offer roster = product_offers[] (no per-offer FBA flag; infer from seller/ships_from).
    offers = product.get("product_offers")
    seller_data = None
    if isinstance(offers, list):
        seller_data = []
        for o in offers:
            if not isinstance(o, dict):
                continue
            seller = o.get("seller")
            ships = o.get("ships_from")
            is_fba = None
            if seller and "amazon" in str(seller).lower():
                is_fba = True
            elif ships and "amazon" in str(ships).lower():
                is_fba = True
            seller_data.append({
                "seller_name": seller,
                "seller_id": o.get("seller_id"),
                "price": _to_float(o.get("product_price")),
                "original_price": _to_float(o.get("product_original_price")),
                "condition": o.get("product_condition"),
                "is_fba": is_fba,
                "ships_from": ships,
            })

    return {
        "asin": asin,
        "source_host": os.getenv("RAPIDAPI_HOST_REALTIME"),
        "title": title,
        "price": price,
        "original_price": original,
        "reviews": num,
        "star_rating": star,
        "bsr": bsr_raw,
        "is_prime": is_prime,
        "is_amazon_choice": is_amazon_choice,
        "is_best_seller": is_best_seller,
        "prime_fba_status": prime_fba_status,
        "buy_box_status": buy_box_status,
        "seller_data": seller_data,
        "num_offers": _to_int(product.get("product_num_offers")),
    }


def to_intel_market_real_time(asin: str, data: dict) -> dict:
    """Build an intel_schema facts.market dict from a real-time payload."""
    from intel_schema import normalize_bsr
    u = normalize_real_time(asin, data)
    bb = u["buy_box_status"] or {}
    offers = u["seller_data"] or []

    fba_observed = sum(1 for o in offers if o.get("is_fba") is True)
    fbm_observed = sum(1 for o in offers if o.get("is_fba") is False)
    # No per-offer FBA/FBM flag is exposed by this provider; if every offer is
    # unresolved, report unknown (None) rather than implying 0 FBA/FBM.
    if offers and fba_observed == 0 and fbm_observed == 0:
        fba_observed = fbm_observed = None

    if offers:
        if u["num_offers"] is not None and len(offers) < u["num_offers"]:
            status = "partial"
            reason = "returned %d of %d claimed offers" % (len(offers), u["num_offers"])
        else:
            status = "full"
            reason = "rapidapi realtime product_offers roster"
    else:
        status = "unknown"
        reason = "no roster returned"

    return {
        "amazon_price": u["price"],
        "bsr": normalize_bsr(u["bsr"], source="rapidapi_realtime"),
        "buy_box": {
            "available": bool(u["buy_box_status"]),
            "price": bb.get("price"),
            "seller_name": bb.get("seller"),
            "seller_id": bb.get("seller_id"),
            "fulfillment": bb.get("fulfillment"),
            "source": "rapidapi_realtime",
            "observed_at": None,
        },
        "seller_counts": {
            "total_observed": len(offers),
            "fba_observed": fba_observed,
            "fbm_observed": fbm_observed,
            "amazon_observed": 0,
            "claimed_total": u["num_offers"],
        },
        "coverage": {
            "offer_list_available": len(offers) > 0,
            "offers_complete_status": status,
            "coverage_reason": reason,
        },
        "offers": offers,
    }


def _normalize(host_key: str, asin: str, data: dict) -> dict:
    """Map any provider payload into the unified shape."""
    if host_key == "RAPIDAPI_HOST_REALTIME":
        return normalize_real_time(asin, data)
    title = _find_any(data, _TITLE_KEYS)
    price = _to_float(_find_any(data, _PRICE_KEYS))
    reviews = _to_int(_find_any(data, _REVIEWS_KEYS))
    bsr = _find_any(data, _BSR_KEYS)

    # prime_fba_status: best-effort from known fulfillment signals.
    fba_flag = _find_any(data, ["is_fba", "fulfillment_channel", "isFba",
                                "prime", "is_prime"])
    prime_fba_status = None
    if isinstance(fba_flag, str):
        low = fba_flag.lower()
        if "fba" in low or low == "amazon":
            prime_fba_status = "FBA"
        elif "fbm" in low or "merchant" in low:
            prime_fba_status = "FBM"
        elif "prime" in low:
            prime_fba_status = "PRIME"
    elif fba_flag is True:
        prime_fba_status = "FBA"

    # buy_box_status: nested object if present, else None.
    bb = _find_any(data, ["buybox", "buy_box", "buyBox", "buybox_winner"])
    buy_box_status = None
    if isinstance(bb, dict):
        buy_box_status = {
            "available": True,
            "price": _to_float(bb.get("price") or bb.get("buybox_price")),
            "seller": bb.get("seller_name") or bb.get("seller"),
            "is_prime": bb.get("is_prime") or bb.get("prime"),
        }
    elif bb is not None:
        buy_box_status = {"available": True, "raw": bb}

    # seller_data: list of offers/sellers when present.
    seller_data = _find_any(data, ["offers", "sellers", "seller_list",
                                    "buybox_sellers", "sellers_list"])
    if not isinstance(seller_data, list):
        seller_data = None

    return {
        "asin": asin,
        "source_host": os.getenv(host_key),
        "title": title,
        "price": price,
        "reviews": reviews,
        "bsr": bsr,
        "prime_fba_status": prime_fba_status,
        "buy_box_status": buy_box_status,
        "seller_data": seller_data,
    }


# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
def _fetch(host: str, asin: str) -> tuple:
    """Synchronous GET; returns (status, payload_or_None). Blocks; run in thread."""
    url = "https://%s%s" % (host, _path_for(_env_key_for_host(host), asin))
    headers = {"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": host}
    try:
        resp = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        return (-1, {"error": _mask(str(exc))})
    status = resp.status_code
    try:
        payload = resp.json()
    except ValueError:
        payload = {"raw_text": _mask(resp.text[:500])}
    return (status, payload)


def _env_key_for_host(host: str):
    for k in HOST_ENV_KEYS:
        if os.getenv(k) == host:
            return k
    return HOST_ENV_KEYS[0]


async def _fetch_async(host: str, asin: str) -> tuple:
    return await asyncio.to_thread(_fetch, host, asin)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
async def run_router(asins: list, verbose: bool = True) -> dict:
    pool = [os.getenv(k) for k in HOST_ENV_KEYS if os.getenv(k)]
    if not pool:
        raise RuntimeError("No active RapidAPI hosts in pool (check .env).")
    if not KEY:
        raise RuntimeError("RAPIDAPI_KEY is not set in the environment.")

    results = {}
    normalized = {}
    drained = []
    stats = {"attempts": 0, "drained": 0, "ok": 0, "failed_asins": []}

    for asin in asins:
        done = False
        attempts = 0
        while not done and pool and attempts < MAX_ATTEMPTS_PER_ASIN:
            host = random.choice(pool)
            attempts += 1
            stats["attempts"] += 1
            status, payload = await _fetch_async(host, asin)
            if status == 200 and isinstance(payload, dict):
                results[asin] = payload
                normalized[asin] = _normalize(_env_key_for_host(host), asin, payload)
                stats["ok"] += 1
                done = True
                if verbose:
                    print("[OK] %s via %s" % (asin, host))
            elif status in (403, 429):
                # Quota / forbidden / hard rate limit -> drain permanently.
                pool.remove(host)
                drained.append(host)
                stats["drained"] += 1
                if verbose:
                    print("[DRAIN] %s -> %s (status %s); pool now %d"
                          % (host, asin, status, len(pool)))
            else:
                # Other error (404/401/timeout) -> retry on another host,
                # but do NOT drain (may be a per-ASIN miss, not a quota).
                if verbose:
                    print("[RETRY] %s via %s (status %s); trying another host"
                          % (asin, host, status))
                if len(pool) <= 1 and attempts >= 2:
                    break
        if not done:
            stats["failed_asins"].append(asin)
            if verbose:
                print("[FAIL] %s not scraped (pool=%d)" % (asin, len(pool)))
        if not pool:
            print("[STOP] pool exhausted; remaining ASINs unprocessed.")
            break

    return {"results": results, "normalized": normalized,
            "drained": drained, "stats": stats}


# ---------------------------------------------------------------------------
# Dry-run + offline normalization validation
# ---------------------------------------------------------------------------
SYNTHETIC = {
    "product": {
        "title": "Kirkland Chewable Calcium",
        "price": 12.99,
        "reviews_count": 1820,
        "sales_rank": "#1,291 in Health & Household",
        "buy_box": {"price": 12.99, "seller_name": "Amazon",
                    "is_prime": True},
        "offers": [{"seller_name": "A", "price": 12.99, "is_fba": True}],
    }
}


def _dry_run(asins: list):
    pool = [os.getenv(k) for k in HOST_ENV_KEYS if os.getenv(k)]
    print("=== DRY RUN (no network) ===")
    print("RAPIDAPI_KEY set : %s" % ("YES" if KEY else "NO"))
    print("Active pool (%d):" % len(pool))
    for h in pool:
        print("  - %s" % h)
    print("ASINs to process: %d" % len(asins))
    print("Normalization sample (synthetic payload):")
    sample = _normalize("RAPIDAPI_HOST_BDC", asins[0] if asins else "TEST",
                        SYNTHETIC)
    print(json.dumps(sample, indent=2, default=str))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def _load_asins() -> list:
    path = ASIN_FILE
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()
                and re.fullmatch(r"[A-Za-z0-9]{10}", line.strip())]


def main():
    asins = _load_asins()
    if not asins:
        print("No ASINs loaded from %s (one valid ASIN per line)." % ASIN_FILE)
        # Fall back to a single demo ASIN so dry-run still demonstrates.
        asins = ["B00F4MD808"]
    if not LIVE:
        _dry_run(asins)
        return
    out = asyncio.run(run_router(asins))
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(out["results"], f, indent=2, default=str)
    with open(NORMALIZED_PATH, "w", encoding="utf-8") as f:
        json.dump(out["normalized"], f, indent=2, default=str)
    print("Wrote %d results -> %s" % (len(out["results"]), RESULTS_PATH))
    print("Wrote %d normalized -> %s" % (len(out["normalized"]), NORMALIZED_PATH))
    print("Drained hosts: %s" % (out["drained"] or "none"))
    print("Stats: %s" % out["stats"])


if __name__ == "__main__":
    main()
