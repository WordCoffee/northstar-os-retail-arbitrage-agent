# Image scorers: installed, calibrated, wired

**Date:** 2026-11-04 · **Asked:** "Fully install everything we need and make sure it's configed right."

---

## 1. What is installed

| Package | Version | Licence | Role |
|---|---|---|---|
| torch | **2.15.0+cpu** | BSD-3-Clause | CPU runtime (128.6 MB wheel, no CUDA libs) |
| transformers | **5.22.1** | Apache-2.0 | PickScore `CLIPModel` + `CLIPProcessor` |
| open_clip_torch | **3.3.0** | MIT | HPSv2 ViT-H/14 tower |
| timm | 1.0.31 | Apache-2.0 | open_clip dependency |
| torchvision | 0.29.2 | BSD-3-Clause | open_clip dependency |
| ftfy | 6.3.1 | Apache-2.0 | open_clip text normalisation |
| safetensors | 0.8.0 | Apache-2.0 | weights loader |

Python 3.14.5 (the interpreter the service runs on). Installed from the PyTorch CPU index for torch
and PyPI for the rest; **no cache kept**. Seven provenance rows were appended to `provenance.csv`
(`local-lane`). Disk 31.1 → **27.7 GB free** (above the 10 GB floor).
Pins are in `Northstar_backend/requirements-image-review.txt`.

Weights were already on disk from 2026-11-03 and were not re-downloaded:

* PickScore `model.safetensors` 3.94 GB (`yuvalkirstain__PickScore_v1`);
* HPSv2 `HPS_v2.1_compressed.pt` 1.97 GB (`xswu__HPSv2`).

## 2. The configuration decision that mattered: one model per process

Both towers are ViT-H/14. Measured on this 16 GB box:

| State | RSS | Free RAM |
|---|---|---|
| PickScore fp32 + HPSv2 in one process | **6.4 GB** | **0.7 GB** — swap territory |
| PickScore bf16, one process | 2.47 GB | 5.1 GB |
| HPSv2 bf16 (mmap load), one process | 4.81 GB | 3.0 GB |

Freeing and reloading inside one process does not return the memory (measured: RSS stayed 6.36 GB
after `del`), so `image_review_scorers` runs **each axis in its own child process** and lets it exit.
The parent stays small; peak is one tower at a time. bf16 changes the score by 0.006 (PickScore fp32
20.756 vs bf16 20.750), so precision is not the bottleneck.

Scoring conventions follow the authors, verified against their source:
PickScore = `CLIPModel(...).logits_per_image`; HPSv2 = normalised cosine, no logit scale (the HPSv2
`forward` normalises both features).

## 3. Calibration (measured, this box's own outputs)

`state/evidence/image_review_calibration_20261104.json`

| Image | Adherence (PickScore) | Preference (HPSv2) |
|---|---|---|
| `product_front.png` | 21.375 | 0.2412 |
| `product_back.png` | 19.375 | 0.2363 |
| listing white-bg | 23.250 | 0.2559 |
| TikTok frame | 18.125 | 0.1572 |
| flat label artwork | 19.000 | 0.1514 |
| rejected white-bg A / B | 23.750 / 23.625 | 0.2656 / 0.2637 |

Two facts this baseline forced:

1. **Preference separates a product picture from flat label art** (0.236-0.241 vs 0.151). That is
   exactly the owner-flagged failure, so `product_picture` blocks on it.
2. **It does not catch the listing-rubric defects.** The two images the rubric rejected for fill and
   shadow score *higher* than the accepted one. Preference is a floor for "is this a plausible
   product photograph", not a replacement for the page-level rubric, and the report says so rather
   than implying coverage it does not have.

Designed social frames score low by nature (0.157), so that surface records the score without
blocking on it.

## 4. Configuration

`config/image_review.json` — no floors hard-coded in code:

| Surface | Preference floor | Adherence floor | Blocks on scorers |
|---|---|---|---|
| `product_picture` | 0.20 | 18.0 | yes |
| `listing_image` | 0.20 | 18.0 | yes |
| `social_frame` | recorded | recorded | no |
| `default` (unnamed) | recorded | recorded | no |

Identity floors: pHash distance ≤ 16 (primary), SSIM ≥ 0.30 with a 0.55 rescue. A missing scorer is
`needs_review`, never `passed`; a score that is recorded but not blocking can never make an image a
deliverable on its own (pinned by test).

## 5. Wiring

* `Northstar_backend/image_review_scorers.py` — parent call + child CLI, availability probe,
  configured timeout/threads, no download at score time.
* `Northstar_backend/ship_gate.py` — reads the config for the named `surface`; loads the installed
  scorers only when that surface requires them; `Tys GraphicsAdapter` passes `params.surface`
  through, so a work order can declare `product_picture`, `listing_image` or `social_frame`.
* `state/probes/t22_image_scorers.py` — fails (not skips) if the stack is missing, and proves the
  gate reaches a scored verdict rather than `needs_review`.

## 6. Verification (real)

| Run | Result |
|---|---|
| `pytest test_ship_gate test_image_review_scorers test_tys_routing test_tys_assistant test_continuous_loop test_module_hygiene` | **143 passed** (37.6 s) |
| `t10` / `t11` / `t12` / `t21` | OK |
| `t22_image_scorers` | **OK** — preference 0.106, adherence 18.625, verdict `refused` on a flat synthetic label |
| End-to-end gate on the real product picture (`surface=product_picture`, self-reference, wordmark + net weight) | **`passed`** — identity 0, preference 0.2227 ≥ 0.20, adherence 20.75 ≥ 18.0, legibility pass |
| `image_review_scorers.available()` | `ok: true`, all three deps and both weight files present |
| Wall clock per gated image | ~10 s (PickScore) + ~13 s (HPSv2) |
| Disk / RAM after | 27.7 GB free / 7.6 GB free |

## 7. Limits (named, not hidden)

1. **PickScore/HPSv2 are proxies.** They did not separate the rubric-rejected listing images; they
   are not a substitute for `asset_rubric`, `mockup_quality`, or the operator's eye.
2. **Identity needs a reference.** `ship_gate` blocks on identity only when `params.reference` (or
   `reference_assets[0]`) is supplied. A work order that omits the real photo gets legibility and
   the scorers, not product identity.
3. **`/api/design-studio/generate` still does not run the ship gate.** Its delivery path remains
   `quality_gate` + `deliver:true`. That is the next surface to wire.
4. **Floors are provisional** (baseline of seven images, 2026-11-04). They are numbers in a config
   file; tightening them needs more of the owner's reference images, not a rewrite.
5. **Cost:** ~23 s added per fully gated image, and one 2.5-4.8 GB child process at a time. The
   render lane holds the GPU lock; these are CPU, so they do not contend for VRAM.

## 8. Rollback

* `pip uninstall torch transformers open_clip_torch timm torchvision ftfy safetensors` (only if the
  scorers are being removed; other code does not import them).
* Delete `Northstar_backend/image_review_scorers.py`, `test_image_review_scorers.py`,
  `config/image_review.json`, `tools/calibrate_image_scorers.py`, `state/probes/t22_image_scorers.py`.
* In `ship_gate.py`, revert the config/surface/default-scorer additions; in `tys_assistant.py` remove
  the `surface=params.get("surface")` argument.

Gates held: no Amazon request, no spend, no credential read, no cloud call, no policy or allowlist
change. Everything scored locally.
