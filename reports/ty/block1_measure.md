# Block 1 — D-008 measured: prompt-only, per check and per mode

Date: 2026-11-11. Owner: Tyrone. No bar and no weight was changed for this measurement; the pass
bar is each brief's own `pass_score` (70) and it is printed per row in
`reports/ty/block1_prompt_only_measured.md`.

## What was measured

Twelve prompt-only held-out briefs, re-rendered after the D-008 fix (`flat()` inverted, then the
contact-shadow margin), with **every render seed read back from the previous proof and reused** so
the only variable is the pipeline change: `seeds_reused 12, seeds_random 0`
(`state/seller/heldout_prompt_only_proof8.json`, `rerender` block).

Artefacts: `renders/heldout_prompt_only8/`. Scored with the current instrument by
`tools/block1_prompt_only_measure.py`, which re-scores from the bytes on disk:
`python tools/block1_prompt_only_measure.py --dir renders/heldout_prompt_only8 --write`.

## Per-mode table (never blended)

| mode | n | pass | mean | source | measured |
|---|---|---|---|---|---|
| prompt-only | 12 | **12** | **98.3** | `renders/heldout_prompt_only8` | 2026-11-11 (this block) |
| stored-reference | 12 | 11 | 91.8 | `renders/heldout_modes` | 2026-11-10, not re-rendered |
| uploaded-reference | 21 | 16 | 90.0 | `renders/seller_composite_heldout` | 2026-11-10, not re-rendered |

There is no blended headline number. The two rows that were not re-rendered are marked as such.

## Per-check table

`P` pass · `F` fail · `–` not applicable (recorded as skipped with a reason) · `·` not run for a
full generation (a composite-only check).

| brief | situation | score | passed | dimensions | aspect | background | subject_fill | alpha_matte | file_size | text_free |
|---|---|---|---|---|---|---|---|---|---|---|
| PO-001 | white_background_main | 100.0 | yes | P | P | P | P | P | P | P |
| PO-002 | lifestyle | 100.0 | yes | P | P | – | – | – | P | – |
| PO-003 | scale_reference | 100.0 | yes | P | P | P | P | P | P | P |
| PO-004 | bundle_multipack | 100.0 | yes | P | P | P | P | P | P | P |
| PO-005 | background_swap | 100.0 | yes | P | P | P | P | P | P | P |
| PO-006 | series_consistency | 100.0 | yes | P | P | P | P | P | P | P |
| PO-007 | infographic | 100.0 | yes | P | P | – | – | – | P | P |
| PO-008 | packaging_mockup | 100.0 | yes | P | P | – | – | – | P | – |
| PO-009 | white_background_main | 100.0 | yes | P | P | P | P | P | P | P |
| PO-010 | lifestyle | 100.0 | yes | P | P | – | – | – | P | – |
| PO-011 | scale_reference | 100.0 | yes | P | P | P | P | P | P | P |
| PO-012 | bundle_multipack | 80.0 | yes | P | P | P | **F** | P | P | P |

Failures by check:

| check | briefs failing | note |
|---|---|---|
| `dimensions` | 0 | |
| `aspect` | 0 | |
| `background` | 0 | |
| `subject_fill` | 1 | PO-012: fill 24.8 % against a 25.0 % floor — 0.2 points under |
| `alpha_matte` | 0 | the D-008 symptom is gone |
| `file_size` | 0 | |
| `text_free` | 0 | |
| `reference_subject` | 0 | not graded on this mode |

The six briefs that were pinned at exactly 90.0 by `alpha_matte` now sit at 100.0. The check is no
longer failing anywhere, which is what D-008 was.

## The result that matters: the scorer passes it, the eye does not

`reports/ty/block1_prompt_only_contact.png` is all twelve artefacts, numbered left to right, top to
bottom (PO-001…PO-012). **Director's visual review — not a measured judge, and labelled as such:**

| defect class | how many of 12 | examples |
|---|---|---|
| the label is a **flat rectangular panel pasted over** the product instead of being conformed to the pack face | **12** | every artefact; worst in PO-002, PO-004, PO-006, PO-012 |
| the panel extends **beyond the product silhouette**, so a white card floats on the scene | 7 | PO-002, PO-004, PO-005, PO-006, PO-010, PO-011, PO-012 |
| **stray geometry** from the cutout or the layout (a stick above the pouch, dashed rules, ghost rings, a duplicate pack) | 6 | PO-001 (vertical artifact), PO-003 (white ring), PO-004 (dashed rule), PO-005 (diagonal rule), PO-011 (ghosted tube), PO-012 (ghost pack) |
| product body reads as a **flat card**, not a photographed object | 8 | PO-001, PO-002, PO-004, PO-005, PO-006, PO-010, PO-011, PO-012 |

So the honest statement is: **prompt-only passes the mechanical bar 12 of 12 at mean 98.3, and 0 of 12
is a picture a seller would put on a listing.** Those two sentences are both true and the second one
is the one that decides launch readiness. The scorer measures dimensions, aspect, background value,
fill, matte, file size and margin ink; it does not measure whether the label belongs on the pack.

This is why `launch_readiness.md` treats `seller` and `correct` as the dimensions that matter, and why
a judge-based score must be labelled judge-based. Nothing here is a reason to change a bar: the
mechanical bar was met, and the pictures are still not sellable.

## Gap filed

`fix-label-conform` (rank 1): the label panel must be warped onto the measured pack face with the
panel's own quad, its edges clipped to the product mask, and the pack's shading re-applied over it;
the cutout must reject the stray geometry above and beside the subject. Acceptance is visual plus
mechanical: the contact sheet re-shot, and `subject_fill`/`background` still passing.

## Evidence files

- `reports/ty/block1_prompt_only_measured.md` — this table, generated from the artefacts
- `reports/ty/block1_prompt_only_measured.json` — the same, machine-readable
- `reports/ty/block1_prompt_only_contact.png` — the twelve artefacts in one sheet
- `state/seller/heldout_prompt_only_proof8.json` — the run that produced them, with seeds pinned
- `tools/block1_prompt_only_measure.py` — the measurement, re-runnable
