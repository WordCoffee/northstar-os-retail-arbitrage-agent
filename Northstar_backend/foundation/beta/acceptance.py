"""Mandatory, versioned beta acceptance (1C-06).

Every user must accept the current published Terms, Privacy Notice, and
Acceptable Use Policy, attest to business use, and attest to being 18+ before
authenticated feature use. Acceptance events are APPEND-ONLY and persisted
with doc type, version, content hash, timestamp, actor ID, organization ID,
IP handling (consistent with the data inventory), and request/correlation ID.

Enforcement is driven by the PUBLISHED document set: if no documents are
published, enforcement is inactive (pre-launch/dev state). Once documents are
published, feature access is denied (409 acceptance_required) until the actor
has accepted the current versions.
"""
from __future__ import annotations

from typing import Optional

from ..audit import AuditService
from ..context import RequestContext
from ..models import AcceptanceEvent, AccountAcceptance, LegalDocument, utcnow
from ..repositories import Repositories
from . import documents as beta_docs

IP_HANDLING = "not_stored"  # consistent with the data inventory


class AcceptanceError(RuntimeError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def publish_documents(state) -> dict:
    """Publish the current beta document set (idempotent per doc_type/version)."""
    published = []
    for doc_type, spec in beta_docs.document_versions().items():
        existing = state.repos.legal_documents.current(doc_type)
        if existing and existing["version"] == spec["version"]:
            published.append(existing)
            continue
        row = LegalDocument(
            doc_type=doc_type, version=spec["version"], title=spec["title"],
            content_hash=spec["content_hash"], status="published",
            published_at=utcnow())
        published.append(state.repos.legal_documents.add(row))
    return [{"doc_type": d["doc_type"], "version": d["version"],
             "content_hash": d["content_hash"]} for d in published]


def published_documents(state) -> list[dict]:
    return state.repos.legal_documents.published()


def enforcement_active(state) -> bool:
    return bool(published_documents(state))


def _required_versions(state) -> dict:
    required = {}
    for d in published_documents(state):
        required[d["doc_type"]] = d["version"]
    return required


def acceptance_status(state, ctx: RequestContext) -> dict:
    """What is required vs what the actor has accepted (deny-check helper)."""
    required = _required_versions(state)
    current = None
    if ctx.user_id and ctx.effective_organization_id:
        current = state.repos.account_acceptance.current(
            ctx.effective_organization_id, ctx.user_id)
    missing = []
    for doc_type, version in required.items():
        accepted = current and current.get(f"{doc_type}_version") == version
        if not accepted:
            missing.append(doc_type)
    ok = (not required) or (
        bool(current) and not missing
        and bool(current.get("business_attested"))
        and bool(current.get("age_18_attested")))
    return {
        "enforcement_active": bool(required),
        "required_documents": {k: v for k, v in required.items()},
        "missing_documents": missing,
        "business_use_attested": bool(current and current.get("business_attested")),
        "age_18_attested": bool(current and current.get("age_18_attested")),
        "accepted": ok,
    }


def record_acceptance(state, ctx: RequestContext, *, business_use: bool,
                      age_18_plus: bool,
                      request_id: Optional[str] = None) -> dict:
    """Record acceptance for the current published versions. Idempotent when a
    current acceptance already matches."""
    if not ctx.user_id or not ctx.effective_organization_id:
        raise AcceptanceError("no_org_or_actor",
                              "an authenticated organization context is required")
    if not business_use:
        raise AcceptanceError("business_use_required",
                              "business-use attestation is required")
    if not age_18_plus:
        raise AcceptanceError("age_18_required",
                              "an 18+ attestation is required")
    required = _required_versions(state)
    if not required:
        raise AcceptanceError("no_published_documents",
                              "no documents are published; nothing to accept")
    org_id = ctx.effective_organization_id
    user_id = ctx.user_id

    current = state.repos.account_acceptance.current(org_id, user_id)
    already = (current is not None
               and all(current.get(f"{dt}_version") == v for dt, v in required.items())
               and bool(current.get("business_attested"))
               and bool(current.get("age_18_attested")))
    if already:
        return {"status": "already_accepted"}

    # append-only events (source of truth)
    for doc_type, version in required.items():
        doc = state.repos.legal_documents.by_version(doc_type, version)
        event = AcceptanceEvent(
            organization_id=org_id, user_id=user_id, doc_type=doc_type,
            doc_version=version, content_hash=doc["content_hash"] if doc else "",
            business_use_attested=business_use, age_18_attested=age_18_plus,
            ip_handling=IP_HANDLING, request_id=request_id,
            correlation_id=ctx.request_id)
        state.repos.acceptance_events.add(event)
    # current pointer (fast deny check)
    fields = {"organization_id": org_id, "user_id": user_id,
              "business_attested": business_use, "age_18_attested": age_18_plus,
              "updated_at": utcnow()}
    for dt, v in required.items():
        fields[f"{dt}_version"] = v
    if current:
        sets = ", ".join(f"{k}=?" for k in fields)
        state.db.conn.execute(
            f"UPDATE account_acceptance SET {sets} WHERE organization_id=? AND user_id=?",
            list(fields.values()) + [org_id, user_id])
        state.db.conn.commit()
    else:
        acc = AccountAcceptance(id=__import__("uuid").uuid4().hex, **fields)
        state.repos.account_acceptance.add(acc)

    audit = AuditService(state.repos)
    for doc_type, version in required.items():
        audit.record(
            action="legal.acceptance", actor_user_id=user_id,
            actor_role=ctx.effective_role, organization_id=org_id,
            resource_type="legal_document", resource_id=doc_type,
            correlation_id=ctx.request_id,
            after_meta={"doc_type": doc_type, "version": version,
                        "business_use": business_use, "age_18_plus": age_18_plus,
                        "ip_handling": IP_HANDLING})
    return {"status": "accepted", "documents": sorted(required)}


def enforce(state, ctx: RequestContext) -> None:
    """Raise AcceptanceError('acceptance_required') when the actor has not
    accepted the current published documents. No-op when enforcement is
    inactive (nothing published)."""
    if not enforcement_active(state):
        return
    if not ctx.user_id or not ctx.effective_organization_id:
        return  # authn handled elsewhere
    status = acceptance_status(state, ctx)
    if not status["accepted"]:
        raise AcceptanceError(
            "acceptance_required",
            "current beta documents must be accepted before continued use")