"""Moderation / safety policy for the creative lanes.

Deterministic and local — no external moderation provider. Generation prompts and
generated copy are screened against a policy: anything matching a deny rule is
**blocked**, and everything else is marked **review_required** so a human approves
generated creative before it is treated as final. Nothing is silently passed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Regulated/medical/compliance claims that must never be emitted as fact, plus
# unsafe content markers. Matched case-insensitively as substrings.
DENY_TERMS: List[str] = [
    # medical / regulated claims
    "cure", "cures", "treat disease", "prevents disease", "fda approved",
    "medical grade", "clinically proven", "anti-cancer",
    # brand-compliance (Mogra rules: never invent seals/nutrition/identifiers)
    "usda certified", "usda organic seal", "nutrition facts", "supplement facts",
    "non-gmo project verified", "upc", "lot code", "supplier:",
    # unsafe content
    "explicit", "nsfw", "sexual", "gore", "weapon", "drug use",
]

# Default policy. `require_review` means generated creative is never "final"
# without an explicit human approval step.
DEFAULT_POLICY: Dict[str, Any] = {
    "require_review": True,
    "deny_terms": DENY_TERMS,
    "allowlist": [],  # explicit exemptions (exact substrings, matched first)
    "version": "moderation-v1",
}


@dataclass
class ModerationResult:
    allowed: bool
    review_required: bool
    flags: List[Dict[str, str]] = field(default_factory=list)
    checked: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "review_required": self.review_required,
            "flags": self.flags,
            "checked": self.checked,
            "policy": DEFAULT_POLICY["version"],
        }


def policy() -> Dict[str, Any]:
    return {
        "version": DEFAULT_POLICY["version"],
        "require_review": DEFAULT_POLICY["require_review"],
        "deny_term_count": len(DEFAULT_POLICY["deny_terms"]),
        "allowlist_count": len(DEFAULT_POLICY["allowlist"]),
    }


def screen_text(text: str, *, pol: Optional[Dict[str, Any]] = None) -> ModerationResult:
    pol = pol or DEFAULT_POLICY
    low = (text or "").lower()
    allow = [a.lower() for a in pol.get("allowlist", []) if a]
    flags: List[Dict[str, str]] = []
    for term in pol.get("deny_terms", []):
        t = term.lower().strip()
        if not t:
            continue
        # Word-boundary match so "cure" never trips "manicure"/"secure".
        if re.search(r"\b" + re.escape(t) + r"\b", low) and not any(a and a in t for a in allow):
            flags.append({"term": term, "reason": "deny_term"})
    allowed = not flags
    return ModerationResult(
        allowed=allowed,
        review_required=bool(pol.get("require_review", True)) and allowed,
        flags=flags,
        checked=1,
    )


def _iter_strings(obj: Any):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _iter_strings(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _iter_strings(v)


def screen_payload(payload: Any, *, pol: Optional[Dict[str, Any]] = None) -> ModerationResult:
    """Screen every string inside a request payload (prompts, copy, fields)."""
    pol = pol or DEFAULT_POLICY
    flags: List[Dict[str, str]] = []
    checked = 0
    for s in _iter_strings(payload):
        checked += 1
        r = screen_text(s, pol=pol)
        for f in r.flags:
            flags.append({**f, "sample": s[:80]})
    allowed = not flags
    return ModerationResult(
        allowed=allowed,
        review_required=bool(pol.get("require_review", True)) and allowed,
        flags=flags,
        checked=checked,
    )
