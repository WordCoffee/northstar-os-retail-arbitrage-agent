# Creative Component Integrity — 2026-10-08

Local SHA-256 computed for every installed weight. Upstream SHA-256 is
the publisher's Hugging Face LFS OID where the API exposes it; GitHub
release assets have no published digest and are recorded as
`upstream_unavailable` (never invented).

| Component | Local SHA-256 | Upstream | Status |
|---|---|---|---|
| sdxl-base-1.0 | `31e35c80fc4829d1…` | `31e35c80fc4829d1…` | match |
| z-image-turbo | `a553c889dbcb910d…` | `a553c889dbcb910d…` | match |
| z-image-text-encoder | `72450b19758172c5…` | `72450b19758172c5…` | match |
| z-image-vae | `afc8e28272cd15db…` | `afc8e28272cd15db…` | match |
| ip-adapter-sdxl | `3f5062b8400c94b7…` | `3f5062b8400c94b7…` | match |
| clip-vit-h | `6ca9667da1ca9e0b…` | `6ca9667da1ca9e0b…` | match |
| controlnet-canny-sdxl | `bf47cd757ceaf257…` | `bf47cd757ceaf257…` | match |
| birefnet | `9ab37426bf4de056…` | `9ab37426bf4de056…` | match |
| real-esrgan | `4fa0d38905f75ac0…` | `unavailable…` | upstream_unavailable |
| qwen-image-2512 | `b2a5f6249eb58ee1…` | `b2a5f6249eb58ee1…` | match |
| qwen-image-edit-2511 | `8677bac90627adbb…` | `8677bac90627adbb…` | match |

## Evidence

- **sdxl-base-1.0**: stabilityai/stable-diffusion-xl-base-1.0/sd_xl_base_1.0.safetensors (local=yes, status=match)
- **z-image-turbo**: Comfy-Org/z_image_turbo/split_files/diffusion_models/z_image_turbo_nvfp4.safetensors (local=yes, status=match)
- **z-image-text-encoder**: Comfy-Org/z_image_turbo/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors (local=yes, status=match)
- **z-image-vae**: Comfy-Org/z_image_turbo/split_files/vae/ae.safetensors (local=yes, status=match)
- **ip-adapter-sdxl**: h94/IP-Adapter/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors (local=yes, status=match)
- **clip-vit-h**: h94/IP-Adapter/models/image_encoder/model.safetensors (local=yes, status=match)
- **controlnet-canny-sdxl**: xinsir/controlnet-canny-sdxl-1.0/diffusion_pytorch_model.safetensors (local=yes, status=match)
- **birefnet**: ZhengPeng7/BiRefNet/model.safetensors (local=yes, status=match)
- **real-esrgan**: xinntao/Real-ESRGAN/v0.1.0/RealESRGAN_x4plus.pth (local=yes, status=upstream_unavailable)
- **qwen-image-2512**: unsloth/Qwen-Image-2512-GGUF/qwen-image-2512-Q4_K_M.gguf (local=yes, status=match)
- **qwen-image-edit-2511**: unsloth/Qwen-Image-Edit-2511-GGUF/qwen-image-edit-2511-Q4_K_M.gguf (local=yes, status=match)