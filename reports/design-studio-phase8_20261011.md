# Design Studio — Phase 8 report

**Date:** 2026-10-11 · **Branch:** `feature/overnight-remediation-20261009` · **HEAD at start:** `cda7e06` (Phase 7 close `2f7ac89` + other-session commits) · **All items closed.**

---

## 1. Commits (this session)

| Commit | What |
|---|---|
| `902a200` | Item 2: real Postgres support for the data layer + PG harness + D10-on-PG reports |
| `8c382fb` | Item 1: registry updates (title length, AI-people window, formats, no-10MB, A+ eligibility) |
| `dd0c2a2` | Item 3: listing context → tenant store with one-shot migration; PG table-missing dialect fix |
| `f3eef9e` | Item 4: synthetic-tenant labelling + cleanup script |
| `dafd039` | Item 5: local fidelity trial harness + reference-photos drop-in |
| `e255807` | Items 6–7: 3D undo/redo + reorder; performance-loop labels |
| (this close) | Phase 8 docs + regression evidence + the PG read-commit/lock fix |

Other sessions' commits were left untouched; work stacked on top.

## 2. Work items

1. **Registry updates — DONE.** Five claim updates with source id, pulled-at date, tier, cadence and pass+fail fixtures (42/0). Title-length 75 chars → FLAG in the listing mismatch check (75 passes, 76 flags, no block, no truncation). AI-people metadata window 2026-07-22→2026-07-27 with the Product image guide authoritative, REPORTED. Image formats per the guide; the compliance rule now checks an explicit export format (107/0). The 10 MB limit is recorded UNCONFIRMED and NOT enforced (12 MB fixture does not block). A+ eligibility displays "confirm in A+ Content Manager".
2. **Postgres path — DONE.** The data layer's PG branch is real now (it connected but had no schema creation and SQLite-only execution): schema DDL shared and translated, dedicated `northstar_data` schema, `changes()` shim, IntegrityError translation, read-commit so no idle-in-transaction lock holds, lock-avoiding live-columns migration. `DATABASE_URL` set in compose. In-container harness 12/0; **D10 dry-run against PG reports counts per organization, fully mapped, 0 moves applied** (`reports/d10-identity-pg-*.json`); HTTP cross-tenant negatives on the PG stack 18/0.
3. **Listing context → tenant store — DONE.** `ds_listing_records` + endpoints; one-shot idempotent migration from the browser-local records, cleared locally only after server confirmation (the ListingForge working store untouched by design, D23); server-first reads with an explicit local fallback; cross-tenant negatives live.
4. **Synthetic tenants — DONE.** Kept clearly labelled (both markers); `cleanup_test_tenants.py` touches ONLY tenants with both markers (dry-run evidence: 2 marked, T2 untouched).
5. **Local fidelity trial — HARNESS DONE; LIVE TRIAL NOT RUN.** No reference photos supplied and no local media runtime running, both with causes. The labeled 5-image fixture run passes every gate (fidelity, label-region, background replacement, disclosure, export blocked pending sign-off, tamper blocked). Sample size 5 < 20: no pass rate claimed.
6. **3D editing — DONE.** Undo/redo + layer reorder; harness 9/0.
7. **Performance-loop labels — DONE.** "imported results only" + sample size + no-causation on every comparison; asserted in the harness.
8. **Re-verification — DONE.** Pixel paths on the test build 37/0; prod 23/0; bundle contract 14/0; freshness `{"current": 35}`, zero re-pulls, no login-gated page touched.
9. **Full regression — 813 passed / 0 failed / 0 FATAL** across 29 scored harnesses; evidence in `reports/regression_20261011/`; screenshots refreshed at desktop+mobile with the accessibility pass.

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (observed this session):** everything above, including the live PG migration run, the two-tenant HTTP negatives (18/0), the migration idempotency, the registry fixtures, the 3D editing harness, the fidelity-trial fixture gates, and the 813-check regression.
- **REPORTED (by design):** the title-length figure (until an Amazon-owned page is recorded); the AI-people metadata window; the 10 MB limit (recorded as NOT enforced).
- **UNKNOWN (never zero):** metrics absent from files; listing fields no store provides; keyword volumes the file omits; the live fidelity trial (no photos) and runtime generation (no runtime).

## 4. Test counts

Full table in `research/design-studio/CHECKPOINT.md` (Phase 8 section); raw output in `reports/regression_20261011/`. **813 passed, 0 failed, 0 skipped, 0 FATAL.** NOT RUN (with cause): the fidelity live trial (no reference photos), the runtime-generation path (no local media runtime), and the dev-mode compositing rerun (covered by prod+test this phase; ran in Phase 7).

## 5. Gates hit and defaults applied

- **No hard gate was hit.** No live/paid call, no purchase/publish, no credential access, no destructive git/data/model op; generation stayed unarmed for every external provider (the local trial never generated anything).
- Defaults logged (OWNER_DECISIONS addendum D21–D26): PG store via DATABASE_URL; synthetic tenants kept labelled + cleanup script; listing migration clears only the mirror after confirmation; fidelity trial inputs (NOT RUN + fixtures); registry claim statuses; PG read-commit semantics.

## 6. Live/paid calls and arming

**0 live or paid provider calls.** No cloud generation. The local fidelity trial ran composite-only paths against fixtures — no model, no runtime, no spend. Generation remains **UNARMED** for every external provider.

## 7. Honest limits / not inspected

- The fidelity live trial could not run: no operator photos in the drop-in folder, and no local image runtime is running (Ollama on 11434 serves text models only). The harness is ready for both.
- The title-length figure stays REPORTED; the AI-people window is assembled from dated sources with the guide authoritative.
- The PG switch moved the Design Studio store; the old container-local SQLite data was not migrated (the store was empty of shared-bucket rows at the switch, as the D10 report shows).
- The `northstar_data` PG schema is separate from the foundation's `public` schema by design.
- The two synthetic tenants remain in the local foundation DB (labelled; cleanup script provided).
- Not inspected: login-gated Amazon pages (forbidden), other sessions' workstreams.

## 8. Owner morning checklist

1. Review the D10-on-Postgres dry-run/apply reports (`reports/d10-identity-pg-*.json`).
2. Drop ≥5 real reference photos into `research/design-studio/reference-photos/` to enable the live fidelity trial; start a local image runtime first if you want the background-generation path.
3. Decide whether to remove the synthetic tenants (`cleanup_test_tenants.py --apply`) or keep them for the negatives.
4. Skim the registry claims (title 75 → FLAG, formats, no 10 MB block, A+ "confirm in A+ Content Manager").
5. Note the local stack runs with the harness rate-limit opt-out until the next `tools/start-local.ps1`.
6. Next directive: the remaining Phase 5 items or whatever you prioritize.

## 9. Next action

Owner review of the D10-on-PG reports and the Phase 8 registry claims; then the next build directive.
