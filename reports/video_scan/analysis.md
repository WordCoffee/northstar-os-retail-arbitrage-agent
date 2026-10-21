# Video-ecosystem scan — ranking

Inventory: **38,129 Hugging Face models** (GitHub rows are in `github.jsonl`; the unauthenticated search budget blocked a full repo sweep).

## Composition

| class | count |
|---|---|
| other | 18,305 |
| generation | 10,534 |
| noise | 6,306 |
| adapter | 2,641 |
| aux | 287 |
| understanding | 56 |

| pipeline_tag | count |
|---|---|
| `none` | 21,717 |
| `text-classification` | 3,092 |
| `text-to-video` | 1,940 |
| `text-generation` | 1,859 |
| `video-classification` | 1,737 |
| `image-to-video` | 1,318 |
| `unconditional-image-generation` | 1,006 |
| `text-to-image` | 871 |
| `zero-shot-image-classification` | 768 |
| `feature-extraction` | 665 |
| `robotics` | 625 |
| `video-to-video` | 384 |

## Generation models (10,534) — top by downloads

| model | downloads | likes | tag | licence | updated |
|---|---|---|---|---|---|
| `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` | 8,170,723 | 961 | image-to-video | apache-2.0 |  |
| `Kijai/WanVideo_comfy` | 3,411,598 | 2,553 | - | - |  |
| `Lightricks/LTX-2.5` | 2,057,942 | 8,729 | image-to-video | other |  |
| `comfyicu/LTX-2.5` | 1,753,513 | 8 | image-to-video | other |  |
| `DeepBeepMeep/Wan2.1` | 986,115 | 67 | - | - |  |
| `Lightricks/LTX-2.3` | 886,781 | 1,982 | image-to-video | other |  |
| `Lightricks/LTX-Video` | 854,981 | 2,365 | image-to-video | other |  |
| `Kijai/WanVideo_comfy_fp8_scaled` | 761,601 | 749 | - | apache-2.0 |  |
| `QuantStack/Wan2.2-I2V-A14B-GGUF` | 714,377 | 449 | image-to-video | apache-2.0 |  |
| `Comfy-Org/HunyuanVideo_1.5_repackaged` | 710,273 | 106 | - | other |  |
| `Lightricks/LTX-2.3-fp8` | 681,964 | 144 | image-to-video | other |  |
| `WarmBloodAban/Minimax-h3_Singularity` | 669,759 | 802 | image-to-video | apache-2.0 |  |
| `FastVideo/FastVideo-FastH3-4-step-Preview-v1-VSA-DataFree` | 668,038 | 340 | text-to-video | other |  |
| `numz/SeedVR2_comfyUI` | 624,707 | 327 | video-to-video | apache-2.0 |  |
| `DeepBeepMeep/Wan2.2` | 446,767 | 24 | - | - |  |
| `unsloth/LTX-2.3-GGUF` | 376,040 | 586 | image-to-video | other |  |
| `QuantStack/Wan2.2-TI2V-5B-GGUF` | 360,953 | 242 | text-to-video | apache-2.0 |  |
| `unsloth/Wan2.2-TI2V-5B-GGUF` | 322,377 | 25 | text-to-video | apache-2.0 |  |
| `QuantStack/Wan2.2-Animate-14B-GGUF` | 296,059 | 233 | video-to-video | apache-2.0 |  |
| `Lightricks/LTX-2` | 277,037 | 1,802 | image-to-video | other |  |
| `Winnougan/Cobijada_Minimax-H3_Hybrid_Pruned_ComfyUI` | 275,570 | 76 | image-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.1-T2V-1.3B-Diffusers` | 270,176 | 163 | text-to-video | apache-2.0 |  |
| `Abiray/MiniMax-H3-GGUF` | 244,745 | 151 | image-to-video | other |  |
| `leejet/MiniMax-H3-GGUF` | 243,790 | 26 | image-to-video | - |  |
| `Comfy-Org/HunyuanVideo_repackaged` | 234,692 | 246 | - | other |  |
| `lllyasviel/FramePackI2V_HY` | 205,572 | 132 | - | - |  |
| `Wan-AI/Wan2.2-Animate-14B` | 205,501 | 1,295 | video-to-video | apache-2.0 |  |
| `QuantStack/Wan2.2-T2V-A14B-GGUF` | 186,855 | 306 | text-to-video | apache-2.0 |  |
| `t8star/Vdn-Minimax-H3-Comfy` | 184,416 | 23 | text-to-video | other |  |
| `city96/Wan2.1-I2V-14B-480P-gguf` | 184,352 | 287 | image-to-video | apache-2.0 |  |

### Image-to-video (animate our product stills)

| model | downloads | likes | tag | licence | updated |
|---|---|---|---|---|---|
| `Comfy-Org/Wan_2.2_ComfyUI_Repackaged` | 8,170,723 | 961 | image-to-video | apache-2.0 |  |
| `Lightricks/LTX-2.5` | 2,057,942 | 8,729 | image-to-video | other |  |
| `comfyicu/LTX-2.5` | 1,753,513 | 8 | image-to-video | other |  |
| `Lightricks/LTX-2.3` | 886,781 | 1,982 | image-to-video | other |  |
| `Lightricks/LTX-Video` | 854,981 | 2,365 | image-to-video | other |  |
| `QuantStack/Wan2.2-I2V-A14B-GGUF` | 714,377 | 449 | image-to-video | apache-2.0 |  |
| `Lightricks/LTX-2.3-fp8` | 681,964 | 144 | image-to-video | other |  |
| `WarmBloodAban/Minimax-h3_Singularity` | 669,759 | 802 | image-to-video | apache-2.0 |  |
| `unsloth/LTX-2.3-GGUF` | 376,040 | 586 | image-to-video | other |  |
| `QuantStack/Wan2.2-TI2V-5B-GGUF` | 360,953 | 242 | text-to-video | apache-2.0 |  |
| `unsloth/Wan2.2-TI2V-5B-GGUF` | 322,377 | 25 | text-to-video | apache-2.0 |  |
| `Lightricks/LTX-2` | 277,037 | 1,802 | image-to-video | other |  |
| `Winnougan/Cobijada_Minimax-H3_Hybrid_Pruned_ComfyUI` | 275,570 | 76 | image-to-video | apache-2.0 |  |
| `Abiray/MiniMax-H3-GGUF` | 244,745 | 151 | image-to-video | other |  |
| `leejet/MiniMax-H3-GGUF` | 243,790 | 26 | image-to-video | - |  |
| `lllyasviel/FramePackI2V_HY` | 205,572 | 132 | - | - |  |
| `city96/Wan2.1-I2V-14B-480P-gguf` | 184,352 | 287 | image-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.1-I2V-14B-480P` | 180,942 | 241 | image-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.2-TI2V-5B-Diffusers` | 161,176 | 169 | text-to-video | apache-2.0 |  |
| `OpenMOSS-Team/MOVA-360p` | 157,881 | 217 | image-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.2-I2V-A14B-Diffusers` | 157,769 | 315 | image-to-video | apache-2.0 |  |
| `bullerwins/Wan2.2-I2V-A14B-GGUF` | 144,803 | 314 | image-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.1-VACE-14B` | 131,403 | 521 | image-to-video | apache-2.0 |  |
| `stabilityai/stable-video-diffusion-img2vid-xt` | 119,254 | 3,463 | image-to-video | other |  |
| `Wan-AI/Wan2.1-I2V-14B-720P-Diffusers` | 96,118 | 60 | image-to-video | apache-2.0 |  |

### Small / quantised / distilled (16 GB candidates)

| model | downloads | likes | tag | licence | updated |
|---|---|---|---|---|---|
| `Kijai/WanVideo_comfy_fp8_scaled` | 761,601 | 749 | - | apache-2.0 |  |
| `QuantStack/Wan2.2-I2V-A14B-GGUF` | 714,377 | 449 | image-to-video | apache-2.0 |  |
| `Lightricks/LTX-2.3-fp8` | 681,964 | 144 | image-to-video | other |  |
| `unsloth/LTX-2.3-GGUF` | 376,040 | 586 | image-to-video | other |  |
| `QuantStack/Wan2.2-TI2V-5B-GGUF` | 360,953 | 242 | text-to-video | apache-2.0 |  |
| `unsloth/Wan2.2-TI2V-5B-GGUF` | 322,377 | 25 | text-to-video | apache-2.0 |  |
| `QuantStack/Wan2.2-Animate-14B-GGUF` | 296,059 | 233 | video-to-video | apache-2.0 |  |
| `Wan-AI/Wan2.1-T2V-1.3B-Diffusers` | 270,176 | 163 | text-to-video | apache-2.0 |  |
| `Abiray/MiniMax-H3-GGUF` | 244,745 | 151 | image-to-video | other |  |
| `leejet/MiniMax-H3-GGUF` | 243,790 | 26 | image-to-video | - |  |
| `QuantStack/Wan2.2-T2V-A14B-GGUF` | 186,855 | 306 | text-to-video | apache-2.0 |  |
| `city96/Wan2.1-I2V-14B-480P-gguf` | 184,352 | 287 | image-to-video | apache-2.0 |  |
| `bullerwins/Wan2.2-I2V-A14B-GGUF` | 144,803 | 314 | image-to-video | apache-2.0 |  |
| `JoaoZaokk/LTX-2.5-22B-distilled-W4A8-ConvRot` | 142,648 | 2 | text-to-video | other |  |
| `BigDannyPt/Wan-2.2-Remix-GGUF` | 109,170 | 123 | - | apache-2.0 |  |
| `ChrisColeTech/LTX-2.3-uncensored-v1.4-FP8` | 107,081 | 305 | text-to-video | unknown |  |
| `QuantStack/Wan2.1_14B_VACE-GGUF` | 92,293 | 247 | text-to-video | apache-2.0 |  |
| `optimum-intel-internal-testing/tiny-random-ltx-video` | 87,792 | 0 | - | - |  |
| `audio-cpp/LiveAvatar-GGUF` | 74,143 | 3 | image-to-video | apache-2.0 |  |
| `ChrisColeTech/LTX-2.5-uncensored-v1.1-FP8` | 68,281 | 105 | text-to-video | unknown |  |
| `Wan-AI/Wan2.1-T2V-1.3B` | 66,897 | 637 | text-to-video | apache-2.0 |  |
| `Isi99999/Wan2.2BasedModels` | 63,321 | 0 | - | - |  |
| `unsloth/LTX-2.5-GGUF` | 59,049 | 15 | image-to-video | other |  |
| `QuantStack/Wan2.2-S2V-14B-GGUF` | 58,463 | 86 | text-to-video | apache-2.0 |  |
| `IPostYellow/TurboWan2.1-T2V-1.3B-Diffusers` | 57,812 | 0 | text-to-video | apache-2.0 |  |

## Support models (287) — top by downloads

| model | downloads | likes | tag | licence | updated |
|---|---|---|---|---|---|
| `ZawShiShawn/Gestura-MiniMax-H3-VAE-LiteRT` | 61,658 | 1 | image-to-video | other |  |
| `speach1sdef178/MiniMax-H3-X2-Detail-VAE` | 36,483 | 103 | image-to-video | other |  |
| `MangoGoes/libero4in1_wan2.2vae_latent_cosmos_style` | 23,581 | 0 | robotics | other |  |
| `spacepxl/Wan2.1-VAE-upscale2x` | 19,308 | 232 | - | apache-2.0 |  |
| `WANG-CC/flux2-klein-9b-uncensored-text-encoder-Q8_0-GGUF` | 7,344 | 10 | text-to-image | other |  |
| `Anzhc/Noobai11-CLIP-L-and-BigG-Anime-Text-Encoders` | 2,201 | 22 | - | openrail |  |
| `hpcai-tech/OpenSora-VAE-v1.2` | 2,133 | 58 | - | apache-2.0 |  |
| `ai-toolkit/wan2.1-vae` | 1,463 | 0 | - | apache-2.0 |  |
| `corechan/MiniMax-H3-LightVAE` | 1,282 | 3 | text-to-video | other |  |
| `mlx-community/RIFE-4.25` | 724 | 3 | video-to-video | mit |  |
| `EPFL-VILAB/4M_tokenizers_CLIP-B16_8k_224-448` | 522 | 2 | - | other |  |
| `ZawShiShawn/Gestura-MiniMax-H3-VAE-GGUF` | 418 | 0 | image-to-video | other |  |
| `Lightricks/ltxv-spatial-upscaler-0.9.7` | 384 | 19 | video-to-video | other |  |
| `TensorForger/RIFE-safetensors` | 377 | 3 | - | mit |  |
| `antocorr/MiniMax-H3-FL2VA-MLX-Serve-2bit-text-encoder` | 366 | 4 | text-to-video | other |  |
| `allegro/herbert-klej-cased-tokenizer-v1` | 220 | 1 | - | - |  |
| `thornmaze/wan21-vae-upscale2x` | 211 | 0 | - | - |  |
| `akhaliq/frame-interpolation-film-style` | 202 | 10 | - | - |  |
| `hpcai-tech/OpenSora-VAE-v1.3` | 183 | 1 | - | - |  |
| `RockTalk/Wan2.2-VAE-MLX` | 180 | 0 | - | apache-2.0 |  |

## Adapters / LoRAs (2,641) — top by downloads

| model | downloads | likes | tag | licence | updated |
|---|---|---|---|---|---|
| `larryvrh/MiniMax-H3-Turbo-Lora` | 204,313 | 1,138 | text-to-video | apache-2.0 |  |
| `drbaph/MiniMax-H3-Turbo-Lora-ComfyUI` | 203,819 | 514 | text-to-video | apache-2.0 |  |
| `lopi999/Wan2.2-I2V_General-NSFW-LoRA` | 150,776 | 148 | text-to-image | - |  |
| `lightx2v/Wan2.2-Distill-Loras` | 97,553 | 290 | image-to-video | apache-2.0 |  |
| `akatz-ai/MiniMax-H3-Character-Swap-LoRA` | 90,313 | 575 | video-to-video | other |  |
| `alibaba-pai/MiniMax-H3-Acc-LoRAs` | 51,051 | 271 | text-to-video | other |  |
| `Hearmeman/minimax-h3-loras` | 31,311 | 56 | text-to-video | other |  |
| `alibaba-pai/MiniMax-H3-Fun-Controlnet-Union-2.0` | 24,912 | 70 | text-to-video | other |  |
| `Jojocodex/minimax-h3-spatial-physics-lora` | 24,093 | 135 | text-to-video | apache-2.0 |  |
| `alibaba-pai/Wan2.2-Fun-Reward-LoRAs` | 20,782 | 77 | text-to-video | apache-2.0 |  |
| `Jojocodex/minimax-h3-Camera-Motion-lora` | 20,261 | 84 | text-to-video | apache-2.0 |  |
| `Lightricks/LTX-2.5-22b-IC-LoRA-Refine-Details` | 18,825 | 71 | video-to-video | other |  |
| `Jojocodex/wushu-action-v7-minimax-h3-fl2va-ref2va-lora` | 18,359 | 77 | image-to-video | other |  |
| `Lightricks/LTX-Video-ICLoRA-detailer-13b-0.9.8` | 18,278 | 38 | text-to-video | other |  |
| `joyfox/LTX-2.3-Transition-LORA` | 15,571 | 166 | image-to-video | apache-2.0 |  |
| `Lightricks/LTX-2.5-22b-IC-LoRA-Alpha-Gen` | 14,650 | 208 | video-to-video | other |  |
| `Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler` | 11,569 | 130 | video-to-video | other |  |
| `Lightricks/LTX-2.5-22b-IC-LoRA-SDR-To-HDR` | 11,296 | 40 | video-to-video | other |  |
| `adrepale/LTX2.3-10Eros-LoRA` | 10,583 | 17 | image-to-video | - |  |
| `Lightricks/LTX-2.5-22b-IC-LoRA-Ingredients` | 10,577 | 74 | video-to-video | other |  |
