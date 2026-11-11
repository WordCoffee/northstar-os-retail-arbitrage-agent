# pack-03 — box art: a boxed kettle and a boxed drill print on the carton

Unit `pack-03-boxart-forms`. Tag `ty-dir-pack-03-boxart`.

## What was missing

`ST-012` (small appliance) and `ST-028` (tool) asked for a boxed product and declared **no
product_line**, so `design_for_brief` refused them by name: *"brief ST-012 declares no
product_line"*. Even after wiring a line they were refused again, for a second and better
reason — *"the brief asks the model for the lettering; the app composes lettering from the
design"* — because neither brief declared `label_mode: "warp"` or a `body_prompt`. That
message is the app being right: a generated picture with model-drawn words is not a pack.

## What changed

| file | change |
|---|---|
| `Northstar_backend/brand_art.py` | two box-art designs on the **gift_box** form: `t2-kettle-box` (front 180 × 260 mm) and `t2-drill-box` (front 170 × 240 mm), each with its own faces, copy, care/spec panels, draft notes and a `claims` block that claims nothing (no organic seal, no FDA, no voltage or energy rating) |
| `ty/seller_briefs.json` | ST-012 → `t2-kettle-box`, ST-028 → `t2-drill-box`, both with `label_mode: "warp"` and a body prompt that asks for an **unprinted** box and no lettering |
| `ty/_briefs_boxart.json` | the two-brief working catalog, the same pattern the prompt-only pass uses |
| `Northstar_backend/test_boxart_form.py` | eight checks written first: the form and its millimetres, brief → design resolution, an unknown line still raising, the print keeping its aspect and landing inside the face, a blank plate refused by name, a plate brief with no shadow ask, and the app path delivering a flat main image with no residue |

## Measured

`python -m tools.seller_tester product --catalog ty/_briefs_boxart.json --renderer drawn`
→ `reports/ty/pack03_boxart_pass.json`

| brief | design | score | artefact |
|---|---|---|---|
| ST-012 small appliance, scale reference | `t2-kettle-box` | **100.0**, passed | `renders/pack03/ST-012/product_front.png` |
| ST-028 tool, scale reference | `t2-drill-box` | **100.0**, passed | `renders/pack03/ST-028/product_front.png` |

**2 selected, 2 scored, 2 passed, mean 100.0, 0 refused.**

The drill box reads: `T2 WORKSHOP` / *Two Batteries, One Case* / `18 V · 2.0 Ah · 13 MM
CHUCK` / `Brushless motor, 24 torque settings` / `NET WT. 2.4 KG` / `DRAFT · VERIFY BEFORE
PRINT`, on 255 white with no shadow.

**One thing this unit fixed by measuring, not by taste:** the first drill panel was declared
landscape (240 × 170) and the renderer **rotated** the artwork to fit the carton's portrait
face — the aspect survived, the words did not. The panel is now 170 × 240 and the print is
upright. A genuinely landscape drill box needs a landscape carton form, which is a different
unit (new geometry), not a different number in this one.

## What is still weak, said plainly

- **The motif is the shared default** — three ovals. It means nothing on a drill box. A
  per-category motif is a real gap (filed below).
- **The carton is drawn as one flat face-on panel.** A seller's box shot is a 3/4 view with
  the top and side visible; this is a flat pack front.
- **The plate is `synthetic_plate`** (drawn, not a render lane). The lane path is proven in
  D-025/pack-02; running these two through it is a 2-brief GPU pass, not a new capability.

## Filed

- **D-027** — a design cannot choose its motif: `brand_art._spec` sets `motif="bean"` for
  every design that does not declare one, so box art for a tool carries three ovals. Queued
  `design-motifs`, rank 6.

## Tests

```
python -m pytest Northstar_backend/test_boxart_form.py -q  -> 8 passed
```
