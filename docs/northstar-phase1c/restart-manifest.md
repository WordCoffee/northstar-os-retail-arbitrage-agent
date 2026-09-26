# Restart Manifest — Phase 1C-LC (UI wiring: LOCAL_PRIVATE_BETA_UI_READY)

**Timestamp:** 2026-09-24
Prior gates accepted (1C-04/05/06 + master slice + subscriber operations). Final: LOCAL_PRIVATE_BETA_UI_READY.

## Completed
- Tester/owner views (acceptance, onboarding, plan & usage, seats, support, account status).
- Platform-admin Beta Operations (dashboard, filters, org control, notes, overrides, export).
- Role-aware navigation; suspended account-status screen with support pathway.
- Local platform-admin bootstrap (loopback-only, audited).
- Browser E2E a-e validated; full regression suites green.

## Totals
SQLite 633 passed / 58 skipped; disposable PG 58 passed; harness 9/9; staging smoke 31/31.

## Next (external, owner-authorized only)
Live keys / live providers / public signup / production provisioning.

## Tree state
Runnable: yes (browser at http://127.0.0.1:8001/ui). Rollback: none executed.
Branch: main/ecef24a. No commits. Dedicated UI PG on 55434; staging on 55433; disposable on 55432.
