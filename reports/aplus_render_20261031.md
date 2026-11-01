# Creative pipeline — A+ rendering + measured package legibility

**Date:** 2026-10-31
**Scope:** product packages and A+ content in the local creative pipeline
**Spend:** none. No provider key read, no browser, no Amazon host touched.
**Commit:** `ca6c45cb`

---

## 1. What the scan found

I read the creative surface end to end rather than trusting the state notes:

| Module | What it does | Verdict |
|---|---|---|
| `aplus_layout.py` | exact integer geometry per A+ module | sound — but pure geometry |
| `specialists/image_aplus.py` | module sizes, copy rules, `validate_module_image` | **defect** (see 1.2) |
| `creative_flow.py` | state machine: plate → gate → compose → hero → aplus | `aplus` step wrote **specs only** |
| `pouch_label.py` / `format_compositors.py` | label render + warp onto a measured face | sound |
| `mockup_compositor.py` | typography pass, homography warp | sound |
| `prepress.py` / `print_prep.py` | CMYK/TAC/gamut, dieline DPI gate | sound |
| `asset_rubric.py` | OCR legibility, hero scoring | sound, unused on packages |

### 1.1 The gap: A+ content was a JSON file

`creative_flow.step_aplus` wrote `aplus_specs.json` and set `valid: true`. Nothing
anywhere turned a module id into an image. `aplus_layout` was consumed by the
flow and the crew **only as geometry**. So "A+ content" in the product meant a
rectangle map, not an uploadable asset.

### 1.2 The defect: the planner's own validator rejected correct assets

`validate_module_image(path, "three_tiles")` compared the image against
`MODULES["three_tiles"]["w"/"h"]` — which is the **tile** (300×300), not the
**row** (970×300). Every correct row asset failed with
`970x300 does not match the 300x300 module`. `comparison` was not in `MODULES`
at all, so it returned `unknown module`. Found by asserting that a renderer's
output passes the planner's validator — two subsystems that had never been
introduced.

---

## 2. What was built

### `Northstar_backend/aplus_render.py` (new)

Deterministic, offline renderer for all 11 module kinds, drawing only into
rectangles taken from `aplus_layout.pixel_plan()`.

* **Type is composited, never generated** — the same rule the label lane already
  enforces for pouches.
* **`copy_style="panel"` (default)**: the copy owns a brand-field column, the
  photograph owns the rest. This exists because of what the first live render
  showed (below): 4.55:1 contrast over a photo of printed packaging measures
  fine and still reads as a collision.
* **`copy_style="overlay"`**: type on the image behind a scrim whose strength is
  raised until the *measured* contrast passes, plus a backdrop-variance ceiling
  (`0.06`) so a scrim cannot be used to hide busy printing. A dark brand colour
  is not assumed to be the right scrim: the veil is chosen to stand *off* the ink.
* **Legible accent**: a brand accent used for small caps is darkened toward the
  ink until it passes, and the adjustment is recorded. Keylines and icons keep the
  true accent.
* **Prohibited copy is refused before a pixel is written** through
  `specialists.image_aplus.screen_copy` (price, promotion, shipping, competitor,
  medical claim).
* **Keeps the platform contract**: exact canvas, PNG (JPEG fallback over 2 MB),
  passes `validate_module_image`.

### The QA it reports — measured, not claimed

| Check | Rule |
|---|---|
| canvas | exactly `aplus_layout.CANVAS[kind]` |
| containment | every text ink box inside its own container (band, column, tile) |
| contrast | WCAG AA `4.5:1` under 24 px, `3.0:1` at/above — worst *local* cell, not an average |
| type floor | no text below `14 px` at 1x |
| fit | a block that will not fit at the floor is reported, never clipped |
| file | ≤ 2 MB, PNG or JPEG |
| sharpness | a plate blown up past `2x` is refused as too small to place sharply |
| overlay | backdrop variance ≤ `0.06` |

`assert_perfect()` raises `AplusNotPerfect` with the named defects; `render_page()`
returns `ok` plus per-module `problems`, so a bad page is visible rather than silent.

### `Northstar_backend/design_studio_aplus.py` (new, mounted in `main.py`)

* `GET  /api/design-studio/aplus/kinds` — the module contract (sizes, tile counts,
  copy band, safe inset, byte ceiling).
* `POST /api/design-studio/aplus/render` — renders a page from a saved plate
  asset, registers each module (`asset_type=aplus_module`) and a page preview,
  and returns per-module QA. Prohibited copy → 422 before anything is written.

