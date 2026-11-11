# Re-render prompt-only, and the defect the first re-render revealed

Queue job `rerender-prompt-only` (rank 1), run 2026-11-11. Rollback tag
`rollback/pre-rerender-prompt-only-20261111`. Diff: `b3beacf5`, plus this report's commit.

## Result, measured

| run | pipeline | scored | passed | mean |
|---|---|---|---|---|
| v4 (proof4) | flat() inverted, shadow unreserved | 12 | 9 | 86.4 |
| v5 (proof5) | flat() fixed only | 12 | 10 | 88.1 |
| **v6 (proof6)** | **+ shadow reserved inside the frame** | **12** | **10** | **93.9** |

Command: `python tools/rerender_prompt_only.py --previous state/seller/heldout_prompt_only_proof5.json
--out-dir renders/heldout_prompt_only6 --summary-out state/seller/heldout_prompt_only_proof6.json
--gaps state/seller/heldout_prompt_only_gaps6.json` → `EXIT=0`,
output in `reports/ty/_prompt_only_run6.txt`.

**Every render seed was reused** (`seeds_reused: 12, seeds_random: 0`), so the picture changed only
because the pipeline changed. That is what makes the before/after a measurement rather than two
different rolls of the dice.

| brief | situation | v4 | v6 | what changed |
|---|---|---|---|---|
| PO-001 | white_background_main | 90.0 | **100.0** | border std 7.19 → 0.0 |
| PO-003 | scale_reference | 90.0 | **100.0** | border std 7.68 → 0.0 |
| PO-004 | bundle_multipack | 90.0 | **100.0** | border std 7.17 → 0.0 |
| PO-005 | background_swap | 70.0 | **100.0** | flat() branch + shadow |
| PO-006 | series_consistency | 90.0 | **100.0** | border std 9.00 → 0.0 |
| PO-011 | scale_reference | 90.0 | **100.0** | border std 8.43 → 0.0 |
| PO-012 | bundle_multipack | 90.0 | **100.0** | border std 7.79 → 0.0 |
| PO-002 | lifestyle | 63.6 | 63.6 | **still fails** — see below |
| PO-010 | lifestyle | 63.6 | 63.6 | **still fails** — see below |

The six rows that used to sit at *exactly* 90.0 — a rubric constant, not a quality score — are gone.

## The defect the first re-render found, and why the D-008 note was wrong

proof5 re-rendered the twelve with `flat()` corrected and produced **byte-identical border
statistics for PO-001** (mean 252.13, std 7.19 before and after). PO-001's brief declares
`background.mode == "uniform"`, so `flat()` already returned True for it: the inverted branch could
not have been its cause. The recorded reason was wrong, so the proof carries a correction
(`state/seller/heldout_prompt_only_proof6.json` → `rerender.corrected`).

Measured cause, from the pixels: the outer ring is pure 255 for 19 of 20 rows, and the **bottom 20
rows** carry 23,638 dark pixels spanning x 374–1625 — exactly the product's shadow width
(`product_box` x 374–1625, bottom y 1820). `place_product` pasted the contact shadow half its
height below the product's base with nothing reserved for it, so at scale 0.62 / anchor 0.6 the blob
ran to y ≈ 2032 and the frame edge cut it. Mean luminance of that band: **243.5**. That is a real
defect in the picture (a hard straight edge under every such product) before it is a failed check.

**Fix:** `Northstar_backend/product_composite.py::place_product` now treats the shadow as part of
the subject. It reserves the footprint inside the frame margin, shrinking the *shadow* first (the
product's size is the brief's requirement) and the product only when the frame genuinely cannot hold
both, and reports `shadow_inside_frame` so the placement is auditable. Six tests in
`Northstar_backend/test_product_composite_framing.py`, all passing; the 101-test composite/seller
suites still pass.

## Still failing, stated rather than papered over

PO-002 and PO-010 are both `lifestyle` and both fail `subject_fill` at 63.6: **subject fill 94.3 %
against an 8–50 % window**. That is the opposite complaint — the product fills almost the whole
frame in a lifestyle shot. The framing stage places at a fixed 0.62 scale regardless of situation;
a lifestyle brief wants the product at roughly a third of the frame with the scene readable. Filed
as gap work, not fixed here.

## The vision judge, and two more instruments that measured the wrong thing

Mechanical checks alone said 12/12 at 100.0. That is the "rubric constant" smell in reverse, so the
local judge was turned on (`gemma3:4b` through Ollama on loopback, ~15 s per picture, pixels never
leave the machine). Two more instrument defects surfaced before the judge could be believed:

1. **The judge rubric named the taxonomy slot, not the product.** It read "a lifestyle picture for a
   `food_jar`", and PO-004/PO-010 ask for *three pale-pink Word Coffee gift boxes* — filed under
   `food_jar` because that is the catalogue's slot. The judge correctly answered "not a food jar"
   about a correct picture. The rubric now uses the brief's own words (`judge_constraint`, else
   `prompt`), falling back to `situation + category` only when the brief names nothing.
2. **`subject_fill` measured the corner colour on a scene background.** On a generated lifestyle
   scene every pixel differs from the corner, so PO-002 reported "fill 94.3 % vs 8–50 %" on a
   correct picture. A free background now uses the recorded **product box** as the measure
   (`instrument: product_box`, PO-002 39.8 %), and with no box the check is *skipped with a reason*,
   never passed. Flat backgrounds keep the corner-colour instrument. Five tests in
   `Northstar_backend/test_subject_fill_instrument.py`.

**Judged result (`state/seller/heldout_prompt_only_proof6_judged2.json`): 11 of 12 pass, mean 83.5.**

| brief | score | judge's finding |
|---|---|---|
| PO-008 | **68.8 fail** | the box reads "AOW", not "Word Coffee"; "For Mom" and the tagline are missing |
| PO-001 | 80.0 | pouch glossy not matte; label does not read MOGRA ORGANICS; no gold line art; no weight |
| PO-003 | 80.0 | label reads "MOGGARA"; no line art; no weight |
| PO-005 | 80.0 | glossy; label text not readable; weight missing |
| PO-007 | 73.7 | line art green not gold; weight missing |
| PO-009 | 80.0 | pouch black not forest green; text overlay |
| PO-011 | 80.0 | white pouch not matte forest green; label text missing |
| PO-012 | 80.0 | box shows "Mom / Nonna / I love you", not the Word Coffee branding |
| PO-004 | 80.0 | brand name not visible; "For Mom" too small; tagline missing |
| PO-002, PO-006, PO-010 | 100.0 | — |

**This is the honest gap, and it is a text-fidelity gap.** The briefs describe exact label copy
(brand, product, weight, line art) and let the diffusion model draw it; the model cannot spell. The
repo already has the right tool — `tools/seller_tester/label_warp.py` composes the label
deterministically and warps it onto the drawn body — but **no prompt-only brief sets
`label_mode: warp`** (0 of 12), so no label is composed. Queued as the next seller unit: draw an
unlettered body, compose the label from the brief, measure with the judge.


- **Held-out by mode now:** prompt-only 12 scored / 10 passed / **93.9**; stored-reference 12 / 11 /
  91.8; uploaded-reference 21 / 16 / 90.0 — `state/seller/heldout_proof.json`, 45 scored, 37 passed.
- The **seller dimension of the service scorecard** is computed by `tools/seller_scores.py` from
  its own proof and still reads design-studio 100.0 on 3 generated artefacts with a 40-output replay
  at 22.1. That number did **not** move from this unit and is not claimed to have.
- Reference coverage is still **12 of 56 briefs** — the rank-1 blocker is unchanged.
