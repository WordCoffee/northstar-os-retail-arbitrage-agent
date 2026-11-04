# NORTHSTAROS — Master Expansion Plan: Secondary Discovery & Creative Service Optimization

**Campaign:** `expansion_20261104` · **Units:** 5 of 5 (one defect found and repaired, no second
consecutive failure) · **Wall clock:** 31 minutes, under the 4-hour ceiling · **STOP:** absent
throughout. The launcher (`scripts\ty_go_autonomy.cmd`) dispatches queued author tasks, so this
research pass ran directly under the same unit/time/STOP guards instead of through the task queue.

---

## VERDICT

**GO — the discovery pass is complete and the extraction targets are real, but nothing was adopted
in this pass.** The scan indexed **six platforms** and produced a ranked set of component
blueprints, a measured creative-service specification and a fully populated manifest. The stable
baseline was not touched: no product code changed, so there is no regression to explain.

Two things the owner should know up front:

1. **"Licensing exemption via isolated extraction" is not a thing.** Extracting a function does not
   change the source licence. This pass therefore only admits permissive sources; copyleft is
   local-lane-only after review, and non-commercial/proprietary is out. One candidate
   (`daytonaio/daytona`) has **no licence** and is rejected. The extraction protocol is kept; the
   exemption framing is not.
2. **The shortest path to value is B1 (GBNF for Bojo) and B5 (SQLite temporal memory).** Both are
   CPU-only, use models already on disk, and have a number to move (tool-call parse failures and
   retrieval recall@5 respectively).

---

## SCAN SUMMARY — indexed counts by platform

Counts below are rows in the evidence files, not estimates. Exact unique counts and hashes are in
`manifest.json`.

| Platform | Indexed | Unique | Budget | Evidence |
|---|---|---|---|---|
| Hugging Face Hub | 2,784 | 2,769 | 49 requests | `state/evidence/expansion_20261104/hf.jsonl` |
| arXiv | 646 | 641 | 49 queries | `arxiv.jsonl` |
| Google AI Developers Forum | 750 | 698 topics | 14 queries | `gforum.jsonl` |
| YouTube (public RSS) | 177 | 177 videos | 14 channels | `youtube.jsonl` |
| GitHub (extraction-focused) | 5,704 | 5,502 | 60 requests | `github.jsonl` |
| **Total new targets** | **10,061** | **9,791** | — | `manifest.json` |

Combined with the primary GitHub pass (12,135 repositories, commit `1aa4fe32`), the discovery
universe is now **21,926 unique projects and documents**. The 10,000 **indexed** target is met
(10,061); the **unique** count is 9,791 — 209 short of 10,000, reported rather than rounded.

**Licence reality in the index:** 1,361 Hugging Face entries carry no licence tag; 78 are
`cc-by-nc-4.0` (restricted). The GitHub leg records per-repo SPDX. A target is eligible only after
the licence row is read — the count is not a recommendation.

**What the index changed in the plan:**

* **Table extraction has a clear winner:** `microsoft/table-transformer-structure-recognition`
  (MIT, 1.37M downloads) is a better B2 candidate for table structure than a new pipeline; the
  dieline model on HF is CreativeML OpenRAIL-M, so it is **not** eligible.
* **Relighting LoRAs are mostly NC/"other"** (`jasperai/LBM_relighting` CC-BY-NC,
  Kontext community LoRAs "other"). B3 stays on IC-Light (Apache-2.0); no HF LoRA is adopted.
* **Product-photo LoRAs exist and are permissive** (`Shoaibism/sdxl-product-photography-lora`,
  Apache-2.0), useful as style-pack evidence, not as a new lane.
* **arXiv** (641 papers; cs.AI 216, cs.CV 213, cs.CL 139, cs.IR 131) confirms generate-then-rank
  for ad creative and reference-attention drift as a real failure mode — both already reflected in
  the best-of-N and identity gate.
* **Google AI forum** (698 topics) is dominated by Gemma/QAT/LiteRT tool-use questions; that is
  Bojo-lane evidence, not a new component.
* **YouTube** (177 recent videos, 12 channels) is used as a signal for what practitioners ship, not
  as a transcript corpus.

**One defect, repaired:** the GitHub adapter initially rejected the new `creative` focus
(`KeyError`); the scoring table was extended and the leg rerun. That is one failure, not two
consecutive — the campaign stop condition was not triggered.

---

## COMPONENT ADAPTATION BLUEPRINTS

Full contracts (commit hash, extraction bounds, target file, native plan, risk, verification) in
[`COMPONENT_BLUEPRINTS.md`](COMPONENT_BLUEPRINTS.md). Sources resolved to HEAD commits in
`state/evidence/expansion_20261104/blueprint_sources.json`.

