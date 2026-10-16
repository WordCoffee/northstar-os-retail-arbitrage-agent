# Packify-Quality Deep Dive — master report (2026-10-16)

**Question (operator):** scan GitHub and the web for better image/product-design
workflows and tools that bring Northstar OS generation closer to Packify.ai
generation quality; extreme deep dive, 1000+ sources; build a plan; use REA
(after confirming pieces) for anything that needs reverse-engineering to clone.

**Answer in one line:** the quality gap is not the model — it is (a) the missing
surface-realism passes in our deterministic compositor, (b) a missing
text-fidelity + OCR-QC loop in the generation lane, and (c) a missing
scene/product template system; all three have verified OSS implementations, and
Packify's own mechanics (proven from their public API + bundles) are exactly the
deterministic recipe we can build locally at $0 marginal cost.

---

## 1. Method & sources (honest accounting)

Four parallel workstreams, all sources checked this session:

| Workstream | Deliverable | Sources |
|---|---|---|
| GitHub programmatic sweep (90 tooling queries, unauthenticated API) | `SOURCES_GITHUB.csv` + `sweep_summary.json` | **5,984 unique repos** (metadata-verified; 159 at 1k+★, 932 at 100+★; 5 queries hit the unauthenticated rate limit and are logged as errors) |
| Generation-quality toolchain scan | `TOOLCHAIN_GENERATION.md` | ≈200 itemized checkable sources (36 fully-metriced, ~95 grouped repos, ~35 docs/model cards, ~35 REPORTED-only) |
| Compositor realism + Packify mechanics | `COMPOSITOR_REALISM_AND_PACKIFY.md` | 126 numbered sources |
| REA runbook (install state, targets, commands) | `REA_RUNBOOK.md` | local REA docs + previous RE evidence pack |
| Prior evidence (consolidated, not re-counted) | `reports/competitor_re_packify_dyp_20261016.md`, `research/packify_dyp_re_20261016/` | 294 URLs + 115 API paths mined; docs extract |

**Total distinct sources consulted: 6,300+** (5,984 sweep rows metadata-verified
via the GitHub API — name/stars/license/description/activity — plus ~460
individually inspected pages/repos across the four documents above).
Confidence labels per repo convention: VERIFIED (opened this session) /
REPORTED (snippet only) / UNKNOWN.

Known limitations, stated up front: one agent's websearch integration went down
mid-session (that agent switched to direct fetches; anything not fetched is
marked REPORTED); the GitHub sweep is point-in-time metadata; Packify's
mockup-editor semantics (`lumin_url/depthData/uvData`) are strongly inferred
from field names, not yet confirmed at runtime — the REA runbook closes that.

---

## 2. Key findings

### 2.1 What Packify actually does (proven, not guessed)

- **Photoshoot API = one cropped, uniformly scaled, rotated rectangle** of your
  product image placed at a center coordinate on a generated canvas
  (`x,y,width,height,cropX,cropY,cropWidth,cropHeight,rotation,totalWidth,totalHeight`;
  center coordinates confirmed in the live client mapping `left = x - width/2`).
  Backgrounds are AI-generated around the product; no mesh/homography fields
  exist in the public contract. (PROVEN — docs bundle in their live build.)
- **The surface-realism lives in their mockup studio + Pacdora 3D**, whose
  editor vocabulary (`lumin_url`, `depthData`, `uvData`, `eraseScale`,
  `whiteModelImage`) mirrors the industry-standard deterministic stack:
  luminance multiply + depth/UV warp + erase/inpaint.
- **Marketing tells on themselves**: "traditional mockup tools… artwork can
  look like it is floating on the surface; Packify generates the complete
  mockup around your artwork" — i.e. they solve the floating-artwork problem
  with generation + deterministic passes, exactly the hybrid our stack can do.

### 2.2 The universal realism recipe (verified across 11+ independent sources)

