# Legacy Identity Bridge Plan (1C-01F — design; NOT implemented)

**Status:** BLOCKING DECISION — the mapping contract is not yet clear enough to
implement safely. No automated backfill is performed.

## Problem

Authentication tokens are currently issued by `Northstar_backend/auth.py` for users in
the legacy `users` table (SQLite `northstar.db`). The foundation resolves roles from its
own `memberships` table keyed by foundation `users.id`. There is **no bridge** yet, so a
legacy user has no foundation membership and therefore no foundation access (fail-closed).

## Proposed bridge (for owner approval)

1. **Stable subject mapping.** Map a legacy user to a foundation subject by a stable,
   immutable key. Preferred: reuse the legacy `users.id` (a stable hash of email) as the
   foundation `users.id`, and record the legacy id as a `product_alias`-style alias /
   migration reference.
2. **No email-only matching** unless explicitly approved and verified (email can change
   or be reassigned).
3. **Org mapping.** Map legacy `tenant_id` (single-tenant-per-account = the account id)
   to a foundation `organizations` row; avoid creating duplicate organizations.
4. **Conflicts.** Duplicate/ambiguous identities are recorded (unresolved candidate /
   identity conflict), never silently merged.
5. **Idempotent + dry-run.** The bridge must support `--dry-run` producing counts
   (mapped / unresolved / conflict) with no writes and no sensitive output.
6. **Rollback.** Compensating delete of bridge-created rows; legacy tables never dropped.
7. **No automatic elevation.** Ambiguous legacy data never grants owner/admin roles
   automatically; the initial owner is provisioned only via `foundation.bootstrap`.

## Unresolved fields requiring owner decision (blocking)

| # | Question |
|---|---|
| B1 | Is legacy `users.id` (sha256(email)[:16]) the approved stable subject, or is an external IdP required? |
| B2 | How is legacy `tenant_id` mapped when it equals the account id (1:1 org per user)? Is that the intended org model? |
| B3 | May email be used as a *verification* signal (not a key) during the one-time bridge? |
| B4 | Are there legacy accounts whose email changed, or duplicates, requiring quarantine? |
| B5 | Which role(s) migrate as-is vs require re-grant by the owner? |

## Until resolved

- The bridge stays unimplemented; foundation access requires an explicit
  `foundation.bootstrap` membership (no silent bridging).
- This is recorded as a risk (`1C-R1`) and a Phase 1D candidate.