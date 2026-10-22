# Creative pipeline — real-test readiness

**Date:** 2026-10-22 · **Branch:** `feature/v4.1-mesh` · **Lane:** local · **Spend:** $0

Every lane was executed through the **service code**, not a hand-built ComfyUI graph.
The outputs below are real files on disk.

---

## Verdict

**Yes — ready for real testing, with one hard precondition: start ComfyUI with `--cache-none`.**

`tools/start_comfyui.ps1` now does that. Without it the edit lane kills the process (see §2).

| Lane | Live evidence | Verdict |
|---|---|---|
| **Image** — Flux.2 Klein 9B GGUF | `NS_CREATIVE_SMOKE.png` 1.45 MB, **73.3 s**, seed 4242 | **READY** |
| **Cutout** — BiRefNet | `NS_CREATIVE_CUTOUT.png` 1.65 MB RGBA, 694,883 transparent / 349,861 opaque px | **READY** |
| **Edit** — Qwen-Image-Edit 2511 | `NS_CREATIVE_EDIT.png` 1.03 MB, **163.6 s**, copy verdict `preserves_copy: true` | **READY** (needs `--cache-none`) |
| **Video** — Wan 2.2 TI2V 5B | `NS_CREATIVE_VIDEO.mp4` h264 832×480, **49 frames / 2.04 s**, 260 KB, 87.6 s | **READY** (draft quality) |
| **3D texturing** — UltraTex | `NS_UltraTex_Smoke_00001_.glb` 10.27 MB, valid glTF, 200 s | **READY** (bench only — non-commercial weights) |
| **Dieline / print** | `NS_SMOKE_DIELINE.svg` 2,801 B (`<svg`), `.pdf` 2,354 B (`%PDF-`) | **READY** |
| **Prepress** — littlecms | RSWOP.icm, max TAC **272.5 %** vs 300 % limit, 0 px over; gamut check real (dE76 in Lab) | **READY** |
| **OCR copy gate** — RapidOCR | `status ok, contains_text false, boxes 0` on the generated plate | **READY** |
| **Readiness verdict** | `blocked` on MAIN: background not white, fill unmeasurable without alpha | **WORKING AS DESIGNED** |
| **Vision** — qwen2.5vl:7b | 17.1 s, correct caption of a real Northstar plate | **READY** |
| **Compose / typography** | not re-run in this pass — needs a real plate + its quad/preset | **UNVERIFIED** |

The `blocked` readiness verdict is not a failure: the prompt asked for a *warm bone
backdrop*, so the plate is correctly not MAIN-compliant, and the copy gate correctly
found zero words. That is the guard doing its job.

Prepress raised a genuine observation about the generated plate: **6.28 % of pixels
move more than 8 dE** through RSWOP — the warm oranges sit near/outside the press
gamut. Real information, not a bug.

---

## Two defects found and fixed while testing

### 1. `unload_brain` evicted one hard-coded model and lied about the rest

The old code evicted `NORTHSTAR_BRAIN_MODEL` (default `northstaros-qwen3.8:27b`), then
checked only that id. The first render attempt failed with
`DefaultCPUAllocator: not enough memory` after `qwen2.5vl:7b` — loaded by the earlier
vision work — stayed resident holding **6.4 GB VRAM**, while `unload_brain` returned
`True`.

Now it drains Ollama's `/api/ps` list (chat *and* embedding models via
`/api/generate` or `/api/embeddings`), and only reports success when the list is empty.
`NORTHSTAR_BRAIN_MODEL` still pins to one id when an operator wants that.

```
resident before: ['qwen2.5vl:7b']
unload_brain: True
resident after: []
VRAM: 406 MiB
```

Four tests added (drain-all, stubborn-model → False, explicit pin, plus the existing
unreachable case). `test_studio_render_guard.py` → **7 passed**.

### 2. The edit lane exceeded the RAM ceiling

`qwen-image-edit-2511-Q4_K_M` is 12.3 GB and the `qwen_3_8b` text encoder is 8 GB.
ComfyUI caches both, so peak commit was ~20 GB against **15.4 GB RAM + 24 GB pagefile**
with other processes resident. The process was killed mid-render with no traceback —
the log simply stops.

`--cache-none` makes ComfyUI free the encoder before loading the unet: peak drops to
roughly the largest single model. After the flag, the edit lane completed in 163.6 s.

This box is **RAM-bound, not VRAM-bound**. That is the constraint to design around.

---

## What is still not proven

1. **Compose/typography on a real plate.** `mockup_compositor` was shipped and verified
   on 2026-10-16 (`reports/re_build_design_studio_20261016.md`), and one preset exists
   (`mogra-forest-dusk`), but I did not re-run it here. New plates need a quad pass.
2. **Quality.** Every lane was proven to *execute and produce a valid artifact*. Nobody
   has judged whether the image is good. That is the actual "real test".
3. **Video beyond a 2 s draft.** The `final` tier is 97 frames; no hero-length render
   was attempted.
4. **Print against a co-packer's die drawing.** The dieline engine produces valid output,
   but only their drawing is authoritative.

---

## The real test, when you want to run it

1. `powershell -File tools/start_comfyui.ps1`
2. Generate or pick a **real product plate** (known copy, known claims).
3. Cutout → compose/typography → `package_readiness.assess_package(artwork=…, dieline=…)`.
4. Expect `blocked` until: background is white or alpha is present, fill ≥ 85 %, and the
   copy the OCR gate finds matches the brief.

## Machine state after this pass

```
C: free            92 GB
RAM                15.4 GB (the binding constraint)
ComfyUI            0.40.0 on 8188, --cache-none, 1376 nodes
Ollama             idle (evicted) · 27B 16k on demand · qwen2.5vl:7b for vision
```
