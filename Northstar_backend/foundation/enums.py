"""Foundation enums — the canonical vocabulary shared by all P0 modules.

Values are strings for stable persistence and JSON contracts.
"""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


# --- Modes (owner decision 5) -------------------------------------------------

class Environment(StrEnum):
    SANDBOX = "sandbox"
    PRODUCTION = "production"


class Role(StrEnum):
    ORGANIZATION_OWNER = "organization_owner"
    ORGANIZATION_ADMIN = "organization_admin"
    OPERATOR = "operator"
    ANALYST = "analyst"
    VIEWER = "viewer"
    INTERNAL_PLATFORM_ADMIN = "internal_platform_admin"


class ViewContext(StrEnum):
    NORMAL = "normal"
    AUDITED_CUSTOMER_PREVIEW = "audited_customer_preview"


# --- Provenance (owner decision 3; Phase 1A 02 §3) ----------------------------

class ProvenanceClass(StrEnum):
    LIVE = "live"
    CACHED = "cached"
    IMPORTED = "imported"
    BENCHMARK = "benchmark"
    COMPUTED = "computed"
    ESTIMATED = "estimated"
    MOCKED = "mocked"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class VerificationState(StrEnum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class StalenessState(StrEnum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN_AGE = "unknown_age"
    UNAVAILABLE = "unavailable"


class SourceKind(StrEnum):
    PROVIDER = "provider"
    IMPORT = "import"
    USER = "user"
    COMPUTED = "computed"
    DERIVED = "derived"


class ObservationType(StrEnum):
    PRICE = "price"
    OFFER = "offer"
    SELLER_OFFER = "seller_offer"
    DEMAND = "demand"
    RANK = "rank"
    ELIGIBILITY = "eligibility"
    FEE = "fee"
    KEYWORD = "keyword"
    KEYWORD_RANK = "keyword_rank"
    SUPPLIER_PRICE = "supplier_price"


# --- Identity resolution (owner decision 2) -----------------------------------

class IdentityResolution(StrEnum):
    EXISTING_PRODUCT = "existing_product"
    NEW_PRODUCT = "new_product"
    UNRESOLVED_CANDIDATE = "unresolved_candidate"
    IDENTITY_CONFLICT = "identity_conflict"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    PACK_REVIEW_REQUIRED = "pack_review_required"
    VARIATION_REVIEW_REQUIRED = "variation_review_required"


class IdentifierKind(StrEnum):
    ASIN = "asin"
    UPC = "upc"
    EAN = "ean"
    GTIN = "gtin"
    MPN = "mpn"


# --- Jobs (owner decision 4; Phase 1A 06) -------------------------------------

class JobState(StrEnum):
    REQUESTED = "requested"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY_SCHEDULED = "retry_scheduled"
    DEAD_LETTER = "dead_letter"


class FailureClass(StrEnum):
    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    VALIDATION = "validation"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# --- Usage / billing (owner decision 6; shadow mode) --------------------------

class UsageEventStatus(StrEnum):
    PENDING = "pending"
    RESERVED = "reserved"
    FINALIZED = "finalized"
    REVERSED = "reversed"
    ADJUSTED = "adjusted"


class CostKind(StrEnum):
    REPORTED = "reported"
    ESTIMATED = "estimated"
    LOCAL_FREE = "local_free"
    UNKNOWN = "unknown"


# --- Approvals (owner decision 7; Phase 1A 05) --------------------------------

class ApprovalState(StrEnum):
    REQUESTED = "requested"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CapabilitySafetyClass(StrEnum):
    READ = "read"
    DRAFT = "draft"
    WRITE_EXTERNAL = "write_external"
    PURCHASE = "purchase"


# --- Supplier / invoice states (Phase 1B source & invoice safety) -------------

class DocumentationState(StrEnum):
    INVOICE_TYPE_UNKNOWN = "invoice_type_unknown"
    DOCUMENTATION_UNDER_REVIEW = "documentation_under_review"
    INVOICE_CAPABLE = "invoice_capable"
    DOCUMENTATION_REJECTED = "documentation_rejected"
    PURCHASE_AUTHORIZED = "purchase_authorized"  # reserved; disabled in 1B


class SupplyState(StrEnum):
    SUPPLIER_DISCOVERED = "supplier_discovered"
    SUPPLIER_ACCOUNT_AVAILABLE = "supplier_account_available"
    PRODUCT_CARRIED = "product_carried"
    PRICE_OBSERVED = "price_observed"
    PACK_MATCHED = "pack_matched"


# --- Audit --------------------------------------------------------------------

class AuditResult(StrEnum):
    SUCCESS = "success"
    DENIED = "denied"
    FAILURE = "failure"


class ProviderHealth(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    DISABLED = "disabled"
    UNKNOWN = "unknown"