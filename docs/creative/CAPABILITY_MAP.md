# Northstar OS — Creative Services Capability Map

Source of truth: repository at `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
(branch `feature/mogra-exact-text-mockup`), inspected 2026-10-07. Every row below
was verified on disk; nothing is assumed from prior reports.

Legend for **status**: `WIRED` = reachable end-to-end, `PARTIAL` = implemented but
not fully integrated, `PLANNED` = contract only, `MISSING` = no implementation.

---

## 1. Existing creative capabilities and consumers

| # | Capability | Current implementation (files) | Shared service it must consume | Required integration change | Test coverage | Missing / limitation |
|---|---|---|---|---|---|---|
| 1 | Text-to-image | `Northstar_backend/creative/comfy_client.py` `qwen_t2i_workflow`; new `workflows.py` `sdxl_t2i`, `z_image_t2i` | `registry` + `router` + `stages.generate` | Route through `router.route("generate", mode)`; remove implicit Qwen default | `test_creative_mockup.py`, `test_creative_routes.py` | SDXL / Z-Image lanes new (see §2) |
| 2 | Image-to-image / reference-conditioned edit | `comfy_client.qwen_edit_workflow`, `edit_scene` | `router` (`capability=edit`), `stages` | Route via `capability=edit`; expose via pipeline | `test_creative_mockup.py` | IP-Adapter conditioning new |
| 3 | Product photography / scene creation | `mogra_mockup.build_mockup`, `comfy_client.build_scene_prompt` | `pipeline` task `packaging_concept` / `product_ad` | Move scene generation behind `stages.generate` | `test_creative_mockup.py` | — |
| 4 | Packaging / product mockups | `mogra_mockup.py`, `presets.py`, `label_zone.py` | `pipeline` task `packaging_concept` | Add explicit "concept" labelling + provenance | `test_creative_mockup.py`, `test_creative_productization.py` | Concept-vs-faithful labelling enforced in code |
| 5 | Advertising creatives | `AdPilotLane.jsx` (planning only); `service_routes.py` `/api/ad-pilot/*` | `pipeline` `product_ad` + asset library | Add ad-export preset to `bundles.py` consumers | `test_creative_services.py` | No creative ad renderer (PPC planning only) |
| 6 | Background removal / masking | **NEW**: `stages.remove_background` + `workflows.remove_background` (ComfyUI BiRefNet built-in) | `stages` + `registry` (`role=mask`) | Register `birefnet` component; expose `/api/creative/pipeline {task:mask}` | new (`tools/creative/smoke.py`) | None (built-in nodes) |
| 7 | Inpainting / background replacement | **MISSING** (only Qwen edit as a region edit) | `router` (`capability=edit`) + `stages` | Add masked-latent inpainting stage | none | No dedicated inpaint backend yet |
| 8 | Upscaling / enhancement | **NEW**: `stages.upscale` + `workflows.upscale_image` (ComfyUI Real-ESRGAN) | `stages` + `registry` (`role=upscale`) | Register `real-esrgan`; expose pipeline task | new smoke | tiled upscale for >4K later |
| 9 | Brand assets / typography / exact text | `exact_text.py` (623 lines), `assets/fonts/*` (OFL), `presets.py` | `stages.compose_text` | Route all text through the compositor; never let the model draw text | `test_creative_mockup.py`, `test_creative_productization.py` | Real Mogra typeface still a gap (uses Libre Baskerville / DM Sans) |
| 10 | Asset library / export | `assets.py`, `bundles.py`, `storage.py` | `provenance` sidecars + `storage` backend | Attach provenance to every output; export bundles include sidecars | `test_creative_assets.py` | — |
| 11 | Video / motion | `video.py` (catalog/estimate only); `VIDEO_PROVIDER` UI posture | `pipeline` (future `video` task) | Keep specialist backend; do not fake with image models | `test_creative_batchd.py` | No local video backend installed |
| 12 | Creative planning / quality review | `approvals.py`, `providers.py`, `moderation.py` | `router.policy` + `registry` | Gate quarantined lanes at routing time | `test_creative_wiring.py` | — |

## 2. Approved model lanes (registry)

| Component | Family | Role | License | Commercial | Status |
|---|---|---|---|---|---|
| `qwen-image-2512` | qwen-image | generate (t2i) | Apache-2.0 | allowed | **RETIRED 2026-10-08** (authorized creative cleanup; weight removed, recoverable) |
| `qwen-image-edit-2511` | qwen-image | edit | Apache-2.0 | allowed | installed |
| `sdxl-base-1.0` | sdxl | generate | CreativeML Open RAIL++-M | allowed | install (this mission) |
| `z-image-turbo` | z-image | generate (fast) | Apache-2.0 | allowed | install (this mission) |
| `ip-adapter-sdxl` | sdxl | condition | Apache-2.0 | allowed | install (this mission) |
| `controlnet-canny-sdxl` | sdxl | control | Apache-2.0 | allowed | install (this mission) |
| `birefnet` | birefnet | mask | MIT | allowed | install (this mission) |
| `real-esrgan` | realesrgan | upscale | BSD-3-Clause | allowed | install (this mission) |
| `flux1-dev-fp8` | flux | generate (legacy) | FLUX.1 [dev] Non-Commercial | **prohibited** | **QUARANTINED** |
| brand fonts | brand | text | SIL OFL 1.1 | allowed | bundled |

## 3. Consumers that must use shared services

| Consumer | File | Change made / required |
|---|---|---|
| Exact-Text Mockups UI | `northstar-os-ui/src/components/MockupStudio.jsx` | Adds a "Pipeline" panel: component status, lane routing, and job submission via `/api/creative/pipeline`. |
| Creative Studio | `northstar-os-ui/src/pages/internal/CreativeStudio.jsx` | Surfaces shared capabilities (adds a "Creative Services" tab reading `/api/creative/lanes` + `/api/creative/components`). |
| Service lanes API | `Northstar_backend/creative/service_routes.py` | Unchanged contracts; still mounted. |
| Legacy Foundation creative route (WT-C) | `foundation/api/creative.py` | Not merged in this worktree; adapter required if that branch lands. |
| `tools/generate_images.py` | `tools/generate_images.py` | Still standalone (not wired to the shared router). **Remaining gap.** |

## 4. Scope limitations

- The Qwen-Image lane remains the highest-quality local editor and stays installed.
  Routine *generation* now prefers SDXL / Z-Image once validated; Qwen is used for
  edits and hard cases. Fallbacks are explicit.
- Inpainting is not implemented as a dedicated stage; region edits use the Qwen edit lane.
- No local video model is installed; video stays provider-gated.
- The real Mogra brand typeface is not available; bundled OFL fonts are used.

## 5. Acceptance evidence

See `reports/shared_creative_services_20261007.md` and
`reports/shared_creative_services_continuation_20261007.md` for the benchmark,
installed component sizes + SHA-256, job logs, and the representative sample set.

## 6. Consumer integration (continuation pass)

| Consumer | Classification | Routed through shared services? |
|---|---|---|
| `creative/comfy_client.py`, `workflows.py`, `stages.py` | shared-runtime internal | yes (they *are* the runtime) |
| `creative/mogra_mockup.py` scene step | consumer | **yes** (`stages.generate`); Edit-2511 panel prep remains direct (edit lane) |
| `creative/routes.py` `/generate-scene`, `/mockup` | consumer | **yes** |
| `tools/generate_images.py` local backend | consumer | **yes** (in-process, else HTTP); direct graph only as standalone fallback |
| `model_router.py` | diagnostic/config | n/a (no generation) |
| `creative/video.py` | specialised cloud (gated) | n/a (not ComfyUI); gated + provenance-reviewed |
| WT-C `foundation/api/creative.py` | consumer (other worktree) | **adapter provided** (`creative/foundation_contract.py`, `/api/v1/foundation/creative/*`); delegation documented, not auto-applied |
| WT-C `local_image_gen.py` / `comfyui_client.py` | retired on this branch | superseded |

## 7. Routing policy (provisional)

| Capability | draft | standard | high |
|---|---|---|---|
| generate | Z-Image-Turbo | SDXL Base 1.0 | SDXL Base 1.0 (1280²) |
| edit | Qwen-Image-Edit-2511 | same | same |
| inpaint | SDXL + SetLatentNoiseMask | same | same |

Qwen-Image-Edit-2511 is routed by the **editing capability** only — never a generic
"high quality" label. The Qwen-Image-2512 t2i weight (and its explicit `qwen-t2i`
lane) was **retired on 2026-10-08** under the authorized creative cleanup; generation
is covered by SDXL (standard/high) and Z-Image (draft). Quality defaults are
provisional pending owner visual review.
