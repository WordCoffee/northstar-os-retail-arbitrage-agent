"""URL/host handling + the hardcoded Amazon blocklist (Phase 2).

The Amazon check is intentionally broad and NOT configurable: it matches
``amazon.*`` domains and subdomains, the shorteners (``amzn.to``, ``amzn.eu``,
``a.co``), domain-substring typosquats, and confusable/IDNA lookalikes
(e.g. a Cyrillic ``аmazon.com``). Over-blocking here is safe; under-blocking is
not, because Amazon access is hard-prohibited for this build.
"""
from __future__ import annotations

import ipaddress
import re
import urllib.parse

from .errors import PolicyConfigError

ALLOWED_SCHEMES = ("http", "https")

_AMAZON_SUBSTR = "amazon"
_AMAZON_SHORT = re.compile(r"(^|\.)(amzn\.to|amzn\.eu|a\.co)$")

# Common confusables (Cyrillic/Greek) folded to ASCII for lookalike detection.
_CONFUSABLES = str.maketrans(
    {
        "\u0430": "a",  # cyrillic a
        "\u0435": "e",  # cyrillic e
        "\u043e": "o",  # cyrillic o
        "\u0440": "p",  # cyrillic er
        "\u0441": "c",  # cyrillic es
        "\u0445": "x",  # cyrillic ha
        "\u0443": "y",  # cyrillic u
        "\u0456": "i",  # cyrillic i
        "\u04bb": "h",  # cyrillic shha
        "\u03b1": "a",  # greek alpha
        "\u03b5": "e",  # greek epsilon
        "\u03bf": "o",  # greek omicron
        "\u03c1": "p",  # greek rho
    }
)


def parse_http_url(url: str) -> urllib.parse.SplitResult:
    """Parse a URL; only http/https with a host are accepted."""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme.lower() not in ALLOWED_SCHEMES:
        raise PolicyConfigError(f"scheme_not_allowed:{parts.scheme or '(none)'}")
    if not parts.hostname:
        raise PolicyConfigError("missing_host")
    return parts


def is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip())
        return True
    except ValueError:
        return False


def normalize_host(host: str) -> str:
    """Lowercase, strip trailing dot, reject '%', IDNA-encode → ASCII form.

    IP literals (v4/v6) are canonicalized instead of IDNA-encoded.
    """
    h = host.strip().lower().rstrip(".")
    if not h or "%" in h:
        raise PolicyConfigError("host_rejected")
    if is_ip_literal(h):
        return str(ipaddress.ip_address(h))
    try:
        h = h.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise PolicyConfigError("invalid_idna_host") from exc
    return h


def _candidates(raw_host: str, ascii_host: str):
    cands = {raw_host.lower().rstrip("."), ascii_host.lower()}
    try:  # decode punycode back to unicode (catches IDNA lookalikes)
        cands.add(ascii_host.encode("ascii").decode("idna").lower())
    except Exception:
        pass
    return cands | {c.translate(_CONFUSABLES) for c in cands}


def is_amazon_host(raw_host: str, ascii_host: str) -> bool:
    """True for Amazon domains/subdomains/shorteners and lookalike encodings."""
    for cand in _candidates(raw_host, ascii_host):
        if _AMAZON_SUBSTR in cand:
            return True
        if _AMAZON_SHORT.search(cand):
            return True
    return False
