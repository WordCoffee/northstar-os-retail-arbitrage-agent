#!/usr/bin/env python
"""Multi-provider seller-data probe harness (preflight only, free tiers).

Probes ONE Amazon product page per invocation through one provider and
reports which seller-data markers came back. Built to answer a single
question before any backfill is designed: which of the newly supplied
free-tier providers can actually return Amazon seller data?

Providers (each exactly ONE request per preflight invocation, zero retries):
  firecrawl    POST https://api.firecrawl.dev/v2/scrape  (rawHtml)
  scrapedo     GET  https://api.scrape.do?token=KEY&url=URL (raw HTML)
  keenable     GET  https://api.keenable.ai/v1/fetch?url=..&live=true (markdown)
  browserbase  POST https://api.browserbase.com/v1/fetch (raw, no JS, 5MB cap)

Bright Data Web Unlocker is deliberately NOT in this harness: the operator's
live-test approval named the four new providers only.

Discipline (mirrors firecrawl_costco.py / bright_data_costco.py):
  - fail-closed gates: no key -> config_error, no request fires
  - ZERO retries; sequential; one request per invocation
  - HARD failures (config/auth/rate-limit/credits/http/transport/malformed)
    are typed, persisted, and reported; the invocation stops (circuit breaker)
  - SOFT outcomes (page fetched but Amazon block page / no seller markers)
    are reported as data, not failures: blocked / no_data_found
  - API keys are read from env for headers/params only and NEVER persisted
    or printed; evidence files carry byte counts + marker hits + head-capped
    snippets only

Usage:
  python tools/provider_seller_probe.py --mode status
  python tools/provider_seller_probe.py --mode preflight --provider firecrawl \\
      --asin B00BH3HPZW --page dp --live --max-requests 1
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

# Repo-root .env is authoritative for operator-supplied keys: python-dotenv
# resolves .env from the calling file's directory by default, which would
# pick up Northstar_backend/.env (a divergent file without the new keys).
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

import requests

MARKETPLACE = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com").rstrip("/")

PROVIDERS = ("firecrawl", "scrapedo", "keenable", "browserbase")

KEY_ENV = {
    "firecrawl": "FIRECRAWL_API_KEY",
    "scrapedo": "SCRAPE_DO_API_KEY",
    "keenable": "KEENABLE_API_KEY",
    "browserbase": "BROWSERBASE_API_KEY",
}

HARD_FAILURE_TYPES = (
    "config_error",
    "auth_error",
    "rate_limited",
    "credits_exhausted",
    "http_error",
    "transport_error",
    "malformed_response",
)

# --- seller / block marker vocabulary ---------------------------------------
_SELLER_MARKERS = {
    "seller_profile_link": re.compile(r"/sp\?seller=", re.I),
    "sold_by": re.compile(r"[Ss]old by", re.I),
    "fulfilled_by_amazon": re.compile(r"[Ff]ulfilled by Amazon", re.I),
    "ships_from": re.compile(r"[Ss]hips from", re.I),
    "merchant_info": re.compile(r"merchant[_-]?info|sellers?\.?amazon|aod-offer", re.I),
    "new_offers_count": re.compile(r"New\s*\(\d+\)\s*from", re.I),
    "seller_rating": re.compile(r"\d{1,3}(,\d{3})*\s*(ratings|feedback)", re.I),
}
_BLOCK_MARKERS = {
    "captcha": re.compile(r"captcha|Enter the characters you see|robot check", re.I),
    "dog_page": re.compile(r"sorry, we just need to make sure|looking for something\?", re.I),
    "access_denied": re.compile(r"access denied|request blocked|are you a human", re.I),
}
# Offer-roster structures: present only when Amazon actually served an offer
# list / buying-options panel (as opposed to dp-equivalent content).
_OFFER_MARKERS = {
    "aod_offer": re.compile(r"aod-offer", re.I),
    "other_sellers": re.compile(r"Other sellers on Amazon", re.I),
    "buying_options": re.compile(r"See All Buying Options|All Buying Options", re.I),
    "offer_list": re.compile(r"aod-container|aod-list|offer-list", re.I),
}
_CANONICAL_TAG_RE = re.compile(r"<link[^>]*rel=[\"']canonical[\"'][^>]*>", re.I)
_HREF_RE = re.compile(r"href=[\"']([^\"']+)[\"']", re.I)

_AUTH_RE = re.compile(r"\b(auth|unauthori|forbidden|denied|invalid.{0,10}key|api.{0,10}key)\b", re.I)
_CREDITS_RE = re.compile(r"\b(payment|credit|quota|billing|402|allowance|exhausted)\b", re.I)
_RATE_RE = re.compile(r"\b(rate|429|too many|throttl)\b", re.I)


def _run_dir() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", "enrich", "provider-probes", "probe-%s" % ts)
    os.makedirs(path, exist_ok=True)
    return path


def _get(url, *, params=None, headers=None, timeout=60):
    try:
        return requests.get(url, params=params, headers=headers, timeout=timeout), None
    except requests.exceptions.Timeout:
        return None, "transport_error: timeout"
    except requests.exceptions.RequestException:
        return None, "transport_error: network_error"


def _post(url, *, body=None, headers=None, timeout=60):
    try:
        return requests.post(url, json=body, headers=headers, timeout=timeout), None
    except requests.exceptions.Timeout:
        return None, "transport_error: timeout"
    except requests.exceptions.RequestException:
        return None, "transport_error: network_error"


def _classify_http(status, text_head=""):
    if status in (401, 403):
        return "auth_error: HTTP %s" % status
    if status == 402:
        return "credits_exhausted: HTTP 402"
    if status == 429:
        return "rate_limited: HTTP 429"
    return "http_error: HTTP %s" % status


def _classify_payload_error(err_text):
    err_text = (err_text or "")[:160]
    if _CREDITS_RE.search(err_text):
        return "credits_exhausted: %s" % err_text
    if _RATE_RE.search(err_text):
        return "rate_limited: %s" % err_text
    if _AUTH_RE.search(err_text):
        return "auth_error: %s" % err_text
    return "http_error: provider refused%s" % (": %s" % err_text if err_text else "")


def fetch_firecrawl(url):
    """One Firecrawl Scrape request; returns (content, hard_error)."""
    key = os.getenv(KEY_ENV["firecrawl"])
    if not key:
        return None, "config_error: FIRECRAWL_API_KEY not configured"
    body = {"url": url, "formats": ["rawHtml"], "maxAge": 0,
            "timeout": 60000, "proxy": "auto"}
    headers = {"Authorization": "Bearer %s" % key, "Content-Type": "application/json"}
    resp, terr = _post("https://api.firecrawl.dev/v2/scrape", body=body,
                       headers=headers, timeout=90)
    if terr:
        return None, terr
    status = resp.status_code
    if status != 200:
        return None, _classify_http(status)
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None, "malformed_response: invalid JSON"
    if not isinstance(payload, dict) or payload.get("success") is not True:
        err = str((payload or {}).get("error") or (payload or {}).get("message") or "")
        return None, _classify_payload_error(err)
    data = payload.get("data") or {}
    html = data.get("rawHtml")
    if html is None:
        return None, "malformed_response: no rawHtml in response"
    page_status = (data.get("metadata") or {}).get("statusCode")
    return {"content": html, "http_status": status, "page_status": page_status}, None


def fetch_scrapedo(url):
    """One scrape.do request; returns (content, hard_error)."""
    key = os.getenv(KEY_ENV["scrapedo"])
    if not key:
        return None, "config_error: SCRAPE_DO_API_KEY not configured"
    resp, terr = _get("https://api.scrape.do",
                      params={"token": key, "url": url}, timeout=90)
    if terr:
        return None, terr
    status = resp.status_code
    if status != 200:
        ctype = resp.headers.get("Content-Type", "")
        head = resp.text[:160] if "json" in ctype else ""
        try:
            err = resp.json().get("error", "") if "json" in ctype else ""
        except (json.JSONDecodeError, ValueError):
            err = head
        return None, _classify_payload_error(err) if err else _classify_http(status)
    return {"content": resp.text, "http_status": status, "page_status": None}, None


def fetch_keenable(url):
    """One Keenable live fetch (markdown); returns (content, hard_error)."""
    key = os.getenv(KEY_ENV["keenable"])
    if not key:
        return None, "config_error: KEENABLE_API_KEY not configured"
    resp, terr = _get("https://api.keenable.ai/v1/fetch",
                      params={"url": url, "live": "true"},
                      headers={"X-API-Key": key}, timeout=90)
    if terr:
        return None, terr
    status = resp.status_code
    if status != 200:
        try:
            err = resp.json().get("message", "") or resp.json().get("error", "")
        except (json.JSONDecodeError, ValueError, AttributeError):
            err = resp.text[:160]
        return None, _classify_payload_error(err) if err else _classify_http(status)
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None, "malformed_response: invalid JSON"
    content = (payload or {}).get("content")
    if content is None:
        return None, "malformed_response: no content in response"
    return {"content": content, "http_status": status,
            "page_status": None, "title": (payload or {}).get("title")}, None


def fetch_browserbase(url):
    """One Browserbase Fetch (raw, no JS); returns (content, hard_error)."""
    key = os.getenv(KEY_ENV["browserbase"])
    if not key:
        return None, "config_error: BROWSERBASE_API_KEY not configured"
    resp, terr = _post("https://api.browserbase.com/v1/fetch",
                       body={"url": url},  # raw format: cheapest; proxies off (free tier)
                       headers={"Content-Type": "application/json",
                                "X-BB-API-Key": key}, timeout=90)
    if terr:
        return None, terr
    status = resp.status_code
    if status != 200:
        try:
            err = resp.json().get("message", "") or resp.json().get("error", "")
        except (json.JSONDecodeError, ValueError, AttributeError):
            err = resp.text[:160]
        return None, _classify_payload_error(err) if err else _classify_http(status)
    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        return None, "malformed_response: invalid JSON"
    content = (payload or {}).get("content")
    if content is None:
        return None, "malformed_response: no content in response"
    if isinstance(content, dict):
        content = json.dumps(content)
    return {"content": content, "http_status": status,
            "page_status": (payload or {}).get("statusCode")}, None


FETCHERS = {
    "firecrawl": fetch_firecrawl,
    "scrapedo": fetch_scrapedo,
    "keenable": fetch_keenable,
    "browserbase": fetch_browserbase,
}


def _canonical_path(content):
    """Extract the page's canonical URL host+path (never query/params).

    Tells us which page Amazon thinks it served (dp vs offer-listing) even
    when our HTTP layer cannot see server-side merges. Returns None when
    no canonical tag is present (e.g., markdown-only providers).
    """
    if not content:
        return None
    tag = _CANONICAL_TAG_RE.search(content)
    if not tag:
        return None
    href = _HREF_RE.search(tag.group(0))
    if not href:
        return None
    url = href.group(1)
    try:
        from urllib.parse import urlparse
        parts = urlparse(url)
        host = parts.netloc or "amazon.com"
        return "%s%s" % (host, parts.path or "/")
    except Exception:
        return None


def scan_markers(content):
    """Count seller/block/offer marker hits in content (never returns content)."""
    text = content or ""
    return {
        "seller_markers": {k: len(rx.findall(text)) for k, rx in _SELLER_MARKERS.items()},
        "block_markers": {k: len(rx.findall(text)) for k, rx in _BLOCK_MARKERS.items()},
        "offer_markers": {k: len(rx.findall(text)) for k, rx in _OFFER_MARKERS.items()},
        "canonical": _canonical_path(text),
    }


def preflight(provider, asin, page, run_dir):
    """Exactly ONE live request. Returns the scrubbed record."""
    asin = (asin or "").strip().upper()
    if provider not in FETCHERS:
        return {"provider": provider, "asin": asin, "outcome": "config_error",
                "detail": "unknown provider"}
    if not re.fullmatch(r"[A-Z0-9]{10}", asin or ""):
        return {"provider": provider, "asin": asin, "outcome": "config_error",
                "detail": "invalid ASIN"}
    url = "%s/dp/%s" % (MARKETPLACE, asin) if page == "dp" \
        else "%s/gp/offer-listing/%s" % (MARKETPLACE, asin)
    started = time.time()
    try:
        result, hard_error = FETCHERS[provider](url)
    except Exception as exc:  # never raises into the runner
        hard_error, result = "transport_error: %s" % type(exc).__name__, None
    elapsed = round(time.time() - started, 2)
    if hard_error:
        kind = hard_error.split(":")[0]
        record = {"provider": provider, "asin": asin, "page": page, "url_host": "amazon.com",
                  "outcome": kind, "detail": hard_error[:160],
                  "elapsed_seconds": elapsed, "requests_used": 1}
    else:
        content = result["content"]
        marks = scan_markers(content)
        blocked = any(v > 0 for v in marks["block_markers"].values())
        sellers = sum(marks["seller_markers"].values())
        roster = sum(marks["offer_markers"].values())
        record = {"provider": provider, "asin": asin, "page": page, "url_host": "amazon.com",
                  "outcome": "blocked" if blocked else ("has_seller_data" if sellers > 0 else "no_data_found"),
                  "roster_distinct": roster > 0,
                  "http_status": result.get("http_status"),
                  "page_status": result.get("page_status"),
                  "content_bytes": len(content), "content_head": content[:400],
                  "markers": marks, "elapsed_seconds": elapsed, "requests_used": 1}
        if result.get("title"):
            record["page_title"] = str(result["title"])[:160]
    path = os.path.join(run_dir, "probe_%s_%s_%s.json" % (provider, asin, page))
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=True)
    record["_evidence"] = path
    return record


def main(argv=None):
    ap = argparse.ArgumentParser(description="Free-tier seller-data probe (preflight)")
    ap.add_argument("--mode", choices=("status", "preflight"), required=True)
    ap.add_argument("--provider", choices=list(PROVIDERS))
    ap.add_argument("--asin")
    ap.add_argument("--page", choices=("dp", "offer"), default="dp")
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--max-requests", type=int, default=0)
    args = ap.parse_args(argv)

    if args.mode == "status":
        print(json.dumps(
            {"mode": "status", "live_calls": 0,
             "keys": {p: bool(os.getenv(KEY_ENV[p])) for p in PROVIDERS}}, indent=2))
        return 0

    # preflight: exactly ONE live request, explicit --live + finite cap
    if not args.live:
        print("refused: preflight requires --live", file=sys.stderr)
        return 2
    if args.max_requests != 1:
        print("refused: preflight requires --max-requests 1 (exactly one request)",
              file=sys.stderr)
        return 2
    if not args.provider or not args.asin:
        print("refused: preflight requires --provider and --asin", file=sys.stderr)
        return 2
    run_dir = _run_dir()
    record = preflight(args.provider, args.asin, args.page, run_dir)
    printable = {k: v for k, v in record.items() if k != "content_head"}
    printable["content_head_chars"] = len(record.get("content_head", ""))
    print(json.dumps(printable, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
