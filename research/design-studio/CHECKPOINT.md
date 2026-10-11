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

## Resume at (updated 2026-10-11, after Phase 11, HEAD 7193303 + this checkpoint)
Everything in Phases 0-11 is done; Phase 11's full regression evidence lives in
`reports/regression_20261011_final/` (SUMMARY.txt + one raw file per harness).
The only open items are OWNER-blocked, and nothing else in this workstream is
pending:
1. A real Amazon upload of a written change file (by design, the owner performs
   it; the harnesses prove everything up to the file). The corrected-file flow
   (upload a processing report → row-level cause → corrected resubmittable
   file) is the same by-design manual step.
2. The two login-gated capture tasks (`ai-tag-page`, `ai-ads-page`) in
   `research/design-studio/OWNER_CAPTURE_TASKS.md`.
3. The live fidelity trial: needs >=5 real photos dropped into
   `research/design-studio/reference-photos/` AND a running local image
   runtime; the harness (incl. the mask-protected paths) is ready.
4. Owner decisions A4/A5/A7 (bounded hosted call, cloud arming cost cap, the
   six isolated test roles) and the rest of the audit remediation sequence.
5. The Item Highlights flat-file/API column stays UNKNOWN until Amazon
   publishes it; the export notice and the Python writer posture both say so.
6. Housekeeping at any time: `cleanup_test_tenants.py` (dry run first) removes
   only the two labelled synthetic tenants.

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

## PHASE 6 ? COMPOSITING HARNESS ROOT-CAUSED (item 1 done; items 2-8 not started)

### Item 1 ? the harness no longer hangs, and the cause is isolated
Three real defects were fixed in `tools/test-compositing.cjs`:

1. **A hang mechanism.** Every inline `new Image()` loader lacked `onerror`, so
   a failed image never settled its promise and `page.evaluate` hung forever
   with NO output. All three loaders now reject on error.
2. **A scope bug.** `fixtures` was declared inside the `if (hasEngine)` block
   but used by the upload check, which runs in BOTH modes. Hoisted out; it needs
   no engine.
3. **A build-mode contract.** Added `HARNESS_MODE=auto|dev|prod`. `dev` REQUIRES
   the hook (fails loudly without it); `prod` REQUIRES its absence.
   `auto` decides from the page. Plus a WATCHDOG that reports the last step
   reached instead of hanging silently.

With those fixed, the harness completes in **prod mode: 23 passed / 0 failed /
0 FATAL**, correctly SKIPPING the pixel paths with instructions.

### The isolated cause for the dev mode (NOT forced green)
Running `HARNESS_MODE=dev` against the Vite dev server still cannot sign in.
A minimal repro produced the cause precisely:

    LOCAL_DEV in page: undefined
    URL after submit:  .../ui/sign-in        (unchanged)
    body delta:        0
    alert text:        none
    pageerrors:        none
    API calls:         only ui-mode 200 + me/environment/preview 401

**The login POST is never made.** The submit click produces no state change at
all: no request, no error text, no DOM change, no page error. The `onSubmit`
handler does not run. Ruled out along the way:

- the Vite proxy carries the login fine (curl through :8101 returns 200 + both
  cookies), so it is not a proxy or cookie problem;
- the form and the button exist exactly as expected
  (`<form onSubmit={submit}>` + `<button type="submit">`);
- it is NOT a credentials problem: `foundation/dev.js` sets
  `LOCAL_DEV = import.meta.env.DEV`, so a dev build takes the local-shim branch
  (`T2` / `123abc`), which makes no network call. The harness was updated to use
  the shim identity in dev mode and the click STILL produced zero state change.

So the dev-server sign-in failure is upstream of this harness. It is a real,
reproducible defect in the dev-server path, isolated but not root-caused within
budget. The pixel paths were verified passing earlier in the previous session
against a build where the hook was not yet gated; they have NOT been re-confirmed
against current code.

### Items 2-8 ? NOT STARTED
The loop spent its entire budget on item 1, which the exit criteria made the
blocker. No work was begun on: capability audit vs the surface (2), the
file-import data path (3), brief-from-search-terms (4), the variant scaffold (5),
the indexing-honesty register (6), the remaining Phase 4/5 gaps (7), or the
refreshed regression set beyond what was re-run (8).

### Full regression re-run (item 8's core), all green
| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 106 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs | 25 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| check-jsx-imports.py | 95 files, 0 / 0 |
| check-prod-bundle.cjs | 3 / 0 |
| test-compositing.cjs (prod mode) | 23 / 0, pixel paths SKIPPED |
| verify-design-studio.cjs | 67 / 0 |
| test-migration-e2e.cjs | 12 / 0 |
| verify-operator-smoke.cjs | 11 / 0 (21/21 rail) |
| capture-section-evidence.cjs | 62 / 0, 18 screenshots refreshed |
Total: **484 passed, 0 failed, 0 FATAL.**

## PHASE 6 B — DEV SIGN-IN DEFECT ROOT-CAUSED AND FIXED (session 2)

### The previous diagnosis was wrong in one detail
"The `onSubmit` handler does not run" is FALSE. Instrumented repro
(`tools/_repro-signin.cjs`): the click DOES run the handler —
`localStorage.ns-dev-session` is written with the shim identity and a fresh
`/me` probe fires. What actually happens after:

1. Vite dev build → `LOCAL_DEV` true → SignIn takes the in-page shim branch
   (by design, no `/auth/login` call).
2. `session.updateDev()` writes the shim identity and `refresh()` calls
   `/api/v1/foundation/me` with `X-User-Id` headers.
3. **The connected backend answers 401.** Port 8000 (the Vite proxy target) is
   the DOCKER API container (`northstarosretailarbitrageagent-api-1`), started
   by the hosted-container work (A2). The dev shim requires the request's
   effective client to be loopback; through Docker port-forwarding the API sees
   a bridge-network client, so the shim headers are ignored.
