# NORTHSTAROS — Secondary Discovery, Wave 2 (additional targets)

**Campaign:** `expansion_wave2_20261104` · **Units:** 5 of 5 · **Wall clock:** 37 minutes ·
**STOP:** absent throughout · **Quota:** 60/50/50 respected (GitHub 20 used, HF 30, arXiv 25;
the remainder was not needed).

Wave 1 completed at commit `bf648649` (10,061 indexed / 9,791 unique). This wave asks **different
questions** rather than re-indexing the same ones: layout/Donut/Depth/SAM, tool-protocol
implementations, virtual try-on, ad creative, conversion and listing research.

---

## VERDICT

**GO — the additional pass adds 3,950 targets (3,895 unique) and changes three blueprint sources,
but it does not change the first recommendation.** Cumulative discovery is **14,011 indexed /
13,686 unique**; with the primary GitHub pass the universe is ~25,800. Wave 2's value is **licence
triage and better source selection** (TRELLIS, SAM2/Depth Anything, Donut/Table Transformer), not
volume. No product code changed; the baseline smoke (`test_ship_gate.py`) is 16 passed.

**Licence correction stands:** targeted extraction is **not** a licence exemption. Wave 2 rejected
two popular models on licence grounds despite high download counts — `microsoft/layoutlmv3-base`
(CC-BY-NC-SA-4.0) and Tencent Hunyuan3D ("other"). Popularity is not eligibility.

---

## SCAN SUMMARY — indexed counts by platform

| Platform | Wave 2 indexed | Wave 2 unique | Cumulative indexed | Cumulative unique |
|---|---|---|---|---|
| Hugging Face Hub | 1,090 | 1,090 | 3,874 | 3,859 |
| arXiv | 748 | 746 | 1,394 | 1,387 |
| Google AI Developers Forum | 500 | 475 | 1,250 | 1,173 |
| YouTube (public RSS) | 89 | 89 | 266 | 266 |
| GitHub (extraction-focused) | 1,523 | 1,495 | 7,227 | 6,997 |
| **Total** | **3,950** | **3,895** | **14,011** | **13,686** |

Cross-wave overlap is not deduplicated across waves; the cumulative number is an upper bound on
unique projects. Per-file hashes and exact rows are in `manifest.json`.

**Wave 2 licence signal:** HF 1,090 rows — 551 with no licence tag, 142 MIT, 141 Apache-2.0, 104
"other", 39 CC-BY-NC-SA. The permissive core is clear; the NC/unknown tail is large enough that a
model's download count says nothing about whether it can ship.

---

## COMPONENT ADAPTATION BLUEPRINTS — wave 2 changes

Wave 1 contracts are unchanged except as noted. New source coordinates are in
`state/evidence/expansion_wave2_20261104/blueprint_sources_wave2.json`.

| # | Change | Source (commit, licence) | Extraction bounds | Improvement plan |
|---|---|---|---|---|
| B2 | **Add** document/table backbones | `clovaai/donut` 4cfcf97256 (MIT); `microsoft/table-transformer` 16d124f616 (MIT) | Donut's document parsing head and Table Transformer's structure-recognition post-processing; no weights beyond MIT checkpoints | Table cells and reading order for nutrition/dieline documents; Docling/Paddle remain the layout layer; **LayoutLMv3 weights excluded (NC)** |
| B3 | **Add** mask/depth conditioning | `facebookresearch/sam2` 2b90b9f5ce (Apache-2.0); `LiheYoung/depth-anything` 1d03336771 (Apache-2.0) | SAM2 predictor/mask prompt path; Depth Anything V2 Small inference | Better foreground masks and depth-aware lighting for IC-Light; both CPU/GPU-light and local; no cloud |
| B4 | **Upgrade** the quality path | `microsoft/TRELLIS` 193e0502b5 (MIT); `TencentARC/InstantMesh` 08822c52fd (Apache-2.0) | TRELLIS image-to-3D pipeline and mesh extraction; InstantMesh as the middle option | TRELLIS is the quality path; TripoSR stays the fast fallback. TRELLIS is a 4B-class model — run at reduced resolution/offload and gate on VRAM; manifold/bbox checks unchanged |
| B1/B5/B6/B7 | No change | — | — | Wave 2 found no better permissive source for GBNF, memory, browser schema or eval |

