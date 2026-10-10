# Design Studio — Phase 6 continuation report

**Date:** 2026-10-10 · **Branch:** `feature/overnight-remediation-20261009` · **HEAD:** `4c06851` (session start `27a649b`)
**Budget adherence:** all ten work items closed; zero live or paid provider calls; generation stayed UNARMED.

---

## 1. Commits (this session)

| Commit | What |
|---|---|
| `080d056` | Landed the uncommitted Phase 0 merge (one `/design-studio` route, empty seeds, EmptyState, `design_studio_api` mount) after verifying it against the built app |
| `b2505d9` | Dev sign-in root-cause + fix (verify the shim, fall back to real login, never fail silently) |
| `f64c9ad` | Test build for the pixel paths (`VITE_TEST_HOOKS=1`, dist-test), shim removed from served bundles, deploy-compose guard, server-side shim tests |
| `4da7a68` | Legacy redirects carry `?view=` (merge-regression fix found during item 4) |
| `4c06851` | Items 4–7: imported marketplace evidence (SP terms + BA SQP), briefs, variant comparison, indexing register |

## 2. Work items

1. **Dev sign-in defect — root-caused and fixed.** The old diagnosis ("the submit handler does not run") was wrong: the handler runs, writes the shim identity, and the backend answers **401** — the Vite proxy targets the Docker API container, whose client is a bridge address, so the loopback-only dev shim is ignored; the guard then bounced the user back to `/sign-in` with no error. Fixed by verifying the shim result and falling back to the real `/auth/login`, with an explicit alert when both fail. Verified in the browser: demo creds fail visibly; a real account signs in and survives reload.
2. **Test build for pixel paths.** `VITE_TEST_HOOKS=1 npm run build -- --outDir dist-test`, served as a built bundle under `/ui/` with `/api` proxied to the same backend the deploy composition uses. Never deployed: gitignored, dockerignored, and `Dockerfile.api` copies only `/ui/dist` from its own build stage. The bundle guard scans BOTH artifacts: production carries **neither the hook nor the shim** (identity, credentials, header emitter, runtime switch all absent); the test build carries the hook and not the shim. Server-side tests: chosen shim cannot authenticate against a hosted posture; demo credentials never mint a session. Compose: the loopback `127.0.0.1:8000` publish is reset in the hosted overlay — the deploy composition publishes only Caddy (`tools/check-compose-deploy.cjs`, 3/0).
3. **Pixel paths re-verified — VERIFIED** against the test build: 37/0/0 FATAL, including fidelity pass (0.00%) / block (23.9% vs 6%), unverified and generated blocks, the export pipeline, and marker survival (34,263 bytes). The first run exposed a **stale harness fixture** (sign-off predating the Phase-5 hardening); it now uses the engine's own `makeCompareSignOff`, and a new negative test pins the hardening.
4. **File-import data path — VERIFIED.** SP search-term and BA SQP files import into tenant-scoped tables with date + source label; the banner reads `imported file, observed <date>, not live`; missing columns are NULL (never 0); duplicates are idempotent (fingerprint, incl. BOM/CRLF); 65-day/31-day notes travel with every import; BA reads UNAVAILABLE until a file arrives. New endpoints are strictly org-scoped (anonymous → 401). Legacy-route identity collapse found and recorded (D10) rather than changed in passing.
5. **Brief-from-search-terms — VERIFIED.** Composed from imported terms + brand profile; every ranking carries a sample-size label and the click-only caveat; missing data reads UNKNOWN; headlines are never invented; nothing is generated.
6. **Variant scaffold — VERIFIED.** Variants + user- or file-entered metrics; unmatched file rows are reported, never turned into variants; comparison view warns on small samples and makes no causation claim, naming the attribution gap.
7. **Indexing honesty register — VERIFIED.** Claims carry source id / confidence / pulled-at; unofficial claims REPORTED or UNSOURCED; alt text and on-image text carry no recorded ranking support, and a studio-wide source scan (non-vacuous control) proves no positive imagery-ranking claim exists in the UI.
8. **Capability audit — DONE (documented as limits).** `reports/design-studio-capability-audit_20261010.md`: matrix over layers, reference lock, safe-zone, undo/redo, compare sign-off, export gates for all three canvases; gaps in Projects (no undo/redo, no reference lock, no compare) and 3D (no compliance gate on direct export, no reorder stack) are named with file:line evidence.
9. **Remaining gaps — DONE.** Re-check-log migration after the backend move: browser e2e VERIFIED (one-shot, lossless, failed check stored as failure, local copy cleared only after server confirm, no duplication). Policy freshness register re-run 2026-10-10: `{"current": 35}` — nothing past cadence, zero re-pulls, no login-gated page touched.
10. **Full regression — 750 passed, 0 failed, 0 FATAL.** Every harness with full output + FATAL counting, evidence in `reports/regression_20261010/`; screenshots refreshed at desktop and mobile widths (18 images); accessibility pass included in the section-evidence harness (62 checks). No failure needed a parent-commit comparison because there were none.

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (this session, observed in running code/test output):** every item above; the seven harness runs listed in the checkpoint; the strict 401 on the new routes; the deploy-compose contract; the migration; the freshness register.
- **REPORTED (carried from sources, unchanged):** the two login-gated Amazon pages in `OWNER_CAPTURE_TASKS.md`; unofficial indexing folklore items (deliberately marked REPORTED/UNSOURCED).
- **UNKNOWN (left null, never zero):** all metrics absent from supplied files; Brand Analytics before a file exists; any spec/rule without a source (blocks export).

