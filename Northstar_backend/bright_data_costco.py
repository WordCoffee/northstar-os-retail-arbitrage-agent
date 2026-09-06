"""Bright Data Web Unlocker — Costco item-detail parallel adapter.

A drop-in swap for Unwrangle's `costco_detail` role, built as a PARALLEL
module: it uses the proven Web Unlocker transport (bright_data_client._fetch)
but never touches costco_api_client.py. Costco product pages expose a JSON-LD
Product block (title + offers.price) plus a descriptive <title> tag — both
verified live on items 424976, 926628, 98501, 690843, 1089787 in
operator-authorized probes (2026-09-05); 1493188 returned a content-level
"Page Not Found!" page and is handled as a typed per-item failure.

Gating (fail-closed):
  BRIGHTDATA_COSTCO_DETAIL_ENABLED=1 is required to run live calls. Default 0.

Discipline (mirrors Batch 08/10):
  - one request per item via bright_data_client._fetch, ZERO retries
  - sequential pacing: BRIGHTDATA_REQUEST_DELAY_SECONDS (default 2.0)
  - HARD failures (auth_error / http_error / transport_error / config_error)
    HALT the batch immediately (circuit breaker) — successes already captured
    are persisted, then the batch stops.
  - SOFT per-item failures keep the batch moving:
      url_not_found  — HTTP 200 but content-level "Page Not Found!" page
      no_data_found  — HTTP 200 but no Product JSON-LD and no parseable title
    These produce normalized records with NO fabricated fields (all null-first).
  - exact HTTP status via bright_data_client.LAST_HTTP_STATUS, plus a scrubbed
    response-headers snapshot via LAST_RESPONSE_HEADERS when the transport
    supplies one. Raw evidence on EVERY fetched item — including empty or
    unusually short bodies — records response_body_bytes,
    response_body_diagnostic ('empty' | 'short' | 'normal'), and
    response_html_head_capped, so future no_data_found items are diagnosable
    (unlocker empty body vs anti-bot/challenge interstitial) instead of just
    'zero bytes'.

Normalization contract (identical field vocabulary to the Batch 10
normalized/items.json records): requested_item_id, returned_costco_item_id,
exact_title, brand, listed_price, currency, unit_price, quantity_or_pack,
size_or_weight, UPC_GTIN_EAN, availability, product_url, captured_at,
identity_match_status, missing_fields. Missing/unparseable values are None,
never 0 or fabricated.

Lookup method is item-number flat URL only (/.product.<id>.html). Alternate
slug/search-based lookup for unresolvable item numbers is deliberately OUT OF
SCOPE for this build (deferred follow-up).

Env vars:
  BRIGHTDATA_COSTCO_DETAIL_ENABLED  (default "0"; "1" enables live calls)
  BRIGHTDATA_REQUEST_DELAY_SECONDS  (default 2.0)
  (transport settings come from bright_data_client: BRIGHTDATA_UNLOCKER_API_KEY,
   BRIGHTDATA_UNLOCKER_ZONE, BRIGHTDATA_REQUEST_TIMEOUT_SECONDS)
"""

import argparse
import html as html_module
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

import bright_data_client  # transport layer (LAST_ERROR / LAST_HTTP_STATUS)

RUN_ID = "20260828T021658Z"
DEFAULT_RUN_DIR = os.path.join("data", "costco-discovery-runs", RUN_ID)

GATE_ENV = "BRIGHTDATA_COSTCO_DETAIL_ENABLED"
DELAY_ENV = "BRIGHTDATA_REQUEST_DELAY_SECONDS"
DEFAULT_DELAY_SECONDS = 2.0

# Evidence diagnostics for empty/short response bodies (design input: make
# future no_data_found evidence diagnosable — blocked vs genuinely absent).
HEAD_CAP_CHARS = 2000
SHORT_BODY_CHARS = 512

COSTCO_ITEM_URL_TEMPLATE = "https://www.costco.com/.product.{item_id}.html"

# --- parser patterns --------------------------------------------------------
_TITLE_TAG_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.S | re.I)
_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.S | re.I,
)
_PAGE_NOT_FOUND_RE = re.compile(r"page\s*not\s*found", re.I)
_KS_BRAND_RE = re.compile(r"kirkland\s*signature", re.I)
_COUNT_PACK_RE = re.compile(
    r"(\d[\d,]*)\s*[-–—]?\s*(count|tablets?|softgels?|servings?|ounces?|oz\.?|"
    r"ct\.?|capsules?|pills?|bottles?|wipes?)\b",
    re.I,
)

