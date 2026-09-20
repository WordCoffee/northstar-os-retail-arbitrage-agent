# Northstar OS — Security Boundaries Contract v1 (B4)

**Contract id:** `security-boundaries/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B4).
**Parents:** [`BFF_CONTRACT_v1.md`](BFF_CONTRACT_v1.md) ·
[`AUTH_RBAC_v1.md`](AUTH_RBAC_v1.md) · [`DISCLAIMER_EMBED_v1.md`](DISCLAIMER_EMBED_v1.md).
**Phase alignment:** Alpha Build Blueprint Phase B / B4 ("IDOR-safe API layer,
input validation, basic rate limits, export sanitizer design; threats listed
(IDOR, mass-assignment, path traversal, injection via exports); mitigation
patterns documented; design used later in D1 audit").

---

## 1. Boundary classification (what is public vs protected)

| Surface | Class | Enforcement |
|---|---|---|
| Static UI (`public/`, landing, auth pages) | **Public** | none (edge Access optional) |
| `GET /health` | **Public** | none |
| `POST /api/v1/auth/{register,login,refresh}` | **Public** | rate-limited; validation |
| `GET /api/v1/auth/me` | **Authenticated** | valid access token |
| `GET /api/v1/plans`, `/plans/{id}` | **Public** | read-only catalog |
| `GET /api/v1/{service}/…` (dashboards) | **Authenticated + plan** | token + plan entitlement |
| `POST /api/v1/{service}/jobs` | **Authenticated + role + plan** | `operator`+ and plan gate |
| Exports (`/jobs/{id}/result`, export manifest) | **Authenticated + role + plan** | `operator`+; export sanitizer |
| `GET /api/v1/admin/accounts/{id}` | **Admin (least privilege)** | `admin` role; whitelisted fields |
| Cloudflare Pages Functions `/api/*` | **Edge-gated** | Cloudflare Access in front; envelope no-leak |

**Alpha posture:** the Pages Functions dashboard is protected at the **edge**
(Cloudflare Access) and additionally enforces the **no-leak envelope**; the
FastAPI backend enforces token + role + plan at the app layer. The two layers
are complementary, not redundant.

## 2. No-leak enforcement at the boundary (B1 allowlist)

The BFF §6 deny-list is enforced **at the boundary**, not by convention:

1. **Functions layer** — `functions/api/_envelope.js` emits only generic error
   messages (`internal_error` never includes exception text); responses carry
   only `data` from an allowlisted shape.
2. **Backend layer** — every response is (Phase C) wrapped in the bff/v1
   envelope; error `message` is generic; `details` is validated.
3. **Export layer** — `export_manifest.assert_no_export_leakage()` rejects
   forbidden keys/values (provider names, paths, secrets) before an export is
   written.
4. **Audit** — the D1 no-leak audit scans UI, payloads, exports, and job ids
   against this same deny-list.

Enforcement points already live: `_envelope.js` (B5), `export_manifest.py`
(B7), and the boundary checks below.

## 3. Least-privilege admin — technically enforced (not just documented)

- **Role gate:** `auth_deps.require_admin` rejects any non-`admin` role with
  BFF `forbidden` (403). `admin` is a separate axis from tenant roles, so an
  admin does **not** satisfy `owner`/`operator` checks.
- **Field whitelist:** `auth.admin_account_view()` returns **only**
  `{id, email, plan, created_at}`. Password hashes, tokens, session ids,
  gate/live state, and tenant product data are structurally excluded — the
  endpoint cannot leak them even if called with a valid admin token.
- **IDOR-safe:** admin reads are by opaque account id; unknown id → `not_found`.

## 4. Threat model & mitigations

| Threat | Mitigation |
|---|---|
| **IDOR** (access another tenant's data) | opaque ids only; `tenant_id` from token; mismatched tenant → `not_found` |
| **Mass-assignment** (set role/plan/tenant via body) | role/plan/tenant derived from the token only, never from request bodies |
| **Path traversal** (Functions `data/[filename]`) | `_envelope`-wrapped route validates `*.json` only; KV key is namespaced (`scored:`); no filesystem paths |
| **Injection via exports** | `assert_no_export_leakage` + column allowlist; no formula/CSV-injection-leading characters in Phase C build |
| **Secret/credential exposure** | no secret in any token claim, payload, error, or export; generic error messages |
| **Privilege escalation** | unknown role fails closed to `member`; admin whitelisted; role checks fail closed |
| **Denial of service** | basic rate limits at the edge (Access/WAF) + per-route rate limit (Phase C) |

## 5. Minimal wiring (this phase)

- `auth_deps.require_role(min_role)` and `auth_deps.require_admin` (fail-closed).
- `auth.admin_account_view()` least-privilege whitelist.
- Backend: `GET /api/v1/admin/accounts/{user_id}` guarded by `require_admin`,
  returning only the whitelisted view (demonstrates technical enforcement).
- Functions: verified read-only + envelope-only by the B5 contract test; the
  edge Access boundary is documented in `CLOUDFLARE_DEPLOY.md`.
- Tests: admin 403 for non-admin, admin view field whitelist, tenant/role
  fail-closed, and the no-leak assertions in the functions contract suite.

---

*Designed Phase B (B4), 2026-09-19. FROZEN for Phase C. Enforced at the
boundary, not just documented.*