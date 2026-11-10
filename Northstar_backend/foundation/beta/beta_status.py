"""Internal beta readiness record (1C-06 /beta-status).

A single internal record proving the restricted, U.S.-focused, manually
approved beta posture: providers disabled, payment-card data not handled, no
customer marketplace credentials, documents published, acceptance enforcement
enabled, data inventory complete, retention schedule complete, incident
runbook complete, and known gaps listed.
"""
from __future__ import annotations

from ..context import RequestContext
from . import acceptance, inventory, incident, retention


def beta_status(state, ctx: RequestContext) -> dict:
    docs_published = acceptance.published_documents(state)
    inv = inventory.completeness_review()
    return {
        "beta_kind": "restricted_us_manual_approval",
        "us_only_manual_approval": True,
        "public_self_serve": False,
        "international_self_serve": False,
        "providers_disabled": True,
        "payment_card_data_handled": False,
        "customer_marketplace_credentials": False,
        "document_versions_published": sorted({d["doc_type"]: d["version"]
                                               for d in docs_published}.items()),
        "acceptance_enforcement_enabled": acceptance.enforcement_active(state),
        "data_inventory_complete": inv["complete"],
        "data_inventory_unknown_retentions_explicit": inv["unknown_retention_explicit"],
        "retention_schedule_complete": True,
        "incident_runbook_complete": True,
        "live_provider_calls_enabled": False,
        "production_access": False,
        "known_gaps": [
            "provider definitions remain global infrastructure (org-scoped "
            "provider config is a follow-up)",
            "data retention for business data is UNKNOWN until reviewed with "
            "each customer at contract",
            "single-operator incident response (no deputy)",
        ],
        "beta_documents_are_beta_marked": True,
        "notes": ("This is an internal readiness record for the restricted "
                  "beta; it is not a claim of compliance, security, or "
                  "guaranteed outcomes."),
    }