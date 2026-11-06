"""No-direct-Amazon-scan policy guard.

This pipeline never opens Amazon product pages, never scrapes Amazon search or
offer pages, never uses Amazon browser automation, and never calls undocumented
Amazon endpoints. Amazon-market information comes ONLY from approved
SellerAmp snapshots or approved exports.

`assert_no_amazon_direct_scan()` is the enforcement point: any code path that
would open an Amazon.com URL raises `AmazonDirectScanProhibited`.

T1-amazon-guard (2026-11-06): the guard used to inspect `url=` only, while both
production callers pass `asin=`, so it never fired. It now inspects the `asin`
argument too - see `assert_no_amazon_direct_scan`.
"""
from __future__ import annotations

import re
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

# A bare ASIN is an *identity token*, never a fetch target: 5-20 alphanumerics
# and nothing else. Anything carrying a scheme, host, slash, dot, space or
# query string is a locator that could be fetched, so it is refused.
_BARE_ASIN_RE = re.compile(r"^[A-Za-z0-9]{5,20}$")


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
    """Enforce the no-direct-Amazon-scan policy, before any request is made.

    Refused (raises `AmazonDirectScanProhibited`):

    * a `url` that points at an Amazon marketplace host, and
    * an `asin` that is not a *bare* ASIN identity - a URL, a share link, a
      host, or a `/dp/` path. A provider column or a manifest item labelled
      "asin" is exactly where a direct-scan target would be smuggled into
      `adapter.fetch(asin)`, so the locator form is refused on this argument
      too, not only on `url=`.

    Allowed: `asin=None`, an empty/whitespace value, and a bare ASIN.

    Why a bare ASIN is still allowed (decision, 2026-11-06): both production
    callers pass `asin=` for every row of an *authorized* input -
    `pipeline.py:383` (manifest items fetched through an approved provider
    adapter) and `provider_imports/selleramp_importer.py:67` (rows of an
    approved SellerAmp export). Those are the sanctioned path; refusing every
    ASIN would raise on 100% of sanctioned rows, i.e. disable the permitted
    workflow instead of blocking the prohibited one. The ASIN is only ever
    used as an identity key for the provider lookup, never to build an
    amazon.com URL (see this module's contract above), and
    `tests/test_signin_disallowed_guard.py::test_assert_allows_provider_deep_link`
    pins that behaviour. What was actually broken - and is now fixed - is that
    a *locator* arriving through `asin=` was waved straight through.
    """
    if is_amazon_direct_url(url):
        raise AmazonDirectScanProhibited(
            "Direct Amazon.com page access is prohibited for this pipeline. "
            "Use approved SellerAmp snapshots or exports only.")
    if asin is not None:
        ident = str(asin).strip()
        if ident and not _BARE_ASIN_RE.match(ident):
            raise AmazonDirectScanProhibited(
                "Direct Amazon page access is prohibited for this pipeline: "
                f"asin={ident[:80]!r} is a URL/host/path, not a bare ASIN. "
                "Pass the ASIN identity from an approved SellerAmp snapshot or "
                "export; never a fetchable locator.")
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