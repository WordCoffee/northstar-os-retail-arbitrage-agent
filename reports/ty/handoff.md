# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Owner instruction, 2026-11-11 03:48 local — no browser pages

The owner, verbatim: *"stop the broswer from ope8101/ui/beta-ops"* / *"please stop opening
multiple different northstar os pages back to back"*. Chrome history shows the behaviour:
Profile 1 at 09:14–09:16 and Profile 4 at 09:38 walked `/ui/keywords → /ui/beta →
/ui/beta#support → /ui/beta-signup → /ui/design-studio` six seconds apart. Chrome Connect is
ruled out — its journal's last entry is 2026-11-05.

What was done: `state/vision/PAUSE` written (blocks every vision-control action by name),
the `tys_launcher` lane and its agent stopped, and the competing director sessions
interrupted through the server API (`POST /api/session/<id>/interrupt`) rather than by
killing processes. **No lane may navigate, click, type or walk pages until the owner lifts
it.** Delete `state/vision/PAUSE` only on the owner's word — never to make a check pass.

## Position, 2026-11-11 cycle 23 — one colour cut can no longer pass as a clean picture, and apparel prints

Unit reports: `reports/ty/d026_fullgen_silhouette.md` (tag `ty-dir-d026-silhouette`) and
`reports/ty/pack02_apparel_flat_print.md` (tag `ty-dir-pack-02-apparel`).

| # | job | result |
|---|---|---|
| 1 | `fix-fullgen-silhouette` (D-026, rank 2) — the residue check counted pixels outside the **recorded** silhouette, and on the generation route that silhouette is the cutout, so an attached shadow sat inside it and a smear scored 0.00 % | **D-026 closed.** `check_matte_residue` takes `silhouette_source`; a colour cut (`grabcut`/`background_distance`/`otsu_lab`) returns **UNVERIFIED with words**, never a clean number. The live pass passes `generation.cutout_matte.method` through |
| 2 | `pack-02-apparel-flat-print` (rank 3) — `brand_art` knew a pouch, a carton and a cylinder, so every apparel brief was refused by name | **merged.** Apparel is a declared form with a **280 × 350 mm** chest print; the garment route measures the body from its own silhouette, keeps the artwork's aspect, refuses a blank plate by name, and `scene_render` draws the garment |

**D-026 measured on the real artefacts, no render:** `renders/d025/PO-001.png` (matte) →
0.00 %, 100.0 passed; `renders/d022_pinned/PO-001.png` (grabcut) → **14.76 %, 90.0,
`matte_residue` failed** — reproducing D-022's own number, so the two instruments now agree.

**Apparel measured: ST-017 100.0** (cream tee on 255 white, Mogra chest print inside the
body, no shadow). **ST-046 80.0** — `reference_subject` **cannot verify**: the uploaded file
`tee_charcoal-folded.jpg` is not in this checkout. The garment rendered; it cannot be scored
without the owner's file, and `cannot_verify` is a failure by contract, not a skip.

**Also closed this session, and it was corrupting the resume mirror:**
`director_queue.acceptance` was written as `[list(c) for c in "..."]`, so a 400-character
acceptance line became 400 one-character commands in `reports/ty/director_queue.json`. Now
`acceptance_list()` splits on newlines and `_repair_acceptance()` rebuilds old rows.

**Tests:** 19 in silhouette/matte/residue (6 new), 5 + 1 skipped in apparel, 92 in the
seller/composite/fill group, 21 in the queue store.

**Next, in rank order:** `reference-depth` → `pack-03-boxart-forms` → `block3-workspaces` →
`block4-seller-tests` → `block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 21 — a generated plate's cast shadow is cut by a matte, not by colour

Unit report: `reports/ty/d025_fullgen_matte_cutout.md`. Tag `ty-dir-d025-fullgen-matte`.

| # | job | result |
|---|---|---|
| 1 | `fix-fullgen-matte-cutout` (D-025, rank 1) — D-022's re-render left PO-001 at seed 2747063199 on **14.760 %** residue: the *plate's* own cast shadow, attached and opaque, survived a grabcut that cuts by colour | **D-025 closed.** `CompositeGenerator._matte_cut()` asks BiRefNet for the product's matte inside the media lane (`comfy_lane.lane(needed_gb=3.0, role="scene:matte")`); grabcut is now only a **named** fallback (`record["cutout_matte"] = {requested, method, reason}`), never the silent default |

**Ground truth on a synthetic plate with a known ellipse: matte keeps 3 band px, grabcut
keeps 768** — and the grabcut artefact reads 0.00 % on the residue check, which is D-026
proven rather than assumed (the control test asserts it).

**Real lane, the same pinned seed: 100.0, residue 0.00 %, `cutout_matte.method=birefnet`,
the smear gone, the label copy intact.** The honest limit: the two artefacts differ in
framing, so that pair is visual + score, not per-pixel truth; the synthetic plate is the
instrument with truth.

**Also fixed, and it was hiding results:** `scorers._product_mask_from_cutout` returned
`None` for the cutout's PNG **bytes**, so the residue check was *skipped* (and reported
`ok`) whenever a caller passed bytes. It decodes them now.

**Two things this session had to repair first:** four autonomous lanes were alive on one
queue (the launcher's director, the tys launcher and its agent, an orphaned
`rerender_prompt_only.py` plus a second ComfyUI on the same port). One director now holds
the lease (`state/director/director.pid` → the opencode service serving this session), the
others were interrupted through the server API, and the duplicate GPU lane was stopped.

**Tests:** 4 in `test_fullgen_matte_cutout.py` (written before the code) + 1 lane-gated;
43 in the residue / fullgen-white / composite group.

**Next, in rank order:** `fix-fullgen-silhouette` (D-026) → `pack-02-apparel-flat-print`
(its plate form, brand art and briefs are already in the tree, uncommitted) →
`reference-depth` → `pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 20 — three thin reference categories deepened, and a claim corrected

Unit report: `reports/ty/reference_depth.md`. Tag `ty-dir-reference-depth`.

| # | job | result |
|---|---|---|
| 1 | `reference-depth` (rank 5) — `ceramic_mug` had 2 usable references, `food_jar` and `skincare_bottle` had 1 each; a category with one photo is one photo's opinion | **partly met, and said so.** 6 public references fetched through `reference_coverage.fetch` (Openverse, CC0/BY/BY-SA, licence + licence URL + source page on every row), **5 kept and 1 refused on visual review** — the CC0 "Body wash bottle clipart" is an illustration, not a photograph. `ceramic_mug` 2 → 3 and `food_jar` 1 → 3 in usable depth |

**The acceptance is NOT met and the row count is not the measure.** The coverage tool counts
an image only if it has no `reject` verdict; fourteen rows already carried rejections from the
2026-11-09 review, so five categories hold three rows and only one or two usable pictures:
`pet_product` 1, `toy` 2, `tool` 2, `small_appliance` 1, `electronics_accessories` 1. I wrote
"below 3: []" from row counts first and corrected it in the report — the tool's table is the
number to quote. Queued as `reference-review-backfill` (rank 5).

**Tests:** 5 in `test_reference_coverage.py`; `python tools/reference_coverage.py` regenerates
`reports/ty/reference_coverage.md` (56 of 56 briefs covered, 28 usable of 42 reviewed).

**Next, in rank order:** `pack-02-apparel-flat-print` → `reference-review-backfill` →
`pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 19 — D-022 measured on a real lane, and its sibling defect fixed

Reports: `reports/ty/d022_fullgen_white_composite.md` (measurement section),
`reports/ty/d024_composite_shadow.md`. Tags `ty-dir-fix-fullgen-white-composite`,
`ty-dir-fix-composite-white-shadow`.

| # | job | result |
|---|---|---|
| 1 | `d022-real-rerender` (rank 3) — D-022 was fixed by test but not yet measured on a real render | **done.** The lane came free; `composite --limit 2 --renderer comfy --method birefnet --model sdxl` ran. `check_matte_residue`: PO-001 **25.647 % → 0.000 %** (1 025 874 px → 0 px, 1 022 424 of them neutral before) |
| 2 | found on the same run: **SR-001** (white-main, composite route) carried **11.473 %** residue — 458 900 of 458 901 px neutral | **D-024 closed.** The composite's white-main guard measured the four **corners**, which a shadow under the product never touches. `_composite` now places with `shadow=not white_main`; two checks (white-main `False`, lifestyle `True`) |

**The 25.647 % → 0.000 % is a real render**, at the model's own seed, on the app's own path
(`renders/d022/PO-001.png`); the before is the published artefact that scored 100.0.
Record: `reports/ty/d022_residue_before_after.json`.

**Still owed, and queued:** the real-lane after-number for SR-001 (`d024-real-residue`,
rank 2) — the GPU lock was held by another lane (`role: seller_composite`, pid 2144) when
this unit closed, and one heavy lane at a time is the rule.

**Tests:** 26 in the composite group, 4 in the full-generation group.

**Next, in rank order:** `d024-real-residue` → `pack-02-apparel-flat-print` →
`reference-depth` → `pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 18 — cartons carry their safe layer, and the packaging lane is 8/8

Unit report: `reports/ty/d023_carton_safe_layer.md`. Tag `ty-dir-fix-carton-safe-layer`.

| # | job | result |
|---|---|---|
| 1 | `fix-carton-safe-layer` (D-023, rank 1) — `package_readiness.REQUIRED_LAYERS` needs trim, fold **and safe**, and `build_carton` never emitted `safe`; the app blocked every carton and sleeve it printed | **D-023 closed.** `_panel_blank(..., safe_mm=)` writes one safe rectangle per body face, inset from the trim and from both folds; `build_carton(..., safe_mm=)` and all three carton templates declare it (default 3 mm) and `build_from_template` passes it through |

**Measured on the same eight briefs, same engine: 2/8 → 8/8 passed, mean 78.6 → 100.0.**
Safe margins are now readable per artefact: 5 mm on the two doypacks, 3 mm on the six
cartons. `reports/ty/packaging_pass.json`, artefacts in `renders/packaging/`.

**Tests:** 13 in `test_carton_safe_layer.py` (written first — including "each safe rectangle
sits inside the trim by the margin on all four sides" measured against the trim polyline's
own bounding box, and "the margin is the brief's own number"), 80 + 45 related green.

