# NorthstarOS Image / Text Workflow Standard

> Reusable path for **crisp product images** and **exact readable text on any
> generated image**. Built first for Mogra Organics packaging mockups; designed
> so any Northstar service (Creative Studio, marketing, comparison graphics,
> hero banners, UI annotations) can reuse the same two lanes.
> Status: implemented locally. Engine: `Northstar_backend/creative/`.

---

## 1. The rule (non-negotiable)

For any Northstar image that needs **exact brand names, buttons, labels, product
names, prices, weights, UI copy, packaging text, or readable words**:

1. **AI image model generates or edits the visual scene.**
2. **A deterministic compositor applies the final exact text.**
3. **The AI is never the source of truth for critical text.**

An image model may *suggest* a layout, but every glyph a customer reads is drawn
by a real font at a known position. This removes hallucinated brand names,
misspelled product copy, and garbled packaging text.

---

## 2. The standard pipeline

```
1. SCENE GENERATION      Qwen-Image-2512 (t2i)  /  Qwen-Image-Edit-2511 (edit)
2. TEXT-SAFE ZONE PREP   container/surface preset -> normalized 4-corner quad
3. EXACT TEXT MODE       deterministic compositor (Pillow) -> high-res PNG
4. (OPTIONAL) SURFACE    perspective warp onto quad + barrel curvature for jars
5. OUTPUT                flattened PNG  +  editable JSON sidecar (params/presets)
```

Each step is a module, usable independently or through the one-call pipeline.

| Step | Module | Function |
|------|--------|----------|
| 1. Scene generation | `creative.comfy_client` | `generate_scene`, `edit_scene` |
| 2. Zone prep | `creative.presets` | container/surface `quad_norm` + `curvature` |
| 3. Exact text | `creative.exact_text` | `compose_exact_text`, `render_label_layer` |
| 4. Surface warp | `creative.exact_text` | `warp_to_quad`, `quad_homography` |
| 5. Orchestration | `creative.mogra_mockup` | `build_mockup` (writes PNG + sidecar) |
| UI / API | `creative.routes` | `/api/creative/*`, `/mogra-mockup` |

---

## 3. Local model lane

Local ComfyUI (RTX 5080 16 GB, Blackwell — nvfp4 capable).

| Role | File | Location | Source |
|------|------|----------|--------|
| Scene t2i | `qwen-image-2512-Q4_K_M.gguf` | `models/unet/` | `unsloth/Qwen-Image-2512-GGUF` |
| Scene edit | `qwen-image-edit-2511-Q4_K_M.gguf` | `models/unet/` | `QuantStack`/`unsloth` Edit-2511 GGUF |
| Text encoder | `qwen_2.5_vl_7b_nvfp4.safetensors` | `models/text_encoders/` | `Comfy-Org/Qwen-Image_ComfyUI` |
| VAE | `qwen_image_vae.safetensors` | `models/vae/` | `Comfy-Org/Qwen-Image_ComfyUI` |
| GGUF loader | `ComfyUI-GGUF` custom node | `custom_nodes/` | provides `UnetLoaderGGUF` |
| Fallback t2i | `flux1-dev-fp8.safetensors` | `models/unet/` | already present |

Workflows mirror ComfyUI's own Qwen blueprints (`Image Edit (Qwen 2511).json`,
`Text to Image (Qwen-Image 2512).json`) node-for-node, swapping `UNETLoader`
for `UnetLoaderGGUF` so the quantized weights load. `ModelSamplingAuraFlow`
shift `3.1`; t2i latent is `EmptySD3LatentImage`; edit uses
`TextEncodeQwenImageEditPlus` + `FluxKontextImageScale`.

Model routing policy:
* **DeepSeek V4.1 Max** — initial repo-aware implementation and hard debugging.
* **DeepSeek V4.1 Flash** — routine follow-up coding and fixes.
* Large reasoning loops are **not** used for repetitive mockup generations.

