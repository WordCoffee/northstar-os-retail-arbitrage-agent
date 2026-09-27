"""No-direct-Amazon-scan policy guard.

This pipeline never opens Amazon product pages, never scrapes Amazon search or
offer pages, never uses Amazon browser automation, and never calls undocumented
Amazon endpoints. Amazon-market information comes ONLY from approved
SellerAmp snapshots or approved exports.

`assert_no_amazon_direct_scan()` is the enforcement point: any code path that
would open an Amazon.com URL raises `AmazonDirectScanProhibited`.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class AmazonDirectScanProhibited(Exception):
    """Raised when code attempts to open/fetch an Amazon.com page directly."""


# Hosts that are never to be fetched by this pipeline.
AMAZON_DIRECT_HOSTS = (
    "amazon.com", "www.amazon.com", "amazon.co.uk", "amazon.ca", "amazon.de",
    "amazon.co.jp", "amazon.in", "amazon.com.mx", "amazon.com.br",
)

# Documented authorized Amazon-market sources (approved providers/exports only).
AUTHORIZED_AMAZON_MARKET_SOURCES = ("selleramp", "approved_amazon_export")


def is_amazon_direct_url(url: Optional[str]) -> bool:
    """True if the URL points at an Amazon marketplace page."""
    if not url:
        return False
    u = url.lower()
    for host in AMAZON_DIRECT_HOSTS:
        if host in u:
            return True
    return False


def assert_no_amazon_direct_scan(url: Optional[str] = None, *, asin: Optional[str] = None) -> None:
    """Enforce the no-direct-Amazon-scan policy.

    Raises AmazonDirectScanProhibited if a direct Amazon URL is supplied.
    `asin` is accepted (Amazon-market identity) but never used to build a fetch URL.
    """
    if is_amazon_direct_url(url):
        raise AmazonDirectScanProhibited(
            "Direct Amazon.com page access is prohibited for this pipeline. "
            "Use approved SellerAmp snapshots or exports only.")
    return None


def authorized_market_source(source: Optional[str]) -> bool:
    """True when the Amazon-market data source is an approved provider/export."""
    if not source:
        return False
    return (source or "").lower() in AUTHORIZED_AMAZON_MARKET_SOURCES


def verify_market_provenance(fields: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Verify that each Amazon-market field's source is authorized.

    Returns a dict of field -> {ok, source, reason}. Fields whose source is not
    an approved provider/export are flagged (fail-closed for downstream use).
    """
    fields = fields or {}
    out = {}
    for field_name, meta in fields.items():
        source = (meta or {}).get("source")
        ok = authorized_market_source(source)
        out[field_name] = {
            "ok": ok,
            "source": source,
            "reason": "authorized" if ok else "source not authorized for Amazon market data",
        }
    return out