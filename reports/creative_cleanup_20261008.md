# Creative Cleanup — Boundary-Compliant Removal Report

Date: 2026-10-08
Scope: remove authorized large **Qwen-Image creative** weights only, under the
mandatory boundary that preserves all non-creative models and shared runtimes.

## Method (applied before any deletion)

1. **Exact path + identity** resolved for every candidate (path, size, SHA-256,
   upstream source).
2. **Reference check across ALL worktrees/services** (mogra worktree, WT-C
   worktree, canonical `Northstar OS Retail Arbitrage Agent`, `northstar-wt-mogra`):
   the Qwen image model ids appear **only** in the creative package, its tests,
   docs, and the registry — **no non-creative service references them**.
3. **Authorized lane check:** only the large Qwen-Image creative weights were
   named as removal candidates.
4. **Dependency check (rule 4):** a retained capability that depends on a weight
   blocks its removal.

## Exact creative components removed

| Component | Path | Size | SHA-256 | Source | Recoverable |
|---|---|---|---|---|---|
| `qwen-image-2512` (t2i) | `C:\Users\T2Hol\ComfyUI\models\unet\qwen-image-2512-Q4_K_M.gguf` | **12.34 GB** | `b2a5f6249eb58ee10c9e2ce8cb1114b89897db23de2fdf7dc49140800aa928fc` | `unsloth/Qwen-Image-2512-GGUF` (Apache-2.0) | yes — re-download from source |

Disk free: **35.4 GB → 47.7 GB** (+12.3 GB).

Registry updated: `qwen-image-2512` set to `status: retired`, `present: false`;
the explicit `qwen-t2i` lane removed from `_SELECTABLE`. Generation is unaffected
(SDXL = standard/high, Z-Image = draft).

## Shared components retained

- **`qwen-image-edit-2511`** — **retained** because the retained **edit capability**
  and Mogra panel-prep depend on it (rule 4). (Authorized candidate, but protected
  by the boundary.)
- **`qwen_2.5_vl_7b_nvfp4`** (Qwen2.5-VL) — **retained**: a Qwen *vision* model,
  explicitly not authorized for removal.
- **`qwen_3_4b_fp8_mixed`** — **retained**: the Qwen3-4B encoder required by
  Z-Image-Turbo (explicitly called out).
- `qwen_image_vae` (0.24 GB) — retained (small; not a named "large" candidate).
- SDXL Base 1.0, Z-Image-Turbo, IP-Adapter, CLIP-ViT-H, ControlNet Canny SDXL,
  BiRefNet, Real-ESRGAN, bundled fonts, ComfyUI runtime.

## Confirmation: no non-creative models or runtimes removed

Ollama inventory **before == after** (identical IDs, sizes, modified dates):

| Model | ID | Size | Role |
|---|---|---|---|
| `qwen3:4b` | `359d7dd4bcda` | 2.5 GB | chat/general |
| `northstar-qwen3:rev1` | `b997b3cdd19f` | 9.3 GB | Northstar assistant |
| `qwen3:14b` | `bdbd181c33f2` | 9.3 GB | reasoning/coding |
| `qwen2.5vl:7b` | `5ced39dfa4ba` | 6.0 GB | vision |

Ollama blob store unchanged: **17 files, 16.52 GB** before and after. No blanket
cleanup of Hugging Face, Ollama, PyTorch, or shared download/model caches was
performed. No non-creative runtime was uninstalled or modified.

## Uncertain files deliberately left untouched

- **`flux1-dev-fp8.safetensors` + `t5xxl_fp8_e4m3fn.safetensors` + `clip_l` +
  `flux-vae-bf16`** (~15.8 GB): FLUX.1 [dev] is **quarantined** (non-commercial)
  but was **not** in the authorized removal lane and is still referenced by
  `comfy_client.flux_t2i_workflow` → preserved (rule 3/4).
- **`qwen_image_vae.safetensors`**: orphaned by the retirement but small and not a
  named candidate → preserved.
- **`qwen-image-edit-2511-Q4_K_M.gguf`**: authorized candidate but protected by a
  retained capability → preserved.

## Follow-up (needs explicit owner confirmation)

If the owner authorizes retiring the **Qwen editing capability** (and accepting
that Mogra panel-prep becomes unavailable), the following become removable:
`qwen-image-edit-2511-Q4_K_M.gguf` (12.34 GB) and, once nothing references them,
`qwen_image_vae.safetensors` (0.24 GB). No such authorization was given, so they
were preserved.
