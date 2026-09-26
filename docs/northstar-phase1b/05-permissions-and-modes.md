# 05 — Permissions and Modes (implemented)

## Three orthogonal dimensions (owner decision 5)

| Dimension | Values | Where enforced |
|---|---|---|
| ENVIRONMENT | `sandbox` \| `production` | `context.RequestContext.is_sandbox`; `permissions.evaluate` |
| ROLE | `organization_owner` \| `organization_admin` \| `operator` \| `analyst` \| `viewer` \| `internal_platform_admin` | `permissions._ROLE_PERMISSIONS` |
| VIEW CONTEXT | `normal` \| `audited_customer_preview` | `context.build_context` (set from active preview) |

## Permission strings

`view, draft, run_local, request_refresh, approve, manage_team, manage_org, view_audit,
preview, write_external, purchase, platform_admin`.

Role → permission matrix is the single source of truth in `foundation/permissions.py`
and is exposed read-only at `GET /api/v1/foundation/roles`.

## Enforcement (server-side)

- `permissions.evaluate(ctx, permission)` returns `(allowed, reason)`.
- Guards applied in every route via `_require(ctx, permission)` → HTTP 403 with a
  stable error envelope.
- **Verified live**: a `viewer` calling `POST /identity/submit` received `http 403`;
  an `operator` succeeded.

## Preview guarantees (implemented)

- `PreviewContext` preserves the real actor identity (`actor_user_id`) and records the
  target org/role; `read_only=True` by default.
- `RequestContext.effective_role = min(real_role, target_role)` — **preview can never
  elevate** (verified by unit test).
- `RequestContext.allow_write()` returns `False` while previewing → `write_external` and
  `purchase` are blocked (`preview_read_only`).
- Entry/exit actions are written to the audit log.
- **No identity impersonation** is implemented (per owner decision).
- Persistent, non-dismissable banner rendered by `PreviewBanner.jsx`.

## Environment guard

- `evaluate` blocks `write_external` when `is_sandbox` → `sandbox_blocks_external_write`.

## What is deliberately NOT enabled

- No `write_external` or `purchase` **execution** path exists in Phase 1B. Those
  permissions gate *approval requests* only; nothing executes them.