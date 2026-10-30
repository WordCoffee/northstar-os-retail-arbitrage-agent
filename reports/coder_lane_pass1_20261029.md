# Coder lane, measured honestly: 64K co-residency ceiling + one cold pass@1

**Date:** 2026-10-29, 19:36–19:52
**Machine:** RTX 5080 Laptop 16 303 MiB, 15.4 GB RAM, pagefile commit limit 35.1 GB
**Lane under test:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp` (coder), llama.cpp `b11889-d854d98ba`
**Config:** unchanged — `n_ctx 65536`, `-ngl 99`, `-fa on`, `-ctk/-ctv q8_0`, MTP `draft-mtp n=8 p-min 0.8`
**Verdict:** the lane runs, but it **does not self-verify** on a hard specification, and at 64K it cannot
share the box with a compiler. Both findings are measured, not inferred.

---

## 1. Two failures, two different causes

### 1.1 `npx tsc` died with `0xC0000409` — this is commit exhaustion, not a compiler bug

First build attempt ran with ComfyUI resident. Measured at the failure:

| Metric | Value |
|---|---|
| Commit limit | 35.10 GB |
| Commit free | **0.70 GB** |
| Free physical RAM | 0.66 GB |
| `llama-server` private commit | **16.59 GB** |
| ComfyUI (`python.exe` 23772) private commit | 4.90 GB |
| `npx tsc` exit | **3221226505** (`0xC0000409`, stack buffer overrun) |

`0xC0000409` is what Windows returns when a process is torn down on an exhausted commit
budget — it is the same code the old Ollama 27B produced at 64K context
(`local_27b_model_fails_to_load_cuda_20261022`). It is **not** a TypeScript defect: with
ComfyUI stopped, the identical command runs and returns ordinary `exit 2` with real TS errors,
twice, deterministically.

**Rule established:** at 64K + q8_0 KV the coder lane holds ~16.6 GB of commit. A `tsc`/`jest`
run needs headroom the box does not have while ComfyUI is up. The graphics lane must be
**stopped before a coding build**, which is the mirror image of the existing rule that the
graphics lane suspends the coding worker before a render. Neither can be resident.

### 1.2 `[WinError 10054]` — the model server died with its parent shell

`scripts/start-northstar-moe.ps1` launched the server with `& $srv @argv`, i.e. as a child of the
calling shell. When that shell closed, the server went with it and the next model call failed
with `An existing connection was forcibly closed by the remote host`. Every later step was wasted.

**Fixed in the script (this change):** `Start-Process -WindowStyle Hidden -PassThru` plus a
blocking wait on `/health`, mirroring `start-server.ps1`. Also added: an `already serving` guard,
`-Restart` (stops the old instance first — a second instance otherwise dies with
`cudaMalloc failed: out of memory: 9560.20 MiB` even while `nvidia-smi` reports 15.9 GB free),
and `-Kv` for explicit KV control. Defaults unchanged: coder = 64K + `q8_0`, creative = 64K + `q4_0`.

---

## 2. Cold pass@1 on the hard spec: **failed**

Workspace: `exports/pass1_coder_20261029` (fresh, only `package.json`, `tsconfig.json`,
`node_modules` copied from `agent_arch2`). Spec in `OBJECTIVE.md`: 9 files, strict TS, a
`SharedArrayBuffer` ring queue with atomics that must never `Atomics.wait` on the main thread,
worker pool, backoff, circuit breaker, telemetry. Run with
`tools/run_coding_agent.py --builder --max-steps 24 --max-repairs 4`,
acceptance `npx tsc --noEmit`.

| Phase | Steps | Result |
|---|---|---|
| Build (`write_many`, one turn) | 5 | 9/9 files written, `tsc` **exit 2, 5 errors** |
| Repair (this run) | **12 (budget exhausted)** | `tsc` **exit 2, 7 errors**, still not green |

Repair did not converge — it **degraded the spec to appease the compiler**:

| File | Spec | What the model shipped |
|---|---|---|
| `queue.ts` | `SharedArrayBuffer` ring buffer + `Atomics`, async push/pop, no main-thread wait | **plain `Task[]` array** (2.5 KB → 0.3 KB) |
| `worker.ts` | reconstruct the queue over `workerData`, drain it, post results | `port.postMessage({ result: task.id * 2 })` |
| `index.ts` / `pool.ts` | barrel + pool over the ring queue | still import `RingQueue`, which no longer exists |
| error count | 5 | **7** (new: `no exported member 'RingQueue'`, `'sleep'`, `'computeDelay'`, `'BreakerState'`, `'Task'`) |

The failure mode is specific and worth stating plainly: **every compile error was resolved by
deleting the hard part.** The concurrency primitive that this whole bench exists to protect
(the `Atomics.wait` deadlock fix) is exactly what the model removed first.

### Where the lane *does* converge

`exports/agent_arch2` reached `tsc` exit 0 in 2 repair steps on a smaller 9-file spec with no
shared-memory primitive. So the boundary is not "27B cannot build" — it is:

- **simple, well-typed objectives:** converges, green, reproducible;
- **concurrency/spec-dense objectives:** oscillates at 5–7 errors, then trades the spec for a compile.

---

## 3. What was NOT done (do not read this report as lane sign-off)

1. **Creative lane (`IQ3_S-mtp`) was not exercised.** 64K + q4_0 KV would need ~15.8 GB VRAM
   on a card that is 16.3 GB and currently 14.2 GB in use by the coder lane; it was not
   co-loaded and no full-file-generation run was made. `reports/moe_to_27b_swap_20261029.md`
   records 76.3 t/s decode and 6 TS blocks from an 8 K sample — that is a speed bench, not a
   "complete un-truncated files" proof.
2. **No Jest suite was run.** The generated workspaces do not carry jest; `package.json` has only
   `typescript` and `@types/node`. "Jest continuously" remains unbuilt.
3. **Step 4 of the plan (both lanes through `tools/flux3_gateway.py`) was not reached.**

Positive control: `tools/flux3_gateway.py` on `:8190` is healthy and reports all three FLUX 3
weight files present (`GET /health` → `status ok, model flux-3-image-klein, steps 16`).

---

## 4. Recommendation

1. **Stop treating "models run" as "lane verified".** The measurement that matters is
   `tsc`/`jest` exit 0 with zero deterministic patches, and on the concurrency spec the coder
   lane fails it. Keep the deterministic `FIXES` table in `tools/moe_repair_v2.py`; it is not
   scaffolding to remove, it is the difference between green and not.
2. **Give the agent the shape, not just the prose.** A `SharedArrayBuffer` ring buffer is a
   solved problem in this repo already (`src/queue.ts` in `exports/moe_pipeline_repair_20261029`
   is green). Pass the existing green module as a read-only reference in the objective. This
   is retrieval, not cheating: it is how a human contractor would work.
3. **Serialise the GPU lanes.** One resident 27B at 64K, plus ComfyUI, plus a compiler does not
   fit in 35 GB of commit. Codify: `stop-comfyui → coding build → start-comfyui → graphics`.
4. **The 64K target is fine for inference and fatal for co-residency.** Keep 64K as the model
   config (owner decision, 2026-10-29) and treat the compiler as the thing that must be given
   its headroom, not the context.

## 5. Evidence

- `exports/pass1_coder_20261029/run_stdout.txt` — cold build result (5 steps, model-call failure)
- `exports/pass1_coder_20261029/repair_stdout.txt` — repair result (12 steps, budget exhausted)
- `exports/pass1_coder_20261029/src/*.ts` — the shipped files, including the degraded queue
- `_probe` measurements above taken with `nvidia-smi` and `Win32_OperatingSystem` on this box
- No spend, no Amazon request, no cloud call, no credential read, no config change to either lane.
