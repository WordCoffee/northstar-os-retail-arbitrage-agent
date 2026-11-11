# D-016 — the label is scaled to the body that is actually in the plate

Unit `fix-label-scale-plate`, tag `ty-dir-fix-label-scale-plate`, rollback
`rollback/pre-d016-20261111` (pre-change snapshot `51aedd9c`).

D-016 had two halves, and they are two different faults:

1. **The measured body was narrower than the body.** On a pale body against a
   pale sweep the silhouette edge differs from the sweep by only a few levels.
   `find_cylinder_bands` cut the mask at a **fixed 16 levels**, so the edge was
   never in the mask, the column band stopped short, the measured width set
   pixels-per-mm, and the printed label came out small.
2. **A mug was drawn as a plain cylinder.** The plate brief was per *form*
   ("a rigid cylindrical package"), so a mug with a handle and a canister with a
   lid were both asked of the model as the same anonymous tube.

## What changed

| file | change |
|---|---|
| `Northstar_backend/mockup_compositor.py` | the mask cut is now **relative to the plate's own subject contrast**: `cut = max(5.0, min(threshold, 0.20 * p99.5(diff)))`, floored above the sweep's noise and capped by the caller's threshold. The body's **vertical** extent is still measured on the caller's firm cut (`firm`), because the fine cut reached into a soft contact shadow at the base. |
| `Northstar_backend/brand_art.py` | each cylinder design declares a `plate_subject` (`ceramic mug with a handle`, `cylindrical coffee canister with a screw lid`, `slim amber glass bottle with a pump cap`, `wide plastic supplement tub with a screw lid`). |
| `Northstar_backend/product_picture.py` | `plate_brief(face, form, design)` renders the design's own subject for `CYLINDER`; `build` passes the design through. A form with no per-design subject keeps its form brief unchanged. |
| `Northstar_backend/test_package_cylinder_form.py` | 4 new tests (below). |

**A relaxation of the column-growth hysteresis (0.35 → 0.22) was tried first and
rejected on measurement.** It widened the band, but it also let a shadow 22 % of
the body height into the band on the other side (+4.8 % over-measure). The
relative mask cut fixes the cause instead and leaves the growth rule at 0.35.

## Measured, before → after (one synthetic plate, truth known exactly: body x 250..750, y 150..1050)

The old rule is not retyped — it is `git show HEAD~…:mockup_compositor.py`,
parsed with `ast`, and executed against the same image:

```
HEAD 0.35: band=[261.0, 150.0, 740.0, 1050.0] width=479.0px (95.8% of the true 500px body) height=900.0px
tree      : band=[254.0, 150.0, 747.0, 1050.0] width=493.0px (98.6% of the true 500px body) height=900.0px
label scale on this plate: new/old = 1.0292 (+2.9%)
```

**+2.9 % of label scale on this plate, and 100 % of the true body height.** That
is the honest size of this fix: it is a real correction, not a large one. The
plate from the cycle-8 real render (`ST-002`) was **not retained on disk**, so
the real-plate delta cannot be re-measured; the fixture above is the substitute
and is labelled as such.

Shadow discipline, measured on the same body with a soft shadow to its right
(no over-measure at any realistic shadow height):

```
shadow 10% of body height: band x=(250,750) width=500px  over-measure=+0.0%
shadow 22% of body height: band x=(250,750) width=500px  over-measure=+0.0%
shadow 30% of body height: band x=(250,750) width=500px  over-measure=+0.0%
shadow 45% of body height: band x=(250,750) width=500px  over-measure=+0.0%
```

Plate grain (σ 2.5 levels) moves the measured width to 491 px (98.2 %), i.e. the
error stays on the conservative side — a label slightly smaller than the body,
never past its silhouette.

## Tests

`python -m pytest Northstar_backend/test_package_cylinder_form.py -q` →
**27 passed** (was 24; three new measurement tests plus the per-design brief
test).

```
python -m pytest Northstar_backend/test_blank_plate.py test_compositor_realism.py \
  test_mockup_compositor.py test_mockup_product_picture.py test_package_forms.py \
  test_plate_geometry.py test_pouch_label_geometry.py test_creative_pipeline_chain.py -q
→ 79 passed
python -m pytest Northstar_backend/test_seller_tester.py test_seller_tester_composite.py -q
→ 75 passed
```

New tests:

- `test_a_low_contrast_body_is_measured_to_its_silhouette` — width within 3 % of
  the true body, top and bottom within 12 px.
- `test_the_measurement_holds_with_plate_grain` — the same, with σ 2.5 noise.
- `test_a_tall_side_shadow_is_not_measured_as_body` — a shadow 30 % of the body
  height does not widen the band.
- `test_a_design_names_its_own_body_in_the_plate_brief` — the mug, the tub and
  the untouched gift-box form.

## Seller-side measurement

`python -m tools.seller_tester product --renderer drawn --skip-unavailable` on
the held-out modes catalog: **6 scored, 6 passed, mean 100.0** (PO-001…PO-006;
the six stored-reference briefs are refused by name — they ask the model for the
lettering and that needs `label_mode: warp`). This is a 6-brief subset of the
24-brief catalog and is **not** comparable with cycle 9's 20-brief 95.0; it is
recorded, not published as a new seller number.

## Limits, stated rather than hidden

- A **drawn** plate is still a generic cylinder: `synthetic_plate` takes a form,
  not a design, so a mug brief's stand-in picture is a tube with a cap. The drawn
  plate is labelled `synthetic_plate` in every record; adding a handle to a
  stand-in is cosmetic and was not done in this unit.
- With `count=2`, a shadow 30 % of the body height can still be counted as a
  second unit. `count=1` (the shipped path for every single-unit brief) excludes
  it, and that is asserted.
- The real-plate ST-002 delta is unknown for the reason above.
