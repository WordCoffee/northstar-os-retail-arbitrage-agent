# D-021 — a main image gets a shadowless plate, on both the drawn and the real route

Unit `fix-drawn-plate-shadow`. Tag `ty-dir-fix-drawn-plate-shadow`. Rollback point
`rollback/pre-d021-20261111` at `19f11650`.

## What was wrong

Two places asked for a contact shadow on **every** brief, including main images, where a
shadow is exactly what the picture must not have:

* `scene_render.synthetic_plate` drew a base ellipse `(206, 204, 200)` under each package
  ("so the plate is not a sticker on a flat field");
* the plate prompts (`PLATE_BRIEFS`, `BOX_PLATE_BRIEFS`, the cylinder template and the
  bundle branch) all said "a gentle contact shadow" / "a soft contact shadow under each".

Once the colour cut keeps the ellipse — and it does, the ellipse is attached to the base —
the silhouette **contains** it, so D-020's residue check, which measures outside the
silhouette, reads 0.00 % on a picture a seller cannot list. The shadow has to be prevented
at the plate, not removed downstream.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/scene_render.py` | `synthetic_plate(shadow=False)` omits both drawn base ellipses (pouch/carton branch and cylinder branch). The drawn renderer passes `shadow=not white`, using the same `white` flag that already decided the field, so a uniform/white-matte brief gets a shadowless plate and a free/scene brief keeps its shadow. |
| `Northstar_backend/product_picture.py` | `plate_brief(..., shadow=False)` rewrites the shadow clause in every branch (single package, bundle, cylinder, and a design's own `plate_subject`) to "even shadowless light, no shadow and no cast shadow". `build()` chooses it from the background: `background="white"/"flat"` → no shadow, anything else → the shadow stays. |
| `Northstar_backend/test_plate_shadow_brief.py` | 5 checks, written before the code. |

**Why the real route matters more than the drawn one.** The drawn plate is a stand-in; the
FLUX plate is the product. Asking the model for "a gentle contact shadow" on a main-image
brief was asking for the defect, and it is the same sentence the D-017 matte then had to
undo. The plate prompt now asks for a shadowless field, so the matte has less to remove and
a cold lane produces a better picture instead of a shadowed one.

## Measured (drawn route, `renders/d020` before → `renders/d021` after)

`python state/director/_d021_measure.py` → `reports/ty/d021_plate_shadow.json`; contact
sheet `reports/ty/d021_contact.png`.

| brief | form | neutral mid-grey px, before → after | product box before → after |
|---|---|---|---|
| PO-001 | stand-up pouch | **941 848 → 30 820** | 1280 × 1748 → 1192 × **1877** |
| PO-003 | stand-up pouch | **64 405 → 8 006** | 921 × 1258 → 858 × **1351** |
| PO-004 | folding gift box | 821 → 821 | identical (control: this form never drew a shadow) |

The counter is "neutral pixels between 190 and 215 levels" — the grey the ellipse is drawn
in. PO-001's picture is the clear before/after: a large soft ellipse under the pouch becomes
bare 255 white, and the product is **7 % taller in the frame** because the crop no longer
wastes height on a shadow. PO-004 is the honest control: the gift-box branch never drew a
shadow, so nothing changed there and the fix did not disturb it by accident.

The pass itself is unchanged where it should be: 4 scored, 4 passed, mean 100.0
(`reports/ty/d021_sample_pass.json`). Nothing was made to pass by moving a bar.

## Tests

```
python -m pytest Northstar_backend/test_plate_shadow_brief.py -q                  -> 5 passed
python -m pytest Northstar_backend/test_product_picture_white_main.py \
  test_product_picture.py test_product_picture_reference.py \
  test_plate_shadow_brief.py test_plate_shadow_matte.py -q                         -> 34 passed, 1 skipped
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py test_matte_residue.py \
  test_package_forms.py test_package_cylinder_form.py -q                           -> 136 passed
```

The five new checks: a shadowless plate has no mark below the body's last row while a
shadowed one does; the drawn renderer drops the shadow for a main-image brief and keeps it
for a free one; `plate_brief` stops asking for a contact shadow on all three forms and on a
bundle; `build(background="white")` hands the generator a brief without the shadow ask
while a scene brief keeps it.

## Honest limits

* **The real FLUX route is not re-measured here.** The prompt change is proven by test
  (`plate_brief(shadow=False)` carries no shadow ask), not by a fresh plate render: that is
  a 70–90 s lane per picture and belongs to the next real-plate pass. The drawn route is
  measured end to end, with pictures.
* **This narrows D-022, it does not fix it.** A *full generation* (`route:
  full_generation`, SDXL/FLUX scene) still has no white-composite step and still produces a
  grey pool — 8 published artefacts at 10.2–25.6 % residue. That is queued next.
* **The residue check is still the only thing watching the background.** On the drawn route
  it now reads 0.00 % because the picture is clean, not because it is blind: the silhouette
  no longer contains a shadow, so a future shadow would land outside it and be caught.
