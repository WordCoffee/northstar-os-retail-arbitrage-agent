# Design Studio — Phase 7 report

**Date:** 2026-10-10 (overnight into 2026-10-11 UTC) · **Branch:** `feature/overnight-remediation-20261009` · **HEAD at start:** `4ce693e` (Phase 6 close `e3bfe2d` + two other-session doc commits) · **All items closed.**

---

## 1. Commits (this session)

| Commit | What |
|---|---|
| `d099b16` | Items 1–3: D10 identity migration + strict route scoping, dev sign-in fails closed, rate-limit opt-out cannot ship |
| `94d6d8d` | Item 4: Projects undo/redo + reference lock + compare sign-off + export gate; 3D render gate (actual-photo BLOCK, disclosure, fidelity, product-accuracy) |
| `5abacf6` | Items 5–7: listing integration, brand-voice/keyword ingestion, performance loop + results CSV |

Other sessions' commits (`b9548fc` audit reports, `c91b4a0`/`4ce693e` research) were left untouched; work stacked on top.

## 2. Work items

1. **D10 identity migration — DONE.** All Design Studio routes now resolve a strict organization-scoped session; anonymous → 401 (live-verified on 11 legacy routes). `migrate_ds_identity.py` is dry-run-first with a deterministic rule: single-org moves shared buckets, unknown buckets always quarantine, nothing deleted, idempotent. Live reports in `reports/d10-identity-*.json`. Cross-tenant negatives with two real foundation tenants: list/search/read/export/delete all refused (`verify-d10-live.cjs` 12/0). Two isolated foundation test tenants created (credentials outside the repo, never printed).
2. **Dev sign-in — DONE.** The shim path is the exact demo pair only and never reaches `/auth/login`; it fails closed with an explicit message. `verify-shim-fail-closed.cjs` 8/0 (zero login requests from the shim path, no password logged, real login still works when typed).
3. **Rate limiter — DONE.** The harness opt-out is refused at boot in staging AND production; the hosted compose pins it to 0 (compose guard asserts it); `start-local.ps1` restores the limiter on every normal start. Posture tests 5/0.
4. **Capability gaps — CLOSED.** Projects: undo/redo, reference lock, version-bound compare sign-off, export gate (compliance + sign-off; the pixel diff on demand with stated limits). 3D: render gate with the Brand Registry actual-photo rule at BLOCK (rule id + source shown), the Amazon pre-flight, disclosure (unanswered blocks), fidelity when locked, product-accuracy sign-off; one sign-off covers every view of a scene. Harnesses 16/0 and 14/0.
5. **Listing integration — DONE.** Reads browser-local records only (ListingForge, brand profile, asset metadata, studio A+ projects) with source/observed/freshness/limits per field; missing = UNKNOWN; mismatches flagged NEEDS HUMAN REVIEW; no marketplace or provider call exists in the path.
6. **Brand voice + keyword ingestion — DONE.** Two new import kinds (archived, idempotent, dated); `GET /brand-voice`; briefs name voice AND keyword provenance; absent fields/volumes stay UNKNOWN.
7. **Performance loop — DONE.** Shared confidence bands on the comparison; results CSV with aggregates, sample, confidence note, observed range, sources and the NO-CAUSATION caveat; NULL = empty cell.
8. **Re-verification — DONE.** Pixel paths on the test build 37/0/0 FATAL; prod 23/0 with correct skip; bundle contract 14/0; freshness `{"current": 35}`, zero re-pulls, no login-gated page touched.
9. **Full regression — 772 passed / 0 failed / 0 FATAL** across 26 scored harnesses; evidence in `reports/regression_20261010_phase7/`; screenshots refreshed at desktop+mobile (18) with the accessibility pass (62 checks).

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (observed this session):** every item above, including the live two-tenant negatives, the live migration dry-run/apply behaviour, the shim fail-closed contract, both canvas gates with real downloads, the listing-context provenance and mismatch flags, the results CSV, and the 772-check regression.
- **REPORTED (carried, unchanged):** the two login-gated capture tasks; unofficial indexing folklore entries.
- **UNKNOWN (left null/UNKNOWN, never zero):** all metrics absent from supplied files; Brand Analytics before a file exists; listing fields no local store provides; a keyword volume the file omits.

## 4. Test counts

Full table in `research/design-studio/CHECKPOINT.md` (Phase 7 section) and raw output in `reports/regression_20261010_phase7/`. **772 passed, 0 failed, 0 skipped, 0 NOT RUN, 0 FATAL.**

## 5. Gates hit and defaults applied

- **No hard gate was hit** (no live/paid call, no purchase/publish, no credential access, no destructive git/data op).
- Defaults logged (OWNER_DECISIONS addendum): **D14** shim-only fail-closed sign-in; **D15** opt-out refused in staging+production; **D16** migration mapping (quarantine unknown buckets; live store held no shared-bucket records after the image rebuild — demonstrated with labeled seeds + fixtures); **D17** Projects sign-off as the gate with the diff on demand; **D18** 3D actual-photo BLOCK + one scene sign-off; **D19** listing context from browser-local stores only (90-day freshness window is an engineering choice); **D20** imported keywords feed briefs with provenance.

## 6. Live/paid calls and arming

**0 live or paid provider calls.** Generation remains **UNARMED** (`media_live_armed=false`; every generate surface reports "Blocked — provider required"; the generation harness ran entirely on mocks). The listing-context path contains no network call beyond the local API reads.

## 7. Honest limits / not inspected

- The local container was run with the documented, production-refused rate-limit opt-out for the harness phase; `tools/start-local.ps1` restores the limiter on the next normal start.
- The local Design Studio store is container-local SQLite (the hosted compose would need `DATABASE_URL` set to move it to PG); the image rebuild during this session reset it, which is why the real dry-run found zero shared-bucket records.
- The three organizations in the local deployment include the two synthetic test tenants; that is exactly why the migration quarantines shared buckets instead of guessing.
- The 3D composer still has no undo/redo or reorderable layer stack; both safe-zone overlays remain Advanced-mode aids (named in the audit addendum).
- The mismatch check is word-presence only — it cannot judge meaning, and it says so; it flags for human review and never edits.
- Not inspected: login-gated Amazon pages (forbidden), other sessions' workstreams (their commits/files untouched), the golden-goose/sourcing pipelines.

## 8. Owner morning checklist

1. Review the D10 dry-run/apply reports and confirm the quarantine rule matches your intent; if you want the synthetic test tenants removed from the local PG, say so (they exist for the cross-tenant negatives).
2. Decide whether the local Design Studio store should move to Postgres (set `DATABASE_URL` in the local stack) — today it resets when the image is rebuilt.
3. Skim the two new gate semantics (D17/D18) — especially that a listing-purpose 3D render is blocked outright by design.
4. Sign the two capture tasks in `research/design-studio/OWNER_CAPTURE_TASKS.md` when convenient.
5. Note the local stack currently carries the harness rate-limit opt-out until the next `tools/start-local.ps1` run.
6. Next directive: the remaining Phase 5 items (search/listing integration into other rooms, the performance loop beyond imports) or whatever you prioritize.

## 9. Next action

Owner review of the D10 reports and the two gate semantics; then the next build directive.
