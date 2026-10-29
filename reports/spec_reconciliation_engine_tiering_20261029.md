# Spec-vs-disk reconciliation — heterogeneous engine tiering / defect / verification doc

**Date:** 2026-10-29
**Input:** the supplied architecture document (engine tiering, telemetry, AgentScope/Matrix, AST patching, p01/p03 remediation, `POST /tasks/{id}/run?engine=kernel`, 5-point harness, 20-brief benchmark table).
**Verdict:** the two-engine split is **real and running**, but on different mechanics and numbers than stated. Six of the document's named subsystems **do not exist on disk**. Two defects are **misidentified**. The 20-brief benchmark table is **not this repo's data** and cannot be — the path it measures is not built here.

Evidence in this report is from files on disk and live probes on 2026-10-29. Where the document and the disk disagree, the disk wins and the document line is amended, not reinterpreted.

---

## 1. Claim-by-claim

| # | Document claim | Disk | Verdict |
|---|---|---|---|
| 1 | Two engines: Ty 27B GPU, Bojo 2B CPU | `scripts/start-northstar-llm.ps1` (Ty) + `scripts/bojo-cpu.Modelfile` (Bojo) | **TRUE, different internals** |
| 2 | Task Orchestrator Gateway routes on complexity + resources | `model_router.py` tiers only; `lane_telemetry.py` refuses to emit a policy under 30 samples/lane | **ABSENT** |
| 3 | `telemetryd` daemon, 100 ms sampling, routing score `R = f(A,C,V,T)`, threshold fallback | no such module; no 100 ms sampler; no scheduler | **ABSENT** |
| 4 | KV offload trigger above 64k via AgentScope offloading hooks | hard `-c 65536` launch ceiling; no offload path | **ABSENT** |
| 5 | AgentScope TeamPipeline, Matrix rooms, `state_dict`/`load_state_dict`, `handle_interrupt` | `agentscope` not installed (`ModuleNotFoundError`); no Matrix; `agent_kernel/` implements plan/subagents/session/resume itself | **ABSENT** |
| 6 | Target AST Patching Engine (libcst/tree-sitter, symbol targeting, 5-stage pipeline) | `agent_kernel/patch_tool.py` = `git apply` on a unified diff; `coding_tools` = write + apply_patch + run | **ABSENT — the repo does the thing the doc argues against** |
| 7 | Defect p01 = concurrency deadlock / session-context race | p01 is **brief id 1** ("Fix a failing unit test"); the real p01 defect was acceptance-recovery returning `needs_human` after valid artifacts | **MISIDENTIFIED** |
| 8 | Defect p03 = subprocess handle leak / zombies | p03 is **brief id 3** ("Refactor a module"); the real p03 defect was a write-stall, fixed with required-artifact step pressure | **MISIDENTIFIED** |
| 9 | `git worktree add -b task/<id>` per task, merged after verification | no task-scoped worktree; tasks run in `scope.workspace`; isolation is `diff.py` + session checkpoints | **ABSENT** |
| 10 | `POST /tasks/{id}/run?engine=kernel` → 202 + `engine_allocated` + `worktree_path` + `matrix_room_id`, SSE/WS | `POST /api/admin/tys/tasks/{task_id}/run`, **synchronous 200** `{"task": …}`, no `engine` param, no 202, no SSE; polling via `GET /tasks/{id}` | **PARTIAL** |
| 11 | 5-point empirical verification harness | `agent_kernel/verify.py` registers **17** named verifiers; `unknown` never passes | **DIFFERENT SHAPE** |
| 12 | 20-brief table: diff 82.4/41.2/12.0 %, AST 100 %, per-tier latency + VRAM | measured here: harness validation 20/20; live text lane 20/20 artefacts, 17/20 content; hybrid coding 20/20, p50 7.3–8.5 s, p95 15.7–25.6 s | **NOT THIS REPO'S DATA** |

---

## 2. What the two engines actually are

