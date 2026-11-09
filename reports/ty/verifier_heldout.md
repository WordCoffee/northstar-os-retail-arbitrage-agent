# Held-out run — independent verification (third pass, 2026-11-09)

Verifier: separate session from the author. Repo root
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`. Two earlier verifications are
superseded by this one (see the end of this file).

## Verdict: AGREE

21 scored, **16 passed, mean 90.0** — reproduced exactly from the proof rows on disk, not from the
summary block. Lions Mane 10 / 8 / 94.0, Word Coffee 11 / 8 / 86.3. No per-brief pass/fail differs
from the claim. Eight distinct product photographs, all 21 artefacts real.

## What I ran, in order, and the real output

### 1. Status first — the pass is complete, so it was not re-run

```
> python tools/heldout_composite.py --status
{ "total": 21, "done": 21, "remaining": [], "passed": 16, "mean": 90.0 }
```

### 2. Everything recomputed from the result rows

```
> python $env:TEMP\opencode\recheck3.py
rows 21 scored 21 passed 16 cannot_verify 0
mean 90.0
lions-mane 10 8 94.0
word-coffee 11 8 86.3
artefact problems: none | min 683227 | max 7360417
sit background_swap 2 of 2
sit bundle_multipack 2 of 2
sit infographic 0 of 3
sit lifestyle 4 of 4
sit packaging_mockup 0 of 2
sit scale_reference 2 of 2
sit series_consistency 2 of 2
sit white_background_main 4 of 4
summary block: 21 16 90.0
```

`mean = round(sum(score)/count(scored), 1)`; `passed` counts `passed == true and not cannot_verify`.
The two situations with no pass are exactly `infographic` (0/3) and `packaging_mockup` (0/2).

### 3. Report table vs proof rows

```
> python $env:TEMP\opencode\refs3.py
distinct paths 8
distinct bytes 8
dup (ref,situation): 0
logo refs: []
report vs proof mismatches: none
```

### 4. Bar check

```
> python -m pytest -q Northstar_backend/test_heldout_set.py
............                                                             [100%]
12 passed in 0.27s
```

Twelve tests pass, covering roster membership, hash-distinctness, no product twice in a situation,
and each brief's constraints equal to the tuned catalogue's for its situation (no D-002 repeat).

### 5. Reference roster — opened, not counted

| file | briefs | shows the physical product? |
|---|---|---|
| `mogra_pair_main.png` | HO-001, 004, 007, 010 | yes — lion's mane + shiitake pouches, white |
| `mogra_pair_lifestyle.png` | HO-002, 005, 008 | yes — same pouches, greenhouse |
| `mogra_forest_dusk.png` | HO-003, 006, 009 | yes — pouches, forest dusk |
| `word_coffee_moms_front.jpg` | HO-011, 016, 021 | yes — For Mom box on white |
| `word_coffee_women_front.jpg` | HO-012, 017 | yes — Modern Woman box in a kitchen |
| `wc_women_pic_box.jpg` | HO-013, 018 | yes — Modern Woman box on white |
| `wc_women_in_purse.png` | HO-015, 020 | yes — box in a handbag |
| `wc_women_easter_table.png` | HO-014, 019 | yes — box on an Easter table |

None fails. The two files I asked to be removed last time are in
`reports/ty/quarantined/references_word-coffee_not_products/` (`wc_women_card_mirror.jpg`,
`wc_women_main_front_duplicate_of_women_front.jpg`), alongside the eleven earlier non-products. No
file was deleted.

Honest limit, already stated by the author: eight photographs, but fewer product designs — the three
Mogra frames are one pouch pair and the five Word Coffee frames are two box designs. The 21 briefs
vary situation and frame, not product range.

### 6. Digest

`reports/ty/digest_composites_2026-11-09.png` is six rows, each labelled `source` (left) and
`composite` (right), from six distinct source files (three Mogra photographs, the For Mom box, and the
Modern Woman box in two different scenes). No source repeats, and every right-hand tile is a
composite of the left-hand product.

## Superseded runs

1. **21 / 13 / 86.2** — original 12-file pool, which held quote cards and the wordmark. Proof
   archived at `reports/ty/quarantined/heldout_composite_proof_first_run_20261109.json`.
2. **21 / 16 / 92.0** — ten-path pool that still contained `wc_women_card_mirror.jpg` (a quote card,
   HO-015) and a byte-identical duplicate of `word_coffee_women_front.jpg`. Both findings were acted
   on; that proof is no longer on disk.

The D-002 bar check and the artefact/PNG checks were re-run here and still hold.

## Reproduce my numbers

```powershell
python tools/heldout_composite.py --status          # done 21 -> verify, do not re-run
python -m pytest -q Northstar_backend/test_heldout_set.py
# then recompute mean from state/seller/heldout_proof.json results[]
```
