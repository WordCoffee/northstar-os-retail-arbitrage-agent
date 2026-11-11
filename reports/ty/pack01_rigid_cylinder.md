# pack-01 — the third packaging form: a rigid cylinder

Unit: `pack-01-rigid-cylinder-form` (queue rank 4, the named next unit in the
2026-11-11 cycle-6 handoff). Rollback tag: `rollback/pre-pack01-20261111`.

## Why this unit

The catalog asks for **eight** product categories. The app could print **two**
forms: a stand-up pouch (Mogra) and a folding carton (Word Coffee). Twenty-four
of thirty-two prompt-only briefs were refused with one true reason —
*"declares no product_line"* — and the largest block of them (mug, skincare
bottle, pet tub) are round bodies no form could draw. More testing was not the
blocker; a missing form was.

## What was built

| layer | change | file |
|---|---|---|
| form | `CYLINDER = "rigid_cylinder"`, its plate kind, its `FORM_NAMES` entry | `Northstar_backend/brand_art.py` |
| designs | four new SKUs as data entries: `word-coffee-canister` (118 × 100 mm label), `word-coffee-mug` (129 × 100), `harbor-body-oil` (63 × 50), `pine-paws-joint` (141 × 70). Every claim block declares what is **not** claimed (organic seal, FDA, vet-approved, food-safe) and every panel carries `DRAFT · VERIFY BEFORE PRINT` | `brand_art.py` |
| artwork | `render_front_label` / `render_back_label`: a label's own vertical rhythm (brand, rule, product, script, subtitle, tagline, weight band, codes, UPC) and back sections driven by the design's `label_sections`, not by coffee-specific headings | `Northstar_backend/package_art.py` |
| compositor | `warp_cylinder` now accepts the **RGB** panel the app produces (it indexed an alpha channel and raised `operands could not be broadcast` on every real design panel); `find_label_band` measures the printable band and refuses a plate with no package | `Northstar_backend/mockup_compositor.py` |
| pipeline | `CYLINDER_PLATE_BRIEFS`, `FORM_INSETS[CYLINDER]` (3 % sides, 26 % top for the shoulder, 10 % base) and `_compose_cylinder`: the label's **declared physical size** sets the band — the body's measured width gives px-per-mm, the declared label height gives the band height, and the label is centred on the body. A label taller than the body is refused as `label_too_tall_for_body`, never squeezed | `Northstar_backend/product_picture.py` |
| drawn plate | a cylinder body (body, shoulder, cap, base shadow), and the drawn renderer now picks the body from the **design's form**, not the brief's category | `tools/seller_tester/scene_render.py` |
| catalog | 12 prompt-only briefs wired to the app path (mug 4, skincare 4, pet 4) with `product_line`, `label_mode: warp` and their own `body_prompt`; 5 uploaded-reference briefs left alone because they have no local file | `ty/seller_briefs.json` |

## Measured

`python -m tools.seller_tester product --catalog ty/seller_briefs.json --renderer drawn --skip-unavailable --limit 60`

```
scored 20  passed 20  mean 96.0
by_category  ceramic_mug 4/4 90.0 · food_jar 4/4 95.0 · pet_product 4/4 90.0
             skincare_bottle 4/4 95.0 · supplement_pouch 4/4 100.0
```

Before this unit the same command scored **8** briefs (mean 97.5); the pass now
covers **20** briefs across **5** categories. Published seller dimension:
**96.9 over 32 outputs, 32 passed** (was 98.0 over 20) — coverage up 60 %, mean
down 1.1, because the new pictures are a harder set.

### Checks that still fail inside passing pictures (stated, not hidden)

| brief | check | detail | why |
|---|---|---|---|
| ST-011, ST-027 | `text_free` | margin ink 0.00 % vs min 0.20 % (`text_expected`) | these are **infographic** briefs; the app makes a package picture and has no overlay layer |
| ST-029 | `subject_fill` | 28.1 % vs 30–72 % | it is a `food_jar` brief whose design is the Word Coffee **gift box**, drawn at 0.44 of the frame; the band is a bundle band |

## Tests

`python -m pytest Northstar_backend/test_package_cylinder_form.py` — 23 tests, all pass:

- the form is declared, not inferred; its plate brief is neither pouch nor carton; its insets leave the shoulder and the base unprinted;
- a cylinder must declare `face_mm` and is refused **by name** when it does not;
- every cylinder label is legible on both faces (wordmark + net weight, OCR);
- regression: the wordmark is no longer printed on the frame rule (OCR read "WORD COFFEE" as "WORDCOEEEE" before the label got its own rhythm);
- regression: `warp_cylinder` accepts an RGB panel; a zero-area band is refused;
- `find_label_band` measures a drawn cylinder and refuses a blank plate;
- end-to-end: a cylinder plate yields a gated labelled picture front **and** back; a blank plate is refused and writes no file; three cylinders measure three bands left-to-right;
- the drawn body follows the design's form, not the brief's category;
- the shipping pouch is still **byte-identical**, and the carton is untouched;
- the API lists all four cylinder designs with their own plate briefs.

Related suites re-run green: `test_package_forms.py`, `test_mockup_compositor.py`,
`test_mockup_product_picture.py`, `test_package_design*.py`,
`test_product_picture*.py`, `test_seller_scores.py`,
`test_seller_tester_product_pipeline.py`, `test_seller_tester*.py`,
`test_seller_label_warp.py`, `test_seller_deterministic.py`,
`test_scene_lane_gpu.py`, `test_heldout_composite.py` — **268 passed**.

`test_package_forms.py` had one exact-set assertion (`set(by_id) == {mogra,
word-coffee}`); it now asserts those two are present, because four designs exist.

## What this does not prove

1. **The plate is drawn.** `synthetic_plate` is a labelled stand-in; the artwork,
   warp, band measurement and OCR gate are real, the photograph is not. ComfyUI is
   not running (`engine_status()`: *armed but unreachable at 127.0.0.1:8188*).
   `python -m tools.seller_tester product --renderer comfy` is the next real
   measurement and it needs ComfyUI started.
2. **The drawn body's size is calibrated** to the catalog's fill bands (0.52 ×
   0.70 of the frame). A real plate gets its own size from the photograph.
3. **Four designs are demo SKUs.** They are declared DRAFT with explicit
   non-claims; they are not the owner's products.
4. **Apparel, small appliance and tool still have no form.** They are the next
   three categories and each needs its own (flat print, box art, blister).

## Defects filed

- **D-012** `bundle_multipack` briefs declare no `units`, so a bundle plate is
  drawn as one unit and the fill band misses (ST-029, 28.1 % vs 30 %).
- **D-013** infographic briefs require margin ink (`text_expected`) and the app
  has no overlay/infographic composer, so they can never satisfy that rule.
- **D-014** four `food_jar` briefs (ST-008/015/022/029) describe a folding gift
  box in their own `body_prompt`; their category is the seller's taxonomy, their
  design is a carton. The category is left as declared and the mismatch is
  recorded here rather than silently re-labelled.
