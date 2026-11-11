# D-017 — the contact shadow is removed by a real matte, and the colour cut was worse than the shadow

Unit `fix-plate-shadow-matte`. Tag `ty-dir-fix-plate-shadow-matte`. Rollback point
`rollback/pre-d017-20261111` at `602f562f`.

## What was wrong

`_place_on_flat` (the main-image path: the product alone on flat white) cut the plate
with `background_distance`, then kept the largest solid blob. A studio plate's contact
shadow differs from the sweep by more than the threshold **and is attached to the
product**, so the largest-blob pass could not drop it and the solid pass kept it. Its own
comment said so: *"removing it needs a real matte (BiRefNet in the lane)"*.

## What was measured on the real plate, not asserted

The plate is a real FLUX render already on disk —
`renders/comfy_plate7/ST-002/_rejected/front_plate.png`, a white ceramic mug on a pale
grey sweep with a soft contact shadow to the left of the base. Both instruments were run
on **the same plate**, inside one lane (`tools/comfy_lane.lane`, role `d017-matte`).
Record: `reports/ty/d017_matte_measure.json`; contact sheet
`reports/ty/d017_contact.png`.

| instrument | subject box (px, on a 2000² plate) | box aspect | seconds |
|---|---|---|---|
| `background_distance` (before) | 1934 × 1137 — **a band across the frame** | 1.701 | 0.6 |
| `matte_alpha` / BiRefNet (after) | 1162 × 1000 — **the mug** | 1.161 | **3.68** |

* The matte rejects **130,357 px** that the colour cut had kept, of which **130,003
  (99.73 %)** are dark and neutral — the contact shadow and the sweep's own vignette.
* The matte's border contact is **0.0** (it never owns the frame edge) and its edge
  gradient is **2.73 px** (a real edge, not a staircase).
* The colour cut keeps only **53.2 %** of the mug's own pixels.

**The colour cut on this plate is worse than "it keeps the shadow": it eats the mug.**
The contact sheet shows it — the body is chewed on the right, the handle arrives as
three detached fragments, the inner rim floats. A white product on a pale sweep has no
colour difference to find, so the threshold finds the *sweep's* gradient instead. Two
defects in one instrument; the matte fixes both.

## What changed

| file | change |
|---|---|
| `Northstar_backend/product_cutout.py` | `MatteUnavailable`; `lane_reachable()` (0.5 s probe, negative result cached 10 s — on this box a closed port is *dropped*, so a 2 s probe costs 2.03 s, measured); `matte_alpha()` — BiRefNet through the lane, connected-component speck filter at 0.04 % of the frame, soft edge kept only around what the matte chose. It **raises by name** when the lane is down or the run fails; it never returns a colour cut wearing a matte's name. |
| `Northstar_backend/product_picture.py` | `_place_on_flat(..., matte="auto" \| "birefnet" \| "none", matte_url=)`; `"birefnet"` refuses rather than degrades, `"auto"` falls back to the colour cut **and records why**, `"none"` is the old behaviour kept deliberately; `matte.rejected_px` records what the matte bought. `build()` takes `matte=` and every face record carries `matte`; the manifest carries `checks.matte` per face. |
| `Northstar_backend/test_plate_shadow_matte.py` | new: 8 checks (7 run without a lane, 1 needs `NS_PLATE_MATTE=1`). |

**Why `"auto"` and not `"birefnet"` by default:** the lane is not resident most of the
time, and a main-image render that refuses every time the lane is cold would stop the
seller harness for a reason that has nothing to do with the picture. A cold lane is now
a *stated* colour cut (`matte.method: "none"`, `matte.reason: "the media lane is
unreachable…"`) instead of an unstated one. When the lane is up — which it is for every
real-plate pass — `build()` takes the matte automatically.

## Tests

```
python -m pytest Northstar_backend/test_plate_shadow_matte.py -q              -> 7 passed, 1 skipped
python -m pytest Northstar_backend/test_product_picture_white_main.py \
  test_product_picture.py test_product_picture_reference.py \
  test_subject_fill_instrument.py -q                                         -> 30 passed
python -m pytest Northstar_backend/test_package_forms.py \
  test_package_cylinder_form.py test_product_composite_framing.py \
  test_seller_label_warp.py -q                                               -> 66 passed
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py -q                                         -> 78 passed
python -m pytest Northstar_backend/test_product_picture_white_main.py \
  test_product_picture.py test_product_picture_reference.py \
  test_plate_shadow_matte.py -q                                              -> 29 passed, 1 skipped
```

New checks, written before the code:

1. the colour cut **keeps** an opaque, attached shadow on a fixture whose truth is exact
   (a brown pack on a 200 grey sweep, a 150-grey shadow rectangle: the delivered canvas
   carries > 9,000 neutral-grey px);
2. a real matte **removes** it (< 200 neutral px) and keeps the product;
3. the matte **records** the pixels the colour cut had kept and it rejected;
4. `matte_alpha` **refuses by name** when the lane is unreachable (`MatteUnavailable`,
   "unreachable" in the message);
5. an explicit `matte="birefnet"` **never** falls back to a colour cut;
6. `matte="auto"` takes the fallback and **records** it;
7. the manifest carries `matte.method` / `matte.rejected_px` per face;
8. the real plate (skipped unless `NS_PLATE_MATTE=1`): 99.7 % of the rejected pixels are
   dark neutral, border contact 0, and the colour cut's box aspect exceeds the matte's by
   > 0.2.

## Honest limits

* **The scorers cannot see this defect.** `check_background` samples the four corners and
  `check_alpha_matte`'s white-matte branch samples an outer ring; a grey shadow under the
  product passes both. Every white-main number in the published seller sample was produced
  that way. Filed as **D-020**, not fixed here (it is another module's manifest).
* **The published seller dimension does not move from this unit.** It is still 96.2 over
  32 outputs, all of them drawn plates, where the shadow is drawn and controlled. The gain
  is real on real plates and is measured above; a real-plate white-main pass at pinned
  seeds is the number that would close it, and it is a scheduled lane, not an interactive
  one.
* **One plate, one product.** A mug on a pale sweep is the worst case for a colour cut and
  the case D-017 was filed on. A pouch, carton or dark product has not been measured
  against the matte yet; the pouch (ST-001) is the next real-plate check.

## Next, in rank order

`sel-04-packaging` → `pack-02-apparel-flat-print` → `reference-depth` → `pack-03-boxart-forms`
→ `block3-workspaces` → `block4-seller-tests` → `block5-production-hardening` →
`block7-verification`, plus **D-019** (stray scene geometry) and **D-020** (the white-matte
checks are blind to a shadow).