Verified through the real app: `GET /api/design-studio/aplus/kinds` → `200 OK`,
11 kinds.

### `creative_flow.step_aplus` now renders

Geometry is still written, then the page is rendered from `01_plate.png` with the
job's own brand and copy (flow keys `title`/`subtitle` are mapped to the A+
`headline`/`sub`), saved under `<out>/aplus/`, and recorded as
`upload_ready: true|false` with the defects. A defect is **not** a code rollback —
`state.status` stays `ok` and the defect is surfaced, which is the honest split
between "the repo is broken" and "this artefact is not sellable".

### `creative_flow.face_legibility` (new)

The package side had no check that the words survive the warp: the geometry gate
proves the label is *in the right place*, not that it is *readable*. This crops
the measured quad (+8 px), upsamples 2x and runs the same OCR gate the listing
lane uses. `compose` now records `label_illegible` when the copy cannot be found.
No quad → `skipped`; no OCR → `unavailable`. It never invents a verdict.

---

## 3. The live render, and what looking at it changed

Plate: `renders/mogra-forest-dusk-mockup-complete.png` (the operator's finished
two-pouch mockup). Six-module story, Mogra palette.

**First pass — all green, and wrong.** Contrast 4.55:1, every check passed, and
the headline sat directly on the pouch's own printed "MOGRA ORGANICS / ORGANIC
LION'S MANE" lockup. The measurement was satisfied; the artwork was not. This is
exactly the class of defect the contrast rule alone cannot catch.

**Fix:** the reserved panel became the default, the overlay path gained the
variance ceiling, and the tile captions became a caption strip instead of a wash
over the whole photograph.

**Final, measured:**

| # | module | size | bytes | copy mode | min contrast |
|---|---|---|---|---|---|
| 01 | header | 970×600 | 526,117 | panel | 4.57 |
| 02 | three_tiles | 970×300 | 119,792 | panel | 10.85 |
| 03 | banner | 970×300 | 284,950 | panel | 4.57 |
| 04 | four_tiles | 970×220 | 67,199 | panel | 10.85 |
| 05 | comparison | 970×600 | 31,687 | field | 5.20 |
| 06 | logo | 600×180 | 12,099 | field | 10.85 |

Page verdict `ok: true`, 1,041,844 bytes total. Reproduce with
`python tools/aplus_page_proof.py`.

Warnings carried (not hidden): `accent darkened for legible small caps` on the
two band modules, `one image reused across the tile row` on both tile rows —
one plate was supplied, so all tiles are crops of it.

---

## 4. Tests

| suite | count |
|---|---|
| `test_aplus_render.py` (new) | 64 passed |
| `test_design_studio_aplus.py` (new) | 8 passed |
| `test_creative_flow.py` | 13 passed (was 6) |
| creative sweep (21 suites) | **358 passed, 19 skipped, 1 failed** |

The one failure — `test_mockup_compositor.py::test_compose_endpoints` — is
pre-existing: it fails identically with my changes stashed. It is unrelated
(compose endpoint response shape), and I did not touch that surface.

---

## 5. State registry

`00_STATE.json` carries an operator `edit` deny, so it was not touched. The entry
is queued as a fragment and verifies clean:

```
python tools/state_fragment.py --check state/fragments/20261031_aplus_render.json
→ would_add: ["creative_aplus_render_20261031"], status: OK (nothing written)
```

`--apply` is the operator's step by design.

---

## 6. Honest limits
1. **Tiles need distinct imagery.** One plate reused across a row is allowed and
   warned, but a real A+ page wants three or four different crops. The API accepts
   `tile_asset_ids` for that.
2. **No UI panel yet.** The route exists and is mounted; the Design Studio SPA
   does not have an A+ module builder. That is the next unit.
3. **Panel is a design decision, not a universal answer.** It is the reliable
   default; `overlay` is legitimate for full-bleed lifestyle spreads with clean
   skies or walls, which is why it is kept — gated by variance.
4. **Package legibility depends on OCR at render size.** On a 1216 px plate the
   label type is small; `face_legibility` upsamples 2x, but a 4.5k-char brief's
   fine print would still be beyond it. The gate reports `unavailable` rather than
   a false pass.
5. **A+ is screen media.** No 300 DPI gate applies; `print_prep` stays the
   authority for anything that goes to a co-packer.
6. **`copy_style="overlay"` refuses real product photography with printing on
   it** — measured 0.077 and 0.127 variance on the two plates tested, both above
   the 0.06 ceiling. That is the intended outcome, not a bug.
