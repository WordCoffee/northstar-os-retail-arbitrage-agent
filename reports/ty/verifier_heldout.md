# Held-out run — independent verification (re-run, 2026-11-09)

Verifier: separate session from the author. Repo root
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`. This file replaces the earlier
13 / 86.2 verification, which is now **superseded**: the reference pool changed (D-003) and both the
briefs file and the composite proof were regenerated.

## Verdict: AGREE

21 scored, **16 passed, mean 92.0** — reproduced exactly from the proof rows on disk, not from the
summary block. Lions Mane 10 / 8 / 95.0, Word Coffee 11 / 8 / 89.3. No per-brief pass/fail differs
from the claim. All 21 artefacts are real PNGs.

One brief's reference is still a quote card (HO-015) and the pool is 9 distinct photographs, not 10 —
both recorded below as findings; neither moves a score.

## What I ran, in order, and the real output

### 1. Status first — the pass is complete, so it was not re-run

```
> python tools/heldout_composite.py --status
{ "total": 21, "done": 21, "remaining": [], "passed": 16, "mean": 92.0 }
```

### 2. Everything recomputed from the result rows

```
> python $env:TEMP\opencode\recheck2.py
rows 21 scored 21 passed 16 cannot_verify 0
mean 92.0
lions-mane scored 10 passed 8 mean 95.0
word-coffee scored 11 passed 8 mean 89.3
artefact problems: none | min bytes 429160
sit background_swap passes 2 of 2
sit bundle_multipack passes 2 of 2
sit infographic passes 0 of 3
sit lifestyle passes 4 of 4
sit packaging_mockup passes 0 of 2
sit scale_reference passes 2 of 2
sit series_consistency passes 2 of 2
sit white_background_main passes 4 of 4
summary block: 21 16 92.0
```

`mean = round(sum(score)/count(scored), 1)`; `passed` counts `passed == true and not cannot_verify`.
The two situations with no pass are exactly `infographic` (0/3) and `packaging_mockup` (0/2), as
claimed.

### 3. Report table vs proof rows

```
> python $env:TEMP\opencode\tablecheck2.py
report rows vs proof mismatches: none
```

Score, pass flag and situation agree for all 21 briefs.

### 4. Bar check

```
> python -m pytest -q Northstar_backend/test_heldout_set.py
...........                                                              [100%]
11 passed in 0.25s

> python $env:TEMP\opencode\bar2.py
BAR_OK briefs= 21 situations= 8
distinct paths 10 distinct image bytes 9
DUPLICATE BYTES: ['renders/references/word-coffee/wc_women_main_front.jpg',
                  'renders/references/word-coffee/word_coffee_women_front.jpg']
```

All 21 briefs carry the tuned catalogue's constraints for their situation (no D-002 repeat); no
reference filename contains `logo`/`wordmark`; no `(reference, situation)` pair repeats.

### 5. Reference pool — looked at, not counted

`renders/references/word-coffee/` now holds 7 files; `renders/references/mogra/` holds 3;
10 non-product files (9 quote cards + `word_coffee_logo.png`) are quarantined at
`reports/ty/quarantined/references_word-coffee_not_products/`. I opened the files themselves.

| brief | situation | reference | shows the physical product? |
|---|---|---|---|
| HO-011, HO-018 | white_background_main, series_consistency | `word_coffee_moms_front.jpg` | yes — For Mom box |
| HO-012, HO-019 | lifestyle, white_background_main | `word_coffee_women_front.jpg` | yes — Modern Woman box |
| HO-014, HO-021 | scale_reference, infographic | `wc_women_main_front.jpg` | yes — same bytes as the file above |
| HO-013, HO-020 | infographic, lifestyle | `wc_women_pic_box.jpg` | yes — box on white |
| HO-016 | packaging_mockup | `wc_women_easter_table.png` | yes — boxes on a table |
| HO-017 | background_swap | `wc_women_in_purse.png` | yes — box in a handbag |
| **HO-015** | **bundle_multipack** | **`wc_women_card_mirror.jpg`** | **no — a pink affirmation card on a bathroom mirror, no box in frame** |
| HO-001…HO-010 | all eight situations | 3 Mogra photographs | yes — lion's mane / shiitake pouches |

So one of 21 briefs (HO-015, scored 80.0, **passed**) is still scored against a quote card. That is
the exact class D-003 quarantined; the file was not caught because its name has no `logo` / `card`
marker that the pin test checks.

### 6. Digest

`reports/ty/digest_composites_2026-11-09.png` is six rows, each labelled `source` (left) and
`composite` (right), and no source file repeats. The six are not six distinct products, though:
rows 1–3 are the same Mogra pouch pair from three photographs, row 4 is the For Mom box, rows 5–6 are
the same Modern Woman box in two photographs. Three product designs over six distinct source
photographs.

## Findings that do not change the numbers

1. **HO-015 is still a quote card** — D-003 residue, and it passed. The pin test only rejects names
   containing `logo`/`wordmark`, so a card with an innocuous filename gets through.
2. **`wc_women_main_front.jpg` == `word_coffee_women_front.jpg`** (sha256 `AE941A3C…`). Ten reference
   paths, nine distinct photographs. D-003's "ten real products" is one too many.
3. **Digest = 3 product designs, 6 photographs**, not six distinct products.

## Superseded run

The 21 / 13 / 86.2 verification in this file's earlier revision covered the old 12-file pool. That
proof is archived at `reports/ty/quarantined/heldout_composite_proof_first_run_20261109.json` and the
AGREE recorded there applies to an artefact no longer on disk. The D-002 bar check and the
artefact/PNG checks were re-run here and still hold.

## Reproduce my numbers

```powershell
python tools/heldout_composite.py --status          # done 21 -> verify, do not re-run
python -m pytest -q Northstar_backend/test_heldout_set.py
# then recompute mean from state/seller/heldout_proof.json results[]
```
