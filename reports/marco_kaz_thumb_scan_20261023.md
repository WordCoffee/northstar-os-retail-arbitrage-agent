# Marco Kaz — thumbnail scan (2026-10-23)

**Correction to the 2026-10-22 pass.** The caption-only sweep found 2 usable repos because his
captions are empty and he speaks generic descriptions ("this tool", "someone built"). The
thumbnails carry the actual `github.com/owner/repo` URL as burned-in text. OCR over the
thumbnails recovers them.

## 1. Method

| Step | Result |
|---|---|
| Thumbnails downloaded | **265** (`i.ytimg.com/vi/<id>/oar2.jpg`, vertical 1080×1920) |
| OCR | **265/265**, `rapidocr_onnxruntime`, fully offline |
| owner/repo-shaped strings after filtering | **~180** (many are OCR noise: prices, "requests/month", file paths) |
| Hand-curated real repositories | **~60** |
| Metadata-verified through GitHub API (stars / SPDX / last push) | **29** |
| Visually spot-checked against the image itself | 4 (`skylos`, `open-design`, `laya`, `text-to-cad`) |

Spot-checks matched the OCR exactly, including the URL path.

## 2. Scorecard against my first list

| | Caption pass (10-22) | Thumbnail pass (10-23) |
|---|---|---|
| Real repos found | 12 | ~60 |
| Still recommended after verification | 1 (`headroomlabs-ai/headroom` — its thumbnail has no URL, so the two passes are complementary) | 10 |
| Wrong identification | `2akouwu/reverify` labelled as the "deterministic checkpoint" | Actual repo is `duriantaco/skylos` (same author as `ravage`) |

The caption method could only ever find tools whose names are spoken. `text-to-cad`,
`open-design`, `laya`, `claude-mem`, `turbovec`, `SkillOpt`, `Sana`, `img2threejs` and `surya`
are never named out loud — they exist only in the thumbnail URL. That is the structural blind
spot, and it is the operator's point.

## 3. Top 10 that actually move Northstar

Verified 2026-10-23 via `api.github.com`. Sorted by gap closed, not by stars.

| # | Repo | ★ | Licence | Lane | The Northstar gap it closes |
|---|---|---:|---|---|---|
| 1 | `earthtojake/text-to-cad` | 22,588 | MIT | cloud OK | **Packaging becomes CAD.** Agent emits STEP assemblies and validates mechanisms. Dielines, pouch geometry and cartons stop being 2D fitting heuristics |
| 2 | `nexu-io/open-design` | 103,408 | Apache-2.0 | cloud OK | **Design studio instead of hand-built UI.** Local-first workspace that turns an existing agent into a designer; 0.13.0 explicitly resumes Codex / **OpenCode** / Pi runs and exports PPTX/PDF |
| 3 | `NandhaKishorM/laya` | 34,006 | Apache-2.0 | cloud OK | **The Jev answer, local and free.** 421M non-autoregressive System-1 engine, typed choice/score/yes-no, 9.1 ms p50 vs 278 ms API round-trip on the same benchmark. No spend, no tenant data leaving the box |
| 4 | `thedotmack/claude-mem` | 102,358 | Apache-2.0 | cloud OK | **Session continuity.** Captures everything an agent does and replays the relevant slice next session — the memory-bank gap |
| 5 | `RyanCodrai/turbovec` | 17,412 | MIT | cloud OK | **Knowledge plane at scale.** Rust vector index on TurboQuant with Python bindings — local retrieval without a cloud vector DB |
| 6 | `microsoft/SkillOpt` | 18,638 | MIT | cloud OK | **Self-evolving skills, with evaluation.** Text-space optimizer that trains reusable natural-language skills instead of hand-tuning prompts — exactly the deferred D2 direction |
| 7 | `NVlabs/Sana` | 9,606 | Apache-2.0 | cloud OK | **Cheap high-res generation.** Linear-diffusion transformer built for high-resolution synthesis at far lower compute than Flux-class stacks |
| 8 | `img2threejs/img2threejs` | 18,920 | Apache-2.0 | cloud OK | **Photo → procedural 3D object**, quality-gated. Product 3D and mockup geometry from a single reference image |
| 9 | `datalab-to/surya` | 21,519 | Apache-2.0 | cloud OK | **Supplier paperwork becomes data.** OCR + layout + reading order + tables in 90+ languages: spec sheets, labels, dieline PDFs |
| 10 | `duriantaco/skylos` | 848 | Apache-2.0 | cloud OK | **The build loop's evidence gate.** Local PR scanner for dead code, secrets, security and quality — pass/fail/incomplete instead of trusting the model |

## 4. Runner-ups worth knowing

| Repo | ★ | Why it is not top 10 |
|---|---:|---|
| `AlexsJones/llmfit` | 38,271 | Tells you what runs on the 3080 before downloading 8 GB — genuinely useful, but a utility, not a capability |
| `Adam-CAD/CADAM` | 5,318 | Same job as #1 but **GPL-3.0** → local lane only |
| `HKUDS/ViMax` | 12,732 | Agentic video (director/screenwriter/producer); marketing clips, not the core |
| `context-labs/HALO` | 1,194 | Hierarchical agent-loop optimizer; overlaps SkillOpt with fewer stars |
| `openclaw/openclaw` | 392,801 | Enormous harness, but we already run OpenCode; adopting a second runtime is the OpenDots problem again |
| `rowboatlabs/rowboat` | 18,055 | Local AI coworker; same category |
| `playcanvas/supersplat` | 10,449 | 3DGS editor; needs a capture pipeline we do not have |
| `jetify-com/devbox` | — | Reproducible dev envs; infrastructure, not product |

## 5. Still rejected

| Repo | Reason |
|---|---|
| `Panniantong/Agent-Reach` (101k) | Scrapes Twitter/Reddit/YouTube — ToS and the read-only Chrome Connect rule |
| `lightpanda-io/browser` (36.9k) | AGPL + a second browser path around the controller |
| `pinchtab/pinchtab` | Stealth injection; bot-detection evasion |
| `bytedance/UI-TARS` (39.4k) | GUI/browser control outside Chrome Connect |
| `duriantaco/ravage`, `PurpleAILAB/Decepticon` | Offensive-security tooling |
| `onyx-dot-app/onyx`, `sandbox-quantum/switch` | `NOASSERTION` licence, and both duplicate what we own |
| `elder-/plinius` | Censorship-removal tooling; no product fit |

## 6. Recommended order of work

1. **`text-to-cad` on a real dieline** — take one pouch the operator already renders, ask for a
   STEP assembly with the measured face, and compare it to the current geometric fit. This is
   the only item that changes what Northstar can physically deliver.
2. **`laya` as the decision layer** — the exact role Jev was proposed for, but local: route
   Simple/Pro, dedupe listings, flag compliance. Measure against 100 hand-labelled cases.
3. **`skylos` in the continuous loop** — run it on one card's diff; require `pass` before DONE.
4. Then `open-design` (biggest UI surface, needs a design decision from the operator) and
   `claude-mem` + `turbovec` (memory plane, needs a schema decision).

## 7. Artifacts

- `research/marco_kaz_20261022/ocr_thumbs.py` — offline thumbnail OCR + URL extractor
- `research/marco_kaz_20261022/thumbs_ocr.csv` — 265 rows of raw OCR text
- `research/marco_kaz_20261022/thumbs_gh.csv` — every extracted owner/repo with video id
- `thumbs/` git-ignored (40.7 MB, reproducible from the video ids)