**Next, in rank order:** `d022-real-rerender` → `pack-02-apparel-flat-print` →
`reference-depth` → `pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 17 — packaging is a real lane, and the app's own gate blocks six of eight

Unit report: `reports/ty/sel04_packaging.md`. Tag `ty-dir-sel-04-packaging`.

| # | job | result |
|---|---|---|
| 1 | `sel-04-packaging` — packaging was never exercised: the app owns a dieline engine (`design_studio_print`: geometry gate, layered SVG, PDF) and `package_readiness`, and no seller brief asked for packaging | **merged as a real lane.** 8 briefs over 4 templates (`doypack`, `tuck_end`, `rsc_box`, `sleeve`), 7 mechanical checks, a gap file, and `python -m tools.seller_tester packaging` |

**Measured: 8 scored, 2 passed, 6 failed, mean 78.6.** The two doypacks are 100.0. The six
cartons/sleeves fail `layers` + `readiness` for one reason: **`build_carton` emits no `safe`
layer**, and `package_readiness.REQUIRED_LAYERS` is `("trim", "fold", "safe")`, so the app's
own retail-readiness gate refuses every carton and sleeve it prints — in its own words,
*"dieline is missing its 'safe' layer"*. Filed **D-023**, queued rank 1 as
`fix-carton-safe-layer`.

**The checks are mechanical, so no judge is involved:** sheet mm, panels (doypack named
faces; carton body widths + glue + both bleeds spanning the sheet), bleed, safe, the four
layer kinds, the PDF page in points, and the app's readiness verdict.

**Tests:** 9 in `test_seller_packaging.py`, including the geometry gate refusing a
`rsc_box` with flaps deeper than its body **by name** (`tab_deeper_than_body`) and writing
no file.

**Next, in rank order:** `fix-carton-safe-layer` (D-023) → `d022-real-rerender` →
`pack-02-apparel-flat-print` → `reference-depth` → `pack-03-boxart-forms` →
`block3-workspaces` → `block4-seller-tests` → `block5-production-hardening` →
`block7-verification` → D-019.

## Position, 2026-11-11 cycle 16 — a main image is composed without the composite's own shadow

Unit report: `reports/ty/d022_fullgen_white_composite.md`. Tag `ty-dir-fix-fullgen-white-composite`.

| # | job | result |
|---|---|---|
| 1 | `fix-fullgen-white-composite` (D-022, rank 2) — the full-generation route already composes the product on the brief's flat canvas, then called `place_product` with its default `shadow=True`; that soft ellipse *is* the grey pool on 255 white | **D-022 closed.** `_generate_cut_and_compose` passes `shadow=not flat(brief)`: a uniform/white-matte brief gets no shadow, a free/scene brief keeps it |

**Measured before the fix, from D-020's audit:** eight published artefacts at **10.2 – 25.6 %
background residue**; PO-001 was 25.6 %. The shadow is not a model artefact — it is
`product_composite._contact_shadow`, 1.15 × product width, blurred, filled `(18,14,10)`, and
it was added on purpose (D-018 reserved its footprint so it could not be clipped). The bug
was that a main image kept it.

**The real re-render was refused, and is queued rather than claimed:** `budget: refused:
8.48 GB free - 8.2 GB needed = 0.28 GB < 1.0 GB reserve` — `qwen2.5vl:7b` sat on the GPU for
another lane and its lease was **extended** mid-attempt (03:36 → 03:42), so it is in use and
not mine to unload. `d022-real-rerender` (rank 3) is the number that retires it.

**Tests:** 4 in `test_fullgen_white_composite.py` (written first, including the control: the
same composition with the shadow on **fails** the residue check), 91 in the seller group.

**Next, in rank order:** `d022-real-rerender` → `sel-04-packaging` → `pack-02-apparel-flat-print`
→ `reference-depth` → `pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 15 — a main image gets a shadowless plate, drawn and real

Unit report: `reports/ty/d021_drawn_plate_shadow.md`. Tag `ty-dir-fix-drawn-plate-shadow`.

| # | job | result |
|---|---|---|
| 1 | `fix-drawn-plate-shadow` (D-021, rank 1) — the drawn plate drew a base ellipse and **every** plate prompt asked FLUX for "a gentle contact shadow", including main images, where the cutout then keeps it inside the silhouette and no check can see it | **D-021 closed.** `synthetic_plate(shadow=False)` draws no ellipse and the drawn renderer passes `shadow=not white`; `plate_brief(..., shadow=False)` rewrites the clause in every branch (package, bundle, cylinder, `plate_subject`) and `build()` chooses it from the background |

**Measured, drawn route, before → after** (`reports/ty/d021_plate_shadow.json`,
`reports/ty/d021_contact.png`): PO-001's neutral mid-grey px **941 848 → 30 820** and its
product box **1280 × 1748 → 1192 × 1877** — the product is 7 % taller because the crop no
longer wastes height on a shadow. PO-003 **64 405 → 8 006**. PO-004 (gift box) **unchanged**,
the control: that form never drew a shadow. Pass unchanged: 4/4, mean 100.0.

**The real route is proven by test, not by a re-render:** `plate_brief(shadow=False)` carries
no shadow ask on all three forms and on a bundle; a fresh FLUX plate is a 70–90 s lane and
belongs to the next real pass.

**New, and the reason the 8 failing published outputs are still failing:** **D-022** — a
full generation (`SDXL`/`FLUX` scene) has no white-composite step, so a main-image brief gets
a generated sweep with a grey pool (10.2–25.6 % of the frame). Queued rank 2.

**Tests:** 5 in `test_plate_shadow_brief.py` (written first), 34 + 1 skipped in the
picture/plate group, 136 in the seller/package group.

**Next, in rank order:** `fix-fullgen-white-composite` (D-022) → `sel-04-packaging` →
`pack-02-apparel-flat-print` → `reference-depth` → `pack-03-boxart-forms` →
`block3-workspaces` → `block4-seller-tests` → `block5-production-hardening` →
`block7-verification` → D-019.

## Position, 2026-11-11 cycle 14 — the background is measured on the whole frame, and eight published 100.0s do not survive it

Unit report: `reports/ty/d020_matte_residue.md`. Tag `ty-dir-fix-matte-residue-check`.

| # | job | result |
|---|---|---|
| 1 | `fix-matte-residue-check` (D-020, rank 1) — the two instruments that exist for "is the background flat" sample the four **corners** and an outer **ring**, so a shadow under the product passes both | **D-020 closed.** `scorers.check_matte_residue` measures the whole frame outside the product's silhouette; `background` 0.20 → 0.10 + `matte_residue` 0.10 (the denominator is unchanged, and a picture with no silhouette keeps the old single weight), critical where graded |

**The measurement, on the published artefacts** (`reports/ty/d020_residue_audit.json`):
the 12 full-generation outputs re-score as **8 checked, 8 failed, residue 10.2 – 25.6 % of
the frame, mean 100.0 → 90.0**. PO-001 alone is 25.6 %. The control is a fresh drawn pass
with the new wiring: 0.00 % residue, still 100.0 — the check does not fire on a clean
picture. `ty/seller_scores.json` now carries that statement next to the 96.2 rather than a
quietly rewritten mean.

**Three provenance defects were fixed to make the check possible at all:** the harness
loaded a cutout **only** on the composite route (0 of 20 `product_picture` artefacts ever
reached the scorers), `generation.product_box` is null on that route, and the app's own
manifest beside the picture carries the truth. All three are in `harness.py`.

**New, and the reason the drawn plates are unmeasured:** **D-021** — the drawn plate draws
its own base shadow, so the silhouette *includes* it and the residue check reads 0.00 % on
a picture that visibly has a shadow. **D-022** — a full generation has no white-composite
step, which is why its background is a grey pool. Both queued, ranks 1 and 2.

**Tests:** 9 in `test_matte_residue.py` (written first), 95 in the seller/scorer group,
15 + 1 skipped in the plate/picture group.

**Next, in rank order:** `fix-drawn-plate-shadow` (D-021) → `fix-fullgen-white-composite`
(D-022) → `sel-04-packaging` → `pack-02-apparel-flat-print` → `reference-depth` →
`pack-03-boxart-forms` → `block3-workspaces` → `block4-seller-tests` →
`block5-production-hardening` → `block7-verification` → D-019.

## Position, 2026-11-11 cycle 13 — the contact shadow is gone, and the colour cut was worse than it

Unit report: `reports/ty/d017_plate_shadow_matte.md`. Tag `ty-dir-fix-plate-shadow-matte`.

| # | job | result |
|---|---|---|
| 1 | `fix-plate-shadow-matte` (D-017, rank 0) — a studio plate's contact shadow is opaque **and attached**, so the largest-blob pass could not drop it and the main image shipped with a grey smear under the product | **D-017 closed.** `product_cutout.matte_alpha` runs BiRefNet through the media lane and raises `MatteUnavailable` **by name** when the cold lane cannot supply one; `_place_on_flat(matte="birefnet" \| "auto" \| "none")` and `build(matte=)` route it; the face record and the manifest state which matte produced the picture and how many px it rejected |

**Measured on a real plate, both instruments on the same image**
(`renders/comfy_plate7/ST-002/_rejected/front_plate.png`, a white mug on a pale sweep),
inside one lane: the matte returns the mug at **1162 × 1000 in 3.68 s**; the colour cut
returns a **1934 × 1137 band across the frame** that keeps **53.2 %** of the product and
leaves the handle in three fragments. The matte rejects **130 357 px** the colour cut had
kept, of which **99.73 %** are dark and neutral — the shadow. Border contact 0.0.
Contact sheet: `reports/ty/d017_contact.png`. Record: `reports/ty/d017_matte_measure.json`.

**Honest limit, repeated from the report:** the published seller dimension does not move
(96.2 over 32 drawn-plate outputs — drawn plates have a drawn shadow). And **the scorers
cannot see this defect**: `check_background` samples the corners, `check_alpha_matte`
samples an outer ring, so a shadow under the product passes both. Filed as **D-020** and
ranked **1** for the next cycle.

**Tests:** 8 in `test_plate_shadow_matte.py` (7 run cold, 1 needs `NS_PLATE_MATTE=1`),
30 in the picture group, 66 in the package/composite/label group, 78 in the seller group.

**Next, in rank order:** `fix-matte-residue-check` (D-020) → `sel-04-packaging` →
`pack-02-apparel-flat-print` → `reference-depth` → `pack-03-boxart-forms` →
`block3-workspaces` → `block4-seller-tests` → `block5-production-hardening` →
`block7-verification` → D-019.

## Position, 2026-11-11 cycle 12 — the fill instrument can see white on white

Unit report: `reports/ty/d018_fill_instrument.md`. Tag `ty-dir-d018-fill`.

| # | job | result |
|---|---|---|
| 1 | `fix-shadow-and-white-fill` (rank 3) — ST-024 read 20.7 % against a 24 % floor and ST-031 19.8 % against 20 %, because `subject_fill` measured the share of pixels that differ from the corner colour and a white product on 255 white differs by ~5 levels | **D-018 fixed.** `_product_mask_from_cutout` maps the product's own silhouette onto the frame, and the fill check uses it **only when the corner instrument is blind** (under 5 % on a flat background). `product_picture.build` now records `product_box` and writes `<face>.cutout.png` — without that provenance the fallback cannot fire |

