"""Foundation domain models (dataclasses + pydantic contracts).

Pure data structures. No I/O. Persistence is handled by repositories.py.
Null-first: unknown values are ``None`` and never coerced to 0/"".
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from .enums import (
    Environment, Role, ViewContext, ProvenanceClass, VerificationState,
    StalenessState, SourceKind, ObservationType, IdentityResolution,
    IdentifierKind, JobState, FailureClass, UsageEventStatus, CostKind,
    ApprovalState, RiskLevel, CapabilitySafetyClass, DocumentationState,
    SupplyState, AuditResult, ProviderHealth,
)


def _uuid() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --- Organization / identity --------------------------------------------------

@dataclass
class Organization:
    id: str = field(default_factory=_uuid)
    name: str = ""
    slug: str = ""
    environment: str = Environment.PRODUCTION.value
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class User:
    id: str = field(default_factory=_uuid)
    email: str = ""
    display_name: str = ""
    active: bool = True
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Membership:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    user_id: str = ""
    role: str = Role.VIEWER.value
    status: str = "active"  # active | suspended | revoked
    created_at: datetime = field(default_factory=utcnow)


# --- Marketplace / product identity -------------------------------------------

@dataclass
class Marketplace:
    id: str = field(default_factory=_uuid)
    code: str = "amazon.com"          # marketplace code
    country: str = "US"
    currency: str = "USD"
    domain: str = "www.amazon.com"
    active: bool = True


@dataclass
class CatalogProduct:
    id: str = field(default_factory=_uuid)   # immutable product_id
    marketplace_id: str = ""
    asin: Optional[str] = None
    brand: Optional[str] = None
    canonical_title: Optional[str] = None
    pack_config_id: Optional[str] = None
    variation_family_id: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class ProductIdentifier:
    id: str = field(default_factory=_uuid)
    product_id: str = ""
    kind: str = IdentifierKind.ASIN.value
    raw_value: str = ""
    normalized_value: str = ""
    marketplace_id: Optional[str] = None
    verification_state: str = VerificationState.UNVERIFIED.value
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class PackConfig:
    id: str = field(default_factory=_uuid)
    product_id: Optional[str] = None
    count: Optional[int] = None
    unit: Optional[str] = None
    unit_type: Optional[str] = None
    is_multipack: Optional[bool] = None
    is_bundle: Optional[bool] = None
    verification_state: str = VerificationState.UNVERIFIED.value


@dataclass
class VariationRelationship:
    id: str = field(default_factory=_uuid)
    family_id: str = ""
    child_product_id: str = ""
    axis: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class ProductAlias:
    id: str = field(default_factory=_uuid)
    product_id: str = ""
    alias_value: str = ""
    reason: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class UnresolvedCandidate:
    id: str = field(default_factory=_uuid)
    raw_asin: Optional[str] = None
    raw_title: Optional[str] = None
    raw_identifier: Optional[str] = None
    reason: str = ""
    source: str = SourceKind.PROVIDER.value
    source_identifier: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class IdentityConflict:
    id: str = field(default_factory=_uuid)
    conflict_type: str = ""
    candidate_id: Optional[str] = None
    product_id: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


# --- Provenance / observations ------------------------------------------------

@dataclass
class Observation:
    """Append-only observation envelope (owner decision 3)."""
    id: str = field(default_factory=_uuid)
    product_id: Optional[str] = None
    candidate_id: Optional[str] = None
    marketplace_id: Optional[str] = None
    provider: Optional[str] = None
    provider_record_id: Optional[str] = None
    observation_type: str = ObservationType.PRICE.value
    observed_value: Any = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    captured_at: datetime = field(default_factory=utcnow)
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    confidence: Optional[float] = None
    verification_state: str = VerificationState.UNVERIFIED.value
    provenance_class: str = ProvenanceClass.UNAVAILABLE.value
    raw_source_ref: Optional[str] = None
    transformation_version: Optional[str] = None
    job_run_id: Optional[str] = None
    environment: str = Environment.PRODUCTION.value
    created_at: datetime = field(default_factory=utcnow)


# --- Provider registry --------------------------------------------------------

@dataclass
class ProviderDefinition:
    id: str = field(default_factory=_uuid)
    provider_key: str = ""
    name: str = ""
    category: str = "discovery"
    adapter_module: Optional[str] = None
    read_capable: bool = True
    write_capable: bool = False
    sandbox_supported: bool = True
    credential_ref_names: list[str] = field(default_factory=list)  # names only
    rate_limit_rpm: Optional[int] = None
    timeout_seconds: Optional[int] = None
    cost_model: Optional[dict] = None
    health: str = ProviderHealth.UNKNOWN.value
    enabled: bool = False  # default disabled (owner decision 4/7)


# --- Jobs ---------------------------------------------------------------------

@dataclass
class JobRequest:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    user_id: str = ""
    service: str = ""
    scope_type: Optional[str] = None
    scope_id: Optional[str] = None
    data_types: list[str] = field(default_factory=list)
    provider_policy: Optional[str] = None
    max_estimated_cost: Optional[float] = None
    currency: str = "USD"
    environment: str = Environment.PRODUCTION.value
    idempotency_key: Optional[str] = None
    requires_approval: bool = False
    reason: Optional[str] = None
    priority: int = 5
    created_at: datetime = field(default_factory=utcnow)
    # --- 1C-04 durable execution (additive) ---
    state: str = JobState.REQUESTED.value
    job_type: Optional[str] = None
    payload: Optional[dict] = None
    payload_schema_version: Optional[str] = None
    approval_id: Optional[str] = None
    provider_class: Optional[str] = None
    budget_class: Optional[str] = None
    estimated_cost: Optional[Decimal] = None
    parent_job_id: Optional[str] = None
    correlation_id: Optional[str] = None
    provenance: Optional[dict] = None


@dataclass
class JobRun:
    id: str = field(default_factory=_uuid)
    job_request_id: str = ""
    state: str = JobState.REQUESTED.value
    run_id: str = field(default_factory=_uuid)
    attempts: int = 0
    max_attempts: int = 3
    failure_class: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)
    # --- 1C-04 durable execution (additive) ---
    priority: int = 5
    reserved_cost: Optional[Decimal] = None
    actual_cost: Optional[Decimal] = None
    scheduled_time: Optional[datetime] = None
    heartbeat_time: Optional[datetime] = None
    lease_owner: Optional[str] = None
    lease_expiration: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    parent_job_id: Optional[str] = None
    correlation_id: Optional[str] = None
    output_reference: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None
    cancellation_state: Optional[str] = None


@dataclass
class JobStateHistory:
    """Append-only transition evidence (1C-04/B01)."""
    id: str = field(default_factory=_uuid)
    job_id: str = ""
    run_id: Optional[str] = None
    previous_state: str = ""
    new_state: str = ""
    actor: str = ""
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    audit_event_ref: Optional[str] = None
    occurred_at: datetime = field(default_factory=utcnow)


@dataclass
class JobSchedule:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    owner_user_id: str = ""
    job_template: dict = field(default_factory=dict)
    timezone: str = "UTC"
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    enabled: bool = False  # provider-backed schedules default disabled
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    concurrency_policy: dict = field(default_factory=dict)
    misfire_policy: str = "skip"
    approval_policy: dict = field(default_factory=dict)
    budget_policy: dict = field(default_factory=dict)
    provider_policy: dict = field(default_factory=dict)
    failure_policy: dict = field(default_factory=dict)
    version: str = "schedule-1.0.0"
    archived: bool = False
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class ScheduleOccurrence:
    id: str = field(default_factory=_uuid)
    schedule_id: str = ""
    occurrence_key: str = ""
    scheduled_for: Optional[datetime] = None
    enqueued_job_request_id: Optional[str] = None
    state: str = "created"
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class OrgBalance:
    """Org-level usage ledger counters (1C-04/B09).

    ``granted`` is the credited allowance; ``reserved`` and ``consumed`` are
    denormalized counters updated atomically so concurrent reservations cannot
    overspend. Decimal/NUMERIC throughout.
    """
    organization_id: str = ""
    granted: Decimal = Decimal("0.00")
    reserved: Decimal = Decimal("0.00")
    consumed: Decimal = Decimal("0.00")
    updated_at: datetime = field(default_factory=utcnow)

    @property
    def available(self) -> Decimal:
        return self.granted - self.reserved - self.consumed


# --- 1C-05 keyword & SEO intelligence (additive) -----------------------------

@dataclass
class Keyword:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    normalized_phrase: str = ""
    original_phrase: str = ""
    marketplace: str = "amazon.com"
    language: str = "en"
    match_type: str = "broad"          # broad | phrase | exact | negative
    brand_terms: list[str] = field(default_factory=list)
    confidence: Optional[float] = None
    freshness_state: str = StalenessState.UNKNOWN_AGE.value
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SearchTerm:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    raw_term: str = ""
    normalized_term: str = ""
    marketplace: str = "amazon.com"
    search_volume: Optional[int] = None     # null = unknown (never 0)
    observed_volume: Optional[int] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    spend: Optional[Decimal] = None
    orders: Optional[int] = None
    revenue: Optional[Decimal] = None
    source: str = "import"
    observed_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Target:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    keyword_id: str = ""
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    match_type: str = "broad"
    bid: Optional[Decimal] = None
    status: str = "active"
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class KeywordLink:
    """Product/listing/campaign/ad-group/competitor/brand relationship."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    keyword_id: str = ""
    link_kind: str = "product"           # product|listing|campaign|ad_group|competitor|brand
    target_ref: Optional[str] = None
    asin: Optional[str] = None
    product_id: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class ImportBatch:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    source_file_id: Optional[str] = None
    status: str = "created"              # created|dry_run|running|completed|cancelled|failed
    submitted_by: Optional[str] = None
    submitted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SourceFile:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    file_name: str = ""
    file_sha256: str = ""
    file_size: int = 0
    marketplace: Optional[str] = None
    currency: Optional[str] = None
    report_type: Optional[str] = None     # search_term|campaign|placement|targeting|business|keyword_workbook|unknown
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: str = "registered"           # registered|validated|imported|duplicate|rejected
    registered_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SourceRow:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    import_batch_id: str = ""
    source_file_id: Optional[str] = None
    row_index: int = 0
    row_json: dict = field(default_factory=dict)
    status: str = "accepted"             # accepted|rejected
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class RejectedRow:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    import_batch_id: str = ""
    source_file_id: Optional[str] = None
    row_index: int = 0
    row_json: dict = field(default_factory=dict)
    rejection_reason: str = ""
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class NormalizationDecision:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    original_phrase: str = ""
    normalized_phrase: str = ""
    rule: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class RankObservation:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    keyword_id: str = ""
    asin: Optional[str] = None
    rank: Optional[int] = None            # null = unknown (never 0)
    placement: str = "organic"           # organic | sponsored
    observed_at: Optional[datetime] = None
    source: str = "import"
    confidence: Optional[float] = None
    freshness_state: str = StalenessState.UNKNOWN_AGE.value
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class AdPerformanceObservation:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    search_term_id: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    impressions: Optional[int] = None
    clicks: Optional[int] = None
    spend: Optional[Decimal] = None
    orders: Optional[int] = None
    revenue: Optional[Decimal] = None
    ctr: Optional[float] = None
    cvr: Optional[float] = None
    observed_at: Optional[datetime] = None
    source: str = "import"
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class KeywordConflict:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    keyword_id_a: str = ""
    keyword_id_b: str = ""
    conflict_type: str = ""              # duplicate|overlap|ambiguous|other
    detail: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


