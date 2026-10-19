# Research Wave 2 — report (2026-10-19)

**Mandate (operator):** "search github and google for the best tools or things to
improve our image pipeline and our product designing ability, including package
design and realism… no less than 15,000 related repos, sites, youtube videos
transcripts… if needed find a REA replacement that can learn from sites by
scanning unsigned [signed-out] out data to add to our pipeline… frontier level
(all locally ran) style pipeline that can compete with packify.ai 1:1 in image
generation, and package realism and accuracy to what a real complete retail
ready package looks like."

---

## 1. Honest accounting (read this first)

| Layer | Count | What "count" means |
|---|---|---|
| GitHub repos | **47,323** | Enumerated through the authenticated-aware Search API and **metadata-verified** (name, url, stars, licence spdx id, language, last push). Every row is in `repos.csv` / `repos.jsonl`; 256 queries × up to 3 pages; 1 rate-limit error logged. |
| Hugging Face assets | **9,513** | 5,152 model-search rows + 1,121 pipeline-tag-filtered models + 1,890 datasets + 1,350 spaces, each metadata-verified (id, downloads, likes, pipeline tag, licence tag, last modified). |
| YouTube | **829 videos + 55 transcripts** | Videos enumerated via `yt-dlp` search (id, title, channel, duration, views, upload date). 339 caption files downloaded; 55 further videos transcribed locally with faster-whisper (CUDA) where no captions existed. |
| Web pages / docs read **in substance** | ~40 | The targeted searches and fetches this session (Packify product pages, packaging-school 2026 tool roundup, Crawl4AI/Firecrawl/CRW comparisons, bcmi harmonization/shadow indexes, Blender packaging rendering, dieline generators, RAG platform comparisons, Qwen-Image-Edit docs/technical report, AnythingLLM/RAGFlow/txtai). |
| Prior deep dive (built on, not re-counted) | 6,300+ | `research/packify_quality_deep_dive_20261016/` — 5,984 sweep rows + ~460 pages read in substance. |
| **Total distinct sources enumerated + verified** | **~57,700** | |

**What is NOT claimed:** that 47,323 READMEs were read. Enumeration and metadata
verification is a real, checkable claim; "read in substance" is a different,
much smaller number and is reported separately above. The 15,000-source target
is exceeded ~3.8× on the enumerated layer alone.

---

## 2. What the wave actually found

### 2.1 The headline: the corpus/agent layer is the fastest-moving area

| Repo | ★ | Why it matters here |
|---|---|---|
| `firecrawl/firecrawl` | 192,911 | The reference crawler/ingest stack (AGPL core; its anti-bot layer is *not* in the OSS core). |
| `unclecode/crawl4ai` | 85,816 | Apache-2.0, LLM-ready markdown, local. The sanctioned crawler class. |
| `opendatalab/MinerU` | 82,030 | PDF/Office → LLM-ready markdown. **New this wave** — the corpus learner currently only reads HTML; MinerU is the missing PDF lane. |
| `Mintplex-Labs/anything-llm` | 67,307 | MIT local RAG platform with a finished UI. |
| `langgenius/dify` | 158,869 | Agentic workflow + RAG platform (self-host). |

### 2.2 Packaging and print (where "retail ready" is lost)

- Dieline/pouch generation is a **commercial SaaS niche**: every open-source
  dieline project found generates folding cartons, not doypacks. The custom
  generator in `design_studio_print.build_doypack` remains the right call, and
  it now carries a published-ladder proportion check.
- Prepress: the wave confirmed the free, local chain used here — ICC via
  littleCMS (`Pillow.ImageCms`), Ghostscript for CMYK/PDF-X, Scribus for PDF/X-3
  with an embedded profile. Windows already ships a SWOP CMYK profile
  (`RSWOP.icm`), which is what `prepress.py` uses.
- The published stand-up-pouch ladder (Sparal's six sizes, cross-checked against
  PackagingBest templates and real mylar dielines) is the only calibration
  corpus found; it is encoded in `DOYPACK_LADDER`.

### 2.3 Composition realism (the part that makes a mockup believable)

- `bcmi/libcom` + the bcmi awesome-lists (harmonization, shadow generation,
  reflection generation, object placement, generative composition) are the
  canonical index. 2026 additions logged: CoShadow (multi-object shadow),
  MetaShadow (CVPR'25), VSDiffusion (ECCV'26), DEROBA (reflection).
- `lllyasviel/IC-Light` (8,549★) is already installed here and the wave found no
  better commercial-safe relighting model.
- `danielgatis/rembg` (25,125★) vs `ZhengPeng7/BiRefNet` (MIT): BiRefNet remains
  the pick for product cutouts, and the installed core nodes make it a one-node
  lane (now wired, with the mask-inversion trap documented).

### 2.4 Editing / inpainting (Packify's "erase" step)

- `Sanster/IOPaint` (23,306★) and `geekyutao/Inpaint-Anything` (7,726★) are the
  practical local erase/repair tools. **New this wave.**
