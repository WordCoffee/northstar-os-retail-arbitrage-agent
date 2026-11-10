"""Internal data inventory (1C-06).

Every collected field with purpose, sensitivity, source, storage location,
access roles, vendor/subprocessor, retention period, deletion mechanism, and
whether it is optional. Data minimization: only fields needed for beta
identity, authentication, organization access, support, billing metadata, or
platform security are collected.

Where a retention value is genuinely unknown it is EXPLICITLY marked
"UNKNOWN" — never assumed.
"""
from __future__ import annotations

from typing import Optional

# retention period (ISO-8601 duration) or "UNKNOWN" or "LIFETIME_OF_ACCOUNT"
R = "retention"

FIELDS = [
    {
        "field": "user.id",
        "purpose": "beta identity + primary key",
        "sensitivity": "internal", "source": "system_generated",
        "storage": "foundation db (sqlite/pg)", "access_roles": "owner/admin/operator",
        "vendor_subprocessor": None, R: "LIFETIME_OF_ACCOUNT",
        "deletion_mechanism": "account deletion request", "optional": False,
    },
    {
        "field": "user.email",
        "purpose": "authentication + support contact",
        "sensitivity": "pii", "source": "operator_provisioned",
        "storage": "foundation db (sqlite/pg)", "access_roles": "owner/admin/operator",
        "vendor_subprocessor": None, R: "LIFETIME_OF_ACCOUNT",
        "deletion_mechanism": "account deletion request (masked on delete)",
        "optional": False,
    },
    {
        "field": "organization.id/name/slug",
        "purpose": "organization access + tenant scoping",
        "sensitivity": "internal", "source": "operator_provisioned",
        "storage": "foundation db", "access_roles": "owner/admin/operator",
        "vendor_subprocessor": None, R: "LIFETIME_OF_ACCOUNT",
        "deletion_mechanism": "account deletion request", "optional": False,
    },
    {
        "field": "membership.role/status",
        "purpose": "authorization (owner/operator/viewer matrix)",
        "sensitivity": "internal", "source": "operator_provisioned",
        "storage": "foundation db", "access_roles": "owner/admin",
        "vendor_subprocessor": None, R: "LIFETIME_OF_ACCOUNT",
        "deletion_mechanism": "membership revocation + deletion request",
        "optional": False,
    },
    {
        "field": "session.jti (revocation registry)",
        "purpose": "session invalidation",
        "sensitivity": "internal", "source": "system_generated",
        "storage": "foundation db", "access_roles": "owner/admin/operator (self)",
        "vendor_subprocessor": None, R: "30 days after expiry",
        "deletion_mechanism": "scheduled cleanup job", "optional": False,
    },
    {
        "field": "audit_events (actor, action, resource, correlation_id)",
        "purpose": "platform security + incident attribution",
        "sensitivity": "internal", "source": "system_generated",
        "storage": "foundation db", "access_roles": "owner/admin/operator (view_audit)",
        "vendor_subprocessor": None, R: "7 years (financial/audit record)",
        "deletion_mechanism": "none during legal retention; reviewed after",
        "optional": False,
    },
    {
        "field": "acceptance_events (doc_type, version, hash, attestations)",
        "purpose": "beta acceptance + regulatory-style record",
        "sensitivity": "internal", "source": "user_action",
        "storage": "foundation db", "access_roles": "owner/admin",
        "vendor_subprocessor": None, R: "7 years (audit record)",
        "deletion_mechanism": "append-only; no routine deletion",
        "optional": False,
    },
    {
        "field": "ip_handling",
        "purpose": "consistent with data inventory (raw IPs NOT stored)",
        "sensitivity": "internal", "source": "policy",
        "storage": "not stored (constant 'not_stored')", "access_roles": "n/a",
        "vendor_subprocessor": None, R: "n/a",
        "deletion_mechanism": "n/a", "optional": True,
    },
    {
        "field": "job_requests payload + runs + usage/ledger",
        "purpose": "operate permitted research jobs; billing metadata",
        "sensitivity": "confidential", "source": "user_action / system",
        "storage": "foundation db", "access_roles": "owner/admin/operator",
        "vendor_subprocessor": None, R: "UNKNOWN (business data; reviewed with "
        "customer at contract)", "deletion_mechanism": "customer deletion request",
        "optional": False,
    },
    {
        "field": "keyword/search-term/import data",
        "purpose": "research intelligence (local/imported only)",
        "sensitivity": "confidential", "source": "user import / system",
        "storage": "foundation db", "access_roles": "owner/admin/operator",
        "vendor_subprocessor": None, R: "UNKNOWN",
        "deletion_mechanism": "customer deletion request", "optional": True,
    },
]

_SOURCE_OF_TRUTH_NOTE = (
    "The runtime system collects exactly the fields above. If a retention "
    "value is marked UNKNOWN it is a genuine unknown, stated explicitly — it "
    "is never assumed or silently defaulted."
)


def inventory() -> dict:
    return {"fields": FIELDS, "note": _SOURCE_OF_TRUTH_NOTE}


def completeness_review() -> dict:
    """Data-minimization + completeness review evidence."""
    issues = []
    for f in FIELDS:
        for key in ("purpose", "sensitivity", "source", "storage",
                    "access_roles", "vendor_subprocessor", "retention",
                    "deletion_mechanism", "optional"):
            if key not in f:
                issues.append(f"{f['field']}:missing_{key}")
    unknown_retentions = [f["field"] for f in FIELDS
                          if f["retention"] == "UNKNOWN"]
    return {
        "field_count": len(FIELDS),
        "issues": issues,
        "complete": not issues,
        "unknown_retention_explicit": unknown_retentions,
        "data_minimization_note": "only identity/auth/org/support/billing-metadata/"
                                  "security fields are collected",
    }