# ux-09 — Design Studio canvas workspace (builder pass 1)

Date: 2026-11-09 · Branch: `ty/ux-09-design-studio-canvas` · Base: `6658f7c2`

## Spec vs disk, reconciled first

The queue entry lists write paths `northstar-os-ui/src/rooms`, `src/pages`, `src/components`.
`src/rooms/` does not exist in this tree. The live surface is:

- page route `src/pages/internal/DesignStudio.jsx` → section
  `src/pages/internal/design-studio/CanvasWorkspace.jsx`
- canvas component `src/studio/components/Stage.jsx`
- model/renderer `src/studio/engine/doc.js`
- workspace data `src/lib/studioCanvas.js`

Most of the unit had already landed on disk before this lane (U7/U8), including PDF export,
dieline overlay and package panels, and the asset-dashboard / dielines links. This pass did not
pretend otherwise: it audited the six spine points, closed the two real gaps, and added the
missing proof. The "leave PDF/dieline/dashboard for next pass" note is therefore **not** a
claim that those are unbuilt — they were already present and are outside this commit.

## Document model (one paragraph)

A design is a flat list of layers in normalised coordinates (0..1 of the canvas), so one master
renders correctly at any raster size. Each layer carries `id`, `kind` (`bg`/`shape`/`text`/`image`),
`x/y/w/h/z`, `visible`, `locked`, `opacity`; text layers carry `text`, `size`, `weight`, `color`,
`align`; image layers carry `assetId` and `fit`. `src/studio/engine/doc.js` owns the immutable
factories (`createDoc`, `addLayer`, `updateLayer`, `removeLayer`, `reorderLayer`, `rescaleDoc`) and
the pure renderer. `src/lib/studioCanvas.js` wraps that model with registry-backed content types,
`createDesign`/`addText`/`addImage`/`addShape`, a value-based undo history and the autosave record
written to `localStorage` under the versioned key `ns-ds-canvas` (`v: 1`, 14-day TTL, record
discarded whole if it is corrupt, stale, foreign or references an unknown content type).

## The six points

| # | Point | State | Evidence |
|---|-------|-------|----------|
| 1 | Document model + versioned localStorage | works | `engine/doc.js`, `lib/studioCanvas.js`, `workspace.test.js` round-trip/refusal tests |
| 2 | Canvas renders text / image / rectangle + selection | works | `renderDoc` tests (rect fill, text `fillText`, decoded image, placeholder for a missing asset); `Stage` hit-test/selection |
| 3 | Move/resize by pointer; **8 px** snap to canvas edges **and other layers** | works — built this pass | new `src/studio/engine/snap.js`, wired into `Stage.jsx` move + bottom-right resize; 10 tests |
| 4 | Zoom fit / 100 % / ± and undo/redo | works — 100 % added this pass | `Stage` zoom rail now shows true raster scale and has a real `100%` (1 doc px = 1 CSS px) button; undo/redo already in `studioCanvas` history |
| 5 | Debounced autosave + visible saved state | works | 400 ms debounce in `CanvasWorkspace`, status line says saved time / oversized image / unavailable |
| 6 | PNG export via `canvas.toBlob`, real download | works (pre-existing) | `doExport('png')` → `canvas.toBlob` → `downloadBlob`; not unit-tested because it needs a browser DOM |

### What this commit changed

- **8 px snapping, in pixels.** The previous snap was normalised 1.2 % and only knew canvas
  start/centre/end. `snap.js` converts to display pixels, compares layer/canvas start, centre and
  end on both axes, applies the nearest alignment within 8 px, and returns the guide that actually
  fired (`axis`, `at`, `name`). Move preserves size; resize only changes `w/h`.
- **True 100 % zoom.** The stage now reports raster scale (document px → CSS px), so "Fit" is a
  fit and `100%` is actual size rather than the same number twice. The workspace status line uses
  the same figure.

## Commands actually run

```
npm ci
added 66 packages, and audited 67 packages in 3s
5 vulnerabilities (3 moderate, 2 high)

npm run build
✓ 277 modules transformed.
✓ built in 1.41s
(warnings only: unresolved /ui/fonts/*.woff2 at build time, and vite:reporter notices that
fidelity.js / disclosure.js / compliance.js / compose.js are both statically and dynamically
imported — both pre-existed this change)

npx vitest run src/studio
RUN  v5.1.0
Test Files  3 passed (3)
      Tests  25 passed (25)
```

`vitest` is not in `package.json` or `package-lock.json`; `npx` resolved v5.1.0 transiently, so no
dependency was added to the repo. A first vitest run failed two of my own assertions (wrong
expectation for the placeholder path, and a guide that tied with the canvas centre); both were
test bugs, corrected, and the suite then passed.

## Still left (next pass)

1. **Click-path coverage**: no test drives `CanvasWorkspace` itself (drag, select, properties
   edit, layers panel). That needs jsdom/React testing or Playwright Test on localhost.
2. **PNG/PDF export proof**: the `toBlob` → download path has no automated test; it needs a real
   browser canvas.
3. **Snapping to rotated layers** uses axis-aligned boxes only; rotation is rendered, not snapped.
4. **No keyboard nudge** (arrow keys) and no top-left resize handle; the stage exposes one
   bottom-right handle.
5. **File paths in the queue are stale** (`src/rooms`); the queue entry should be repointed at
   `src/studio` + `src/pages/internal/design-studio`.
