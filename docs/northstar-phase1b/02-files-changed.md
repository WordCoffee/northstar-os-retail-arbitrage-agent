# 02 — Files Changed

## Production files ADDED (new)

| Path | Purpose |
|---|---|
| `Northstar_backend/foundation/__init__.py` | package marker, schema version |
| `Northstar_backend/foundation/enums.py` | canonical vocabulary (modes, provenance, identity, jobs, usage, approvals, docs) |
| `Northstar_backend/foundation/models.py` | dataclasses + pydantic contracts |
| `Northstar_backend/foundation/db.py` | SQLite store + additive DDL + Postgres DDL generator |
| `Northstar_backend/foundation/repositories.py` | per-aggregate repositories |
| `Northstar_backend/foundation/provenance.py` | observation envelope, freshness, null-first |
| `Northstar_backend/foundation/context.py` | request/preview context (3 modes) |
| `Northstar_backend/foundation/permissions.py` | server-side RBAC evaluation |
| `Northstar_backend/foundation/identity.py` | identity resolution service |
| `Northstar_backend/foundation/providers.py` | provider registry, adapter contract, fixture adapter |
| `Northstar_backend/foundation/jobs.py` | job request/run state machine |
| `Northstar_backend/foundation/usage.py` | append-only usage + shadow pricing |
| `Northstar_backend/foundation/audit.py` | audit events + redaction |
| `Northstar_backend/foundation/approvals.py` | approval policy/request/decision |
| `Northstar_backend/foundation/observability.py` | ids, redacting logger, timed events |
| `Northstar_backend/foundation/app.py` | standalone app factory (tests / optional mount) |
| `Northstar_backend/foundation/api/__init__.py` | api package |
| `Northstar_backend/foundation/api/state.py` | dependency container + reference seed |
| `Northstar_backend/foundation/api/deps.py` | context extraction (dev shim) |
| `Northstar_backend/foundation/api/router.py` | 32 API routes |
| `Northstar_backend/foundation/tests/**` | 9 test modules (74 tests) |
| `Northstar_backend/migrations_foundation/001_foundation.sql` | additive Postgres DDL (NOT applied) |
| `Northstar_backend/tools/foundation_migrate_dryrun.py` | read-only migration dry-run tool |
| `northstar-os-ui/src/foundation/api.js` | foundation API client |
| `northstar-os-ui/src/foundation/flags.js` | feature flags |
| `northstar-os-ui/src/foundation/session.jsx` | session provider (org/role/env/preview) |
| `northstar-os-ui/src/foundation/HelpTour.jsx` | help/tour registry + overlay |
| `northstar-os-ui/src/foundation/foundation.css` | shell styles |
| `northstar-os-ui/src/foundation/components/*.jsx` | EnvBadge, PreviewBanner, OrgSelector, StatusPrimitives, PinnedDrawer, CommandPalette, Notifications, RouteGuard |
| `northstar-os-ui/src/foundation/pages/FoundationStatus.jsx` | internal foundation page (consumes real APIs) |

## Production files MODIFIED (additive, reviewable)

| Path | Change | Risk |
|---|---|---|
| `Northstar_backend/main.py` | appended a defensive `include_router` block mounting `/api/v1/foundation/*` | LOW — wrapped in try/except; existing routes untouched; compiles |
| `northstar-os-ui/src/App.jsx` | wrapped Shell in `SessionProvider`; added env badge/org/palette/notifications; replaced right rail with collapsible `PinnedDrawer`; added `/foundation` route | LOW — additive; build passes |
| `northstar-os-ui/src/main.jsx` | imported `foundation.css` | LOW |
| `northstar-os-ui/src/components/Header.jsx` | accept + render `rightSlot` | LOW |
| `northstar-os-ui/src/components/Sidebar.jsx` | role-aware filtering via `useSession`/`hasPerm` | LOW |
| `northstar-os-ui/src/components/Icon.jsx` | added `sync`, `clock`, `lock`, `bell` icons | LOW |
| `northstar-os-ui/src/data/services.js` | added Internal → Foundation nav item | LOW |

## Untouched (explicitly)

`AGENTS.md`, `docs/OPERATING_CONSTITUTION.md`, `docs/northstar-discovery/**`,
`docs/northstar-phase1/**`, `Northstar_backend/data/northstar.db`, `migrations/*.sql`,
and all existing service pages.

## Rollback boundaries

- Foundation is self-contained; removing `Northstar_backend/foundation/` and the
  appended `main.py` block fully reverts the backend foundation.
- Frontend: reverting the 6 additive edits + removing `src/foundation/` reverts the shell.
- No schema change is applied, so there is no data rollback required.