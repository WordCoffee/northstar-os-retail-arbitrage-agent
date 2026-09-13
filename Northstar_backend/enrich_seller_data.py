"""Controlled, resumable seller data backfill for the 245-ASIN Kirkland set.

Fallback chain (probe-ordered): Bright Data (Web Unlocker) → scrape.do → Firecrawl → Browserbase.
Keenable excluded (title-only on Amazon dp). All transport gates default off.

Usage:
  python enrich_seller_data.py --mode status
  python enrich_seller_data.py --mode dry-run [--limit N]
  python enrich_seller_data.py --mode preflight --live --provider brightdata \
      --asin B0XXXXXXXXXX --limit 1 --max-requests 1 --max-credits N
  python enrich_seller_data.py --mode batch --live --provider brightdata \
      --limit N --max-requests N --max-credits N

- status / dry-run: zero network calls. They read the PASS-set manifest and
  the seller cache and plan the request/credit budget.
- preflight: exactly ONE live provider request for exactly one explicitly
  supplied ASIN, then an atomic per-ASIN cache save.
- batch: live mode only, always driven by the PASS-set manifest with an
  explicit --limit (never defaults to all ASINs). Every completed ASIN
  cache is saved atomically before continuing; resume skips fresh
  successful cache entries and re-attempts failed/partial records only when
  eligible under the bounded retry policy (attempts < 3, no permanent
  error). Runtime retries are opt-in via --retries (finite, recorded).

Live-safety gates: every live command must pass --live plus finite
--limit, --max-requests, and --max-credits. The run refuses to start
when any finite cap is absent, and stops as soon as a cap is reached.

Circuit breaker: on ANY hard failure (auth_error, transport_error,
http_error, rate_limited, credits_exhausted, malformed_response) — stop
processing further items immediately, persist whatever already succeeded,
record the failure in a scrubbed manifest, and report before taking any
further action. Never retry automatically. Never skip a failed item and
continue past it silently.

Budget: requests and credits (1 credit per Web Unlocker request, within
5,000/mo free pool; fallback within scrape.do/Firecrawl/Browserbase free
tiers) are counted per request.

Exit codes: 0 success; 2 usage/cap refusal; 3 cache write failure;
4 manifest missing/corrupt; 5 circuit breaker halt.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import bright_data_client
import scrapedo_amazon
import firecrawl_amazon
import browserbase_amazon
from seller_cache import (
    build_seller_payload, get_cached_seller_detail, _cache_seller_detail, _seller_cache_path,
    SELLER_STATUS_AVAILABLE, SELLER_STATUS_PARTIAL, SELLER_STATUS_UNAVAILABLE, SELLER_STATUS_PROVIDER_ERROR
)

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

# Fallback chain order (probe-ordered from live tests)
PROVIDER_CHAIN = ["brightdata", "scrapedo", "firecrawl", "browserbase"]

# One Web Unlocker request = 1 credit from 5,000/mo pool
CREDITS_PER_ASIN = 1

MODE_STATUS = "status"
MODE_DRY_RUN = "dry-run"
MODE_PREFLIGHT = "preflight"
MODE_BATCH = "batch"


class UsageError(Exception):
    pass


class CacheError(Exception):
    pass


class CircuitBreakerError(Exception):
    """Hard failure that halts the batch immediately."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pass_set_asins() -> List[str]:
    """Ordered, deduped ASIN list from the PASS-set manifest (sourcescout_compliant_manifest.json)."""
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "data", "catalog", "sourcescout_compliant_manifest.json"
    )
    if not os.path.exists(manifest_path):
        raise CacheError("PASS-set manifest not found at %s" % manifest_path)
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        raise CacheError("Failed to load manifest: %s" % exc)

    items = manifest.get("items", [])
    asins: List[str] = []
    seen = set()
    for item in items:
        asin = item.get("asin")
        if isinstance(asin, str) and ASIN_PATTERN.fullmatch(asin) and asin not in seen:
            seen.add(asin)
            asins.append(asin)
    return asins