**No published score moved:** re-scoring the twelve prompt-only artefacts leaves
`instrument: corner_colour` on **12 of 12**, so the fallback fires only where the old
instrument was blind. Proven by test against a known 36 % white-on-white product (corner
reads under 2 %, the cutout reads 35.0–37.0 %).

**Still owed:** ST-024/ST-031 were rendered before the provenance existed and have
`product_box: None`; their new number needs a white-main re-render at the pinned seeds.

**D-017 is not done and is not claimed:** a plate's opaque contact shadow still survives
the cutout; its own comment says a real matte (BiRefNet in the lane) is what removes it.
Queued as `fix-plate-shadow-matte`.

**Tests:** 8 in `test_subject_fill_instrument.py`, 8 in `test_product_picture_white_main.py`,
74 in the package/composite/label group, 89 in the seller group.

**Next, in rank order:** `fix-bundle-units` (D-012) → `fix-plate-shadow-matte` (D-017) →
`reference-depth` → `block3-workspaces` → `block4-seller-tests` → `pack-02-apparel-flat-print`
→ `pack-03-boxart-forms` → `block5-production-hardening` → `block7-verification` →
`sel-04-packaging` → D-019.

## Position, 2026-11-11 cycle 11 — the label sits on the pack, and the pack is whole

Unit report: `reports/ty/label_conform.md`. Tag `ty-dir-fix-label-conform`.

| # | job | result |
|---|---|---|
| 1 | `fix-label-conform` (rank 1) — the label was a flat rectangle drawn from the product's bounding box and pasted over a taper; nothing clipped it to the product; the cutout kept a 20 px stick, a ring and a ghost pack | **merged.** `face_quad` measures the quad on the silhouette's body band (rows ≥ 55 % of the widest row) and `warp_label(mask_png=)` clips every written pixel to the mask; `product_composite.drop_detached_specks` + `drop_thin_runs` clean the cutout (a bottle neck survives at 37 % of body width) |

**Twelve prompt-only briefs, real renders, seeds pinned to the previous proof:
12 scored, 12 passed, mean 100.0** (PO-012 was 80.0 — subject_fill 24.8 % against a
25.0 % floor). Every label is inside the silhouette: **0 px outside on 12 of 12**,
label width 55–92 % of the body, height 20–39 %. Cutout cleanup removes **266 thin
rows** (PO-001 230, PO-006 36) and 0 in the other ten.

**Local vision judge (`gemma3:4b`, loopback):** "one label panel **on** the product,
not a card beside it" **12/12**; "free of stray marks" **10/12** — PO-006 and PO-007
carry a stick, a dashed rule and a ring drawn into the **scene**, which is kept as the
background for a free-background brief. **D-019** filed with that diagnosis.

**Tests:** 12 in `test_seller_label_warp.py` (5 new), 97 in the composite / seller /
stage groups. Contact sheet: `reports/ty/label_conform_contact.png`.

**Next, in rank order:** `fix-shadow-and-white-fill` (D-017/D-018) → `fix-bundle-units`
(D-012) → `reference-depth` → `block3-workspaces` → `block4-seller-tests` →
`pack-02-apparel-flat-print` → `pack-03-boxart-forms` → `block5-production-hardening`
→ `block7-verification` → `sel-04-packaging` → D-019.

## Position, 2026-11-11 cycle 10 — the label is scaled to the body that is in the plate

Unit report: `reports/ty/d016_label_scale_plate.md`. Tag `ty-dir-fix-label-scale-plate`.

| # | job | result |
|---|---|---|
| 1 | `fix-label-scale-plate` (D-016) — a pale body on a pale sweep was cut at a fixed 16 levels, so the silhouette edge was never in the mask and the label was printed small; and the plate brief was per *form*, so a mug was asked of the model as an anonymous tube | **merged.** The mask cut is relative to the plate's own contrast (`max(5.0, min(threshold, 0.20·p99.5))`); the vertical extent stays on the caller's firm cut; each cylinder design declares its `plate_subject` and `plate_brief(face, form, design)` asks for that object |

**Measured on a fixture whose truth is exact:** 479 px measured of a 500 px body →
**493 px** (+2.9 % label scale), body height 900 px exact. A shadow 0–45 % of the
body height does not widen the band (+0.0 %); plate grain moves it to 491 px. The
earlier idea of relaxing the column-growth hysteresis 0.35 → 0.22 was **rejected on
measurement** (+4.8 % over-measure behind a 22 %-tall shadow) and left at 0.35.

**Tests:** 27 in `test_package_cylinder_form.py` (4 new), 79 in the compositor /
package / geometry group, 75 in the seller-tester group. Held-out modes pass (6
briefs, drawn): 6/6, mean 100.0 — a subset, not comparable with cycle 9's 20-brief 95.0.

**Two directors were alive at 01:05–01:23 (D-011, the takeover race);** the other
session had already swept this unit's three source files into `80ad1659` before it
released the lease. Content verified at HEAD by `grep`, not assumed.

**Next, in rank order:** `fix-label-conform` → `fix-shadow-and-white-fill`
(D-017/D-018) → `fix-bundle-units` (D-012) → `reference-depth` → `block3-workspaces`
→ `block4-seller-tests` → `pack-02-apparel-flat-print` → `pack-03-boxart-forms` →
`block5-production-hardening` → `block7-verification` → `sel-04-packaging`.

## Position, 2026-11-11 cycle 9 — a main image is now the product alone on white

Unit report: `reports/ty/white_cutout_main.md`. Tag `ty-dir-white-cutout-main`.

| # | job | result |
|---|---|---|
| 1 | `white-cutout-main` (D-015) — a main-image brief was scored on a photograph of a product on a sweep, so `background` and `alpha_matte` failed | **merged.** The cutout runs on the **plate**, before the label is composed (cutting the finished picture punched the label's light panel out and took the wordmark with it); the product is stood on the brief's value at a share of the canvas **area** from the brief's own fill band; a free/scene background keeps the photograph |

**Real plate: ST-001 70 → 100.** The delivered picture is a kraft pouch with its
real wrinkles, the designed label on the front panel, on 255 white, corners ≥ 250,
border std ≤ 4 (`renders/comfy_plate6/ST-001/product_front.png`).

**Drawn catalog pass: 20/20 passed, mean 95.0** — ceramic_mug 90, food_jar 100,
pet_product 92.5, skincare_bottle 92.5, supplement_pouch 100. Published seller
dimension **96.2 over 32 outputs**.

**New defects:** D-017 a plate's opaque contact shadow survives the cutout (needs a
real matte — BiRefNet in the lane — not a colour threshold); D-018 a **white product
on a white canvas** defeats the fill instrument (ST-024 20.7 % vs 24, ST-031 19.8 %
vs 20), because it measures the subject by difference from the corner colour.

**Next, in rank order:** `fix-label-scale-plate` (D-016) → `fix-shadow-and-white-fill`
(D-017/D-018) → `pack-02-apparel-flat-print` → `pack-03-boxart-forms` →
`sel-04-packaging` → `fix-bundle-units` → `ux-0610-live-verify`.

**Still the honest ceiling:** every drawn-plate number is a stand-in photograph. The
real-plate lane works and costs 70–90 s per picture, so a full 20-brief real pass is
a scheduled lane (`python tools/comfy_plate_pass.py --limit 20`), not an interactive
one.

## Position, 2026-11-11 cycle 8 — the render lane is real, and one real plate scores 100

Unit report: `reports/ty/comfy_plate_live.md`. Tag `ty-dir-comfy-plate-live`.

| # | job | result |
|---|---|---|
| 1 | `comfy-plate-live` — `engine_status()` had said *armed but unreachable* since 2026-11-08 | **merged.** ComfyUI is started by `tools/comfy_lane.lane()` (`--cache-none`), the pass runs, the process is stopped in `finally`; the proof the VRAM came back is that the process exited, not a `/free` acknowledgement. New `tools/comfy_plate_pass.py` runs one pass inside one lane |
| 2 | the harness's `--renderer comfy` refused every brief | fixed: the comfy route no longer injects a plate, it calls the app's own FLUX 3 Klein text-safe lane, so the number is the product |
| 3 | the cylinder measurement was pouch geometry | `find_cylinder_bands`: difference from the plate's own background + a column profile with hysteresis. The old measurement returned a **153 × 121 px patch of shadow** on a 410 px body |

**Real plates: ST-002 (ceramic mug) 100 passed; ST-001 (pouch, white-background
brief) 70, failing `background` and `alpha_matte`.** One `pp.build` on a real plate
measured **72.4 s**. Lane row in `state/gpu/comfy_lanes.jsonl`; afterwards port
closed, 16.0 GB VRAM free, 7.6 GB RAM free.

**The two findings that matter:**
1. **D-015** a main-image brief needs the product **cut out on 255 white**; the app
   composites onto a photograph of a sweep. That is a missing path, not a lane fault.
2. **D-016** on a white body against a pale sweep the measured body is narrower
   than the body, so the label is drawn too small; and a mug is drawn as a plain
   cylinder because the plate brief is per *form*, not per category.

**Next, in rank order:** `white-cutout-main` (D-015) → `fix-label-scale-plate`
(D-016) → `pack-02-apparel-flat-print` → `pack-03-boxart-forms` →
`sel-04-packaging` → `fix-bundle-units` → `ux-0610-live-verify` (parked:
`python tools/ty_unlock_checks.py --status`).

**Lane discipline that is now proven, keep it:** one real-plate pass at a time,
inside `comfy_lane.lane()`. With ComfyUI resident the app's own guard refused a
second render at 2.6 GB free (`system_ram_insufficient: free 2601 MB, need 4096 MB`).

## Position, 2026-11-11 cycle 7 — a third form, and the sample is 20 briefs across five categories

Unit report: `reports/ty/pack01_rigid_cylinder.md`. Tag `ty-dir-pack-01`.

| # | job | result |
|---|---|---|
| 1 | `pack-01-rigid-cylinder-form` — the app printed a pouch and a carton; a mug, a bottle and a tub had no form | merged. `CYLINDER` is a declared form with its own plate brief, its own insets and a **physical** label band: the body's measured width gives px-per-mm, the design's declared label height gives the band height, and a label taller than the body is refused as `label_too_tall_for_body`. Four designs (`word-coffee-canister`, `word-coffee-mug`, `harbor-body-oil`, `pine-paws-joint`), label front/back renderers, `warp_cylinder` now takes the RGB panel the app produces, drawn cylinder body. 23 tests |
| 2 | the catalog | 12 prompt-only briefs wired through the app path (mug 4, skincare 4, pet 4); 5 uploaded-reference briefs left alone for want of a file |