4. Session stays signed out → `navigate('/home')` → the auth guard bounces
   back to `/sign-in` → the form re-renders identically.
5. The old dev branch had NO failure path: no error text, no request, no DOM
   change, no page error. A silent no-op by construction.

Proof of the isolation (all run this session):
- shim `GET /me` direct to `:8000` → **401**; via the Vite proxy → **401**.
- the same shim request issued INSIDE the api container → the shim is
  ACCEPTED (403 `cross_organization_access_denied` — the demo user is simply
  not a member of `org-t2` there), `ENVIRONMENT=development` in-container.
- real credential login `POST /auth/login` against the same stack → **200**.
- `docker ps`: `:8000` is published by the api container, not a host uvicorn.

### The fix (minimal, honest, no posture loosening)
- `foundation/session.jsx` — `refresh()` now RETURNS an identity snapshot
  (`{authenticated, userId, status?, suspended?}`) so callers can act on the
  real result instead of assuming success.
- `pages/public/SignIn.jsx` — the dev branch verifies the shim result and, if
  the shim did not authenticate, falls back to the REAL `/auth/login` with the
  entered credentials. Both failure modes now show an explicit alert naming the
  cause (shim inactive on a containerized backend). No silent bounce remains.
- Button shows `Signing in…` and disables while busy.

### Verified in the running dev server (browser, Playwright)
- demo shim creds → stays on `/sign-in` WITH the explicit alert (no longer
  silent);
- real account `t2` → navigates to `/ui/home`, stays there after settle, and
  the session survives a reload;
- 0 page errors, 0 unhandled rejections.

DECIDED-BY-DEFAULT (D8): a dev build may now complete sign-in through the real
`/auth/login` path when the shim is unavailable. Reverse: remove the fallback
block in `SignIn.jsx` (the shim-first attempt is preserved above it).

## PHASE 6 C — TEST BUILD + PIXEL PATHS RE-VERIFIED (items 2 + 3)

### The test build
- `VITE_TEST_HOOKS=1 npm run build -- --outDir dist-test` produces a build that
  carries the `?engine=1` engine hook. The gate is compile-time:
  `import.meta.env.DEV || import.meta.env.VITE_TEST_HOOKS === '1'`.
- It is never deployed: `northstar-os-ui/dist-test` is gitignored and
  dockerignored, and Dockerfile.api copies only `/ui/dist` from its own
  in-image build (which never sets VITE_TEST_HOOKS).
- Served the same way as production: a built bundle under `/ui/` with `/api`
  same-origin proxied to the same backend the deploy composition uses
  (`npx vite preview --outDir dist-test --port 8200`).

### Dev shim removed from served bundles
- `foundation/dev.js`: `LOCAL_DEV` is now `!!import.meta.env.DEV` — a literal in
  every build. The runtime `window.__NORTHSTAR_LOCAL_DEV__` switch is gone, so
  no served bundle can enable the shim by setting a global.
- The demo identity, the demo password and the X-User-Id emitter fold out of
  built bundles (SignIn.jsx constants + the api.js branch).
- `tools/check-prod-bundle.cjs` asserts against the REAL artifacts:
  production → hook AND shim ABSENT (7/0, positive control);
  test build → hook PRESENT, shim ABSENT (7/0).

### Pixel paths re-verified (item 3) — VERIFIED against the test build
`HARNESS_MODE=test` against the served test build: **37 passed / 0 failed /
0 FATAL**, including:
- matching composite PASSES (mean 0.00%); redrawn product BLOCKS (23.9% vs 6%)
- locked-without-reference = UNVERIFIED; generated product region BLOCKS
- the full pipeline: blocks without a sign-off, blocks on an UNBOUND sign-off,
  passes with the engine's own `makeCompareSignOff`; the marker survives the
  real export (34,263 bytes)
- upload check marker-present / marker-missing, tenant-scoped backend log,
  cure window, reload persistence.

The one real failure found on the first run was a STALE HARNESS FIXTURE: the
sign-off record predated the Phase 5 hardening (no user / assetVersion /
referenceHash). Fixed to use the engine's own `makeCompareSignOff`, and a new
negative assertion pins the hardening (an unbound sign-off is refused).

Also re-run: prod mode vs the deployed-like build → 23/0 (pixel paths correctly
SKIPPED); dev mode vs :8101 → 37/0 (proves the dev sign-in fix + the dev hook).

### Deploy composition guard
- The loopback `127.0.0.1:8000:8000` publish (added in afc0bc8 so the Vite dev
  server can proxy) stays in the LOCAL composition. docker-compose.hosted.yml
  now `!reset`s the api ports, so the DEPLOY composition publishes only Caddy
  (80/443). `tools/check-compose-deploy.cjs` verifies both compositions against
  `docker compose config --format json`: 3/0.

### Server-side dev-shim tests (item 2)
`foundation/tests/test_auth_guard.py` +3: the shim cannot authenticate against a
hosted posture even from loopback; a dev-posture API refuses the shim for a
non-loopback client (the Docker port-forward case); the in-page demo credentials
never mint a session. File total: 16 passed / 0 failed.

DECIDED-BY-DEFAULT (D9): the engine-hook build flag is named `VITE_TEST_HOOKS`
(the alternative spelling `VITE_ENGINE_HOOK` was not used). Reverse: rename the
flag in DesignStudio.jsx, the harness docs and this checkpoint.

## PHASE 6 D — IMPORTED EVIDENCE, BRIEFS, VARIANTS, INDEXING (items 4-7)

### Item 4 — file-import data path (no live calls)
- New tenant-scoped tables `ds_imports` + `ds_search_terms` with DAOs; the same
  file re-imported (BOM/CRLF included) returns the EXISTING import via a UNIQUE
  fingerprint index — proven idempotent in `tools/test_design_studio_imports.py`.