## 4. Test counts

| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 106 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs (mocked) | 25 / 0 |
| test-indexing-register.mjs (new) | 28 / 0 |
| check-prod-bundle.cjs | 14 / 0 |
| check-compose-deploy.cjs (new) | 3 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| test_design_studio_imports.py (new) | 33 / 0 |
| test_auth_guard.py (pytest, +3 new) | 16 / 0 |
| check-jsx-imports.py | 97 files, 0 / 0 |
| test-compositing.cjs prod | 23 / 0 / 0 FATAL |
| test-compositing.cjs test build | 37 / 0 / 0 FATAL |
| test-compositing.cjs dev | 37 / 0 / 0 FATAL |
| verify-design-studio.cjs | 67 / 0 / 0 FATAL |
| test-migration-e2e.cjs | 12 / 0 / 0 FATAL |
| verify-operator-smoke.cjs | 11 / 0 |
| verify-search-terms.cjs (new) | 33 / 0 / 0 FATAL ×2 |
| _check-recheck-migration.cjs | 1 / 0 (migration contract) |
| capture-section-evidence.cjs | 62 / 0 / 0 FATAL, 18 screenshots |
| **TOTAL** | **750 passed / 0 failed / 0 FATAL.** |

Skipped: none. NOT RUN: none.

## 5. Gates hit and defaults applied

- **No hard gate was hit.** No live/paid call, no purchase, no publish, no credential access, no destructive git.
- Defaults logged in `reports/audit-2026-10-08/OWNER_DECISIONS_A1-A9.md` addendum: **D8** dev sign-in fallback; **D9** `VITE_TEST_HOOKS` naming; **D10** strict route scoping for the new endpoints (legacy buckets untouched); **D11** local container run with the documented, production-refused rate-limit opt-out; **D12** capability gaps documented (not closed); **D13** harness fixture cleanup for re-runs.
- The uncommitted Phase 0 merge encountered at session start was verified (build 0 errors, route sweep evidence, `verify-design-studio` 67/0) and committed — it was REPORTED complete in the checkpoint and is now VERIFIED.

## 6. Live/paid calls and arming

**0 live or paid provider calls.** Generation remains **UNARMED** (`model_router.media_live_armed()` false; every generate surface reports "Blocked — provider required"; `test-generation.mjs` ran entirely on mocks). The new import/brief/variant paths make no provider call — they store and compose the operator's own files.

## 7. Honest limits / not inspected

- **Single-user local posture**: route-level identity for the LEGACY design-studio endpoints collapses into one shared bucket (recorded as D10). The new imported-evidence endpoints are org-scoped; fixing the legacy surfaces moves stored data and is an owner decision.
- **The local container currently runs with the harness rate-limit opt-out** (D11). `tools/start-local.ps1` restores the limiter on the next normal start; production refuses the flag at boot.
- The **:8200 vite preview** serving `dist-test` was left running for harness re-runs; stop the node process to free the port.
- Capability gaps in Projects/3D (item 8) are documented, not closed.
- The test build was served as a built bundle with the same-origin `/api` proxy (equivalent shape), not through Caddy itself.
- Not inspected: the Amazon Seller Central / Ads pages behind sign-in (forbidden), the golden-goose and sourcing workstreams (other sessions), the untracked files of other sessions (left untouched).
- The db/runtime files (`northstar.db`, ledgers, discovery manifests) changed by runtime use during the session were left uncommitted, as before.

## 8. Owner morning checklist

1. Read `reports/design-studio-capability-audit_20261010.md` and decide whether to close the Projects (undo/reference/compare) or 3D (compliance gate) gaps.
2. Decide on D10: migrate the legacy design-studio buckets to org scoping (moves existing rows) or accept the demo bucket.
3. Sign the two capture tasks in `research/design-studio/OWNER_CAPTURE_TASKS.md` when convenient (login-gated pages, one or two observed sentences each).
4. Confirm you are happy that the dev sign-in now falls back to real credentials (D8) — the local demo identity no longer authenticates against the containerized backend by design.
5. If you re-run the harnesses, note the local stack was left with the harness rate-limit opt-out; `tools/start-local.ps1` clears it.
6. Decide the next workstream: the remaining Phase 5 items (search/listing integration into other rooms, performance loop) are still NOT STARTED.

## 9. Next action

Owner review of the capability audit and D10; then either the performance loop scaffold or the listing-integration item as the next build directive.
