"""Offline manual import for the Product Scout candidate cache.

Populates data/scanner-search-cache.json (the existing candidate cache
used by GET /api/kirkland/scanner in cache-only mode) from a local JSON
or CSV file. The import NEVER makes a network request: no Scavio, Bright
Data, Easyparser, Chocodata, Unwrangle, Amazon, Costco API, or any other
provider call, and no credits are ever consumed.

The imported cache is then analyzed by the existing cache-only scanner
(SCANNER_OFFER_ENRICHMENT=OFF) against the local Kirkland/Costco catalog
with the existing exact / high-confidence / candidate / mismatch
matching, Costco cost lookup, and fee-engine economics — zero outbound
calls.

Safety contract
---------------
- Validation happens before any write; a malformed or fully-invalid
  import never touches an existing cache.
- Zero valid candidates or a failed atomic write preserves any existing
  valid cache (the write is verified by re-reading the cache afterwards;
  a swallowed write error is reported as a failure).
- Default behavior refuses to overwrite an existing valid cache;
  ``--replace`` is required to replace it. A corrupt/missing cache may
  be replaced without the flag.
- ``--dry-run`` validates and reports only; it never writes.
- Dedupe by ASIN is deterministic: the newest valid ``observed_at`` wins;
  ties or missing ``observed_at`` use the last valid input row.
- Unknown values stay null/Unknown — never 0, never fabricated.
- Imported values are labeled with the import source and are never
  presented as live, verified, or provider-fetched.

CLI
---
    python manual_import.py --input path/to/file.json
    python manual_import.py --input path/to/file.csv
    python manual_import.py --input path --dry-run
    python manual_import.py --input path --replace
    python manual_import.py --input path --source my_label
    python manual_import.py --input path --report out.json

Exit codes: 0 success; 2 zero valid candidates; 3 existing valid cache
without --replace; 4 cache write failed or verification failed.

Memory behavior: JSON files are decoded with a streaming decoder that
yields one candidate at a time (the full parse tree is never built);
CSV uses a streaming csv.DictReader. Only the validated candidate list
itself (a few hundred small dicts) is held, plus any nested offers the
user supplied.
"""

import argparse
import csv
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import amazon_search
import costco_client
import product_analysis

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
FULFILLMENT_VALUES = ("FBA", "FBM", "Amazon")
BOOLEAN_WORDS = {
    "true": True, "false": False, "1": True, "0": False,
    "yes": True, "no": False,
}
DEFAULT_SOURCE = "manual_import"

# Candidate fields preserved through the import. Everything else in the
# input is ignored (unknown columns/keys are forward-compatible noise).
JSON_ALIASES = {
    "title": "name",
    "name": "name",
    "amazon_url": "product_url",
    "product_url": "product_url",
    "estimated_monthly_sales": "monthly_sales_estimate",
    "monthly_sales": "monthly_sales_estimate",
    "fba_seller_count": "fba_sellers",
    "fbm_seller_count": "fbm_sellers",
}

_NUMERIC_FIELDS = (
    "amazon_price",
    "amazon_shipping",
    "buy_box_price",
    "buy_box_shipping",
    "monthly_sales_estimate",
    "referral_fee",
    "fba_fee",
    "weight_lbs",
    "seller_rating",
)

_INT_FIELDS = (
    "total_sellers",
    "fba_sellers",
    "fbm_sellers",
    "pack_count",
    "unit_count",
    "browse_node_id",
    "rating_count",
)

_BOOL_FIELDS = ("monthly_sales_estimated",)

_TEXT_FIELDS = (
    "buy_box_seller_name",
    "buy_box_fulfillment",
    "upc",
    "gtin",
    "ean",
    "product_form",
    "variant",
    "flavor",
    "scent",
    "weight",
    "volume",
    "amazon_category",
    "category_source_hint",
)

_OFFER_NUMERIC_FIELDS = ("item_price", "shipping_price", "landed_price", "seller_rating")
_OFFER_INT_FIELDS = ("rating_count",)
_OFFER_BOOL_FIELDS = ("is_buy_box_winner", "is_prime")
_OFFER_TEXT_FIELDS = (
    "seller_name",
    "seller_id",
    "condition",
    "fulfillment",
    "source",
    "observed_at",
)


