"""Costco Non-Kirkland research — canonical vocabularies.

PURE / OFFLINE. Single source of truth for every status vocabulary the pipeline
uses. No external calls. Values follow the Northstar "null-first" honesty rules
(unknown stays None / its own status, never zero, never silently merged).
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:
        return self.value


# ---------------------------------------------------------------------------
# Costco source product
# ---------------------------------------------------------------------------

class EvidenceClass(StrEnum):
    """How a Costco record entered Northstar (never "live" for offline data)."""
    USER_PROVIDED_EXPORT = "user_provided_export"
    CACHED_SOURCE_SNAPSHOT = "cached_source_snapshot"
    BENCHMARK_REFERENCE = "benchmark_reference"
    HISTORICAL_REFERENCE = "historical_reference"
    MANUAL_ENTRY = "manual_entry"


class FreshnessStatus(StrEnum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    UNKNOWN = "unknown"


ALLOWED_EVIDENCE_CLASSES = tuple(e.value for e in EvidenceClass)
ALLOWED_FRESHNESS_STATUSES = tuple(e.value for e in FreshnessStatus)


def classify_freshness(observed_at: object, now: object = None,
                       fresh_days: int = 7, aging_days: int = 30) -> str:
    """Classify a record's freshness from an observed timestamp.

    Offline records are never 'live'; freshness is a measure of how old the
    cached snapshot is. Unknown/missing timestamps are 'unknown'.
    """
    from datetime import datetime, timezone
    if observed_at is None:
        return FreshnessStatus.UNKNOWN.value
    if isinstance(observed_at, (int, float)):
        dt = datetime.fromtimestamp(observed_at, tz=timezone.utc)
    else:
        try:
            dt = datetime.fromisoformat(str(observed_at).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return FreshnessStatus.UNKNOWN.value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if isinstance(now, (int, float)):
        now = datetime.fromtimestamp(now, tz=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    age_days = (now - dt).total_seconds() / 86400.0
    if age_days <= fresh_days:
        return FreshnessStatus.FRESH.value
    if age_days <= aging_days:
        return FreshnessStatus.AGING.value
    return FreshnessStatus.STALE.value


# ---------------------------------------------------------------------------
# Amazon match candidate
# ---------------------------------------------------------------------------

class IdentityStatus(StrEnum):
    UNRESOLVED = "unresolved"
    UPC_EXACT_CANDIDATE = "upc_exact_candidate"
    MANUFACTURER_PART_EXACT_CANDIDATE = "manufacturer_part_exact_candidate"
    TITLE_PACK_CANDIDATE = "title_pack_candidate"
    VERIFIED_EXACT_PACK_MATCH = "verified_exact_pack_match"
    PACK_MISMATCH = "pack_mismatch"
    SIZE_MISMATCH = "size_mismatch"
    VARIATION_AMBIGUOUS = "variation_ambiguous"
    IDENTITY_CONFLICT = "identity_conflict"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


ALLOWED_IDENTITY_STATUSES = tuple(e.value for e in IdentityStatus)


# ---------------------------------------------------------------------------
# Identity validation state machine (source product -> provider-reported ASIN)
# ---------------------------------------------------------------------------

class IdentityState(StrEnum):
    """Deterministic identity state linking a source product to a provider
    reported Amazon listing. `exact_match_verified` requires additional
    validation beyond provider-reporting (see identity.py)."""
    EXACT_MATCH_VERIFIED = "exact_match_verified"
    EXACT_MATCH_PROVIDER_REPORTED = "exact_match_provider_reported"
    PROBABLE_MATCH = "probable_match"
    TITLE_PACK_CANDIDATE = "title_pack_candidate"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    PACK_MISMATCH = "pack_mismatch"
    VARIATION_MISMATCH = "variation_mismatch"
    BRAND_MISMATCH = "brand_mismatch"
    IDENTIFIER_MISMATCH = "identifier_mismatch"
    NO_MATCH = "no_match"
    UNKNOWN = "unknown"


ALLOWED_IDENTITY_STATES = tuple(e.value for e in IdentityState)


# ---------------------------------------------------------------------------
# Multipack split validation
# ---------------------------------------------------------------------------

class SplitPackState(StrEnum):
    APPROVED_SPLIT = "approved_split"
    INTACT_ONLY = "intact_only"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    PROHIBITED_SPLIT = "prohibited_split"
    UNKNOWN = "unknown"


ALLOWED_SPLIT_PACK_STATES = tuple(e.value for e in SplitPackState)


# ---------------------------------------------------------------------------
# Provider import row outcomes
# ---------------------------------------------------------------------------

class ImportRowStatus(StrEnum):
    IMPORTED = "imported"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    NEEDS_MAPPING = "needs_mapping"
    STALE = "stale"
    MISSING_REQUIRED_FIELDS = "missing_required_fields"
    IDENTITY_AMBIGUOUS = "identity_ambiguous"


ALLOWED_IMPORT_ROW_STATUSES = tuple(e.value for e in ImportRowStatus)


# ---------------------------------------------------------------------------
# Market snapshot / provenance
# ---------------------------------------------------------------------------

class CaptureStatus(StrEnum):
    CAPTURED = "captured"
    UNAVAILABLE = "unavailable"
    PROVIDER_NOT_SUPPORTED = "provider_not_supported"
    PARSE_ERROR = "parse_error"
    IDENTITY_CONFLICT = "identity_conflict"
    NOT_REQUESTED = "not_requested"
    STALE = "stale"


ALLOWED_CAPTURE_STATUSES = tuple(e.value for e in CaptureStatus)


class SnapshotEvidenceClass(StrEnum):
    BENCHMARK_REFERENCE = "benchmark_reference"
    CACHED_PROVIDER_SNAPSHOT = "cached_provider_snapshot"
    PROVIDER_ESTIMATE = "provider_estimate"
    USER_ENTERED_ASSUMPTION = "user_entered_assumption"
    LIVE_VERIFIED = "live_verified"
    INDEPENDENTLY_VERIFIED_DOCUMENT = "independently_verified_document"
    UNAVAILABLE = "unavailable"


# ---------------------------------------------------------------------------
# Economics
# ---------------------------------------------------------------------------

class EconomicsCompleteness(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE_COST = "incomplete_cost"
    INCOMPLETE_FEES = "incomplete_fees"
    INCOMPLETE_PRICE = "incomplete_price"
    BLOCKED_IDENTITY_MISMATCH = "blocked_identity_mismatch"
    BLOCKED_SOURCE_STALE = "blocked_source_stale"
    NOT_CALCULATED = "not_calculated"


ALLOWED_ECONOMICS_COMPLETENESS = tuple(e.value for e in EconomicsCompleteness)


class CalculationClass(StrEnum):
    """Economics classification.

    `hypothetical` is the ONLY class allowed when any assumption is used.
    A `hypothetical` model never authorizes a purchase.
    """
    VERIFIED = "verified"
    HYPOTHETICAL = "hypothetical"
    ESTIMATED = "estimated"
    BLOCKED = "blocked"
    NOT_CALCULATED = "not_calculated"


# ---------------------------------------------------------------------------
# Golden Goose scoring
# ---------------------------------------------------------------------------

class RecommendationStatus(StrEnum):
    CANDIDATE = "candidate"
    RESEARCH_REQUIRED = "research_required"
    WATCHLIST = "watchlist"
    HIGH_PRIORITY_REVIEW = "high_priority_review"
    REJECTED = "rejected"
    BLOCKED_IDENTITY_MISMATCH = "blocked_identity_mismatch"
    BLOCKED_INCOMPLETE_ECONOMICS = "blocked_incomplete_economics"
    BLOCKED_COMPLIANCE_RISK = "blocked_compliance_risk"


ALLOWED_RECOMMENDATION_STATUSES = tuple(e.value for e in RecommendationStatus)


# ---------------------------------------------------------------------------
# Operational recommendation statuses (Phase 6 — manual-export workflow)
# ---------------------------------------------------------------------------

class OperationalRecommendation(StrEnum):
    """Candidate-level operational recommendation states."""
    BLOCKED = "blocked"
    NEEDS_ENRICHMENT = "needs_enrichment"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    WATCHLIST = "watchlist"
    TEST_BUY_CANDIDATE = "test_buy_candidate"
    QUALIFIED_CANDIDATE = "qualified_candidate"
    PRIORITY_CANDIDATE = "priority_candidate"
    PURCHASE_AUTHORIZATION_REQUIRED = "purchase_authorization_required"
    PURCHASE_AUTHORIZED = "purchase_authorized"


ALLOWED_OPERATIONAL_RECOMMENDATIONS = tuple(e.value for e in OperationalRecommendation)


# ---------------------------------------------------------------------------
# Approval states
# ---------------------------------------------------------------------------

class ApprovalState(StrEnum):
    REQUESTED = "requested"
    GRANTED = "granted"
    EXPIRED = "expired"
    REVOKED = "revoked"
    INVALIDATED = "invalidated"


ALLOWED_APPROVAL_STATES = tuple(e.value for e in ApprovalState)


# ---------------------------------------------------------------------------
# Identity / match reason codes (for exports and decision reports)
# ---------------------------------------------------------------------------

class ReasonCode(StrEnum):
    BLOCKED_EXCLUSION = "blocked_exclusion"
    BLOCKED_POLICY = "blocked_policy"
    BLOCKED_IDENTITY = "blocked_identity"
    BLOCKED_RESTRICTED = "blocked_restricted"
    BLOCKED_AMAZON_RETAIL = "blocked_amazon_retail_active"
    BLOCKED_BRAND_SELLER = "blocked_brand_seller_active"
    BLOCKED_FBA_COMPETITION = "blocked_fba_competition"
    BLOCKED_SPLIT = "blocked_split_pack"
    BLOCKED_WEIGHT = "blocked_overweight"
    BLOCKED_EVIDENCE = "blocked_incomplete_evidence"
    NEEDS_ENRICHMENT = "needs_enrichment"
    MANUAL_REVIEW = "manual_review_required"
    WATCHLIST_BELOW_THRESHOLD = "watchlist_below_threshold"
    TEST_BUY_BELOW_QUALIFIED = "test_buy_below_qualified"
    QUALIFIED = "qualified"
    PRIORITY = "priority"


ALLOWED_REASON_CODES = tuple(e.value for e in ReasonCode)


PURCHASE_AUTHORIZATION_NOT_AUTHORIZED = "not_authorized"
PURCHASE_AUTHORIZATION_AUTHORIZED = "authorized"


# ---------------------------------------------------------------------------
# Disallowed product classes (excluded alongside Kirkland at import)
# ---------------------------------------------------------------------------

class DisallowedClass(StrEnum):
    HAZARDOUS = "hazardous"
    MELTABLE = "meltable"
    FRAGILE = "fragile"
    EXPIRY = "expiry_risk"
    OVERSIZED = "oversized"
    GATED = "restricted_gated"
    FOOD_PERISHABLE = "perishable_food"
    FOOD = "food"
    GROCERY = "grocery"
    BEVERAGE = "beverage"
    SUPPLEMENT = "supplement"
    OTC = "otc_drug"
    NICOTINE = "nicotine"
    COSMETICS = "cosmetics"
    SKINCARE = "skincare"
    HAIRCARE = "haircare"
    FRAGRANCE = "fragrance"
    TOPICAL_BEAUTY = "topical_beauty"
    COLLECTIBLE = "collectible"
    FINE_JEWELRY = "fine_jewelry"
    GIFT_CARD = "gift_card"
    REGULATED = "regulated_medical_or_drug"
    ALCOHOL = "alcohol"
    TOBACCO = "tobacco"
    WEAPONS = "weapons"
    ANIMAL_PRODUCTS = "animal_or_animal_products"


ALLOWED_DISALLOWED_CLASSES = tuple(e.value for e in DisallowedClass)

DISALLOWED_CLASS_EXCLUSION_REASON = "disallowed_product_class"


# ---------------------------------------------------------------------------
# Provider sign-in gate
# ---------------------------------------------------------------------------

class SignInService(StrEnum):
    COSTCO = "costco"
    SELLERAMP = "selleramp"


SIGN_IN_SERVICES = tuple(e.value for e in SignInService)


# ---------------------------------------------------------------------------
# Risk flags (canonical vocabulary)
# ---------------------------------------------------------------------------

class RiskFlag(StrEnum):
    KIRKLAND_SOURCE = "kirkland_source_product"
    IDENTITY_MISMATCH = "identity_mismatch"
    VARIATION_AMBIGUITY = "variation_ambiguity"
    STALE_DATA = "stale_data"
    MISSING_ECONOMICS = "missing_economics"
    BUY_BOX_RISK = "buy_box_risk"
    EXCESSIVE_COMPETITION = "excessive_seller_competition"
    HAZARDOUS = "hazardous"
    MELTABLE = "meltable"
    FRAGILE = "fragile"
    EXPIRY = "expiry_risk"
    OVERSIZED = "oversized"
    GATED_UNKNOWN = "restricted_gated_uncertainty"
    INVOICE_READINESS_UNKNOWN = "invoice_readiness_unknown"
    RETAIL_RECEIPT_ONLY = "costco_retail_receipt_only"
    SUPPLY_BOTTLENECK = "supply_bottleneck"
    SINGLE_ASIN_CONCENTRATION = "single_asin_concentration"
    ONE_SOURCE_ONLY = "one_source_only_evidence"
    PACK_MISMATCH = "pack_mismatch"
    UNVERIFIED_EXACT_MATCH = "unverified_exact_match"
    NO_SALES_ESTIMATE = "no_sales_estimate"


def risk_flag_values() -> tuple:
    return tuple(r.value for r in RiskFlag)