# --- 1C-06 Lean B2B beta launch controls (additive) -------------------------

@dataclass
class LegalDocument:
    """Versioned, published legal/beta document (Privacy Notice, ToS, AUP)."""
    id: str = field(default_factory=_uuid)
    doc_type: str = ""                    # privacy_notice|terms_of_service|acceptable_use_policy
    version: str = ""
    title: str = ""
    content_hash: str = ""
    status: str = "draft"                 # draft|published
    published_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class AcceptanceEvent:
    """Append-only record of a user accepting a specific document version."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    user_id: str = ""
    doc_type: str = ""
    doc_version: str = ""
    content_hash: str = ""
    business_use_attested: bool = False
    age_18_attested: bool = False
    ip_handling: str = "not_stored"       # consistent with the data inventory
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    accepted_at: datetime = field(default_factory=utcnow)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class AccountAcceptance:
    """Current acceptance pointer per (organization, user) — fast deny check.
    The append-only acceptance_events remain the source of truth."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    user_id: str = ""
    privacy_notice_version: Optional[str] = None
    terms_of_service_version: Optional[str] = None
    acceptable_use_policy_version: Optional[str] = None
    private_beta_addendum_version: Optional[str] = None
    business_attested: bool = False
    age_18_attested: bool = False
    updated_at: datetime = field(default_factory=utcnow)


