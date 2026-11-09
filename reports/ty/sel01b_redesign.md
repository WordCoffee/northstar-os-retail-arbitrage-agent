# sel-01b redesigned: composite the real product, generate only the scene

Owner instruction, 2026-11-08. The job stays first in the queue; its design changed.

## The new design

| input | path | why |
|---|---|---|
| **uploaded reference** | cut the product out of the upload (alpha) and **composite** it into a generated scene | the product pixels must be the real product; generating them risks a different pouch |
| **stored reference** | composite when a cutout exists, otherwise the same cut-out step on the stored asset | same reason |
| **prompt only** / briefs marked `fidelity: tolerant` | full generation | nothing to preserve exactly |

So the generator is a **CompositeGenerator**: cutout → scene → composite, with the scene coming
from the render lane (`tools/comfy_lane.py`, start fresh and stop after). Where the media lane is
unavailable the generator must fail with a reason — a replayed image dressed as a composite is
the failure mode this design exists to prevent.

## The first real uploads are in place

`renders/references/mogra/manifest.json` names three genuine Mogra Organics assets already in
this checkout, copied into the reference tree with their source path recorded:

| file | source | subject |
|---|---|---|
| `mogra_pair_main.png` | `renders/smoke_main_2000.png` | two stand-up pouches, white background main |
| `mogra_pair_lifestyle.png` | `renders/smoke_cutout_alpha.png` | the same pouches in a greenhouse scene |
| `mogra_forest_dusk.png` | `renders/mogra-forest-dusk-mockup-complete.png` | packaging mockup, forest dusk |

Their printed text is recorded too, because that is what the check now matches on:
`MOGRA ORGANICS`, `ORGANIC LION'S MANE`, `MUSHROOM POWDER`, `6 oz (170 g)`, `ORGANIC SHIITAKE`,
`8 oz (227 g)`.

## The reference check changed with it

`tools/seller_tester/reference_check.py` now decides by, in order:

1. **printed text** — OCR with the local ONNX engine (`rapidocr_onnxruntime`, 4.3 s cold, no
   network). Real OCR on the Mogra main returns `MOGRAORGAICS`, `ORGANISLION'SMANE`,
   `ORGANIC SHITAKE` — mangled, so matching is fuzzy (`difflib`, ratio ≥ 0.82) and token-based
   over key words of 5+ characters. A produced picture must recall ≥ 60 % of them.
2. **meaning** — cosine between the local vision model's descriptions of the two pictures,
   embedded with `qwen3-embedding:0.6b` (installed). Threshold 0.72, used when there is no text.
3. **colour — diagnostic only.** The 0.60 agreement is still measured and reported, and it no
   longer decides anything. That is the owner's instruction and it is also the honest reading of
   the calibration: a genuine pouch crop scored 0.603 while three dark-green UI screenshots
   scored 0.637.

`cannot_verify` remains a failure. Nothing reports a pass it did not measure.

## Tests

```
python -m pytest Northstar_backend/test_seller_tester.py -q
44 passed in 9.89s
```

New cases pin the behaviour that changed: text decides (colour cannot override it), a
different-colour picture with correct text **passes** and says `colour_gate: false`, colour
matches do not rescue missing text, embeddings decide when there is no text, and OCR noise
(`MOGRAORGAICS`) still matches.

## The editor benchmark

Part of the job, not a side quest: three or more local cutout approaches measured on the three
Mogra assets (coverage, edge quality, time), the winner recorded as an `editors` role in the
model leaderboard, and every candidate's licence logged in `provenance.csv`. Preference is not
evidence.
