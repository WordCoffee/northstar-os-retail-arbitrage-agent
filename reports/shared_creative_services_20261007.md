# Shared Creative Services Pipeline — Implementation Report

Date: 2026-10-07
Worktree: `C:\Users\T2Hol\Desktop\northstar-wt-mogra` (branch `feature/mogra-exact-text-mockup`)
Baseline hardware: MSI Vector 16 HX AI, RTX 5080 Laptop 16 GB, ~15.4 GB usable RAM.

Status legend: **INSTALLED** · **IMPLEMENTED** · **TESTED** · **VISUALLY APPROVED (pending owner)** · **BLOCKED**.

---

## 1. Architecture / capability map

Full map: `docs/creative/CAPABILITY_MAP.md`. Summary of what consumes the shared
pipeline:

- Scene generation → `registry` + `router` + `stages.generate` (SDXL / Z-Image / Qwen).
- Reference conditioning → `stages.condition` (IP-Adapter Plus).
- Structural control → `stages.control` (ControlNet Canny SDXL).
- Masking → `stages.remove_background` (BiRefNet, built-in ComfyUI node).
- Upscaling → `stages.upscale` (Real-ESRGAN, built-in ComfyUI node).
- Exact text/brand → existing `exact_text.py` compositor via `stages.compose_text`.
- Orchestration → `pipeline.py` tasks (`generate`, `edit`, `condition`, `control`,
  `mask`, `upscale`, `compose_text`, `product_ad`, `packaging_concept`).
- Job queue → `jobs.py` (single heavy worker, cancellation, stage progress, persistence).
- Provenance → `provenance.py` JSON sidecars (model, license, params, SHA-256, inputs).
- Deployment → `workers.py` + `shared/creative-deployment.json` (multi-GPU-ready).

ComfyUI is the shared local inference runtime (torch/CUDA live in its venv);
the FastAPI backend talks HTTP.

## 2. Components actually installed

20 components tracked; **19 approved / installed**, 1 quarantined.
`shared/creative-components.json` (with SHA-256 digests and presence):

- **Generation**: Qwen-Image-2512 (pre-existing), Qwen-Image-Edit-2511 (pre-existing), SDXL Base 1.0, Z-Image-Turbo nvfp4.
- **Conditioning**: IP-Adapter Plus SDXL, CLIP-ViT-H-14.
- **Control**: ControlNet Canny SDXL (xinsir).
- **Masking**: BiRefNet (444 MB).
- **Upscaling**: Real-ESRGAN x4plus (67 MB).
- **Text**: bundled Libre Baskerville + DM Sans (OFL).
- **Runtime**: ComfyUI 0.38.0 + ComfyUI-GGUF + ComfyUI_IPAdapter_plus (custom node added).
- **Z-Image support weights**: Qwen3-4B fp8 text encoder (5.63 GB), `ae.safetensors` VAE (335 MB).
- **Quarantined**: FLUX.1 [dev] fp8 + companions — non-commercial license.

Disk: 39.7 GB free before → 36.1 GB free after the core batch (Z-Image added later);
~30 GB of new weights installed total.

## 3. License manifest and notices

Full manifest: `docs/creative/LICENSE_MANIFEST.md`; machine-readable:
`shared/creative-components.json`.

Key finding: **FLUX.1 [dev] is non-commercial** and is now quarantined by the
router (never a default; surfaced explicitly). Qwen-Image/Edit, Z-Image-Turbo,
IP-Adapter, xinsir ControlNet, BiRefNet, Real-ESRGAN are all commercially usable;
SDXL is CreativeML Open RAIL++-M (use-restrictions pass-through).

## 4. Creative services / endpoints integrated

All under `/api/creative/*` (existing `mount_creative`), additive:

| Endpoint | Purpose |
|---|---|
| `GET /api/creative/components` | license manifest + presence |
| `GET /api/creative/components/status` | registry status |
| `GET /api/creative/lanes` | capability routing per mode + runtime readiness |
| `GET /api/creative/workers` | device assignment + health |
| `POST /api/creative/pipeline` | submit a task (generate/edit/condition/control/mask/upscale/compose_text/product_ad/packaging_concept) |
| `GET /api/creative/jobs`, `/jobs/{id}` | job state + stage progress |
| `POST /api/creative/jobs/{id}/cancel` | cancellation |

UI: `northstar-os-ui/src/components/CreativeServicesPanel.jsx`, rendered inside
`MockupStudio` (Studio → Exact-Text Mockups). Shows component/license status,
routing, and runs shared jobs. `npm run build` → **✓ built, 0 errors**.

