# 12 — Security and Permissions

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). No secret values read; env names only.

## 1. Distinguish the concepts

| Concept | Status | Evidence |
|---|---|---|
| **Authentication** (prove identity) | Implemented: JWT (HS256), bcrypt, access 60m + refresh 30d, jti session ids | `auth.py:31-34,151-208` |
| **Authorization** (what can they do) | Roles member/operator/owner/admin (admin separate axis); `require_role`/`require_admin` fail-closed; only 4 admin-gated routes + 3 user-gated routes at dependency level; otherwise layered via plan-aware rate-limit + alpha gate | `auth_deps.py:86-114`; route list in `03` |
| **Organization tenancy** | `tenant_id` embedded in tokens (`auth.py:131`); `admin_account_view` returns whitelisted fields only (`auth.py:139`) | S |
| **Admin role** | `require_admin` 403 unless role==admin (`auth_deps.py:103-114`) | S |
| **Operator role** | exists in role set (`auth.py:88-96`) but no operator-specific gating found beyond member checks | S |
| **Customer role** | `member` is the base customer role; `foundation` plan default | S |
| **Environment mode** | **MISSING** — no runtime sandbox/production selector; only `ENVIRONMENT` env used by rate-limit prod guard and config | S |
| **Sandbox mode** | **MISSING** in app code (only §3.4 prose + standing-approval template + test harnesses reference sandbox) | S |
| **Production mode** | Partial: `ENVIRONMENT=production` blocks disabling rate limiter (`rate_limiter.py:22-46`, PROD_POSTURE.md) | S |
| **Customer-view preview** | **MISSING** | S |
| **True impersonation** | **MISSING** — no route takes a target-user parameter; grep found no `impersonat/preview_mode/as_user/on_behalf_of` | S |

## 2. Auth details (STATICALLY CONFIRMED)

- JWT secret: `NORTHSTAR_JWT_SECRET` env, else ephemeral random hex (`auth.py:31`) — note: ephemeral secret means tokens invalidate on restart.
- Password: bcrypt `hash_password`/`verify_password` (`auth.py:151-158`).
- Anonymous demo fallback: no token → `is_demo=True`, foundation/member (`auth_deps.py:39-48`). App runs open by default.
- Plan enforcement: `require_plan(minimum)` factory (foundation<scout<mover<autothink) (`auth_deps.py:117-136`).

## 3. Alpha gate (`alpha_gate.py`)

- `NORTHSTAR_PRIVATE_ALPHA=1` + `NORTHSTAR_ALPHA_ALLOWLIST`; empty allowlist fails closed (`:115-116`); public prefixes allow auth/plans/legal/static shells (`:28-46`); `decide()` deterministic.

## 4. Rate limiting (`rate_limiter.py`)

- In-memory token bucket; plan limits 30/60/120/300 req/min (`:52-57`); client by IP (X-Forwarded-For); 429 + X-RateLimit-* headers; prod-posture guard raises at startup if disabled in production.
- In-memory → resets on restart (not multi-worker safe).

## 5. Security headers (`security.py`)

- nosniff, X-Frame-Options SAMEORIGIN, X-XSS-Protection, Referrer-Policy, Permissions-Policy, Cache-Control no-store, X-Request-ID; tracing X-Request-ID + X-Response-Time; CORS from `CORS_ORIGINS` (default localhost:8000/3000).

## 6. "Authorization Posture" in the UI — real checks or presentation?

- **Mostly presentation.** Gate pills render from `/api/v1/models` (`cloud.live_armed`, `key_present`) and from env-driven gate flags. There is no route that returns a per-gate authorization decision; the Account "Authorization Posture" badges in the SIGNAL SPA toggle toasts locally (S). Real enforcement lives in backend gates (env flags) + §3 policy, not in these badges.

## 7. Frontend credential scan (S)

- **No hardcoded credentials found in frontend JS** (`static/**`, `northstar-os-ui/src/**`, `src/**`, `public/**`, `components/**`).
- Non-frontend literals flagged for awareness: `tools/browser_agent.py:102` (local placeholder), `tools/test_chrome.py:30,40` (hardcoded test email/password — credential-hygiene concern), `data/costco-costs.json:5,34` (env-read, no literal).
- Open issue `credential_exposure_in_test_failure_diff` (`00_STATE.json:161-166`): DataForSEO captures credentials at import time; a unittest diff previously rendered real values; transport flag now false (H, OPEN). Recommend lazy config reads.

## 8. Audit logging

- Three channels: gateway JSONL (`shared/master-brain/audit.log.jsonl`), `audit_log` table (8 rows), `live_pulls` table (3 rows). No unified audit search/UI. Actions logged are limited (gateway + provider pulls); arbitrary CRUD on products/suppliers is NOT audited end-to-end (S).

## 9. Customer-view system design (PROPOSAL — not implemented in Phase 0)

A future customer-view/impersonation must NOT be a visual toggle. Required characteristics:

- Preserve the operator's real identity (separate `acting_user_id` + `viewing_user_id`).
- Record target organization/user context (tenant scope).
- Persistent, un-dismissable preview banner.
- Block production writes while previewing (route-level guard).
- Audit entry/exit and every action (`audit_log`).
- Reauthorization for sensitive actions (re-prompt operator password/token).
- Never weaken the authorization model to enable preview.

## 10. Counting methods

- Env names: regex scan of modules; values never read. Route/dependency protection: grep of `Depends(` across main.py (see `17` §E).