# ---------------------------------------------------------------------------
# Streaming JSON
# ---------------------------------------------------------------------------

def _skip_ws(text: str, idx: int) -> int:
    while idx < len(text) and text[idx] in " \t\r\n":
        idx += 1
    return idx


def _iter_json_candidates(path: str):
    """Stream candidate objects from a JSON file.

    Accepts a top-level array or an object carrying a ``candidates``
    array. Each candidate is decoded one at a time and released before
    the next is read, so the full parse tree is never materialized
    (memory-safe for 500+ candidates with thousands of nested offers).
    Raises ValueError on malformed structure.
    """
    with open(path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    decoder = json.JSONDecoder()
    idx = _skip_ws(text, 0)
    if idx >= len(text):
        raise ValueError("empty JSON document")

    if text[idx] == "[":
        idx += 1
        while True:
            idx = _skip_ws(text, idx)
            if idx >= len(text):
                raise ValueError("unterminated top-level array")
            if text[idx] == "]":
                return
            item, idx = decoder.raw_decode(text, idx)
            yield item
            idx = _skip_ws(text, idx)
            if idx < len(text) and text[idx] == ",":
                idx += 1
            elif idx >= len(text) or text[idx] != "]":
                raise ValueError("malformed top-level array")

    if text[idx] == "{":
        idx += 1
        seen_candidates = False
        while True:
            idx = _skip_ws(text, idx)
            if idx >= len(text):
                raise ValueError("unterminated top-level object")
            if text[idx] == "}":
                break
            if text[idx] == ",":
                idx += 1
                idx = _skip_ws(text, idx)
            key, idx = decoder.raw_decode(text, idx)
            if not isinstance(key, str):
                raise ValueError("object keys must be strings")
            idx = _skip_ws(text, idx)
            if idx >= len(text) or text[idx] != ":":
                raise ValueError("malformed top-level object")
            idx += 1
            idx = _skip_ws(text, idx)
            if key == "candidates":
                if seen_candidates:
                    raise ValueError("duplicate 'candidates' key")
                seen_candidates = True
                if idx >= len(text) or text[idx] != "[":
                    raise ValueError("'candidates' must be an array")
                idx += 1
                while True:
                    idx = _skip_ws(text, idx)
                    if idx >= len(text):
                        raise ValueError("unterminated 'candidates' array")
                    if text[idx] == "]":
                        idx += 1
                        break
                    item, idx = decoder.raw_decode(text, idx)
                    yield item
                    idx = _skip_ws(text, idx)
                    if idx < len(text) and text[idx] == ",":
                        idx += 1
                    elif idx >= len(text) or text[idx] != "]":
                        raise ValueError("malformed 'candidates' array")
            else:
                _, idx = decoder.raw_decode(text, idx)
        if not seen_candidates:
            raise ValueError("top-level object has no 'candidates' array")
        return

    raise ValueError(
        "top-level JSON must be an array or an object with a 'candidates' array"
    )


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _iso_datetime(value) -> Optional[datetime]:
    """Valid ISO-8601 timestamp normalized to UTC, or None when invalid."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _number(value, field: str) -> Optional[float]:
    """Strict finite non-negative number. None when invalid.

    JSON numbers must be int/float (bool is rejected); CSV cells arrive
    as strings and are parsed. Never coerces invalid text.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            num = float(text)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(num) or num < 0:
        return None
    return num


def _integer(value, field: str) -> Optional[int]:
    """Strict non-negative integer. None when invalid."""
    num = _number(value, field)
    if num is None or not num.is_integer():
        return None
    return int(num)


def _boolean(value, field: str) -> Optional[bool]:
    """Strict boolean. JSON must be true/false; CSV accepts
    true/false/1/0/yes/no (case-insensitive). None when invalid."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return BOOLEAN_WORDS.get(value.strip().lower())
    return None


def _fulfillment(value) -> Optional[str]:
    """Normalized fulfillment: FBA | FBM | Amazon | None (unknown)."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() == "unknown":
            return None
        if text in FULFILLMENT_VALUES:
            return text
        if text.upper() in FULFILLMENT_VALUES:
            return text.upper()
    return "INVALID"


def _iso_string(value) -> Tuple[Optional[str], Optional[datetime]]:
    dt = _iso_datetime(value)
    if value is not None and dt is None:
        return None, None  # supplied but invalid
    return (dt.isoformat() if dt else None), dt


# ---------------------------------------------------------------------------
# Candidate normalization
# ---------------------------------------------------------------------------

def _normalize_candidate(
    raw: Any, default_source: str, imported_at: str
) -> Tuple[Optional[Dict], Optional[datetime], Optional[str]]:
    """Validate one input row into a cache candidate dict.

    Returns (candidate, observed_dt, reason). reason is None on success.
    On failure the candidate is None and reason explains the rejection.
    """
    if not isinstance(raw, dict):
        return None, None, "row is not an object"

    asin = raw.get("asin")
    if not isinstance(asin, str) or not ASIN_PATTERN.fullmatch(asin.strip()):
        return None, None, "invalid ASIN (expected 10 alphanumeric characters)"
    asin = asin.strip().upper()

    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        title = raw.get("name")
    if not isinstance(title, str) or not title.strip():
        return None, None, "missing title/name"

    candidate: Dict[str, Any] = {
        "asin": asin,
        "name": title.strip(),
        "product_url": None,
        "amazon_price": None,
        "amazon_shipping": None,
        "buy_box_price": None,
        "buy_box_shipping": None,
        "monthly_sales_estimate": None,
        "monthly_sales_estimated": False,
        "total_sellers": None,
        "fba_sellers": None,
        "fbm_sellers": None,
        "buy_box_seller_name": None,
        "buy_box_fulfillment": None,
        "referral_fee": None,
        "fba_fee": None,
        "weight_lbs": None,
        "upc": None,
        "gtin": None,
        "ean": None,
        "pack_count": None,
        "unit_count": None,
        "weight": None,
        "volume": None,
        "product_form": None,
        "variant": None,
        "flavor": None,
        "scent": None,
        "amazon_category": None,
        "browse_node_id": None,
        "category_source_hint": None,
        "source": default_source,
        "imported_at": imported_at,
        "observed_at": None,
        "live_observed": False,
        "offers": [],
    }

    flag_supplied = False
    observed_at: Optional[datetime] = None

    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        target = JSON_ALIASES.get(key, key)
        if key == "asin" or key == "title" or key == "name":
            continue
        if target in _NUMERIC_FIELDS:
            parsed = _number(value, key)
            if value is not None and parsed is None:
                return None, None, "%s: invalid non-negative number %r" % (key, value)
            candidate[target] = parsed
        elif target in _INT_FIELDS:
            parsed = _integer(value, key)
            if value is not None and parsed is None:
                return None, None, "%s: invalid non-negative integer %r" % (key, value)
            candidate[target] = parsed
        elif target in _BOOL_FIELDS:
            parsed = _boolean(value, key)
            if parsed is None:
                return None, None, "%s: invalid boolean %r" % (key, value)
            candidate[target] = parsed
            flag_supplied = True
        elif target == "buy_box_fulfillment":
            parsed = _fulfillment(value)
            if parsed == "INVALID":
                return None, None, (
                    "buy_box_fulfillment: must be FBA, FBM, Amazon, or unknown"
                )
            candidate[target] = parsed
        elif target == "observed_at":
            iso, dt = _iso_string(value)
            if value is not None and iso is None:
                return None, None, "observed_at: invalid ISO-8601 timestamp %r" % (value,)
            candidate[target] = iso
            observed_at = dt
            if dt is not None:
                candidate["live_observed"] = True
        elif target == "source":
            if isinstance(value, str) and value.strip():
                candidate[target] = value.strip()
            elif value is not None:
                return None, None, "source: must be a non-empty string"
        elif target == "product_url":
            if isinstance(value, str) and value.strip():
                candidate[target] = value.strip()
            elif value is not None:
                return None, None, "product_url: must be a string"
        elif target in _TEXT_FIELDS:
            if isinstance(value, str) and value.strip():
                candidate[target] = value.strip()
            elif value is not None:
                return None, None, "%s: must be a string" % key
        elif target == "offers":
            if not isinstance(value, list):
                return None, None, "offers: must be an array"
            candidate["offers"] = value
        else:
            # Unknown keys are ignored (forward-compatible).
            continue

    # A supplied monthly sales value without an explicit flag is an
    # estimate by definition (manual import is never live-verified).
    if candidate["monthly_sales_estimate"] is not None and not flag_supplied:
        candidate["monthly_sales_estimated"] = True

    return candidate, observed_at, None


# ---------------------------------------------------------------------------
# Offer normalization
# ---------------------------------------------------------------------------

def _normalize_offer(raw: Any, default_source: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Validate one nested seller offer. Returns (offer, reason)."""
    if not isinstance(raw, dict):
        return None, "offer is not an object"

    offer: Dict[str, Any] = {
        "seller_name": None,
        "seller_id": None,
        "fulfillment": None,
        "item_price": None,
        "shipping_price": None,
        "landed_price": None,
        "condition": None,
        "is_buy_box_winner": None,
        "is_prime": None,
        "seller_rating": None,
        "rating_count": None,
        "observed_at": None,
        "source": default_source,
    }

    for key, value in raw.items():
        if not isinstance(key, str):
            continue
        if key == "name" and "seller_name" not in raw:
            key = "seller_name"
        if key in _OFFER_NUMERIC_FIELDS:
            parsed = _number(value, key)
            if value is not None and parsed is None:
                return None, "offer %s: invalid non-negative number %r" % (key, value)
            offer[key] = parsed
        elif key in _OFFER_INT_FIELDS:
            parsed = _integer(value, key)
            if value is not None and parsed is None:
                return None, "offer %s: invalid non-negative integer %r" % (key, value)
            offer[key] = parsed
        elif key in _OFFER_BOOL_FIELDS:
            parsed = _boolean(value, key)
            if parsed is None:
                return None, "offer %s: invalid boolean %r" % (key, value)
            offer[key] = parsed
        elif key == "fulfillment":
            parsed = _fulfillment(value)
            if parsed == "INVALID":
                return None, "offer fulfillment: must be FBA, FBM, Amazon, or unknown"
            offer[key] = parsed
        elif key == "observed_at":
            iso, _ = _iso_string(value)
            if value is not None and iso is None:
                return None, "offer observed_at: invalid ISO-8601 timestamp %r" % (value,)
            offer[key] = iso
        elif key == "source":
            if isinstance(value, str) and value.strip():
                offer[key] = value.strip()
            elif value is not None:
                return None, "offer source: must be a non-empty string"
        elif key in _OFFER_TEXT_FIELDS:
            if isinstance(value, str) and value.strip():
                offer[key] = value.strip()
            elif value is not None:
                return None, "offer %s: must be a string" % key
        else:
            continue
    return offer, None


def _normalize_offers(offers: Any, default_source: str) -> Tuple[List[Dict], List[Dict]]:
    accepted = []
    rejected = []
    for raw in offers or []:
        offer, reason = _normalize_offer(raw, default_source)
        if offer is None:
            rejected.append({"reason": reason})
        else:
            accepted.append(offer)
    return accepted, rejected


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def _iter_csv_rows(path: str):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            return
        for row in reader:
            yield row


def _csv_row_to_raw(row: Dict[str, str]) -> Dict[str, Any]:
    """CSV cells are strings; empty cells become absent (None) values so
    the shared validator treats them as unknown, never as invalid text."""
    return {key: (value.strip() if isinstance(value, str) and value.strip() else None)
            for key, value in row.items()}


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------

def _dedupe_candidates(validated: List[Tuple[Dict, Optional[datetime]]]):
    """Deterministic ASIN dedupe: newest valid observed_at wins; ties or
    missing observed_at keep the LAST valid input row."""
    best: Dict[str, Tuple[Dict, Optional[datetime]]] = {}
    order: List[str] = []
    for candidate, observed_dt in validated:
        asin = candidate["asin"]
        if asin not in best:
            best[asin] = (candidate, observed_dt)
            order.append(asin)
            continue
        _, current_dt = best[asin]
        if observed_dt is None:
            if current_dt is None:
                best[asin] = (candidate, None)  # both missing: last wins
        elif current_dt is None or observed_dt >= current_dt:
            best[asin] = (candidate, observed_dt)  # newest (or tie): last wins
    return [best[asin][0] for asin in order], len(validated) - len(order)


# ---------------------------------------------------------------------------
# Costco match-ready check (read-only, zero network)
# ---------------------------------------------------------------------------

def _costco_match_quality(name: str) -> Optional[str]:
    """Local Costco resolution for the match-ready report count.

    Never creates files and never calls the network: when the local
    catalog is not ready the count is simply 0. Uses the same resolver
    the scanner uses (product_analysis.get_costco_price).
    """
    if costco_client.catalog_state() != "ready":
        return None
    row = product_analysis.get_costco_price(name) or {}
    return row.get("match_quality")


MATCH_READY_QUALITIES = ("exact", "invoice_confirmed", "high_confidence")


# ---------------------------------------------------------------------------
# Cache write (atomic, verified)
# ---------------------------------------------------------------------------

def _write_cache(products: List[Dict], source_label: str) -> Tuple[bool, Optional[str]]:
    """Atomically write the candidate cache and VERIFY the result.

    amazon_search.save_cached_candidates() writes via tmp file +
    os.replace and swallows write errors, so a successful return does not
    prove the write landed. We therefore re-read the cache afterwards and
    confirm the expected record count and source before reporting success.
    """
    amazon_search.save_cached_candidates(
        products, search_terms=["manual_import"], source=source_label
    )
    data = amazon_search._read_cache_file()
    if data is None or data is False:
        return False, "cache unreadable after write (existing cache preserved)"
    if data.get("candidate_count") != len(products):
        return False, (
            "cache write verification failed: expected %d products, found %r "
            "(existing cache preserved)" % (len(products), data.get("candidate_count"))
        )
    if (data.get("source") or "").lower() != source_label.lower():
        return False, (
            "cache write verification failed: expected source %r, found %r "
            "(existing cache preserved)" % (source_label.lower(), data.get("source"))
        )
    return True, None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _import_rows(path: str):
    """Yield (row, source_format) pairs. Raises ValueError on malformed
    JSON structure or unreadable files."""
    if path.lower().endswith(".csv"):
        for row in _iter_csv_rows(path):
            yield _csv_row_to_raw(row)
        return
    for item in _iter_json_candidates(path):
        yield item


def run_import(
    input_path: str,
    source_label: str = DEFAULT_SOURCE,
    dry_run: bool = False,
    replace: bool = False,
) -> Dict[str, Any]:
    """Full import pipeline. Returns the report dict; never raises on
    validation outcomes (file-level errors propagate as ValueError)."""
    imported_at = datetime.now(timezone.utc).isoformat()

    validated: List[Tuple[Dict, Optional[datetime]]] = []
    rejected_rows = []
    rejected_offers_total = 0
    accepted_offers_total = 0
    input_rows = 0

    for raw in _import_rows(input_path):
        input_rows += 1
        candidate, observed_dt, reason = _normalize_candidate(
            raw, source_label, imported_at
        )
        if candidate is None:
            asin_raw = raw.get("asin") if isinstance(raw, dict) else None
            rejected_rows.append({
                "row": input_rows,
                "asin": asin_raw,
                "reason": reason,
            })
            continue
        offers, rejected_offers = _normalize_offers(
            candidate.get("offers"), candidate.get("source") or source_label
        )
        rejected_offers_total += len(rejected_offers)
        accepted_offers_total += len(offers)
        candidate["offers"] = offers
        validated.append((candidate, observed_dt))

    kept, duplicated = _dedupe_candidates(validated)
    accepted = len(kept)

    missing_market_data = sum(
        1
        for c in kept
        if c.get("amazon_price") is None and c.get("buy_box_price") is None
    )
    match_ready = sum(
        1
        for c in kept
        if (
            (c.get("amazon_price") is not None or c.get("buy_box_price") is not None)
            and (_costco_match_quality(c["name"]) in MATCH_READY_QUALITIES)
        )
    )

    report: Dict[str, Any] = {
        "status": None,
        "input": input_path,
        "dry_run": bool(dry_run),
        "replaced": False,
        "source": source_label,
        "fetched_at": imported_at,
        "cache_path": amazon_search._cache_path(),
        "counts": {
            "input_rows": input_rows,
            "accepted": accepted,
            "rejected": len(rejected_rows),
            "duplicated": duplicated,
            "offers_accepted": accepted_offers_total,
            "offers_rejected": rejected_offers_total,
            "missing_market_data": missing_market_data,
            "match_ready": match_ready,
        },
        "rejected_rows": rejected_rows,
        "notes": [],
    }

    if accepted == 0:
        report["status"] = "no_valid_candidates"
        report["notes"].append(
            "Zero valid candidates; the cache was not written."
        )
        return report

    if dry_run:
        report["status"] = "dry_run"
        report["notes"].append(
            "Dry run: validation only, cache was not written."
        )
        return report

    existing = amazon_search._read_cache_file()
    if existing is not None and existing is not False and not replace:
        report["status"] = "cache_exists_requires_replace"
        report["notes"].append(
            "An existing valid cache is present; pass --replace to "
            "overwrite it. The existing cache was preserved."
        )
        return report

    ok, error = _write_cache(kept, source_label)
    if not ok:
        report["status"] = "write_failed"
        report["notes"].append(error or "cache write failed")
        return report

    report["status"] = "ok"
    report["replaced"] = existing is not None
    report["notes"].append(
        "Cache written atomically to %s (%d products, source %r)." % (
            report["cache_path"], accepted, source_label
        )
    )
    return report


def _print_report(report: Dict[str, Any]) -> None:
    counts = report["counts"]
    print("status:              %s" % report["status"])
    print("input:               %s" % report["input"])
    print("source:              %s" % report["source"])
    print("fetched_at:          %s" % report["fetched_at"])
    print("cache_path:          %s" % report["cache_path"])
    print("input_rows:          %d" % counts["input_rows"])
    print("accepted:            %d" % counts["accepted"])
    print("rejected:            %d" % counts["rejected"])
    print("duplicated:          %d" % counts["duplicated"])
    print("offers_accepted:     %d" % counts["offers_accepted"])
    print("offers_rejected:     %d" % counts["offers_rejected"])
    print("missing_market_data: %d" % counts["missing_market_data"])
    print("match_ready:         %d" % counts["match_ready"])
    for note in report.get("notes") or []:
        print("note:                %s" % note)
    for entry in report.get("rejected_rows") or []:
        print(
            "rejected row %s: %s" % (
                entry.get("row"), entry.get("reason")
            )
        )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline manual import for the Product Scout candidate "
        "cache (zero network calls).",
    )
    parser.add_argument("--input", required=True, help="JSON or CSV import file")
    parser.add_argument(
        "--source",
        default=None,
        help="source label for this import (default: manual_import)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="validate and report only; never write"
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="allow overwriting an existing valid cache",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="also write a machine-readable report JSON to this path",
    )
    args = parser.parse_args(argv)

    source_label = (args.source or DEFAULT_SOURCE).strip() or DEFAULT_SOURCE

    try:
        report = run_import(
            args.input,
            source_label=source_label,
            dry_run=args.dry_run,
            replace=args.replace,
        )
    except (ValueError, OSError) as e:
        print("error: %s" % e)
        return 2

    _print_report(report)

    if args.report:
        try:
            with open(args.report, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except OSError as e:
            print("error: could not write report file: %s" % e)
            return 4

    if report["status"] == "ok":
        return 0
    if report["status"] == "dry_run":
        return 0
    if report["status"] == "cache_exists_requires_replace":
        return 3
    if report["status"] == "write_failed":
        return 4
    return 2  # no_valid_candidates


if __name__ == "__main__":
    sys.exit(main())