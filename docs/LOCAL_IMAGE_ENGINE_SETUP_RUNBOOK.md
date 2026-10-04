# Local Image-Engine Setup Runbook (ComfyUI dev lane, 2026-10-04)

> Scope: a **localhost-only, image-only, operator-controlled development lane**.
> This is **not** production readiness and does **not** enable generation on its
> own. `MEDIA_GEN_LIVE` remains the single arming gate.

## Status (read-only, current environment)

```
python tools/local_image_engine_status.py
```

Last run:
- GPU: **present** — NVIDIA GeForce RTX 5080 Laptop GPU, 16303 MiB
- Disk free: **~110 GB** (guide budgets ~50–60 GB)
- ComfyUI installed: **missing**
- Weights: **0/4** expected files present
- Local engine reachable: **unreachable** (127.0.0.1:8188)
- Media gate: **off**

`ready_for_local_generation: False`.

## What is already wired (no owner action)

- `tools/generate_images.py` — CLI with a `local` backend that talks to ComfyUI at
  `COMFYUI_URL` (`/system_stats` health, `/prompt` submit).
- `Northstar_backend/local_image_engine.py` — read-only status detector (shared
  by the CLI and the readiness route).
- `Northstar_backend/foundation/api/creative.py` → `GET
  /api/v1/foundation/creative/readiness` now returns a `local_setup` block
  (installed / weights / engine / gate / ready) — read-only, no install.
- `tools/setup_local_image_engine.ps1` — localhost-only setup script (`-Check` is
  safe/read-only; install/download/start are owner-gated).
- Creative Studio Provider Readiness shows the local dev lane when the live route
  is reachable; otherwise the static checklist.

## Owner-gated steps (each requires explicit owner approval)

Run these **only** after approval; the script refuses without
`-IUnderstandThisIsOwnerGated`.

1. **Install ComfyUI + deps**
   `powershell -ExecutionPolicy Bypass -File tools/setup_local_image_engine.ps1 -Install -IUnderstandThisIsOwnerGated`
   (clones ComfyUI into `<repo>/ComfyUI`, creates a venv, installs torch cu128 + requirements)
2. **Download weights** (FLUX.1 Dev FP8 + VAE + CLIP, ~18 GB)
   `... -DownloadWeights -IUnderstandThisIsOwnerGated`
3. **Start ComfyUI** (localhost only)
   `... -Start -IUnderstandThisIsOwnerGated`
   → `python main.py --lowvram --listen 127.0.0.1 --port 8188`
4. **Arm the gate** — set `MEDIA_GEN_LIVE=1` (a separate, explicit owner step).
   Until this is set, generation stays **PLANNED / NOT ARMED**.

After all four, `local_image_engine_status.py` reports
`ready_for_local_generation: True`.

## Boundaries (enforced by design)

- **localhost only** — bind `127.0.0.1`; never `0.0.0.0`/LAN/public.
- **image only** — video generation is out of scope and disabled.
- **one job at a time** — ComfyUI default queue.
- **no cloud providers, no paid calls**.
- **no UI claim that generation is generally available**; no fake results.
- Provider-neutral cloud architecture (`media_providers.py`) is preserved and
  unchanged.

## Truth semantics

- **Local readiness ≠ production readiness.**
- **Engine installed ≠ generation enabled** (`MEDIA_GEN_LIVE` gates it).
- If a gated step is not approved, the app stays in a truthful **not-armed**
  state.
