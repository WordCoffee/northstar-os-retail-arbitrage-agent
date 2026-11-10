"""Drop-before-see: nothing reaches a model or a disk before this says yes.

Work order §2, screen privacy rules. The owner works a day job on this machine, so the
default is refusal and the blocklist is checked on **title, process name and URL**
before a frame exists. A blocked window is recorded as `blocked-window` with a
timestamp and nothing else: no pixels, no OCR text, no interaction.

    from vision.privacy import classify, redact
    verdict = classify(title, process, url)
    if not verdict["allow"]:
        raise RuntimeError(verdict["reason"])
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

#: Matched case-insensitively as substrings. Amazon is first and absolute: the work
#: order forbids Amazon "including by screen control", so no exception exists here.
BLOCK_TITLES = (
    "amazon", "amzn",
    "1password", "bitwarden", "lastpass", "keepass", "dashlane", "enpass",
    "password", "passwords",
    "bank", "banking", "chase", "wells fargo", "citi", "hsbc", "barclays",
    "paypal", "venmo", "wise", "stripe dashboard",
    "tax", "irs", "hmrc",
)

BLOCK_PROCESSES = (
    "amazon.exe", "amazonapp.exe",
    "1password.exe", "bitwarden.exe", "keepassxc.exe", "lastpass.exe",
    "dashlane.exe", "enpass.exe",
    "keepass.exe",
)

BLOCK_URLS = (
    "amazon.", "amzn.", "smile.amazon.", "media-amazon.",
    "1password.com", "bitwarden.com", "lastpass.com", "keepass.info",
    "paypal.com", "stripe.com/dashboard",
)

#: Credential-shaped strings that must not leave the machine even in allowed frames.
_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer|basic)\s+[a-z0-9._\-]{8,}"),
    re.compile(r"(?i)\b(sk|pk|rk)[-_][a-z0-9_\-]{8,}"),
    re.compile(r"(?i)\b(api[_-]?key|secret|token|password|passwd|pwd)\s*[:=]\s*\S+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
)


def _hit(text: str, needles: Iterable[str]) -> str:
    folded = (text or "").casefold()
    for needle in needles:
        if needle.casefold() in folded:
            return needle
    return ""


def classify(title: str = "", process: str = "", url: str = "") -> Dict[str, Any]:
    """Allow or refuse one window, by title, process and URL. Refusal names the match."""
    for field, value, needles in (("title", title, BLOCK_TITLES),
                                  ("process", process, BLOCK_PROCESSES),
                                  ("url", url, BLOCK_URLS)):
        match = _hit(value, needles)
        if match:
            return {"allow": False, "field": field, "matched": match,
                    "reason": f"{field} matches blocked pattern {match!r}"}
    return {"allow": True, "field": "", "matched": "", "reason": "no blocked pattern"}


def redact(text: str) -> str:
    """Strip credential-shaped substrings before any text leaves the machine."""
    out = text or ""
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


def mask_regions(elements: Iterable[Dict[str, Any]]) -> list:
    """Mark password and payment fields for masking from UIA roles, not from pixels.

    Returns the same elements with `mask: True` where a field must be blacked out.
    """
    masked = []
    for element in elements or ():
        item = dict(element or {})
        role = str(item.get("role") or item.get("control_type") or "").casefold()
        name = str(item.get("name") or item.get("label") or "").casefold()
        sensitive = (
            "password" in role or "password" in name
            or "card" in name or "credit" in name or "cvv" in name or "cvc" in name
            or "security code" in name or "iban" in name or "account number" in name
        )
        if sensitive:
            item["mask"] = True
            item["value"] = ""
        masked.append(item)
    return masked