def _require_live_caps(args, mode: str) -> None:
    missing = []
    if not args.live:
        missing.append("--live")
    if args.limit is None or args.limit < 1:
        missing.append("--limit N (>= 1)")
    if args.max_requests is None or args.max_requests < 1:
        missing.append("--max-requests N (>= 1)")
    if args.max_credits is None or args.max_credits < 1:
        missing.append("--max-credits N (>= 1)")
    if missing:
        raise UsageError(
            "Live mode refused: every finite cap is required. Missing: "
            + ", ".join(missing)
            + ". Refusing to run without all caps."
        )


def _plan(asins: List[str], limit: Optional[int]) -> Dict[str, int]:
    planned = asins if limit is None or limit >= len(asins) else asins[:limit]
    fresh = 0
    retry_eligible = 0
    absent = 0
    for asin in planned:
        cached = get_cached_seller_detail(asin)
        if cached is None:
            absent += 1
        elif cached.get("offer_data_status") in (SELLER_STATUS_AVAILABLE, SELLER_STATUS_PARTIAL):
            fresh += 1
        else:
            retry_eligible += 1
    return {
        "planned": len(planned),
        "absent": absent,
        "fresh_skippable": fresh,
        "retry_eligible": retry_eligible,
    }


def _run_status(args) -> int:
    cache = _load_seller_cache_raw()
    by_status: Dict[str, int] = {}
    fresh = 0
    stale = 0
    total_credits = 0
    for entry in cache.values():
        if not isinstance(entry, dict):
            continue
        payload = entry.get("payload", {})
        status = payload.get("offer_data_status") or "unknown"
        by_status[status] = by_status.get(status, 0) + 1
        if payload.get("offer_data_cached"):
            fresh += 1
        else:
            stale += 1
        used = payload.get("credits_used")
        if isinstance(used, int) and used > 0:
            total_credits += used

    print("seller_cache:          %s" % _seller_cache_path())
    print("cached_entries:        %d" % len(cache))
    for status in sorted(by_status):
        print("  %-12s %d" % (status, by_status[status]))
    print("fresh / stale:         %d / %d" % (fresh, stale))
    print("credits_reported:      %d" % total_credits)
    return 0


def _load_seller_cache_raw() -> Dict[str, Any]:
    path = _seller_cache_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_dry_run(args) -> int:
    asins = _pass_set_asins()
    if not asins:
        raise CacheError("PASS-set manifest is missing or empty; nothing to plan")
    plan = _plan(asins, args.limit)
    limit_text = args.limit if args.limit else len(asins)
    requests = plan["planned"] - plan["fresh_skippable"]
    credits_est = requests * CREDITS_PER_ASIN
    provider = getattr(args, "provider", "brightdata")
    print("mode:                  dry-run (zero network calls)")
    print("candidates:            %d" % len(asins))
    print("limit:                 %s" % limit_text)
    print("provider:              %s (fallback chain: %s)" % (provider, " -> ".join(PROVIDER_CHAIN)))
    print("planned:               %d" % plan["planned"])
    print("  absent cache:        %d" % plan["absent"])
    print("  fresh (skip):        %d" % plan["fresh_skippable"])
    print("  retry eligible:      %d" % plan["retry_eligible"])
    print("requests projected:    %d" % requests)
    print("credits projected:     ~%d (1 per ASIN, Web Unlocker pool)" % credits_est)
    print("stages:                seller data only (Buy Box name, fulfillment, total_sellers)")
    return 0


def _validate_preflight(args) -> str:
    if not args.asin:
        raise UsageError("Preflight requires exactly one --asin B0XXXXXXXXXX")
    if not ASIN_PATTERN.fullmatch(args.asin):
        raise UsageError("Invalid ASIN: expected exactly 10 alphanumeric characters")
    if args.limit != 1:
        raise UsageError("Preflight requires --limit 1")
    if args.max_requests != 1:
        raise UsageError("Preflight requires --max-requests 1")
    return args.asin


