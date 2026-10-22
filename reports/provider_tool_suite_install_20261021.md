# Install run — UltraTex + OpenMontage on the local bench

**Date:** 2026-10-21 · **Branch:** `feature/v4.1-mesh`
**Operator instruction:** "ok install everything you recommend"
**Lane:** LOCAL only. Nothing installed touched a cloud path, a provider key, or spend.

---

## Installed, in one table

| Tool | Where | Size | Live proof |
|---|---|---|---|
| UltraTex (ComfyUI nodes) | `C:\Users\T2Hol\ComfyUI\custom_nodes\ComfyUI-UltraTex` | — | 9 nodes registered, 1376 total (+9) |
| FLUX.2 Klein **base** 9B Q6_K GGUF | `C:\Users\T2Hol\ComfyUI\models\diffusion_models` | 7,865,424,160 B | loaded in the live run |
| UltraTex LoRA (albedo) | `models\loras\ultratex_flux2.safetensors` | 456 MB | applied over GGUF |
| UltraTex LoRA (metallic-roughness) | `models\loras\ultratex_flux2_mr.safetensors` | 456 MB | installed, not yet exercised |
| UltraTex foreground decoder | `models\ultratex\ultratex_flux2_decoder.pt` | 94.7 MB | used in the live run |
| OpenMontage | `C:\Users\T2Hol\Desktop\Northstar External\OpenMontage` | ~1.5 GB | 690-frame MP4 rendered |
| piper-tts 1.8.0 + onnxruntime 1.31.0 | OpenMontage venv (py 3.11) | — | CLI verified |
| faster-whisper 1.2.1 | OpenMontage venv | — | flipped `transcriber` → available |

---

## UltraTex — full pipeline, live

```
queued 71f4d4af-d057-4704-a897-2e32cc24a73f
status success  completed True  elapsed_s 200
node 10 -> ['3d']   NS_UltraTex_Smoke_00001_.glb
node 11 -> ['result']
```

```
NS_UltraTex_Smoke_00001_.glb          10.27 MB   glTF magic verified
NS_UltraTex_Smoke_00001__albedo.png    2.19 MB
```

Graph: `UnetLoaderGGUF(base Q6_K) → UltraTexLoraLoader → UltraTexSampler(25 steps,
ultratex_sparse, token_chunk 8192) → UltraTexBake(2048)`, with
`qwen_3_8b_fp8mixed` as the flux2 text encoder, `flux2-vae`, the UltraTex
foreground decoder, and `uv_mode=comfy_gpu`.

### Three deviations from the example workflow, all forced and all recorded

1. **Base model is GGUF Q6_K, not the fp8 safetensors.** The fp8 repo is
   HF-gated (`401` anonymous) and the bf16 repo is 16.9 GB — neither is usable
   with 15 GB free. Q6_K is 7.33 GB and ungated. The LoRA still applies cleanly
   because `ultratex_core/lora.py` converts PEFT keys to ComfyUI's generic
   `lora_down/lora_up` patches instead of touching weights.
2. **xatlas was not installed.** It has no Python 3.14 wheel and fails to build.
   It is not required: `uv_mode=comfy_gpu` uses ComfyUI's own GPU unwrapper.
3. **Two rejected submissions before the successful one.**
   - `mask_meaning: 'background'` → the enum is literally `'background (LoadImage)'`.
   - then `ValueError: connect reference_mask` → LoadImage's MASK output must be
     wired into `UltraTexPrep.reference_mask`.

### The licence question is now answered — and it is not the answer we hoped

The first pass recorded `weights_license_unverified`. The published weight mirror
ships **`FLUX-NON-COMMERCIAL-LICENSE.md`** alongside the LoRAs. So the weights
inherit FLUX's non-commercial terms.

That is not a problem — it is the whole point of the lane split. UltraTex is
installed, works, and stays on the operator bench. `provider-suite.json` now records
`weights_license: "FLUX-NonCommercial"`, `commercial_ok: false`, and the cloud lane
returns `license_noncommercial`. **No customer render may ever use this output.**

### Honest limit on the smoke

The reference image was a synthetic orange silhouette drawn with PIL, paired with
the repo's sample fox GLB. That proves *the pipeline runs end to end*; it does not
prove *texture quality*. Quality needs a real product mesh + its approved hero plate.

---

## OpenMontage — installed outside the repo, rendered for real

```
tools 138
{'available': 38, 'unavailable': 96, 'degraded': 4}
transcriber: available        # was unavailable before faster-whisper
```

```
Rendering: world-in-numbers
Done: ...\projects\demos\renders\world-in-numbers.mp4 (4.2 MB)
Rendered 690/690 · Encoded 690/690
```

Zero API keys. ffmpeg resolved from `C:\Users\T2Hol\tools\ffmpeg\bin\ffmpeg.exe`.

**Never vendored.** It sits at `C:\Users\T2Hol\Desktop\Northstar External\OpenMontage`
for two reasons: AGPL-3.0's §13 network clause is an unanswered legal question, and
a 700-file AGPL tree inside the repo would put the whole application under review
for a feature we can reimplement.

### The number that matters

**38 of 138 tools work with no keys. 96 need paid provider keys.** "Local lane"
means *installed on this machine*, not *offline*. The suite now records
`network: true` for OpenMontage so the brain cannot infer otherwise.

---

## What the suite now reports

```
# gates off (default shell)
local: 4 usable / 14 blocked

# MEDIA_GEN_LIVE=1 + CHROMECONTROL_ROOT set
local: 11 usable / 7 blocked
  + chromeconnect, comfyui, flux2_klein, qwen_image_edit, birefnet, ultratex,
    wan22_ti2v, rapidocr, faster_whisper, piper_tts, sapi_voice
  - openmontage: gate_not_armed
  - elevenlabs_tts, fal_image_video, openrouter_text, replicate_edit: not_in_lane

cloud: 0 usable / 18 blocked
  - openmontage: agpl_network_copyleft_unreviewed
  - flux1_dev:   license_noncommercial
  - ultratex:    license_noncommercial
```

`openmontage` is still `gate_not_armed` because `OPENMONTAGE_LIVE` was not set —
that is correct. The install is proven; arming is an operator decision.

---

## Verification

```
python -m pytest test_provider_suite.py -q              24 passed
python -m pytest test_provider_suite.py test_model_router.py -q   45 passed
npm run build                                           0 errors
```

Suite-test change: `test_ready_tool_is_allowed_but_not_installed` now uses
`blender` (still genuinely `ready`), and a new
`test_unverified_weights_reason_code` covers the unverified path directly, since
UltraTex graduated from "unverified" to "confirmed non-commercial".

---

## Not installed, deliberately

| Item | Why |
|---|---|
| **Blender** | Was listed `ready`, not in the ranked adoption table. ~300 MB system app, needs admin; nothing in the two shipped adoptions depends on it. |
| **UltraTex MR LoRA run** | Installed, not exercised. The metallic-roughness pass doubles sampling time; it needs a real asset to be worth an hour. |
| **fp8 base model** | HF-gated (needs an operator token) and 16.9 GB bf16 does not fit in 15 GB free. |
| **Any paid provider key** | Not needed. The zero-key path rendered a real video. |
| **OpenMontage cloud use** | AGPL §13. Not until reviewed. |

---

## Next step

Run UltraTex once on a **real** Product Designer mesh with its approved hero plate,
and judge the bake by eye against the flat mockup. If it holds up, wire
`NS_UltraTex_*.glb` as a Design Studio asset type. That is the only remaining
question — capability is no longer in doubt.

Disk is now 8 GB free on C:. Any further model install needs a cleanup or another
drive first.
