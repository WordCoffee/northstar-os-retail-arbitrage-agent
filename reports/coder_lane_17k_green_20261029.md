# Coder lane at 17K: 7 errors → 1 error → green, zero patches

**Date:** 2026-10-29, 19:53–20:20
**Lane:** `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp`, llama.cpp `b11889-d854d98ba`
**Config:** `-c 17408` (17K), `-ngl 99`, `-fa on`, `-ctk/-ctv q8_0`, MTP `draft-mtp n=8 p-min 0.8`
**Outcome:** **`npx tsc --noEmit` exit 0** on the 9-file concurrency spec, **0 deterministic patches**, 28 model steps total.

---

## 1. The four runs, side by side

| # | Context | Rewrite gate | Steps | `tsc` errors | SharedArrayBuffer queue |
|---|---|---|---|---|---|
| 1 | 64K | no | 5 + 12 | 7 | **deleted** → plain `Task[]` |
| 2 | 17K | no | 24 (exhausted) | 7 | kept |
| 3 | 17K | **yes** | 24 (exhausted) | **1** | kept |
| 4 | 17K | yes | **2** | **0** | kept |

Run 4 was a scoped repair: `REPAIR_ONE.md` named the single remaining error and restricted the
write to `src/worker.ts`. It read the file once, wrote it once, acceptance returned
`PASS: missing=[]; failures=[]`. Independently re-verified outside the harness: `TSC_EXIT=0`.

**28 model steps, 0 human edits, 0 deterministic patches.** The `FIXES` table in
`tools/moe_repair_v2.py` was not used and was not needed.

## 2. What actually unblocked it

Not the model, the loop. In run 2, **17 of 24 steps were bare `run` calls** returning `exit 2`
with no edit between them — a compiler that cannot change its answer, asked repeatedly.

`Northstar_backend/agent_kernel/coding_agent.py` now:

- refuses a `run` when acceptance already failed and no file changed since, and returns a
  `verify_stall` observation instead of burning the step on the same compiler output;
- injects `VERIFY STALL: … the only way forward is to change files` into the next prompt;
- clears the latch on any `write` / `write_many` / `apply_patch`.

Fired **5 times** in run 3 and each refusal was followed by a real rewrite. Regression test:
`test_repeated_acceptance_run_after_failure_is_refused` (asserts step 1 runs, steps 2–4 refused).
`test_coding_agent` + `test_coding_runner` + `test_local_model`: **28 passed**; after adding the
test, 23 passed in the same two files.

## 3. The bug the model could not see, and then saw

Run 3's last error:

```
src/worker.ts(26,20): TS2769 — Argument of type 'SharedArrayBuffer' is not
assignable to parameter of type 'Int32Array'
    Atomics.wait(queue.sharedBuffer, 0, 1, 100);
```

The model had the **architecture** right — `Atomics.wait` belongs in the worker, and the main
thread uses `setTimeout(0)` polling — and only the argument type wrong. Given the error text
scoped to one file, it fixed it in one write.

## 4. Hardware, measured

| Metric | 64K + q8_0 | **17K + q8_0** |
|---|---|---|
| VRAM used | 14,158 / 16,303 MiB | **12,152 / 16,303 MiB** |
| VRAM free | 1,846 MiB | **3,852 MiB** |
| Private commit (`llama-server`) | 16.59 GB | ~8.5 GB free commit observed across the run |
| ComfyUI required off | **yes** (compiler died `0xC0000409` at 0.70 GB commit free) | **no** — `tsc` ran repeatedly during the build |

17K is the working point on this box: it preserves the spec **and** leaves the compiler its headroom.
The 64K lane is fine as pure inference and fatal as a co-resident build environment.

## 5. Honest limits

1. **n = 1 per configuration.** These are single samples, not pass@k. Run 1 (64K) gutting the queue
   and run 2 (17K) keeping it may be sampling noise as much as a context effect — the falsifiable
   claim is narrower: *at 17K with the rewrite gate, this spec reached green once, in 28 steps.*
2. **Step 4 of the plan (both lanes through `tools/flux3_gateway.py`) is still not done.**
   The gateway itself is healthy (`:8190` → `status ok`, all three FLUX 3 weights present).
3. **Creative lane (`IQ3_S-mtp`) is still unproven** for full un-truncated file output.
4. **No Jest suite exists** in any generated workspace — `package.json` carries only
   `typescript` and `@types/node`. "Jest continuously" remains unbuilt.
5. A **read loop** replaced the run loop as the remaining waste pattern in run 3 (queue.ts read 5×,
   tsconfig 3×). Same class of defect, not yet gated.
6. **ComfyUI is stopped** (pid 23772, stopped for the 64K test) and was **not** restarted: with the
   17K lane resident only 3,852 MiB of VRAM is free, less than the 4.92 GB FLUX 3 transformer needs.
   Start it with `tools/start_comfyui.ps1` once the lane is stopped.

## 6. What this changes in the plan

Phase 3's premise — "the legacy lane failed autonomous convergence, so replace the model" — was
half right. The model **did** need to be the 27B (spec fidelity collapsed on the older MoE), but the
convergence blocker was the loop handing it a compiler it could not satisfy. Two gates (no-op run,
scoped repair) turned 7 errors into 1 and 1 into 0.

Recommended next: run the same spec 3× to get a real pass@3, then the creative lane on the same
harness, then Step 4 through the FLUX 3 gateway.

## 7. Evidence

- `exports/pass1_coder_17k_20261029/run_stdout.txt` — run 2 (7 errors, 24 steps)
- `exports/pass1_coder_17k_v2_20261029/run_stdout.txt` — run 3 (1 error, 24 steps, 5 refusals)
- `exports/pass1_coder_17k_v2_20261029/repair_one_stdout.txt` — run 4 (green, 2 steps)
- `exports/pass1_coder_17k_v2_20261029/src/*.ts` — the green tree, `queue.ts` still SharedArrayBuffer
- `Northstar_backend/agent_kernel/coding_agent.py`, `Northstar_backend/test_coding_agent.py`
- No spend, no Amazon request, no cloud call, no credential read, no change to either lane's model config.
