# Write-Path Authorization Map (non-creative admin/operator surface)

**Status:** design + scoped activations. **Five actions are ACTIVATED**
(owner-approved, platform-admin only): **Issue invite**, **Revoke invite**,
**Suspend organization**, **Resume organization**, and the read-only
**Dashboard export CSV**. Every other classified action remains disabled;
activation of any further action requires explicit owner approval.

**Scope:** Beta-Ops / Admin / Support / Audit / account write surfaces outside the
creative-media cluster.

**Classification key:**
- **SAFE LOCAL ENABLE NOW** — non-destructive, audited, platform/organization-scoped; safe to enable locally.
- **ENABLE LATER WITH OWNER APPROVAL** — real backend route exists; enable only on explicit owner activation.
- **REQUIRE PER-EVENT OWNER CONFIRMATION** — high-risk; each execution must be individually approved.
- **KEEP DISABLED** — irreversible/terminal; do not enable without a separate owner decision.
- **OUT OF SCOPE / MISSING BACKEND (or UI)** — no route or no surface; design later.

---

## 1. Invites

| Action | UI state | Backend route | Permission | Audit | Risk | Classification | Required on activation |
|---|---|---|---|---|---|---|---|
| Issue invite | **ACTIVATED — "Issue Invitation" (platform-admin only)** | `POST /api/v1/foundation/invites` | `PERM_MANAGE_ORG` | `invite.issue` (email domain only) | Medium (grants future access) | **ACTIVATED (owner-approved)** | confirmation checkbox required; invite code shown once to the issuing admin; list refresh; honest 401/403/400/no-org states |
| Reissue invite | disabled "Reissue Invitation" | **none** (compose revoke + issue) | — | — | Medium | OUT OF SCOPE / MISSING BACKEND | add route (or compose) before enabling |
| Revoke invite | **ACTIVATED — "Revoke Invitation" (platform-admin only)** | `POST /api/v1/foundation/invites/{id}/revoke` | `PERM_MANAGE_ORG` | `invite.revoke` (with reason) | Medium (revokes pending access) | **ACTIVATED (owner-approved)** | confirmation checkbox + reason; UI guards used/revoked (backend does not pre-check); detail + list refresh; honest 401/403/404 states |

## 2. Organization lifecycle

Validated transition matrix (`foundation/operations/lifecycle.py`); every
transition is append-only audited (`org_lifecycle_events` + audit) with actor,
previous→new state, reason, correlation id. Blocking states set `active=false`
so the **next authenticated request is blocked**.

| Action | UI state | Backend route | Risk | Classification |
|---|---|---|---|---|
| Grant / activate | disabled "Verify Eligibility" | `POST /admin/orgs/{id}/grant` | High (access grant) | ENABLE LATER WITH OWNER APPROVAL |
| Change plan | no UI | `POST /admin/orgs/{id}/plan` | Medium | ENABLE LATER WITH OWNER APPROVAL |
| Suspend | **ACTIVATED — OrgDetail (platform-admin only)** | `POST /admin/orgs/{id}/suspend` | High (blocks access) | **ACTIVATED (owner-approved)** — confirmation + reason; append-only audit `org.lifecycle.suspended`; eligible from onboarding/active/paused/downgraded |
| Resume | **ACTIVATED — OrgDetail (platform-admin only)** | `POST /admin/orgs/{id}/resume` | Low–Med (restore) | **ACTIVATED (owner-approved)** — confirmation + reason; audit `org.lifecycle.active`; restores access only (not plan/entitlements); eligible from suspended/paused |
| Downgrade | disabled (select) | `POST /admin/orgs/{id}/downgrade` | High | REQUIRE PER-EVENT OWNER CONFIRMATION |
| Cancel | disabled (select) | `POST /admin/orgs/{id}/cancel` | High (near-terminal) | REQUIRE PER-EVENT OWNER CONFIRMATION |
| Archive | no UI | `POST /admin/orgs/{id}/archive` | High (terminal) | KEEP DISABLED |

## 3. Entitlements / notes / support

| Action | UI state | Backend route | Permission | Audit | Risk | Classification |
|---|---|---|---|---|---|---|
| Entitlement override | no UI | `POST /admin/orgs/{id}/override` | `PERM_PLATFORM_ADMIN` | `admin.override.set` | Medium | REQUIRE PER-EVENT OWNER CONFIRMATION |
| Add internal note | absent (draft only this pass) | `POST /admin/orgs/{id}/notes` | `PERM_PLATFORM_ADMIN` | `admin.note.add` | Low (non-destructive, internal-only) | SAFE LOCAL ENABLE NOW (draft-only implemented) |
| Support triage write | absent | `POST /support/tickets/{id}/triage` | `PERM_PLATFORM_ADMIN` | support audit | Medium | OUT OF SCOPE / MISSING UI |

## 4. Export / reports

| Action | UI state | Backend route | Permission | Risk | Classification |
|---|---|---|---|---|---|
| Dashboard export CSV | **ACTIVATED — "Download CSV" (platform-admin only)** | `GET /admin/dashboard/export` | `PERM_PLATFORM_ADMIN` | Low–Med (safe field set; hard-excludes secrets/tokens/card/credentials) | **ACTIVATED (owner-approved; read-only, no audit event)** |
| Sample report downloads | disabled | none (sample) | — | None | OUT OF SCOPE / SAMPLE |

Safe export field set: `organization_id, organization_name, lifecycle_state,
plan_tier, subscription_status, invite_status, acceptance_complete,
onboarding_complete, monthly_jobs_used, max_jobs_per_month, seats_used,
seat_limit, open_tickets, blocker_tickets, last_activity, flags`.
Excluded tokens (hard-fail): `secret, token, password, card, credential,
provider_key, api_key`.

## 5. Approval mechanism (existing)

`POST /api/v1/foundation/approvals` (`PERM_DRAFT`), `/approvals/{id}/decide`
(`PERM_APPROVE`), `/cancel` (`PERM_APPROVE`) already provide the auditable
approval workflow (execution is out of scope: `not_performed_phase_1b`). This is
the **recommended path** for any per-event-confirmation action. Approving records
a grant + audit event; it does not execute an external write.

## 6. Rules

1. Least privilege first: `PERM_MANAGE_ORG` for org-scoped invite actions;
   `PERM_PLATFORM_ADMIN` for cross-org/lifecycle/export.
2. No hidden or silent state changes — every enabled write must emit an audit
   event and return a clear success/error state.
3. No destructive action without explicit confirmation + a recorded reason.
4. No surface may appear more live than it is; disabled actions state the real
   route, permission, audit, and the reason they are disabled.
5. Activation of any ENABLE-LATER or PER-EVENT action requires explicit owner
   approval (owner gate), not merely the existence of a backend route.
