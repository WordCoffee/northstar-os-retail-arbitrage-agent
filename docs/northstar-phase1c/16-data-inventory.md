# 16 — Internal Data Inventory (1C-06 beta)

Every collected field with purpose, sensitivity, source, storage, access roles, subprocessors, retention, deletion mechanism, and optionality. Data minimization: only fields needed for beta identity, authentication, organization access, support, billing metadata, or platform security are collected. Where retention is genuinely unknown it is explicitly marked UNKNOWN — never assumed.

| Field | Purpose | Sensitivity | Source | Storage | Access roles | Vendor/subprocessor | Retention | Deletion | Optional |
|---|---|---|---|---|---|---|---|---|---|
| user.id | beta identity + primary key | internal | system_generated | foundation db (sqlite/pg) | owner/admin/operator | — | LIFETIME_OF_ACCOUNT | account deletion request | False |
| user.email | authentication + support contact | pii | operator_provisioned | foundation db (sqlite/pg) | owner/admin/operator | — | LIFETIME_OF_ACCOUNT | account deletion request (masked on delete) | False |
| organization.id/name/slug | organization access + tenant scoping | internal | operator_provisioned | foundation db | owner/admin/operator | — | LIFETIME_OF_ACCOUNT | account deletion request | False |
| membership.role/status | authorization (owner/operator/viewer matrix) | internal | operator_provisioned | foundation db | owner/admin | — | LIFETIME_OF_ACCOUNT | membership revocation + deletion request | False |
| session.jti (revocation registry) | session invalidation | internal | system_generated | foundation db | owner/admin/operator (self) | — | 30 days after expiry | scheduled cleanup job | False |
| audit_events (actor, action, resource, correlation_id) | platform security + incident attribution | internal | system_generated | foundation db | owner/admin/operator (view_audit) | — | 7 years (financial/audit record) | none during legal retention; reviewed after | False |
| acceptance_events (doc_type, version, hash, attestations) | beta acceptance + regulatory-style record | internal | user_action | foundation db | owner/admin | — | 7 years (audit record) | append-only; no routine deletion | False |
| ip_handling | consistent with data inventory (raw IPs NOT stored) | internal | policy | not stored (constant 'not_stored') | n/a | — | n/a | n/a | True |
| job_requests payload + runs + usage/ledger | operate permitted research jobs; billing metadata | confidential | user_action / system | foundation db | owner/admin/operator | — | UNKNOWN (business data; reviewed with customer at contract) | customer deletion request | False |
| keyword/search-term/import data | research intelligence (local/imported only) | confidential | user import / system | foundation db | owner/admin/operator | — | UNKNOWN | customer deletion request | True |

The runtime system collects exactly the fields above. If a retention value is marked UNKNOWN it is a genuine unknown, stated explicitly — it is never assumed or silently defaulted.