# --- 1C-06 master slice: private beta readiness (additive) ------------------

@dataclass
class BillingCustomer:
    """Processor customer reference — ID ONLY, never card data."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    processor: str = "test"
    processor_customer_id: str = ""
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class CheckoutSession:
    """Redirect-based hosted checkout intent (test-mode). No card fields."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    price_id: str = ""
    tier: str = ""
    status: str = "open"                # open|completed|expired|canceled
    expires_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Subscription:
    """Processor subscription reference — IDs + status only."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    billing_customer_id: str = ""
    processor_subscription_id: str = ""
    price_id: str = ""
    tier: str = ""
    status: str = "incomplete"          # trialing|active|canceled|unpaid|past_due|incomplete
    current_period_end: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class BillingEvent:
    """Append-only, exactly-once webhook event record (keyed on processor id)."""
    id: str = field(default_factory=_uuid)
    processor_event_id: str = ""
    event_type: str = ""
    payload_hash: str = ""
    status: str = "processed"           # processed|failed
    processed_at: datetime = field(default_factory=utcnow)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class Invite:
    """Admin-managed invite / approved-email allowlist (invite-gated access)."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    invite_code: str = ""
    email: str = ""
    role: str = ""
    status: str = "pending"             # pending|used|revoked|expired
    created_by: Optional[str] = None
    expires_at: Optional[datetime] = None
    used_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class OrgEntitlement:
    """Materialized per-org entitlement flags (centralized enforcement)."""
    organization_id: str = ""
    tier: str = "free"
    max_jobs_per_month: int = 1000
    export_enabled: bool = False
    advanced_reports: bool = False
    seat_limit: int = 10
    updated_at: datetime = field(default_factory=utcnow)