**Published seller dimension: 96.9 over 32 outputs, 32 passed** (was 98.0 over 20).
The catalog pass alone: **20 scored, 20 passed, mean 96.0, five categories**
(ceramic_mug 90, food_jar 95, pet_product 90, skincare_bottle 95, supplement_pouch 100).
Coverage up 60 %, mean down 1.1 — the new pictures are a harder set.

**Checks that fail inside passing pictures:** ST-011/ST-027 are *infographic*
briefs that require margin ink and the app has no overlay layer (D-013); ST-029 is
a `food_jar` brief whose design is the Word Coffee gift box, so it misses a bundle
fill band (D-012). Both are stated in the report, not hidden.

**One command that changes the next number:** start ComfyUI, then
`python -m tools.seller_tester product --renderer comfy --skip-unavailable`.
Every plate stops being drawn — that is job rank 1 (`comfy-plate-live`).

**Next, in rank order:** `comfy-plate-live` → `pack-02-apparel-flat-print` →
`pack-03-boxart-forms` (small appliance + tool) → `sel-04-packaging` →
`fix-bundle-units` (D-012) → `ux-0610-live-verify` (still parked:
`python tools/ty_unlock_checks.py --status`).

## Position, 2026-11-11 cycle 6 — the sample is 20 outputs, and six product categories have no form

Reports: `reports/ty/sel_refs_designs.md`, `reports/ty/sel08_prompt_only_coverage.md`, and the
`sel-06`/`sel-07` corrections below.

| # | job | result |
|---|---|---|
| 1 | `sel-refs-designs` — the rubric had no source | merged. `tools/reference_scout.py`: Openverse, `cc0`/`by`/`by-sa` only, a landing URL to verify at, ≥700 px, a packaging word in the row's own text, and the file must open or it is deleted. **17 kept / 51 refused** over 7 packaging families, every row with creator, licence + version, licence URL and source page. 8 tests |
| 2 | `sel-08-prompt-only-coverage` — the seller sample was stuck at 12 | merged. 8 prompt-only briefs wired to the app path (**8/8, mean 97.5**); **24 refused** with one true reason: *"declares no product_line"* — ceramic mug, apparel, skincare bottle, small appliance, pet product, tool. A catalog pass now records a refusal and continues instead of dying on it |
| 3 | the media flag | fixed. `MEDIA_GEN_LIVE=1` **is** set in `.env`; `engine_status()` said "unarmed" in every tool run because only the API loads dotenv. It now loads the repo `.env` and reports the truth: **gate on, ComfyUI unreachable — start ComfyUI.** Four reports were corrected; 4 tests |
| 4 | `units` through the API | merged. `ProductPictureIn.units` 1–6, passed to `build`; 22 tests in `test_package_forms` |

**Published seller dimension: 20 outputs, mean 98.0, 20 passed** (judged + mechanical held-out + the
catalog pass, deduped by brief). design-studio **89.7**, 4 services at bar.

**Next unit is named, and it is not a brief edit:** the app prints `stand_up_pouch` and `gift_box`, and
the catalog asks for **eight** product categories. A rigid-cylinder form (jar/bottle/tube, via
`mockup_compositor.warp_cylinder`) is the smallest real addition; apparel flat-print and appliance
box-art follow. 24 of 32 prompt-only briefs are waiting on that, not on more testing.

**One command that changes the next number:** start ComfyUI, then
`python -m tools.seller_tester product --renderer comfy --skip-unavailable`. Every plate stops being
drawn.

## Position, 2026-11-11 cycle 5 — bundles measure as bundles

Report: `reports/ty/sel07_bundle_units.md`.

| # | job | result |
|---|---|---|
| 1 | `sel-07-bundle-and-body-shape` — PO-012 asked for three units and measured one | merged. `package_components` keeps every package-sized component (the single-subject mask held **1** component of 343,596 px — the first box only); `find_panel_quads` measures each on its own crop with the neighbours flattened; `build(units=3)` warps one panel per measured face and refuses `units_not_found: measured N of M`. PO-004/PO-012: **3 quads, fill 25.9 % (was 20.3 %), score 100**. The briefs' `body_prompt` said "one unit shown" against a three-unit prompt — corrected. |

**Also fixed, and worth remembering:** `stock_from_brief` matched colour words as substrings, so the
tagline "One Message at a Time" contains **sage** and every Word Coffee box was painted sage-green.
Word boundaries now.

**Judged pass: 12/12, mean 98.3** (was 11/12, 94.9). Seller dimension **98.3**, design-studio
**89.8**, 4 services at bar. The judge moved on PO-002 — the *lifestyle* brief — on the **same flat
sweep**, so its verdict tracked colour, not scene. It is weak evidence for colour and copy and no
evidence for a scene; recorded in the report.

**Next, in rank order:** `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (still parked: `python tools/ty_unlock_checks.py --status`).
Arming `MEDIA_GEN_LIVE` and running `--renderer comfy` remains the one thing that turns every plate
from drawn to real.

## Position, 2026-11-11 cycle 4 — the app prints two forms, and the seller number is the product's

Two jobs merged, both of them structural. Reports: `reports/ty/sel06b_second_brand.md`,
`reports/ty/sel06_product_pipeline.md`.

| # | job | result |
|---|---|---|
| 1 | `sel-06b-second-brand` — the app could print **one** packaging form for **one** brand | merged. `brand_art` is a dispatch layer; the folding-carton renderers are new; a brand is a data entry. Pouch output sha256 `e0160055bf0884c1` **unchanged**. 17 new tests, 55 packaging tests pass, OCR gate on both carton faces, local judge 4/4 at 95 |
| 2 | `sel-06-exercise-product-pipeline` (D-011) — the harness rendered its own lookalike | merged. `ProductPipelineGenerator` calls `product_picture.build` with a supplied plate; refusals carry the app's own reason. Prompt-only 12 held-out briefs, both brands: **12/12 mean 97.5** mechanical, **11/12 mean 94.9** judged |
| 3 | the seller dimension read the harness | merged. `seller_scores.py` publishes the app pass; harness pass not averaged beside it. design-studio **75.9 → 89.3**, seller 94.9 over 12 generated outputs; **4 services at bar** (hub, prospector, keyword-tracker, profitability 100) |

**What the 94.9 does not prove.** The plate is `drawn` (`synthetic_plate`) because
`studio_generation.engine_status()` reports `armed: False` — `MEDIA_GEN_LIVE` is not 1 and ComfyUI is
not reachable. The plate is named in the published record (`pipeline.plate_source: "drawn"`), and the
one judged failure (PO-002) is that plate: the judge's own reasons are "the counter is not a light oak
kitchen counter", "the lighting is not morning light". **Arming the lane and running
`python -m tools.seller_tester product --renderer comfy` is the next real measurement.**

**Next, in rank order:** `sel-07-bundle-and-body-shape` (PO-012 measures one unit of three; the pouch
prompts drew a box twice) → `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (still parked: `python tools/ty_unlock_checks.py --status`).

## Position, 2026-11-11 cycle 3 — prompt-only is honest now, and the label gap is named

Unit report: `reports/ty/rerender_prompt_only_20261111.md`. Six jobs merged, two defects closed.

| # | job | status |
|---|---|---|
| 1 | `rerender-prompt-only` — 12 briefs re-rendered at the same seeds: 9/12 mean 86.4 → 10/12 mean 93.9 | merged |
| 2 | `fix-shadow-frame-clip` — the contact shadow ran past the frame edge and was cut; the six "exactly 90.0" rows were this, not the flat() branch | merged |
| 3 | `fix-fill-and-judge-instruments` — `subject_fill` measured the corner colour on a scene; the judge rubric named the taxonomy slot instead of the product | merged |
| 4 | `fix-queue-mirror-divergence` — the store held 35 jobs while the resume mirror held 51; `mirror()` deleted the difference. 16 jobs recovered, 14 statuses refreshed, `rank` migrated | merged |
| 5 | `fix-launcher-heartbeat-red` (D-010) — heartbeat is red when the stream's last line is an error (243 such lines were on disk) | merged |
| 6 | `fix-dev-start-pids` (D-009) — the pid record is resolved from the listeners and pruned of the dead | merged |
| 7 | `ppc-upload-live` — upload → propose → approve → write v1 → write v2 → download, hash matches | merged |
| 8 | `sel-05-label-fidelity` — label composed and warped onto an unlettered body: judged **83.5 → 98.7**, 12/12 | merged |
| 9 | visual gate, first live run — 62 captures (31 views × desktop + iPhone 12 WebKit) at `/ui/`, no baseline without a passing scorecard; three views described by the local model as real workspaces (`reports/ty/visual_gate_and_views_20261111.md`) | evidence, no code change |

**The seller number, per mode, never blended:** prompt-only 12 scored / **12 passed / 98.3**
mechanically; with the local vision judge (`gemma3:4b`, loopback) **12 passed / 98.7**. Stored
12/11/91.8, uploaded 21/16/90.0 — 45 scored, 39 passed, mean 92.7. **All of it is the harness
pipeline, not the app's** (D-011 below).

