"""Subscriber tiers & entitlements (1C-06 master slice / Phase B).

ONE server-side mapping of subscription tier -> atomic feature flags. No
hardcoded plan-name checks anywhere else in the codebase; every enforcement
goes through EntitlementService.

Free/trial tier has EXPLICIT, enforced limits (never implicit). Unknown
remains unknown.
"""
from __future__ import annotations

FREE = "free"
TRIAL = "trial"
PRO = "pro"
TEAM = "team"

# Single source of truth: tier -> atomic flags.
TIERS = {
    FREE: {
        "max_jobs_per_month": 1000,
        "export_enabled": False,
        "advanced_reports": False,
        "seat_limit": 10,
        "support_level": "none",
        "override_allowed": False,
    },
    TRIAL: {
        "max_jobs_per_month": 5,
        "export_enabled": True,
        "advanced_reports": False,
        "seat_limit": 3,
        "support_level": "email",
        "override_allowed": True,
    },
    PRO: {
        "max_jobs_per_month": 5000,
        "export_enabled": True,
        "advanced_reports": True,
        "seat_limit": 25,
        "support_level": "priority",
        "override_allowed": True,
    },
    TEAM: {
        "max_jobs_per_month": 50000,
        "export_enabled": True,
        "advanced_reports": True,
        "seat_limit": 100,
        "support_level": "priority",
        "override_allowed": True,
    },
}

# Beta cohorts: a cohort is a named plan assignment (source of truth for the
# lifecycle admin plan/cohort field).
COHORTS = {
    "free": {"tier": FREE, "label": "Free (beta)"},
    "trial": {"tier": TRIAL, "label": "Trial (beta)"},
    "pro": {"tier": PRO, "label": "Pro (beta)"},
    "team": {"tier": TEAM, "label": "Team (beta)"},
}

ATOMIC_ENTITLEMENTS = ("max_jobs_per_month", "export_enabled",
                       "advanced_reports", "seat_limit", "support_level",
                       "override_allowed")

PRICES = {
    "price_trial": {"tier": TRIAL, "label": "Beta Trial (test mode)", "amount": "0.00"},
    "price_pro": {"tier": PRO, "label": "Pro (test mode)", "amount": "99.00"},
    "price_team": {"tier": TEAM, "label": "Team (test mode)", "amount": "299.00"},
}

DEFAULT_TIER = FREE


def tier_flags(tier: str) -> dict:
    """Atomic flags for a tier. Unknown tiers fail closed to FREE."""
    return dict(TIERS.get(tier, TIERS[FREE]))


def price_tier(price_id: str) -> str:
    return PRICES.get(price_id, {}).get("tier", FREE)


def is_known_price(price_id: str) -> bool:
    return price_id in PRICES