## 5. Tests run and results

- New: `Northstar_backend/test_creative_shared_services.py` — **18 passed**.
- Creative suite (mockup, routes, productization, services, assets, rooms, wiring, shared):
  **133 passed in 38.45 s**.
- UI production build: **0 errors**.

## 6. Verified outputs

All produced through `/api/creative/pipeline` (job records in
`generated_images/creative_jobs/`, provenance sidecars beside each output):

| Task | Lane | Result |
|---|---|---|
| generate (draft) | z-image-draft | ✓ photorealistic turmeric jar |
| generate (standard) | sdxl-standard | ✓ studio glass jar |
| generate (standard) | qwen-t2i | ✓ (comparison) |
| condition | ip-adapter-sdxl | ✓ reference-matched jar |
| control | controlnet-canny-sdxl | ✓ canny-guided scene |
| mask | birefnet | ✓ foreground mask + transparent cutout |
| upscale | real-esrgan | ✓ 896×1152 → 3584×4608 |

## 7. Before / after performance (1024×1024, 1 variant, warm)

| Lane | Steps | Total s | Peak VRAM | Notes |
|---|---|---|---|---|
| Qwen-Image-2512 (baseline) | 20 | **53.1** | **14 087 MB** | highest quality editor; keeps routine jobs off it |
| SDXL Base 1.0 (standard) | 25 | **17.2** | **7 559 MB** | fastest + lowest VRAM; new default for standard |
| Z-Image-Turbo (draft, cold→warm) | 8 | 27.8 → **18.9** | 11 749 MB | fast concept lane; new default for draft |

Earlier Qwen reference on a 4032×3024 phone photo (16× the pixels): 20 steps in
~25.5 min (~76 s/step). At 1024² the same lane is ~53 s total, and SDXL is ~3×
faster still with ~half the VRAM. No multi-flag memory changes were made; the
existing `--lowvram` + DynamicVRAM posture was preserved.

## 8. Selected defaults and rationale

- **Draft** → Z-Image-Turbo (8 NFEs, CFG 1): near-SDXL quality, very fast, Apache-2.0.
- **Standard** → SDXL Base 1.0 (25 steps, CFG 7): fastest, lowest VRAM, commercially usable.
- **High** → Qwen-Image-2512 (30 steps): best local quality; heavy lane kept for hard cases.
- **Edit** → Qwen-Image-Edit-2511 (unchanged).
- Fallbacks are explicit and ordered; quarantined components are never selected.

## 9. Known quality/resource limitations

- Inpainting has no dedicated stage; region edits use the Qwen edit lane.
- AI-rendered text remains unreliable (the ControlNet sample rendered garbled
  text) — reinforcing that all final text goes through the deterministic compositor.
- Z-Image is ~11.7 GB VRAM at 1024²; SDXL is the safer default on 16 GB.
- The real Mogra brand typeface is not available; OFL fonts are used.
- `tools/generate_images.py` (legacy CLI) is not yet routed through the shared
  router — remaining integration gap.
- The legacy Foundation creative route (`foundation/api/creative.py`, WT-C branch)
  is not in this worktree; an adapter is required if that branch lands.

## 10. Multi-GPU readiness

`shared/creative-deployment.json` separates machine settings from workflows:
per-GPU worker entries, capabilities, max concurrency, health path, bounded queue
(`queue_max`), job timeout, retention days, component allowlist enforcement, and
quarantined-component blocking. `workers.py` exposes device assignment + health at
`/api/creative/workers`. No VRAM pooling or single-job multi-GPU acceleration is
claimed or implemented (model sharding is a separate backend concern).

## 11. Remaining owner gates

- **Final visual approval** of the representative sample set (jar generation,
  cutout, upscale, conditioned/control outputs) is pending.
- **Public/production deployment** requires approval.
- **Commercial use of FLUX.1 [dev]** would require a paid BFL license (not needed
  for the approved lanes).
- **Real-money / hosted-spend actions** remain operator-gated.

## 12. Honest status

- INSTALLED: SDXL, Z-Image-Turbo (+ encoder/VAE), IP-Adapter + CLIP-ViT-H,
  ControlNet Canny SDXL, BiRefNet, Real-ESRGAN.
- IMPLEMENTED: registry, capability router, job queue, provenance, stage
  executors, pipeline tasks, deployment config, API endpoints, UI panel.
- TESTED: 133 creative tests (18 new) + all seven stage/task paths live.
- VISUALLY APPROVED: pending owner review.
- BLOCKED: none.
- NOT integrated: legacy `tools/generate_images.py`; WT-C Foundation creative route.
