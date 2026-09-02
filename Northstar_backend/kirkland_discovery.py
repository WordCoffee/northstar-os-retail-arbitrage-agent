"""Layers 1-3 - Kirkland catalog discovery, dedup, brand verification, manifest.

Discovery is SEARCH-ONLY: the injected search_fn returns keyword/brand search
hits (asin + title + brand). It must never call pricing / offers / BSR
endpoints; those belong to the enrichment waterfall, not discovery.

Layer 2: dedupe ASINs across pages/queries; verify the structured brand field
equals "Kirkland Signature" (title-text is only a fallback). Near-matches are
logged with a reason, never silently included.

Layer 3: freeze a deduplicated, brand-verified manifest with a SHA-256
fingerprint. The manifest is immutable once written (re-writing the same path
raises); mutation requires a new (timestamped) manifest.
"""

import hashlib
import json
import os
import requests
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

DISCOVERY_QUERIES = [
    "Kirkland Signature",
    "Kirkland Signature vitamins supplements",
    "Kirkland Signature trash bags",
    "Kirkland Signature paper towels",
    "Kirkland Signature olive oil",
    "Kirkland Signature snacks",
    "Kirkland Signature body wash",
]

# Search-route registry for keyword/brand discovery. Each of the 6 RapidAPI
# pool apps carries an explicit status: verified | unverified | dead_host |
# blocked_awaiting_operator_host. Discovery must only use apps marked 'verified'.
SEARCH_ROUTES = {
    "RAPIDAPI_REALTIME": {
        "path": "/search",
        "status": "verified",
        "note": "GET /search?query=<q>&country=US verified 2026-08-24 (HTTP 200, "
                "data.products[] returned 1663 Kirkland hits for 'Kirkland "
                "Signature'). Pagination via integer 'page' param (no cursor). "
                "No explicit 'brand' field per item -> brand inferred from "
                "product_title (verify_kirkland_brand title fallback). Viable "
                "for Layer 1 discovery on its own.",
    },
    "RAPIDAPI_BDC": {
        "path": None,
        "status": "blocked_awaiting_operator_host",
        "note": "BDC host not supplied this turn (placeholder <PASTE_BDC_HOST_HERE>); "
                "prior probe returned RapidAPI 'No such app'. A valid host is required.",
    },
    "RAPIDAPI_AXESSO": {
        "path": None,
        "status": "unverified",
        "note": "Amazon lookup product is ASIN-scoped; keyword search not expected. "
                "Structurally unsuitable for discovery (see Task D).",
    },
    "RAPIDAPI_PRICING": {
        "path": None,
        "status": "unverified",
        "note": "Pricing & product info is ASIN-scoped; keyword search not expected. "
                "Structurally unsuitable for discovery (see Task D).",
    },
    "RAPIDAPI_ONLINE": {
        "path": None,
        "status": "unverified",
        "note": "Online stock lookup is ASIN-scoped; keyword search not expected. "
                "Structurally unsuitable for discovery (see Task D).",
    },
    "RAPIDAPI_SCOUT": {
        "path": "/Amazon-Search-Data",
        "status": "unverified",
        "note": "Route resolves (HTTP 206, NOT 404); param 'searchTerm' accepted "
                "(no 400), and adding 'domainCode=com' did not help. Every query "
                "value tried returned {\"error\":\"Invalid Search Query\"}. The "
                "required parameter set / value format is still unresolved from "
                "docs; NOT producing result payloads yet.",
    },
}


def verify_kirkland_brand(product):
    """True for genuine Kirkland brand, title-based only when no brand field.

    Real-Time Amazon Data returns no structured brand field, so the brand is
    inferred from the product_title. We accept a clear 'Kirkland' brand token
    but reject hyphenated near-misses (e.g. 'Kirkland-ish') so they stay out
    of the genuine set. Match basis is logged, never fabricated.
    """
    brand = (product.get("brand") or "").strip()
    title = (product.get("title") or "").strip()
    tl = title.lower()
    if brand.lower() == "kirkland signature":
        return True, None  # brand field confirmed
    if "kirkland signature" in tl:
        return True, "title_inferred"
    if "kirkland" in tl and "kirkland-" not in tl:
        return True, "title_inferred"
    return False, "brand_not_kirkland_signature"


