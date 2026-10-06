# Mogra Organics exact-text mockup workflow — build report

**Date:** 2026-10-06
**Worktree:** `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
**Branch:** `feature/mogra-exact-text-mockup`
**Base commit:** `435c9a1` (`feature/creative-social-local`)
**Class:** autonomous build + install + live validation

---

## Why

Set up the complete local Mogra Organics exact-text mockup workflow, install and
validate the local Qwen image lane, and define a **reusable NorthstarOS standard
so any future service can produce crisp product images with exact text**.

The governing rule, now enforced in code: **the AI image model generates or edits
the scene; a deterministic compositor applies every final glyph. The AI is never
the source of truth for text.**

---

## Inspection findings (what existed before)

* `C:\Users\T2Hol\ComfyUI` already present, `ComfyUI-GGUF` node installed.
* `qwen-image-edit-2511-Q4_K_M.gguf` on disk but **truncated (3.16 GB)** — an
  unfinished download; a 20B Q4_K_M is ~12.34 GB.
* **Missing:** the shared Qwen text encoder and the Qwen VAE.
* No Qwen GGUF workflow builder, no exact-text compositor, no Mogra presets, no
  `tools/mogra_label_render.py` anywhere in the repo.
* Existing adjacent tooling: `tools/generate_images.py` (ComfyUI local backend),
  `Northstar_backend/model_router.resolve_vision` (local → `comfyui`, gated by
  `MEDIA_GEN_LIVE`), `docs/LOCAL_IMAGE_GEN_SETUP.md`. None of it covered Qwen,
  exact text, or presets — so a focused new lane was built and reuses the same
  ComfyUI install.
* Disk 66 GB free, GPU RTX 5080 Laptop 16 GB (Blackwell, nvfp4-capable), 16 GB RAM.

---

## Installs / downloads completed

| File | Size | Source | Location |
|------|------|--------|----------|
| `qwen_2.5_vl_7b_nvfp4.safetensors` (shared encoder) | 5.69 GB | `Comfy-Org/Qwen-Image_ComfyUI` | `models/text_encoders/` |
| `qwen_image_vae.safetensors` | 0.24 GB | `Comfy-Org/Qwen-Image_ComfyUI` | `models/vae/` |
| `qwen-image-2512-Q4_K_M.gguf` (t2i) | 12.34 GB | `unsloth/Qwen-Image-2512-GGUF` | `models/unet/` |
| `qwen-image-edit-2511-Q4_K_M.gguf` (edit, **re-downloaded**) | 12.34 GB | `unsloth/Qwen-Image-Edit-2511-GGUF` | `models/unet/` |

* The truncated edit file was retired to `qwen-image-edit-2511-Q4_K_M.gguf.truncated`.
* `ComfyUI-GGUF` was already installed — reused, no new node.
* No new infrastructure; the existing ComfyUI lane was extended.

---

## Files created / changed

New package `Northstar_backend/creative/`:

| File | Purpose |
|------|---------|
| `__init__.py` | package + the two-lane contract |
| `exact_text.py` | deterministic exact-text compositor: `LabelSpec`, `render_label_layer`, `quad_homography`, `warp_to_quad`, `compose_exact_text`; rectangle / 4-corner quad perspective / cylindrical curvature; brand-content guard (`BrandContentError`); width-aware font auto-fit |
| `comfy_client.py` | ComfyUI client (stdlib only) + `qwen_t2i_workflow` (Qwen-Image-2512), `qwen_edit_workflow` (Edit-2511), `flux_t2i_workflow`; `resolve_models`; `generate_scene` / `edit_scene`; GGUF-vs-safetensors loader auto-select |
| `presets.py` | Mogra brand + rules + forbidden-tokens; 3 container presets; 3 product presets; generic surface zones; label styles; `catalog()` |
| `mogra_mockup.py` | `build_mockup` pipeline + CLI; writes PNG + editable JSON sidecar |
| `routes.py` | `/api/creative/*` routes + `mount_creative(app)` |
| `static/mockup.html` | beginner standalone UI (upload, preset dropdowns, text fields, preview, one "Generate Final Mockup" button, advanced corners/curvature) |
| `README.md` | package pointer |

Changed: `Northstar_backend/main.py` (mounts the lane additively, local-only),
`.gitignore` (ignore `generated_images/mogra_mockups/`), `00_STATE.json`
(activity + known issue + next batch), `docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md` (new).

Tests: `Northstar_backend/test_creative_mockup.py`,
`Northstar_backend/test_creative_routes.py` — **38 passed**.

---

## The reusable workflow standard

1. **Scene generation** — Qwen-Image-2512 (t2i) or Qwen-Image-Edit-2511 (edit).
2. **Text-safe zone prep** — container/surface preset → normalized 4-corner quad.
3. **Exact text mode** — deterministic composite → high-res PNG.
4. **Optional surface** — perspective warp onto the quad + cylindrical curvature.
5. **Output** — flattened PNG + JSON sidecar with the exact params/presets.

Presets: containers `mogra_5lb_clear_handled_pet_jar`, `mogra_32oz_standup_pouch`,
`mogra_4oz_window_pouch`; products (Black Peppercorns / White Onion Powder /
Turmeric Powder, each with exact descriptor + `NET WT. 5 LB (2.27 kg)`); generic
`plain_rectangle`, `angled_product_face`, `card_banner_hero`,
`ui_screenshot_annotation`; styles `mogra_label_panel`, `mogra_text_only`,
`plain_ink`, `hero_card`, `ui_annotation`.

Any service reuses it with one call:
`mogra_mockup.build_mockup(product=..., container=..., source_image=..., out_path=...)`.

---

## Live validation (real runs, not mocks)

| Check | Result |
|-------|--------|
| `resolve_models()` | `comfy_up` + `gguf_node` true; clip/vae/t2i_unet/edit_unet resolved; `qwen_ready` + `qwen_edit_ready` true |
| Qwen-Image-2512 t2i, 896×1152, 20 steps | scene in **131.5 s** |
| Qwen-Image-Edit-2511 GGUF, 20 steps | first run FAILED on the truncated model (`cannot reshape … (18432,1728)`, 6.44 s); after full re-download → **edit executed in 203.0 s** |
| `POST /api/creative/mockup` (`generate=true`) | **HTTP 200 in 123.7 s** → 958,947-byte PNG + sidecar, lane `qwen-image-2512` |
| `GET /api/creative/health` `/presets` `/mogra-mockup` `/static/mockup.html` | all **200** |
| CLI composite smoke | `OK lane=composited_only` → real PNGs |
| Offline pytest | **38 passed** |

Artifacts under `generated_images/mogra_mockups/` (git-ignored):
`live_mockup_turmeric.png` (AI turmeric jar + exact text),
`live_mockup_turmeric_edited.png` (Edit-2511 refined + exact text),
`mogra_organic_black_peppercorns_*.png` (AI pouch + exact text),
`smoke_turmeric_jar.png`, `smoke_rect_peppercorns.png` (composite-only).

**Bug found and fixed this pass:** the first curvature implementation used a
`PIL Image.MESH` warp with the wrong source-quad order and smeared the label into
horizontal streaks. Replaced with a correct `asin`-based cylindrical
foreshortening (rows untouched → text stays sharp). A regression test now guards
that curvature does not destroy label content.

**Second bug found and fixed:** the pre-existing Edit-2511 GGUF was truncated and
failed to load (`cannot reshape array of size 24294816 into shape (18432,1728)`);
re-downloaded in full from `unsloth/Qwen-Image-Edit-2511-GGUF`.

**Third bug found and fixed:** `ComfyClient.wait_for` only returned on non-empty
`outputs`, so a failed ComfyUI run (empty outputs + `status_str == "error"`) hung
until the 900 s timeout instead of raising. It now detects `status_str == "error"`
immediately and surfaces the ComfyUI message.

After the fixes the full edit path was re-run live: Qwen-Image-Edit-2511 refined
the generated scene in **203.0 s**, then exact text was composited onto the edited
render in **4.5 s** → `generated_images/mogra_mockups/live_mockup_turmeric_edited.png`.

---

## Run instructions

```powershell
# 1. scene lane (ComfyUI)
cd C:\Users\T2Hol\ComfyUI
.\venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188

# 2. Northstar app (serves API + UI)
cd "C:\Users\T2Hol\Desktop\northstar-wt-mogra\Northstar_backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
#    open http://127.0.0.1:8000/mogra-mockup

# 3. CLI (no browser)
cd "C:\Users\T2Hol\Desktop\northstar-wt-mogra\Northstar_backend"
python -m creative.mogra_mockup --list
python -m creative.mogra_mockup --product organic_turmeric_powder `
  --container mogra_5lb_clear_handled_pet_jar --generate --out out.png

# 4. tests
python -m pytest ..\Northstar_backend\test_creative_mockup.py ..\Northstar_backend\test_creative_routes.py -q
```
(Full standard: `docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md`.)

---

## Blocker protocol / notes

* GGUF mirror repos (`QuantStack`, `city96`, …) intermittently return HF 401
  (rate-limit / not-found); the working source is `unsloth/Qwen-Image-Edit-2511-GGUF`.
* The official fp8mixed Edit-2511 (19 GB) is **not** appropriate on this 16 GB-RAM
  box; the 12.34 GB Q4_K_M GGUF is the correct lane. The loader auto-selects
  GGUF vs safetensors, so an fp8 upgrade is a one-file change if hardware changes.
* No credentials read/printed; no `.env` values touched; no paid API used.

---

## Guardrails honored

* Local-only, additive integration; no auth changes, migrations, or DB work.
* No push (local commits on a `feature/*` branch only).
* Real-money / purchase / listing paths untouched.
* Brand rules enforced in code (exact "Mogra Organics", "Fuel Your Focus.", no
  celestial mark, no invented seals/nutrition/UPC/lot/supplier/legal text).