- `Northstar_backend/design_studio_imports.py` parses Sponsored Products
  search-term reports and Brand Analytics SQP files (CSV/JSON, alias headers).
  A missing column is NULL in every row — never 0; a literal 0 stays 0. Every
  import carries the 65-day lookback, 31-day API-range and click-only notes;
  the observed range is operator input or the file's own dates (else UNKNOWN).
- Endpoints: POST/GET/DELETE `/imports`, GET `/terms` (+filters), GET
  `/terms/export` (NULL → empty cell), POST `/terms/brief`. Brand Analytics
  reads UNAVAILABLE until a file is imported.
- **Route-level tenancy fix for the new surface:** the legacy
  `get_current_user` dependency has no cookie awareness, so every legacy caller
  collapses into one shared bucket; the new endpoints use a strict,
  organization-scoped session dependency (`studio_account`) and anonymous
  callers get 401 (verified by curl and by the harness). The legacy bucket
  behaviour is left as-is and recorded (see OWNER_DECISIONS addendum D10).

### Item 5 — brief from search terms
`build_brief()` composes from imported terms + the brand profile; every ranking
carries a sample-size/confidence label, the click-only caveat travels with any
clicks reading, missing metrics read UNKNOWN, headlines are never invented and
nothing is generated. The UI sub-view lives in Ads › Search terms.

### Item 6 — variant scaffold
`ds_variants` + `ds_variant_metrics`; user-entered or file-imported metrics
only. A metrics file matches existing variants by id or exact name; unmatched
rows are REPORTED, never turned into variants. The comparison view warns on
samples below 25 clicks and states the no-causation rule and the attribution
gap (Amazon reports carry no creative identifier).

### Item 7 — indexing honesty register
`studio/engine/indexing.js` holds claims with source id, confidence and the
source's pulled-at date; unofficial claims are REPORTED/UNSOURCED. Alt text and
on-image text carry NO recorded ranking support and the register says so. It
renders as a sub-view of A+; a studio-wide source scan (with a non-vacuous
control) proves no positive imagery-ranking claim exists anywhere in the UI.

## PHASE 6 E — CAPABILITY AUDIT (item 8)
`reports/design-studio-capability-audit_20261010.md`: matrix over layers,
reference lock, safe-zone overlay, undo/redo, compare sign-off and export gates
for the compositing surface, the Projects canvas and the 3D composer, with
file:line evidence. Gaps documented as limits, not closed: Projects has no
undo/redo, no reference lock and no compare sign-off; 3D exports bypass the
compliance pre-flight; 3D has no reorderable layer stack; the Projects/3D
safe-zone is a 6% Advanced-mode aid, not the documented keep-out geometry.

## PHASE 6 F — REMAINING GAPS (item 9)
- **Re-check-log migration, browser e2e (backend move):** VERIFIED with
  `tools/_check-recheck-migration.cjs` — a seeded localStorage log of 2 entries
  migrates to the tenant backend exactly once, a failed check is stored as a
  failure, the local copy clears only after the server confirms, the flag is
  set, and a second mount does not duplicate.
- **Policy freshness register:** re-run 2026-10-10 → `{"current": 35}` — all 35
  sources current on the pull date, nothing past cadence, ZERO re-pulls, no
  login-gated page touched.

## PHASE 6 G — FULL REGRESSION (item 10)
All harnesses with full output + FATAL counting, evidence in
`reports/regression_20261010/`:

| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 106 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 (freshness: 35/35 current) |
| test-generation.mjs (mocked) | 25 / 0 |
| test-indexing-register.mjs (new) | 28 / 0 |
| check-prod-bundle.cjs | 14 / 0 |
| check-compose-deploy.cjs (new) | 3 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| test_design_studio_imports.py (new) | 33 / 0 |
| test_auth_guard.py (pytest, +3 new) | 16 / 0 |
| check-jsx-imports.py | 97 files, 0 / 0 |
| test-compositing.cjs prod (container) | 23 / 0, 0 FATAL |
| test-compositing.cjs test build (dist-test) | 37 / 0, 0 FATAL |
| test-compositing.cjs dev server | 37 / 0, 0 FATAL |
| verify-design-studio.cjs | 67 / 0, 0 FATAL |
| test-migration-e2e.cjs | 12 / 0, 0 FATAL |
| verify-operator-smoke.cjs | 11 / 0 |
| verify-search-terms.cjs (new) | 33 / 0, 0 FATAL (twice, deterministic) |
| _check-recheck-migration.cjs (new) | migration VERIFIED |
| capture-section-evidence.cjs | 62 / 0, 0 FATAL, 18 screenshots refreshed |

**Total: 750 passed, 0 failed, 0 FATAL. Zero live or paid calls; generation
UNARMED; the production bundle carries neither the engine hook nor the dev
shim.**

## PHASE 7 — OVERNIGHT CONTINUOUS COMPLETION (items 1-9)

### 1. D10 identity migration (item 1)
- Every Design Studio route (legacy AND imported-evidence) now resolves a
  strict, organization-scoped session (`studio_account`); anonymous callers are
  refused with 401 on all 11 legacy routes and all new ones (live-verified).
- `Northstar_backend/migrate_ds_identity.py`: dry-run-first migration. Rule:
  records already owned by a real organization stay; shared buckets
  ("default"/"anonymous"/empty) move ONLY when the deployment holds exactly one
  organization; unknown buckets ALWAYS quarantine (they may belong to another
  tenant). Nothing is deleted; apply is idempotent (re-plan shows 0 moves).
- Live reports: `reports/d10-identity-dry-run_20261010.json` (real store: no
  shared-bucket records at run time — the local store was reset by the image
  rebuild, so the honest dry-run shows zero records), `...dry-run2...` (labeled
  demo seeds quarantined with the reason, `fully_mapped: False` — the 3-org
  deployment cannot attribute them), `...apply-real...` (apply moved nothing),
  `...apply-demo...` (test-only `--orgs` override demonstrated the move path
  live; the demo rows were then deleted).
- `create_foundation_test_accounts.py` created two isolated foundation tenants
  (the A7 accounts live in the legacy store, which the foundation login does not
  use). Credentials live outside the repo and were never printed.