def discover(search_fn, max_pages=5, max_queries=None, budget=None,
             early_stop_non_kirkland=True):
    """Bounded, page-looping Kirkland discovery over DISCOVERY_QUERIES.

    search_fn(q, page) -> list of normalized items (each carrying at least
    asin + title) OR None when the caller's budget is exhausted (signals a
    hard stop). Returns (seen, rejected) dicts.

    * max_queries caps how many DISCOVERY_QUERIES are used (default: all).
    * budget is an optional _RequestBudget; when remaining<=0 the loop stops.
    * early_stop_non_kirkland breaks a query's page loop when a non-empty
      page yields zero Kirkland-verified items (clearly non-Kirkland-dominated).
    """
    queries = DISCOVERY_QUERIES
    if max_queries is not None:
        queries = queries[:max_queries]
    seen = {}
    rejected = []
    for q in queries:
        for page in range(1, max_pages + 1):
            if budget is not None and budget.remaining() <= 0:
                break
            results = search_fn(q, page)
            if results is None:
                break
            if not results:
                break
            verified_on_page = 0
            for p in results:
                asin = p.get("asin")
                if not asin:
                    continue
                if asin in seen:
                    continue
                ok, reason = verify_kirkland_brand(p)
                if ok:
                    basis = ("brand_field_confirmed"
                             if reason is None else "title_inferred")
                    seen[asin] = {
                        "asin": asin,
                        "title": p.get("title"),
                        "product_title": p.get("product_title") or p.get("title"),
                        "brand": p.get("brand"),
                        "product_price": p.get("product_price"),
                        "product_star_rating": p.get("product_star_rating"),
                        "product_num_ratings": p.get("product_num_ratings"),
                        "product_num_offers": p.get("product_num_offers"),
                        "product_url": p.get("product_url"),
                        "source_query": q,
                        "page_found": page,
                        "brand_match_basis": basis,
                        "brand_verify_note": reason,
                    }
                    verified_on_page += 1
                else:
                    rejected.append({
                        "asin": asin,
                        "title": p.get("title"),
                        "brand": p.get("brand"),
                        "reason": reason,
                    })
            if early_stop_non_kirkland and len(results) > 0 and verified_on_page == 0:
                break
        if budget is not None and budget.remaining() <= 0:
            break
    return seen, rejected


class _RequestBudget:
    """Count live requests against a hard cap; capture last quota headers."""

    def __init__(self, cap):
        self.cap = cap
        self.count = 0
        self.last_remaining = None
        self.last_limit = None

    def remaining(self):
        return self.cap - self.count

    def consume(self):
        self.count += 1


def fetch_realtime_search(query, page, budget, country="US"):
    """One GET /search on real-time-amazon-data. Null-first; no secrets logged.

    Returns list[normalized items] or None when budget exhausted. Captures
    X-RateLimit-Requests-Remaining/Limit into the budget for accounting.
    """
    if budget is not None and budget.remaining() <= 0:
        return None
    host = os.getenv("RAPIDAPI_HOST_REALTIME")
    key = os.getenv("RAPIDAPI_KEY")
    if not host or not key:
        return []
    params = {
        "query": query,
        "country": country,
        "page": page,
        "sort_by": "RELEVANCE",
        "product_condition": "ALL",
        "is_prime": "false",
        "deals_and_discounts": "NONE",
    }
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}
    if budget is not None:
        budget.consume()
    try:
        resp = requests.get(
            "https://%s/search" % host, headers=headers, params=params, timeout=20)
    except requests.exceptions.RequestException:
        return []
    rem = resp.headers.get("X-RateLimit-Requests-Remaining")
    lim = resp.headers.get("X-RateLimit-Requests-Limit")
    if rem is not None:
        try:
            budget.last_remaining = int(rem)
        except ValueError:
            pass
    if lim is not None:
        try:
            budget.last_limit = int(lim)
        except ValueError:
            pass
    if resp.status_code != 200:
        return []
    try:
        data = resp.json()
    except ValueError:
        return []
    products = (data.get("data") or {}).get("products") or []
    out = []
    for p in products:
        if not isinstance(p, dict):
            continue
        out.append({
            "asin": p.get("asin"),
            "title": p.get("product_title"),
            "product_title": p.get("product_title"),
            "brand": None,
            "product_price": p.get("product_price"),
            "product_star_rating": p.get("product_star_rating"),
            "product_num_ratings": p.get("product_num_ratings"),
            "product_num_offers": p.get("product_num_offers"),
            "product_url": p.get("product_url"),
        })
    return out


