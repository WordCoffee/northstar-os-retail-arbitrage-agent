# measure_surface — generalized face measurement + live four-format validation

- date: 2026-10-31
- base commit: `0be3fb99` (box/bottle/tube compositors, format routing, T1 rollback)
- directive: generalize `measure_face()` across all four formats so a label is
  placed on the surface the render actually produced, then run real FLUX plates
  through the full flow for pouch, box, bottle and tube.

## What shipped

### `Northstar_backend/surface_measure.py` (new)

One algorithm, four parameter sets. Every format goes through the same pipeline:

```
background median -> silhouette mask -> sub-pixel edges -> format fit -> residual gate
```

| format | fit |
|---|---|
| pouch | delegates to the proven `pouch_label.measure_face` (quadratic side fit, sine bow, 1.5 px residual gate) |
| box | four intersecting line fits on the visible front face; a strong interior vertical edge splits a 3/4 view into side + front, and the larger face wins |
| bottle | longest near-constant-width band of the silhouette (the body, not the cap or shoulder) |
| tube | the same band measured against its own linear taper, with a horizontal cap-seam search that trims the band when the cap has nearly the body's diameter |

The result carries `quad` (TL/TR/BR/BL), `face`, `geom_residual_px`,
`geom_residual_by_side`, `method`, `confidence`, format metrics (`face_share`,
`band`, `width_px`, `taper`, `crimp_top_px`, `crimp_bottom_px`, `convexity`) and
`warnings`. `SurfaceNotMeasurable` is raised when the plate cannot support a fit
inside `MAX_GEOM_RESIDUAL_PX` (1.5 px, the same gate the pouch already used).

### Flow wiring

`creative_flow.step_compose` no longer scales a nominal profile quad. For
box/bottle/tube it measures the plate, then warps the label onto the measured
quad. A measurement refusal blocks the run with `surface_unmeasurable`; there is
no nominal-quad fallback. Pouch keeps the existing measured compose and now
records its measurement in the compose state too.

### Compositor defects found by the live run (and fixed)

1. **Box label sideways and on the side panel.** `box_composite` used PIL `QUAD`
   with the source corners in the wrong winding and no destination mapping, so
   the label was stretched to the whole plate and cropped by the quad. It now
   solves the label -> quad homography and passes its inverse to PIL
   `PERSPECTIVE`. A quadrant-orientation test pins upright, unflipped output.
2. **Box measured the whole silhouette.** The interior-edge share test was 5% of
   the central gradient sum; the real 3/4 box peak was 1%. Relaxed to 1% with a
   3.5x median floor. On the live plate the front/side corner is found at x=369,
   face share 72%, residual 0.16 px.
3. **Bottle artwork mirrored into two half-labels.** The resample used
   `(1 - sin(theta))`, which samples centre -> left edge -> centre. It now
   samples the inverse cylindrical projection (`asin`), continuous from edge to
   edge and compressed only toward the silhouette. A gradient test pins
   monotonicity.
4. **Tube rejected as a -26% taper.** The render is a tube seen from slightly
   above: its body is wider at the top, which is a perspective effect, not an
   invalid tube. Negative taper is accepted within the same 35% bound, and
   `tube_composite` now warps to the four measured corners instead of applying a
   fixed top inset.
5. **Tube label ran onto the cap.** The cap has nearly the body's diameter, so a
   width step cannot find the seam. `surface_measure` now searches the outer
   quarter of the tube band for a strong horizontal luminance step (peak >= 4x
   median, >= 3% of the zone sum, >= 2x the surrounding median) and trims there.
   Bottles skip this trim because their base is part of the printable body.
6. **Shading darkened the plate around the product.** The box ramp darkened
   above/below the face; the bottle ramp darkened the left edge of the entire
   background. Both are now masked to the face/label area. A tube crimp band is
   also excluded from shading.

### `tools/run_flow_formats.py` (new)

Sequential live runner for all four formats:

```
render (FLUX 3, fixed seed) -> gate (OCR) -> measure -> compose -> hero
-> evaluate -> aplus -> report
```

It records per-format plate/labelled/hero paths, the measured surface, paint
inside vs outside the quad, OCR verdict and the rubric score. `--dry-run` uses
synthetic plates and no GPU. A hard render failure stops the sequence; there is
no auto-retry.

## Verification (offline)

```
python -m pytest Northstar_backend/test_surface_measure.py \
  Northstar_backend/test_format_compositors.py \
  Northstar_backend/test_format_integration.py \
  Northstar_backend/test_creative_flow.py \
  Northstar_backend/test_geometry_profiles.py \
  Northstar_backend/test_asset_rubric.py -q
```

**60 passed, 1 skipped** (the skip is the pre-existing live-only geometry test).

| suite | result |
|---|---|
| `test_surface_measure.py` | 10 passed |
| `test_format_compositors.py` | 14 passed |
| `test_format_integration.py` | 9 passed |
| `test_creative_flow.py` | 6 passed, 1 skipped |
| `test_geometry_profiles.py` | 14 passed |
| `test_asset_rubric.py` | 7 passed |

