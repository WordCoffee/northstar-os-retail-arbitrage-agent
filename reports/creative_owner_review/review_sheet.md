# Owner Review Sheet — Shared Image Services

Generated: 2026-10-08T00:18:25
Folder: `generated_images/creative/review_set/`

These are **representative samples for owner visual approval**. Quality-based
defaults remain **provisional** until reviewed. "High resolution" does **not**
automatically mean higher quality — judge each sample on its own merits.

## What to inspect

| # | File | Inspect for |
|---|---|---|
| 1 | `1_faithful_product_ad.png` | Product identity preserved (source jar); label text exact & correctly spelled; contact/edges clean |
| 2 | `2_packaging_concept_exact_text.png` | It is labelled a **concept** (not a real SKU); exact text correct; label zone clean |
| 3 | `3_finished_branded_ad.png` | Text band does not cover the product; brand lockup correct; export 1080×1080 |
| 4a/4b | `4a_masked_edit_before.png` / `4b_masked_edit_after.png` | Only the masked (lower) region changed; product/label above the mask is pixel-identical |
| 5a/5b | `5a_sdxl_standard_1024.png` / `5b_sdxl_high_1280.png` | Compare detail, artifact level, and whether 1280 is actually better |

## Observations from the technical pass (not a quality verdict)

- **5a (1024, standard)** rendered a plausible jar but with **garbled AI label text**
  ("TUARIC PPODER"). This is expected and is exactly why final packaging text is
  applied by the deterministic compositor, never by the diffusion model. It also
  shows that a higher resolution is **not automatically** higher quality.
- **5b (1280, high)** produced a *different composition* at the same seed (resolution
  changes the latent layout). Judge it on its own; it is not a "better" version of 5a.
- **4a/4b (masked edit)**: the mask supplied here covers the **lower ~45%**, so the
  lower jar body and surface were redrawn. To protect the product, pass a mask that
  excludes it; unmasked pixels are preserved exactly. There is no semantic lock
  beyond the mask.

## Execution paths (this set)

- Standard run: `{'lane': 'sdxl-standard', 'execution_s': 13.535, 'interval_s': 13.67}`
- High run: `{'lane': 'sdxl-high', 'execution_s': 21.186, 'interval_s': 21.48}`
- Inputs: samples 1 and 3 **reuse** the source product photo; samples 2 and 5 are
  **freshly generated**; sample 4 **reuses** the source and a generated mask.
- ComfyUI models are unloaded between jobs; execution time **includes model loading**.

## Decisions requested

1. Approve / reject each sample.
2. Confirm or change the provisional defaults (draft = Z-Image-Turbo,
   standard = SDXL 1024, high = SDXL 1280).
3. Confirm whether 1280² is worth the extra time/VRAM vs 1024².