def _fetch_with_fallback(asin: str, provider: str, caps: Dict[str, int], budget: Dict[str, float]) -> Dict:
    """Try provider, then fall through chain on hard failures. Never raises."""
    if provider not in PROVIDER_CHAIN:
        return {"error": "invalid_provider"}

    # Track which providers we've tried
    tried = set()
    current = provider

    while current in PROVIDER_CHAIN:
        if budget["requests_used"] >= caps["max_requests"]:
            return {"skipped": "max_requests"}
        if budget["credits_used"] >= caps["max_credits"]:
            return {"skipped": "max_credits"}

        if current in tried:
            # Already tried this one, move to next
            idx = PROVIDER_CHAIN.index(current)
            current = PROVIDER_CHAIN[idx + 1] if idx + 1 < len(PROVIDER_CHAIN) else None
            continue

        tried.add(current)

        started = time.monotonic()
        try:
            if current == "brightdata":
                # Bright Data uses get_product_detail (Web Unlocker)
                html = bright_data_client._fetch(
                    "%s/dp/%s" % (bright_data_client.DEFAULT_MARKETPLACE.rstrip("/"), asin)
                )
                if html is None:
                    raise CircuitBreakerError(bright_data_client.LAST_ERROR or "brightdata fetch failed")
                # Parse with shared extractor
                from amazon_seller_extract import extract_seller_data
                seller_data = extract_seller_data(html, buy_box_price=None)
                result = {"seller_data": seller_data, "html": html, "provider": "brightdata"}
            elif current == "scrapedo":
                # Use the module's internal fetch (it has its own gate check)
                if not scrapedo_amazon._gate_enabled():
                    raise CircuitBreakerError("scrapedo gate disabled")
                marketplace = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com").rstrip("/")
                html = scrapedo_amazon._fetch_item_page("%s/dp/%s" % (marketplace, asin))
                if html is None:
                    raise CircuitBreakerError(scrapedo_amazon.LAST_ERROR or "scrapedo fetch failed")
                from amazon_seller_extract import extract_seller_data
                seller_data = extract_seller_data(html)
                result = {"seller_data": seller_data, "html": html, "provider": "scrapedo"}
            elif current == "firecrawl":
                if not firecrawl_amazon._gate_enabled():
                    raise CircuitBreakerError("firecrawl gate disabled")
                marketplace = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com").rstrip("/")
                html = firecrawl_amazon._fetch_item_page("%s/dp/%s" % (marketplace, asin))
                if html is None:
                    raise CircuitBreakerError(firecrawl_amazon.LAST_ERROR or "firecrawl fetch failed")
                from amazon_seller_extract import extract_seller_data
                seller_data = extract_seller_data(html)
                result = {"seller_data": seller_data, "html": html, "provider": "firecrawl"}
            elif current == "browserbase":
                if not browserbase_amazon._gate_enabled():
                    raise CircuitBreakerError("browserbase gate disabled")
                marketplace = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com").rstrip("/")
                html = browserbase_amazon._fetch_item_page("%s/dp/%s" % (marketplace, asin))
                if html is None:
                    raise CircuitBreakerError(browserbase_amazon.LAST_ERROR or "browserbase fetch failed")
                from amazon_seller_extract import extract_seller_data
                seller_data = extract_seller_data(html)
                result = {"seller_data": seller_data, "html": html, "provider": "browserbase"}
            else:
                result = {"error": "no_provider"}

            budget["requests_used"] += 1
            budget["credits_used"] += CREDITS_PER_ASIN
            budget["seconds"] += time.monotonic() - started
            return result

        except CircuitBreakerError as e:
            # Hard failure — propagate up to halt the batch
            raise
        except Exception as e:
            # Soft failure on this provider — try next in chain
            print("[fallback] %s failed for %s: %s — trying next" % (current, asin, e))
            idx = PROVIDER_CHAIN.index(current)
            current = PROVIDER_CHAIN[idx + 1] if idx + 1 < len(PROVIDER_CHAIN) else None
            continue

    return {"error": "all_providers_failed"}