Check the lane any time:

```powershell
python -c "from creative.comfy_client import resolve_models; import json; print(json.dumps(resolve_models(), indent=2))"
# or, with the app running:
curl http://127.0.0.1:8000/api/creative/health
```

---

## 4. Exact-text mode

`creative.exact_text` renders a `LabelSpec` (brand, tagline, product name,
descriptor, net weight, optional ingredients placeholder, optional rear-label
placeholders, extra lines) into an RGBA layer, then warps it onto a **rectangle
or 4-corner quad** and alpha-composites it onto the scene.

* **Deterministic & offline.** Same inputs → same pixels. No model, no network.
* **Crisp by construction.** Rendered at 2× supersample, warped with bicubic
  resampling, so text stays sharp through perspective.
* **Brand guard.** `check_brand_content` refuses tokens that would fabricate
  compliance content (USDA seals, Nutrition Facts, UPC, lot codes, supplier /
  legal statements) in Mogra brand mode. It fails loudly rather than inventing.
* **Reusable surfaces.** Same compositor serves plain rectangles, angled product
  faces, card/banner/hero overlays, and UI screenshot annotations.

Brand rules encoded: brand is always **`Mogra Organics`**; default tagline is
**`Fuel Your Focus.`**; no sun/sunrise/sunburst/celestial mark; premium polished
realism; no invented seals, nutrition facts, UPCs, lot codes, supplier names, or
legal claims.

---

## 5. Presets

All in `creative.presets` (single source of truth; loaded by the UI and API).

**Containers:** `mogra_5lb_clear_handled_pet_jar`, `mogra_32oz_standup_pouch`,
`mogra_4oz_window_pouch`.

**Products:**
* Organic Black Peppercorns — Whole • Aromatic • Bold — `NET WT. 5 LB (2.27 kg)`
* Organic White Onion Powder — Smooth • Savory • Versatile — `NET WT. 5 LB (2.27 kg)`
* Organic Turmeric Powder — Earthy • Golden • Vibrant — `NET WT. 5 LB (2.27 kg)`

**Generic surface zones (any Northstar service):** `plain_rectangle`,
`angled_product_face`, `card_banner_hero`, `ui_screenshot_annotation`.

**Styles:** `mogra_label_panel`, `mogra_text_only`, `plain_ink`, `hero_card`,
`ui_annotation`.

Coordinates are normalized `[x, y]` in reading order
(`ul → ur → lr → ll`, `0..1`), so presets are resolution-independent. A quad or
curvature can always be overridden per request.

---

## 6. Launch locally

**One-time (already done on this box):** the model files above are in place.
ComfyUI lives at `C:\Users\T2Hol\ComfyUI`.

**Start the scene lane (ComfyUI):**

```powershell
cd C:\Users\T2Hol\ComfyUI
.\venv\Scripts\python.exe main.py --listen 127.0.0.1 --port 8188
```

**Start the Northstar app (serves the UI + API):**

```powershell
cd "C:\Users\T2Hol\Desktop\northstar-wt-mogra\Northstar_backend"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000/mogra-mockup** → upload or generate a base scene,
pick presets, edit the text, press **Generate Final Mockup**.

**CLI (no browser):**

```powershell
# list presets
python -m creative.mogra_mockup --list

# full pipeline: generate the scene, then stamp exact text
python -m creative.mogra_mockup --product organic_turmeric_powder `
  --container mogra_5lb_clear_handled_pet_jar --generate --out out.png

# composite exact text onto your own base image
python -m creative.mogra_mockup --product organic_black_peppercorns `
  --surface plain_rectangle --source base.png --out tagged.png
