"""Tests for the Bojo scanner tool (`scan_products`).

Offline: no network, no Amazon request, no database. The scanner module is the
one injectable dependency and is faked here; the fake records the production
call shape so the "cache first, live only on request" rule is pinned.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from bojo_tools import sourcing_extra  # noqa: E402
from bojo_tools.sourcing_extra import TOOLS, scan_products  # noqa: E402

CACHE_ROWS = [
    {"asin": "B001", "name": "Northstar Matcha Powder 8 oz",
     "brand": "Northstar", "amazon_price": 24.99},
    {"asin": "B002", "name": "Kirkland Green Tea Bags",
     "brand": "Kirkland Signature", "amazon_price": 19.99},
]

LIVE_ROWS = [
    {"asin": "B003", "name": "Matcha Ceremonial Grade", "amazon_price": 31.5},
]


class FakeGate:
    def __init__(self, enabled):
        self.enabled = enabled

    def live_enabled(self):
        return self.enabled


class FakeScanner:
    def __init__(self, cached=None, live=None, meta=None, load_error=None,
                 live_error=None, gate=None, search_error=None):
        self.cached = cached if cached is not None else []
        self.live = live if live is not None else []
        self.meta = meta or {"cache_status": "fresh", "cache_candidate_count": len(self.cached)}
        self.load_error = load_error
        self.live_error = live_error
        self.search_error = search_error
        self.calls = []
        if gate is not None:
            self.live_gate = gate

    def cache_meta(self):
        return dict(self.meta)

    def load_cached_candidates(self):
        if self.load_error is not None:
            raise self.load_error
        return [dict(row) for row in self.cached]

    def search_products(self, keywords=None, pages=None, match_all=False):
        self.calls.append(
            {"keywords": keywords, "pages": pages, "match_all": match_all}
        )
        if self.live_error is not None:
            raise self.live_error
        return [dict(row) for row in self.live]


def test_tools_registry_exports_scan_products():
    assert set(TOOLS) == {"scan_products"}
    assert TOOLS["scan_products"] is scan_products


def test_scan_products_reads_the_cache_first_and_never_goes_live():
    scanner = FakeScanner(cached=CACHE_ROWS)

    result = scan_products("matcha", live=True, scanner=scanner)

    assert result["ok"] is True
    assert result["tool"] == "scan_products"
    data = result["data"]
    assert data["source"] == "cache"
    assert data["count"] == 1
    assert data["candidates"][0]["asin"] == "B001"
    assert data["cache"]["cache_status"] == "fresh"
    assert scanner.calls == []  # the live search was never asked for
    json.dumps(result)


def test_scan_products_goes_live_only_when_asked_and_the_cache_misses():
    scanner = FakeScanner(cached=[], live=LIVE_ROWS)

    result = scan_products("matcha", keywords=["green tea"], live=True, scanner=scanner)

    assert result["ok"] is True
    assert result["data"]["source"] == "live"
    assert result["data"]["candidates"][0]["asin"] == "B003"
    assert scanner.calls == [
        {"keywords": ["matcha", "green tea"], "pages": None, "match_all": True}
    ]


def test_scan_products_cache_miss_without_live_is_a_business_failure():
    scanner = FakeScanner(cached=CACHE_ROWS)

    result = scan_products("protein powder", scanner=scanner)

    assert result["ok"] is False
    assert result["tool"] == "scan_products"
    assert result["reason"].startswith("no candidates for 'protein powder' (cache=fresh")
    assert "no live request made" in result["reason"]


def test_scan_products_reports_a_refused_live_envelope():
    scanner = FakeScanner(cached=[], live=[], gate=FakeGate(False))

    result = scan_products("matcha", live=True, scanner=scanner)

    assert result["ok"] is False
    assert "the live envelope is not armed" in result["reason"]


def test_scan_products_reports_a_live_search_error():
    scanner = FakeScanner(cached=[], live=[], search_error="402 insufficient credits")
    scanner.LAST_SEARCH_ERROR = "402 insufficient credits"

    result = scan_products("matcha", live=True, scanner=scanner)

    assert result["ok"] is False
    assert "live error: 402 insufficient credits" in result["reason"]


def test_scan_products_cache_read_error_is_reported_not_raised():
    scanner = FakeScanner(load_error=RuntimeError("cache file is corrupt"))

    result = scan_products("matcha", scanner=scanner)

    assert result["ok"] is False
    assert result["reason"].startswith("candidate cache read failed: RuntimeError")


def test_scan_products_live_dependency_error_is_reported_not_raised():
    scanner = FakeScanner(cached=[], live_error=RuntimeError("provider down"))

    result = scan_products("matcha", live=True, scanner=scanner)

    assert result["ok"] is False
    assert result["reason"].startswith("live candidate search failed: RuntimeError")


def test_scan_products_empty_query_is_a_business_failure():
    result = scan_products("   ", keywords=[""], scanner=FakeScanner())

    assert result == {
        "ok": False,
        "tool": "scan_products",
        "reason": "no query or keywords supplied",
    }


def test_scan_products_rejects_a_bad_limit_and_pages():
    scanner = FakeScanner()
    assert scan_products("matcha", limit=0, scanner=scanner)["reason"] == "limit must be >= 1"
    assert scan_products("matcha", pages=0, scanner=scanner)["reason"] == "pages must be >= 1"


def test_scan_products_programmer_errors_raise():
    with pytest.raises(TypeError):
        scan_products(5)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scan_products("matcha", keywords="green tea")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scan_products("matcha", limit="5")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scan_products("matcha", live="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        scan_products("matcha", pages="2")  # type: ignore[arg-type]


def test_default_scanner_is_the_real_amazon_search_module():
    import amazon_search

    assert sourcing_extra._default_scanner() is amazon_search
    assert scan_products.__defaults__[-1] is None
