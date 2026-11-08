# Agentic MoE build — coder lane, 4 rounds — 2026-10-29

## Method
`tools/moe_agentic_build.py` against `llama-server` (Tiel-Coder-35B-A3B-MTP-UD-IQ3_S, 64K, MTP n=8/p=0.8, thinking off).
The architect brief (`tests/bench/architect_prompt.txt`) is the system prompt; one round per file group; the model must emit
`=== FILE: path ===` blocks only. Workspace: `exports/moe_pipeline_20261029/` (package.json, tsconfig strict, ts-jest provided by us).

## Rounds (measured)
| # | Group | Files | Decode | Prompt | Tokens | Seconds |
|---|---|---|---|---|---|---|
| 1 | core | types, queue, backoff, circuit-breaker, telemetry | 121.3 t/s | 541.7 | 5,650 | 47.6 |
| 2 | runtime | worker, pool, pipeline, index | 123.4 t/s | 540.3 | 5,955 | 48.5 |
| 3 | tests | 5 Jest suites | 130.8 t/s | 632.1 | 5,975 | 45.9 |
| 4 | docs | ARCHITECTURE.md | 106.2 t/s | 2,434.7 | 2,623 | 27.2 |

Total: **15 files, 1,918 lines, 68.9 KB** in ~2m 50s wall (20,203 tokens).

## Validation (actual)
`npx tsc --noEmit` → **exit 2**.

1 syntax error (unbalanced parens in `queue.ts:93`) + 11 strict-type errors:

| File | Error |
|---|---|
| `src/queue.ts:1` | imports `Atomics`/`SharedArrayBuffer` from `node:worker_threads` — neither is exported there |
| `src/worker.ts:3` | imports `receiveMessageOnParentPort` — API does not exist (real: `receiveMessageOnPort`) |
| `src/worker.ts:114` | `RingQueue.isEmpty` called but not implemented |
| `src/worker.ts:147` | result literal `durationMs` not in the declared union |
| `src/worker.ts:256` | message type compared against `'config'`, not in the union |
| `src/pool.ts:99,100` | `config.workerCount` accessed after `Omit<..., "workerCount">` |
| `src/pool.ts:141` | `WorkerEntry.handler` does not exist |
| `src/pool.ts:154` | `Task<T>` passed where `Task<Task<T>>` expected |
| `tests/pool.test.ts:145,169` | `event` is `unknown` under strict |
| `tests/pipeline.test.ts:44` | `MockPool` not assignable to `WorkerPool` |

Design-level defect: `src/queue.ts` stores payloads with `this.dataView.setBigInt64(offset, item as unknown as bigint, true)` —
JS object references cannot live in a `SharedArrayBuffer`; the "lock-free queue" is structurally invalid, not just mistyped.

Placeholders: 2 hits (`TODO`/`placeholder`) despite the brief forbidding them.

Tests: 5 suites, ~50 `describe/it/test` blocks, 13 real imports — **cannot run** because the sources do not compile.

## Verdict
The coder lane produces plausible, well-shaped, fast output (120-130 t/s, correct file layout, real imports, test blocks) but
**does not deliver a compiling, strictly-typed implementation**. Claimed properties (strict type safety, no placeholders,
working lock-free queue) are false on inspection. Single-shot and 4-round multi-turn both fail the "production-ready" bar;
multi-turn improves coverage, not correctness.

The failure mode is characteristic: confident code with hallucinated APIs (`receiveMessageOnParentPort`, Atomics import) and a
design that ignores the runtime constraint (objects in SAB). Expect the same from the creative lane at this size.

## Artifacts
- Workspace: `exports/moe_pipeline_20261029/` (src/, tests/, docs/, agentic_log.jsonl)
- Driver: `tools/moe_agentic_build.py`
- Server log: `%USERPROFILE%\models\northstar-moe\server_agentic.log`