**New candidates noted, not yet blueprints:** `QwenLM/Qwen-Agent` (Apache-2.0) and
`aipotheosis-labs/aci` (Apache-2.0) for tool-call harness patterns; `IBM/mcp-context-forge`
(Apache-2.0) for an MCP gateway; `colbymchenry/codegraph` (MIT) and `Graphify-Labs/graphify`
(Apache-2.0) for code graphs (overlaps `code-review-graph`). None displaces a current pick.

---

## E-COMMERCE CREATIVE SERVICE SPECIFICATION — wave 2 findings

The measured floors do not change. The additions are exclusions and one research direction:

* **Virtual try-on is not a lane yet.** HF returned 127 try-on models; the majority are
  CreativeML OpenRAIL or NC, with one Apache-2.0 LoRA. Not eligible for the cloud lane, and not a
  measured quality gain over the reference-conditioned product picture we already ship.
* **LayoutLMv3 is excluded** (CC-BY-NC-SA weights) even though the code is MIT; Donut and Table
  Transformer are the permissive document path.
* **Ad creative / conversion / short-video research** (arXiv wave 2: ad targeting 50, conversion 50,
  multimodal recommendation 50, copywriting 15, creative ranking 5) reinforces generate-then-rank
  and holdout evaluation; it does not justify a new gate or a conversion-lift claim.
* **No change to:** A+ canvases (970×600 header, 970×300 three tiles, 1464×600 premium), 86% listing
  fill, 1080×1920/30 fps video, −16 LUFS, OCR sharpness ≥40, identity pHash ≤24 + SSIM ≥0.40,
  preference ≥0.20, adherence ≥18.0, 300 DPI dieline.
* **Amazon:** still untouched; presets remain `verified:false`.

---

## DECISIONS

1. **Licence beats popularity.** LayoutLMv3 (776k downloads, NC) and Hunyuan3D ("other") are
   rejected; Donut/Table Transformer/TRELLIS/SAM2/Depth Anything (MIT/Apache-2.0) are in.
2. **B4 uses TRELLIS as the quality path and TripoSR as the fast path.** TRELLIS's 4B-class size is
   a VRAM risk on the 5080; it runs at reduced resolution/offload and is gated by the existing
   manifold/bbox checks.
3. **B2 stays multi-backbone.** Docling/Paddle for layout, Donut/Table Transformer for document
   structure; no single OCR vendor replaces RapidOCR.
4. **Wave 2 is evidence, not adoption.** No product code changed; the blueprint queue is B1 first,
   then B5.
5. **The next unit remains B1** unless the owner chooses B4; wave 2 did not produce a
   higher-return, lower-risk first step.

---

## NEXT DECISION (one)

**Approve B1 (JSON-schema → GBNF from `llama.cpp` @ 6f1e654370) as unit 1, acceptance = tool-call
parse-failure rate on the 20-brief bench.** If the 3D/image lane matters more this quarter, say
**"B4 first"** and TRELLIS becomes the first extraction instead.

---

## Artifacts

* `reports/expansion_wave2_20261104/README.md` — this report
* `reports/expansion_wave2_20261104/manifest.json` — wave 2 + cumulative counts, every file hashed
* `reports/expansion_20261104/COMPONENT_BLUEPRINTS.md` — wave 1 contracts (unchanged)
* `reports/expansion_20261104/CREATIVE_SPECS.md` — measured creative specification (unchanged floors)
* `state/evidence/expansion_wave2_20261104/` — platform JSONL, summaries, new source coordinates

## Gates held

No Amazon request, no spend, no credential read, no cloud inference, no policy/allowlist change.
Public GitHub/HF/arXiv/Discourse/YouTube endpoints only. STOP checked before and after; absent.
No product code modified.
