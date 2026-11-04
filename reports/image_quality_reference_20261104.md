# Image generation: reference conditioning, best-of-N, and a measured identity floor

**Date:** 2026-11-04 · **Directive:** "Have Ty do what's best for Northstar OS and our goal. That includes quality. We can work on video later but image generation needs to be perfect for all our use cases."

---

## 1. The defect that mattered most is now fixed

Every render was text-to-image, so the model drew *a* pouch, not *your* pouch. FLUX 3 Image
Klein's multi-image conditioning was already installed and supported by this ComfyUI build
(`comfy/model_base.py` `class Flux3` consumes `reference_latents`; the `ReferenceLatent` node is in
`comfy_extras/nodes_edit_model.py`) — it was simply never used.

Live proof, same prompt and seed 4242, 512×512, measured against the real `product_front.png`:

| Render | Time | pHash distance | SSIM | Identity |
|---|---|---|---|---|
| **reference-conditioned** | 42.8 s | 22 | **0.4843** | pass |
| text-only (old behaviour) | 12.1 s | 24 | **0.2306** | **refused** |

Visually: the reference render carries the MOGRA wordmark, the lion's-mane mark and the net weight;
the text-only render invents `AETICHIN ERMNICSES` and a different pouch. Images:
`renders/mogra_lions_mane/reference_check/reference_4242.png` and `text_4242.png`.

## 2. What was built

| Piece | Where | What it does |
|---|---|---|
| FLUX 3 **mi2i** graph | `studio_generation._flux3_reference_graph` | LoadImage → VAEEncode → `ReferenceLatent` on the positive conditioning; one reference, chainable to ten |
| Reference generator | `studio_generation.generate_reference` | uploads a bounded (≤1024px) reference and renders; shares the GPU lock, RAM gate, timeout and cache release with the text lane |
| Reference plate + vector type | `product_picture.build(reference=…)` | the pouch comes from the photo, the label from the deterministic vector panel — typography is never diffused |
| Per-face references | `product_picture._reference_for` + API `references` | `{"front": id, "back": id}`; a single reference still applies to both |
| Gateway reference lane | `tools/flux3_gateway.py` | `reference_image` (base64) → multipart upload → mi2i graph; `mode` reported |
| Tys graphics lane | `tys_ops.graphics.generate` + `GraphicsAdapter` | passes reference bytes, records `mode: reference`; a missing reference file blocks instead of inventing |
| **Best-of-N** | `image_best_of.py` + `params.attempts` (1–5) | renders N, reviews each, keeps the winner, records every reject and score; ties broken by preference → adherence |
| **/generate** | `design_studio_api.GenerateIn` | `reference_asset_ids`, `surface`, `review`; a ship-gate refusal blocks the deliverable |

## 3. The gate was lying about identity (fixed)

`min_ssim` was recorded but **never used** in the decision, so a text-only render passed on pHash
alone (24 ≤ 24). Identity now requires **both** the hash distance and SSIM, unless SSIM ≥ 0.55.
Floors calibrated on the pair above: `max_phash_distance 24`, `min_ssim 0.40` — the reference render
passes (22 / 0.484), the invented one is refused (24 / 0.231). Still provisional; one pair, one seed.

## 4. Live results on the real product

**Product picture, reference plate + vector panel, `product_front.png`, seed 778:**
`ok=true`, OCR read every line — `MOGRA`, `ORGANICS`, `LION'S MANE`, `MUSHROOM POWDER`,
`NET WT. 6 0z (170 g)`, `DISTRIBUTED BY T2 HOLDINGS LLC`, `DRAFT · VERIFY BEFORE PRINT`.
Output: `renders/mogra_lions_mane/reference_pp/product_front.png`.

**Front and back pair, per-face references, seed 780:**
both faces `ok=true`, `plate_mode=reference`; the back OCR read `Supplement Facts`,
`Servings per container 85`, `2,000 mg`, the barcode line and the DRAFT notice.
Outputs: `renders/mogra_lions_mane/reference_pair/product_front.png` / `product_back.png`.

**Full ship gate on a reference render, 1024×1536, seed 777:**
`passed` — legibility pass, identity pHash 0 / SSIM 0.9329, preference 0.2314 ≥ 0.20,
adherence 20.75 ≥ 18.0. Output: `reference_check/reference_1536_seed777.png`.

## 5. Verification (real runs)

| Run | Result |
|---|---|
| `pytest` — ship gate, scorers, routing, assistant, loop, hygiene, studio reference, best-of, reference wiring, generate contract, design-studio openapi | **173 passed** (43.2 s) |
| `pytest` — product picture (reference) + product picture + mockup product picture | **27 passed** (23.6 s) |
| Probes `t10`, `t11`, `t12`, `t21`, `t22` | all **OK** |
| Live renders | 4 (2 sizes + front/back pair), all gated as recorded above |
| After the run | ComfyUI stopped (RAM 8.7 GB free), disk 34.9 GB free |

## 6. What is still not perfect (named)

1. **Reference-only renders still diffuse small print.** The 1536 reference render reads
   `MOGRA` and `NET WT. 6 oz (170 g)` correctly but invents the sub-lines. The product-picture path
   avoids this by compositing the vector panel; a scene render with the reference does not. Route
   any copy-bearing surface through the composite, not the raw render.
2. **Back-face data is still DRAFT.** Nutrition values are the owner-stated ones and the barcode is a
   placeholder (`8 500000 00000 4`). The picture is honest about it; a print order needs the real
   numbers and UPC.
3. **Best-of-N is opt-in** (`params.attempts`). Three candidates cost 3× render + 2× scoring (~2–3
   minutes). It is the right default for a final packshot, not for every iteration.
4. **The gateway's multipart upload is structurally tested, not live-tested.** The live renders went
   through `studio_generation.upload_image`; the Tys gateway path has not yet run a reference end to
   end. First agent reference render should be treated as a wiring check.
5. **Identity floors are provisional.** One same-seed pair and a self-reference. More of the owner's
   reference images tighten them.

## 7. Rollback

* New files: `Northstar_backend/image_best_of.py`, `test_image_best_of.py`,
  `test_reference_wiring.py`, `test_studio_reference.py`, `test_product_picture_reference.py`,
  `test_studio_generate_contract.py` — delete to revert.
* `studio_generation.py` — remove `_flux3_reference_graph`, `prepare_reference`,
  `_run_image_session`, `generate_reference`; restore the inline body in `generate_image`.
* `product_picture.py` — remove `reference` / `_reference_for` and the per-face branch.
* `tys_assistant.py` — remove the reference read and `image_best_of` branch.
* `tools/flux3_gateway.py`, `Northstar_backend/tys_ops/graphics.py` — remove the reference fields.
* `design_studio_api.py`, `product_picture_api.py` — remove the new request fields and review block.

Gates held: no Amazon request, no spend, no credential read, no cloud call, no policy/allowlist
change. All renders ran on the local GPU; ComfyUI was stopped afterwards.