- Qwen-Image-Edit-2511's own technical report notes text legibility at small
  render scales is a known weak point — which is exactly what the live smoke
  measured here (the edit rewrote "6 oz" as "8 oz"). The deterministic text
  layer therefore stays the law; the OCR drift gate now enforces it.

### 2.5 3D (Packify's Pacdora parity)

- `Tencent-Hunyuan/Hunyuan3D-2` (15,158★), `img2threejs/img2threejs` (18,412★),
  `google/filament` (20,628★) and the Blender/cycles cluster (4,051 repos in the
  3D bucket). Blender is **not installed on this machine** — recorded as an
  operator decision, not silently assumed.

### 2.6 Licence reality across the sweep

- 13,224 MIT + 3,301 Apache-2.0 + 324 BSD-3 + 145 Unlicense + 139 CC0 (permissive
  and usable), vs 2,107 GPL-3.0 + 545 AGPL-3.0 (usable as external tools, not for
  embedding) and 2,829 NOASSERTION + 23,846 with no licence at all (read-only
  reference material).
- 21,197 of the 47,323 repos were pushed in 2026 — this is a live ecosystem, not
  an archive.

---

## 3. What was built from the wave (all committed)

| Deliverable | Module | Evidence |
|---|---|---|
| Surface-realism passes (displacement, soft-light, specular, grain sync, fold shadow, print sim, junction AO, tonal match) | `Northstar_backend/compositor_realism.py` | Real-plate A/B `renders/ab_realism_*.png` + sidecar (mean_abs 2.65, 7.14 % of pixels >8); 12 tests |
| Static-fetch corpus learner (the REA-replacement lane) | `Northstar_backend/corpus_learner.py` | robots honoured, throttle, provenance-complete records, idempotent; 16 tests |
| Corpus ingest for the wave (GitHub / HF / YouTube / transcripts) | `corpus_ingest.py` + `tools/ingest_wave2.py` | **57,355 records** in the local index (47,323 repos, 9,148 HF, 884 YouTube) |
| Qwen-Image-Edit-2511 edit lane | `studio_generation.generate_edit` | Live smoke 8 steps/94.5 s; scene changed, copy drifted |
| Edit-drift OCR gate | `text_fidelity.verify_edit_preserves_copy` | Caught the real drift: `6 oz (170 g)` → `(6 0/L) Z0 9`, verdict `drift_numeric` |
| Doypack planning dieline + published-ladder check | `design_studio_print.build_doypack` | mm-true sheet, seal/zipper/AO layers, gusset warning on the 8 oz spec; 11 tests |
| Prepress (ICC CMYK, soft proof, gamut dE, ink limit) + endpoints | `prepress.py`, `/print/prepress/*` | Real dev plate → CMYK TIFF + proof assets, report in metadata; 9 tests |
| BiRefNet cutout → Amazon MAIN framing + compliance | `studio_generation.generate_cutout`, `image_prep.py` | Live: compliant at 2000×2000, fill 0.8795, white bg 1.0; 10 tests |
| Deterministic upscale (model upscaling disabled after a server abort) | `image_prep.upscale_lanczos` | 1216 → 2432, no GPU; failure recorded in `00_STATE` known_issues |
| Studio lane endpoints | `design_studio_lanes.py` | 9 tests incl. auth, gating, asset registration |

---

## 4. Still open

1. **RealESRGAN / SeedVR2 upscaling** — the x4 model aborted ComfyUI on a 1216px
   input; SeedVR2 ships only component nodes here. Operator decision recorded.
2. **3D mockup lane** — no Blender on this machine. The wave's 3D finds
   (Hunyuan3D-2, img2threejs) are the alternatives if Blender is not wanted.
3. **PDF ingestion for the corpus learner** — MinerU is the identified tool; the
   learner currently reads HTML only.
4. **LayerStyle / ComfyUI-RMBG** — not installed; the deterministic compositor
   already owns type, so the value is edge-halo refinement on cutouts.
5. **Doypack die accuracy** — still a *planning* dieline until the co-packer's
   die drawing (or a measured competitor pouch) calibrates the gusset.

---

## 5. Files

| File | What |
|---|---|
| `repos.csv` / `repos.jsonl` | 47,323 metadata-verified repos |
| `sweep_state.json` / `sweep_summary.json` | per-query completion + error log |
| `hf_models.csv`, `hf_models_by_tag.csv`, `hf_datasets.csv`, `hf_spaces.csv` | 9,513 HF assets |
| `videos_index.csv` / `videos.jsonl` | 829 enumerated videos |
| `transcripts/*.vtt`, `*.whisper.json` | captions + 55 local transcriptions |
| `gh_sweep_v2.py`, `hf_sweep_v2.py`, `yt_sweep_v2.py`, `transcribe_missing.py` | the sweeps (re-runnable, resumable) |
| `analyze_repos.py` | category/bucket analysis used in §2 |
