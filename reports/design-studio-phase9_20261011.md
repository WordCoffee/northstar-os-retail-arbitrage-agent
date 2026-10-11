# Design Studio — Phase 9 report

**Date:** 2026-10-11 · **Branch:** `feature/overnight-remediation-20261009` · **HEAD at start:** `3d7c7d4` (Phase 8 close) · **All items closed.**

---

## 1. Commits (this session)

| Commit | What |
|---|---|
| `92d62f7` | Items 1+3: title rules VERIFIED via the owner capture (FLAGS only) + flat-file/Item-Highlights contract with the UNKNOWN column notice |
| (this close) | Item 2 panels, item 4 mask paths, item 5 evidence, docs + full regression evidence |

Other sessions' commits interleaved were left untouched.

## 2. Work items

1. **Title rules — VERIFIED via the owner capture.** New `title-guide` source (Amazon's Product title requirements page; login-gated — a public read returned the sign-in gate only, stated). Rules recorded and applied as FLAGS only: 75 chars incl. spaces (brand name counts, bundles not exempt), no promotional phrases (illustrative list), the characters ! $ ? _ { } ^ ¬ ¦ disallowed, same word ≤2×, applies to all except media and the four Gulf/Türkiye stores, rollout 2026-07-27 gradual with a 14-day review window (REPORTED, date-sensitive). Pass+fail fixtures per rule (registry-claims 65/0). Nothing is ever edited or truncated.
2. **Master-brain read-only panels — DONE.** One tenant-scoped read-only endpoint; the panel renders in ListingForge, AdPilot and SocialPulse with source/observed/freshness/limits and UNKNOWN for missing sections; no provider call exists in the path. Panels 13/0; cross-tenant + anonymous negatives 21/0.
3. **Flat-file contract — DONE.** Item Highlights = 125-char comma-separated field; flat-file column UNKNOWN until Amazon publishes it; the new ListingForge CSV export carries the notice, an empty `item_highlights` column and a trailing contract comment; the editor shows the notice. Harness 8/0.
4. **Fidelity trial — mask paths added; LIVE TRIAL NOT RUN.** Mask-protected edits pass (transparency-skip is the mask contract) and in-mask violations block; 5/5 fixtures pass all gates; live trial NOT RUN (no reference photos) and runtime generation NOT RUN (no local media runtime), each with its cause; sample size 5 (< 20): no pass rate claimed.
5. **Housekeeping — DONE.** Cleanup dry-run only (2 marked tenants, T2 untouched, nothing deleted); the rate-limit opt-out is absent from every deploy artifact (hosted pin "0", base default 0, merged deploy config shows "0" for all six services, no ENV in Dockerfile.api, none in `deploy/`).
6. **Re-verification — DONE.** Test-build pixel paths 37/0; prod 23/0; bundle 14/0; PG isolation 12/0 in-container + 21/0 HTTP; freshness suite 57/0, zero re-pulls, no login-gated page touched.
7. **Full regression — 860 passed / 0 failed / 0 FATAL** across 31 scored harnesses; evidence in `reports/regression_20261011_phase9/`; screenshots refreshed + accessibility pass.

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (observed this session):** all harnesses above; the title-rule fixtures; the panels in all three rooms; the CSV contract; the mask-path behaviour; the deploy-artifact rate-limit evidence; the cleanup dry-run.
- **VERIFIED (via the owner's capture, recorded):** the title rules and the Item Highlights field (login-gated page; the studio's own public read hit the gate — stated in the source note).
- **REPORTED:** the title-rule rollout (date-sensitive); the promotional example list is illustrative, not Amazon's full list.
- **UNKNOWN (never zero):** the Item Highlights flat-file/API column; absent metrics/volumes/fields; the live fidelity trial (no photos) and runtime generation (no runtime).

## 4. Test counts

Full table in `research/design-studio/CHECKPOINT.md` (Phase 9 section). **860 passed, 0 failed, 0 skipped, 0 FATAL.** NOT RUN (with cause): the fidelity live trial (no reference photos), the runtime-generation path (no local media runtime).

## 5. Gates hit and defaults applied

- **No hard gate was hit.** No live/paid call; no cloud generation or cloud templates; no model install/removal; no destructive git/data/model op; credentials never read; other sessions' files untouched.
- Defaults logged (D27–D31): title-guide source VERIFIED from the owner capture with FLAGS-only enforcement; master-brain panels read-only; Item Highlights column UNKNOWN; mask-protected fidelity semantics; harness fixture hygiene under PG persistence.

## 6. Live/paid calls and arming

**0 live or paid provider calls. No cloud generation.** The fidelity trial ran composite-only paths on fixtures (no model, no runtime, no spend). Generation remains **UNARMED for every external provider**.

## 7. Honest limits / not inspected

- The title rules rest on the owner's capture (login-gated page); the studio itself only ever saw the sign-in gate.
- The live fidelity trial awaits ≥5 reference photos in the drop-in folder and a running local image runtime; the runtime-generation path was never exercised.
- The mask-protected semantics use the engine's transparency-skip; a mask covering pixels that the reference DOES carry is not expressible here (documented as the trial's construction).
- The local stack still runs with the harness rate-limit opt-out (deploy artifacts are clean; `start-local.ps1` restores the limiter).
- Not inspected: login-gated Amazon pages beyond the single gate hit; other sessions' workstreams.

## 8. Owner morning checklist

1. Optionally drop ≥5 real photos into `research/design-studio/reference-photos/` and start a local image runtime to run the live fidelity trial.
2. Review the title rules in the listing mismatch check (FLAGS only) and the Item Highlights contract in the ListingForge CSV export.
3. Confirm the master-brain panels read as intended in the three rooms.
4. Decide on the synthetic tenants (`cleanup_test_tenants.py --apply`) — dry run shows 2 marked, T2 untouched.
5. Re-run `tools/start-local.ps1` before normal use (rate-limit posture).
6. Next directive: the remaining Phase 5 items or whatever you prioritize.

## 9. Next action

Owner review of the Phase 9 registry capture and the three-room panels; then the next build directive.