_CONTRACT_FIELDS = (
    "exact_title",
    "brand",
    "listed_price",
    "currency",
    "unit_price",
    "quantity_or_pack",
    "size_or_weight",
    "UPC_GTIN_EAN",
    "availability",
)

# Failure vocabularies (Batch 08 pattern).
HARD_FAILURE_TYPES = ("config_error", "auth_error", "http_error", "transport_error")
SOFT_FAILURE_TYPES = ("url_not_found", "no_data_found")


def _gate_enabled() -> bool:
    """Live-call gate: BRIGHTDATA_COSTCO_DETAIL_ENABLED must be '1'."""
    return os.getenv(GATE_ENV, "0").strip().upper() == "1"


def _build_costco_url(item_id) -> str:
    return COSTCO_ITEM_URL_TEMPLATE.format(item_id=str(item_id).strip())


def _clean_text(raw) -> Optional[str]:
    if raw is None:
        return None
    clean = html_module.unescape(re.sub(r"<[^>]+>", "", raw))
    return " ".join(clean.split()) or None


def _coerce_price(value) -> Optional[float]:
    """Run any price shape ($17.99, 17.99, '17.99', '1,199.00') to float or None."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip().lstrip("$"))
    except (ValueError, TypeError):
        return None


def _parse_jsonld_product(html) -> Optional[Dict]:
    """Best JSON-LD Product block: name + offers-aware price. None if absent.

    Price sources, in priority order: an `offers` dict's price/lowPrice/highPrice,
    the first price-bearing offer in an `offers` list, then top-level `price`.
    """
    for block in _JSONLD_RE.findall(html or ""):
        try:
            data = json.loads(block)
        except (ValueError, TypeError):
            continue
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict) or data.get("@type") != "Product":
            continue

        price = None
        offers = data.get("offers")
        if isinstance(offers, dict):
            for key in ("price", "lowPrice", "highPrice"):
                if offers.get(key) is not None:
                    price = offers[key]
                    break
        elif isinstance(offers, list):
            for offer in offers:
                if not isinstance(offer, dict):
                    continue
                for key in ("price", "lowPrice"):
                    if offer.get(key) is not None:
                        price = offer[key]
                        break
                if price is not None:
                    break
        if price is None:
            price = data.get("price")

        brand = data.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")

        name = data.get("name")
        if not name:
            continue
        return {
            "name": _clean_text(name),
            "price": _coerce_price(price),
            "brand": _clean_text(brand),
            "sku": data.get("sku") or data.get("itemId"),
        }
    return None


def _is_url_not_found(html) -> bool:
    """Content-level 404 detection: <title> literally says 'Page Not Found'."""
    m = _TITLE_TAG_RE.search(html or "")
    if not m:
        return False
    return bool(_PAGE_NOT_FOUND_RE.search(m.group(1) or ""))


def _body_diagnostic(html) -> str:
    """Classify a response body's size for evidence diagnostics.

    'empty'  — zero bytes returned (HTTP 200 with no content: the unlocker
               delivered nothing, as seen live for 98501/1493188 in run
               20260906T015531Z);
    'short'  — unusually short (< SHORT_BODY_CHARS): possible anti-bot /
               challenge / consent interstitial, not a real product page;
    'normal' — long enough to be a plausible real page.
    """
    n = len(html or "")
    if n == 0:
        return "empty"
    if n < SHORT_BODY_CHARS:
        return "short"
    return "normal"


def _extract_count_pack(text) -> Optional[str]:
    """Hyphen-tolerant pack: '200-count', '200 count', '400 Tablets' -> '200 count'."""
    if not text:
        return None
    m = _COUNT_PACK_RE.search(str(text))
    if not m:
        return None
    number = m.group(1).replace(",", "")
    unit = m.group(2).lower().rstrip(".")
    return f"{number} {unit}"


def _normalize_pack(text) -> str:
    """Pack comparison key: strip everything non-alphanumeric (lowercased)."""
    return re.sub(r"[^0-9a-z]", "", (text or "").lower())


def _norm_tokens(text):
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    stopwords = {"and", "the", "of", "for", "with", "de", "la", "&"}
    return {t for t in tokens if t not in stopwords and len(t) > 2}


def _jaccard_overlap(a, b) -> float:
    a, b = set(a), set(b)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _identity_status(exact_title, quantity_or_pack, expected) -> str:
    """probable_match when brand + (pack or title overlap) hit the expectation."""
    if not expected or not exact_title:
        return "unverified"
    exp_title = expected.get("requested_title", "") or ""
    exp_pack = expected.get("requested_pack", "") or ""
    exp_brand = expected.get("requested_brand", "") or ""
    brand_hit = bool(_KS_BRAND_RE.search(exact_title)) and "Kirkland" in exp_brand
    pack_hit = bool(quantity_or_pack and exp_pack) and _normalize_pack(
        quantity_or_pack
    ) == _normalize_pack(exp_pack)
    overlap = _jaccard_overlap(_norm_tokens(exact_title), _norm_tokens(exp_title))
    if brand_hit and (pack_hit or overlap >= 0.5):
        return "probable_match"
    return "unverified"


def _missing_fields(item: Dict) -> List[str]:
    return [f for f in _CONTRACT_FIELDS if item.get(f) is None]


def parse_costco_item_page(html, item_id, expected=None) -> Dict:
    """Parse one Costco product page into a normalized item record (null-first).

    Content-level 404 pages return a typed url_not_found record with every
    field None — never fabricated.
    """
    requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    url = _build_costco_url(item_id)
    item_id = str(item_id).strip()

    if _is_url_not_found(html):
        rec = {
            "requested_item_id": item_id,
            "returned_costco_item_id": None,
            "exact_title": None,
            "brand": None,
            "listed_price": None,
            "currency": None,
            "unit_price": None,
            "quantity_or_pack": None,
            "size_or_weight": None,
            "UPC_GTIN_EAN": None,
            "availability": None,
            "product_url": url,
            "captured_at": requested_at,
            "identity_match_status": "url_not_found",
            "missing_fields": [],
        }
        rec["missing_fields"] = _missing_fields(rec)
        return rec

    ld = _parse_jsonld_product(html)
    tag_m = _TITLE_TAG_RE.search(html or "")
    title_tag = _clean_text(tag_m.group(1)) if tag_m else None

    if not ld and not title_tag:
        rec = {
            "requested_item_id": item_id,
            "returned_costco_item_id": None,
            "exact_title": None,
            "brand": None,
            "listed_price": None,
            "currency": None,
            "unit_price": None,
            "quantity_or_pack": None,
            "size_or_weight": None,
            "UPC_GTIN_EAN": None,
            "availability": None,
            "product_url": url,
            "captured_at": requested_at,
            "identity_match_status": "no_data_found",
            "missing_fields": [],
        }
        rec["missing_fields"] = _missing_fields(rec)
        return rec

    exact_title = None
    brand = None
    price = None
    if ld:
        exact_title = ld.get("name") or title_tag
        brand = ld.get("brand")
        price = ld.get("price")
    if exact_title is None:
        exact_title = title_tag
    if brand is None and _KS_BRAND_RE.search(exact_title or ""):
        brand = "Kirkland Signature"

    pack = _extract_count_pack(exact_title)
    returned_id = item_id if item_id in (html or "") else None

    rec = {
        "requested_item_id": item_id,
        "returned_costco_item_id": returned_id,
        "exact_title": exact_title,
        "brand": brand,
        "listed_price": price,
        "currency": "USD" if price is not None else None,
        "unit_price": None,
        "quantity_or_pack": pack,
        "size_or_weight": None,
        "UPC_GTIN_EAN": None,
        "availability": None,
        "product_url": url,
        "captured_at": requested_at,
        "identity_match_status": _identity_status(exact_title, pack, expected),
        "missing_fields": [],
    }
    rec["missing_fields"] = _missing_fields(rec)
    return rec


def _load_expected(manifest_path) -> Dict[str, Dict]:
    """Expected identities from a manifest-style JSON (BOM-tolerant)."""
    with open(manifest_path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    out = {}
    for item in data.get("items", []):
        iid = str(item.get("item_id", "")).strip()
        if iid:
            out[iid] = item
    return out


def _classify_hard_failure(last_error, raise_exc) -> str:
    """Map a no-HTML outcome to the Batch 08 hard-failure vocabulary."""
    if raise_exc is not None and "value_error" in str(raise_exc.__class__.__name__).lower():
        return "config_error"
    if last_error and last_error.startswith("auth_error"):
        return "auth_error"
    if last_error and last_error.startswith("http_error"):
        return "http_error"
    if last_error and last_error.startswith("transport_error"):
        return "transport_error"
    if raise_exc is not None:
        return "config_error"
    return "transport_error"


def _persist_evidence(run_dir, ts, item_id, raw_record, norm_record):
    raw_dir = os.path.join(run_dir, "raw")
    norm_dir = os.path.join(run_dir, "normalized")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(norm_dir, exist_ok=True)
    raw_path = os.path.join(raw_dir, f"brightdata_{item_id}_{ts}.json")
    norm_path = os.path.join(norm_dir, f"items_{item_id}_brightdata_{ts}.json")
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
    """Fetch Costco item-detail pages via the Bright Data Web Unlocker.

    Gated (BRIGHTDATA_COSTCO_DETAIL_ENABLED=1). One request per item, zero
    retries, sequential pacing. HARD failures halt the batch; soft per-item
    failures (url_not_found / no_data_found) are recorded and the batch
    continues. Evidence (raw + normalized, scrubbed) is persisted under
    run_dir (default: the frozen 20260828T021658Z discovery run directory).
    """
    if not _gate_enabled():
        msg = (
            f"[BrightDataCostco] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        print(msg)
        return {
            "status": "blocked",
            "reason": f"{GATE_ENV} not enabled",
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
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
    expected_map = _load_expected(manifest_path) if manifest_path else {}

    items: List[Dict] = []
    failures: List[Dict] = []
    evidence_paths: List[str] = []
    halted = False
    total = len(item_ids or [])

    for idx, item_id in enumerate(item_ids or []):
        if idx > 0:
            time.sleep(delay)

        item_id = str(item_id).strip()
        url = _build_costco_url(item_id)
        requested_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        html = None
        raise_exc = None
        try:
            html = bright_data_client._fetch(url)
        except ValueError as exc:
            raise_exc = exc
        except Exception as exc:  # noqa: BLE001 - adapter persists then reports
            raise_exc = exc

        http_status = bright_data_client.LAST_HTTP_STATUS
        last_error = bright_data_client.LAST_ERROR

        if html is None:
            failure_type = _classify_hard_failure(last_error, raise_exc)
            fail_rec = {
                "run_id": RUN_ID,
                "attempt": f"brightdata_costco_{item_id}",
                "requested_at": requested_at,
                "provider": "BRIGHTDATA_WEB_UNLOCKER",
                "platform": "web_unlocker_costco_page",
                "endpoint": "https://api.brightdata.com/request",
                "url": url,
                "http_status": http_status if http_status is not None else 0,
                "failure_type": failure_type,
                "last_error": last_error or (str(raise_exc) if raise_exc else None),
                "response_headers": bright_data_client._scrub_response_headers(
                    bright_data_client.LAST_RESPONSE_HEADERS
                ),
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

        item = parse_costco_item_page(html, item_id, expected_map.get(item_id))
        items.append(item)

        raw_record = {
            "run_id": RUN_ID,
            "attempt": f"brightdata_costco_{item_id}",
            "requested_at": requested_at,
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "platform": "web_unlocker_costco_page",
            "endpoint": "https://api.brightdata.com/request",
            "payload": {
                "zone": bright_data_client.BRIGHTDATA_UNLOCKER_ZONE,
                "url": url,
                "format": "raw",
            },
            "auth_header": "Bearer <redacted>",
            "http_status": http_status,
            "failure_type": None,
            "last_error": last_error,
            "retries": 0,
            "scrubbed": True,
            "response_headers": bright_data_client._scrub_response_headers(
                bright_data_client.LAST_RESPONSE_HEADERS
            ),
            "response_body_bytes": len((html or "").encode("utf-8")),
            "response_body_diagnostic": _body_diagnostic(html),
            "response_html_head_capped": (html or "")[:HEAD_CAP_CHARS],
        }
        norm_record = {
            "run_id": RUN_ID,
            "attempt": f"brightdata_costco_{item_id}",
            "requested_at": requested_at,
            "provider": "BRIGHTDATA_WEB_UNLOCKER",
            "platform": "web_unlocker_costco_page",
            "endpoint": "https://api.brightdata.com/request",
            "url": url,
            "http_status": http_status,
            "failure_type": None,
            "retries": 0,
            "stop_on_block": "sequential_batch",
            "scrubbed": True,
            "item": item,
        }
        raw_path, norm_path = _persist_evidence(run_dir, ts, item_id, raw_record, norm_record)
        evidence_paths.extend([raw_path, norm_path])

        status_marker = item["identity_match_status"]
        print(
            f"[{idx + 1}/{total}] item {item_id} {status_marker} "
            f"http={http_status} title={item.get('exact_title')} "
            f"price={item.get('listed_price')} body={_body_diagnostic(html)}"
        )

    return {
        "status": "halted" if halted else "completed",
        "provider": "BRIGHTDATA_WEB_UNLOCKER",
        "run_id": RUN_ID,
        "attempt": f"brightdata_costco_run_{ts}",
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
def _cli(argv=None):
    parser = argparse.ArgumentParser(
        prog="bright_data_costco.py",
        description="Bright Data Web Unlocker Costco item-detail adapter (gated).",
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
            f"[BrightDataCostco] BLOCKED: {GATE_ENV} != '1'. "
            f"Set {GATE_ENV}=1 to enable live calls."
        )
        return 2

    summary = refresh_product_details(
        item_ids=args.item_ids,
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