- Fixtures: `tools/test_d10_identity_migration.py` 12/0 (single/multi/zero-org,
  unknown bucket, idempotency, nothing deleted). Live negatives:
  `tools/verify-d10-live.cjs` 12/0 — tenant B cannot list, search, read, export
  or delete tenant A's records; anonymous → 401 everywhere.

### 2. Dev sign-in fails closed (item 2)
`SignIn.jsx`: only the EXACT demo pair takes the shim path; that path NEVER
reaches `/auth/login` whatever the backend posture, and the failure is explicit.
Real credentials are attempted only when the operator types them.
`tools/verify-shim-fail-closed.cjs` 8/0: zero login requests from the shim path,
explicit alert, no console line carries the demo password, a typed real account
still signs in.

### 3. Rate-limit opt-out cannot ship (item 3)
`prod_posture_ok()` now refuses `NORTHSTAR_DISABLE_RATE_LIMIT=1` in staging AND
production (the hosted overlay runs staging); the hosted compose pins it to
"0"; `tools/start-local.ps1` sets it to 0 on every normal start. Tests:
`test_rate_limit_posture.py` 5/0; the compose guard now asserts the deploy pin
(5/0).

### 4. Capability gaps closed (item 4)
- **Projects:** undo/redo (bounded history + Ctrl+Z / Ctrl+Shift+Z), a
  reference lock, and a version-bound compare sign-off (every edit stamps
  `meta.lastEditAt` via `commitDoc`, so any edit invalidates it). Export gate =
  compliance pre-flight + sign-off when locked. The objective pixel diff is
  ON DEMAND ("Run fidelity diff") with its verdict and limits stated — a
  composed canvas legitimately differs from the raw photograph, so the diff is
  a readout, not an automatic gate (DECIDED-BY-DEFAULT, see D17).
- **3D Product Scene:** `studio/engine/render3d.js` runs the actual-photo rule
  (BLOCK for listing purpose; rule `render-actual-photo`, source `img-guide`),
  the Amazon pre-flight, disclosure (same rules everywhere; unanswered blocks),
  fidelity (when a reference is locked), and product-accuracy compare sign-off.
  One kind-agnostic sign-off covers every view of the same scene state.
- Harnesses: `tools/verify-projects-gates.cjs` 16/0/0 FATAL;
  `tools/verify-render3d-gate.cjs` 14/0/0 FATAL — both twice.

### 5. Listing integration (item 5)
`studio/engine/listingContext.js` reads the seller's OWN local records only
(ListingForge browser records, brand-profile detail-page copy, asset metadata,
studio A+ projects). Every field carries source, observed date, freshness (a
stated 90-day engineering window) and limits; a missing field reads UNKNOWN.
The mismatch check flags a ranked creative term absent from the local listing
copy as NEEDS HUMAN REVIEW — never auto-fixed, never called an error; with no
listing copy the state is UNKNOWN. No marketplace or provider call exists in
this path.

### 6. Brand voice + keyword ingestion (item 6)
New import kinds `brand_voice` and `keywords` (JSON/CSV, idempotent, archived
with source label + date). `GET /brand-voice` returns the latest imported voice
with provenance. Briefs name their voice AND keyword provenance (an imported
file wins over the brand profile and is named with its label/date); imported
keywords feed the brief's matching. Absent voice fields and empty keyword
volumes stay UNKNOWN.

### 7. Performance loop (item 7)
Variant comparison carries the shared confidence band (very small/small/
moderate/large/UNKNOWN); `GET /variants/export` produces a results CSV with
per-variant aggregates, sample, confidence note, observed range, sources and
the NO-CAUSATION caveat; a NULL metric exports as an EMPTY cell.

### 8. Re-verification (item 8)
Pixel paths on the test build: **37/0/0 FATAL**; prod mode 23/0 with the pixel
paths correctly skipped; bundle contract 14/0 (prod carries neither hook nor
shim; test carries the hook, not the shim). Freshness register re-run
2026-10-10: `{"current": 35}` — nothing past cadence, zero re-pulls, no
login-gated page touched.

### 9. Full regression (item 9)
Evidence in `reports/regression_20261010_phase7/` (27 files):

| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 106 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs (mocked) | 25 / 0 |
| test-indexing-register.mjs | 28 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| test_design_studio_imports.py | 40 / 0 |
| test_d10_identity_migration.py (new) | 12 / 0 |
| test_rate_limit_posture.py | 5 / 0 |
| test_auth_guard.py | 16 / 0 |
| check-jsx-imports.py | 97 files, 0 / 0 |
| check-prod-bundle.cjs | 14 / 0 |
| check-compose-deploy.cjs | 5 / 0 |
| test-compositing.cjs prod / test / dev | 23 / 37 / 37, 0 FATAL each |
| verify-design-studio.cjs | 67 / 0 |
| test-migration-e2e.cjs | 12 / 0 |
| verify-operator-smoke.cjs | 11 / 0 |
| verify-search-terms.cjs (extended) | 46 / 0 |
| verify-d10-live.cjs (new) | 12 / 0 |
| verify-projects-gates.cjs (new) | 16 / 0 |
| verify-render3d-gate.cjs (new) | 14 / 0 |
| _check-recheck-migration.cjs | migration VERIFIED |
| verify-shim-fail-closed.cjs (new) | 8 / 0 |
| capture-section-evidence.cjs | 62 / 0, 18 screenshots refreshed |

**Total: 772 passed, 0 failed, 0 FATAL. Zero live or paid calls; generation
UNARMED; no failure needed a parent-commit comparison.**

## PHASE 8 — OVERNIGHT CONTINUOUS COMPLETION (items 1-9)

