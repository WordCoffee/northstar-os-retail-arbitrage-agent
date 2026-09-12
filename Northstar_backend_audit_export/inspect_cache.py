"""Read-only cache inspector for data/scanner-search-cache.json.

Prints the cache file's integrity and provenance without ever writing:
path, existence, size in bytes, schema_version, provider source,
fetched_at, candidate_count, per-field product coverage (how many of the
234 candidates carry each expected field), freshness vs. today, and the
SHA-256 checksum (so a cache file can be proven unchanged between runs).

Optional --path overrides the cache (env SCANNER_SEARCH_CACHE_PATH is
honored, same as the scanner). Exit codes: 0 inspected, 2 unreadable.

Never modifies the cache, never writes any file, never touches the
network.
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import amazon_search

PRODUCT_FIELDS = (
    "asin",
    "name",
    "amazon_price",
    "product_url",
    "brand",
    "sales_volume",
    "monthly_sales_estimate",
    "monthly_sales_estimated",
    "rating",
    "reviews_count",
    "upc",
    "ean",
    "weight",
    "weight_lbs",
    "fba_fee",
    "total_sellers",
    "fba_sellers",
    "observed_at",
    "enriched_at",
)


def _sha256(path: str) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _field_coverage(products: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(products)
    counts: Dict[str, int] = {}
    for field in PRODUCT_FIELDS:
        counts[field] = sum(1 for p in products if p.get(field) is not None)
    return {
        "total_products": total,
        "fields_present": {field: counts[field] for field in PRODUCT_FIELDS},
        "fields_missing_everywhere": [
            field for field in PRODUCT_FIELDS if counts[field] == 0
        ],
    }


def inspect_cache(path: Optional[str] = None) -> Dict[str, Any]:
    """Inspect the scanner search cache read-only. Never raises for a
    missing/corrupt file: states are reported, not crashed."""
    cache_path = path or amazon_search._cache_path()
    result: Dict[str, Any] = {
        "path": cache_path,
        "exists": False,
    }
    if not os.path.exists(cache_path):
        return result

    size = os.path.getsize(cache_path)
    result["exists"] = True
    result["size_bytes"] = size
    result["sha256"] = _sha256(cache_path)

    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        result["parseable"] = False
        return result

    if not isinstance(data, dict) or not isinstance(data.get("products"), list):
        result["parseable"] = False
        return result

    result["parseable"] = True
    result["schema_version"] = data.get("schema_version")
    result["source"] = data.get("source")
    result["fetched_at"] = data.get("fetched_at")
    result["candidate_count"] = data.get("candidate_count")
    result["observed_count"] = len(data["products"])

    age = None
    if isinstance(result["fetched_at"], str):
        try:
            fetched = datetime.fromisoformat(result["fetched_at"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - fetched).total_seconds() / 86400.0
        except ValueError:
            age = None
    if age is None:
        result["freshness_label"] = "Unknown timestamp"
        result["age_days"] = None
    elif age < 7:
        result["freshness_label"] = "Fresh (<7 days)"
        result["age_days"] = round(age, 2)
    elif age < 30:
        result["freshness_label"] = "Aging (8-30 days)"
        result["age_days"] = round(age, 2)
    else:
        result["freshness_label"] = "Stale (>30 days)"
        result["age_days"] = round(age, 2)

    result["coverage"] = _field_coverage(data["products"])
    return result


def _print_report(report: Dict[str, Any]) -> None:
    print("cache path: %s" % report["path"])
    if not report["exists"]:
        print("status: missing (no cache file; run a scan or a manual import first)")
        return
    print("status: ok")
    print("size bytes: %s" % report.get("size_bytes"))
    print("sha256: %s" % (report.get("sha256") or "unavailable"))
    if not report.get("parseable"):
        print("parseable: no (corrupt/unparseable JSON)")
        return
    print("schema_version: %s" % (report.get("schema_version") or "unknown"))
    print("source: %s" % (report.get("source") or "unknown"))
    print("fetched_at: %s" % (report.get("fetched_at") or "unknown"))
    print("freshness: %s (age %s days)" % (
        report.get("freshness_label"), report.get("age_days") if report.get("age_days") is not None else "?"))
    print("candidate_count (declared): %s" % report.get("candidate_count"))
    print("candidate_count (observed): %s" % report.get("observed_count"))
    coverage = report.get("coverage") or {}
    print("field coverage (%d products):" % coverage.get("total_products", 0))
    for field, count in (coverage.get("fields_present") or {}).items():
        print("  %-24s %d/%d" % (field, count, coverage.get("total_products", 0)))
    if coverage.get("fields_missing_everywhere"):
        print("fields absent on every product: %s" % ", ".join(coverage["fields_missing_everywhere"]))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only cache inspector (never writes, never calls the network).",
    )
    parser.add_argument("--path", default=None, help="cache path to inspect (default: scanner cache path)")
    args = parser.parse_args(argv)

    try:
        report = inspect_cache(args.path)
    except OSError as e:
        print("error: %s" % e)
        return 2

    _print_report(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