# --- 1C-06 master slice: private beta operations (additive) ------------------

@dataclass
class OrgLifecycle:
    organization_id: str = ""
    state: str = "active"
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class OrgLifecycleEvent:
    """Append-only lifecycle transition record."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    actor_user_id: Optional[str] = None
    previous_state: str = ""
    new_state: str = ""
    reason: str = ""
    correlation_id: Optional[str] = None
    occurred_at: datetime = field(default_factory=utcnow)
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class OrgAdminNote:
    """INTERNAL admin annotation — never visible to external testers."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    author_user_id: Optional[str] = None
    note: str = ""
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class EntitlementOverride:
    """Temporary entitlement override with reason, actor, scope, expiry."""
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    feature: str = ""
    value_text: Optional[str] = None
    value_int: Optional[int] = None
    reason: str = ""
    created_by: Optional[str] = None
    scope: str = "org"
    expires_at: Optional[datetime] = None
    permanent: bool = False
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SupportTicket:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    reference_id: str = ""
    reporter_user_id: Optional[str] = None
    category: str = "other"
    severity: str = "low"
    subject: str = ""
    description: str = ""
    status: str = "new"
    assignee_user_id: Optional[str] = None
    internal_note: Optional[str] = None
    tester_visible_note: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class Onboarding:
    organization_id: str = ""
    checklist: dict = field(default_factory=dict)
    completed: bool = False
    completed_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=utcnow)


# --- Usage --------------------------------------------------------------------

@dataclass
class UsageEvent:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    user_id: Optional[str] = None
    service: str = ""
    workflow_run_id: Optional[str] = None
    provider: Optional[str] = None
    model_or_endpoint: Optional[str] = None
    input_units: Optional[int] = None
    output_units: Optional[int] = None
    provider_reported_cost: Optional[float] = None
    estimated_cost: Optional[float] = None
    credits_debited_shadow: Optional[float] = None
    cost_kind: str = CostKind.UNKNOWN.value
    status: str = UsageEventStatus.PENDING.value
    idempotency_key: Optional[str] = None
    reversal_ref: Optional[str] = None
    environment: str = Environment.PRODUCTION.value
    occurred_at: datetime = field(default_factory=utcnow)
    provenance: Optional[dict] = None