### 1. Registry updates (item 1)
New claims register `studio/engine/registryClaims.js` with source id, pulled-at
date, tier, cadence and date-sensitivity; pass+fail fixtures in
`tools/test-registry-claims.mjs` (42/0).
- **Title length 75 chars** incl. spaces, non-media categories, effective
  2026-07-27, tier FLAG, cadence 90d, REPORTED until an Amazon-owned page
  records it; applied to the listing mismatch check as a FLAG (75 passes, 76
  flags; nothing truncated; no compliance rule blocks it).
- **AI-people metadata window 2026-07-22 → 2026-07-27** recorded with the
  Product image guide as the authoritative method; stays REPORTED (assembled
  from dated, partly non-Amazon sources).
- **Image formats** JPEG/TIFF/PNG/non-animated GIF per the guide; the
  `no-animated-gif` rule now READS `doc.meta.exportFormat` (previously always
  passed) — PNG passes, animated GIF/unknown blocks (107/0 compliance
  fixtures).
- **10 MB size limit**: recorded UNCONFIRMED and NOT enforced; a 12 MB fixture
  proves no block and no rule references it.
- **A+ eligibility**: displays "confirm in A+ Content Manager" in the register
  and the A+ workspace note.

### 2. Postgres path (item 2)
- `DataLayer` gained a REAL Postgres branch (psycopg v3): working
  execute/executemany/commit/close, `?`→`%s` translation with literal-percent
  escaping, `SELECT changes()` answered from the statement rowcount, driver
  IntegrityError translated to `sqlite3.IntegrityError` (fingerprint and
  legacy-key idempotency work on both backends). The schema DDL is shared; the
  PG creator translates the SQLite-isms and runs idempotently on every boot.
- The data layer owns a dedicated `northstar_data` PG schema (the shared public
  schema already held foundation tables with different shapes).
- **Reads commit immediately** (live finding: an idle-in-transaction SELECT on
  ds_rechecks held locks that blocked `ALTER TABLE products` — two harness
  processes hung on the lock). The live-columns migration now checks
  information_schema first so a steady-state boot takes no ACCESS EXCLUSIVE
  lock.
- `docker-compose.yml` sets `DATABASE_URL` (local + hosted): the ds_* tables
  survive container recreation.
- Harness `tools/test_design_studio_pg.py` (in-container) 12/0: schema +
  idempotent re-init, isolation on every store, duplicate fingerprint returns
  the existing id, legacy key idempotency, changes() shim, D10 plan.
- **D10 against PG** (item 2 addition): `reports/d10-identity-pg-dry-run_
  20261011.json` — 3 orgs, counts per organization, no shared-bucket rows,
  fully mapped, **0 moves applied**; the quarantine path was demonstrated with
  probe buckets; HTTP-level cross-tenant negatives on the PG stack 18/0.

### 3. Listing context → tenant store (item 3)
`ds_listing_records` + DAO + four strict endpoints; the SearchTerms surface
runs a one-shot idempotent migration from the browser-local ListingForge
records and clears the local marker/mirror ONLY after the server confirms (the
ListingForge working store itself is never deleted). The panel reads the tenant
record first ("tenant listing record (server)") with the local record as an
explicit fallback. Live: migration created 1 record, re-run skipped, tenant B
cannot list/read/delete A's record (`verify-d10-live` 18/0; full surface
`verify-search-terms` 49/0).

### 4. Synthetic tenants (item 4)
Kept but clearly labelled (slug `ns-test-tenant-` + name `Northstar Test
Tenant`) because the live cross-tenant negatives use them;
`cleanup_test_tenants.py` removes ONLY tenants carrying both markers, dry-run
by default, and lists every untouched organization (live dry run: 2 marked
tenants identified, T2 Holdings untouched). DECIDED-BY-DEFAULT (D22).

### 5. Local fidelity trial (item 5)
`tools/fidelity-trial.cjs` + `research/design-studio/reference-photos/`
(owner drop-in). No reference photos supplied and no local media runtime
running → **LIVE TRIAL: NOT RUN** (no photos) and **runtime-generation path:
NOT RUN** (no runtime), each with its cause. The labeled 5-image fixture run
passes every executed check — fidelity pass, label-region pass,
background-replacement pass, disclosure pass, **export blocked pending human
compare sign-off**, tamper probe blocked — 77-141 ms per image. Sample size 5
(< 20): NO pass rate claimed, per the rule.

### 6. 3D Product Scene editing (item 6)
Undo/redo (bounded history + Ctrl+Z / Ctrl+Shift+Z) and Move up/down reorder on
every layer row. `tools/verify-3d-editing.cjs` 9/0: reorder actually swaps the
list, undo restores, redo re-applies, a removed layer comes back.

### 7. Performance-loop labelling (item 7)
The variants panel says "imported results only" + "user- or file-entered
metrics"; every comparison states its sample size and the no-causation rule
explicitly (`verify-search-terms` asserts the labels).

### 8. Re-verification (item 8)
Pixel paths on the test build 37/0/0 FATAL; prod 23/0 with the pixel paths
correctly skipped; bundle contract 14/0; freshness register re-run
`{"current": 35}` — zero re-pulls, no login-gated page touched.

### 9. Full regression (item 9)
Evidence in `reports/regression_20261011/` (31 files):

| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 107 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs (mocked) | 25 / 0 |
| test-indexing-register.mjs | 28 / 0 |
| test-registry-claims.mjs (new) | 42 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| test_design_studio_imports.py | 40 / 0 |
| test_d10_identity_migration.py | 12 / 0 |
| test_rate_limit_posture.py | 5 / 0 |
| test_auth_guard.py | 16 / 0 |
| check-jsx-imports.py | 97 files, 0 / 0 |
| check-prod-bundle.cjs | 14 / 0 |
| check-compose-deploy.cjs | 5 / 0 |
| test_design_studio_pg.py (new) | 12 / 0 |
| cleanup_test_tenants.py (dry run, evidence) | 2 marked tenants, T2 untouched |
| test-compositing.cjs prod / test | 23 / 37, 0 FATAL each |
| verify-design-studio.cjs | 67 / 0 |
| test-migration-e2e.cjs | 12 / 0 |
| verify-operator-smoke.cjs | 11 / 0 |
| verify-search-terms.cjs | 49 / 0 |
| verify-d10-live.cjs | 18 / 0 |
| verify-projects-gates.cjs | 16 / 0 |
| verify-render3d-gate.cjs | 14 / 0 |
| verify-3d-editing.cjs (new) | 9 / 0 |
| verify-shim-fail-closed.cjs | 8 / 0 |
| _check-recheck-migration.cjs | migration VERIFIED |
| fidelity-trial.cjs (new) | 5 / 0 fixtures; live trial NOT RUN (cause) |
| capture-section-evidence.cjs | 62 / 0, 18 screenshots refreshed |