**Next, in rank order:** `sel-06-exercise-product-pipeline` (D-011 — until it lands, every seller
number is a harness number) → `sel-07-bundle-and-body-shape` (PO-012 measures one unit of three; the
pouch prompts drew a box twice) → `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (desktop still locked: `tools/ty_unlock_checks.py
--status` says `no foreground window`).

**`sel-coverage-44` was blocked on a measuring error, not on missing work:** 32 of its 44 are
prompt-only briefs, which must *not* have a reference — a prompt-only brief with a stored reference
stops being prompt-only. The real gap is 12 uploaded-reference briefs with no file, plus design depth.

**Defects filed or closed this cycle:** D-008 closed (it was misdiagnosed; the proof carries the
correction), D-009 closed, D-010 closed, D-011 filed (the seller tester renders a lookalike
pipeline), plus three new ones in-repo: the queue/mirror divergence, the clipped shadow, and the two
invalid instruments.

## Queue lease, 2026-11-11T02:08Z — this session holds it (pid 24680, launcher-started)

Step (1) of the resume order, measured before any work:

| check | result |
|---|---|
| `state/director/director.pid` | pid 8864, written `2026-11-11T00:32:40+00:00` — **process gone** (`Get-Process -Id 8864` → nothing) |
| live `--agent director` session | **none** |
| `NorthstarTyDirector` scheduled task | **Running**, started `2026-11-09 09:59:35`, last result `267009` (0x41301, still running) |
| launcher child sessions | **every one dies in under a second with `Agent not found: "director"`** — `logs/ty_director_stream.jsonl` is 73 identical error lines; `logs/ty_director.log` shows a five-minute restart cadence since 2026-11-10T19:40 |
| `NorthstarTysWatchdog` task | Ready, last result `-1073741510` (control-C exit) — **not** keeping anything alive |
| queue lock | there is no separate lock file; the pid file is the lease (`scripts/ty_director.py:find_director`) |

**Conclusion: no other director holds the queue.** The lease is free, so this session claimed every
unclaimed job. The lease was held at the opencode process serving this session (pid 21844) so the
launcher's `find_director` saw a live director and stopped spawning dead children; it is **released at
the end of the unit** (the pid file is cleared) so the launcher resumes on its next tick — and now it
can, because the lane it starts exists.

**Defect found and being fixed:** `opencode.jsonc` defines `tys`, `verifier` and `research` — there is
no `director` agent, so the launcher's `opencode run --agent director` has been failing since it was
installed. The director lane was never actually alive outside a manual chat session. Fixing the config
is a one-line addition; the proof is a launcher tick that reports `running` with a real pid.

## LAUNCH PUSH, 2026-11-11T06:10Z — lease taken, Blocks 1 and 2 measured

**Lease.** The launcher had spawned a director after the previous unit released the lease
(`ses_e36f86943ffe7yUb1Q7ErT5EXg`, pid 26000). That session was live and mid-tool-call, so it was
**stopped at 06:09Z** to enforce one-director-per-queue, and the lease was written to the opencode
service that serves this owner-initiated session. Its uncommitted work was preserved in commit
`80ad1659` (brand_art/mockup_compositor/product_picture + a cylinder-form test, 24 tests green) and
its queue entries (D-012, D-016, D-017/018, packaging forms) were kept and re-ranked.

**Defect found in the takeover itself (D-011).** The launcher ticked between the kill and the lease
write and started a **second** director (pid 8620, 01:05 local). It ran alongside this session for
the rest of the block. Nothing was lost — every change is committed and the tree is clean — but the
sequence "kill, then write the lease" has a race window of up to one heartbeat. The correct order is
**write the lease first, then stop the other session**; `scripts/ty_director.py` should also refuse to
start when another session already holds the lease. The lease is released at the end of this block so
the surviving director continues at rank 1.

**Block 1 — D-008 measured.** `reports/ty/block1_measure.md`.
12 prompt-only briefs re-rendered with all 12 render seeds pinned to the previous proof.
**n 12 · pass 12 · mean 98.3.** One mechanical failure: PO-012 `subject_fill` 24.8 % against 25.0.
Zero `alpha_matte` failures — the D-008 symptom is gone.
**And 0 of 12 is a picture a seller would list.** The label is a flat panel pasted over the product
in all twelve; 7 have the panel beyond the silhouette; 6 carry stray cutout geometry. Both sentences
are true. No bar was changed. `fix-label-conform` is rank 1.

**Block 2 — reference coverage.** `reports/ty/reference_coverage.md`.
**56 of 56 briefs** now have a reviewed, licence-logged reference: 17 brand assets (hash roster),
39 public licensed (Openverse; licence + URL on every row), 185 synthetic images tagged and
**excluded** from every pass-rate claim. 14 of 29 public candidates were rejected on visual review
(`reports/ty/reference_public_contact.png`, `ty/reference_review.json`). Held-out split 17 briefs /
39 tuning, disjoint image split. **Depth is thin — 1 to 3 reviewed images per category** — and is
rank 5 (`reference-depth`). Neck Nirvana stays unscorable.

## Position, 2026-11-11 (cycle 2)

Unit report: `reports/ty/unit_20261111_security_and_fixes.md`. Nine units merged, three defects filed.

| # | job | status |
|---|---|---|
| 1 | `sec-classify-history` — 88 URLs / 535 assignments / 674 emails / 319 phones, counts only | merged |
| 2 | `sec-wordcoffee-repos` — nine other public repos scanned, Pages listed | merged |
| 3 | `sec-rewrite-plan-extended` — commit map, quiet window, re-point, remap, recreate-private evaluation | merged |
| 4 | `sec-keys-rotated-watcher` — 5-minute model-free poll, then retire + gitleaks + promotion test | merged, running |
| 5 | `fix-stage-refused` — typed `StageRefused`; `ValueError`/`RuntimeError` now abort | merged, 17 tests |
| 6 | `fix-ppc-primary-action` — AdPilot's toast replaced by the real upload→bulk flow | merged, e2e 2/2 |
| 7 | `fix-rescan-main-ef9cad1d` — fixed config, no size cap, 5 findings | merged |
| 8 | `score-prompt-only-rescore` — 90.0 explained; per-mode n/pass/mean | merged |
| 9 | `fix-launcher-director-agent` — the missing lane existed; that is why nothing ran | merged |

**Headline numbers, stated per mode and never blended:** prompt-only n 12 / pass 9 / mean 86.4;
stored-reference 12 / 11 / 91.8; uploaded-reference 21 / 16 / 90.0. Seller reference coverage is
still **12 of 56 briefs** — the rank-1 blocker is unchanged and is job 1 of the next cycle.

**Next cycle, in rank order:** `sel-coverage-44` → `fix-alpha-matte-route` (D-008) →
`ppc-upload-live` → `ux-0610-live-verify` (parked on a locked desktop, verified as locked) →
`fix-launcher-heartbeat-red` (D-010) → `fix-dev-start-pids` (D-009) → `sel-04-packaging`.

## Position, 2026-11-09

| # | job | status |
|---|---|---|
| 1 | `sel-01c-cutout-provenance` | **merged** — the generator saves `<artefact>.cutout.png` + a sidecar; product region verified at 0.9958 / 0.9931 / 0.9835 |
| 2 | `ux-05-render-routes` | **merged** — 29/29 routes render; 60 Playwright tests pass |
| 3 | `reg-01-service-registry` | **merged** — 29 services in `ty/service_registry.json`, tool list and workspaces generated |
| 4 | `sel-02-design-studio` | queued |
| 5 | `sel-03-aplus` | queued |
| 6 | `sel-04-packaging` | queued |
| 7 | `ux-06-shell` | queued |
| 8–10 | `ux-07-tabs`, `ux-08-scene`, `ux-09-design-studio-canvas` | queued |

Both completed prerequisite units sit **ahead of ux-06 shell** in the ranking, which is stored in
`jobs.rank` rather than inferred from insertion order.

## Registry confidence (new)

Every entry now carries `evidence.confidence`: **high 4 · low 21 · none 4**. High means a live
page described with three or more controls; low means a committed screenshot; none means backend
only. A later walk that could not go live **cannot downgrade** a recorded live observation — the
blocked retry goes in `evidence.latest_attempt_blocked` instead.

## Waiting on an unlocked desktop — one command

```
python tools/ty_unlock_checks.py
```

It runs the live walk over every route, applies it to the registry, then runs V3 (ten-task parity
twice) and V9 (dogfood), and refuses by name while the desktop is locked — which it is right now
(`foreground is 'Windows Default Lock Screen'`). `--status` answers the question without running
anything.

## In flight

- **reg-01** (rank 5, ahead of the UX chain) — the **service registry as the single source of
  truth**: walk every advanced-view route with Ty's Vision plus the backend, record purpose,
  inputs, outputs, actions and Bojo tool per service, then generate the Bojo tool list and the
  default Northstar workspaces from it. Advanced view is **not** rebuilt; gaps are recorded in
  `ty/registry_gaps.json` only where a service has no controls.

## Composites: verified at last

The product-region check now runs on the real artefacts and passes:

| brief | score | region (masked SSIM) | passed |
|---|---|---|---|
| MG-C01 white main (flat 255 canvas, 2000 px) | **100** | 0.9958 | yes |
| MG-C02 greenhouse | **81** | 0.9931 | yes |
| MG-C03 forest mockup | **100** | 0.9835 | yes |

**3 passed, mean 93.7, 3 verified.** Two unit bugs had to be fixed to get there: `place_product`
records `[left, top, right, bottom]` and the check took `[x, y, w, h]`, and the audit was
re-implementing a comparison the repo already had — `product_composite.identity_check` was right
all along at 0.9958.

Seller dimension is still 22.1 from the **40-output stored pass**; the three composites are below
the five-output floor, so they inform the proof but not the score yet.

## The reference check changed on 2026-11-08

`tools/seller_tester/reference_check.py` decides by **printed text (OCR, fuzzy token match)**
then **meaning (local embeddings, cosine)**, and reports colour agreement as a **diagnostic
only** — the 0.60 proxy is no longer a gate. `cannot_verify` is still a failure. 44 tests.

## sel-01 landed, and here is exactly how far

56 briefs across the three modes (32 prompt-only, 12 stored-reference, 12 uploaded-reference),
a per-mode summary, and a reference check. A real pass scored **40 outputs: prompt-only 16
(mean 26.4), stored 12 (22.6), uploaded 12 (16.0); 0 passed in any mode.** Seller mean across
the service moved **16.7 → 22.1**, design-studio 75.2 → 75.9.

Three limits the builder stated and I am not going to paper over:

1. **No generator produces *from* an input.** The stored lane replays existing artefacts, so no
   mode is really "covered" — that is what `sel-01b` exists for.
2. **`uploaded_reference` never saw a real upload** — all twelve are `cannot_verify` by
   construction.
3. **The reference proxy has a measured overlap**: a genuine pouch crop fails at 0.603 while
   three dark-green UI screenshots pass at 0.637, so it fails conservatively and cannot be the
   only gate. The local vision judge stays off by default until it is measured.

## The finding that matters most

`python -m tools.vision.ux_audit --run` → **renders 3 of 29**. Only `account`, `beta` and
`design-studio` render their own page. `listings`, `socialpulse`, `competitor-monitor`,
`product-finder`, `listingforge` and the rest open the generic Bojo shell. U12 of the UX work
order passes only if "every service is reachable by click and nothing renders blank"; today it
is not. Evidence: `ty/ux_audit.json` + `reports/ty/ux_audit_shots/`.

## Scoring, 2026-11-09

Seven dimensions, bar 85 each: works 0.23, correct 0.25, complete 0.12, usable 0.07,
measured 0.10, seller 0.13, **contract 0.10** (new, paid for from `works` and `usable`).

**2 services at bar: `hub` 100, `prospector` 100.** Twelve at 86.2, held back by `complete`
because their declared Bojo tool has no handler.

Integrity fix landed with the contract work: `complete` used to mean "this tool's name appears
somewhere in the backend source", which a comment or a test satisfies — `keyword-tracker` and
`profitability` were scoring 100 with no handler at all. It now means a **callable handler
exists** in the chat tool table or the domain registry: the same gate that decides what Bojo is
offered.

Contract check: **20 of 29 pass, 4 persist, 3 gaps, 6 fail** (`reports/ty/contract_01.md`). A
service that only has paid-model actions is never called — that is standing gate (a), not a
skip.

**Today: 2 services at bar (`hub` 100, `prospector` 100), twelve at 86.2.** The ceiling was 77
this morning. `measured` is 28 of 29 after ux-05.

## Verified today

- **D17 complete.** Craft Anything 0.5.0 installed (checksum verified, `doctor` healthy) and the
  bake-off ran all six cells: craft-anything 0.859 / 0.353 / 1.000 vs REA 0.752 / 0.133 / 0.753.
  Craft Anything is the default on all three targets. `reports/ty/d17_bakeoff_final.md`.
- **BASELINE.json** updated from the measured 7,067 run (+450 passed vs 6,617; names +451/−1).
- **V3/V9 run.** V9: design-studio passes the seller task, the other three fail by rendering the
  shell. V3: UIA scores 5/10 because Chrome exposes no renderer accessibility tree; page content
  comes from pixels (`understand.describe_page`), which reads Design Studio correctly.
- **Disk 215 GB free**, worktrees removed.

## What is still open

- The render defect above (ranked 5th by the owner's ordering).
- V3's remaining half: either `--force-renderer-accessibility` or `--remote-debugging-port=9222`
  needs one Chrome relaunch by the owner.
- D17's hosted target: neither tool found the site's facts (0/7 each) — recorded, not hidden.

## Numbers to keep in mind

- 29 services, 0 at bar, best 77. Weakest dimension: 17 `complete`, 10 `seller`, 2 `measured`.
- Router: Bojo 15/18. Vision: qwen2.5vl:7b, page reading works, app reading works, grounding 61.7 %.
- Full suite: 7,067 passed, 0 failed, 117 skipped, 125 subtests, 18:49.
- The dev stack is running on 8101/8000 for the audit; stop it with the recorded pids when idle.

| unit | state | tag | note |
|---|---|---|---|
| D0–D7 | done | `ty-dir-D*` | baseline, probe, launcher, queue, scorecards, gaps, privacy, structure |
| D8 control/browser | done | `ty-dir-D8` | risk classes, verify-after-act (V4), injection (V6), Profile 6 lease, CDP layer; six-point parity 6/6 twice |
| D9 seller-tester | done | `ty-dir-D9` | 32 briefs, 28 tests, 30 artefacts scored, 29 gaps |
| D10 visual regression | done | `ty-dir-D10` | 31 views, frozen scenes, 6/6 fixtures, 41 tests |
| D11 intel plane | done | `ty-dir-D11` | 5 connectors, 58 findings, 58/58 URLs verified |
| D12 parallel bundles | done | `ty-dir-D12` | 6 merged; competitor-monitor 15→85, three services 15→75, 13 × +10 |
| D13 live mode | done | `ty-dir-D13` | narration + Q&A, blocked windows yield no pixels |
| D14 computer mode | done | `ty-dir-D14` | scope + grants; outside-scope write refused |
| D15 verification | done | `ty-dir-D15` | 17 agree, 2 FAILED (D17, V9), 1 BLOCKED (V3) |
| D16 model scout | continuous | `ty-dir-D16` | router eval fixed; Bojo 15/18; qwen3.5:4b +1 (no swap) |
| D17 bake-off | partial | `ty-dir-D17` | REA on the OSS target only; other two no result |
| Chrome via UIA | done | see batch report | CDP unavailable; Profile 6 driven through UIA + pixels |
| Seller dimension | done | — | `seller` 0.13 with a 5-output minimum; a passing test is worth 60, not 100 |

## Scoring changed on 2026-11-08 — read this before trusting a score

Six dimensions: works 0.28, correct 0.25, complete 0.12, usable 0.12, measured 0.10,
seller 0.13. **No service is at the bar, and the ceiling on artefacts alone is 77.** That is
the honest reading: `listings` and `socialpulse` dropped 100 → 77 the moment seller scores
entered the model, because no seller output has been scored for them.

## Blocked, and what unblocks it

1. **V3 parity and V9 dogfood: the desktop is locked** (`foreground = LockApp.exe`). The UIA
   route is built and refuses by name; the dogfood harness is built and refuses by name.
   Unlock the session and run:
   `python -m tools.vision.dogfood --services competitor-monitor,listings,socialpulse`
   then `python -m tools.vision.parity --twice --base http://127.0.0.1:8101/ui/`.
   No password is needed by Ty and none will be used.
