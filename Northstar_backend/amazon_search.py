"""Amazon keyword-search provider dispatch for the Product Scout.

Selects the live search backend via SCANNER_SEARCH_SOURCE:
  - BRIGHTDATA  Bright Data Web Unlocker (POST api.brightdata.com/request,
                zone + url, raw HTML of the Amazon search page; per-request
                billing, no credits). Primary source (default).
  - CHOCODATA  chocodata.com (free 1,000 credits on signup, no card;
               /amazon/search = 5 credits per call, so a full scan of
               N keywords x M pages costs 5 x N x M credits)
  - SCAVIO     Scavio (default fallback)

The Bright Data HTTP + card parsing lives in bright_data_client; this
module only dispatches, mirrors the provider error, and (when
SCANNER_SEARCH_FALLBACK is set) falls back to CHOCODATA or SCAVIO after a
Bright Data failure. All providers normalize to the same candidate shape
(asin, name, amazon_price, product_url), never raise, and record a
single human-readable LAST_SEARCH_ERROR so the scanner endpoint can
distinguish "no candidates" from "upstream unavailable".

Persisted candidate cache (data/scanner-search-cache.json by default,
env SCANNER_SEARCH_CACHE_PATH project-root relative): written atomically
only after a fully successful live search (no upstream error), never
overwritten by a failed/malformed/disabled run, and used as the sole
candidate source in cache-only mode — zero outbound calls.
"""

_SCHEMA_VERSION = 1

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import quote
import requests
from dotenv import load_dotenv

import bright_data_client
import scavio_client
import live_gate
from kirkland_filter import is_genuine_kirkland_candidate

load_dotenv()

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _cache_path() -> str:
    raw = os.getenv("SCANNER_SEARCH_CACHE_PATH") or "data/scanner-search-cache.json"
    if os.path.isabs(raw):
        return raw
    return os.path.join(_BACKEND_DIR, raw)


def _cache_ttl_hours() -> Optional[float]:
    """Freshness window from SCANNER_SEARCH_CACHE_TTL_HOURS; None = never stale."""
    raw = os.getenv("SCANNER_SEARCH_CACHE_TTL_HOURS")
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _read_cache_file():
    """Raw cache payload with distinct honest states. Zero network.

    Returns the payload dict when valid, False when corrupt/unparseable,
    None when the file is missing.
    """
    path = _cache_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return False
    if not isinstance(data, dict) or not isinstance(data.get("products"), list):
        return False
    return data


def cache_meta() -> Dict:
    """Read-only cache provenance for the scanner summary. Never raises.

    cache_status: fresh | stale | missing | corrupt. stale requires
    SCANNER_SEARCH_CACHE_TTL_HOURS > 0; without it the cache never
    expires and the fetched_at timestamp stays visible.
    """
    data = _read_cache_file()
    if data is None:
        return {"cache_status": "missing"}
    if data is False:
        return {"cache_status": "corrupt"}

    fetched_at = data.get("fetched_at")
    stale = False
    ttl = _cache_ttl_hours()
    if ttl is not None and isinstance(fetched_at, str):
        try:
            fetched = datetime.fromisoformat(fetched_at)
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            stale = datetime.now(timezone.utc) - fetched > timedelta(hours=ttl)
        except ValueError:
            stale = True

    return {
        "cache_status": "stale" if stale else "fresh",
        "cache_fetched_at": fetched_at,
        "cache_source": data.get("source"),
        "cache_schema_version": data.get("schema_version"),
        "cache_candidate_count": data.get("candidate_count"),
    }


def load_cached_candidates() -> List[Dict]:
    """Candidates from the local search cache; [] when missing/corrupt.

    Cache-only candidate source: never touches the network.
    """
    data = _read_cache_file()
    if data is None or data is False:
        return []
    products = [p for p in data["products"] if isinstance(p, dict)]
    # Normalize: ensure every candidate carries a "name" key. The flagship
    # product_analysis pipeline indexes candidates by c["name"] directly, and
    # past scanner snapshots sometimes recorded rows without a title/name.
    # Default to an empty string (never None) so no hard index later raises
    # KeyError on a partial record; empty-name rows simply match nothing.
    for p in products:
        p.setdefault("name", "")
    return products