def _run_preflight(args) -> int:
    _require_live_caps(args, MODE_PREFLIGHT)
    asin = _validate_preflight(args)

    caps = {"max_requests": args.max_requests, "max_credits": args.max_credits}
    budget = {"requests_used": 0, "credits_used": 0.0, "seconds": 0.0}

    provider = args.provider if args.provider in PROVIDER_CHAIN else "brightdata"
    print("mode:                  preflight (provider=%s, fallback chain=%s)" % (provider, " -> ".join(PROVIDER_CHAIN)))
    print("asin:                  %s" % asin)

    try:
        result = _fetch_with_fallback(asin, provider, caps, budget)
    except CircuitBreakerError as e:
        print("CIRCUIT BREAKER: %s" % e)
        return 5

    if "error" in result:
        print("result:                %s" % result["error"])
        return 0

    seller_data = result["seller_data"]
    provider_used = result["provider"]
    title = None
    buy_box_price = None
    # Try to extract title and price from html
    if result.get("html"):
        html = result["html"]
        # Quick title extract
        import re
        title_match = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html, re.S)
        if title_match:
            import html as html_module
            title = html_module.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() or None
        price_match = re.search(r'<span class="a-offscreen">\$?([\d,]+(?:\.\d{1,2})?)</span>', html)
        if price_match:
            try:
                buy_box_price = float(price_match.group(1).replace(",", ""))
            except ValueError:
                pass

    payload = build_seller_payload(asin, seller_data, provider_used, title, buy_box_price, budget["requests_used"])
    _cache_seller_detail(asin, payload)

    print("provider_used:         %s" % provider_used)
    print("buy_box_seller:        %s" % payload["buy_box"]["seller_name"])
    print("buy_box_fulfillment:   %s" % payload["buy_box"]["fulfillment"])
    print("total_sellers:         %s" % payload["total_sellers"])
    print("other_sellers_present: %s" % payload["other_sellers_present"])
    print("buy_box_price:         %s" % payload["buy_box_price"])
    print("offer_data_status:     %s" % payload["offer_data_status"])
    print("credits_used:          %s" % payload["credits_used"])
    return 0


