"""Scrapling usage policy (Phase 4) — parser + plain-HTTP tiers ONLY.

The Stealthy/Dynamic (browser) fetchers and Scrapling's MCP server stay
DISABLED in this codebase: this module is the runtime guard, and tests also
scan our sources to prove nothing here imports or enables them. Stealth/anti-bot
evasion is permanently out of scope; browser work goes through the gateway and
Chrome Connect policy.
"""
from __future__ import annotations

from northstar.policy.errors import PolicyDenied

ALLOWED_TIERS = ("parser", "http")

FORBIDDEN_FEATURES = (
    "StealthyFetcher",
    "DynamicFetcher",
    "StealthySession",
    "DynamicSession",
    "PlaywrightFetcher",
    "mcp",
)


def assert_scrapling_tier(tier: str) -> None:
    """Only the parser + plain-HTTP tiers may be used."""
    if tier not in ALLOWED_TIERS:
        raise PolicyDenied("scrapling_tier_forbidden", tier)


def assert_scrapling_feature(feature: str) -> None:
    """Refuse stealth/browser/MCP features of Scrapling."""
    if feature in FORBIDDEN_FEATURES:
        raise PolicyDenied("scrapling_feature_forbidden", feature)


def healed_selector_record(
    *, selector: str, match_confidence: float, url: str
) -> dict:
    """Record a healed selector with its match confidence.

    Healed selectors are ALWAYS flagged for review and can NEVER be marked
    verified, regardless of confidence — callers persist this shape (e.g. into
    snapshot ``limitations``) so a stale-but-healed read is visible.
    """
    try:
        conf = float(match_confidence)
    except (TypeError, ValueError):
        conf = 0.0
    conf = min(1.0, max(0.0, conf))
    return {
        "selector": selector,
        "url": url,
        "match_confidence": conf,
        "flagged_for_review": True,
        "verified": False,
        "note": "healed selectors are never marked verified",
    }
