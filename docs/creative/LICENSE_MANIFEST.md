# Creative Component License Manifest

Machine-readable source: `shared/creative-components.json`. Verified from primary
sources on 2026-10-07. **This is a factual manifest, not legal certification.**

## Policy

- `commercial_use == "allowed"` → eligible for production/paid output.
- `commercial_use == "prohibited"` → **quarantined**; the router never selects it
  as a default and it may only be used for local evaluation.
- Weights and code licenses are tracked separately. A permissive code repo does
  **not** automatically license the weights.

## Approved (commercial-use allowed)

| Component | Role | License | Weight source | Commercial | Notes |
|---|---|---|---|---|---|
| qwen-image-2512 | generate | Apache-2.0 | Qwen (HuggingFace) | allowed | high-quality lane |
| qwen-image-edit-2511 | edit | Apache-2.0 | Qwen | allowed | region edits |
| qwen-clip (Qwen2.5-VL) | text-encoder | Apache-2.0 | Qwen | allowed | |
| qwen-vae | vae | Apache-2.0 | Qwen | allowed | |
| sdxl-base-1.0 | generate | CreativeML Open RAIL++-M | Stability AI | allowed | use-based restrictions pass-through |
| z-image-turbo | generate (draft) | Apache-2.0 | Tongyi-MAI / Comfy-Org | allowed | 8 NFEs |
| z-image-text-encoder (Qwen3-4B) | text-encoder | Apache-2.0 | Qwen | allowed | |
| z-image-vae (ae) | vae | Apache-2.0 | BFL autoencoder | allowed | |
| ip-adapter-sdxl | condition | Apache-2.0 | h94 (Tencent AI Lab) | allowed | |
| clip-vit-h | image-encoder | MIT | LAION | allowed | |
| controlnet-canny-sdxl | control | Apache-2.0 | xinsir | allowed | |
| birefnet | mask | MIT | ZhengPeng7 | allowed | do not substitute RMBG-2.0 (non-commercial) |
| real-esrgan | upscale | BSD-3-Clause | Xintao Wang | allowed | |
| Libre Baskerville / DM Sans | font | SIL OFL 1.1 | Impallari / Google Fonts | allowed | bundled |
| ComfyUI | runtime | GPL-3.0 | comfyanonymous | allowed | hosted distribution may trigger GPL obligations |

## Quarantined (not production-usable)

| Component | License | Reason |
|---|---|---|
| flux1-dev-fp8 (+ clip_l, t5xxl, flux-vae companions) | FLUX.1 [dev] Non-Commercial License v1.1.1 | No revenue-generating, end-user-facing, or commercial-distillation use without a paid BFL license. |

The legacy FLUX lane remains installed for local evaluation only; the router logs
it under `quarantined` and will not select it.

## Required notices

- **SDXL**: include the CreativeML Open RAIL++-M use-based restrictions
  (Attachment A) in any downstream/hosted agreement.
- **Z-Image**: retain the Apache-2.0 notice.
- **Fonts**: retain the OFL notices; do not use the Reserved Font Names on modified versions.
- **FLUX** (if ever used locally): display "The FLUX.1 [dev] Model is licensed by
  Black Forest Labs Inc. under the FLUX.1 [dev] Non-Commercial License."
- **ComfyUI**: GPL-3.0; review source-distribution obligations before hosting.

## Verification evidence

- SDXL license: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/blob/main/LICENSE.md
- Z-Image license: https://huggingface.co/Tongyi-MAI/Z-Image-Turbo (apache-2.0)
- IP-Adapter license: https://github.com/tencent-ailab/IP-Adapter/blob/main/LICENSE
- BiRefNet license: https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE
- Real-ESRGAN license: https://github.com/xinntao/Real-ESRGAN/blob/master/LICENSE
- xinsir ControlNet license: https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0 (apache-2.0)
- FLUX.1 [dev] license: https://huggingface.co/black-forest-labs/FLUX.1-dev/blob/main/LICENSE.md

SHA-256 digests for every installed weight are recorded in
`shared/creative-components.json` (populated by `tools/creative/fetch_models.py`).
