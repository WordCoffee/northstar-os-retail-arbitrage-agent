# PLAN — Northstar OS "Packify-grade" quality program (2026-10-16)

Built from: `REPORT.md` + `COMPOSITOR_REALISM_AND_PACKIFY.md` (9-step upgrade
path) + `TOOLCHAIN_GENERATION.md` (verified stack picks) + the prior teardown
(`reports/competitor_re_packify_dyp_20261016.md`, §7 build plan). Everything
runs locally; marginal cost $0; all model picks commercial-safe.

Guiding rule: **generation for surfaces, deterministic code for truth.**
Diffusion never owns typography or label geometry; the compositor never
pretends to be a camera. Harmonization passes glue them.

---

## P0 — Compositor realism v2 (hours, immediate; kills the "AI-like" look)

Fix for the operator's own complaint on `renders/mogra-forest-dusk-mockup-complete.png`.

1. **Luminance displacement inside `warp_panel()`** — sample the panel at
   `(u + k·D, v + k·D)` where `D` = blurred face luminance minus local mean;
   start max shift 0.02 × face width. (The core "printed on fabric" mechanism.)
2. **Print-grain sync** — multiply the panel by high-pass grain measured from
   the plate (reuse `grain_patch`); soften ink alpha by ~0.4 px (print scale).
3. **Lighting upgrade** — replace the 0.55 global multiply with Soft-Light at
   ~0.9 inside the panel mask + a capped specular screen pass (sheen over ink).
4. **Print-edge grounding** — 2–4 px inner AO rim (3–6%) + 1–2 px faint seam
   outside the print; drop the old disc "sticker shadows".
   Deliverable: `--debug` A/B strip (current / +1–2 / +1–4) + updated sidecar.
   Accept: at 100% zoom the print follows folds, no sticker read, no text wobble.

## P1 — Generation lane upgrades (1–2 weeks)

1. **Install + wire Qwen-Image-Edit-2511** (int8/Nunchaku 4-bit; native
   ComfyUI template) as the edit/refine lane; keep klein 4B for fresh art.
2. **LayerStyle nodes** for any text touched inside ComfyUI; otherwise our
   deterministic text layer stays the law.
3. **OCR-QC gate** — extend existing `text_fidelity.py`: every generation run
   that is expected to carry copy must pass OCR-diff vs intended strings
   (PaddleOCR/RapidOCR both available); failures auto-recompose, never ship.
4. **Matting + cutout lane** — BiRefNet via ComfyUI-RMBG (never RMBG-2.0);
   enables scene compositing and product cutouts.
5. **Upscale wiring** — SeedVR2 endpoint (upscale before final text composite).
6. Model-policy audit: refuse-list (Qwen-Image-2.1, FLUX.2-dev, klein 9B,
   RMBG-2.0, MatAnyone, Sapiens2) enforced in the engine config.

## P2 — Product surface system (2–3 weeks)

1. **Auto-placement** — replace hand-measured `FACES` quads: label-area
   segmentation (Grounded-SAM-2 / SAM2 "segment the label area") + corner
   refine; fallback stays manual quads.
2. **TPS crease refinement + pseudo-normals** (compositor steps 5–6): fit
   SciPy `RBFInterpolator(kernel='thin_plate_spline')` control points along
   detected creases; fold-shadow pass over the print.
3. **Depth pass (optional offline)** — Depth Anything V2-**Small**
   (Apache-2.0 weights only) cached per plate for conformal warp + Lambert +
   specular; mirrors Packify's `depthData`/`lumin_url` vocabulary.
4. **Print-process knobs** (compositor step 8) — ink show-through on dark film,
   sub-pixel dot gain, gamut guard for gold/cream; flags + sidecar evidence.
5. **Scene compositor with Packify-parity contract** — implement the *proven*
   photoshoot model (rectangle place: crop/scale/rotate/center-x/y) for our
   public API lane + a prompt-assembled background lane `[SCENE]/[PRODUCT]`
   (DYP's convention, reused openly); scene × product template gallery on the
   existing canvas compositor.

## P3 — The moat pieces (3–6 weeks; from prior teardown §7.2)

1. **Chat → layered design agent** (AutothinK → design-studio jobs; pause /
   regenerate-layer / retry; per-layer artifacts).
2. **Layered editable dieline generation** — parametric SVG generators + canvas
   editor (fabric.js) + PDF/ZIP export (reportlab/svglib); preview-cheap /
   full-expensive metering — the trick Packify sells at ~100 credits.
3. **Metered public API + webhooks** with compliance-evidence payloads.
4. **REA confirmation runs** (runbook `REA_RUNBOOK.md`), only for the three
   remaining inference-level pieces: photoshoot `extracted_coordinates` payload
   · mockup `lumin/depth/UV` formats · deep-agents event grammar. Operator
   present; passive only; circuit breaker on.
   Accept: ≥1 captured payload per piece; findings folded back here; build the
   mirror from evidence, not guesswork.

## P4 — Print & craft lane (ongoing)

1. vtracer vectorize → resvg raster at DPI → `ImageCms` soft-proof (ECI ISO
   Coated v2 300%) → Ghostscript CMYK PDF; Scribus for PDF/X checks.
2. Dielines: PackBox Studio (MIT) + boxes.py ideas (GPL — patterns only).
3. **Brand LoRA** — ai-toolkit on klein-base-4B (512–768 px, batch 1, 16 GB
   practical); train on our approved packaging style set; ship the Apache
   artifact; document dataset provenance (we own the renders).

---

## What we clone vs what we build (final)

| Piece | Source | How |
|---|---|---|
| Photoshoot rectangle-placement contract | Packify public docs (proven) | Implement equivalent (our API lane); no REA needed |
| Mockup lumin/depth/UV composite semantics | Packify bundle (inferred) | REA confirm → mirror with §P2 stack |
| Layered/pausable agent generation | Packify bundle (proven vocabulary) | Build from our AutothinK + jobs (no REA needed) |
| Realism passes (displace/blend/spec/grain/AO) | Industry canon + 15+ OSS refs | Implement in `compose_mogra_complete.py` v2 |
| Qwen-Edit / BiRefNet / LayerStyle / vtracer / ai-toolkit | OSS (license-checked) | Install + wire |
| Dielines, D3D | PackBox/boxes.py; BlenderProc (future) | OSS adopt |

## Evidence discipline

Every phase ships: code + `--debug` A/B artifacts + sidecar JSONs +
OCR/compliance gates where copy is involved + a short report under `reports/`.
No phase is "done" on vibes — the acceptance criterion is a side-by-side the
operator can judge at 100%.
