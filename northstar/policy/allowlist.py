"""Source allowlist (default deny) + Amazon hard-block composition (Phase 2).

Policy data is code-owned: ``DEFAULT_ALLOWLIST`` entries are added only by
reviewed commits — there is deliberately no runtime mutation API. The Amazon
blocklist is checked before the allowlist and cannot be overridden by it.
"""
from __future__ import annotations

from typing import Iterable

from .errors import PolicyDenied
from .urls import is_amazon_host, normalize_host, parse_http_url

DEFAULT_ALLOWLIST: tuple[str, ...] = ()
# Default deny: empty until the owner approves sources (added via reviewed
# commits). Phase 3's compatibility run will use the owner-approved list.


def domain_allowed(ascii_host: str, allowlist: Iterable[str]) -> bool:
    """Exact host or subdomain of an allowlisted entry."""
    for entry in allowlist:
        e = normalize_host(entry)
        if ascii_host == e or ascii_host.endswith("." + e):
            return True
    return False


def assert_not_amazon(raw_host: str, ascii_host: str) -> None:
    """Hardcoded block — always first, never overridable by config."""
    if is_amazon_host(raw_host, ascii_host):
        raise PolicyDenied("amazon_blocked", f"host={ascii_host}")


def check_source(url: str, allowlist: Iterable[str]) -> str:
    """Validate scheme/host, enforce Amazon block, enforce allowlist.

    Returns the normalized ASCII host. Raises ``PolicyConfigError`` for
    unparseable URLs and ``PolicyDenied`` for policy denials.
    """
    parts = parse_http_url(url)
    raw_host = parts.hostname or ""
    ascii_host = normalize_host(raw_host)
    assert_not_amazon(raw_host, ascii_host)
    if not domain_allowed(ascii_host, allowlist):
        raise PolicyDenied("domain_not_allowed", f"host={ascii_host}")
    return ascii_host
