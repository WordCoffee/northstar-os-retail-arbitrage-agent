# Design Studio — capability audit: Projects · 3D Product Scene · compositing surface

**Date:** 2026-10-10 · **Branch:** feature/overnight-remediation-20261009 · **Phase 6 item 8**

Scope: compare the three canvases the studio owns against the capability list in
the directive — layers, reference lock, safe-zone overlay, undo/redo, compare
sign-off, export gates — and either close a gap or document it as a limit.

Evidence is code that runs (file:line) plus this session's harness output. No
capability is claimed from a docstring alone.

## Matrix

| Capability | Compositing surface (all 7 sections) | Projects (master canvas) | 3D Product Scene |
|---|---|---|---|
| Layers | **Present** — add/select/reorder/delete, left rail + inspector (`CompositingSurface.jsx`; exercised 37/0 by `tools/test-compositing.cjs`) | **Present** — add / duplicate / reorder / delete; layer rows with Move up/down (`CreativeStudio.jsx:1156-1157`), visibility + `locked` flag honored by the stage (`Stage.jsx:86,104,197`) | **Partial** — scene documents with object records (`studio/engine/sceneDoc.js`), edited per object; no reorder stack |
| Reference lock | **Present** — locked reference required for any asset containing the product; a locked doc without a reference is UNVERIFIED and blocks (`compose.js` fidelity step; test-compositing: matching 0.00% pass / redrawn 23.9% block) | **Absent** — layers can be marked `locked` (editing guard), but there is no locked fidelity reference and no diff | **Absent** — "reference artwork" exists as uploaded art (`ProductDesigner.jsx:551`) but is not lockable or diffed |
| Safe-zone overlay | **Present** — documented keep-out zones; on-image text inside one is FLAGged (`text-overflows-safe-zone`, 50/50 rules green) | **Present** — Advanced composition grid `{ cols: 3, safe: 0.06 }` (`CreativeStudio.jsx:523`) | **Present** — Advanced composition grid `{ cols: 3, safe: 0.06 }` (`ProductDesigner.jsx:405`) |
| Undo / redo | **Present** — Undo/Redo in the surface's left rail, asserted by test-compositing | **Absent** — no undo/redo on the Projects canvas; a discarded edit is re-made by hand | **Absent** |
| Compare sign-off | **Present** — human compare required for product assets, bound to asset version + reference hash; an unbound sign-off is refused (new negative test this session) | **Absent** | **Absent** |
| Export gates | **Present** — render → fidelity → compare → compliance → marker-embed → marker-verify; a step that did not run is never 'pass' (37/0) | **Present** (compliance only) — the Amazon pre-flight is a hard gate: `gate === 'blocked'` refuses export (`CreativeStudio.jsx:543`), and a channel set refuses if ANY placement breaks a blocking rule (`CreativeStudio.jsx:238-244`) | **Absent** — scene/pack/mockup PNGs export directly; generation stays blocked in the queue (`ProductDesigner.jsx:244`) |

## Documented limits (not closed this pass)

1. **Projects — no undo/redo, no reference lock, no compare sign-off.** The
   canvas is a composition tool with a compliance gate; the *fidelity* track
   lives only on the compositing surface. Closing it would mean porting the
   compose pipeline into Stage. Documented here rather than duplicated, per the
   Phase 5 decision D1.
2. **3D Product Scene — no compliance gate on direct PNG export.** Its exports
   are geometry renders of the operator's own art, not listing placements; a
   user can still export a scene that would violate a listing rule. A limit
   worth naming to the owner. The generation queue is gated separately and is
   UNARMED.
3. **3D — scene objects are not a reorderable layer stack.** Ordering is by
   scene recipe; there is no per-object z-control surface.
4. **The safe-zone overlay on Projects/3D is a 6% inset grid in Advanced mode**,
   not the documented per-placement keep-out geometry the compositing surface
   enforces. It is a design aid, not a rule.

## What this changes

Nothing in behaviour: this session verified the above against code and the
compositing harness; gaps are documented as limits (option the directive
allows). Two follow-ups for the owner if the gaps should close:
- port compose.exportComposite's gates into Stage exports (Projects), and
- run the compliance pre-flight before 3D direct exports.

---

## ADDENDUM — Phase 7 item 4 (2026-10-10/11): gaps CLOSED

The two follow-ups above were closed this session; the matrix updates to:

| Capability | Projects (master canvas) | 3D Product Scene |
|---|---|---|
| Layers | Present (unchanged) | Partial — scene objects; still no reorder stack (limit kept) |
| Reference lock | **Present** — lock the product layer's own file; unlock clears it (`CreativeStudio.jsx`, `proj-lock-reference`) | **Present** — lock the product photograph (`render-lock-reference`) |
| Safe-zone overlay | Present (unchanged, 6% Advanced aid) | Present (unchanged, 6% Advanced aid) |
| Undo / redo | **Present** — bounded history + Ctrl+Z / Ctrl+Shift+Z; proven 7→6→7 in the harness | Absent (limit kept — the composer has no edit history surface) |
| Compare sign-off | **Present** — version-bound self-declaration; every edit invalidates it (`commitDoc` stamps `meta.lastEditAt`) | **Present** — one sign-off covers every view of the same scene state |
| Export gates | **Present** — compliance + sign-off when locked; the objective pixel diff is ON DEMAND with its verdict and limits stated | **Present** — actual-photo BLOCK for listing purpose (`render-actual-photo`, source `img-guide`), Amazon pre-flight, disclosure (unanswered blocks), fidelity when locked, product-accuracy sign-off |

Semantics decisions (logged as D17/D18 in the owner journal): on Projects the
human sign-off is the gate and the pixel diff is a readout (a composed canvas
legitimately differs from the raw photograph); on 3D, a listing-purpose render
is blocked outright and internal renders pass the same disclosure/fidelity
machinery as every other section. Remaining named limits: 3D has no reorderable
layer stack and no undo/redo; both safe-zone overlays remain Advanced-mode aids
rather than the documented per-placement keep-out geometry.
