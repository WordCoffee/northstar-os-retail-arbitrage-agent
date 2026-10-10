# Design Studio ? Phase Checkpoint

## Phase 0: MERGE THE STRUCTURE ? COMPLETE (21/21 verified)
`/design-studio` route; Creative Studio ? Projects section; Product Designer ?
3D Product Scene; rail 22 ? 21; `ds_projects`/`ds_assets`/`ds_jobs` backend
store + CRUD API; sample data purged.

## Phase 1: DEEP RESEARCH ? COMPLETE (GATE 1 approved)
149 vetted sources; 10 competitor files; 7 track files; SYNTHESIS.md;
coverage-report.md. All under `research/design-studio/`.

## Phase 2: DESIGN SYSTEM + WORKSPACE REDESIGN ? IN PROGRESS

### Delivered this phase
1. **`studio/engine/specRegistry.js` (NEW)** ? the single source of truth for
   every Amazon spec the studio can export. Each row carries a source id and a
   pulled-at date. Contents:
   - 46 specs across 10 groups: Listing gallery (2), A+ Basic (10),
     A+ Premium (11), Brand Story (2), Store header (2), Store tiles (6),
     SB video (2), Brand asset (1), Custom image (3), DSP display (6).
   - `SAFE_ZONES` (normalised 0..1) for Store hero (16% crop each side + 18%
     logo), Store tiles (19% rectangle / 12% square link-title overlay),
     SB video landscape + vertical (no text bottom-right).
   - `AMAZON_CAPS` (A+ 2 MB/RGB/72 dpi/alt text, video 6-45 s/MP4/H.264/1 Mbps/96 kbps/44.1 kHz,
     ads char caps 50/25/100/60/30, Store limits).
   - `AI_POLICY` (IPTC `contains-synthetic-performer`, Brand Registry
     actual-photo rule, product-accuracy rule).
   - `FLAT_FILE_IMAGE_COLUMNS` (main_image_url, other_image_url1..8, swatch).

2. **`studio/engine/compliance.js` (EXTENDED)** ? 9 new rules added to the
   register (22 rules total), each with a source and accessed date:
   store-safe-zone, store-no-embedded-text, sbv-video-spec,
   sbv-text-safe-area, ai-people-disclosure, brand-registry-not-a-mockup,
   aplus-alt-text, aplus-file-size, ad-char-caps. `rulesInScope()` now covers
   the Amazon Store and Amazon A+ scopes.

3. **`studio/components/StudioShell.jsx` (NEW)** ? the editor-grade shell used
   by every section: StudioTopBar (undo/redo, zoom, safe-zone toggle, export,
   verdict), StudioLeftRail, StudioCanvas (zoom/pan, safe-zone overlays drawn
   from the registry, Ctrl+wheel zoom, caption with source), StudioInspector +
   InspectorSection, StudioBottomStrip, VerdictPill, CompliancePanel,
   SpecPicker, StudioEmpty, `useStudioZoom` (Ctrl +/-/0), `useUndo`.

4. **`styles/studio.css` (EXTENDED)** ? 183 lines of shell CSS: grid frame,
   top bar, left rail, checkerboard canvas, keep-out / keep-in zone styling,
   inspector, bottom strip, compliance panel, spec picker, empty state,
   reduced-motion guard.

5. **`pages/internal/design-studio/ListingImages.jsx` (NEW)** ? the reference
   workspace. Left rail: Format (spec registry), Product (live rows only, from
   `/api/products/finder` which already filters `data_kind='live'`), Slots
   (flat-file columns), Rules (documented Amazon constraints). Center: the
   format at its true aspect ratio + safe-zone overlays. Inspector: compliance
   pre-flight with block/warn/pass and source lines, format facts, A+ rules,
   bulk export contract. Bottom strip: the six gallery slots. Export is
   DISABLED while the pre-flight blocks.

6. **`DesignStudio.jsx`** ? Listing Images section flipped from "not built" to
   built; wired to the new workspace.

### Verification (all real command output)
- `python tools/check-jsx-imports.py northstar-os-ui/src` ? 87 files, no
  undefined JSX references.
- `npm run build` ? success (113 modules).
- `node tools/verify-design-studio.cjs` ? **16 passed, 0 failed**. Proves:
  sign-in, 9-section picker, workspace mounts, all five shell regions render,
  the spec picker is registry-driven, the compliance verdict pill renders
  ("Pre-flight blocks" on an empty main image ? correct, an empty doc has no
  white background), 22 rule rows with sources, safe-zone toggle present, six
  gallery slots, format switch safe, deep-link re-mount, zero uncaught errors.
- `node tools/verify-operator-smoke.cjs` ? **11 passed, 0 failed**, 21/21 rail
  destinations still render (no regression from Phase 0).

### Not done in Phase 2 (honest)
- Six of nine sections still render "Not built yet": A+ / Brand Story,
  Storefront, Ads, Video & UGC Clips, Social, Packaging & Mockups. The spec
  registry and safe zones for all of them are already in place.
- No per-section design-token pass (dark/light, motion rules, icon set) beyond
  the shell CSS.
- No migration of Creative Studio / Product Designer localStorage state to the
  `ds_*` backend store yet.
- Live generation remains unarmed; no ComfyUI workflow set exists.

### Files touched this phase
- `northstar-os-ui/src/studio/engine/specRegistry.js` (new)
- `northstar-os-ui/src/studio/engine/compliance.js`
- `northstar-os-ui/src/studio/components/StudioShell.jsx` (new)
- `northstar-os-ui/src/styles/studio.css`
- `northstar-os-ui/src/pages/internal/DesignStudio.jsx`
- `northstar-os-ui/src/pages/internal/design-studio/ListingImages.jsx` (new)
- `tools/verify-design-studio.cjs` (new)

## Resume at
Phase 2 continued: build the next workspace (A+ / Brand Story) on the same
shell, or wire live product data into Product Designer per the Phase 2 brief.
