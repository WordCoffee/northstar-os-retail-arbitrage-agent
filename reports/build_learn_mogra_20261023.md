# Build log — Mogra Lion's Mane 6 oz pouch (2026-10-23)

**What happened:** the package lane was taught to split a pouch into surfaces, then a real product
was built four times. Each build exposed a defect; each defect changed the code. This is the record.

Artifacts: `reports/northstar_acceptance_20261023/screenshots/build-mogra-{whole-face,per-panel}.png`
Dieline: doypack 95 × 200 mm + 80 mm gusset → `meta.panels.front = [9,11,95,200]`,
`meta.panels.gusset = [9,217,95,80]`
Plate: the Flux pouch render already approved; logo: the operator's real `logo.png`.

---

## Build 1 — per-surface split at full depth

Visible geometry: `gusset_left 31% · front 37% · gusset_right 31%`

**Result:** the subtitle clipped at both ends — rendered as `ORC ... DER` — and the gold keyline
became two vertical flaps.

**Cause:** two mistakes at once.
1. `panel_widths` read `rect[2]` for both panels, but the gusset is drawn **rotated** on the flat
   sheet, so its `w` is the pouch width and its `h` is the gusset depth. That gave a 95/95/95 split.
2. Even corrected, a gusset is **edge-on** in a front view; allocating its full 80 mm depth to the
   visible face handed the sides half the pack.

## Build 2 — foreshortened gussets

`GUSSET_FORESIGHTEN = 0.35` → `gusset_left 19% · front 63% · gusset_right 19%`

**Result:** text fit again, but the three surfaces were warped **independently**, and each warp
carried its own surface maps. Hard vertical seams appeared at both joins.

**Cause:** seams are a compositing-order problem, not a geometry problem.

## Build 3 — one wrapped artwork

`_wrap_panel()` composes `[gusset][front][gusset]` into a single artwork, then a **single**
`warp_panel` call applies one homography and one shading pass.

**Result:** no seams, no clipping, gussets read as turned-away sides.

## Build 4 — the artifact on record

`build-mogra-per-panel.png` — front panel intact and legible, two shaded side wings, the label inside
the silhouette rather than stretched edge to edge. `build-mogra-whole-face.png` is kept for
comparison: it is clean but the artwork runs to the pack's edge.

**Honest assessment:** this is a better *structural* result (correct panel proportions, one warp),
not yet a better *photograph*. The plate is still flat and frame-filling, and the gussets are blank
field colour where a real pack would carry the side panel.

---

## What the build taught — recorded as lessons

Stored in `data/build_lessons.json` and served by `specialists/lessons.py`
(`PROPOSED → APPLIED`, with the file that encodes each one).

| ID | Lesson | Status |
|---|---|---|
| L1 | The doypack gusset rect is rotated; use `min(w, h)` as its depth | **APPLIED** `panel_map.panel_widths` |
| L2 | A gusset is edge-on; foreshorten its share (0.35) | **APPLIED** `panel_map.GUSSET_FORESIGHTEN` |
| L3 | Independent per-surface warps seam; compose one wrapped artwork | **APPLIED** `pouch_label._wrap_panel` |
| L4 | Gussets should carry the side panel, not blank field | **PROPOSED** |

`lessons.notes_for_prompt()` returns only the APPLIED ones, so the store can be carried into an
agent prompt without shipping unproven advice.

---

## Test evidence

| Command | Result |
|---|---|
| `pytest test_lessons.py test_panel_map.py test_pouch_label.py` | 30 passed |
| full specialist set (12 modules) | **150 passed**, exit 0 |
| acceptance suite | 138/138, 22/22 tasks |

## Next (from L4)

Wire `specialists.panels.render_side_panel` into `_wrap_panel` so the gussets show weight, claims and
certification marks. That is the difference between "side wings" and a pack a converter would
recognise.
