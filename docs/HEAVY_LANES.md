# Heavy V3 lanes — readiness and validation hooks

Generated status: `reports/heavy_lanes_readiness_20261105.json`
(`python tools/heavy_lane_check.py`). The check is read-only; it never imports
the heavy stack or installs anything.

| Lane | Status | Blocker |
|---|---|---|
| B2 layout OCR | **blocked** — `docling`, `paddleocr` not installed | install in a staging venv; compare against RapidOCR before wiring |
| B3 IC-Light relight | **ready for validation** | node + SD15 base present; needs a 10-scene run |
| B4 TRELLIS / InstantMesh | **blocked** — weights absent | download one permissive checkpoint (TRELLIS MIT / InstantMesh Apache-2.0) |
| Video A14B 30 s | **blocked** — weights staged in `_incoming`, not in ComfyUI; no A14B graph | copy both experts, add the two-expert graph, validate a 5 s clip first |

## B2 — layout/table OCR

```powershell
python -m venv .venv-docling
.\.venv-docling\Scripts\python -m pip install -U pip
.\.venv-docling\Scripts\pip install docling paddleocr
python tools\heavy_lane_check.py
```

Do **not** install this into the service venv first: Docling pulls `rapidocr 3.10`,
OpenCV and a Hugging Face hub upgrade, which can change the live OCR path. Validate
layout/reading-order on 20 label/table images in the staging venv, then wire it as
an optional child process like the image scorers.

**Validation hook:** `state/probes/t11_mockup_legibility.py` must stay green; add a
20-image table/label comparison and require ≥90% region IoU before default-on.

## B3 — IC-Light relighting

```powershell
# node is present: ComfyUI/custom_nodes/ComfyUI-IC-Light-Native
# base checkpoint must be the SD15-class file checked by heavy_lane_check
python tools\heavy_lane_check.py
```

Run after a FLUX render, never beside it (16 GB VRAM, one heavy model at a time).
Validate 10 scenes × 2 light directions: identity pHash/SSIM, legibility, preference
floor, VRAM peak < 15 GB. Use `ship_gate` with the reference photo.

## B4 — image-to-mesh

TRELLIS is MIT; InstantMesh is Apache-2.0. Do not install Hunyuan3D (Tencent
licence, not eligible). Download one checkpoint, run 256³ marching cubes, export
OBJ/GLB, and require `geometry_handoff` manifold/bbox checks. A mesh is a
candidate, not a print asset.

## Video A14B 30 s

The two Q4_K_M experts are staged at
`ComfyUI/models/_incoming/QuantStack__Wan2.2-I2V-A14B-GGUF/{HighNoise,LowNoise}`.
They are **not** in `ComfyUI/models/diffusion_models`, and `shorts.py` still builds
the 5B graph. Before any 30 s claim:

1. copy both experts into `ComfyUI/models/diffusion_models` (18 GB; disk floor 10 GB);
2. add a two-expert graph (high-noise → low-noise switch) and validate a 5 s clip;
3. run the 30 s chain (12 × 77-frame clips), then captions/audio;
4. verify ffprobe duration, OCR captions, −16 LUFS, and the guardrail audit log.

The existing 15 s master is 5B and silent by construction; it is not evidence for
A14B or audio synchronisation.

## Validation hooks already installed

* `tools/v3_graduation.py` — Stage 1 AST/tests, Stage 2 Ty's Vision, Stage 3 E2E.
* `tools/heavy_lane_check.py` — this readiness report.
* `state/probes/` — t10/t11/t12 image/dieline contracts, t21/t22 ship gate/scorers.
* `reports/v3_graduation_memory_20261105.json` — the first module to pass all three.