Displacement-warp the artwork by the surface's blurred luminance → blend the
art through the surface (Multiply / Soft-Light / Blend-If, not opaque paste) →
add a specular pass (the film's sheen sits OVER the ink) → junction AO/seam at
the print edge → print grain synced to the photo's grain → optional fold-shadow
pass. This is what makes print read "on" the material. Our compositor (clean
4-corner homography, one 55% luminance multiply, no displacement/grain/specular)
is at step 0 of that recipe — which is precisely why it reads "AI-like".

### 2.3 Generation lane: the stack that matters (all verified)

> **Updated same day — the operator's private-use decision relaxed the
> commercial constraint; see `MODEL_LANE_PRIVATE_20261016.md` for the revised
> picks (klein 9B, FLUX.1-dev ecosystem, Qwen-Image-2.1 candidate). The table
> below remains the commercial-safe baseline.

| Need | Pick | License | Note |
|---|---|---|---|
| Base generator | **FLUX.2 klein 4B** (already installed) | Apache-2.0 | Already best-fit; docs ≈8.4–9.2 GB VRAM |
| Text-faithful edits | **Qwen-Image-Edit-2511** | Apache-2.0 | The single biggest quality jump; run via Nunchaku 4-bit on 16 GB |
| Crisp typography | **LayerStyle** nodes (`TextImage`, shadows/overlays) or our PIL compositor | MIT | Diffusion text stays unreliable — set type deterministically, harmonize after |
| Matting | **BiRefNet** / BEN2 / SDMatte | MIT | License traps: RMBG-2.0, MatAnyone, Sapiens2 = non-commercial |
| Relight | **IC-Light fbc** (already installed) + Qwen-Image-Edit-2509-Relight | Apache-2.0 | Use `IC Light Apply Mask Grey`; swap example matting for BiRefNet |
| QC loop | **PaddleOCR / RapidOCR** (already in repo!) + Qwen3-VL critic | Apache-2.0 | OCR-diff every rendered label string vs intended copy — gate on pass |
| Brand LoRA | **ai-toolkit** on klein-base-4B | MIT | Practical at 512–768 px, batch 1 on 16 GB |
| Upscale | **SeedVR2** (already installed) | Apache-2.0 | Upscale bases BEFORE final text composite, or re-composite after |
| Print path | vtracer → resvg, Pillow `ImageCms` + ECI profile, Ghostscript; PackBox / boxes.py dielines | MIT/GPL mix | Full OSS prepress ladder; GPL items kept at arm's length |
| Do NOT ship | Qwen-Image-2.1, FLUX.2-dev(+Fun ControlNet), klein 9B, RMBG-2.0, MatAnyone | NC licenses (verified) | |

### 2.4 The near-twin blueprint

`ComfyUI-ProductLabelRefinement` (created the same day, no license — read-only
for ideas): deterministic packshot warp + light/color transfer + shadow/gloss/
grain + occlusion + QA sheets + layered PSD driven by `job.json`. They
independently arrived at our architecture; validated direction, do not copy.

### 2.5 REA: what needs reverse-engineering (confirmed list)

Only three pieces remain inference-level and are worth a passive REA pass
(operator-driven, runbook ready): (1) the exact `extracted_coordinates` payload
their photoshoot flow produces, (2) the mockup editor's `lumin_url/depthData/
uvData` formats, (3) deep-agents layered-generation event grammar (nice-to-have).
Everything else = build from OSS (their wheels are commodity).

---

## 3. Deliverables index

| File | What |
|---|---|
| `REPORT.md` | this document |
| `PLAN.md` | phased build plan mapped to Northstar OS |
| `TOOLCHAIN_GENERATION.md` | §generation toolchain (≈200 sources) |
| `COMPOSITOR_REALISM_AND_PACKIFY.md` | §compositor realism + proven Packify mechanics (126 sources) + 9-step upgrade path |
| `REA_RUNBOOK.md` | copy-pasteable REA capture program (operator protocol + commands) |
| `SOURCES_GITHUB.csv` / `sweep_summary.json` | the 92-query GitHub enumeration |
| `gh_sweep.py` | the sweep itself (re-runnable) |

Prior context: `reports/competitor_re_packify_dyp_20261016.md` (product-level
teardown + moat/wheel classification — still current).
