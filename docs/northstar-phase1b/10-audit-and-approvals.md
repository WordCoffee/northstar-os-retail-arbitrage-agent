# 10 — Audit and Approvals (implemented)

## Audit events (owner decision G)

`foundation/audit.py:AuditService.record` captures: actor (user + role), organization,
target organization/user, action, resource type/id, before/after metadata, environment,
view context, approval ref, job/run ref, result, failure class, timestamp.

**Redaction guarantee:** `_scrub()` replaces any key matching
`password|secret|token|api_key|authorization|refresh_token|access_token|credential|
private_key|session` with `[REDACTED]`, recursively. **Secrets are never stored in
audit payloads** (verified by tests).

## Approval foundation (owner decision H)

`foundation/approvals.py:ApprovalService`:

- `request()` — creates an `ApprovalRequest` with capability, safety class, resource,
  change preview, risk level, cost estimate, required approver role, expiry, idempotency.
- `decide()` — only an authorized approver role may decide (rank check). Unauthorized
  attempts are audited as denied. Expired requests are rejected. Double-decide rejected.
- `cancel()`.
- **No external write executes on grant.** The API returns
  `execution: "not_performed_phase_1b"`.

Capability safety classes: `read, draft, write_external, purchase` (owner decision 7).
Required approver for `write_external`/`purchase` = `organization_owner`.

Purchases remain manual and are never executed by the system.

## Evidence

- `foundation/audit.py`, `foundation/approvals.py`
- `foundation/tests/test_audit.py` (3 tests), `foundation/tests/test_approvals.py` (7 tests)