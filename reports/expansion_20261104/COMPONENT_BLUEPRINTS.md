# Component Adaptation Blueprints — targeted extraction, not repo adoption

Each blueprint names the **exact source commit**, the **only** parts worth taking, the **file in
NorthstarOS** they land in, and the changes needed for this box (RTX 5080 Laptop 16 GB VRAM,
16 GB system RAM, local GGUF/nvfp4, zero cloud). No code is copied in this pass; these are the
extraction contracts for the implementation units.

**Licence rule (the owner's "exemption" is not a licence exemption):** extracting a sub-function
does not change the licence of the source. Only permissive sources are eligible now; copyleft is
local-lane-only after review; non-commercial/proprietary is out. Every row records the lane.

Source coordinates are in `state/evidence/expansion_20261104/blueprint_sources.json`
(repo, licence, HEAD commit, matching paths).

---

## B1 — GBNF from a JSON schema (Bojo tool calls)

| Field | Value |
|---|---|
| Source | `ggml-org/llama.cpp` @ **6f1e654370** (MIT) — `common/json-schema-to-grammar.cpp/.h`; `dottxt-ai/outlines` @ **c52af8472c** (Apache-2.0) — `src/outlines/types/json_schema_utils.py` |
| Extract | `json_schema_to_grammar(schema, force_gbnf)`, `build_grammar`, literal escaping, and the schema→typed-dict utilities. **Not** the server, chat templates, or sampler. |
| Target | `Northstar_backend/agent_kernel/tool_protocol.py` (`_SCHEMA`), `Northstar_backend/agent_kernel/local_model.py` (llama.cpp request) |
| Native plan | Generate one GBNF from `_SCHEMA` at import; send it as the llama.cpp `grammar`. For Ollama, send the same schema as `format`/`json_schema` and keep the current parser as the validator. Measure parse-failure rate before/after; no new runtime, no VRAM. |
| Risk | A too-strict grammar can block a legitimate repair action; keep `finish`/`reply` in the schema and test all 12 tools. |
| Verify | 200 repeated tool-choice prompts: parse failures, invalid-arg rate, and successful `run` steps on the 20-brief bench. |

## B2 — Layout and reading order for labels, dielines and tables

| Field | Value |
|---|---|
| Source | `docling-project/docling` @ **e3681a613e** (MIT) — `docling/models/stages/layout/layout_object_detection_model.py`, `layout_postprocessing_model.py`, `docling/models/stages/ocr/rapid_ocr_model.py`; `PaddlePaddle/PaddleOCR` @ **dab3fe3537** (Apache-2.0) — `ppstructure` table/layout post-processing paths |
| Extract | Layout label taxonomy, reading-order assembly, table cell geometry, and the RapidOCR stage contract. **Not** the OCR weights (RapidOCR stays) and not Docling's full pipeline. |
| Target | `Northstar_backend/text_fidelity.py` (`_ocr_boxes`), `Northstar_backend/pouch_label.py` (`measure_face`), `Northstar_backend/mockup_quality.py`, `knowledge/` ingestion |
| Native plan | Add a layout pass in front of the existing OCR: detect the label/table region, order lines top-to-bottom, and feed boxes to the legibility gate. CPU-only (Docling layout model ~100 MB) and it must not add a Torch dependency to the service; run it as an optional child process like the scorers, with the current OCR as fallback. If the Torch-free path wins, `jingsongliujing/OnnxOCR` (Apache-2.0) and `qurator-spk/eynollah` (Apache-2.0) are the ONNX-first alternatives found in the GitHub leg; compare disk and latency before choosing. |
| Risk | Dieline drawings are not documents; the layout model will mislabel them. Gate by a `surface` flag and keep the geometric quad measurement as the authority for dielines. |
| Verify | 20 label/table images from `renders/` + synthetic dielines: region IoU, line order, and no regression on `t11` / `t10` / `t12`. |

## B3 — Foreground relighting for product scenes

| Field | Value |
|---|---|
| Source | `lllyasviel/IC-Light` @ **bcf3f29ca8** (Apache-2.0) — `gradio_demo.py` (`process_relight`, `run_rmbg`, `hooked_unet_forward`), `briarmbg.py` |
| Extract | The relight pipeline: foreground mask → lighting-conditioned UNet pass → composite back; the hooked UNet forward and prompt encoding. **Not** the Gradio UI and not the demo assets. |
| Target | `Northstar_backend/relight.py` (already exists), `Northstar_backend/studio_generation.py` (new lane) |
| Native plan | Run after a FLUX render, never instead of it: FLUX owns identity, IC-Light changes only the light. SD15-class weights (~2 GB) fit beside the 4.9 GB FLUX weights only sequentially — use the existing GPU lock and unload between lanes. Output goes through `ship_gate` with the reference photo for identity. |
| Risk | Relighting can shift label colours; the identity/legibility gate must reject a drifted render. |
| Verify | 10 scenes × 2 light directions: SSIM to the source ≥ 0.55, legibility pass, preference floor, VRAM peak < 15 GB. |

## B4 — Image-to-mesh for packshots and dieline previews

| Field | Value |
|---|---|
| Source | `VAST-AI-Research/TripoSR` @ **107cefdc24** (MIT) — `tsr/system.py` (`TSR.from_pretrained`, `extract_mesh`, `set_marching_cubes_resolution`), `tsr/models/` |
| Extract | The single-image triplane reconstruction wrapper, marching-cubes extraction and mesh cleanup. **Not** training code or the renderer UI. |
| Target | `Northstar_backend/geometry_handoff.py` (mesh/bbox contract), new `Northstar_backend/tys_ops/product3d.py` |
| Native plan | Run on the 5080 at 256³ marching cubes (peak ~6 GB), export OBJ/GLB, then reuse `geometry_handoff` for bbox/manifold checks. CPU fallback is allowed but slow; never on the render critical path. |
| Risk | A generated mesh is a candidate, not a print-ready die. Refuse `manifold_edges > 0` in the manifest and keep the dieline as the print authority. |
| Verify | 5 product photos: watertight mesh, bbox within 2% of the photo's measured face, < 60 s per asset, VRAM < 12 GB. |

## B5 — Temporal memory graph, SQLite-native

| Field | Value |
|---|---|
| Source | `getzep/graphiti` @ **fb60e59d4a** (Apache-2.0) — `graphiti_core/edges.py` (`Edge`, `EpisodicEdge`, `EntityEdge`, validity fields), `nodes.py`; `mem0ai/mem0` @ **ed1f10fc87** (Apache-2.0) — consolidation pipeline |
| Extract | The node/edge schema (episode → entity → fact), `valid_at`/`invalid_at` bi-temporal fields, dedupe/merge rules, and the consolidation sequence. **Not** the Neo4j/FalkorDB driver or the hosted service. |
| Target | `Northstar_backend/tys_ops/memory.py` (hashed index), `Northstar_backend/memory_bank.py` (facts/supersession) |
| Native plan | Two SQLite tables plus a `vec0` index: `episodes`, `facts` with `valid_at`/`invalid_at`; write path extracts candidates, merges duplicates, invalidates contradicted facts, and keeps the old row for audit. Real embeddings come from the already-installed `qwen3-embedding:0.6b` (1024-d), not a new model. |
| Risk | Silent fact deletion is unacceptable; invalidation must be append-only with a reason. |
| Verify | 50 seeded facts with 10 contradictions: correct winner, 0 lost audit rows, recall@5 on 20 questions vs the current hashed index. |

## B6 — Browser action schema and verification loop

| Field | Value |
|---|---|
| Source | `browser-use/browser-use` @ **b49a68e406** (MIT) — `browser_use/tools/registry/service.py`, `browser_use/tools/views.py`, `browser_use/browser/watchdogs/dom_watchdog.py` |
| Extract | The indexed-element action space (element id + action + args), action result/verification shape, and DOM diff observation. **Not** the agent loop, the cloud service, or stealth/anti-bot code. |
| Target | `Northstar_backend/chromeconnect_ai_loop.py`, `tools/browser_agent.py` |
| Native plan | Keep Chrome Connect as the controller and policy gate; use the action schema only to make each step explicit and verifiable (element id, expected post-condition). Any anti-bot or CAPTCHA behaviour is excluded — the controller stops instead. |
| Risk | Action-space drift between the model and the live DOM; require a post-condition check per action and fail closed. |
| Verify | 10 localhost-only flows: action parse rate, post-condition pass rate, 0 policy bypasses, and the existing Chrome Connect suite green. |

## B7 — Evaluation harness for Bojo and Tys

| Field | Value |
|---|---|
| Source | `UKGovernmentBEIS/inspect_ai` @ **572e288078** (MIT) — `src/inspect_ai/scorer/_scorer.py` (`Scorer`, `ScorerSpec`, `scorer_create`) and the solver/eval interfaces; `promptfoo/promptfoo` (MIT) for prompt assertions |
| Extract | Dataset → solver → scorer composition, sample/log schema, and the metric aggregation. **Not** the runtime or its model providers. |
| Target | `tools/tys_kernel_bench.py` (existing), new `tools/bojo_eval.py` |
| Native plan | Keep the harness local: JSONL samples, a solver that calls Bojo or the kernel, deterministic scorers (exact match, tool name, argument schema, retrieval recall@5). No cloud judges; a model judge is optional and local. |
| Risk | A benchmark that only measures what is easy to pass; include the 20-brief acceptance set and the 20-question retrieval set. |
| Verify | Baselines for Bojo tool selection and memory recall recorded before any change; every future change reports the delta. |

---

## What is deliberately not extracted

| Source | Why not |
|---|---|
| `browser-use` agent loop / cloud | Chrome Connect is the controller by charter; the loop is the part we must not duplicate. |
| `OpenHands` / `SWE-agent` runtimes | The kernel already has the same event/step shape; adopting the runtime would replace the policy layer. |
| `daytonaio/daytona` | No licence metadata — ineligible. |
| Graphiti's Neo4j driver | 16 GB RAM and a single-user box; SQLite is the right store. |
| Docling/Paddle model weights | RapidOCR is already installed and proven; adding a second OCR stack would double the surface for no measured gain. |

**Extraction protocol (all blueprints):** pin the commit, copy only the named functions/logic,
rewrite imports and types to the local interfaces, add a provenance header with source URL +
commit + licence, write a focused test before wiring, and never modify the source repo.