def save_cached_candidates(
    products: List[Dict],
    search_terms: Optional[List[str]] = None,
    source: Optional[str] = None,
) -> None:
    """Atomically replace the candidate cache. Call ONLY after a fully
    successful live search (LAST_SEARCH_ERROR unset) — never after an
    upstream error, timeout, malformed response, or disabled mode, so a
    valid prior cache is never wiped by a failed run. Never raises into
    the scanner; a write failure just leaves the prior cache in place.
    """
    if not search_terms:
        search_terms = [kw.strip() for kw in SEARCH_KEYWORDS.split(",") if kw.strip()]
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": (source or SCANNER_SEARCH_SOURCE).lower(),
        "search_terms": search_terms,
        "candidate_count": len(products),
        "products": products,
    }
    path = _cache_path()
    tmp_path = f"{path}.tmp"
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    except OSError:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from urllib.parse import quote
import requests
from dotenv import load_dotenv

import bright_data_client
import scavio_client
from kirkland_filter import is_genuine_kirkland_candidate

load_dotenv()

SCANNER_SEARCH_SOURCE = os.getenv("SCANNER_SEARCH_SOURCE", "BRIGHTDATA").upper()
SCANNER_SEARCH_FALLBACK = os.getenv("SCANNER_SEARCH_FALLBACK", "").upper()
CHOCODATA_API_KEY = os.getenv("CHOCODATA_API_KEY")
SEARCH_KEYWORDS = os.getenv("SEARCH_KEYWORDS", "")
PAGES_TO_SEARCH = int(os.getenv("PAGES_TO_SEARCH", "1"))
DEFAULT_MARKETPLACE = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com")

CHOCODATA_SEARCH_URL = os.getenv(
    "CHOCODATA_SEARCH_URL",
    "https://api.chocodata.com/api/v1/amazon/search",
)
REQUEST_TIMEOUT_SECONDS = 60

# 502 target_unreachable is transient and uncharged; wait ~10s per the
# provider guidance before retrying, and give up after two attempts.
CHOCDATA_RETRY_MAX_ATTEMPTS = 2
RETRY_SLEEP_SECONDS = float(os.getenv("CHOCODATA_RETRY_SLEEP_SECONDS", "8"))

# Amazon search cards report velocity as "5K+ bought in past month",
# "200+ bought in past week", "1K+ bought in past day". Convert to a
# numeric monthly estimate (week x4.33, day x30.4). None when absent.
_SALES_VOLUME_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*([KM]?)\+?\s*bought in past\s+(month|week|day)",
    re.IGNORECASE,
)
_SALES_VOLUME_MULTIPLIERS = {"K": 1000.0, "M": 1_000_000.0, "": 1.0}
_SALES_VOLUME_PERIODS = {"month": 1.0, "week": 4.33, "day": 30.4}


def _parse_sales_volume(raw) -> Optional[float]:
    """Parse an Amazon search-card sales_volume string into a monthly estimate."""
    if not raw or not isinstance(raw, str):
        return None
    match = _SALES_VOLUME_RE.search(raw)
    if not match:
        return None
    number = float(match.group(1))
    multiplier = _SALES_VOLUME_MULTIPLIERS.get(match.group(2).upper(), 1.0)
    period = _SALES_VOLUME_PERIODS.get(match.group(3).lower(), 1.0)
    return number * multiplier * period


def _search_brightdata(
    keywords: Optional[List[str]],
    pages: Optional[int],
    match_all: bool = False,
) -> List[Dict]:
    """Fetch Amazon search pages via the Bright Data Web Unlocker.

    Delegates the HTTP + card parsing to bright_data_client (one POST
    /request per page, zone northstaros, raw HTML). ``match_all=False``
    (default) keeps the shared Kirkland relevance rule inside the client;
    ``match_all=True`` returns every parsed card (universal sourcing). Any
    request failure is mirrored from bright_data_client.LAST_ERROR.
    """
    global LAST_SEARCH_ERROR

    if not keywords:
        keywords = [kw.strip() for kw in SEARCH_KEYWORDS.split(",") if kw.strip()]
    if not pages or pages <= 0:
        pages = PAGES_TO_SEARCH

    results: List[Dict] = []
    try:
        for keyword in keywords:
            page_results = bright_data_client.search_products(
                keyword, pages, match_all=match_all
            )
            results.extend(page_results)
            LAST_SEARCH_ERROR = bright_data_client.LAST_ERROR
            if LAST_SEARCH_ERROR:
                print(f"[Bright Data] keyword='{keyword}' error: {LAST_SEARCH_ERROR}")
                break
    except ValueError as e:
        LAST_SEARCH_ERROR = str(e)
        print(f"[Bright Data] {e}")

    return results