@dataclass
class PricingPolicy:
    version: str = "shadow-0"
    platform_markup: float = 0.0
    minimum_charge: float = 0.0
    service_multipliers: dict = field(default_factory=dict)
    free_local_execution: bool = True
    failed_run_charge: bool = False  # shadow: never charge failed runs by default


# --- Audit --------------------------------------------------------------------

@dataclass
class AuditEvent:
    id: str = field(default_factory=_uuid)
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    organization_id: Optional[str] = None
    target_organization_id: Optional[str] = None
    target_user_id: Optional[str] = None
    action: str = ""
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    before_meta: Optional[dict] = None
    after_meta: Optional[dict] = None
    environment: str = Environment.PRODUCTION.value
    view_context: str = ViewContext.NORMAL.value
    approval_ref: Optional[str] = None
    job_run_ref: Optional[str] = None
    result: str = AuditResult.SUCCESS.value
    failure_class: Optional[str] = None
    correlation_id: Optional[str] = None
    occurred_at: datetime = field(default_factory=utcnow)


# --- Approvals ----------------------------------------------------------------

@dataclass
class ApprovalRequest:
    id: str = field(default_factory=_uuid)
    organization_id: str = ""
    requested_by_user_id: str = ""
    capability: str = ""
    safety_class: str = CapabilitySafetyClass.WRITE_EXTERNAL.value
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    change_preview: Optional[dict] = None
    risk_level: str = RiskLevel.MEDIUM.value
    cost_estimate: Optional[float] = None
    currency: str = "USD"
    state: str = ApprovalState.REQUESTED.value
    required_approver_role: str = Role.ORGANIZATION_OWNER.value
    expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    execution_ref: Optional[str] = None
    environment: str = Environment.PRODUCTION.value
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class ApprovalDecision:
    id: str = field(default_factory=_uuid)
    approval_request_id: str = ""
    decided_by_user_id: str = ""
    decided_by_role: Optional[str] = None
    decision: str = ApprovalState.GRANTED.value
    note: Optional[str] = None
    decided_at: datetime = field(default_factory=utcnow)


# --- Supplier / documentation -------------------------------------------------

@dataclass
class Supplier:
    id: str = field(default_factory=_uuid)
    name: str = ""
    supplier_class: Optional[str] = None
    public_catalog_url: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


@dataclass
class SupplierProductDocumentation:
    id: str = field(default_factory=_uuid)
    supplier_id: str = ""
    product_id: Optional[str] = None
    supply_state: str = SupplyState.SUPPLIER_DISCOVERED.value
    documentation_state: str = DocumentationState.INVOICE_TYPE_UNKNOWN.value
    note: Optional[str] = None
    created_at: datetime = field(default_factory=utcnow)


# --- UI preferences -----------------------------------------------------------

@dataclass
class UiPreference:
    user_id: str = ""
    organization_id: Optional[str] = None
    key: str = ""
    value: dict = field(default_factory=dict)
    updated_at: datetime = field(default_factory=utcnow)


# --- Pydantic API contracts (typed request/response) --------------------------

class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    request_id: Optional[str] = None


class ProvenanceMeta(BaseModel):
    provenance_class: str = ProvenanceClass.UNAVAILABLE.value
    source: Optional[str] = None
    source_identifier: Optional[str] = None
    captured_at: Optional[datetime] = None
    confidence: Optional[float] = None
    verification_state: str = VerificationState.UNVERIFIED.value
    staleness_state: str = StalenessState.UNKNOWN_AGE.value


class UserContextResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    organizations: list[dict]
    active_organization_id: Optional[str] = None
    role: Optional[str] = None
    environment: str
    view_context: str
    permissions: list[str]


class PreviewStartRequest(BaseModel):
    target_organization_id: str
    target_role: Optional[str] = None
    reason: str


class PreviewSessionResponse(BaseModel):
    preview_id: str
    actor_user_id: str
    target_organization_id: str
    target_role: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    reason: str
    read_only: bool = True
    active: bool = True