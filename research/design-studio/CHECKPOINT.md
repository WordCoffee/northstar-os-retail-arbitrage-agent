# Design Studio ? Phase Checkpoint

## Phase 0 ? MERGE THE STRUCTURE ? COMPLETE (21/21 verified)
## Phase 1 ? DEEP RESEARCH ? COMPLETE (GATE 1 approved), 149 sources

## Phase 2 ? DESIGN SYSTEM + WORKSPACE REDESIGN ? COMPLETE

### 1. Registry fixes (directive item 1)
- **SB video aspect**: 16:9 is the default (`aspectDefault: true`, VERIFIED, sbv).
  9:16 is a separate row (`aspectDefault: false`, `aspectWarn: true`,
  date-sensitive) and surfaces as rule `sbv-vertical-date-sensitive` at level
  **flag ? never a block**.
- **Hero safe zone**: BOTH documented figures recorded with source id and
  pulled-at date, and the overlay uses the STRICTER union and says so:
  - `stores-hero` (2026-10-10): 16% cropped each side below 1500px + logo covers
    a further 18% of the left ? left 34%, right 16%.
  - `stores-pdf` (2026-10-10): "Hero Image Safe Area: 50% width" ? 25% each side.
  - Stricter union: **left 34%, right 25%, always-visible band 41% wide**
    (x 0.34 ? 0.75). The `figures` array is exposed so the UI shows both.
- **Separate video rows**: `sbv-landscape` (SB), `sbv-vertical` (SB),
  `spv-video` (**UNSOURCED** ? export refused), `display-video` (REPORTED),
  `amazon-video-ads` (VERIFIED). One row per ad product.
- **VERIFIED / REPORTED / UNSOURCED** confidence label on every spec, with
  source id, pulled-at date and a `date-sensitive` marker.

### 2. Per-rule fixture test (directive item 2)
`tools/test-compliance-rules.mjs` ? a pass fixture AND a fail fixture for every
rule in the register (30 rules, not 22 ? the register grew during the build).
Rules with no fail path by construction declare `alwaysPass` with the reason and
are asserted, never skipped. Also asserts every rule has a source + accessed
date, and that every spec group is exposed through `SPEC_GROUPS`.

**It found two real bugs, both fixed:**
1. `main-white-bg` passed a NON-white background because
   `(gradient || []).every(...)` is vacuously true on an empty array ? a
   listing-suppression-class bug.
2. `SPEC_GROUPS` silently dropped the new `SP video`, `Display video` and
   `Amazon video` groups because they were missing from the order list, so
   those rows were invisible in every picker. Now appended with a warning.

### 3?4. All 9 sections built on the shell (directive items 3 + 4)
One generic `SectionWorkspace.jsx` drives every section; each section file is
configuration, so a spec can only come from the registry and a rule only from
the engine.
- **A+ / Brand Story** ? 23 registry modules (Basic, Premium, Brand Story),
  alt-text field REQUIRED (accessibility requirement; explicitly no SEO claim),
  2 MB limit, module-count and Premium-gating notes.
- **Storefront** ? 8 specs, hero + 4 tile sizes + video tiles, hero safe-zone
  overlay with both figures.
- **Ads** ? 15 specs across SB / SP / Display / Amazon video / custom images /
  DSP display / brand asset. Video duration field; char-cap fields from the
  registry; 9:16 warn.
- **Video & UGC Clips** ? 11 specs, hook + duration + caption fields, mute-first
  and safe-area rules. Generation stays unarmed.
- **Social** ? 6 specs; states honestly that Amazon specs do not cover social and
  that Amazon Attribution is not wired (no reach/conversion claim).
- **Packaging & Mockups** ? 6 specs; Brand Registry actual-photo rule and the
  product-accuracy rule are BLOCK-level notes.
- **Listing Images** (built earlier this phase) and **3D Product Scene** and
  **Projects** unchanged.

Hard behaviours verified in the browser: an UNSOURCED spec disables Export; the
9:16 vertical surfaces as a warn while the verdict does not newly block; A+
alt-text and the 2 MB cap appear in the pre-flight.

### 5. Non-creative degradation fix (found by the harness)
The harness surfaced a 503 on `/api/v1/noncreative/activity`. Root cause: the
`costco_*` pipeline tables do not exist in this deployment, and the strict
`_rows` contract turned "table never created" into a hard 503 ? taking the
Command Center activity feed, SourceScout sources, Commerce Ops, Listing
Guardian health and Competitor Monitor down with it.

Fix: a new `_optional_rows` / `_optional_scalar` pair distinguishes
**table-never-created** (legitimate empty state ? 200 with an `unavailable`
reason NAMING the table) from **table-exists-but-unreadable** (still a hard
503). All 8 non-creative endpoints now return 200 and carry an honest reason.

### Verification ? all three harnesses, full output, FATAL counted
| Harness | Result |
|---|---|
| `tools/test-compliance-rules.mjs` | **57 passed, 0 failed** ? 30/30 rules covered, 13/13 groups exposed, 48 specs sourced, 0 broken |
| `tools/verify-design-studio.cjs` | **45 passed, 0 failed, 0 FATAL** ? all 9 sections, zero console errors AFTER sign-in (was 1 before the fix) |
| `tools/verify-operator-smoke.cjs` | see final report (throttled to 5 logins/300s by the auth limiter) |

Pre-auth console noise is reported separately (3 ? 401 on `/me` from the
signed-out SPA) ? expected, not hidden.

### Generation status
**UNARMED.** No live or paid call was made. No cron, no on-load provider call.
Every spec carries a source id and a pulled-at date; every rule carries a source
and an accessed date.

### Files touched this phase
- `studio/engine/specRegistry.js` ? confidence labels, hero dual figures,
  5 separate video rows, group-order guard
- `studio/engine/compliance.js` ? 2 new rules (32 in register), spec-registry
  resolution for `safe`/`allowedDims`/`media`, `main-white-bg` fix
- `studio/components/StudioShell.jsx`
- `pages/internal/design-studio/SectionWorkspace.jsx` (new, drives 6 sections)
- `pages/internal/design-studio/{APlus,Storefront,Ads,VideoUgc,Social,Packaging}.jsx` (new)
- `pages/internal/design-studio/ListingImages.jsx`
- `pages/internal/DesignStudio.jsx`
- `styles/studio.css`
- `Northstar_backend/noncreative_reads.py`
- `tools/test-compliance-rules.mjs` (new), `tools/verify-design-studio.cjs`

## Resume at
Phase 3 (or Phase 2 polish): the six new sections are wired to the registry and
the pre-flight but hold no artwork yet; the `ds_projects`/`ds_assets`/`ds_jobs`
store is live but the sections still keep state in memory. Next: persist a
project per section to the backend store, then arm the local ComfyUI pipeline
behind explicit Run + cost preview.