def run_layer1_discovery(max_queries=5, max_pages=8, max_requests=40,
                         country="US"):
    """Approved full paginated Layer 1 discovery via Real-Time Amazon Data only.

    Writes a frozen deduplicated Kirkland-verified manifest and returns a
    summary. Does NOT trigger enrichment / DataForSEO / offer calls.
    """
    budget = _RequestBudget(max_requests)

    def _fn(query, page):
        if budget.remaining() <= 0:
            return None
        return fetch_realtime_search(query, page, budget, country=country)

    seen, rejected = discover(
        _fn, max_pages=max_pages, max_queries=max_queries, budget=budget,
        early_stop_non_kirkland=True)

    os.makedirs("data/catalog", exist_ok=True)
    path = "data/catalog/layer1_discovery_manifest_%s.json" % (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    manifest, written = build_manifest(seen, rejected, path=path)
    return {
        "manifest": manifest,
        "path": written,
        "seen_count": len(seen),
        "rejected_count": len(rejected),
        "requests_used": budget.count,
        "quota_remaining": budget.last_remaining,
        "quota_limit": budget.last_limit,
    }


def redundancy_probe(host_env, path, param_name="keyword", query="Kirkland Signature"):
    """Best-effort backstop probe of a non-primary search route (Task C).

    Returns pass/fail only; results are NEVER folded into the manifest.
    """
    host = os.getenv(host_env)
    key = os.getenv("RAPIDAPI_KEY")
    if not host or not key:
        return {"host_env": host_env, "status": "skipped", "reason": "no host/key"}
    params = {param_name: query, "country": "US"}
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": host}
    try:
        resp = requests.get("https://%s%s" % (host, path), headers=headers,
                            params=params, timeout=20)
    except requests.exceptions.RequestException as exc:
        return {"host_env": host_env, "status": "error", "reason": type(exc).__name__}
    try:
        body = resp.json()
    except ValueError:
        body = {"raw_text": resp.text[:200]}
    products = None
    if isinstance(body, dict):
        products = (body.get("data") or {}).get("products")
        if products is None:
            products = body.get("products")
    ok = resp.status_code == 200 and isinstance(products, list) and len(products) > 0
    return {
        "host_env": host_env,
        "status": "pass" if ok else "fail",
        "http_status": resp.status_code,
        "product_count": len(products) if isinstance(products, list) else None,
    }


def build_manifest(seen, rejected, path=None):
    asins = sorted(seen.keys())
    records = [seen[a] for a in asins]
    if path is None:
        os.makedirs("data/catalog", exist_ok=True)
        path = "data/catalog/kirkland_catalog_manifest_%s.json" % (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if os.path.exists(path):
        raise RuntimeError("manifest immutable: already frozen at %s" % path)
    canonical = {
        "asins": records,
        "count": len(records),
        "rejected_count": len(rejected),
    }
    fp_src = json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    fingerprint = hashlib.sha256(fp_src).hexdigest()
    manifest = {
        "schema_version": 1,
        "kind": "kirkland_catalog_manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "frozen": True,
        "fingerprint": fingerprint,
        "count": len(records),
        "asins": records,
        "rejected_count": len(rejected),
        "rejected_sample": rejected[:50],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    return manifest, path


def load_manifest(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
