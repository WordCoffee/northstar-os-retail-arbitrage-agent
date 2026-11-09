# Verifier task — reproduce the held-out numbers

You are an independent lane. The author of the held-out run is a different session; **your job is to
disagree if the numbers do not reproduce**, not to confirm them.

## What was claimed

`reports/ty/heldout_2026-11-09.md` and `state/seller/heldout_proof.json`: a mean over 21 held-out
briefs on two product lines (Lion's Mane, Word Coffee), plus three Neck Nirvana briefs declared
unscorable because no product photograph exists on this machine.

## How to reproduce

Run from the repository root. Do not edit anything; write only to `reports/ty/verifier_*`.

```powershell
# 1. the briefs are the ones on disk, not a re-generation
python tools/heldout_briefs.py --write

# 2. the composite pass, from the same crowded-catalogue script the author used
python -m tools.seller_tester composite --catalog ty/seller_briefs_heldout.json --limit 21 `
    --renderer comfy --model sdxl --scene-size 768 --steps 20 `
    --out-dir renders/seller_composite_heldout `
    --summary-out state/seller/heldout_composite_proof.json `
    --gaps state/seller/heldout_gaps.json

# 3. the split
python tools/heldout_run.py --write
```

Then recompute the mean yourself from `state/seller/heldout_proof.json` — do not trust the
`summary` block. `mean = sum(score) / count(scored)`, one decimal place, and `cannot_verify` counts
as a failure.

## What to record in `reports/ty/verifier_heldout.json`

```json
{"unit": "heldout-run", "verdict": "AGREE" | "DISAGREE",
 "claimed": {"scored": 0, "passed": 0, "mean": null},
 "reproduced": {"scored": 0, "passed": 0, "mean": null},
 "per_brief_mismatches": [], "notes": ""}
```

## Rules

- A `cannot_verify` is a failure, never a pass.
- If the composite pass refuses (RAM below the 3 GB floor, ComfyUI unreachable), say **BLOCKED** and
  name the reading; do not substitute `--renderer synthetic` and call it a reproduction.
- Renders are stochastic. Scores may differ slightly; a **different pass/fail on any brief** is a
  DISAGREE, and so is a mean more than 3 points away.
- Record the command you actually ran and its real output line, not a paraphrase.
