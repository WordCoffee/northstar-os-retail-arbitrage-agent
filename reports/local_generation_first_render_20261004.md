# First Local Render — Evidence (2026-10-04)

> Owner-approved first local generation (owner-gated step 5). Localhost only,
> image only, one job. **The base model is non-commercial** — this output is an
> internal test, not for shipped/commercial use.

## Run

- Command: `python tools/local_flux_smoketest.py --prompt "a stainless steel countertop water filter on a light pine counter, soft daylight, clean minimal studio product photo" --yes`
- Engine: local ComfyUI 0.38.0 on `127.0.0.1:8188` (localhost only)
- Model: `flux1-dev-fp8.safetensors` (FLUX.1 [dev] fp8) + `flux-vae-bf16` + `clip_l` + `t5xxl_fp8`
- Graph: UNETLoader → DualCLIPLoader(flux) → VAELoader → CLIPTextEncode ×2 → EmptyLatentImage → KSampler (cfg 1.0, euler, simple, 20 steps) → VAEDecode → SaveImage
- Settings: 1024×1024, 20 steps, batch 1, `--lowvram`

## Result

- **Succeeded** — 1 image produced.
- **Latency: 38.3 s** (includes first-time model load into VRAM).
- Output: `C:\Users\T2Hol\ComfyUI\output\northstar_smoke_00001_.png`
- Verified: valid PNG (sig `89504E470D0A1A0A`), **1024×1024**, 8-bit RGB, **708,377 bytes**.
- No cloud provider contacted; no credits spent; nothing published/uploaded.

## Truth / rights notes

- The output is from **FLUX.1 [dev] (non-commercial)** → **test-only**, not for
  commercial shipping. The model-choice decision (keep dev-for-testing vs. switch
  to FLUX.1 schnell / FLUX.2 Klein 4B / HiDream-I1) remains open.
- `tools/generate_images.py --backend local` (single-file `CheckpointLoaderSimple`)
  does **not** match the split FLUX install; the smoke test is the correct path.
- ComfyUI warned that cu128 is below its preferred cu130 for optimized CUDA ops
  (it ran regardless).

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** (smoke-test `tools/local_flux_smoketest.py`; this evidence report)
**Autonomous work completed:** prepared the FLUX smoke test; ran the first real local generation; verified the output; recorded evidence
**Environment findings:** ComfyUI 0.38.0 running on 127.0.0.1:8188; weights 4/4; gate on; RTX 5080 16 GB; render completed
**Setup/install scripts prepared:** `tools/setup_local_image_engine.ps1`, `tools/local_image_engine_status.py`, `tools/local_flux_smoketest.py`
**Readiness/test changes:** readiness reports `ready_for_local_generation: True`; 24 creative/local tests pass
**Tests/builds run:** creative/local tests 24/0 · `npm run build` 0 errors
**Owner-gated actions still pending:** model-choice/rights decision (non-commercial dev model); video enablement; cloud/paid providers; non-localhost exposure
**Blocked items:** none
**Next owner gate:** model-choice/rights decision for anything beyond internal testing
**Recommended next action:** decide the commercially-licensed base model for the lane, then (optionally) wire the local engine into the Creative Studio composer behind the existing gate.