2. **D17** needs Craft Anything installed and `northstar-os-ui/dist` built to complete the
   three-target bake-off.

## Queue now

Four bundles were queued by the re-plan (`raise complete` for goldengoose, offerchisel,
prospector, hub) and their Bojo tools are declared. Two builders are implementing them; after
that, re-score and re-plan again. Empty queue means re-plan, never idle.

## Numbers to keep in mind

- 29 services, **0 at bar**, best 77. Weakest dimension across the set: 17 `complete`,
  10 `seller`, 2 `measured`.
- **Full suite on `7fd881cc`/`d2c29a55`: 7,067 passed, 0 failed, 117 skipped, 125 subtests,
  18:49.** Baseline was 6,617 passed / 117 skipped / 125 subtests. Names: +451, −1 (the −1
  has no file and no git history).
- Router: Bojo 15/18. Vision: qwen2.5vl:7b on a clean server, grounding 61.7 % on 40 screens.
- Disk 8.5 GB free; floor 5 GB. ComfyUI is not resident. The 27B needs a lease.

## Rules that are easy to get wrong

- `state/` is gitignored: anything a fresh checkout needs must live under `ty/`.
- A per-dimension bar means an 85 average is not a pass.
- The launcher's pid file is authoritative; the logon task is `NorthstarTyDirector`.
- A bake-off result without an artefact on disk is "did not run". D17 proved that the hard way.
- Never leave a debug script behind; this session's temporary tools were removed.

- 2026-11-09T20:51:18+00:00 launcher: director session ended (session 16592 gone; launcher restarting).

- 2026-11-09T20:56:19+00:00 launcher: director session ended (session 8564 gone; launcher restarting).

- 2026-11-09T21:01:22+00:00 launcher: director session ended (session 23616 gone; launcher restarting).

- 2026-11-09T21:06:25+00:00 launcher: director session ended (session 1936 gone; launcher restarting).

- 2026-11-09T21:11:27+00:00 launcher: director session ended (session 548 gone; launcher restarting).

- 2026-11-09T21:16:30+00:00 launcher: director session ended (session 22168 gone; launcher restarting).

- 2026-11-09T21:21:31+00:00 launcher: director session ended (session 19380 gone; launcher restarting).

- 2026-11-09T21:26:35+00:00 launcher: director session ended (session 22680 gone; launcher restarting).

- 2026-11-09T21:31:36+00:00 launcher: director session ended (session 12080 gone; launcher restarting).

- 2026-11-09T21:36:37+00:00 launcher: director session ended (session 21196 gone; launcher restarting).

- 2026-11-09T21:41:39+00:00 launcher: director session ended (session 18412 gone; launcher restarting).

- 2026-11-09T21:46:41+00:00 launcher: director session ended (session 21780 gone; launcher restarting).

- 2026-11-09T21:51:43+00:00 launcher: director session ended (session 7760 gone; launcher restarting).

- 2026-11-09T21:56:46+00:00 launcher: director session ended (session 24328 gone; launcher restarting).

- 2026-11-09T22:01:48+00:00 launcher: director session ended (session 24288 gone; launcher restarting).

- 2026-11-09T22:06:50+00:00 launcher: director session ended (session 22820 gone; launcher restarting).

- 2026-11-09T22:11:53+00:00 launcher: director session ended (session 22448 gone; launcher restarting).

- 2026-11-09T22:16:56+00:00 launcher: director session ended (session 20600 gone; launcher restarting).

- 2026-11-09T22:21:58+00:00 launcher: director session ended (session 17500 gone; launcher restarting).

- 2026-11-09T22:27:00+00:00 launcher: director session ended (session 7400 gone; launcher restarting).

- 2026-11-09T22:32:01+00:00 launcher: director session ended (session 20736 gone; launcher restarting).

- 2026-11-09T22:37:03+00:00 launcher: director session ended (session 17584 gone; launcher restarting).

- 2026-11-09T22:42:04+00:00 launcher: director session ended (session 24288 gone; launcher restarting).

- 2026-11-09T22:47:06+00:00 launcher: director session ended (session 23292 gone; launcher restarting).

- 2026-11-09T22:52:07+00:00 launcher: director session ended (session 21264 gone; launcher restarting).

- 2026-11-09T22:57:09+00:00 launcher: director session ended (session 9400 gone; launcher restarting).

- 2026-11-09T23:02:10+00:00 launcher: director session ended (session 16296 gone; launcher restarting).

- 2026-11-09T23:07:12+00:00 launcher: director session ended (session 6344 gone; launcher restarting).

- 2026-11-09T23:12:13+00:00 launcher: director session ended (session 18132 gone; launcher restarting).

- 2026-11-09T23:17:14+00:00 launcher: director session ended (session 12760 gone; launcher restarting).

- 2026-11-09T23:22:16+00:00 launcher: director session ended (session 4788 gone; launcher restarting).

- 2026-11-09T23:27:17+00:00 launcher: director session ended (session 3408 gone; launcher restarting).

- 2026-11-09T23:32:19+00:00 launcher: director session ended (session 19876 gone; launcher restarting).

- 2026-11-09T23:37:23+00:00 launcher: director session ended (session 4952 gone; launcher restarting).

- 2026-11-09T23:42:25+00:00 launcher: director session ended (session 22740 gone; launcher restarting).

- 2026-11-09T23:47:27+00:00 launcher: director session ended (session 3288 gone; launcher restarting).

- 2026-11-09T23:52:29+00:00 launcher: director session ended (session 13500 gone; launcher restarting).

- 2026-11-09T23:57:30+00:00 launcher: director session ended (session 22036 gone; launcher restarting).

- 2026-11-10T00:02:36+00:00 launcher: director session ended (session 17620 gone; launcher restarting).

- 2026-11-10T00:07:37+00:00 launcher: director session ended (session 13080 gone; launcher restarting).

- 2026-11-10T00:12:38+00:00 launcher: director session ended (session 15864 gone; launcher restarting).

- 2026-11-10T00:17:40+00:00 launcher: director session ended (session 24012 gone; launcher restarting).

- 2026-11-10T00:22:41+00:00 launcher: director session ended (session 21468 gone; launcher restarting).

- 2026-11-10T00:27:42+00:00 launcher: director session ended (session 3996 gone; launcher restarting).

- 2026-11-10T00:32:44+00:00 launcher: director session ended (session 7456 gone; launcher restarting).

- 2026-11-10T00:37:46+00:00 launcher: director session ended (session 4260 gone; launcher restarting).

- 2026-11-10T00:42:47+00:00 launcher: director session ended (session 16324 gone; launcher restarting).

- 2026-11-10T00:47:48+00:00 launcher: director session ended (session 7808 gone; launcher restarting).

