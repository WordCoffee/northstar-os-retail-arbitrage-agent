"""Browserbase — Amazon product page adapter (free-tier last resort).

One request per ASIN via Browserbase Fetch API (raw HTML, no JS on free
tier). Parses the same seller data contract via the shared
amazon_seller_extract parser so records are byte-compatible.

Free tier (verified 2026-09-13): 1,000 Fetch calls + 1 browser-hour/month.
NO proxies / NO CAPTCHA solving on free tier — expected weakest for Amazon.

Gating (fail-closed):
  BROWSERBASE_AMAZON_DETAIL_ENABLED=1 required for live calls. Default 0.

Discipline (mirrors firecrawl_costco.py / bright_data_costco.py):
  - one request per item via requests.post to /v1/fetch, ZERO retries
  - sequential pacing: BROWSERBASE_AMAZON_REQUEST_DELAY_SECONDS (default 3.0)
  - HARD failures (config_error / auth_error / http_error / transport_error /
    rate_limited / credits_exhausted / malformed_response) HALT the batch
    immediately (circuit breaker) — successes already captured are persisted,
    then the batch stops.
  - SOFT per-item failures keep the batch moving:
      url_not_found  — the page is a content-level "Page Not Found!"
      no_data_found  — HTTP 200 but no seller markers
    These produce normalized records with NO fabricated fields (all null-first).
  - exact HTTP status via LAST_HTTP_STATUS, typed LAST_ERROR string on every
    outcome. Raw evidence (scrubbed, never the API key) is persisted under
    the run-directory convention, keyed with the `browserbase_` prefix.

Env vars:
  BROWSERBASE_AMAZON_DETAIL_ENABLED        (default "0"; "1" enables live calls)
  BROWSERBASE_API_KEY                      (required for live; value never logged)
  BROWSERBASE_AMAZON_REQUEST_URL           (default https://api.browserbase.com/v1/fetch)
  BROWSERBASE_AMAZON_REQUEST_DELAY_SECONDS (default 3.0)
  BROWSERBASE_AMAZON_REQUEST_TIMEOUT_SECONDS (default 90)
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

import requests

from amazon_seller_extract import extract_seller_data

# --- run / gate constants ----------------------------------------------------

GATE_ENV = "BROWSERBASE_AMAZON_DETAIL_ENABLED"
DELAY_ENV = "BROWSERBASE_AMAZON_REQUEST_DELAY_SECONDS"
DEFAULT_DELAY_SECONDS = 3.0
KEY_ENV = "BROWSERBASE_API_KEY"
REQUEST_URL_ENV = "BROWSERBASE_AMAZON_REQUEST_URL"
DEFAULT_REQUEST_URL = "https://api.browserbase.com/v1/fetch"
TIMEOUT_ENV = "BROWSERBASE_AMAZON_REQUEST_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 90

HARD_FAILURE_TYPES = (
    "config_error",
    "auth_error",
    "http_error",
    "transport_error",
    "rate_limited",
    "credits_exhausted",
    "malformed_response",
)
SOFT_FAILURE_TYPES = ("url_not_found", "no_data_found")

# --- transport state (test-injectable) ---------------------------------------

LAST_HTTP_STATUS = None  # type: Optional[int]
LAST_ERROR = None  # type: Optional[str]
LAST_PAGE_STATUS = None  # type: Optional[int]

_AUTH_RE = re.compile(r"\b(auth|forbidden|denied|invalid.{0,10}key|api.{0,10}key)\b", re.I)
_CREDITS_RE = re.compile(r"\b(payment|credit|quota|billing|402|allowance|exhausted)\b", re.I)
_RATE_RE = re.compile(r"\b(rate|429|too many|throttl)\b", re.I)


def _gate_enabled() -> bool:
    """Live-call gate: BROWSERBASE_AMAZON_DETAIL_ENABLED must be '1'."""
    return os.getenv(GATE_ENV, "0").strip().upper() == "1"


def _request_url() -> str:
    return os.getenv(REQUEST_URL_ENV, DEFAULT_REQUEST_URL).strip() or DEFAULT_REQUEST_URL


def _timeout() -> int:
    try:
        return max(1, int(float(os.getenv(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def _fetch_item_page(url: str) -> Optional[str]:
    """One Browserbase Fetch request; returns raw content or None on hard failure.

    Sets LAST_HTTP_STATUS / LAST_ERROR / LAST_PAGE_STATUS and NEVER raises
    (except the missing-key ValueError contract). The API key is only read
    for the X-BB-API-Key header and never included in any persisted payload.
    """
    global LAST_HTTP_STATUS, LAST_ERROR, LAST_PAGE_STATUS
    LAST_ERROR = None
    LAST_PAGE_STATUS = None

    key = os.getenv(KEY_ENV)
    if not key:
        LAST_HTTP_STATUS = None
        LAST_ERROR = "config_error: %s not configured" % KEY_ENV
        raise ValueError("%s not configured; cannot run live Browserbase calls." % KEY_ENV)

    body = {"url": url}  # raw format, no proxies on free tier
    headers = {"Content-Type": "application/json", "X-BB-API-Key": key}

    try:
        resp = requests.post(_request_url(), json=body, headers=headers, timeout=_timeout())
    except requests.exceptions.Timeout:
        LAST_HTTP_STATUS = None
        LAST_ERROR = "transport_error: timeout"
        return None
    except requests.exceptions.RequestException:
        LAST_HTTP_STATUS = None
        LAST_ERROR = "transport_error: network_error"
        return None

    LAST_HTTP_STATUS = resp.status_code

    if resp.status_code == 402:
        LAST_ERROR = "credits_exhausted: Browserbase free allowance exhausted"
        return None
    if resp.status_code in (401, 403):
        LAST_ERROR = "auth_error: HTTP %s" % resp.status_code
        return None
    if resp.status_code == 429:
        LAST_ERROR = "rate_limited: HTTP 429"
        return None
    if resp.status_code != 200:
        LAST_ERROR = "http_error: HTTP %s" % resp.status_code
        return None

    try:
        payload = resp.json()
    except (json.JSONDecodeError, ValueError):
        LAST_ERROR = "malformed_response: invalid JSON"
        return None

    content = payload.get("content")
    if content is None:
        LAST_ERROR = "malformed_response: no content in response"
        return None

    if isinstance(content, dict):
        content = json.dumps(content)

    status_code = payload.get("statusCode")
    if isinstance(status_code, int):
        LAST_PAGE_STATUS = status_code

    LAST_ERROR = None
    return content


def _classify_hard_failure(last_error: Optional[str], raise_exc: Optional[BaseException]) -> str:
    """Map a no-HTML outcome to the typed hard-failure vocabulary."""
    if raise_exc is not None and "value_error" in str(raise_exc.__class__.__name__).lower():
        return "config_error"
    for token in ("credits_exhausted", "rate_limited", "malformed_response",
                  "auth_error", "http_error", "transport_error", "config_error"):
        if last_error and last_error.startswith(token):
            return token
    if raise_exc is not None:
        return "config_error"
    return "transport_error"


def _body_diagnostic(html: Optional[str]) -> str:
    if not html:
        return "empty"
    text = html.strip()
    if len(text) < 500:
        return "short:%d" % len(text)
    return "ok:%d" % len(text)


def _persist_evidence(run_dir: str, ts: str, asin: str, raw_record: Dict, norm_record: Dict) -> List[str]:
    raw_dir = os.path.join(run_dir, "raw")
    norm_dir = os.path.join(run_dir, "normalized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"browserbase_{asin}_{ts}.json")
    norm_path = os.path.join(norm_dir, f"items_{asin}_browserbase_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw_record, fh, indent=2, ensure_ascii=True)
    with open(norm_path, "w", encoding="utf-8") as fh:
        json.dump(norm_record, fh, indent=2, ensure_ascii=True)
    return [raw_path, norm_path]


def refresh_product_details(
    asins: List[str],
    manifest_path: Optional[str] = None,
    run_dir: Optional[str] = None,
    delay: Optional[float] = None,
) -> Dict:
    """Fetch Amazon product pages via Browserbase Fetch.

    Gated (BROWSERBASE_AMAZON_DETAIL_ENABLED=1). One request per ASIN, zero
    retries, sequential pacing. HARD failures halt the batch; soft per-item
    failures (url_not_found / no_data_found) are recorded and the batch
    continues. Evidence (raw + normalized, scrubbed) is persisted under
    run_dir.
    """
    if not _gate_enabled():
        msg = (
            f"[BrowserbaseAmazon] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        print(msg)
        return {
            "status": "blocked",
            "reason": f"{GATE_ENV} not enabled",
            "provider": "BROWSERBASE",
            "items_requested": len(asins or []),
            "items_fetched": 0,
            "items_failed": 0,
            "items": [],
            "failures": [],
            "evidence_paths": [],
        }

    run_dir = run_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "data", "enrich", "browserbase-amazon", "runs"
    )
    os.makedirs(run_dir, exist_ok=True)
    delay = max(0.0, float(delay if delay is not None else DEFAULT_DELAY_SECONDS))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    items: List[Dict] = []
    failures: List[Dict] = []
    evidence_paths: List[str] = []
    halted = False
    total = len(asins or [])

    marketplace = os.getenv("DEFAULT_MARKETPLACE", "https://www.amazon.com").rstrip("/")

    for idx, asin in enumerate(asins or []):
        if idx > 0:
            time.sleep(delay)

        asin = str(asin).strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{10}", asin):
            continue
        url = "%s/dp/%s" % (marketplace, asin)
        requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        html = None
        raise_exc = None
        try:
            html = _fetch_item_page(url)
        except ValueError as exc:
            raise_exc = exc
        except Exception as exc:  # noqa: BLE001 - adapter persists then reports
            raise_exc = exc

        http_status = LAST_HTTP_STATUS
        last_error = LAST_ERROR

        if html is None:
            failure_type = _classify_hard_failure(last_error, raise_exc)
            fail_rec = {
                "run_id": "browserbase_amazon_%s" % ts,
                "attempt": "browserbase_amazon_%s" % asin,
                "requested_at": requested_at,
                "provider": "BROWSERBASE",
                "platform": "browserbase_fetch",
                "endpoint": _request_url(),
                "url": url,
                "http_status": http_status if http_status is not None else 0,
                "failure_type": failure_type,
                "last_error": last_error or (str(raise_exc) if raise_exc else None),
                "reason": (
                    "http_%s" % http_status if http_status is not None else failure_type
                ),
                "retries": 0,
                "stop_on_block": "halted_run",
                "scrubbed": True,
                "asin": asin,
            }
            failures.append(fail_rec)
            evidence_paths.extend(_persist_evidence(run_dir, ts, asin, fail_rec, fail_rec))
            print(
                f"[{idx + 1}/{total}] asin {asin} FAILED: {failure_type} "
                f"(http={http_status}) — halting batch (circuit breaker)."
            )
            halted = True
            break

        # Parse with shared seller extractor
        seller_data = extract_seller_data(html)
        soft_failure = None
        if seller_data["total_sellers"] is None and not seller_data["other_sellers_present"]:
            soft_failure = "no_data_found"

        item = {
            "asin": asin,
            "buy_box_seller_name": seller_data["buy_box_seller_name"],
            "buy_box_fulfillment": seller_data["buy_box_fulfillment"],
            "total_sellers": seller_data["total_sellers"],
            "other_sellers_present": seller_data["other_sellers_present"],
            "lowest_price": seller_data["lowest_price"],
            "seller_marker_counts": seller_data["marker_counts"],
            "identity_match_status": soft_failure or "matched",
            "html_size": len(html),
        }
        items.append(item)

        raw_record = {
            "run_id": "browserbase_amazon_%s" % ts,
            "attempt": "browserbase_amazon_%s" % asin,
            "requested_at": requested_at,
            "provider": "BROWSERBASE",
            "platform": "browserbase_fetch",
            "endpoint": _request_url(),
            "payload": {"url": url},
            "auth_header": "X-BB-API-Key <redacted>",
            "http_status": http_status,
            "page_status": LAST_PAGE_STATUS,
            "failure_type": None,
            "last_error": last_error,
            "retries": 0,
            "scrubbed": True,
            "response_body_bytes": len(html.encode("utf-8")),
            "response_body_diagnostic": _body_diagnostic(html),
            "response_html_head_capped": html[:2000],
        }
        norm_record = {
            "run_id": "browserbase_amazon_%s" % ts,
            "attempt": "browserbase_amazon_%s" % asin,
            "requested_at": requested_at,
            "provider": "BROWSERBASE",
            "platform": "browserbase_fetch",
            "endpoint": _request_url(),
            "url": url,
            "http_status": http_status,
            "page_status": LAST_PAGE_STATUS,
            "failure_type": None,
            "retries": 0,
            "stop_on_block": "sequential_batch",
            "scrubbed": True,
            "item": item,
        }
        evidence_paths.extend(_persist_evidence(run_dir, ts, asin, raw_record, norm_record))

        status_marker = item["identity_match_status"]
        print(
            f"[{idx + 1}/{total}] asin {asin} {status_marker} "
            f"http={http_status} seller={item['buy_box_seller_name']} "
            f"total={item['total_sellers']} other={item['other_sellers_present']} "
            f"body={_body_diagnostic(html)}"
        )

    return {
        "status": "halted" if halted else "completed",
        "provider": "BROWSERBASE",
        "run_id": "browserbase_amazon_%s" % ts,
        "items_requested": total,
        "items_fetched": len(items),
        "items_failed": len(failures),
        "items_soft_failed": sum(1 for it in items if it.get("identity_match_status") in SOFT_FAILURE_TYPES),
        "items": items,
        "failures": failures,
        "evidence_paths": evidence_paths,
    }


# --- CLI -------------------------------------------------------------------

def _expand_asins(tokens):
    """Accept both space- and comma-separated ASINs."""
    out = []
    for tok in tokens or []:
        for part in str(tok).split(","):
            part = part.strip().upper()
            if part:
                out.append(part)
    return out


def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="browserbase_amazon.py",
        description="Browserbase Amazon product adapter (gated, free-tier last resort).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    details = sub.add_parser("details", help="product detail operations")
    details_sub = details.add_subparsers(dest="details_command", required=True)
    refresh = details_sub.add_parser("refresh", help="refresh product details (live, gated)")
    refresh.add_argument("--asins", nargs="+", required=True, help="ASINs to fetch")
    refresh.add_argument("--run-dir", default=None, help="evidence run directory")
    refresh.add_argument("--delay", type=float, default=None)

    args = parser.parse_args(argv)

    if not args.command == "details" or not args.details_command == "refresh":
        parser.error("only 'details refresh' is implemented")

    if not _gate_enabled():
        print(
            f"[BrowserbaseAmazon] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        return 2

    summary = refresh_product_details(
        asins=_expand_asins(args.asins),
        run_dir=args.run_dir,
        delay=args.delay,
    )
    print("\n=== SUMMARY ===")
    print("status          : %s" % summary["status"])
    print("items_requested : %s" % summary["items_requested"])
    print("items_fetched   : %s" % summary["items_fetched"])
    print("items_failed    : %s" % summary["items_failed"])
    return 0


if __name__ == "__main__":
    sys.exit(_cli())