def _is_kirkland_signature(title: Optional[str], brand: Optional[str] = None) -> bool:
    """True if a genuine Kirkland listing, by title OR brand.

    Thin wrapper over the shared kirkland_filter.is_genuine_kirkland_candidate
    used by every provider, so relevance rules stay in one place.
    """
    return is_genuine_kirkland_candidate({"name": title, "brand": brand})

PROVIDER_LABELS = {
    "BRIGHTDATA": "Bright Data",
    "CHOCODATA": "Chocodata",
    "SCAVIO": "Scavio",
}
PROVIDER_BILLING_URLS = {
    "BRIGHTDATA": "https://www.brightdata.com",
    "CHOCODATA": "https://app.chocodata.com",
    "SCAVIO": "https://dashboard.scavio.dev/billing",
}

# Single source of truth for the scanner endpoint: set whenever the active
# provider could not be reached or returned an unusable response; cleared
# after any successful HTTP response is parsed.
LAST_SEARCH_ERROR = None

if not CHOCODATA_API_KEY:
    print("[Chocodata] CHOCODATA_API_KEY not set; source will report an error")


def active_search_source() -> str:
    return SCANNER_SEARCH_SOURCE


def provider_label() -> str:
    return PROVIDER_LABELS.get(SCANNER_SEARCH_SOURCE, SCANNER_SEARCH_SOURCE)


def provider_billing_url() -> str:
    return PROVIDER_BILLING_URLS.get(SCANNER_SEARCH_SOURCE)


def search_kirkland_products(
    keywords: Optional[List[str]] = None,
    pages: Optional[int] = None,
) -> List[Dict]:
    """Search Amazon via the configured provider, normalized to candidates.

    Kirkland-profile wrapper: identical behavior to the historical function,
    now delegating to :func:`search_products` with ``match_all=False`` (the
    shared Kirkland relevance rule stays in force).
    """
    return search_products(keywords=keywords, pages=pages, match_all=False)


def search_products(
    keywords: Optional[List[str]] = None,
    pages: Optional[int] = None,
    match_all: bool = False,
) -> List[Dict]:
    """Category-agnostic Amazon keyword search (Phase 1 generalization).

    ``match_all=False`` keeps the Kirkland relevance filter (default,
    backward compatible). ``match_all=True`` returns EVERY normalized
    candidate for the given keywords regardless of brand — the universal
    sourcing path used by Product Finder / Supplier Finder.

    Hard containment boundary: when SCANNER_LIVE_ALLOWED is not an explicit
    opt-in, this returns [] immediately — zero provider calls, zero error
    flags, zero output — so no GET/static/UI/import path can ever reach a
    live search provider. Live searches only run through the explicit
    refresh paths (POST /api/kirkland/refresh or the npm pipeline) with the
    gate enabled.

    A successful HTTP response (even with zero products) clears the error
    flag; any failure records a human-readable LAST_SEARCH_ERROR. When the
    primary BRIGHTDATA source fails and SCANNER_SEARCH_FALLBACK is set to
    CHOCODATA or SCAVIO, the fallback is tried before giving up; a
    successful fallback clears the error so the scanner reports fresh data.
    """
    global LAST_SEARCH_ERROR
    if not live_gate.live_enabled():
        return []
    LAST_SEARCH_ERROR = None

    if SCANNER_SEARCH_SOURCE == "BRIGHTDATA":
        products = _search_brightdata(keywords, pages, match_all=match_all)
        if not products and LAST_SEARCH_ERROR and SCANNER_SEARCH_FALLBACK:
            fallback = SCANNER_SEARCH_FALLBACK
            if fallback == "CHOCODATA":
                products = _search_chocodata(keywords, pages, match_all=match_all)
            elif fallback == "SCAVIO":
                products = scavio_client.search_kirkland_products(keywords, pages)
                LAST_SEARCH_ERROR = scavio_client.LAST_SEARCH_ERROR
            if products:
                print(
                    f"[Bright Data] primary failed; fallback {fallback} "
                    f"returned {len(products)} products"
                )
        return products

    if SCANNER_SEARCH_SOURCE == "CHOCODATA":
        return _search_chocodata(keywords, pages, match_all=match_all)

    products = scavio_client.search_kirkland_products(keywords, pages)
    LAST_SEARCH_ERROR = scavio_client.LAST_SEARCH_ERROR
    return products


