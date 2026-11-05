# V3 execution — state, idle systems, video, packaging, heavy lanes

**Date:** 2026-11-05 · **Scope:** the five V3 execution tasks. No Amazon request, no spend, no
credential read, no cloud inference.

---

## 1. State maintenance — done

59 pending fragment entries were folded into `00_STATE.json` through the operator merge tool
(`tools/state_fragment.py --apply`), one atomic write with a pre-merge backup.

* Before: 39 keys · After: **98 keys**
* Backups: `backups/state/00_STATE_20261105T050724884861Z.json` (pre-merge) and the apply-time copy.
* The flat `20261104_v3_readiness_closure.json` was **not** valid as a registry entry (12 metadata
  keys, no entry id). It is now wrapped as `v3_readiness_closure_20261104`; the 12 junk keys it
  originally produced were removed by restoring the backup and re-merging only valid single-entry
  fragments.
* `v3_readiness_closure_20261104` and `vision_bakeoff_20261105` are present; no metadata keys leaked.

## 2. Installed-but-idle systems — wired

### 2.1 Semantic memory in the Tys task lifecycle

`TysAssistant` now accepts a `memory` dependency. The live `default_assistant()` opens
`Northstar_backend/data/tys_memory.db` with `semantic=True`.

* on **submit**: top context is retrieved and stored on the task as `scope.memory_context` (the
  scope JSON is already persisted; no schema migration);
* on **completion**: `_remember_outcome` writes the objective + outcome (status/reason) to memory,
  source `task:<id>`;
* a memory failure is swallowed: it never blocks submission or completion.

Tests: `test_tys_memory_lifecycle.py` — 3 passed (context attached, outcome written, failure does not
block).

### 2.2 Northstar MCP server

`tools/northstar_mcp_server.py` (`mcp` 2.1.1, `MCPServer`) exposes six read-only tools over stdio:

`northstar_health`, `tys_state`, `tys_tasks`, `memory_search`, `provider_suite`,
`render_manifest`.

`render_manifest` refuses any path outside `renders/`; the server exposes no write, submit or browser
tool. Tests: `test_northstar_mcp.py` — 3 passed (registration, traversal refusal, provider catalog).

### 2.3 ast-grep and repomix in the coding lane

`agent_kernel/coding_tools.Workspace` gained two workspace-scoped, read-only tools:

* `ast_grep` — `ast-grep run --pattern … --lang …`, read-scope checked, bounded output;
* `repo_pack` — `repomix --stdout`, bounded to 20k chars by default.

Both are in `tool_protocol._SCHEMA`/`CANONICAL_ACTIONS`/`_PATH_ARG`, so the model can choose them and
the path is still normalised and scope-checked. Tests: `test_coding_toolchain.py` — 3 passed;
184 focused tests across the coding/tool/Tys/video suites passed.

### 2.4 Human-feature override audit

`video_guard.audit_override` appends a JSONL record to `state/audit/human_features_overrides.jsonl`:
id, timestamp, account, surface, acknowledged flag, matched terms, prompt SHA-256 and a 200-char
prefix. It is called for every override attempt on `/shorts` and `/generate` (allowed or refused).
Audit failure never blocks the render. Tests: 7 in `test_video_guard.py`.

## 3. V3.2 video pipeline — audit done, A14B 30 s **blocked**

**What is done:** the override audit above; the 15 s Wan 2.2 **5B** master already shipped
(`reports/v3_master_video_20261104.json`, 450 frames, 1080×1920, OCR-clean, silent by construction).

**What is not done and why:**

| Requirement | Status |
|---|---|
| Wan 2.2 **A14B** experts in ComfyUI | The Q4_K_M high/low experts are staged in `ComfyUI/models/_incoming/QuantStack__Wan2.2-I2V-A14B-GGUF/{HighNoise,LowNoise}` (18 GB), **not** in `ComfyUI/models/diffusion_models`; no A14B graph exists. `shorts.py` builds the 5B graph. |
| 30 s chained master | Not rendered. A 30 s 5B run would not satisfy the A14B requirement, so it was not mislabelled as one. |
| Audio synchronisation | `video_audio.py` exists, but the 15 s master has no audio; no 30 s voice/music bed was produced. |

Installing the A14B checkpoint pair would leave ~1.6 GB free at the current 19.6 GB disk headroom
(below the 10 GB floor) if both are copied into ComfyUI; the safe path is to free space or point
ComfyUI at the staged files, then validate a 5 s clip before any 30 s run. Details:
`docs/HEAVY_LANES.md`.

## 4. V3.3 packaging — dieline ready, official data blocked

Generated a real 6 oz stand-up-pouch planning dieline:

* `renders/mogra_lions_mane/print/dieline_6oz.svg`
* `renders/mogra_lions_mane/print/dieline_6oz.pdf` (2,209 bytes)
* `renders/mogra_lions_mane/print/dieline_manifest.json` (template, dimensions, hashes, confidence)

The dieline engine already reserves the nutrition/QR/UPC zones and runs the geometry audit. The
**official** nutrition panel and UPC/GTIN cannot be finalized because the values are not in the repo:
the current label carries `DRAFT · VERIFY BEFORE PRINT` and a placeholder barcode. The print lane
must not invent them. Required from the owner:

1. UPC/GTIN (12/13 digits) and symbology;
2. Supplement Facts: serving size, servings per container, each amount and %DV;
3. ingredient list, allergens, warnings, storage;
4. lot/best-by format, distributor block;
5. converter confirmation of width/height/gusset and material.

Until those arrive, the asset status is `dieline_ready_data_blocked`; the fake barcode is not
promoted to a final asset.

## 5. Heavy model preparation — readiness hooks

`tools/heavy_lane_check.py` → `reports/heavy_lanes_readiness_20261105.json`:

| Lane | Status |
|---|---|
| B2 Docling/Paddle layout OCR | **blocked** — packages absent; install in a staging venv (it pulls a second OCR stack) |
| B3 IC-Light relight | **ready for validation** — node + SD15 base present |
| B4 TRELLIS/InstantMesh | **blocked** — weights absent |
| Video A14B | **blocked** — staged weights, no ComfyUI copy/graph |

`docs/HEAVY_LANES.md` records the exact install/validation commands, VRAM/RAM limits, and the rule
that a mesh is a candidate, not a print asset.

## 6. Verification

| Run | Result |
|---|---|
| Focused coding/tool/Tys/video suite | **184 passed** |
| Memory lifecycle | **3 passed** |
| MCP server | **3 passed** |
| Video guard (including audit) | **7 passed** |
| Coding toolchain | **3 passed** |
| Full backend suite | **6105 passed, 117 skipped, 2 xfailed, 0 failed** in 15:57 (`logs/v3_full_suite_timeout.log`) |

## 7. Open

* A14B weights/graph and the 30 s master (blocked above).
* Official nutrition/UPC values (owner data).
* B2/B4 installs and validation runs.
* Wire the MCP server into the client config; start the OTel collector (tracing remains opt-in).
* `state/fragments/_pending_merge_20261105.json` is the applied merge record; retained for audit.