- 2026-11-10T00:52:50+00:00 launcher: director session ended (session 9176 gone; launcher restarting).

- 2026-11-10T00:57:51+00:00 launcher: director session ended (session 16540 gone; launcher restarting).

- 2026-11-10T01:02:53+00:00 launcher: director session ended (session 21004 gone; launcher restarting).

- 2026-11-10T01:07:54+00:00 launcher: director session ended (session 22356 gone; launcher restarting).

- 2026-11-10T01:12:55+00:00 launcher: director session ended (session 15108 gone; launcher restarting).

- 2026-11-10T01:17:57+00:00 launcher: director session ended (session 9360 gone; launcher restarting).

- 2026-11-10T01:22:58+00:00 launcher: director session ended (session 17264 gone; launcher restarting).

- 2026-11-10T01:27:59+00:00 launcher: director session ended (session 18396 gone; launcher restarting).

- 2026-11-10T01:33:01+00:00 launcher: director session ended (session 20040 gone; launcher restarting).

- 2026-11-10T01:38:02+00:00 launcher: director session ended (session 9008 gone; launcher restarting).

- 2026-11-10T01:43:03+00:00 launcher: director session ended (session 20016 gone; launcher restarting).

- 2026-11-10T01:48:05+00:00 launcher: director session ended (session 12040 gone; launcher restarting).

- 2026-11-10T01:53:06+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T01:58:07+00:00 launcher: director session ended (session 19364 gone; launcher restarting).

- 2026-11-10T02:03:09+00:00 launcher: director session ended (session 10552 gone; launcher restarting).

- 2026-11-10T02:08:11+00:00 launcher: director session ended (session 14664 gone; launcher restarting).

- 2026-11-10T02:13:13+00:00 launcher: director session ended (session 22500 gone; launcher restarting).

- 2026-11-10T02:18:15+00:00 launcher: director session ended (session 23632 gone; launcher restarting).

- 2026-11-10T02:23:16+00:00 launcher: director session ended (session 18132 gone; launcher restarting).

- 2026-11-10T02:28:18+00:00 launcher: director session ended (session 6104 gone; launcher restarting).

- 2026-11-10T02:34:09+00:00 launcher: director session ended (session 21552 gone; launcher restarting).

- 2026-11-10T02:39:13+00:00 launcher: director session ended (session 3240 gone; launcher restarting).

- 2026-11-10T02:44:33+00:00 launcher: director session ended (session 23564 gone; launcher restarting).

- 2026-11-10T02:50:06+00:00 launcher: director session ended (session 9540 gone; launcher restarting).

- 2026-11-10T02:55:09+00:00 launcher: director session ended (session 21920 gone; launcher restarting).

- 2026-11-10T03:00:16+00:00 launcher: director session ended (session 23636 gone; launcher restarting).

- 2026-11-10T03:05:20+00:00 launcher: director session ended (session 12768 gone; launcher restarting).

- 2026-11-10T03:10:28+00:00 launcher: director session ended (session 2924 gone; launcher restarting).

- 2026-11-10T03:15:29+00:00 launcher: director session ended (session 8484 gone; launcher restarting).

- 2026-11-10T03:20:31+00:00 launcher: director session ended (session 3380 gone; launcher restarting).

- 2026-11-10T03:25:35+00:00 launcher: director session ended (session 6996 gone; launcher restarting).

- 2026-11-10T03:30:38+00:00 launcher: director session ended (session 9912 gone; launcher restarting).

- 2026-11-10T03:35:39+00:00 launcher: director session ended (session 8144 gone; launcher restarting).

- 2026-11-10T03:40:41+00:00 launcher: director session ended (session 7760 gone; launcher restarting).

- 2026-11-10T03:45:43+00:00 launcher: director session ended (session 10688 gone; launcher restarting).

- 2026-11-10T03:50:45+00:00 launcher: director session ended (session 3220 gone; launcher restarting).

- 2026-11-10T03:55:49+00:00 launcher: director session ended (session 22564 gone; launcher restarting).

- 2026-11-10T04:00:54+00:00 launcher: director session ended (session 21784 gone; launcher restarting).

- 2026-11-10T04:06:03+00:00 launcher: director session ended (session 3768 gone; launcher restarting).

- 2026-11-10T04:11:08+00:00 launcher: director session ended (session 25496 gone; launcher restarting).

- 2026-11-10T04:16:11+00:00 launcher: director session ended (session 22408 gone; launcher restarting).

- 2026-11-10T04:21:13+00:00 launcher: director session ended (session 21072 gone; launcher restarting).

- 2026-11-10T04:26:15+00:00 launcher: director session ended (session 8868 gone; launcher restarting).

- 2026-11-10T04:31:17+00:00 launcher: director session ended (session 4604 gone; launcher restarting).

- 2026-11-10T04:36:18+00:00 launcher: director session ended (session 18320 gone; launcher restarting).

- 2026-11-10T04:41:21+00:00 launcher: director session ended (session 9024 gone; launcher restarting).

- 2026-11-10T04:46:23+00:00 launcher: director session ended (session 20896 gone; launcher restarting).

- 2026-11-10T04:51:25+00:00 launcher: director session ended (session 25260 gone; launcher restarting).

- 2026-11-10T04:56:26+00:00 launcher: director session ended (session 13804 gone; launcher restarting).

- 2026-11-10T05:01:31+00:00 launcher: director session ended (session 3548 gone; launcher restarting).

- 2026-11-10T05:06:33+00:00 launcher: director session ended (session 24692 gone; launcher restarting).

- 2026-11-10T05:11:35+00:00 launcher: director session ended (session 25452 gone; launcher restarting).

- 2026-11-10T05:16:36+00:00 launcher: director session ended (session 22600 gone; launcher restarting).

- 2026-11-10T05:21:38+00:00 launcher: director session ended (session 1656 gone; launcher restarting).

- 2026-11-10T05:26:39+00:00 launcher: director session ended (session 18804 gone; launcher restarting).

- 2026-11-10T05:31:40+00:00 launcher: director session ended (session 21592 gone; launcher restarting).

- 2026-11-10T05:36:42+00:00 launcher: director session ended (session 24068 gone; launcher restarting).

- 2026-11-10T05:41:44+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T05:46:45+00:00 launcher: director session ended (session 14016 gone; launcher restarting).

- 2026-11-10T05:51:46+00:00 launcher: director session ended (session 24612 gone; launcher restarting).

- 2026-11-10T05:56:48+00:00 launcher: director session ended (session 20060 gone; launcher restarting).

- 2026-11-10T06:01:49+00:00 launcher: director session ended (session 23700 gone; launcher restarting).

- 2026-11-10T06:06:51+00:00 launcher: director session ended (session 22652 gone; launcher restarting).

- 2026-11-10T06:11:53+00:00 launcher: director session ended (session 17844 gone; launcher restarting).

- 2026-11-10T06:16:55+00:00 launcher: director session ended (session 21288 gone; launcher restarting).

- 2026-11-10T06:22:00+00:00 launcher: director session ended (session 17936 gone; launcher restarting).

- 2026-11-10T06:27:01+00:00 launcher: director session ended (session 19360 gone; launcher restarting).

- 2026-11-10T06:32:02+00:00 launcher: director session ended (session 16408 gone; launcher restarting).

- 2026-11-10T06:37:04+00:00 launcher: director session ended (session 19428 gone; launcher restarting).

- 2026-11-10T06:42:06+00:00 launcher: director session ended (session 23284 gone; launcher restarting).

- 2026-11-10T06:47:08+00:00 launcher: director session ended (session 11716 gone; launcher restarting).

- 2026-11-10T06:52:10+00:00 launcher: director session ended (session 24344 gone; launcher restarting).

- 2026-11-10T06:57:12+00:00 launcher: director session ended (session 12656 gone; launcher restarting).

- 2026-11-10T07:02:15+00:00 launcher: director session ended (session 16596 gone; launcher restarting).

- 2026-11-10T07:07:28+00:00 launcher: director session ended (session 22712 gone; launcher restarting).

- 2026-11-10T07:12:31+00:00 launcher: director session ended (session 2520 gone; launcher restarting).

- 2026-11-10T07:17:32+00:00 launcher: director session ended (session 24944 gone; launcher restarting).

- 2026-11-10T07:22:34+00:00 launcher: director session ended (session 12856 gone; launcher restarting).

- 2026-11-10T07:27:36+00:00 launcher: director session ended (session 3608 gone; launcher restarting).

- 2026-11-10T07:32:38+00:00 launcher: director session ended (session 9008 gone; launcher restarting).

- 2026-11-10T07:37:48+00:00 launcher: director session ended (session 15924 gone; launcher restarting).

- 2026-11-10T07:42:51+00:00 launcher: director session ended (session 7916 gone; launcher restarting).

- 2026-11-10T07:47:53+00:00 launcher: director session ended (session 20836 gone; launcher restarting).

- 2026-11-10T07:52:54+00:00 launcher: director session ended (session 4804 gone; launcher restarting).

- 2026-11-10T07:57:56+00:00 launcher: director session ended (session 21752 gone; launcher restarting).

- 2026-11-10T08:02:57+00:00 launcher: director session ended (session 25408 gone; launcher restarting).

- 2026-11-10T08:07:59+00:00 launcher: director session ended (session 15072 gone; launcher restarting).

- 2026-11-10T08:13:00+00:00 launcher: director session ended (session 20064 gone; launcher restarting).

- 2026-11-10T08:18:02+00:00 launcher: director session ended (session 13240 gone; launcher restarting).

- 2026-11-10T08:23:03+00:00 launcher: director session ended (session 25256 gone; launcher restarting).

- 2026-11-10T08:28:04+00:00 launcher: director session ended (session 12812 gone; launcher restarting).

- 2026-11-10T08:33:05+00:00 launcher: director session ended (session 7152 gone; launcher restarting).

- 2026-11-10T08:38:07+00:00 launcher: director session ended (session 21344 gone; launcher restarting).

- 2026-11-10T08:43:08+00:00 launcher: director session ended (session 7576 gone; launcher restarting).

- 2026-11-10T08:48:10+00:00 launcher: director session ended (session 6828 gone; launcher restarting).

- 2026-11-10T08:53:12+00:00 launcher: director session ended (session 7400 gone; launcher restarting).

- 2026-11-10T08:58:13+00:00 launcher: director session ended (session 25152 gone; launcher restarting).

- 2026-11-10T09:03:15+00:00 launcher: director session ended (session 22652 gone; launcher restarting).

- 2026-11-10T09:08:16+00:00 launcher: director session ended (session 4120 gone; launcher restarting).

- 2026-11-10T09:13:18+00:00 launcher: director session ended (session 9324 gone; launcher restarting).

