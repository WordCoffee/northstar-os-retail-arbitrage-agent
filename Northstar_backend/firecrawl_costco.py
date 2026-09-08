"""Firecrawl — Costco item-detail parallel adapter (free-tier redundancy).

A second drop-in for Unwrangle's `costco_detail` role, running in PARALLEL
with ``bright_data_costco.py``: it uses the Firecrawl Scrape API (one POST to
``https://api.firecrawl.dev/v2/scrape`` returning ``rawHtml``) and parses the
exact same normalized record contract via the shared
``bright_data_costco.parse_costco_item_page`` parser, so evidence is
byte-compatible with the Bright Data adapter (same field vocabulary, same
null-first discipline, same soft/hard failure taxonomy plus two extra typed
hard failures that are specific to how Firecrawl behaves: ``rate_limited``
and ``credits_exhausted``).

Free tier (verified 2026-09-08): the $0 plan renews 1,000 pages/month
recurring, no credit card, 2 concurrent requests, low rate limits — a
perfect fit for the sequential, one-request-per-item detail batch. When the
monthly allowance is spent, Firecrawl returns HTTP 402, which this adapter
surfaces as a typed ``credits_exhausted`` hard failure (never conflated with
auth).

Gating (fail-closed):
  FIRECRAWL_COSTCO_DETAIL_ENABLED=1 is required to run live calls. Default 0.

Discipline (mirrors Batch 08/10 and bright_data_costco.py):
  - one request per item via requests.post to /v2/scrape, ZERO retries
  - sequential pacing: FIRECRAWL_COSTCO_REQUEST_DELAY_SECONDS (default 2.0)
  - HARD failures (config_error / auth_error / http_error / transport_error /
    rate_limited / credits_exhausted / malformed_response) HALT the batch
    immediately (circuit breaker) — successes already captured are persisted,
    then the batch stops.
  - SOFT per-item failures keep the batch moving:
      url_not_found  — the page is a Costco content-level "Page Not Found!"
      no_data_found  — HTTP 200 but no Product JSON-LD and no parseable title
    These produce normalized records with NO fabricated fields (all null-first).
  - exact HTTP status via LAST_HTTP_STATUS, a typed LAST_ERROR string, and the
    page-level status (metadata.statusCode) via LAST_PAGE_STATUS on every
    outcome. Raw evidence (scrubbed, never the API key) is persisted under the
    same run-directory convention as the Bright Data adapter, keyed with the
    `firecrawl_` prefix.

Env vars:
  FIRECRAWL_COSTCO_DETAIL_ENABLED        (default "0"; "1" enables live calls)
  FIRECRAWL_API_KEY                      (required for live; value never logged)
  FIRECRAWL_COSTCO_REQUEST_URL           (default https://api.firecrawl.dev/v2/scrape)
  FIRECRAWL_COSTCO_REQUEST_DELAY_SECONDS (default 2.0)
  FIRECRAWL_COSTCO_REQUEST_TIMEOUT_SECONDS (default 60)
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

import bright_data_costco  # reuses the shared Costco page parser + conventions

# --- run / gate constants ----------------------------------------------------
RUN_ID = bright_data_costco.RUN_ID
DEFAULT_RUN_DIR = bright_data_costco.DEFAULT_RUN_DIR

GATE_ENV = "FIRECRAWL_COSTCO_DETAIL_ENABLED"
DELAY_ENV = "FIRECRAWL_COSTCO_REQUEST_DELAY_SECONDS"
DEFAULT_DELAY_SECONDS = 2.0
KEY_ENV = "FIRECRAWL_API_KEY"
REQUEST_URL_ENV = "FIRECRAWL_COSTCO_REQUEST_URL"
DEFAULT_REQUEST_URL = "https://api.firecrawl.dev/v2/scrape"
TIMEOUT_ENV = "FIRECRAWL_COSTCO_REQUEST_TIMEOUT_SECONDS"
DEFAULT_TIMEOUT_SECONDS = 60

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

# --- transport state (test-injectable, mirrors bright_data_client) -----------
LAST_HTTP_STATUS = None  # type: Optional[int]
LAST_ERROR = None  # type: Optional[str]  (typed: config_error | auth_error | ... )
LAST_PAGE_STATUS = None  # type: Optional[int]  (the page's own statusCode)

_AUTH_RE = re.compile(r"\b(auth|forbidden|denied)\b", re.I)
_CREDITS_RE = re.compile(r"\b(payment|credit|quota|billing)\b", re.I)


def _gate_enabled() -> bool:
    """Live-call gate: FIRECRAWL_COSTCO_DETAIL_ENABLED must be '1'."""
    return os.getenv(GATE_ENV, "0").strip().upper() == "1"


def _request_url() -> str:
    return os.getenv(REQUEST_URL_ENV, DEFAULT_REQUEST_URL).strip() or DEFAULT_REQUEST_URL


def _timeout() -> int:
    try:
        return max(1, int(float(os.getenv(TIMEOUT_ENV, DEFAULT_TIMEOUT_SECONDS))))
    except (TypeError, ValueError):
        return DEFAULT_TIMEOUT_SECONDS


def _fetch_item_page(url: str) -> Optional[str]:
    """One Firecrawl Scrape request; returns rawHtml or None on hard failure.

    Sets LAST_HTTP_STATUS / LAST_ERROR / LAST_PAGE_STATUS and NEVER raises
    (except the missing-key ValueError contract, mirrored from
    bright_data_client). The API key is only read for the Authorization
    header and never included in any persisted payload.
    """
    global LAST_HTTP_STATUS, LAST_ERROR, LAST_PAGE_STATUS
    LAST_ERROR = None
    LAST_PAGE_STATUS = None

    key = os.getenv(KEY_ENV)
    if not key:
        LAST_HTTP_STATUS = None
        LAST_ERROR = "config_error: %s not configured" % KEY_ENV
        raise ValueError("%s not configured; cannot run live Firecrawl calls." % KEY_ENV)

    body = {
        "url": url,
        "formats": ["rawHtml"],
        "maxAge": 0,  # force a fresh scrape — the pull is for CURRENT prices
        "timeout": 60000,
        "proxy": "auto",
    }
    headers = {"Authorization": "Bearer %s" % key, "Content-Type": "application/json"}

    try:
        resp = requests.post(
            _request_url(), json=body, headers=headers, timeout=_timeout()
        )
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
        LAST_ERROR = "credits_exhausted: Firecrawl free allowance exhausted"
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

    if not isinstance(payload, dict) or payload.get("success") is not True:
        err_text = ""
        if isinstance(payload, dict):
            err_text = str(payload.get("error") or payload.get("message") or "")
        if _CREDITS_RE.search(err_text):
            LAST_ERROR = "credits_exhausted: %s" % err_text[:120]
        elif _AUTH_RE.search(err_text):
            LAST_ERROR = "auth_error: %s" % err_text[:120]
        else:
            LAST_ERROR = "http_error: success=false%s" % (
                ": %s" % err_text[:120] if err_text else ""
            )
        return None

    data = payload.get("data")
    if not isinstance(data, dict):
        LAST_ERROR = "malformed_response: missing data object"
        return None

    metadata = data.get("metadata")
    if isinstance(metadata, dict) and isinstance(metadata.get("statusCode"), int):
        LAST_PAGE_STATUS = metadata["statusCode"]

    raw_html = data.get("rawHtml")
    if raw_html is None:
        LAST_ERROR = "malformed_response: no rawHtml in response"
        return None
    return raw_html


def _classify_hard_failure(last_error, raise_exc) -> str:
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


def _persist_evidence(run_dir, ts, item_id, raw_record, norm_record):
    raw_dir = os.path.join(run_dir, "raw")
    norm_dir = os.path.join(run_dir, "normalized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"firecrawl_{item_id}_{ts}.json")
    norm_path = os.path.join(norm_dir, f"items_{item_id}_firecrawl_{ts}.json")
    with open(raw_path, "w", encoding="utf-8") as fh:
        json.dump(raw_record, fh, indent=2, ensure_ascii=True)
    with open(norm_path, "w", encoding="utf-8") as fh:
        json.dump(norm_record, fh, indent=2, ensure_ascii=True)
    return raw_path, norm_path


def refresh_product_details(
    item_ids: List[str],
    manifest_path: Optional[str] = None,
    run_dir: Optional[str] = None,
    delay: Optional[float] = None,
) -> Dict:
    """Fetch Costco item-detail pages via the Firecrawl Scrape API.

    Gated (FIRECRAWL_COSTCO_DETAIL_ENABLED=1). One request per item, zero
    retries, sequential pacing. HARD failures halt the batch; soft per-item
    failures (url_not_found / no_data_found) are recorded and the batch
    continues. Evidence (raw + normalized, scrubbed) is persisted under
    run_dir (default: the frozen 20260828T021658Z discovery run directory).
    """
    if not _gate_enabled():
        msg = (
            f"[FirecrawlCostco] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        print(msg)
        return {
            "status": "blocked",
            "reason": f"{GATE_ENV} not enabled",
            "provider": "FIRECRAWL",
            "run_id": RUN_ID,
            "items_requested": len(item_ids or []),
            "items_fetched": 0,
            "items_failed": 0,
            "items": [],
            "failures": [],
            "evidence_paths": [],
        }

    run_dir = run_dir or DEFAULT_RUN_DIR
    delay = max(0.0, float(delay if delay is not None else DEFAULT_DELAY_SECONDS))
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    expected_map = (
        bright_data_costco._load_expected(manifest_path) if manifest_path else {}
    )

    items: List[Dict] = []
    failures: List[Dict] = []
    evidence_paths: List[str] = []
    halted = False
    total = len(item_ids or [])

    for idx, item_id in enumerate(item_ids or []):
        if idx > 0:
            time.sleep(delay)

        item_id = str(item_id).strip()
        url = bright_data_costco._build_costco_url(item_id)
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
                "run_id": RUN_ID,
                "attempt": f"firecrawl_costco_{item_id}",
                "requested_at": requested_at,
                "provider": "FIRECRAWL",
                "platform": "firecrawl_scrape",
                "endpoint": _request_url(),
                "url": url,
                "http_status": http_status if http_status is not None else 0,
                "failure_type": failure_type,
                "last_error": last_error or (str(raise_exc) if raise_exc else None),
                "reason": (
                    f"http_{http_status}" if http_status is not None else failure_type
                ),
                "retries": 0,
                "stop_on_block": "halted_run",
                "scrubbed": True,
                "item_id": item_id,
            }
            failures.append(fail_rec)
            raw_path, norm_path = _persist_evidence(
                run_dir, ts, item_id, fail_rec, fail_rec
            )
            evidence_paths.extend([raw_path, norm_path])
            print(
                f"[{idx + 1}/{total}] item {item_id} FAILED: {failure_type} "
                f"(http={http_status}) — halting batch (circuit breaker)."
            )
            halted = True
            break

        item = bright_data_costco.parse_costco_item_page(
            html, item_id, expected_map.get(item_id)
        )
        items.append(item)

        raw_record = {
            "run_id": RUN_ID,
            "attempt": f"firecrawl_costco_{item_id}",
            "requested_at": requested_at,
            "provider": "FIRECRAWL",
            "platform": "firecrawl_scrape",
            "endpoint": _request_url(),
            "payload": {
                "url": url,
                "formats": ["rawHtml"],
                "maxAge": 0,
                "proxy": "auto",
            },
            "auth_header": "Bearer <redacted>",
            "http_status": http_status,
            "page_status": LAST_PAGE_STATUS,
            "failure_type": None,
            "last_error": last_error,
            "retries": 0,
            "scrubbed": True,
            "response_body_bytes": len((html or "").encode("utf-8")),
            "response_body_diagnostic": bright_data_costco._body_diagnostic(html),
            "response_html_head_capped": (html or "")[: bright_data_costco.HEAD_CAP_CHARS],
        }
        norm_record = {
            "run_id": RUN_ID,
            "attempt": f"firecrawl_costco_{item_id}",
            "requested_at": requested_at,
            "provider": "FIRECRAWL",
            "platform": "firecrawl_scrape",
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
        raw_path, norm_path = _persist_evidence(
            run_dir, ts, item_id, raw_record, norm_record
        )
        evidence_paths.extend([raw_path, norm_path])

        status_marker = item["identity_match_status"]
        print(
            f"[{idx + 1}/{total}] item {item_id} {status_marker} "
            f"http={http_status} title={item.get('exact_title')} "
            f"price={item.get('listed_price')} body={bright_data_costco._body_diagnostic(html)}"
        )

    return {
        "status": "halted" if halted else "completed",
        "provider": "FIRECRAWL",
        "run_id": RUN_ID,
        "attempt": f"firecrawl_costco_run_{ts}",
        "items_requested": total,
        "items_fetched": len(items),
        "items_failed": len(failures),
        "items_soft_failed": sum(
            1
            for it in items
            if it.get("identity_match_status") in SOFT_FAILURE_TYPES
        ),
        "items": items,
        "failures": failures,
        "evidence_paths": evidence_paths,
    }


# --- CLI -------------------------------------------------------------------
def _expand_item_ids(tokens):
    """Accept both space- and comma-separated Costco item IDs."""
    out = []
    for tok in tokens or []:
        for part in str(tok).split(","):
            part = part.strip()
            if part:
                out.append(part)
    return out


def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="firecrawl_costco.py",
        description="Firecrawl Costco item-detail adapter (gated, free-tier redundancy).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    details = sub.add_parser("details", help="item-detail operations")
    details_sub = details.add_subparsers(dest="details_command", required=True)
    refresh = details_sub.add_parser(
        "refresh", help="refresh item details (live, gated)"
    )
    refresh.add_argument(
        "--item-ids", nargs="+", required=True, help="Costco item numbers"
    )
    refresh.add_argument(
        "--expected-json",
        default=None,
        help="manifest-style JSON with requested_title/requested_brand/requested_pack",
    )
    refresh.add_argument(
        "--run-dir",
        default=None,
        help="evidence run directory (default: frozen 20260828T021658Z discovery run)",
    )
    refresh.add_argument("--delay", type=float, default=None)

    args = parser.parse_args(argv)

    if not args.command == "details" or not args.details_command == "refresh":
        parser.error("only 'details refresh' is implemented")

    if not _gate_enabled():
        print(
            f"[FirecrawlCostco] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        return 2

    summary = refresh_product_details(
        item_ids=_expand_item_ids(args.item_ids),
        manifest_path=args.expected_json,
        run_dir=args.run_dir,
        delay=args.delay,
    )
    print("\n=== SUMMARY ===")
    print(f"status          : {summary['status']}")
    print(f"items_requested : {summary['items_requested']}")
    print(f"items_fetched   : {summary['items_fetched']}")
    print(f"items_failed    : {summary['items_failed']}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())