| | Ty | Bojo |
|---|---|---|
| Runtime | llama.cpp CUDA (`llama-server`, port 8080, OpenAI-compatible `/v1`) | Ollama |
| Weights | Qwen3.8-27B GSQ-RCO **IQ3_XXS** + MTP (10.4 GB) | qwen3.5 **1.9B, Q8_0** (2.7 GB) |
| Placement | `-ngl 99`, ~13 GB VRAM of 16 GB | `PARAMETER num_gpu 0` — CPU only |
| Context | **65 536** | **8 192** |
| KV cache | **q4_0** K and V | default |
| Throughput | ~69 tok/s with MTP (**~14.5 ms/token**), ~47 tok/s without | not benchmarked in-repo |
| Availability | on demand only; **not running** at time of check (`127.0.0.1:8080` refused) | idle-resident; `ollama ps` empty |
| Capabilities | completion + tools, no vision (`--mmproj` withheld for VRAM) | completion + **vision** + **tools** + thinking |

Document corrections, in both directions:

* **32k not 128k.** `-c 65536`. This is a measured ceiling, not a choice: the previous Ollama 27B died at `num_ctx 64576` (`cudaOccupancyMaxActiveBlocksPerMultiprocessor` → `0xc0000409`), bisected to a working 32 768 and recreated at 16 384, then moved to llama.cpp at 65 536 with q4_0 KV.
* **q4_0, not q8_0.** q8_0 KV caps at ~32k on this card. The document's "8-bit quantized KV" premise is the one configuration that does not fit.
* **~14.5 ms/token, not <45 ms/token.** The document understates Ty by roughly 3x.
* **~13 GB, not 18–22 GB VRAM.** IQ3_XXS is ~3.06 bpw. The document's 18–22 GB figure would not load on this machine.
* **Bojo is not a formatter.** It carries vision, tools and thinking, and it is the resident brain for `T1`/`T2`/`T3` (`model_router.LOCAL_MODELS` maps all three to `bojo`). Characterising it as an AST/lint/shell-formatting shim understates what is actually serving chat.
* **Bojo is absent from `shared/model-suite.json`.** The declared "single source of truth for tiered model selection" does not name the model that `model_router` actually returns for every local text tier. That is a real drift, independent of this document.

---

## 3. The six missing subsystems, and what stands in for them

Nothing below should be represented as built.

1. **Routing/telemetry.** `lane_telemetry.py` records one row per measured run (lane, latency, tokens, ok) and computes nearest-rank p50/p95. `recommend()` returns `available: False` until every candidate has 30 samples. There is no live VRAM/thermal sampling, so `R = w_A·A + w_C·C + w_V·V + w_T·T` has no inputs. The *concern* is handled point-wise instead: `local_vision` reads free VRAM before choosing a device, `unload_brain` drains `/api/ps` and verifies, the render guard re-evicts on OOM. That is three local guards, not a daemon.
2. **KV offload.** Enforced by refusing to launch above the measured ceiling. No host-DRAM tail, no compression hooks.
3. **AgentScope/Matrix.** `agentscope` is not installed and nothing imports it. The functional equivalents are in `agent_kernel/`: `plan`/`graph` (validated DAG, cycles rejected), `subagents.py` (ThreadPoolExecutor, isolated context, sha256-checked reports, parent re-verifies), `session.py` (journal + checkpoint + resume), `policy.py` (deny→ask→allow, expiring grants). Resume is tested for not repeating a completed node. HITL exists as plan gates and `needs_human` status, not as room injection.
4. **AST patching.** `patch_tool.py` invokes `git apply --whitespace=nowarn` with no `--unsafe-paths`, resolving every path against the workspace root and refusing a workspace nested in another repo. Its own docstring is explicit that there is no Python applier and no silent fallback. So the document's central technical argument — diffs are brittle, symbols are stable — is **unaddressed in code**, and the failure rates it attributes to diffs have never been measured here.
5. **Worktree isolation.** `patch_tool.worktree_root()` only locates the `.git` root to validate patch paths. No `git worktree add`, no per-task branch, no merge-gated cleanup. Isolation is per-file snapshots (`diff.py`) plus checkpoints, which the kernel documents as not covering subagent edits or non-file state.
6. **Async run endpoint.** The route exists and is admin-gated, but it is a blocking call that returns the finished task. `202`, `engine_allocated`, `worktree_path`, `matrix_room_id` and SSE have no implementation. Long runs are handled by client polling of `GET /tasks/{id}`, plus `POST /resume` and `POST /controller-result` for the Chrome Connect handoff.