**Total: 813 passed, 0 failed, 0 FATAL. Zero live or paid calls; generation
UNARMED for every external provider; no failure needed a parent-commit
comparison.**

## PHASE 9 — OVERNIGHT CONTINUOUS COMPLETION (items 1-7)

### 1. Title rules — VERIFIED via the owner capture (item 1)
- New registry source `title-guide` (Amazon "Product title requirements and
  guidelines", Seller Central help). Login-gated: captured by the owner
  2026-10-11; a public read returned the sign-in gate only (stated in the
  source note). `TITLE_RULES` (all FLAGS in the listing mismatch check, never a
  block, never an edit): 75 chars incl. spaces (brand name counts, bundles not
  exempt); no promotional phrases (illustrative example list, stated as not
  Amazon's full list); the characters ! $ ? _ { } ^ ¬ ¦ disallowed; the same
  word not more than twice; applies to all except media and except stores in
  Saudi Arabia, Egypt, Türkiye and the UAE; rollout kicked off 2026-07-27,
  gradual, 14-day brand-owner review of AI-suggested rewrites (REPORTED,
  date-sensitive).
- `titleRuleFlags()` emits one flag per rule with its rule id; pass+fail
  fixtures per rule in `tools/test-registry-claims.mjs` (65/0).

### 2. Master-brain read-only panels (item 2)
- `GET /api/design-studio/master-brain-context`: one tenant-scoped, read-only
  bundle (brand voice, imported keywords, search-term evidence with the
  click-only bias, listing records) with source/observed/limits per section;
  pure local-store reads, no provider call in the path.
- `MasterBrainPanel` renders it in ListingForge, AdPilot and SocialPulse with
  read-only + no-provider boundaries, freshness (the stated 90-day window) and
  an explicit UNKNOWN state per empty section.
- `tools/verify-master-brain-panels.cjs` 13/0 (all three rooms, seeded record
  shown, UNKNOWN shown, cleaned up); `verify-d10-live.cjs` 21/0 (tenant B never
  sees A's record; anonymous → 401 on the new route).

### 3. Flat-file column contract (item 3)
Item Highlights recorded as a separate 125-char, comma-separated field with the
flat-file/API column UNKNOWN until Amazon publishes it. ListingForge gains
"Export copy (CSV)": first line = the UNKNOWN notice, header carries an
`item_highlights` column whose value is EMPTY, trailing comment restates the
contract; the editor shows the same notice.
`tools/verify-title-contract.cjs` 8/0 (real download inspected).

### 4. Fidelity trial, mask-protected paths (item 4)
The trial now runs a mask-protected path per image: the reference is rendered
with the same engine geometry as a transparent-background product, so the
product pixels are byte-identical and the diff SKIPS transparent areas — an
edit outside the product mask PASSES, an edit inside it BLOCKS. 5/5 fixtures
pass every executed check (fidelity, label, background replacement,
mask-protected pass, mask violation blocked, disclosure, export blocked
pending sign-off, tamper blocked). **LIVE TRIAL: NOT RUN** (no reference photos
in the drop-in folder) and **runtime-generation path: NOT RUN** (no local media
runtime) — each with its cause; sample size 5 (< 20): no pass rate claimed.

### 5. Housekeeping (item 5)
- `cleanup_test_tenants.py` dry run only: 2 marked tenants identified (1
  membership / 1 user each), T2 Holdings untouched, nothing deleted
  (`reports/phase9-evidence/cleanup-dry-run.txt`).
- The harness rate-limit opt-out is absent from every deploy artifact: the
  hosted overlay pins "0", the base compose defaults to 0, the merged deploy
  composition shows `NORTHSTAR_DISABLE_RATE_LIMIT: "0"` for all six services,
  Dockerfile.api has no ENV for it, and `deploy/` carries none
  (`reports/phase9-evidence/deploy-ratelimit.txt`; the compose guard asserts it
  every run).

### 6. Re-verification (item 6)
Pixel paths on the test build 37/0/0 FATAL; prod mode 23/0; bundle contract
14/0; PG isolation negatives (in-container 12/0 + HTTP 21/0); freshness
register re-run (57/0 suite; zero re-pulls, no login-gated page touched).

### 7. Full regression (item 7)
Evidence in `reports/regression_20261011_phase9/` (33 files):

| Harness | Result |
|---|---|
| test-compliance-rules.mjs | 107 / 0 |
| test-disclosure.mjs | 65 / 0 |
| test-fidelity-freshness.mjs | 57 / 0 |
| test-generation.mjs (mocked) | 25 / 0 |
| test-indexing-register.mjs | 28 / 0 |
| test-registry-claims.mjs | 65 / 0 |
| test_design_studio_isolation.py | 37 / 0 |
| test_login_throttle_bypass.py | 16 / 0 |
| test_design_studio_imports.py | 40 / 0 |
| test_d10_identity_migration.py | 12 / 0 |
| test_rate_limit_posture.py | 5 / 0 |
| test_auth_guard.py | 16 / 0 |
| check-jsx-imports.py | 97 files, 0 / 0 |
| check-prod-bundle.cjs | 14 / 0 |
| check-compose-deploy.cjs | 5 / 0 |
| test_design_studio_pg.py | 12 / 0 |
| cleanup_test_tenants.py (dry run) | 2 marked tenants, T2 untouched |
| test-compositing.cjs prod / test | 23 / 37, 0 FATAL each |
| verify-design-studio.cjs | 67 / 0 |
| test-migration-e2e.cjs | 12 / 0 |
| verify-operator-smoke.cjs | 11 / 0 |
| verify-search-terms.cjs | 49 / 0 |
| verify-d10-live.cjs | 21 / 0 |
| verify-projects-gates.cjs | 16 / 0 |
| verify-render3d-gate.cjs | 14 / 0 |
| verify-3d-editing.cjs | 9 / 0 |
| verify-title-contract.cjs (new) | 8 / 0 |
| verify-master-brain-panels.cjs (new) | 13 / 0 |
| verify-shim-fail-closed.cjs | 8 / 0 |
| _check-recheck-migration.cjs | migration VERIFIED (harness now cleans its PG-persisted fixtures) |
| fidelity-trial.cjs | 5 / 0 fixtures incl. mask paths; live trial NOT RUN (cause) |
| capture-section-evidence.cjs | 62 / 0, 18 screenshots refreshed |

**Total: 860 passed, 0 failed, 0 FATAL. Zero live or paid calls; no cloud
generation; generation UNARMED for every external provider; no failure needed a
parent-commit comparison.**

## PHASE 10 — FILE-ONLY AMAZON INTEGRATION (2026-10-11)

### Architecture decision (overrides earlier plans)
NorthstarOS **never signs in to Amazon and never links a seller's Amazon
accounts**: no SP-API, no Ads API, no OAuth/LWA, no Amazon credentials. The
seller downloads files from Amazon, uploads them here, Northstar writes a NEW
change file, and the seller uploads it to Amazon manually.

### 1. Linkage inventory + guard
`reports/amazon-linkage-inventory_20261011.md` lists every path that referenced
Amazon sign-in/APIs/live pulls: the SP-API importer (LWA + SP-API GETs), the
Ads API importer (OAuth + advertising-api calls), the unified `amazon_api`
adapter, the blacklist re-check's live branch, the `data_refresh` provider
registry (names only), the already-gated live-pull family (A1), and the benign
help-URL citations in the UI.
`amazon_linkage_gate.py`: `NS_AMAZON_LINKAGE_ENABLED` default OFF;
`assert_linkage_posture()` REFUSES to boot staging/production with it on (wired
into `main.lifespan`); all four linkage points refuse even WITH credentials
while the gate is off, stating the file-only reason.
`tools/test_no_amazon_linkage.py`: **2127 checks / 0 failed** — static scan of
the backend (outside the gated set) and the UI for Amazon API hosts, OAuth
paths and credential env names; the file-only modules import no network library
and contain no http(s) URL except inert OOXML namespace identifiers; posture +
refusal-with-credentials tests.

### 2-7. The file-only workflow
- **Parsers (read-only, stdlib only)**: Ads bulksheets (.xlsx via zip+XML,
  .csv), search-term sheets, listing/inventory templates (.txt TSV / xlsx),
  Brand Analytics, A+ ASIN lists; type detection with stated reasons; required
  columns validated and missing ones reported as UNKNOWN; observed ranges from
  ISO date cells; checksums; a legacy .xls (BIFF) is honestly refused with the
  fix stated.
- **Change-file writers**: minimal xlsx writer (openpyxl-openable, proven),
  TSV writer; the delta writer keeps the SOURCE column order, writes changed
  rows only, copies IDs exactly, and refuses a blank Operation.
- **Proposals + approval**: before/after, reason, evidence (file, checksum,
  download date); missing/unmatched IDs BLOCK a row; a spend increase above the
  seller's own limit requires a SECOND confirmation; a stale source (past the
  stated 14-day window) warns; title changes carry the four rule FLAGS
  (length 75 / banned characters / repeated word / promotional) — never blocks,
  never edits.
- **Round-trip validator**: re-reads the written file, matches rows by ID
  value, proves the only differences are the approved ones, and records source
  + written checksums and a diff digest. Tampering is caught; the no-op case
  writes zero rows.
- **A+ output**: an asset pack with placement instructions and required alt
  text — NOT an uploadable module file; the ASIN bulk-upload limit is recorded
  UNKNOWN (sources conflict).
- **UI**: `Ads › Amazon files` sub-view (upload, archive, row edits, proposals
  with flags/blocks/guardrail, approve/reject, write + round-trip display,
  download, A+ pack). Tenant-scoped tables + endpoints; the D10 migration
  covers the new tables.
- One real bug found by the UI harness and fixed: the proposals GET returned
  raw DB rows (fields nested under `payload`) while the surface reads the flat
  proposal shape — the serializer now flattens.

### Verification
| Harness | Result |
|---|---|
| test_no_amazon_linkage.py (new) | 2127 / 0 |
| test_amazon_files.py (new) | 34 / 0 |
| verify-amazon-files.cjs (new) | 22 / 0 |
| verify-amazon-files-ui.cjs (new) | 11 / 0 |
| verify-d10-live.cjs (extended) | 28 / 0 |
| Full regression (33 scored harnesses) | **3061 passed / 0 failed / 0 FATAL** |

**NOT RUN with cause**: a real Amazon upload (the owner performs it manually by
design). Zero live or paid calls; no cloud generation; generation unarmed.

## PHASE 11 — DESIGN STUDIO + FILE-ONLY REMAINING BUILD (2026-10-11, overnight)

Directive: 15 items, plan-first then one continuous build loop; full test pass
only at the END. Branch `feature/overnight-remediation-20261009`; commits
`41f54c8` → `b93f45d` → `d19d6cf` → `7193303` (+ this checkpoint).

### 1. Self-hosted fonts; zero third-party requests (item 1)
DM Sans + Libre Baskerville (8 woff2 files) vendored under
`northstar-os-ui/public/fonts/` with a rewritten `fonts.css`; the Google Fonts
`<link>` and the two CSS `@import`s removed. `tools/check-no-third-party.cjs`
(new) scans the BUILT dist: index.html has zero http(s) URLs (XML namespace
identifiers excluded), CSS has no external `url()`/`@import`, JS has no
request-shaped external reference, `dist/fonts/fonts.css` is 20 local refs / 0
external. **5/0.** The API harness now asserts ZERO external requests at
runtime (was: font CDN allowed).

### 2. Processing-report import (item 2)
New detected kinds `ads_error_report` (bulksheet shape + error column) and
`listing_processing_report` (sku + error columns). `match_processing_report()`
matches each error row to the change row and the proposal that produced it —
entity-aware ID preference (a keyword row never matches via its parent campaign
ID), unmatched rows REPORTED, never guessed; cause quoted exactly; fix hints
only for recognised phrases. `build_corrected_change()` + endpoint write a NEW
corrected version (original untouched), round-trip validated. A correction for
a column the file does not carry is refused with a stated reason. Reports can
never produce proposals or be written as change files (422 with reasons).

### 3. Seller Central upload formats (item 3)
`.xlsx` + tab-delimited `.txt`/`.tsv` accepted; an old/partial template is
flagged ("OLD or partial template… re-download from Seller Central") and the
missing operation column is listed in `missing_columns`; legacy `.xls` stays
refused with the fix stated (unchanged from Phase 10).

### 4. More change-file types (item 4)
SB/SD entities added (creative, product collection, bidding adjustment,
negative keyword/targeting); product-detail listing fields added
(bullet1-5, description, generic keywords, brand, item type) with required-
column checks (sku + operation are the hard requirements; absent core
attributes are listed so the operator knows what the file does not cover).

### 5. Before/after performance comparison (item 5)
`compare_performance()` + endpoint + UI: per-entity before/after with sample
size + confidence band, observed ranges, present_in labels, explicit NO
CAUSATION notice, and the 14-day stale window labelled an engineering choice.
A metric missing from one file is UNKNOWN, never 0.

### 6. A+ asset pack copy slots (item 6)
Pack gains copy slots (headline/body/cta): operator text carried with its
source, empty slots stay UNKNOWN with a write-it-yourself note. Still NOT an
uploadable module file; ASIN bulk-upload limit stays UNKNOWN.

### 7. Brief-to-asset loop (item 7)
`brief_to_assets()` + `POST /terms/brief/assets`: templates ONLY (no
generation), copy + on-image text layers from the brand promise/voice/audience
and the imported term, each variant created in the variants table (name +
notes with the brief reference) so a later results import can match it by id or
exact name.

### 8. Title and listing rules in all writers (item 8)
The Python port applies the four title rules as FLAGS in every writer path that
touches a title; Item Highlights is now explicitly UNKNOWN on the Python side
(`item_highlights_column()`), a source column with that header is preserved but
never mapped or interpreted.

### 9. Video & UGC, Social, Packaging output packs (item 9)
`studio/engine/outputPacks.js`: storyboard pack, social asset pack, packaging
spec — built from the operator's own fields + the section pre-flight; each pack
carries its pre-flight summary, UNKNOWN for missing fields, and states that
nothing is rendered or generated. SectionWorkspace gained the Pack control
(disabled exactly when the pre-flight blocks). Browser harness **17/0**
(downloads captured and content-verified for all three sections).

### 10. Master-brain panels in remaining rooms (item 10)
Panel added to KeywordTracker, CompetitorMonitor, ListingGuardian,
ProfitabilityDashboard, CommerceOps, Monitoring (9 rooms total);
`verify-master-brain-panels.cjs` extended to cover all of them.

### 11. Seller onboarding + sample pack (item 11)
First-run guide in the AmazonFiles surface: which files to download and where,
what Northstar returns, and 11 downloadable synthetic samples
(`northstar-os-ui/public/samples/amazon-files/`, generated by
`tools/_make_amazon_fixtures.py`, committed).

### 12. Hosted-readiness package (item 12)
`docs/hosted-readiness/` (README, POSTGRES, DEPLOY_CHECKLIST, BACKUP_RESTORE,
INCIDENT_RUNBOOK, SECRET_HANDLING). Compose guard extended: the deploy
composition publishes NO port besides 80/443 across ALL services and carries no
harness opt-out set to 1 (local too). **8/0.**

### 13. Generation arming package (item 13)
`docs/GENERATION_ARMING_CHECKLIST.md` gained per-tenant job limits (concurrent,
queued, credits/day, GPU-minutes/day, jobs/hour — all server-side, fail-closed,
reported not silent) and a config sketch (names only). Remains UNARMED.

### 14. Research deliverables (item 14)
`research/design-studio/20261011/` assembles SOURCES.csv, COMPETITOR_MATRIX.csv,
WORKFLOWS.md, AMAZON_REQUIREMENTS.md, SELLER_PAIN_POINTS.md, SEO_AD_LOOP.md,
FEASIBILITY.md, OPPORTUNITIES.md, RULES.md + a new RESEARCH_SUMMARY.md and
README.md stating the label system (VERIFIED/REPORTED/UNKNOWN), what changed
since 2026-10-08, coverage limits and items NOT inspected. No fabricated
pricing or statistics.

### 15. Full regression (last)
`tools/run-regression.ps1` (new) runs every harness with one raw output per
harness into `reports/regression_20261011_final/` (SUMMARY.txt carries exit
codes). Focused results during the build: section packs 17/0, AmazonFiles UI
22/0, AmazonFiles API 44/0, amazon files unit 66/0 (later 68/0 with the Item
Highlights checks), compose 8/0, no-third-party 5/0. The full-run numbers are
recorded in the final report and SUMMARY.txt.

**NOT RUN with cause**: a real Amazon upload (owner-performed by design); the
live fidelity trial (no photos/runtime). Zero live or paid calls; generation
unarmed; no Amazon linkage; no third-party UI requests.
