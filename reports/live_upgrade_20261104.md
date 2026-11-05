# Live upgrade — approved improvements applied to the running service

**Date:** 2026-11-04 · **Scope:** the CPU-only, no-new-weights items from the approved Tier-0
queue, applied, tested and running on the live dev stack. Heavy model lanes are listed at the end
with the reason they are not in this pass.

---

## 1. What is live now

| Surface | Address | State |
|---|---|---|
| Backend API | `http://127.0.0.1:8000` | **up** (PID 1104), `/health` 200 |
| UI (Vite) | `http://127.0.0.1:8101` | **up** (PID 25196), 200 |
| Semantic memory | `/api/admin/tys/memory/*` | **operating**, `semantic: true` |
| Tracing | `agent_kernel/tracing.py` | wired into `TysAssistant.run_kernel`, off unless `NORTHSTAR_TRACE=1` |
| Eval harness | `tools/bojo_eval.py` | baseline recorded |

Live memory check (real HTTP, dev shim identity):

```
POST /api/admin/tys/memory/text   -> {"chunks":1,"ids":["c_6ea3a0b516f2"],"semantic":true}
GET  /api/admin/tys/memory/search -> {"semantic":true,"hits":[{"score":0.6629,
                                     "text":"The render lane takes the GPU lock before it starts."}]}
GET  /api/admin/tys/memory/stats  -> {"semantic":true,"semantic_reason":"","chunks":1}
```

## 2. What changed

### 2.1 Semantic memory (B5, first half)

`Northstar_backend/tys_ops/memory.py` now has two retrieval paths:

* **hashed (default):** unchanged 256-dim bag-of-words, no model, works when the GPU/worker is down;
* **semantic (opt-in):** 1024-dim `qwen3-embedding:0.6b` vectors in a `sqlite-vec` `vec0` table
  with **cosine** distance. Any embedder/extension failure disables it for the process and falls
  back to hashed — memory never becomes unavailable because a model is.

Old hashed chunks are **backfilled lazily** (32 per search) so enabling semantic mode does not make
existing memory disappear. The service opens `Northstar_backend/data/tys_memory.db` with
`semantic=True`.

New admin routes in `tys_api.py`: `GET/POST /memory/text`, `GET /memory/search`, `GET/POST
/memory/facts`, `GET /memory/stats`. Documented in `docs/TYS_MEMORY.md`.

Live evidence: `semantic:true`, score 0.6629, `semantic_reason:""`.

### 2.2 Eval harness (B7)

`tools/bojo_eval.py` measures the two things that regress silently:

* tool-call contract: 8 parser/schema cases (prose, two actions, unknown tool, missing arg,
  truncated JSON, valid actions) — **accuracy 1.0**;
* memory recall@3 on a seeded set, hashed or semantic — **recall 1.0 with semantic true**;
* optional `--live` calls Bojo for real tool choices (slow on CPU, opt-in).

Baseline written to `reports/bojo_eval_20261104.json`. This is a seeded contract test, not a model
quality claim.

### 2.3 Toolchain (Tier 0)

Installed and verified: `sqlite-vec 0.1.9`, `ast-grep-cli 0.51.1` (`ast-grep --version`),
`repomix 1.18.1`, `mcp 2.1.1`, `opentelemetry-sdk 1.45.2` + OTLP HTTP exporter.
Pins in `Northstar_backend/requirements-agent-tools.txt`; provenance rows added (local-lane).

### 2.4 Tracing

`agent_kernel/tracing.py` adds `span(name, **attrs)`: a no-op unless `NORTHSTAR_TRACE=1`; when
enabled it sends to `OTEL_EXPORTER_OTLP_ENDPOINT` if set, else the console. `run_kernel` is wrapped
in a `tys.kernel` span. A span failure never fails the work.

### 2.5 Already operating (no change needed)

* **B1 — constrained tool calls** were already implemented: `agent_kernel/local_model.py` sends
  `TOOL_CALL_SCHEMA` as `response_format: json_schema` to llama.cpp, and
  `tool_protocol.json_schemas()` builds the native tool definitions from the same `_SCHEMA`. The
  blueprint's GBNF would duplicate that path; no code change was made.
* **Image review gate, reference conditioning, scorers, best-of-N** were committed earlier
  (`a9c031e6`, `b214404a`) and are part of the same tree.

## 3. Verification

| Run | Result |
|---|---|
| `pytest test_tys_ops test_tys_assistant test_tys_memory_api test_semantic_memory test_tracing test_tys_routing test_ship_gate test_continuous_loop` | **195 passed** |
| `pytest test_semantic_memory` after the backfill test | **4 passed** |
| Live `/health` | 200 `{"status":"ok"}` |
| Live `/api/admin/tys/state` | 200 with the dev operator identity |
| Live memory write/search/stats | 200, `semantic:true`, score 0.6629 |
| `ast-grep --version` / `repomix --version` | 0.51.1 / 1.18.1 |

No product behavior changed outside the new memory routes and the optional trace wrapper; the
existing memory tests pass unchanged.

## 4. Not in this pass (and why)

| Item | Why not | What it needs |
|---|---|---|
| **B2 layout OCR** (Docling/Table Transformer/Donut) | Docling's install pulls a second OCR stack (`rapidocr 3.10`), OpenCV, tree-sitter and a Hugging Face hub upgrade; it would touch the live OCR path without a measured comparison | A staging venv or a measured A/B on 20 label/table images, then wire as an optional child process |
| **B3 IC-Light relighting** | Needs SD15-class weights (~2 GB) and a GPU lane run; sequential with FLUX under the 16 GB lock | Download weights, add a `relight` lane, verify identity/legibility on 10 scenes |
| **B4 TRELLIS / InstantMesh 3D** | 4B-class weights, reduced-resolution/offload plan, VRAM gate | Weight download + 5-product mesh test, manifold/bbox checks |
| **B6 browser action schema** | Touches Chrome Connect, the highest-risk policy surface | A dedicated unit with the existing Chrome Connect suite as the gate |
| **FLUX 3 media lane** | ComfyUI was stopped after the image-quality pass; starting it now would take RAM/VRAM without a render to verify | `scripts/start-flux3.ps1`, then one gated render |

The user-facing service is fully operating on the improvements that are safe to enable now; the
remaining blueprints are model/GPU lanes, not wiring.

## 5. Rollback

1. Stop the dev stack: kill PIDs 1104 (API) and 25196 (UI).
2. Revert `Northstar_backend/tys_ops/memory.py`, `tys_api.py`, `agent_kernel/tracing.py`,
   `tys_assistant.py`, the three new tests and `tools/bojo_eval.py`.
3. Delete `Northstar_backend/data/tys_memory.db` (new file; the hashed memory DB is untouched).
4. Optional: `pip uninstall sqlite-vec ast-grep-cli opentelemetry-sdk
   opentelemetry-exporter-otlp-proto-http` and `npm uninstall -g repomix`.

Gates held: no Amazon request, no spend, no credential read, no cloud inference, no policy/allowlist
change. The dev identity shim was used only on loopback.
