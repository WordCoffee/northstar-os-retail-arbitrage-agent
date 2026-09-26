# Local Legacy-UI Cutoff — Completion Report

**Date:** 2026-09-24
**Scope:** LOCAL-ONLY private-beta stack (port 8001, disposable loopback PG). No production/staging/live changes.

## Decision: PASS

The legacy Operations Hub shell no longer appears in the local private-beta UI. Verified in the running browser on `http://127.0.0.1:8001/ui`.

## How it works (minimal, local-only)
- A **public `ui_mode` signal** (`GET /api/v1/foundation/ui-mode`, plus `ui_mode` on `/environment`) is set by the local stack (`NORTHSTAR_UI_MODE=private_beta`). Default elsewhere is `full` (staging/production unchanged).
- The React shell branches on `session.uiMode === 'private_beta'`:
  - Role-aware default landing at the root: `internal_platform_admin` → `#/beta-ops`; `organization_owner`/tester → `#/beta`; signed-out → `#/beta-signup` (never the old Hub).
  - Any other route in beta mode → a **Legacy-disabled tombstone**.
  - Sidebar filters to only the `Private Beta` + `Beta Operations` groups; the legacy Dock + Pinned drawer are hidden.

## Files changed
- `Northstar_backend/foundation/api/router.py` — public `GET /ui-mode` + `ui_mode` on `/environment` (default `full`).
- `Northstar_backend/tools/local_production_stack.py` — sets `NORTHSTAR_UI_MODE=private_beta` (local only).
- `northstar-os-ui/src/foundation/session.jsx` — fetches public `ui-mode` pre-auth; stores `uiMode`.
- `northstar-os-ui/src/foundation/api.js` — `uiMode()` client method.
- `northstar-os-ui/src/App.jsx` — beta-only route tree + `BetaDefault` redirect + `LegacyDisabled` tombstone; hides Dock/Pinned in beta mode.
- `northstar-os-ui/src/components/Sidebar.jsx` — beta-only group filter + hides the legacy "Live posture" footer in beta mode.
- `Northstar_backend/foundation/tests/test_frontend_gate.py` — regression tests (ui_mode contract + bundle markers).

## Routes / registrations disabled or redirected in beta mode
- **Default**: `/` and old default `/hub` → `BetaDefault` (role-based redirect to `#/beta-ops`, `#/beta`, or `#/beta-signup`).
- **Legacy pages** `/ledger`, `/prospector`, `/goldengoose`, `/offerchisel`, `/towncrier`, `/auctioneer`, `/autothink`, `/thewatch`, `/rankledger`, `/rivalboard`, `/foundation`, `/jobs`, `/keywords`, `/account`, and any other legacy path → **tombstone** (`Legacy UI disabled`).
- **Navigation**: legacy sidebar groups (Workspace, Sourcing, Listings, Social, Advertising, AutothinK, Monitoring, Internal, Account) are hidden; only `Private Beta` and `Beta Operations` remain. Legacy action dock (`Scan/Generate/Review/Create`) and the Pinned drawer are hidden.
- Guards/auth untouched: `#/beta-ops` still requires `platform_admin`; `#/beta` requires `view`; `#/beta-signup` is public.

## Local URLs to test
- `http://127.0.0.1:8001/ui` — role-based landing (admin → `#/beta-ops`, tester → `#/beta`, signed-out → `#/beta-signup`).
- `http://127.0.0.1:8001/ui#/beta-ops` (platform admin) · `http://127.0.0.1:8001/ui#/beta` (owner/tester) · `http://127.0.0.1:8001/ui#/beta-signup` (invite entry).
- Legacy tombstones: `http://127.0.0.1:8001/ui#/hub`, `#/ledger`, `#/sourcing`, etc.

## Commands run
```powershell
# backend + UI build + tests
npm run build          # in northstar-os-ui
python -m pytest Northstar_backend/foundation/tests -q -p no:cacheprovider          # 635 passed / 58 skipped
python -m pytest Northstar_backend/foundation/tests/test_frontend_gate.py -q -p no:cacheprovider  # 25 passed (incl. 2 new cutoff tests)
# disposable PG harness + PG regression
FOUNDATION_DB_URL=... python -m Northstar_backend.tools.foundation_pg_validate_durable   # 9/9 PASS
FOUNDATION_DB_URL=... python -m pytest <all PG modules> -q -p no:cacheprovider             # 58 passed
# stack restart (local, same secret)
python -m Northstar_backend.tools.local_production_stack start --port 8001
```

## Regression totals (all executed)
SQLite **635 passed / 58 skipped** · PG **58 passed** · migration harness **9/9** · frontend gates **25 passed** (2 new legacy-UI-cutoff tests).

## Safety
Loopback only; disposable PG only; no production/staging changes; no live providers; no public signup; no real card data; no committed secrets; no raw tokens echoed. The stack remains running on `127.0.0.1:8001` for inspection.