All edits are UTF-8 without BOM.

## Live FLUX validation

Command:

```
python tools/run_flow_formats.py --out exports/flow_formats_live_verified_20261031
```

Environment: local ComfyUI `:8188` (FLUX 3 Klein), gateway `:8190`, RTX 5080
laptop, 14.6 GB VRAM free at start, 5.8 GB RAM free, 88.8 GB disk free.
All four renders completed; the whole run took **157.4 s** of render/flow time
(41.1 + 39.0 + 38.9 + 38.4 s).

| format | status | surface method | residual | confidence | paint inside quad | OCR | rubric |
|---|---|---|---|---|---|---|---|
| pouch | ok | `pouch-measure_face` | 0.366 px | n/a (existing path) | 95.6% | text present, all 6 lines | 68.1 |
| box | ok | `box-quad` | 0.159 px | 0.947 | 97.7% | matches expected | 63.0 |
| bottle | ok | `bottle-band` | 0.208 px | 0.931 | 100.0% | matches expected | 77.3 |
| tube | ok | `tube-band` | 0.255 px | 0.915 | 96.7% | matches expected | 78.3 |

Measured quads (pixels, 1024x1024 plates):

- pouch `[[264.9,253.0],[757.3,253.0],[722.3,861.0],[299.3,861.0]]`
- box `[[397.1,169.0],[817.2,164.9],[816.0,820.8],[397.1,873.1]]`
- bottle `[[374.5,376.0],[647.9,376.0],[647.8,844.0],[374.1,844.0]]`
- tube `[[369.7,319.0],[654.0,319.0],[627.4,795.0],[392.8,795.0]]`

Hero audits: all four `corners_pure_white = true`; pure-white ratios 0.454
(pouch), 0.336 (box), 0.601 (bottle), 0.628 (tube). Every flow report exists at
`<out>/<format>/flow_report.json`.

Artefacts:

```
exports/flow_formats_live_verified_20261031/run_report.json
exports/flow_formats_live_verified_20261031/{pouch,box,bottle,tube}/01_plate.png
exports/flow_formats_live_verified_20261031/{pouch,box,bottle,tube}/02_labelled.png
exports/flow_formats_live_verified_20261031/{pouch,box,bottle,tube}/03_hero.png
```

The JSON evidence (`run_report.json`, `flow_report.json`, `flow_state.json`,
`aplus_specs.json`) is committed; the PNGs stay local artefacts because they are
13.7 MB of generated binaries.

## Honest caveats

- **This is a mockup fit, not a die drawing.** The measured quad comes from the
  render; a converter's dieline remains the print authority.
- **The rubric still names real defects**: `background_not_white_enough` on all
  four heroes, `subject_touching_frame` on pouch/box, and
  `contact_shadow_or_floor` on box. The corners are pure white, so these are
  framing/shadow issues in the hero, not label alignment. They are the next
  visual-quality target.
- **OCR is evidence, not proof.** Pouch OCR reads `LION'SMANE` as one token and
  still scores legibility 1.0; the tube's `6 oz` line is read with a wobble.
  Visual inspection of `02_labelled.png` is the stronger check.
- **The paint-outside-quad pixels are the feathered edge and the realism
  displacement**, not label spill. Bottle is exactly 0 outside; pouch is 12,724
  px (4.4% of changed pixels) because the pouch realism pass displaces print by
  up to 1.8 px and the mesh bows. Box 6,608 px and tube 4,280 px are the 2 px
  feather plus shading.
- **The live run used fixed prompts**, not the local 27B prompt author. The
  author lane was down and this run's purpose was surface measurement; the
  prompt path is unchanged and still available in `tools/run_flow_e2e.py`.
- **No print-DPI claim.** `geometry_profiles` still reports the mockup's
  px_per_mm as below 300 DPI equivalent; the flow records the warning and does
  not block unless a job sets `require_print_dpi`.
- **No Amazon request, no spend, no credential read.** All work was local
  ComfyUI, PIL/numpy and pytest.

## Commits

```
0be3fb99  base: box/bottle/tube compositors, format routing, T1 rollback
670fd5ad  measure_surface + live runner
06776bbe  box perspective warp + interior corner
ebbed6b5  continuous bottle wrap + measured tube trapezoid
b0a25396  tube band trimmed at horizontal cap seams
```

## Next

1. Fix the hero rubric defects: frame fill for pouch/box, contact shadow
   direction/strength, and background purity measurement rather than a blanket
   flag.
2. Curvature shading for bottle/tube: the label is geometrically correct but
   still reads a little flat on the cylinder; modulate it with the plate's own
   luminance the way the pouch realism pass does.
3. Re-run the same four formats through the 27B prompt author, then compare
   plates and scores.
4. Print path: enforce 300 DPI equivalent per format and emit the measured quad
   into the dieline sidecar.
