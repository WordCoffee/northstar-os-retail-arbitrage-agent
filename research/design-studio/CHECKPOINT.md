# Design Studio ? Phase Checkpoint

## Phase 0 ? MERGE ? COMPLETE (21/21)
## Phase 1 ? DEEP RESEARCH ? COMPLETE (GATE 1 approved), 169 sources
## Phase 2 ? DESIGN SYSTEM + 9 WORKSPACES ? COMPLETE
## Phase 3 ? AI DISCLOSURE, FIDELITY, FRESHNESS, PERSISTENCE ? COMPLETE
## Phase 4 ? COMPOSITING CANVAS ? COMPLETE

### 1. THE SEVENTH QUESTION: identifiability
`IDENTIFIABILITY_QUESTION` ? "Is this intended to look like a real, identifiable
individual?" ? BLOCKS export with an explanation grounded in consent and right
of publicity, and NEVER produces a tag. The block text explains why the marker
does not apply (Amazon defines a synthetic performer as someone "not
recognizable as an identifiable person") and names the New York Fashion Workers
Act consent requirement for a digital replica of a model.
**It runs BEFORE the exemptions on purpose**: consent is not a labelling
question, so no carve-out lifts it. An identifiable synthetic voice in an
audio-only ad is still a consent problem.

### 2. EXEMPTION VERIFICATION
Three carve-outs, each an explicit named gate rather than a special case:
- expressive-work ad (film / TV / streaming / documentary / video game)
- **audio-only** ? the NY statute expressly does not apply to audio ads, so the
  rule must NOT fire. Verified: an audio asset produces a PASSING disclosure
  row, not a block, and is never asked for the marker.
- translation-only AI
Each carries a source and an accessed date. Verified that no exemption applies
to a normal asset, and that an expressive-work exemption does NOT lift the
identifiability block.

### 3. UPLOAD CHECK
`verifyUploadedAsset(bytes, {mime, tagRequired})` runs the real marker reader
against the LIVE bytes. It returns marker-present / marker-missing /
not-required, and the warning names the reported reprocessing cause and the fix
(re-upload the tagged original and check again). Missing bytes fail closed.

### 4. RE-CHECK LIBRARY + NOTICE-AND-CURE
`NOTICE_AND_CURE_DAYS = 5` (a publisher or distributor on notice has five days).
`cureWindow()` computes elapsed and remaining days and reports an expired
window. `recheckEntry()` REFUSES to log a check that did not run, so the log can
never claim a verification that never happened. `recheckSummary()` returns the
count, the latest check and whether it ever failed.

### 5. OWNER CAPTURE TASK
`research/design-studio/OWNER_CAPTURE_TASKS.md` plus a `SOURCES.csv` template
with two rows ready to fill. It asks for ONE OR TWO OBSERVED SENTENCES per page,
not a reproduction of Amazon documentation, and states that a correction is more
valuable than a confirmation. The two labels stay REPORTED until the capture;
`OWNER_CAPTURE_TASKS.md` names the exact line to change in `specRegistry.js`
and the surfaces that upgrade with it.

### 6. THE COMPOSITING SURFACE (new)
`studio/engine/compose.js` ? the one path an asset leaves by:
render -> fidelity -> compare -> compliance -> marker-embed -> marker-verify.
Every step reports pass / block / unverified / not-required / not-run, and a step
that did not run is NEVER shown as passed.

`pages/internal/design-studio/CompositingSurface.jsx` ? layers (add, select,
reorder, delete), a locked reference, the safe-zone overlay, undo/redo, the
compare modal, and the export button. The product is the operator's own
photograph drawn with `contain` (stretching would itself be a fidelity failure);
nothing is generated. Wired into Listing Images.

An opt-in `?engine=1` hook exposes the engine for browser harnesses. It is off
unless the query parameter is present and exposes functions only.

**The fidelity canvas extraction runs in a real browser** (item 6's explicit
requirement), with real generated PNGs:
- a composite that matches the reference: **mean 0.00% -> PASS**
- a product redrawn in a different colour: **mean 23.9% -> BLOCK** (limit 6%)
- locked with no reference -> UNVERIFIED, which blocks
- a generated product region -> BLOCK
- the full pipeline: all six steps pass and the marker survives the real export
  (34,263 bytes written)

### 7. HUMAN COMPARE STEP
`compareStepStatus()` requires a person to compare the render against the locked
reference for ANY asset containing the product. Export is blocked until the
sign-off, which records who and when. **A new reference invalidates the
sign-off.** Verified in the browser: the pipeline blocks on the missing sign-off
and writes no bytes.

### 8. ON-IMAGE TEXT
Text is always a real vector layer drawn by the canvas, never generated pixels.
Three rules added:
- `text-outside-frame` (BLOCK) ? text cut off by the frame edge
- `text-overflows-safe-zone` (FLAG) ? text inside a documented keep-out zone,
  tested against the Store hero left crop and the SB video bottom-right corner
- `text-legibility` (FLAG) ? normalised size x canvas height below an 18 px
  floor

### Verification ? 9 harnesses, full output, FATAL counted
| # | Harness | Result | Exit |
|---|---|---|---|
| 1 | `test-compliance-rules.mjs` | **106 passed, 0 failed**; 50/50 rules, 13/13 groups, 48 specs, 0 unsourced | 0 |
| 2 | `test-disclosure.mjs` | **65 passed, 0 failed** | 0 |
| 3 | `test-fidelity-freshness.mjs` | **34 passed, 0 failed** | 0 |
| 4 | `test_design_studio_isolation.py` | **25 passed, 0 failed** | 0 |
| 5 | `test_login_throttle_bypass.py` | **16 passed, 0 failed** | 0 |
| 6 | `check-jsx-imports.py` | 95 files, 0 undefined, 0 unguarded | 0 |
| 7 | `test-compositing.cjs` | **21 passed, 0 failed, 0 FATAL** | 0 |
| 8 | `verify-design-studio.cjs` | **67 passed, 0 failed, 0 FATAL** | 0 |
| 9a | `test-migration-e2e.cjs` | **12 passed, 0 failed, 0 FATAL** | 0 |
| 9b | `verify-operator-smoke.cjs` | **11 passed, 0 failed**, 21/21 rail | 0 |

### Bugs the harnesses found this phase
1. The expressive-work carve-out never fired (exemptions were only applied for
   `forceSkip` flags).
2. Identifiability had to be reordered ABOVE the exemptions: a carve-out was
   lifting the consent block.
3. The compositing harness initially called the data-URL fidelity variant
   instead of the canvas path the pipeline actually uses.
4. A 400 px fixture was correctly blocked by `raster-range` ? the engine was
   right and the test was wrong. Fixtures moved to a realistic 1200x1200.
5. The sections harness looked for the coverage counter in the first bottom
   strip; the embedded surface adds a second, so the assertion was wrong.

### Generation status
**UNARMED.** No live or paid call. No cron. No on-load provider request.

### Files touched
- `studio/engine/disclosure.js` (7th question, exemptions, upload check, re-check library)
- `studio/engine/compose.js` (new), `fidelity.js`
- `studio/engine/compliance.js` (3 text rules, 50 total)
- `pages/internal/design-studio/CompositingSurface.jsx` (new)
- `pages/internal/design-studio/{ListingImages,SectionWorkspace}.jsx`
- `pages/internal/DesignStudio.jsx` (opt-in engine hook)
- `styles/studio.css`
- `research/design-studio/{OWNER_CAPTURE_TASKS.md,SOURCES.csv}` (new)
- `tools/{test-compositing.cjs}`, extended `test-{disclosure,compliance-rules}.mjs`

## Resume at
Phase 4 remainder: the other eight sections still render the format and the
pre-flight but do not embed the compositing surface. Next: embed it in A+,
Storefront, Ads and the rest, then arm the local ComfyUI pipeline behind an
explicit Run with a cost preview.

### 3 + 4 UI GAP CLOSED (follow-up pass)
The first Phase 4 pass shipped items 3 and 4 as ENGINE functions only. A
verification pass found ZERO page-level references to `verifyUploadedAsset`,
`cureWindow`, `recheckEntry` or `recheckSummary` - the directive asks for a
seller-facing step and a Library action, so the gap was real and is now closed.

`CompositingSurface` gained a **Library** tab:
- **Upload check** - a file input that loads the LIVE image back and runs the
  real marker reader. Verified in the browser: a tagged file reports
  marker-present; an untagged file WARNS and names the fix.
- **Re-check log** - every check is logged with its date, the verdict, the
  surface that ran it and whether it passed. Persisted to localStorage and
  verified to survive a reload. A failed check is logged as a failure.
- **Per-entry "re-check exported ad"** action, plus an optional notice date
  that renders the 5-day cure window.
- Successful exports are recorded in the library, so there is a real asset for
  the re-check action to act on.

The surface also gained an **AI-generated people disclosure** inspector section
(classification, marker toggle, studio-generated flag, identifiability, export
filename). Without it the surface could only ever answer "not-required" for the
upload check - a false pass on an asset that needs the marker. That was the bug
the new harness caught, and the requirement is now derived from the asset's own
classification state rather than an assumption.

### Verification - 9 harnesses (final)
| # | Harness | Result | Exit |
|---|---|---|---|
| 1 | `test-compliance-rules.mjs` | 106 passed, 0 failed | 0 |
| 2 | `test-disclosure.mjs` | 65 passed, 0 failed | 0 |
| 3 | `test-fidelity-freshness.mjs` | 34 passed, 0 failed | 0 |
| 4 | `test_design_studio_isolation.py` | 25 passed, 0 failed | 0 |
| 5 | `test_login_throttle_bypass.py` | 16 passed, 0 failed | 0 |
| 6 | `check-jsx-imports.py` | 95 files, 0 / 0 | 0 |
| 7 | `test-compositing.cjs` | **35 passed, 0 failed, 0 FATAL** | 0 |
| 8 | `verify-design-studio.cjs` | 67 passed, 0 failed, 0 FATAL | 0 |
| 9a | `test-migration-e2e.cjs` | 12 passed, 0 failed, 0 FATAL | 0 |
| 9b | `verify-operator-smoke.cjs` | 11 passed, 0 failed, 21/21 rail | 0 |

## PHASE 5 ? OVERNIGHT CONTINUOUS COMPLETION

### 1. COMPOSITING SURFACE ON ALL SECTIONS ? PARTIAL (6 of 9)
`SectionWorkspace` now embeds `CompositingSurface`, which covers A+ / Brand
Story, Storefront, Ads, Video & UGC, Social and Packaging. Listing Images was
already wired. Projects and 3D Product Scene each OWN an equivalent canvas and
are documented as such in `tools/capture-section-evidence.cjs`:
- Projects: the board owns the Creative Studio master canvas (Stage.jsx) and the
  creative engine (doc model, templates, compliance, render/export).
- 3D Product Scene: owns a real 3D composer (engine/three.js).
The SectionWorkspace's duplicate inspector was removed and the FULL
CompliancePanel now lives in the surface's inspector, so every section keeps the
complete pre-flight rather than only a verdict.
Video & UGC is a storyboard/frame canvas only; no video rendering.

### 2. RE-CHECK LOG TO BACKEND ? DONE
New `ds_rechecks` table (tenant-scoped) + `DesignStudioRechecksDB` + endpoints
POST/GET/GET-by-id/DELETE `/api/design-studio/rechecks` and POST
`/rechecks/migrate`. Idempotency is enforced by a UNIQUE index on
(account_id, legacy_key), so a re-import reports `skipped` rather than
duplicating. New client module `studio/engine/rechecks.js` imports the local log
once and clears it ONLY after the server confirms, keeps a local mirror as an
offline fallback, and reports UNKNOWN (not zero) when the backend is unreachable.
`/search` now covers re-checks too. Negative tests added for read, delete, list,
asset-scoped list, the failed-check record and the idempotent legacy key.

### 3. COMPARE SIGN-OFF HARDENING ? DONE
The sign-off now records the user, the time, the ASSET VERSION and a hash of the
REFERENCE. Any edit or reference change makes it fail to match and re-requires a
fresh sign-off. The record carries its own caveat string, and the satisfied state
still says it "is not evidence that anyone looked".

### 4. FIDELITY THRESHOLD CALIBRATION ? DONE
Six synthetic edit classes measured against the 6% / 45% thresholds. FINDING:
the 6% AVERAGE test is blind to small in-product edits (label text change 0.67%
mean, logo swap 0.58% mean); the worst-pixel tripwire caught ALL FOUR in-product
classes. Relight at +24 luminance blocks on the mean (8.89%). A second,
tighter `labelRegionDiff()` was added with its own 2% / 10% limits, plus an
explicit `FIDELITY_BLIND_SPOTS` list. Thresholds are labelled engineering
choices, not Amazon figures.

### 5. TEST HOOK REMOVED FROM PRODUCTION ? DONE
The `?engine=1` hook is now gated on `import.meta.env.DEV`, so rollup eliminates
its body from a production bundle. Verified against the REAL dist:
`tools/check-prod-bundle.cjs` asserts the global and the query-parameter read are
both ABSENT, with a positive control so the scan cannot pass vacuously. The
compositing harness degrades to a documented SKIP in a production build instead
of failing.

### 6. SEARCH/LISTING INTEGRATION ? NOT DONE (see limits)
### 7. PERFORMANCE LOOP SCAFFOLD ? NOT DONE (see limits)

### 8. POLICY FRESHNESS ? DONE (nothing to re-verify)
The register was re-run: all 35 sources are CURRENT on 2026-10-10, which is the
date the corpus was pulled. Nothing is past its cadence, so there is nothing to
mark needs-re-verification and no public page needed a re-read. `ruleFreshness`
already marks an unregistered source as not-current, and every rule result
carries a freshness verdict. No login-gated page was re-pulled.

### 9. LOCAL GENERATION PATH (UNARMED) ? DONE
New `studio/engine/generation.js` maps a router response into document metadata
so generated output enters the SAME gates as imported art. A generated PRODUCT
REGION is blocked (fidelityMode 'generated' + a pre-flight block). A generated
person AUTO-FLAGS, AUTO-APPLIES the marker, and STILL requires a seller
attestation; switching the marker off is a CONFLICT. An unknown generation kind
is UNKNOWN and refused. `gateGenerate` refuses even when armed without a cost
preview. The module contains NO network call (asserted by scanning its own
source). 25 fixture tests, all mocked responses.
Added: `GET /api/design-studio/generation-status` (read-only, zero provider
calls), a "generation UNARMED" banner in every surface, and
`docs/GENERATION_ARMING_CHECKLIST.md` (spend/time caps, audit log, kill switch).

### 10. SERVICE INVENTORY AND DOCS ? DONE
S26 Design Studio and S27 Product Designer / 3D Product Scene added to
`reports/audit-2026-10-08/SERVICE_INVENTORY.csv` with honest statuses and the
explicit not-done list. `OWNER_CAPTURE_TASKS.md` remains the capture task.

### 11. FINAL HARDENING ? DONE
Static antipattern check (`check-jsx-imports.py`) extended earlier and clean.
NEW `tools/capture-section-evidence.cjs`: 18 screenshots (9 sections x desktop
1440x900 + mobile 390x844) into `reports/screenshots_20261010/`, plus per-section
canvas presence, "generation unarmed" banner presence, keyboard reachability,
focus acquisition, heading contrast and mobile horizontal-overflow checks.
62 passed / 0 failed.

### VERIFICATION (this session, running code)
| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 106 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs (NEW) | 25 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| check-jsx-imports.py | 95 files, 0 / 0 |
| check-prod-bundle.cjs (NEW) | 3 / 0 |
| capture-section-evidence.cjs (NEW) | 62 / 0, 18 screenshots |
| verify-design-studio.cjs | 67 / 0 |
| test-migration-e2e.cjs | 12 / 0 |
| verify-operator-smoke.cjs | 11 / 0, 21/21 rail |
| **test-compositing.cjs** | **NOT RUN ? times out** |

### NOT DONE, WITH REASONS
- **Compositing browser harness**: times out against both the production build
  (hook correctly absent) and the Vite dev server. Its UI-level assertions
  (surface mount, library, upload check) passed earlier this session at 35/0;
  the pixel paths passed earlier this session at 35/0 BEFORE the hook was gated.
  Neither has been re-confirmed against the current code.
- **Items 6 and 7** (search/listing integration, performance loop) were not
  started; the loop reached the end of the budget first.
- Six of nine sections embed the surface; two own equivalent canvases.
