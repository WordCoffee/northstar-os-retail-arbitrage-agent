# Local Generation Setup Mission (2026-10-04)

> Branch `feature/creative-cluster-launch`. Autonomous localhost-only setup work.
> No install, no weights, no `MEDIA_GEN_LIVE`, no generation, no cloud, no
> exposure. Generation remains **PLANNED / NOT ARMED**.

## Autonomous work completed

1. **Read-only status detector** — `Northstar_backend/local_image_engine.py`
   (core) + `tools/local_image_engine_status.py` (CLI). Detects ComfyUI install,
   expected weights (4 files), localhost reachability, `MEDIA_GEN_LIVE`, GPU
   (nvidia-smi, best-effort), and disk. No install/download/arm.
2. **Localhost-only setup script** — `tools/setup_local_image_engine.ps1`.
   `-Check` is read-only and safe; `-Install` / `-DownloadWeights` / `-Start` are
   owner-gated and refuse without `-IUnderstandThisIsOwnerGated`. Binds
   `127.0.0.1` only; image only; no cloud.
3. **Readiness wiring** — `GET /api/v1/foundation/creative/readiness` now returns
   a `local_setup` block (comfyui_installed, weights_found/expected,
   engine_reachable, media_gate, ready_for_local_generation, note). Read-only.
4. **UI** — Creative Studio Provider Readiness (live branch) shows the local dev
   lane line (installed / weights / engine / gate) when the route is reachable.
5. **Tests** — `foundation/tests/test_local_image_engine.py` (8 offline tests:
   weight detection, home resolution, gate default, installed≠enabled, ready
   requires all four). Extended the readiness route test with `local_setup`.
6. **Docs** — `docs/LOCAL_IMAGE_ENGINE_SETUP_RUNBOOK.md` (prerequisites, gated
   steps, boundaries, truth semantics) + `docs/CREATIVE_SOCIAL_LOCAL_STATUS.md`
   §12.

## Environment findings (detected)

| Prerequisite | State |
|---|---|
| GPU | **present** — NVIDIA GeForce RTX 5080 Laptop GPU, 16303 MiB |
| Disk free | **~109.8 GB** of 994.8 GB (guide budgets 50–60 GB) |
| ComfyUI installed | **missing** |
| Weights | **0/4** expected files |
| Engine reachable (127.0.0.1:8188) | **unreachable** |
| `MEDIA_GEN_LIVE` | **off** |
| Provider keys (fal/OpenRouter/Replicate) | **none present** |

`ready_for_local_generation: False` — the only missing pieces are the four
owner-gated steps.

## Validation
- Backend creative/local-engine tests: **24 passed** (offline).
- Full foundation suite: **780 passed, 1 failed, 59 skipped** — the single failure
  is the **pre-existing** `test_frozen_file_boundary_is_a_static_rule`
  (`Northstar_backend/costco_non_kirkland/brightdata_costco_live.py` is absent in
  this worktree; unrelated to this mission), matching the documented known
  failure.
- `npm run build` → 0 errors.
- `verify-smoke` 42/0 · `verify-guards` 11/0 · `verify-acceptance` 32/0.
- `capture-creative-cluster.cjs` 82/0 (incl. local dev lane render).
- `git diff --check` clean.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** (this mission: detector + setup script + readiness wiring + UI + tests + docs)
**Autonomous work completed:** read-only local-engine status detector (core + CLI); localhost-only gated setup script; readiness `local_setup` block; UI local dev lane; 8 new offline tests + extended route test; runbook + status §12
**Environment findings:** GPU present (RTX 5080 Laptop 16GB); disk ~110 GB free; ComfyUI missing; weights 0/4; engine unreachable; gate off; no provider keys
**Setup/install scripts prepared:** `tools/setup_local_image_engine.ps1` (`-Check` safe; `-Install`/`-DownloadWeights`/`-Start` owner-gated), `tools/local_image_engine_status.py`
**Readiness/test changes:** readiness route returns `local_setup` (read-only); Creative Studio shows the local dev lane; 8 tests + route assertion
**Tests/builds run:** creative/local tests 24/0 · full foundation 780 passed / 1 pre-existing failure / 59 skipped · build 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 82/0 · diff --check clean
**Owner-gated actions still pending:** (1) install ComfyUI + deps, (2) download weights, (3) start ComfyUI (localhost), (4) set `MEDIA_GEN_LIVE=1`; also video enablement and any provider/cloud use
**Blocked items:** none autonomous — all remaining work is owner-gated
**Next owner gate:** approval to install ComfyUI + download weights (steps 1–2)
**Recommended next action:** on approval, run `tools/setup_local_image_engine.ps1 -Install -DownloadWeights -IUnderstandThisIsOwnerGated`, then `-Start`, then set `MEDIA_GEN_LIVE=1`; readiness will flip to `ready_for_local_generation: True` and a single image-only, localhost render can be tested.
