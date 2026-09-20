# Northstar OS — Auth / Tenant / RBAC Contract v1 (B2)

**Contract id:** `auth-rbac/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B2).
**Parents:** [`BFF_CONTRACT_v1.md`](BFF_CONTRACT_v1.md) ·
[`SECURITY_BOUNDARIES_v1.md`](SECURITY_BOUNDARIES_v1.md) · Catalog:
[`shared/subscription-plans.json`](../../shared/subscription-plans.json).
**Phase alignment:** Alpha Build Blueprint Phase B / B2 ("Real auth, tenant
isolation, and role model (owner/operator/member); clean install; tests show
tenant A cannot see tenant B; roles enforced; refresh/expiry; no secrets
hardcoded").

---

## 1. Tenancy model — **single-tenant-per-account**

Each account is exactly one tenant. `tenant_id` **equals the account id**;
there is no cross-account sharing in v1. Multi-tenant organizations (several
workspaces under one billing entity) are **deferred** and would be a `v2`
change. Consequence: tenant isolation reduces to *account isolation* — a
session may only ever read/write its own `tenant_id`.

`tenant_id_of(user)` resolves `tenant_id` (falling back to the account `id`)
and **fails closed** (returns `None`) when neither is present.

## 2. Session / token contract

**Access token** (JWT, HS256) claims:

```jsonc
{
  "sub": "<account_id>",          // subject = account id (= tenant_id)
  "email": "owner@example.com",
  "plan": "scout",                // catalog plan id (entitlement tier)
  "role": "owner",                // member | operator | owner | admin
  "tenant_id": "<account_id>",    // single-tenant-per-account
  "type": "access",
  "jti": "sess_<32 hex>",         // opaque session id (never a secret)
  "iat": 1758300000,
  "exp": 1758303600               // +60 min (ACCESS_TOKEN_EXPIRE_MINUTES)
}
```

**Refresh token** claims: `{ sub, type:"refresh", jti, iat, exp }` (+30 days).
Refresh rotates to a fresh access token; a refresh token is **not** an access
token (`type` must match or the request is `unauthorized`).

**Rules**
- No secret, provider, or cost data is ever a claim. `jti` is opaque
  (`sess_` + 32 hex).
- Unknown/absent `role` → treated as `member` (least privilege), never elevated.
- Tokens are bearer; missing/invalid/expired → BFF `unauthorized` (401).
- Alpha posture: **stub/mock auth state is acceptable** (the demo fallback
  below); a full login UI/session store is Phase C.

## 3. Roles & plan (orthogonal axes)

**Role** = what you may *do* within your tenant. **Plan** = what the tenant is
*entitled* to (from the catalog). Effective capability = **role permission ∩
plan entitlement** — neither alone grants access.

### 3.1 Role hierarchy (tenant)

| Role | Rank | Meaning |
|---|---|---|
| `member` | 0 | Read-only within the tenant (view dashboards/results). |
| `operator` | 1 | `member` + run jobs/exports the plan entitles. |
| `owner` | 2 | `operator` + manage account, plan, and members. |
| `admin` | — | **Platform** role, separate axis (see §3.2). |

`member < operator < owner` is strict. **Unknown roles fail closed**: an
unrecognized role gets rank `-1` and fails every role check.

### 3.2 Admin (least privilege, separate axis)

`admin` is **not** part of the tenant hierarchy. It administers *accounts*,
not tenant product data: an admin may view only **basic account info**
(`id`, `email`, `plan`, `created_at`) and **never** password hashes, tokens,
session ids, gate/live state, or tenant product/market data. `admin` does not
satisfy `owner`/`operator` tenant checks — least privilege by construction.

### 3.3 Plans (entitlement tiers)

Plan order from the catalog: `foundation < scout < mover < autothink`
(`shared/subscription-plans.json`). A plan **entitles** gates; it never flips
one. Plan ids are read from the catalog, never duplicated here.

## 4. Permission matrix (role × BFF v1 surface)

`R` = allowed, `–` = denied (fail closed). Plan column = minimum plan, where a
capability is plan-gated.

| BFF surface (v1) | Public | member | operator | owner | admin | Min plan |
|---|---|---|---|---|---|---|
| Static UI / landing / auth pages | R | R | R | R | R | — |
| `POST /api/v1/auth/{register,login,refresh}` | R | R | R | R | R | — |
| `GET /api/v1/auth/me` | – | R | R | R | R | — |
| `GET /api/v1/plans`, `/plans/{id}` | R | R | R | R | R | — |
| Read dashboards (`GET /api/v1/{service}/…`) | – | R | R | R | – | foundation |
| Create/run jobs (`POST /api/v1/{service}/jobs`) | – | – | R | R | – | scout |
| Exports (`…/jobs/{id}/result` → export) | – | – | R | R | – | scout |
| Manage account/plan/members | – | – | – | R | – | — |
| `GET /api/v1/admin/accounts/{id}` | – | – | – | – | R | — |

**Gate rule:** any row whose plan-gate is not entitled returns BFF
`entitlement_required` (403) — the request is authorized by role but not
entitled by plan. Role failures return `forbidden` (403); missing/invalid
session returns `unauthorized` (401).

## 5. Isolation & enforcement

1. Every authenticated request carries `tenant_id`; data access is scoped to it.
2. Admin cross-account reads are **whitelisted to basic account fields** (§3.2).
3. IDOR protection: opaque ids only (BFF §4); a mismatched `tenant_id` → `not_found`.
4. Mass-assignment protection: role/plan/tenant are derived from the **token**,
   never from request bodies.

## 6. Minimal wiring (this phase)

`auth.py` gains fail-closed helpers (no behavior change to existing calls):
`ROLE_*`, `PLAN_ORDER`, `is_valid_role`, `role_rank`, `is_admin`, `has_role`,
`tenant_id_of`, `plan_rank`, `admin_account_view`. `create_access_token` gains
additive `role`/`tenant_id`/`jti` claims (defaults preserve prior behavior).
`auth_deps.py` gains `require_role(min_role)` and `require_admin`, and
`get_current_user` now surfaces `role`/`tenant_id` (demo fallback =
`member`/`anonymous`). See [`SECURITY_BOUNDARIES_v1.md`](SECURITY_BOUNDARIES_v1.md)
for the enforcement boundary.

---

*Designed Phase B (B2), 2026-09-19. FROZEN for Phase C. No secrets hardcoded.*