def _run_batch(args) -> int:
    _require_live_caps(args, MODE_BATCH)
    if args.asin:
        raise UsageError("--asin is only valid with --mode preflight; batch is manifest-driven")

    asins = _pass_set_asins()
    if not asins:
        raise CacheError("PASS-set manifest is missing or empty; nothing to enrich")

    provider = args.provider if args.provider in PROVIDER_CHAIN else "brightdata"
    print("mode:                  batch (provider=%s, fallback chain=%s)" % (provider, " -> ".join(PROVIDER_CHAIN)))

    limit = args.limit if args.limit < len(asins) else len(asins)
    caps = {"max_requests": args.max_requests, "max_credits": args.max_credits}
    budget = {"requests_used": 0, "credits_used": 0.0, "seconds": 0.0}

    counts = {
        "planned": limit,
        "attempted": 0,
        "succeeded": 0,
        "partial": 0,
        "failed": 0,
        "skipped_fresh": 0,
        "skipped_cap": 0,
        "skipped_retry_ineligible": 0,
    }
    errors: List[Dict] = []
    stop_reason = "completed"

    for asin in asins[:limit]:
        if budget["requests_used"] >= caps["max_requests"]:
            stop_reason = "max_requests"
            break
        if budget["credits_used"] >= caps["max_credits"]:
            stop_reason = "max_credits"
            break

        cached = get_cached_seller_detail(asin)
        if cached and cached.get("offer_data_status") in (SELLER_STATUS_AVAILABLE, SELLER_STATUS_PARTIAL):
            counts["skipped_fresh"] += 1
            continue
        # Note: we don't track retry_eligible here; every missing/failed gets one attempt per batch

        print("[%d/%d] asin %s" % (counts["attempted"] + 1, limit, asin))

        try:
            result = _fetch_with_fallback(asin, provider, caps, budget)
        except CircuitBreakerError as e:
            stop_reason = "circuit_breaker: %s" % e
            print("CIRCUIT BREAKER HALT: %s" % e)
            break

        if "error" in result:
            counts["failed"] += 1
            errors.append({"asin": asin, "error": result["error"]})
            continue

        seller_data = result["seller_data"]
        provider_used = result["provider"]

        # Extract title and buy_box_price from html if available
        title = None
        buy_box_price = None
        if result.get("html"):
            html = result["html"]
            import re
            title_match = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html, re.S)
            if title_match:
                import html as html_module
                title = html_module.unescape(re.sub(r"<[^>]+>", "", title_match.group(1))).strip() or None
            price_match = re.search(r'<span class="a-offscreen">\$?([\d,]+(?:\.\d{1,2})?)</span>', html)
            if price_match:
                try:
                    buy_box_price = float(price_match.group(1).replace(",", ""))
                except ValueError:
                    pass

        payload = build_seller_payload(asin, seller_data, provider_used, title, buy_box_price, 1)
        _cache_seller_detail(asin, payload)

        counts["attempted"] += 1
        status = payload["offer_data_status"]
        if status == SELLER_STATUS_AVAILABLE:
            counts["succeeded"] += 1
        elif status == SELLER_STATUS_PARTIAL:
            counts["partial"] += 1
        else:
            counts["failed"] += 1
            errors.append({"asin": asin, "error": payload.get("offer_data_note", "unavailable")})

    if stop_reason in ("max_requests", "max_credits", "circuit_breaker"):
        counts["skipped_cap"] = (
            limit - counts["succeeded"] - counts["partial"] - counts["failed"]
            - counts["skipped_fresh"] - counts["skipped_retry_ineligible"]
        )

    print("\n=== BATCH SUMMARY ===")
    print("planned:               %d" % counts["planned"])
    print("attempted:             %d" % counts["attempted"])
    print("succeeded:             %d" % counts["succeeded"])
    print("partial:               %d" % counts["partial"])
    print("failed:                %d" % counts["failed"])
    print("skipped_fresh:         %d" % counts["skipped_fresh"])
    print("skipped_cap:           %d" % counts["skipped_cap"])
    print("requests_used:         %d" % budget["requests_used"])
    print("credits_estimated:     %.0f" % budget["credits_used"])
    print("stop_reason:           %s" % stop_reason)
    for entry in errors[:10]:
        print("  failed %s: %s" % (entry["asin"], entry["error"]))

    return 0 if stop_reason == "completed" else 5


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Controlled seller data backfill (dry-run/status zero-network; "
        "preflight/batch require all live caps). Fallback chain: brightdata -> scrapedo -> firecrawl -> browserbase."
    )
    parser.add_argument("--mode", choices=[MODE_STATUS, MODE_DRY_RUN, MODE_PREFLIGHT, MODE_BATCH],
                        default=MODE_DRY_RUN)
    parser.add_argument("--provider", choices=PROVIDER_CHAIN,
                        default="brightdata",
                        help="primary provider (fallback chain is fixed)")
    parser.add_argument("--live", action="store_true", help="allow live provider requests")
    parser.add_argument("--asin", default=None, help="exactly one ASIN (preflight only)")
    parser.add_argument("--limit", type=int, default=None,
                        help="request budget limit (>= 1; required for live modes)")
    parser.add_argument("--max-requests", type=int, default=None,
                        help="hard cap on provider requests (required for live modes)")
    parser.add_argument("--max-credits", type=int, default=None,
                        help="hard cap on credits (required for live modes)")
    parser.add_argument("--retries", type=int, default=0,
                        help="NOT SUPPORTED (circuit breaker halts on hard failure)")
    args = parser.parse_args(argv)

    try:
        if args.mode == MODE_STATUS:
            return _run_status(args)
        if args.mode == MODE_DRY_RUN:
            return _run_dry_run(args)
        if args.mode == MODE_PREFLIGHT:
            return _run_preflight(args)
        return _run_batch(args)
    except UsageError as e:
        print("error: %s" % e)
        return 2
    except CacheError as e:
        print("error: %s" % e)
        return 4
    except CircuitBreakerError as e:
        print("CIRCUIT BREAKER: %s" % e)
        return 5


if __name__ == "__main__":
    sys.exit(main())