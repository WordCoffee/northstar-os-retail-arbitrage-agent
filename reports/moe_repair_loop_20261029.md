# Repair loop run — coder lane — 2026-10-29

## Setup
Fresh workspace `exports/moe_pipeline_repair_20261029/` (strict tsconfig, ts-jest, same package.json).
Driver: `tools/moe_repair_loop.py --generate --attempts 3`, llama-server Tiel-Coder-35B-A3B-MTP-UD-IQ3_S, 64K, MTP n=8/p=0.8, thinking off.

## Generation (4 rounds)
| # | Group | Decode | Tokens | Files |
|---|---|---|---|---|
| 1 | core | 127.2 t/s | 6,472 | types, queue, backoff, breaker, telemetry |
| 2 | runtime | 128.8 t/s | 5,230 | worker, pool, pipeline, index |
| 3 | tests | 134.7 t/s | 6,198 | 5 Jest suites |
| 4 | docs | 108.6 t/s | 3,260 | ARCHITECTURE.md |

## tsc → repair
| Stage | Exit | Errors | Changed files | Tokens |
|---|---|---|---|---|
| tsc (initial) | 2 | 12 | — | — |
| repair 1 | 2 | 12 | none (87 tokens emitted) | 87 |
| repair 2 | 2 | 10 | pool.ts, queue.ts, worker.ts | 6,869 |
| repair 3 | 2 | 10 | none (202 tokens emitted) | 202 |

**Result: ATTEMPT_LIMIT_REACHED — 10 errors remain, no green build.**

## Remaining errors (final)
- `pool.ts(313)` — `import.meta` used under `module: commonjs`
- `queue.ts(2-5)` — imports `Int32Array`, `Uint8Array`, `Atomics`, `SharedArrayBuffer` from `node:worker_threads`
- `queue.ts(55)` — `Number.isPow2` does not exist
- `worker.ts(3)` — `receiveMessageOnParentPort` (hallucinated; real API is `receiveMessageOnPort`)
- `worker.ts(74)` — `CircuitOpenError` not defined/imported
- `worker.ts(173)` — `Atomics.compareExchange` called with mismatched typed array
- `worker.ts(202)` — assigns to read-only `sharedBuffer`

## Observations
- Only one of three repair attempts produced any file blocks (attempt 2); attempts 1 and 3 returned short prose (87 / 202 tokens) and changed nothing.
- Attempt 2 fixed exactly 2 of the 12 errors (`message.value` narrowing) and left the structural ones.
- The lane cannot self-repair its own generation at this size; the repair prompt carried all 15 files (~70 KB) and the model still failed to emit targeted fixes.
- Same failure family as the one-shot run: hallucinated APIs, wrong module imports, invalid SharedArrayBuffer payload design.

## Verdict
No green build after 3 attempts. The generate→tsc→repair loop as specified does not converge with a 35B-A3B coder at IQ3_S; it needs either a stronger model, a narrower repair scope (only the failing file, one error at a time), or deterministic fixes for known-wrong patterns (worker_threads imports, import.meta, Atomics usage).

## Artifacts
- Workspace + `repair_log.jsonl` + `tsc_attempt_{0..3}.txt`: `exports/moe_pipeline_repair_20261029/`
- Driver: `tools/moe_repair_loop.py`
- Server log: `%USERPROFILE%\models\northstar-moe\server_repair.log`

## Per-file isolation run (same workspace, continued from 10 errors)
Driver: `tools/moe_repair_perfile.py --attempts 6`; each attempt sends only the highest-error file + its own errors.

| Attempt | Target | Errors left | Changed | Tokens |
|---|---|---|---|---|
| 0 (tsc) | � | 10 | � | � |
| 1 | src/worker.ts | 7 | yes | 1,689 |
| 2 | src/queue.ts | 5 | yes | 2,687 |
| 3 | src/queue.ts | 5 | yes (identical output) | 2,696 |
| 4 | src/queue.ts | 5 | yes (identical output) | 2,696 |
| 5 | src/queue.ts | 5 | yes (identical output) | 2,696 |
| 6 | src/queue.ts | 5 | yes (identical output) | 2,696 |

Result: **ATTEMPT_LIMIT_REACHED, 5 errors left.** Per-file isolation fixed 5 of 10 (worker.ts 3, queue.ts 2), then entered a deterministic repetition loop: attempts 3-6 re-emitted a byte-identical queue.ts (9,802 chars / 2,696 tokens each) at temp 0.1.

Remaining:
- `pool.ts(313)` import.meta under CommonJS
- `queue.ts(2)` still imports `Atomics` from `node:worker_threads`
- `queue.ts(52)` `Number.isPow2` does not exist
- `queue.ts(208)` `Uint8Array.writeUInt32LE` does not exist (needs DataView)
- `worker.ts(203)` assigns read-only `sharedBuffer`

Harness finding: under multi-error prompts the model drops the `=== FILE: ` header and returns a bare fenced file; the parser now falls back to the largest fence when the target header is missing.

## Retry with deterministic table + anti-repeat (v2)
Driver: `tools/moe_repair_v2.py --attempts 6` on the same workspace.

Phase A (deterministic fix table, 7 patches): added `sharedBuffer?: SharedArrayBuffer` to `RingQueueOptions`; removed the bogus `Atomics` import from `node:worker_threads`; `Number.isPow2` -> bit test; `Uint8Array.writeUInt32LE` -> `DataView.setUint32`; queue ctor accepts an existing SAB; worker passes it through options; `import.meta.url` -> `__dirname`.

| Stage | Errors |
|---|---|
| after deterministic table | 2 |
| repair 3 | 3 (model regression) |
| repair 4-6 | 2 |

Result: 2 errors left, both from the model reintroducing `Atomics.wait(this.tail, ...)` inside `TaskProcessor`. One manual replacement (1 ms sleep) -> **tsc exit 0, GREEN BUILD**.

## Jest results (real)
| Suite | Result |
|---|---|
| tests/backoff.test.ts + tests/circuit-breaker.test.ts | 22 passed, 6 failed (1.06 s) |
| tests/queue.test.ts | **hangs** � killed at 90 s |
| tests/pipeline.test.ts | **hangs** � killed at 90 s |
| tests/pool.test.ts | exit 1 |
| tsc --noEmit | exit 0 |

The queue/pipeline deadlock is the same design flaw: blocking `Atomics.wait` on the main thread stalls the event loop, so Jest cannot even time out.

## Bottom line
- Green build: **reached**, but only with 7 deterministic patches + 1 manual edit. The model never converged on its own (5 -> 2 errors, then oscillated).
- Tests: 22/28 pass in the two pure-logic suites; the queue and pipeline suites deadlock.
- This coder lane is usable as a *draft generator under a repair harness*, not as a self-verifying agent.
