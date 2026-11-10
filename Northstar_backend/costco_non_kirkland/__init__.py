"""Northstar — Costco Non-Kirkland Product Research Pipeline.

OFFLINE-FIRST. This package identifies potentially attractive NON-Kirkland
Costco products from data that already exists locally, resolves them to Amazon
ASIN candidates, and persists evidence-backed records into the canonical
Northstar database for Product Finder / Golden Goose use.

SAFETY INVARIANTS
-----------------
* Never crawls or fetches Costco. Uses only local files (CSV/JSON/cache/db).
* Provider adapters (SellerAmp) are DISABLED BY DEFAULT and only
  ever operate on mocks/fixtures, sanctioned exports, or explicitly approved
  live ingestion. No automatic live calls. SellerSprite is retired (no adapter).
* Costco discovery cost is NOT sourcing authorization. `purchase_authorization_status`
  is always `not_authorized` unless an independent, explicit human decision exists.
* Unknown is never zero; identity is evaluated separately from economics.
"""
from __future__ import annotations

from .enums import (
    ALLOWED_EVIDENCE_CLASSES,
    ALLOWED_FRESHNESS_STATUSES,
    ALLOWED_CAPTURE_STATUSES,
    ALLOWED_IDENTITY_STATUSES,
    ALLOWED_ECONOMICS_COMPLETENESS,
    ALLOWED_RECOMMENDATION_STATUSES,
    EvidenceClass,
    FreshnessStatus,
    CaptureStatus,
    IdentityStatus,
    EconomicsCompleteness,
    RecommendationStatus,
)
from .kirkland_exclusion import (
    KIRKLAND_ALIASES,
    is_kirkland,
    evaluate_exclusion,
    audit_exclusion,
)
from .disallowed import (
    DISALLOWED_CLASS_RULES,
    classify_disallowed,
    evaluate_disallowed,
    audit_disallowed,
)
from .amazon_guard import (
    AmazonDirectScanProhibited,
    assert_no_amazon_direct_scan,
    authorized_market_source,
)
from .normalize import normalize_costco_record, normalize_brand
from .matching import (
    AmazonAttributes,
    MatchMethod,
    assess_amazon_match,
    assess_pack_identity,
    ASSESSMENT_PRIORITY,
)
from .economics import (
    compute_economics,
    EconomicsResult,
    conservative_sale_price,
    maximum_buy_cost,
    EconomicsCompleteness as _EC,
)
from .scoring import score_golden_goose, GG_SCORER_VERSION
from .settings import get_settings, DEFAULT_SETTINGS
from .competition import (
    assess_competition,
    mfn_opportunity_score,
    SCORE_VERSION as MFN_SCORE_VERSION,
)
from .identity import (
    assess_identity,
    evaluate_split_pack,
    IdentityAssessment,
)

__all__ = [
    "ALLOWED_EVIDENCE_CLASSES",
    "ALLOWED_FRESHNESS_STATUSES",
    "ALLOWED_CAPTURE_STATUSES",
    "ALLOWED_IDENTITY_STATUSES",
    "ALLOWED_ECONOMICS_COMPLETENESS",
    "ALLOWED_RECOMMENDATION_STATUSES",
    "EvidenceClass",
    "FreshnessStatus",
    "CaptureStatus",
    "IdentityStatus",
    "EconomicsCompleteness",
    "RecommendationStatus",
    "KIRKLAND_ALIASES",
    "is_kirkland",
    "evaluate_exclusion",
    "audit_exclusion",
    "DISALLOWED_CLASS_RULES",
    "classify_disallowed",
    "evaluate_disallowed",
    "audit_disallowed",
    "SIGN_IN_URLS",
    "require_signin",
    "mark_signed_in",
    "SignInPrompt",
    "AmazonDirectScanProhibited",
    "assert_no_amazon_direct_scan",
    "authorized_market_source",
    "normalize_costco_record",
    "normalize_brand",
    "AmazonAttributes",
    "MatchMethod",
    "assess_amazon_match",
    "assess_pack_identity",
    "ASSESSMENT_PRIORITY",
    "compute_economics",
    "EconomicsResult",
    "conservative_sale_price",
    "maximum_buy_cost",
    "score_golden_goose",
    "GG_SCORER_VERSION",
    "get_settings",
    "DEFAULT_SETTINGS",
    "assess_competition",
    "mfn_opportunity_score",
    "MFN_SCORE_VERSION",
    "assess_identity",
    "evaluate_split_pack",
    "IdentityAssessment",
]

PACKAGE_VERSION = "0.1.0"
OFFLINE_ONLY = True
PROVIDERS_DISABLED_BY_DEFAULT = True


def __getattr__(name):
    """Lazy re-export of the signin gate (avoids runpy warning when the signin
    module is run as `python -m costco_non_kirkland.signin`)."""
    if name in ("SIGN_IN_URLS", "require_signin", "mark_signed_in", "SignInPrompt"):
        from . import signin as _signin
        return getattr(_signin, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")