| # | Target | Source (commit) | Extract | Lands in |
|---|---|---|---|---|
| B1 | GBNF constrained tool calls | `llama.cpp` 6f1e654370 (MIT) + `outlines` c52af8472c (Apache-2.0) | `json_schema_to_grammar`, literal escaping, schema utilities | `agent_kernel/tool_protocol.py`, `local_model.py` |
| B2 | Label/dieline/table layout | `docling` e3681a613e (MIT) + `PaddleOCR` dab3fe3537 (Apache-2.0) | layout taxonomy, reading order, table cell geometry | `text_fidelity.py`, `pouch_label.py`, `mockup_quality.py` |
| B3 | Product-scene relighting | `IC-Light` bcf3f29ca8 (Apache-2.0) | `process_relight`, foreground mask/composite | `relight.py`, `studio_generation.py` |
| B4 | Image-to-mesh packshots | `TripoSR` 107cefdc24 (MIT) | `TSR.from_pretrained`, `extract_mesh`, mesh cleanup | `geometry_handoff.py`, new `product3d.py` |
| B5 | Temporal memory graph | `graphiti` fb60e59d4a (Apache-2.0) + `mem0` ed1f10fc87 (Apache-2.0) | edge/node schema, bi-temporal validity, consolidation | `tys_ops/memory.py`, `memory_bank.py` |
| B6 | Browser action schema | `browser-use` b49a68e406 (MIT) | indexed action space, result verification | `chromeconnect_ai_loop.py`, `tools/browser_agent.py` |
| B7 | Agent evaluation harness | `inspect_ai` 572e288078 (MIT) | scorer/solver composition, sample log schema | `tools/tys_kernel_bench.py`, new `tools/bojo_eval.py` |

**Deliberately not extracted:** the browser-use agent loop/cloud, OpenHands/SWE-agent runtimes
(replace the policy layer), Graphiti's Neo4j driver (16 GB box), Docling/Paddle model weights
(RapidOCR already proven). Daytona is ineligible for licence reasons.

---

## E-COMMERCE CREATIVE SERVICE SPECIFICATION

Full contract in [`CREATIVE_SPECS.md`](CREATIVE_SPECS.md). The measurable core:

* **A+ modules:** fixed canvases (header 970×600, three tiles 970×300 with 300×300 tiles, comparison
  970×600, banner 970×300, premium 1464×600 / 600×450, logo 600×180), contrast 4.5 body / 3.0 large
  / 6.0 over photo, body ≥14 px, head ≥24 px, ≤2 MB, six-beat page order.
* **Ad stills:** square 1024², story 864×1536, wide 1536×864; placement safe zones enforced by
  measurement; a contradictory canvas is refused.
* **Listing images:** 86% fill, pure white, text-free main; five shot types (white, lifestyle,
  packaging, zoom, group); the contact-shadow gap is named, not claimed fixed.
* **Shorts/TikTok/Reels:** 1080×1920 at 30 fps; sweet spots 30 s / 21 s / 20 s; safe zones 10/18/12,
  8/22/18, 10/20/14; 4n+1 frames, 81-frame ceiling per sampler call; captions OCR-checked; −16 LUFS;
  h264+aac MP4.
* **Verification floors:** OCR sharpness ≥40 on ≥75% of boxes, text height ≥10 px; identity
  pHash ≤24 **and** SSIM ≥0.40 (or SSIM ≥0.55); preference ≥0.20; adherence ≥18.0; 300 DPI at the
  measured dieline quad.
* **Research direction (not a lift claim):** AdBooster (2309.11507) and the fashion
  hyper-personalisation work (1908.10139) both generate-then-rank; short-video engagement
  (2508.02516) is a recorded score until calibrated; "Mind the RefGAP" (2609.35708) supports the
  identity gate; CTR literature needs impression logs we do not have.
* **Amazon:** no Amazon page, API or asset was read. Amazon presets remain `verified:false`.

---

## DECISIONS

1. **Adopt targeted extraction, not full repos — and no licence bypass.** Only permissive sources
   are eligible; copyleft stays local-lane; Daytona is rejected (no licence). Every extraction pins
   the commit and carries a provenance header.
2. **First implementation unit is B1 (GBNF), not a model change.** It is CPU-only, needs no new
   weights, and its acceptance is a number: tool-call parse-failure rate on the existing 20-brief
   bench. B5 (memory) is second, using `qwen3-embedding:0.6b` + `sqlite-vec` already installed.
3. **Creative rules become data, not prose.** A+ canvases, safe zones, fill %, DPI and OCR floors
   move to `config/creative_specs.json`; a threshold change must not require a code edit.
4. **No product code changed in this pass.** The baseline is untouched; the blueprints are the
   implementation queue. Zero regressions is therefore a fact, not a claim.
5. **Amazon stays behind the gate.** The A+ and ad-video specs remain internal contracts with
   `verified:false` until the owner supplies the current Amazon document.

---

## NEXT DECISION (one)

**Approve B1 as unit 1: extract the JSON-schema→GBNF kernel from `llama.cpp` @ 6f1e654370 and wire
it into `agent_kernel/tool_protocol.py`, with tool-call parse-failure rate as the acceptance
metric.** If B1 is not the priority, say "B5 first" and the memory graph takes the slot instead.

---

## Artifacts

* `reports/expansion_20261104/COMPONENT_BLUEPRINTS.md` — 7 extraction contracts
* `reports/expansion_20261104/CREATIVE_SPECS.md` — A+, ads, listing, video, OCR/dieline floors
* `reports/expansion_20261104/manifest.json` — every file, hash, count, zero placeholders
* `state/evidence/expansion_20261104/` — platform JSONL, summaries, blueprint source coordinates
* `tools/expansion_scan.py`, `expansion_blueprint_sources.py`, `expansion_manifest.py`

## Gates held

No Amazon request, no spend, no credential read, no cloud inference, no policy or allowlist change.
Public GitHub/HF/arXiv/Discourse/YouTube endpoints only. STOP checked before and after the pass;
absent. No product code modified.
