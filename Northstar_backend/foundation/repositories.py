"""Repository interfaces over FoundationDB.

Each repository owns one aggregate and exposes create/get/list/count. Repositories
never call providers and never touch external systems.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from .db import FoundationDB


class BaseRepo:
    table: str = ""

    def __init__(self, db: FoundationDB) -> None:
        self.db = db

    def add(self, obj) -> dict:
        row = asdict(obj)
        self.db.insert(self.table, row)
        if "id" in row:
            return self.db.get(self.table, {"id": row["id"]}) or row
        return row

    def add_idempotent(self, obj, pk_cols=("id",)) -> dict:
        row = asdict(obj)
        key = {k: row[k] for k in pk_cols}
        existing = self.db.get(self.table, key)
        if existing:
            return existing
        # also dedupe on idempotency_key when present and set
        idem = row.get("idempotency_key")
        if idem:
            found = self.db.get(self.table, {"idempotency_key": idem})
            if found:
                return found
        self.db.insert(self.table, row)
        if "id" in row:
            return self.db.get(self.table, {"id": row["id"]}) or row
        return row

    def get(self, id_: str) -> Optional[dict]:
        return self.db.get(self.table, {"id": id_})

    def find(self, where: dict) -> Optional[dict]:
        rows = self.db.list(self.table, where=where, limit=1)
        return rows[0] if rows else None

    def list(self, where: Optional[dict] = None, order_by: Optional[str] = None,
             limit: Optional[int] = None, offset: int = 0) -> list[dict]:
        return self.db.list(self.table, where=where, order_by=order_by,
                            limit=limit, offset=offset)

    def count(self) -> int:
        return self.db.count(self.table)


class OrganizationRepo(BaseRepo):
    table = "organizations"


class UserRepo(BaseRepo):
    table = "users"


class MembershipRepo(BaseRepo):
    table = "memberships"

    def for_user(self, user_id: str) -> list[dict]:
        return self.list(where={"user_id": user_id})

    def for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id})


class MarketplaceRepo(BaseRepo):
    table = "marketplaces"

    def by_code(self, code: str) -> Optional[dict]:
        return self.find({"code": code})


class CatalogProductRepo(BaseRepo):
    table = "catalog_products"

    def by_marketplace_asin(self, marketplace_id: str, asin: str) -> list[dict]:
        return self.list(where={"marketplace_id": marketplace_id, "asin": asin})


class ProductIdentifierRepo(BaseRepo):
    table = "product_identifiers"

    def by_normalized(self, kind: str, normalized_value: str) -> list[dict]:
        return self.list(where={"kind": kind, "normalized_value": normalized_value})


class PackConfigRepo(BaseRepo):
    table = "pack_configs"


class VariationRelationshipRepo(BaseRepo):
    table = "variation_relationships"


class ProductAliasRepo(BaseRepo):
    table = "product_aliases"


class UnresolvedCandidateRepo(BaseRepo):
    table = "unresolved_candidates"


class IdentityConflictRepo(BaseRepo):
    table = "identity_conflicts"


class ObservationRepo(BaseRepo):
    table = "observations"

    def for_product(self, product_id: str, obs_type: Optional[str] = None) -> list[dict]:
        where = {"product_id": product_id}
        if obs_type:
            where["observation_type"] = obs_type
        return self.list(where=where, order_by="captured_at")


class ProviderRepo(BaseRepo):
    table = "providers"

    def by_key(self, provider_key: str) -> Optional[dict]:
        return self.find({"provider_key": provider_key})


class JobRequestRepo(BaseRepo):
    table = "job_requests"


class JobRunRepo(BaseRepo):
    table = "job_runs"

    def by_request(self, job_request_id: str) -> list[dict]:
        return self.list(where={"job_request_id": job_request_id})


class JobStateHistoryRepo(BaseRepo):
    """Append-only transition evidence (1C-04/B01)."""
    table = "job_state_history"

    def for_job(self, job_id: str, limit: int = 500) -> list[dict]:
        return self.list(where={"job_id": job_id},
                         order_by="occurred_at DESC", limit=limit)

    def for_run(self, run_id: str) -> list[dict]:
        return self.list(where={"run_id": run_id}, order_by="occurred_at ASC")


class JobScheduleRepo(BaseRepo):
    table = "job_schedules"

    def for_org(self, org_id: str, *, include_archived: bool = False) -> list[dict]:
        if include_archived:
            return self.list(where={"organization_id": org_id},
                             order_by="created_at DESC")
        rows = self.list(where={"organization_id": org_id},
                         order_by="created_at DESC")
        return [r for r in rows if not r.get("archived")]

    def due(self, before: str) -> list[dict]:
        """Enabled, non-archived schedules with next_run_at <= before.

        Filtering in Python keeps identical semantics on SQLite (ISO TEXT) and
        PostgreSQL (TIMESTAMPTZ normalized to ISO string by the backend)."""
        rows = self.list(order_by="next_run_at ASC")
        return [r for r in rows
                if r.get("enabled") and not r.get("archived")
                and (r.get("next_run_at") or "") <= before]

    def by_org(self, org_id: str, schedule_id: str) -> Optional[dict]:
        return self.find({"organization_id": org_id, "id": schedule_id})


class ScheduleOccurrenceRepo(BaseRepo):
    table = "schedule_occurrences"

    def by_key(self, schedule_id: str, occurrence_key: str) -> Optional[dict]:
        return self.find({"schedule_id": schedule_id, "occurrence_key": occurrence_key})


class OrgBalanceRepo(BaseRepo):
    table = "org_balances"

    def get(self, id_: str) -> Optional[dict]:
        return self.db.get(self.table, {"organization_id": id_})


# --- 1C-05 keyword & SEO repositories (additive) -----------------------------

class KeywordRepo(BaseRepo):
    table = "keywords"

    def by_phrase(self, org_id: str, normalized_phrase: str, match_type: str,
                  marketplace: str) -> Optional[dict]:
        return self.find({"organization_id": org_id,
                          "normalized_phrase": normalized_phrase,
                          "match_type": match_type, "marketplace": marketplace})


class SearchTermRepo(BaseRepo):
    table = "search_terms"

    def by_term(self, org_id: str, normalized_term: str,
                marketplace: str) -> Optional[dict]:
        return self.find({"organization_id": org_id,
                          "normalized_term": normalized_term,
                          "marketplace": marketplace})


class TargetRepo(BaseRepo):
    table = "targets"


class KeywordLinkRepo(BaseRepo):
    table = "keyword_links"


class ImportBatchRepo(BaseRepo):
    table = "import_batches"

    def for_org(self, org_id: str, limit: int = 100) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="created_at DESC", limit=limit)


class SourceFileRepo(BaseRepo):
    table = "source_files"

    def by_sha(self, org_id: str, file_sha256: str) -> Optional[dict]:
        return self.find({"organization_id": org_id, "file_sha256": file_sha256})


class SourceRowRepo(BaseRepo):
    table = "source_rows"

    def for_batch(self, import_batch_id: str) -> list[dict]:
        return self.list(where={"import_batch_id": import_batch_id})


class RejectedRowRepo(BaseRepo):
    table = "rejected_rows"

    def for_batch(self, import_batch_id: str) -> list[dict]:
        return self.list(where={"import_batch_id": import_batch_id})


class NormalizationDecisionRepo(BaseRepo):
    table = "normalization_decisions"


class RankObservationRepo(BaseRepo):
    table = "rank_observations"

    def for_keyword(self, org_id: str, keyword_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id, "keyword_id": keyword_id},
                         order_by="observed_at ASC")


class AdPerformanceObservationRepo(BaseRepo):
    table = "ad_performance_observations"

    def for_org(self, org_id: str, limit: int = 500) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="observed_at DESC", limit=limit)


class KeywordConflictRepo(BaseRepo):
    table = "keyword_conflicts"


class LegalDocumentRepo(BaseRepo):
    table = "legal_documents"

    def published(self) -> list[dict]:
        rows = self.list(where={"status": "published"}, order_by="published_at DESC")
        # one row per doc_type (latest published version)
        latest = {}
        for r in rows:
            latest.setdefault(r["doc_type"], r)
        return list(latest.values())

    def current(self, doc_type: str) -> Optional[dict]:
        rows = self.list(where={"doc_type": doc_type, "status": "published"},
                         order_by="published_at DESC")
        return rows[0] if rows else None

    def by_version(self, doc_type: str, version: str) -> Optional[dict]:
        return self.find({"doc_type": doc_type, "version": version})


class AcceptanceEventRepo(BaseRepo):
    table = "acceptance_events"

    def for_actor(self, org_id: str, user_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id, "user_id": user_id},
                         order_by="accepted_at ASC")


class AccountAcceptanceRepo(BaseRepo):
    table = "account_acceptance"

    def current(self, org_id: str, user_id: str) -> Optional[dict]:
        return self.find({"organization_id": org_id, "user_id": user_id})


class BillingCustomerRepo(BaseRepo):
    table = "billing_customers"

    def for_org(self, org_id: str) -> Optional[dict]:
        return self.find({"organization_id": org_id})


class CheckoutSessionRepo(BaseRepo):
    table = "checkout_sessions"


class SubscriptionRepo(BaseRepo):
    table = "subscriptions"

    def active_for_org(self, org_id: str) -> Optional[dict]:
        rows = self.list(where={"organization_id": org_id},
                         order_by="created_at DESC")
        for r in rows:
            if r["status"] in ("trialing", "active"):
                return r
        return None

    def by_processor_id(self, processor_subscription_id: str) -> Optional[dict]:
        return self.find({"processor_subscription_id": processor_subscription_id})


class BillingEventRepo(BaseRepo):
    table = "billing_events"

    def by_processor_event_id(self, processor_event_id: str) -> Optional[dict]:
        return self.find({"processor_event_id": processor_event_id})


class InviteRepo(BaseRepo):
    table = "invites"

    def by_code(self, invite_code: str) -> Optional[dict]:
        return self.find({"invite_code": invite_code})

    def by_email(self, org_id: str, email: str) -> Optional[dict]:
        return self.find({"organization_id": org_id, "email": email})


class OrgEntitlementRepo(BaseRepo):
    table = "org_entitlements"

    def get(self, id_: str) -> Optional[dict]:
        return self.db.get(self.table, {"organization_id": id_})


class OrgLifecycleRepo(BaseRepo):
    table = "org_lifecycle"

    def get(self, id_: str) -> Optional[dict]:
        return self.db.get(self.table, {"organization_id": id_})


class OrgLifecycleEventRepo(BaseRepo):
    table = "org_lifecycle_events"

    def for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="occurred_at ASC")


class OrgAdminNoteRepo(BaseRepo):
    table = "org_admin_notes"

    def for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="created_at DESC")


class EntitlementOverrideRepo(BaseRepo):
    table = "entitlement_overrides"

    def active(self, org_id: str) -> list[dict]:
        rows = self.list(where={"organization_id": org_id},
                         order_by="created_at DESC")
        return [r for r in rows
                if r.get("permanent") or not r.get("expires_at")
                or str(r["expires_at"]) >= _now()]


def _now() -> str:
    from .models import utcnow
    return utcnow().isoformat()


class SupportTicketRepo(BaseRepo):
    table = "support_tickets"

    def for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="created_at DESC")

    def by_reference(self, reference_id: str) -> Optional[dict]:
        return self.find({"reference_id": reference_id})


class OnboardingRepo(BaseRepo):
    table = "onboarding"

    def get(self, id_: str) -> Optional[dict]:
        return self.db.get(self.table, {"organization_id": id_})


class UsageRepo(BaseRepo):
    table = "usage_events"

    def for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id})


class PricingPolicyRepo(BaseRepo):
    table = "pricing_policies"

    def latest(self) -> Optional[dict]:
        rows = self.list(order_by="version DESC", limit=1)
        return rows[0] if rows else None


class AuditRepo(BaseRepo):
    table = "audit_events"

    def for_org(self, org_id: str, limit: int = 100) -> list[dict]:
        return self.list(where={"organization_id": org_id},
                         order_by="occurred_at DESC", limit=limit)


class ApprovalRepo(BaseRepo):
    table = "approval_requests"

    def pending_for_org(self, org_id: str) -> list[dict]:
        return self.list(where={"organization_id": org_id, "state": "requested"})


class ApprovalDecisionRepo(BaseRepo):
    table = "approval_decisions"


class PreviewSessionRepo(BaseRepo):
    table = "preview_sessions"

    def active_for_actor(self, actor_user_id: str) -> Optional[dict]:
        rows = self.db.list("preview_sessions",
                            where={"actor_user_id": actor_user_id, "active": 1},
                            limit=1)
        return rows[0] if rows else None


class SupplierRepo(BaseRepo):
    table = "suppliers"


class SupplierDocRepo(BaseRepo):
    table = "supplier_documentation"


class SessionRepo(BaseRepo):
    """Server-side session records for JWT revocation (Phase 1C-01).

    Primary key is ``jti`` (not ``id``). A token is revoked when its session row
    has a non-null ``revoked_at``.
    """
    table = "sessions"

    def by_jti(self, jti: str) -> Optional[dict]:
        return self.db.get("sessions", {"jti": jti})

    def is_revoked(self, jti: str) -> bool:
        row = self.by_jti(jti)
        return bool(row and row.get("revoked_at"))

    def register(self, jti: str, user_id: str, organization_id: Optional[str] = None,
                 expires_at: Optional[str] = None) -> dict:
        from datetime import datetime, timezone
        existing = self.by_jti(jti)
        if existing:
            return existing
        # Idempotent at the DB level: concurrent registrations of the same jti
        # must not collide on the PK (PostgreSQL ON CONFLICT / SQLite OR IGNORE).
        self.db.insert_ignore("sessions", {
            "jti": jti, "user_id": user_id, "organization_id": organization_id,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at, "revoked_at": None, "revoked_reason": None,
        }, conflict_cols=("jti",))
        return self.by_jti(jti)

    def revoke(self, jti: str, reason: str = "revoked") -> Optional[dict]:
        from datetime import datetime, timezone
        self.db.conn.execute(
            "UPDATE sessions SET revoked_at=?, revoked_reason=? WHERE jti=?",
            (datetime.now(timezone.utc).isoformat(), reason, jti))
        self.db.conn.commit()
        return self.by_jti(jti)


class UiPreferenceRepo(BaseRepo):
    table = "ui_preferences"

    def get_pref(self, user_id: str, org_id: Optional[str], key: str):
        row = self.db.get("ui_preferences",
                          {"user_id": user_id,
                           "organization_id": org_id if org_id is not None else "",
                           "key": key})
        if not row:
            return None
        value = row["value"]
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                return value
        return value

    def set_pref(self, user_id: str, org_id: Optional[str], key: str, value) -> None:
        import json
        from datetime import datetime, timezone
        self.db.upsert("ui_preferences", {
            "user_id": user_id,
            "organization_id": org_id if org_id is not None else "",
            "key": key,
            "value": json.dumps(value) if not isinstance(value, str) else value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, pk_cols=("user_id", "organization_id", "key"))


class Repositories:
    """Aggregate accessor so services depend on one object."""

    def __init__(self, db: FoundationDB) -> None:
        self.db = db
        self.organizations = OrganizationRepo(db)
        self.users = UserRepo(db)
        self.memberships = MembershipRepo(db)
        self.marketplaces = MarketplaceRepo(db)
        self.products = CatalogProductRepo(db)
        self.identifiers = ProductIdentifierRepo(db)
        self.pack_configs = PackConfigRepo(db)
        self.variations = VariationRelationshipRepo(db)
        self.aliases = ProductAliasRepo(db)
        self.candidates = UnresolvedCandidateRepo(db)
        self.conflicts = IdentityConflictRepo(db)
        self.observations = ObservationRepo(db)
        self.providers = ProviderRepo(db)
        self.job_requests = JobRequestRepo(db)
        self.job_runs = JobRunRepo(db)
        self.job_state_history = JobStateHistoryRepo(db)
        self.job_schedules = JobScheduleRepo(db)
        self.schedule_occurrences = ScheduleOccurrenceRepo(db)
        self.org_balances = OrgBalanceRepo(db)
        self.keywords = KeywordRepo(db)
        self.search_terms = SearchTermRepo(db)
        self.targets = TargetRepo(db)
        self.keyword_links = KeywordLinkRepo(db)
        self.import_batches = ImportBatchRepo(db)
        self.source_files = SourceFileRepo(db)
        self.source_rows = SourceRowRepo(db)
        self.rejected_rows = RejectedRowRepo(db)
        self.normalization_decisions = NormalizationDecisionRepo(db)
        self.rank_observations = RankObservationRepo(db)
        self.ad_perf = AdPerformanceObservationRepo(db)
        self.keyword_conflicts = KeywordConflictRepo(db)
        self.legal_documents = LegalDocumentRepo(db)
        self.acceptance_events = AcceptanceEventRepo(db)
        self.account_acceptance = AccountAcceptanceRepo(db)
        self.billing_customers = BillingCustomerRepo(db)
        self.checkout_sessions = CheckoutSessionRepo(db)
        self.subscriptions = SubscriptionRepo(db)
        self.billing_events = BillingEventRepo(db)
        self.invites = InviteRepo(db)
        self.org_entitlements = OrgEntitlementRepo(db)
        self.org_lifecycle = OrgLifecycleRepo(db)
        self.org_lifecycle_events = OrgLifecycleEventRepo(db)
        self.org_admin_notes = OrgAdminNoteRepo(db)
        self.entitlement_overrides = EntitlementOverrideRepo(db)
        self.support_tickets = SupportTicketRepo(db)
        self.onboarding = OnboardingRepo(db)
        self.usage = UsageRepo(db)
        self.pricing = PricingPolicyRepo(db)
        self.audit = AuditRepo(db)
        self.approvals = ApprovalRepo(db)
        self.approval_decisions = ApprovalDecisionRepo(db)
        self.preview_sessions = PreviewSessionRepo(db)
        self.sessions = SessionRepo(db)
        self.suppliers = SupplierRepo(db)
        self.supplier_docs = SupplierDocRepo(db)
        self.ui_prefs = UiPreferenceRepo(db)