def _marketplace_domain() -> str:
    host = DEFAULT_MARKETPLACE.rstrip("/").split("/", 3)[-1]
    host = host.replace("www.amazon.", "")
    return host or "com"


def _search_chocodata(
    keywords: Optional[List[str]],
    pages: Optional[int],
    match_all: bool = False,
) -> List[Dict]:
    global LAST_SEARCH_ERROR

    if not keywords:
        keywords = [kw.strip() for kw in SEARCH_KEYWORDS.split(",") if kw.strip()]
    if not pages or pages <= 0:
        pages = PAGES_TO_SEARCH

    if not CHOCODATA_API_KEY:
        LAST_SEARCH_ERROR = "CHOCODATA_API_KEY not set"
        print("[Chocodata] CHOCODATA_API_KEY not set; skipping search")
        return []

    results: List[Dict] = []
    base_params = {
        "api_key": CHOCODATA_API_KEY,
        "domain": _marketplace_domain(),
        "sort_by": "best_match",
    }

    for keyword in keywords:
        exhausted = False
        for page in range(1, pages + 1):
            if exhausted:
                break
            attempt = 0
            while True:
                attempt += 1
                try:
                    # NOTE: ChocoData ignores the `pages` param and always
                    # returns the first page (~60 products); page through
                    # start_page explicitly instead. Each page = one billed
                    # request (5 credits).
                    params = dict(base_params)
                    params["query"] = keyword
                    params["start_page"] = page

                    response = requests.get(
                        CHOCODATA_SEARCH_URL,
                        params=params,
                        timeout=REQUEST_TIMEOUT_SECONDS,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        LAST_SEARCH_ERROR = None
                        products = data.get("products") or []
                        print(
                            f"[Chocodata] keyword='{keyword}' page={page}/{pages} "
                            f"raw_products={len(products)}"
                        )
                        for item in products:
                            asin = item.get("asin")
                            name = item.get("title") or item.get("name")
                            brand = item.get("brand")
                            if not match_all and not _is_kirkland_signature(name, brand):
                                continue
                            price = item.get("price")
                            price_val = None
                            if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
                                price_val = float(price)
                            elif isinstance(price, str):
                                try:
                                    parsed = float(price.strip())
                                    if parsed > 0:
                                        price_val = parsed
                                except ValueError:
                                    price_val = None

                            results.append({
                                "asin": asin,
                                "name": name,
                                "amazon_price": price_val,
                                "product_url": item.get("url") or item.get("link"),
                                "brand": brand,
                                "sales_volume": item.get("sales_volume"),
                                "monthly_sales_estimate": _parse_sales_volume(item.get("sales_volume")),
                                "monthly_sales_estimated": True,
                                "rating": item.get("rating"),
                                "reviews_count": item.get("reviews_count"),
                            })
                        # A page with zero products means we've exhausted the
                        # results for this keyword; stop paging.
                        if not products:
                            exhausted = True
                        break

                    body = {}
                    try:
                        parsed = response.json()
                        if isinstance(parsed, dict):
                            body = parsed
                    except Exception:
                        pass

                    # 502 target_unreachable is transient and not charged: the
                    # provider retries internally then tells us to wait ~10s.
                    # Retry once before declaring the keyword failed.
                    if (
                        response.status_code == 502
                        and body.get("retryable")
                        and attempt < CHOCDATA_RETRY_MAX_ATTEMPTS
                    ):
                        print(
                            f"[Chocodata] 502 retryable for keyword '{keyword}' "
                            f"page={page} (attempt {attempt}/{CHOCDATA_RETRY_MAX_ATTEMPTS}); "
                            "waiting and retrying"
                        )
                        time.sleep(RETRY_SLEEP_SECONDS)
                        continue

                    LAST_SEARCH_ERROR = f"HTTP {response.status_code}"
                    message = body.get("message")
                    if isinstance(message, str) and message:
                        LAST_SEARCH_ERROR += f" {message[:120]}"
                    if "credit" in response.text.lower() or "balance" in response.text.lower():
                        LAST_SEARCH_ERROR += " (insufficient credits)"
                    print(f"[Chocodata] {response.status_code} {response.text[:300]}")
                    break

                except Exception as e:
                    LAST_SEARCH_ERROR = str(e)
                    print(f"[Chocodata] Exception: {e}")
                    break

    return results
