# The sel-02 jump, explained — and the number it does not mean

Owner question: *show the scoring diff, per-mode and per-brief scores, and why 21.4 % reference
coverage still yields a 93.5 mean.*

Short answer: **93.5 is the mean over the twelve briefs that can be judged, not over the
catalogue.** 21.4 % is how much of the catalogue those twelve represent. The two numbers are not in
tension — they answer different questions — but quoting 93.5 alone would be misleading, which is
why both are published together in `ty/seller_scores.json`.

## The scoring diff, per brief

Twelve briefs, all `stored_reference` (every brief in the catalogue with a reference on disk that can
be cut out and verified). "Before" is the same brief scored against the replayed file; "after" is the
real composite.

| brief | situation | before | after | passed | failed checks |
|---|---|---|---|---|---|
| ST-033 | white_background_main | 4.0 | **100.0** | yes | — |
| ST-034 | lifestyle | 37.5 | **100.0** | yes | — |
| ST-035 | infographic | 47.4 | **79.2** | no | aspect, text_free |
| ST-036 | scale_reference | 32.0 | **100.0** | yes | — |
| ST-037 | bundle_multipack | 16.0 | **100.0** | yes | — |
| ST-038 | packaging_mockup | 31.2 | **90.5** | no | aspect |
| ST-039 | background_swap | 20.0 | **100.0** | yes | — |
| ST-040 | series_consistency | 4.0 | **100.0** | yes | — |
| ST-041 | lifestyle | 0.0 | **81.0** | yes | subject_fill (non-critical) |
| ST-042 | series_consistency | 12.0 | **100.0** | yes | — |
| ST-043 | background_swap | 36.0 | **100.0** | yes | — |
| ST-044 | packaging_mockup | 31.2 | **71.4** | no | aspect, subject_fill |

Mean: **22.6 → 93.5** on these twelve. Nine pass, three do not, and the three stay in the record.

## Per mode

| mode | briefs | scored | passed | mean |
|---|---|---|---|---|
| **stored_reference** | 12 | 12 | 9 | **93.5** |
| prompt_only | 32 | 0 | — | not scored (no reference to verify) |
| uploaded_reference | 12 | 0 | — | not scored (no upload on disk) |

**One mode carries the whole published mean.** That is the fact to read first: the pipeline has
been measured on *stored* references only. Prompt-only briefs are never scored by the reference
check, and the twelve uploads have no file, so both report `scored: 0` rather than a fake zero mean.

## Per situation (recomputed from the rows)

| situation | n | passed | mean |
|---|---|---|---|
| background_swap | 2 | 2 | 100.0 |
| bundle_multipack | 1 | 1 | 100.0 |
| series_consistency | 2 | 2 | 100.0 |
| scale_reference | 1 | 1 | 100.0 |
| white_background_main | 1 | 1 | 100.0 |
| lifestyle | 2 | 2 | 90.5 |
| packaging_mockup | 2 | **0** | 81.0 |
| infographic | 1 | **0** | 79.2 |

The failures cluster in **packaging_mockup** and **infographic** — both aspect-ratio and text
constraints — not across the board. That is a specific, fixable defect rather than "the pipeline is
mediocre".

## Why 21.4 % coverage still yields 93.5

- **Coverage** = briefs with a verifiable reference ÷ all briefs = 12 ÷ 56 = **21.4 %**.
- **Mean** = average score over the briefs actually scored = 93.5 over those 12.
- **The catalogue-level number**, if every scoreable brief passed, would be **21.4** (12 × 100 ÷ 56),
  because 44 briefs contribute nothing that can be measured. That is the number that says how much
  of the product is proven, and it is the reason the scorecard's `seller` weight is 0.13 and not the
  whole score.

So the honest sentence is: *"On the 12 of 56 briefs that can be verified, the pipeline scores 93.5;
that is 21.4 % of the catalogue."* The jump from 22.1 is real — those twelve went from replayed
files to real composites — but it is a jump on a fifth of the catalogue.

## A defect found while explaining it

The merged artefact `generated_final.json` carries a **stale `by_mode` block**: it says
`stored_reference` has **3 passed**, while its own twelve result rows have **9**. The block was
inherited from the three-brief composite proof during the merge and never recomputed. The per-row
data is the truth (9 passed, mean 93.51 — recomputed here), and `ty/seller_scores.json` publishes
that. The lesson is the usual one: a summary is a second computation and has to be recomputed from
the rows, not carried along with them.

## What would move the number next

1. **Give the twelve uploads a file** — that is 12 briefs and a whole mode, currently invisible.
2. **Fix the packaging_mockup aspect constraint and the infographic text rule** — 3 of the 12
   scoreable briefs, worth roughly +7 points on this mean if they pass.
3. **Add references for the 32 prompt-only briefs** if a prompt-only run can be scored at all;
   today it cannot, so the mode is unmeasured rather than good.