---

## 4. The benchmark table

The 20-brief table in the document cannot have been produced by this repo:

* There is no AST patch path, so the "AST Patching 100.0 %" rows have no code behind them.
* No run in `00_STATE.json` or `reports/` reports a diff-vs-AST comparison, per-tier VRAM peaks, or the 82.4 / 41.2 / 12.0 % figures.
* `eval/projects/ns_proj_20.json` is marked `"status": "provisional"` and its own note says the runner validates plan validity, evidence coverage, retry and resume — not edit-format success.

Real measured numbers, for replacement:

| Run | Result |
|---|---|
| Harness validation (`tools/proj_bench.py --limit 20`) | 20/20 valid plans, evidence 1.0, resume pass — **not a project result** |
| Live text lane, 3 runs | 20/20 artefacts, 18/20 format-valid; content 17/20 each (p11, p13, p14); p50 4.82–6.27 s, p95 11.17–14.08 s |
| Enforced validators | 17/20, evidence 0.95, p50 5.08 s, p95 12.90 s |
| Hybrid coding/tool lane | 20/20 content-valid; p50 7.3–8.5 s, p95 15.7–25.6 s (thresholds 10.2 / 30.7 s, completion 0.90) |
| Ty as-is (no tools/context) | 0/20 content-valid |

---

## 5. Where the document is right and useful

* The two-tier split is the correct shape and is already earning its keep: Bojo holds ~2.7 GB of RAM and zero VRAM, so it can serve chat while ComfyUI owns the GPU; the 27B worker is launched on demand and evicted before renders.
* Keeping deterministic work off the GPU is the live design constraint on this box, and the reason is **RAM, not VRAM** (15.4 GB system RAM is the binding limit for a 10.4 GB model plus a 64k KV cache).
* The KV-cache-dominates-at-long-context argument matches what was measured: at 64 576 context the 16 GB card died, and the fix was context plus KV precision, not a bigger plan.
* The runtime-verification idea (no merge on unverified work) is already enforced more strictly than described: 17 named verifiers, and an `unknown` result never passes.

---

## 6. Recommended order, if this becomes work

1. **Correct the record first** (this report). Do not ship the benchmark table — it would be a fabricated result in a product document.
2. **`shared/model-suite.json` drift**: name `bojo` as the local T1/T2/T3 model, or state explicitly that the suite covers cloud tiers only. Cheap, and it removes a real inconsistency that predates this document.
3. **Engine selection in the kernel** (`engine=kernel|ty|bojo`): the kernel is already model-agnostic, so this is a parameter plus a resolution step, not a rewrite. Do this before any routing score — a router with no engine handle has nothing to route to.
4. **Async run + SSE**: worth doing for long work orders, but it changes a live admin surface and should land with a client that consumes the stream.
5. **AST patch lane**: the only way to test the document's central claim. Build it beside `patch_tool.py` (keep `git apply` as the fallback), then re-run the 20 briefs to get a real diff-vs-AST comparison. Do not report AST numbers before then.
6. **Worktrees per task**: real value for concurrent workers, and the mechanism is well understood. Note the existing checkpoint limits first — worktree isolation does not fix non-file state.
7. **`telemetryd`**: last. `lane_telemetry` already refuses to route without 30 samples per lane; a 100 ms sampler feeding an unvalidated score would replace a measured refusal with an unmeasured guess.
8. **AgentScope/Matrix**: not recommended as a dependency swap. The kernel's plan/subagent/session/policy modules already provide the topology, and adopting a framework to gain Matrix rooms would add a runtime and a licence question for a logging channel. If auditable event streaming is wanted, an append-only journal endpoint is the cheaper path.

---

## 7. Gates held

No Amazon. No spend. No installs. No credentials read. No policy or allowlist change. Chrome Connect not invoked.