```
Run the CLI with `Northstar_backend` on the path
(`cd Northstar_backend` first, or `python -m creative.mogra_mockup ...` from there).

**API:** `GET /api/creative/presets`, `GET /api/creative/health`,
`POST /api/creative/compose`, `POST /api/creative/generate-scene`,
`POST /api/creative/mockup`, `GET /api/creative/file/{name}`.

---

## 7. Reuse by any Northstar service

A service needs only two things:

```python
from creative import mogra_mockup

result = mogra_mockup.build_mockup(
    product="organic_turmeric_powder",          # or a plain dict of fields
    container="mogra_5lb_clear_handled_pet_jar", # optional; or surface_key=...
    source_image="render.png",                    # or generate=True
    out_path="final.png",
)
# -> {"output": "...png", "sidecar": "...json", "lane": "...", "params": {...}}
```

For a non-Mogra brand, pass `brand` / `tagline` / `product_name` overrides and
set `enforce_brand=False` to skip the Mogra compliance guard. Every output
carries a JSON sidecar with the exact quad, curvature, style and text used, so a
service can re-render deterministically.

---

## 8. Validation evidence (live, this pass)

Machine: RTX 5080 Laptop 16 GB VRAM, 16 GB RAM, Python 3.14, Pillow 12.3.

| Check | Result |
|-------|--------|
| `resolve_models()` against live ComfyUI | `comfy_up` + `gguf_node` true; clip, vae, t2i_unet, edit_unet all resolved; `qwen_ready` + `qwen_edit_ready` true |
| Qwen-Image-2512 t2i, 896×1152, 20 steps | scene generated in **131.5 s** |
| Qwen-Image-Edit-2511 (GGUF), 20 steps | edit executed in **203.0 s** (after re-downloading the truncated model) |
| `POST /api/creative/mockup` (`generate=true`) | **HTTP 200 in 123.7 s** → 958,947-byte PNG + JSON sidecar, lane `qwen-image-2512` |
| `GET /api/creative/health`, `/presets`, `/mogra-mockup` | all **200** |
| Offline tests | **38 passed** (`test_creative_mockup.py` + `test_creative_routes.py`) |
| Exact-text composite speed | ~4 s per 896×1152 image (deterministic) |

Sample outputs (git-ignored, regenerable) under `generated_images/mogra_mockups/`:
`live_mockup_turmeric.png` and `mogra_organic_black_peppercorns_*.png` (AI scene +
exact text), `live_mockup_turmeric_edited.png` (Edit-2511 refined + exact text),
plus `smoke_turmeric_jar.png` / `smoke_rect_peppercorns.png` (composite-only).

**Edit model note:** the pre-existing `qwen-image-edit-2511-Q4_K_M.gguf` was a
**truncated 3.16 GB download** (a 20B Q4_K_M is ~12.34 GB) and failed to load with
`cannot reshape array of size 24294816 into shape (18432,1728)`. It was retired to
`*.gguf.truncated` and re-downloaded in full from `unsloth/Qwen-Image-Edit-2511-GGUF`.

**Hardware note:** the official fp8mixed Edit-2511 safetensors is ~19 GB; on a
16 GB-RAM box the 12.34 GB Q4_K_M GGUF is the correct lane. The loader
auto-selects GGUF vs safetensors by file extension, so an fp8 upgrade is a
one-file change.

---

## 9. Known limitations / next steps

* Generation speed depends on the local GPU; the Q4_K_M lanes are chosen for a
  16 GB card. Very large source images are downscaled by `FluxKontextImageScale`
  before editing.
* Curvature is a single-parameter barrel approximation, not a true cylindrical
  unwrap. It reads well on jars; a mesh unwrap is a future upgrade.
* Fonts come from the OS (`C:\Windows\Fonts`) with a deterministic default
  fallback. Bundle brand fonts before shipping exact brand typography.
* Not wired into the React Creative Studio room yet — the standalone
  `/mogra-mockup` page and the API are the integration surface. The foundation
  router is intentionally untouched.
* No certification seals / nutrition panels / UPCs by design; the compositor
  refuses them.
