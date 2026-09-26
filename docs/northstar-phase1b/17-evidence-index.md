# 17 — Evidence Index

## Files of record (Phase 1B)

### Backend foundation
- `Northstar_backend/foundation/enums.py` — canonical vocabulary.
- `Northstar_backend/foundation/models.py` — dataclasses + pydantic contracts.
- `Northstar_backend/foundation/db.py` — SQLite store, `SQLITE_DDL`, `postgres_ddl()`.
- `Northstar_backend/foundation/repositories.py` — repositories (`BaseRepo.add` returns persisted row).
- `Northstar_backend/foundation/identity.py` — `IdentityResolver.submit`, `normalize_asin`, `valid_asin`.
- `Northstar_backend/foundation/permissions.py` — `_ROLE_PERMISSIONS`, `evaluate`, `require`.
- `Northstar_backend/foundation/context.py` — `RequestContext`, `PreviewContext`, `build_context`.
- `Northstar_backend/foundation/provenance.py` — `make_observation`, `classify_staleness`, `is_current_fact`.
- `Northstar_backend/foundation/providers.py` — `ProviderRegistry`, `FixtureAdapter`, `execute_read/write`.
- `Northstar_backend/foundation/jobs.py` — `JobOrchestrator`, `_ALLOWED_TRANSITIONS`, `execute_fixture`.
- `Northstar_backend/foundation/usage.py` — `UsageLedger`, `shadow_charge`, `derived_balance`, `reverse`.
- `Northstar_backend/foundation/audit.py` — `AuditService`, `_scrub`.
- `Northstar_backend/foundation/approvals.py` — `ApprovalService`, `_REQUIRED_APPROVER`.
- `Northstar_backend/foundation/observability.py` — `FoundationLogger`, `redact`, `timed`.
- `Northstar_backend/foundation/api/{state,deps,router}.py` — state container, context deps, 32 routes.
- `Northstar_backend/foundation/app.py` — standalone app factory (lifespan).

### Migration & tooling
- `Northstar_backend/migrations_foundation/001_foundation.sql` — additive Postgres DDL (NOT APPLIED).
- `Northstar_backend/tools/foundation_migrate_dryrun.py` — read-only reconciliation tool.

### Frontend foundation
- `northstar-os-ui/src/foundation/{api.js,flags.js,session.jsx,HelpTour.jsx,foundation.css}`
- `northstar-os-ui/src/foundation/components/*.jsx`
- `northstar-os-ui/src/foundation/pages/FoundationStatus.jsx`
- Modified: `northstar-os-ui/src/{App.jsx,main.jsx}`, `src/components/{Header,Sidebar,Icon}.jsx`, `src/data/services.js`

### Backend mount (additive)
- `Northstar_backend/main.py` — appended defensive `include_router` block (end of file).

## Verification commands & results

| Command | Result |
|---|---|
| `python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider` | 74 passed |
| `cd northstar-os-ui && npm run build` | 67 modules, success |
| `python -m py_compile Northstar_backend/main.py ...` | success |
| `python -m Northstar_backend.tools.foundation_migrate_dryrun --repo-root . --json` | 1,857 records → 1,628 identities; reads only |
| `uvicorn foundation.app:app` (spare port) + curl | `/environment`, `/roles`, `/me`, `/providers` 403 (no auth), viewer `403`, operator product create — then stopped |

## Session at a glance

- Tests executed: 74 (foundation) — all offline, temp-DB, provider-isolated.
- External provider calls: **none**.
- Production DB writes: **none**.
- Migrations applied: **none**.
- Secrets accessed: **none**.
- Policy files changed: **none**.

## Document set

Phase 1B docs: `docs/northstar-phase1b/00..17` (18 md) + 6 JSON reports.
Phase 0 (`docs/northstar-discovery/`, 23 files) and Phase 1A (`docs/northstar-phase1/`, 34 files) remain intact.