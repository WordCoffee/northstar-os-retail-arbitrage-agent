# Local Generation Install Execution (2026-10-04)

> Owner-approved owner-gated steps **1–2 only**: install ComfyUI + download
> FLUX.1 Dev FP8 weights. Steps 3 (start engine) and 4 (`MEDIA_GEN_LIVE=1`)
> remain owner-gated and were **not** performed.

## Executed

1. **ComfyUI installed** at `C:\Users\T2Hol\ComfyUI` (outside the repo worktree,
   so `git status` stays clean):
   - `git clone` → ComfyUI
   - `python -m venv` + `torch 2.11.0+cu128`, `torchvision 0.26.0+cu128`,
     `torchaudio 2.11.0+cu128` (cp314 wheels) + ComfyUI `requirements.txt`.
2. **Weights downloaded** into `models/`:
   | File | Size | Source |
   |---|---|---|
   | `flux1-dev-fp8.safetensors` | 11.08 GB | Kijai/flux-fp8 |
   | `flux-vae-bf16.safetensors` | 0.16 GB | Kijai/flux-fp8 (non-gated VAE) |
   | `clip_l.safetensors` | 0.23 GB | comfyanonymous/flux_text_encoders |
   | `t5xxl_fp8_e4m3fn.safetensors` | 4.56 GB | comfyanonymous/flux_text_encoders |

## Issues found and fixed (committed)

- **`huggingface-cli` is deprecated** in huggingface_hub ≥ 1.x and refuses to
  run → switched to the `hf download` entry point (`f7c4f8e`).
- **`ae.safetensors` not present** at `Kijai/flux-fp8` (and the BFL repos are
  gated) → the non-gated VAE is `flux-vae-bf16.safetensors`; the detector now
  accepts either VAE name and the script downloads the non-gated one (`c0e891b`).
- **Native CLI stderr** terminated the script under `ErrorActionPreference=Stop`
  → set `Continue`; explicit `throw` still enforces owner gating (`f7c4f8e`).
- **Environment-dependent test** (assumed no local install) → made hermetic
  (`c0e891b`).

## Verification (read-only)

`python tools/local_image_engine_status.py`:
- ComfyUI installed: **present**
- Weights: **4/4**
- Engine reachable: **unreachable** (not started)
- Media gate: **off**
- GPU: RTX 5080 Laptop 16 GB · Disk free: **~82 GB**

`ready_for_local_generation: False` — only steps 3–4 remain.

## Still owner-gated (not performed)
3. ~~Start ComfyUI (localhost only)~~ — **done** (owner-approved): ComfyUI 0.38.0
   running on `127.0.0.1:8188`.
4. ~~Set `MEDIA_GEN_LIVE=1`~~ — **done** (owner-approved): set in the repo-root
   `.env` (gitignored, non-secret); `ready_for_local_generation: True`.
5. **Starting the first real generation** — still owner-gated.
Also gated: video enablement, cloud/paid providers, any non-localhost exposure.

**Generation remains unexecuted** — the lane is armed but nothing has been
generated yet.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `c0e891b` (install fixes `f7c4f8e`/`c0e891b`; report docs)
**Autonomous work completed:** executed owner-approved steps 1–2 (ComfyUI install + FLUX.1 Dev FP8 weights); fixed the huggingface-cli/VAE/error-handling issues; verified with the read-only detector; updated runbook + report
**Environment findings:** ComfyUI **installed** (`C:\Users\T2Hol\ComfyUI`, torch 2.11.0+cu128); weights **4/4** (~16 GB); engine **not started**; gate **off**; GPU RTX 5080 16 GB; disk ~82 GB free
**Setup/install scripts prepared:** `tools/setup_local_image_engine.ps1` (validated through -Install and -DownloadWeights), `tools/local_image_engine_status.py`
**Readiness/test changes:** detector accepts the non-gated VAE name; hermetic tests; 24 creative/local tests pass
**Tests/builds run:** creative/local tests 24/0 · `npm run build` 0 errors
**Owner-gated actions still pending:** start ComfyUI (localhost), set `MEDIA_GEN_LIVE=1`; video enablement; cloud/paid providers
**Blocked items:** none autonomous
**Next owner gate:** approval to **start ComfyUI on 127.0.0.1** (step 3)
**Recommended next action:** on approval run `powershell -ExecutionPolicy Bypass -File tools/setup_local_image_engine.ps1 -Start -IUnderstandThisIsOwnerGated`; then (separately gated) set `MEDIA_GEN_LIVE=1` and run a single image-only, localhost render test.
