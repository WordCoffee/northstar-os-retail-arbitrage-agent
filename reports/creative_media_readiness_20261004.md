# Creative Media Readiness — Verification & Truth Pass (2026-10-04)

> Branch: `feature/creative-cluster-launch`. Commit `89754b2`.
> Scope: Creative Studio media-generation surfaces only. No provider/route/
> publishing changes. Local-only; nothing generated.

## Media path inspected (exact reality)

| Path | Exists? | Notes |
|---|---|---|
| `tools/generate_images.py` | **YES** | Standalone CLI. `--backend local` → **ComfyUI at `COMFYUI_URL`** (default `http://127.0.0.1:8188`). Also pollinations / cloudflare / huggingface. Not imported by any API. |
| `shared/model-suite.json` | **YES** | Vision V1/V2/V3 each define `generate.local = "comfyui:flux2-klein-4b"`. |
| `Northstar_backend/model_router.resolve_vision` | **YES** | `provider='local', role='generate'` → `backend=comfyui`, `model=comfyui:flux2-klein-4b`, `available=True` **unconditionally** (no reachability probe). Cloud generation gated by `MEDIA_GEN_LIVE=1` + provider key. |
| `foundation/data_rights.py` | **YES** | `image_generation` = `NOT_INTEGRATED` ("creative assets (planned)"). |
| HTTP route exposing generation | **NO** | `foundation/api/router.py` has zero creative/media endpoints. |
| ComfyUI installed / running | **NO** | Port `127.0.0.1:8188` closed; no ComfyUI install directory found. |
| `MEDIA_GEN_LIVE` armed | **NO** | Off by default. |
| 4-state generation truth UI | was **missing** | `ProviderBoundary` said "PROVIDER REQUIRED / not connected"; readiness checklist was static with no "route" item. |

## Plan answers

1. **What exists for local image generation** — a CLI + model-suite mapping +
   router resolution + data-rights entry. All dormant; none reachable from the UI.
2. **What is missing** — an HTTP media route (doc recommends
   `foundation/api/creative.py`), a ComfyUI install + weights, `MEDIA_GEN_LIVE=1`,
   a readiness probe, and an asset-return path.
3. **What can be made real now** — only the **truth states** (frontend). No
   generation can be made real without the owner arming ComfyUI + a media route.
4. **What must be relabelled while unarmed** — `ProviderBoundary`,
   `Provider Readiness`, composer/video preview pills, and helper copy (all done).
5. **Minimum demo/launch-safe experience now** — a 4-state generation-truth legend
   + an explicitly *static* readiness checklist + "planned, not armed" surfaces.

## Generation truth changes (commit `89754b2`)

- **`ProviderBoundary`** — replaced "PROVIDER REQUIRED / not connected" with an
  explicit state pill from `GEN_STATE` (currently **PLANNED — NOT ARMED**) and,
  for the unarmed state, plainly states: no media route is wired, no local engine
  is reachable, records only.
- **`Provider Readiness`** — header pill **"static · not live-probed"**; **5**
  honest prerequisites including the previously-missing *"Generation route exposed
  to the app"*; each item carries its truth detail (env default, off-by-default
  gate, operator-managed weights, unprobed GPU); footnote states the checklist is
  static and lists exactly what arming requires.
- **4-state legend** — `LOCAL GENERATION AVAILABLE · PROVIDER-GATED · DEMO-ONLY ·
  PLANNED — NOT ARMED`, with the current state emphasised.
- **Composer / Video** — preview pills and helper copy relabelled to
  "planned, not armed"; the composer boundary text now names all arming
  prerequisites.
- **Room notice + "Compose Image" toast** — no longer says "provider not
  connected"; says generation is "planned, not armed".

## Local generation viability

**NOT VIABLE in this environment.** The engine is not installed, the gate is off,
and no route exposes it. Per the truth rules, the UI was corrected to say so
rather than imply capability. Arming is an **owner-required decision** (install
ComfyUI + weights on the operator machine, add a media route, set
`MEDIA_GEN_LIVE=1`).

## UI surfaces updated
- `northstar-os-ui/src/pages/internal/CreativeStudio.jsx` — ProviderBoundary,
  ReadinessChecklist, GenerationTruthLegend, composer/video preview + helper copy,
  room DataNotice, Compose Image toast.

## Tests / builds
- `npm run build` → **0 errors**, 88 modules.
- `verify-smoke.cjs` **42/0** · `verify-guards.cjs` **11/0** ·
  `verify-acceptance.cjs` **32/0**.
- `capture-creative-cluster.cjs` → **32/0** (incl. new media-truth assertions:
  PLANNED label, static readiness label, 4-state legend, no stale
  "not connected"/"provider required" wording).
- `git diff --check` clean.

## Screenshots
`northstar-os-ui/screenshots/session-creative-cluster-20261004/` (untracked):
`creative-studio-desktop-media-truth.png`, `creative-studio-desktop-video-truth.png`
(+ the earlier cluster set).

## Remaining provider-gated gaps
- No media route; ComfyUI not installed/reachable; `MEDIA_GEN_LIVE` off.
- `resolve_vision(local,'generate')` reports `available=True` without probing —
  a latent truth risk if a future route trusts it blindly (left unchanged; a test
  asserts current behaviour).
- No asset store / download path.

---

## REPORT FORMAT

**Worktree:** `C:\Users\T2Hol\AppData\Local\Temp\opencode\ns-creative-social-polish-v2`
**Branch:** `feature/creative-cluster-launch`
**Base commit:** `8ba0c9e`
**Current commit:** `89754b2`
**Creative media paths inspected:** `tools/generate_images.py`, `shared/model-suite.json`, `model_router.resolve_vision`, `foundation/data_rights.py`, `foundation/api/router.py`, Creative Studio readiness/boundary UI, `docs/LOCAL_IMAGE_GEN_SETUP.md`, `docs/CREATIVE_MEDIA_STACK.md`
**Local generation viability:** **NOT VIABLE now** — CLI exists, but no media route, ComfyUI not installed/reachable (port 8188 closed), `MEDIA_GEN_LIVE` off. Arming is an owner decision.
**Generation truth changes:** PLANNED—NOT ARMED boundary; static readiness checklist (5 items incl. "route exposed"); 4-state legend; composer/video relabels
**UI surfaces updated:** `CreativeStudio.jsx` (ProviderBoundary, ReadinessChecklist, GenerationTruthLegend, composer/video copy, DataNotice, toast)
**Tests/builds run:** build 0 errors · smoke 42/0 · guards 11/0 · acceptance 32/0 · capture 32/0 · diff --check clean
**Screenshots captured:** `creative-studio-desktop-media-truth.png`, `creative-studio-desktop-video-truth.png` (+ cluster set)
**Remaining provider-gated gaps:** no media route; ComfyUI absent; gate off; no asset-return path; `resolve_vision` reports local `available=True` without probing
**Blocked items:** **owner decision to arm/allow local ComfyUI execution** (install ComfyUI + weights, add media route, set `MEDIA_GEN_LIVE=1`)
**Recommended next action:** owner approves the minimal `foundation/api/creative.py` readiness-only route (returns `provider_required` when the engine is unreachable) so Provider Readiness becomes a live probe; generation route + asset store follow only after ComfyUI is installed and the gate is armed