- 2026-11-10T09:18:19+00:00 launcher: director session ended (session 20252 gone; launcher restarting).

- 2026-11-10T09:23:20+00:00 launcher: director session ended (session 20500 gone; launcher restarting).

- 2026-11-10T09:28:22+00:00 launcher: director session ended (session 16832 gone; launcher restarting).

- 2026-11-10T09:33:23+00:00 launcher: director session ended (session 12048 gone; launcher restarting).

- 2026-11-10T09:38:25+00:00 launcher: director session ended (session 13268 gone; launcher restarting).

- 2026-11-10T09:43:26+00:00 launcher: director session ended (session 2728 gone; launcher restarting).

- 2026-11-10T09:48:28+00:00 launcher: director session ended (session 21204 gone; launcher restarting).

- 2026-11-10T09:53:29+00:00 launcher: director session ended (session 3824 gone; launcher restarting).

- 2026-11-10T09:58:31+00:00 launcher: director session ended (session 21076 gone; launcher restarting).

- 2026-11-10T10:03:33+00:00 launcher: director session ended (session 13772 gone; launcher restarting).

- 2026-11-10T10:08:34+00:00 launcher: director session ended (session 19728 gone; launcher restarting).

- 2026-11-10T10:13:35+00:00 launcher: director session ended (session 3500 gone; launcher restarting).

- 2026-11-10T10:18:37+00:00 launcher: director session ended (session 2416 gone; launcher restarting).

- 2026-11-10T10:23:39+00:00 launcher: director session ended (session 1496 gone; launcher restarting).

- 2026-11-10T10:28:40+00:00 launcher: director session ended (session 19304 gone; launcher restarting).

- 2026-11-10T10:33:41+00:00 launcher: director session ended (session 23132 gone; launcher restarting).

- 2026-11-10T10:38:43+00:00 launcher: director session ended (session 3708 gone; launcher restarting).

- 2026-11-10T10:43:44+00:00 launcher: director session ended (session 24432 gone; launcher restarting).

- 2026-11-10T10:48:46+00:00 launcher: director session ended (session 21476 gone; launcher restarting).

- 2026-11-10T10:53:47+00:00 launcher: director session ended (session 6236 gone; launcher restarting).

- 2026-11-10T10:58:48+00:00 launcher: director session ended (session 24356 gone; launcher restarting).

- 2026-11-10T11:03:50+00:00 launcher: director session ended (session 4408 gone; launcher restarting).

- 2026-11-10T11:08:51+00:00 launcher: director session ended (session 18688 gone; launcher restarting).

- 2026-11-10T11:13:53+00:00 launcher: director session ended (session 23684 gone; launcher restarting).

- 2026-11-10T11:18:56+00:00 launcher: director session ended (session 13548 gone; launcher restarting).

- 2026-11-10T11:23:57+00:00 launcher: director session ended (session 21320 gone; launcher restarting).

- 2026-11-10T11:28:58+00:00 launcher: director session ended (session 1492 gone; launcher restarting).

- 2026-11-10T11:34:00+00:00 launcher: director session ended (session 4196 gone; launcher restarting).

- 2026-11-10T11:39:02+00:00 launcher: director session ended (session 8504 gone; launcher restarting).

- 2026-11-10T11:44:03+00:00 launcher: director session ended (session 23132 gone; launcher restarting).

- 2026-11-10T11:49:04+00:00 launcher: director session ended (session 23128 gone; launcher restarting).

- 2026-11-10T11:54:07+00:00 launcher: director session ended (session 22212 gone; launcher restarting).

- 2026-11-10T19:35:22+00:00 launcher: director session ended (session 20356 gone; launcher restarting).

- 2026-11-10T19:40:24+00:00 launcher: director session ended (session 12192 gone; launcher restarting).

- 2026-11-10T19:45:27+00:00 launcher: director session ended (session 17768 gone; launcher restarting).

- 2026-11-10T19:50:29+00:00 launcher: director session ended (session 3708 gone; launcher restarting).

- 2026-11-10T19:55:31+00:00 launcher: director session ended (session 228 gone; launcher restarting).

- 2026-11-10T20:00:34+00:00 launcher: director session ended (session 25964 gone; launcher restarting).

- 2026-11-10T20:05:37+00:00 launcher: director session ended (session 18440 gone; launcher restarting).

- 2026-11-10T20:10:39+00:00 launcher: director session ended (session 24140 gone; launcher restarting).

- 2026-11-10T20:15:40+00:00 launcher: director session ended (session 23228 gone; launcher restarting).

- 2026-11-10T20:20:42+00:00 launcher: director session ended (session 8176 gone; launcher restarting).

- 2026-11-10T20:25:45+00:00 launcher: director session ended (session 24988 gone; launcher restarting).

- 2026-11-10T20:30:47+00:00 launcher: director session ended (session 20428 gone; launcher restarting).

- 2026-11-10T20:35:49+00:00 launcher: director session ended (session 5272 gone; launcher restarting).

- 2026-11-10T20:40:51+00:00 launcher: director session ended (session 11568 gone; launcher restarting).

- 2026-11-10T20:45:54+00:00 launcher: director session ended (session 26172 gone; launcher restarting).

- 2026-11-10T20:50:56+00:00 launcher: director session ended (session 5576 gone; launcher restarting).

- 2026-11-10T20:55:59+00:00 launcher: director session ended (session 21644 gone; launcher restarting).

- 2026-11-10T21:01:01+00:00 launcher: director session ended (session 14444 gone; launcher restarting).

- 2026-11-10T21:06:04+00:00 launcher: director session ended (session 17852 gone; launcher restarting).

- 2026-11-10T21:11:06+00:00 launcher: director session ended (session 25292 gone; launcher restarting).

- 2026-11-10T21:16:08+00:00 launcher: director session ended (session 16004 gone; launcher restarting).

- 2026-11-10T21:21:10+00:00 launcher: director session ended (session 21852 gone; launcher restarting).

- 2026-11-10T21:26:11+00:00 launcher: director session ended (session 20692 gone; launcher restarting).

- 2026-11-10T21:31:14+00:00 launcher: director session ended (session 11232 gone; launcher restarting).

- 2026-11-10T21:36:16+00:00 launcher: director session ended (session 21920 gone; launcher restarting).

- 2026-11-10T21:41:19+00:00 launcher: director session ended (session 2104 gone; launcher restarting).

- 2026-11-10T21:46:22+00:00 launcher: director session ended (session 3132 gone; launcher restarting).

- 2026-11-10T21:51:24+00:00 launcher: director session ended (session 22776 gone; launcher restarting).

- 2026-11-10T21:56:26+00:00 launcher: director session ended (session 15080 gone; launcher restarting).

- 2026-11-10T22:01:28+00:00 launcher: director session ended (session 15588 gone; launcher restarting).

- 2026-11-10T22:06:31+00:00 launcher: director session ended (session 9160 gone; launcher restarting).

- 2026-11-10T22:11:34+00:00 launcher: director session ended (session 404 gone; launcher restarting).

- 2026-11-10T22:16:36+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T22:21:38+00:00 launcher: director session ended (session 5772 gone; launcher restarting).

- 2026-11-10T22:26:39+00:00 launcher: director session ended (session 21984 gone; launcher restarting).

- 2026-11-10T22:31:41+00:00 launcher: director session ended (session 2872 gone; launcher restarting).

- 2026-11-10T22:36:47+00:00 launcher: director session ended (session 14080 gone; launcher restarting).

- 2026-11-10T22:41:51+00:00 launcher: director session ended (session 3044 gone; launcher restarting).

- 2026-11-10T22:46:52+00:00 launcher: director session ended (session 24840 gone; launcher restarting).

- 2026-11-10T22:51:55+00:00 launcher: director session ended (session 14228 gone; launcher restarting).

- 2026-11-10T22:56:56+00:00 launcher: director session ended (session 6504 gone; launcher restarting).

- 2026-11-10T23:01:59+00:00 launcher: director session ended (session 11156 gone; launcher restarting).

- 2026-11-10T23:07:01+00:00 launcher: director session ended (session 21804 gone; launcher restarting).

- 2026-11-10T23:12:03+00:00 launcher: director session ended (session 21352 gone; launcher restarting).

- 2026-11-10T23:17:06+00:00 launcher: director session ended (session 25792 gone; launcher restarting).

- 2026-11-10T23:22:09+00:00 launcher: director session ended (session 15080 gone; launcher restarting).

- 2026-11-10T23:27:12+00:00 launcher: director session ended (session 23100 gone; launcher restarting).

- 2026-11-10T23:32:14+00:00 launcher: director session ended (session 3168 gone; launcher restarting).

- 2026-11-10T23:37:17+00:00 launcher: director session ended (session 19888 gone; launcher restarting).

- 2026-11-10T23:42:19+00:00 launcher: director session ended (session 26400 gone; launcher restarting).

- 2026-11-10T23:47:20+00:00 launcher: director session ended (session 16912 gone; launcher restarting).

- 2026-11-10T23:52:22+00:00 launcher: director session ended (session 10040 gone; launcher restarting).

- 2026-11-10T23:57:26+00:00 launcher: director session ended (session 16224 gone; launcher restarting).

- 2026-11-11T00:02:27+00:00 launcher: director session ended (session 14876 gone; launcher restarting).

- 2026-11-11T00:07:29+00:00 launcher: director session ended (session 14224 gone; launcher restarting).

- 2026-11-11T00:12:31+00:00 launcher: director session ended (session 7876 gone; launcher restarting).

- 2026-11-11T00:17:33+00:00 launcher: director session ended (session 4504 gone; launcher restarting).

- 2026-11-11T00:22:35+00:00 launcher: director session ended (session 13788 gone; launcher restarting).

- 2026-11-11T00:27:38+00:00 launcher: director session ended (session 16696 gone; launcher restarting).

- 2026-11-11T00:32:40+00:00 launcher: director session ended (session 20632 gone; launcher restarting).

- 2026-11-11T00:37:42+00:00 launcher: director session ended (session 8864 gone; launcher restarting).

- 2026-11-11T00:42:44+00:00 launcher: director session ended (session 25480 gone; launcher restarting).

- 2026-11-11T00:47:46+00:00 launcher: director session ended (session 15316 gone; launcher restarting).

- 2026-11-11T03:43:57+00:00 launcher: director session ended (session 24680 gone; launcher restarting).

- 2026-11-11T05:14:38+00:00 launcher: director session ended (session 26360 gone; launcher restarting).

- 2026-11-11T07:05:17+00:00 launcher: director session ended (session 21024 gone; launcher restarting).

- 2026-11-11T09:40:08+00:00 launcher: director session ended (session 25952 ended after output; launcher restarting).

- 2026-11-11T09:45:10+00:00 launcher: director session ended (session 18732 gone; launcher restarting).
