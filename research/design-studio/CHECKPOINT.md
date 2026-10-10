# Design Studio ? Phase Checkpoint

## Phase 0 ? MERGE THE STRUCTURE ? COMPLETE (21/21)
## Phase 1 ? DEEP RESEARCH ? COMPLETE (GATE 1 approved)
## Phase 2 ? DESIGN SYSTEM + WORKSPACES ? COMPLETE (9/9 sections)

## Phase 2 ? Phase 3 PREP ? COMPLETE

### 1. SP video sourced; UNSOURCED block removed
`spv-video` now carries a real Amazon source with a pulled-at date:
- Source `spv-guide` (VERIFIED, advertising.amazon.com/library/guides/
  sponsored-products-video) + `spv-guidelines` (VERIFIED, help page).
- 1-5 videos per product per ad group; **7 seconds and longer, no published
  maximum**; horizontal 16:9; 1920x1080 recommended; MP4/MOV; **<=500 MB**;
  **audio is removed**; **product must occupy 50% or more of the frame**.
- Vertical 9:16 recorded as `available: false`, `dateSensitive: true`
  ("to be available in 2026") ? a WARN, never a block.
- `durationMax: null` is honoured as "no published maximum" and is NOT read as
  zero. Fixture: 120s must pass; 5s must block.
- **Unsourced specs: 0.** The `spec-sourced` rule remains as the guard.

### 2. Display video reconciled
Two Amazon pages publish different figures for the same family. Both are
STORED with their source and the STRICTER is ENFORCED:
- Video bitrate: **1 Mbps** (`display-video-creative`) vs **4 Mbps**
  (`ads-overview`, OLV/CTV/STV) -> enforcing **4 Mbps**.
- Audio bitrate: **92 kbps** (`display-video-creative`) vs **192 kbps**
  (`streaming-tv`) -> enforcing **192 kbps**.
- SOURCE DEFECT recorded: the display table repeats the label
  "Minimum duration" on two rows (6s then 45s). Read as min 6s / max 45s and
  the defect is stated in the row's `reconciliation` field.
- Display video is now **VERIFIED** (both figures are Amazon-owned).
- **Amazon Video Ads stays its own row** (`amazon-video-ads`, VERIFIED,
  custom-media page: 1920x1080, >=15 FPS, audio 128 kbps/44.1 kHz, 2 Mbps
  recommended, detail-page 970x250 placement).

### 3. main-white-bg regression fixtures
Three added fixtures, on top of the base pass/fail pair:
- non-white solid `#123456` -> blocks
- **near-white `#FEFEFE` -> passes**; `#ECECEC` -> blocks (tolerance is per
  channel >= 240, not "light")
- **gradient** `['#ffffff','#fafafa']` -> passes; `['#ffffff','#3a3a3a']` -> blocks
  (a gradient passes only when EVERY stop is near-white)

### 4. Rules marked "checked" vs "needs artwork / human review"
Every rule declares what it NEEDS before its result means anything
(`RULE_NEEDS`: nothing | artwork | export | human). An empty canvas now
reports **"Needs artwork"** and never green. The panel separates
`Blocks export`, `Needs review`, `Not yet decidable`, and `Decided and
passing`, and the counter reads "N/M rules decided". Verified in-browser for
all 8 shell sections: **empty canvas does not report green**.

### 5. Projects persisted to ds_*/ with migration + tenant isolation
- **Tenant isolation FIXED**: every by-id DAO operation is now account-scoped
  (`get_by_id`/`update`/`delete` take `account_id`), `account_id` is not
  reassignable through a patch, and a foreign record returns **None / 404** ?
  never a 403 that would confirm existence.
- Router: **17 scoped call sites, 0 unscoped by-id calls** (asserted).
- **Migration**: `POST /api/design-studio/migrate` imports browser-local
  records idempotently by `legacyKey`, rejects unknown sections rather than
  guessing, and reports created/skipped/errors. Client module
  `studio/engine/migrate.js` reads the known localStorage keys, imports once,
  and **only clears the local copy after the server confirms**. Verified live:
  run 1 created 1, run 2 skipped 1 (no duplicate).

### 6. Harness login test mode
`NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS=1` raises the login ceiling to 200
requests/window. Fail-closed by design:
- refused outright in production / production_tenant / staging, whatever the
  env var says (case-insensitive)
- requires the exact value "1" (not "0", "", "no", "true ")
- only ever RAISES the limit ? production still enforces 5/window with the var set
- logs a warning on first activation
The edge rate limiter's pre-existing `NORTHSTAR_DISABLE_RATE_LIMIT=1` opt-out is
prod-guarded by `assert_prod_posture()` (the app refuses to boot in production
with it set). Both are wired into docker-compose, defaulting to 0.

### 7. Three latent crashes found and fixed
The non-creative degradation fix (returning 200 with real data where the API
previously 503'd) EXPOSED pages that could not render real data:
- `SharedDataLayer`: rendering the `live_pulls` ARRAY where a count was
  expected -> React error #31. Backend now emits distinct
  `live_pull_count` / `pipeline_run_count` keys; the page tolerates either shape.
- `ProviderAdapters`: `(v && v.length) ? v.map(...)` ? a STRING satisfies
  `.length`, then throws `a.map is not a function`.
- `admin/Overview`: the same antipattern.
`tools/check-jsx-imports.py` now also scans for this class statically and gates
the build.

### Verification ? all harnesses, full output, FATAL counted
| # | Harness | Result |
|---|---|---|
| 1 | `test-compliance-rules.mjs` | **72 passed, 0 failed** ? 34/34 rules, 13/13 groups, 48 specs sourced, 0 unsourced, 2 stricter-figure checks |
| 2 | `test_design_studio_isolation.py` | **17 passed, 0 failed** |
| 3 | `test_login_throttle_bypass.py` | **16 passed, 0 failed** |
| 4 | `check-jsx-imports.py` | 94 files, no undefined refs, no unguarded renders |
| 5 | `verify-design-studio.cjs` | **61 passed, 0 failed, 0 FATAL** ? zero console errors after sign-in |
| 6 | `verify-operator-smoke.cjs` | **11 passed, 0 failed**, 21/21 rail destinations |

### Generation status
**UNARMED.** No live or paid call. Every spec carries a source id, a
pulled-at date and a VERIFIED / REPORTED / UNSOURCED label.

### Files touched
- `studio/engine/specRegistry.js` ? SP video sourced, Display video reconciled,
  confidence labels, group-order guard
- `studio/engine/compliance.js` ? 4 new rules (34 total), RULE_NEEDS coverage
  states, SP/Display video families, main-white-bg fix
- `studio/engine/migrate.js` (new)
- `studio/components/StudioShell.jsx` ? verdict `incomplete`, coverage panel
- `pages/internal/design-studio/{SectionWorkspace,ListingImages}.jsx`
- `pages/internal/{SharedDataLayer,ProviderAdapters}.jsx`, `pages/admin/Overview.jsx`
- `pages/internal/DesignStudio.jsx` ? migration on mount
- `Northstar_backend/{data_layer,design_studio_api,noncreative_reads}.py`,
  `foundation/login_throttle.py`, `foundation/api/router.py`
- `docker-compose.yml` ? the two test-mode flags
- `tools/{test-compliance-rules.mjs,test_design_studio_isolation.py,test_login_throttle_bypass.py,verify-design-studio.cjs,check-jsx-imports.py}`

## Resume at
Phase 3: arm the local ComfyUI pipeline behind explicit Run + cost preview, and
give the sections a real canvas (they currently render the format, safe zones
and pre-flight, but hold no artwork). The backend store, tenant scoping and the
migration path are all in place.
