# Coding agent loop + Tys Assistant wiring — 2026-10-29

## What was added
| File | Purpose |
|---|---|
| `Northstar_backend/agent_kernel/local_model.py` | `LlamaCppModel` (prompt → text) over llama-server `/v1/chat/completions`; thinking off by default, one retry on reasoning-only answers; `make_local_model()` reads `TYS_CODING_*`; `health()` |
| `Northstar_backend/agent_kernel/coding_runner.py` | `CodingTask` + `run_coding_task()` — wires the existing loop, rooted workspace and acceptance |
| `Northstar_backend/agent_kernel/coding_tools.py` | `write_many` (batched atomic writes), `npx tsc` / `npx jest` / `npm run` in the allowlist, Windows `.cmd` resolution for `run` |
| `Northstar_backend/agent_kernel/coding_agent.py` | schema advertises `write_many`; acceptance shortcut includes it |
| `Northstar_backend/agent_kernel/tys_adapter.py` | acceptance commands resolve `.cmd` (Windows `npx`) |
| `Northstar_backend/tys_assistant.py` | `CodingWorkerAdapter.run_agent()` + `params.mode="agent"` routing; GPU lock, on-demand start/stop, StepResult mapping |
| `scripts/start-northstar-llm.ps1` | points at `northstar-moe\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` (alias unchanged) |
| `shared/model-suite.json` | `local_engines.ty`: weights 10.44 GB, VRAM 12.8 GB, 76 tok/s, 13.2 ms/token |
| `tools/run_coding_agent.py` | CLI entry point against the same runner |
| `Northstar_backend/test_local_model.py`, `test_coding_runner.py` | 4 + 2 tests |

## Tys Assistant usage
A coding step opts in per step:

```json
{"lane": "coding", "objective": "build X",
 "params": {"mode": "agent", "workspace": "exports/agent_ws",
            "acceptance_commands": [["npx", "tsc", "--noEmit"]],
            "acceptance_files": ["src/index.ts"],
            "max_steps": 24, "max_repairs": 2}}
```

Env: `TYS_CODING_URL` (default http://127.0.0.1:8080), `TYS_CODING_MODEL` (northstaros-qwen3.8:27b), `TYS_CODING_LAUNCHER` (scripts/start-northstar-llm.ps1), `TYS_CODING_MAX_TOKENS` (4096), `TYS_CODING_TIMEOUT_S` (600).

## Verification
- Unit/integration: **116 passed** (`test_local_model`, `test_coding_runner`, `test_coding_agent`, `test_coding_guardrails`, `test_tys_routing`, `test_agent_kernel`).
- E2E scoped task (`exports/agent_ws`): 3 steps, wrote 2 files, `npx tsc --noEmit` exit 0.

## Architect task through the loop
| Workspace | Run | Steps | Result |
|---|---|---|---|
| `exports/agent_arch` | build | 24 | 6/9 files, budget exhausted |
| `exports/agent_arch` | continue | 28 | +worker.ts, 3 null-check errors |
| `exports/agent_arch` | continue | 20 | worker.ts rewritten, still incomplete |
| `exports/agent_arch2` | build with `write_many` | 14 | 9/9 files in one call, 1 literal `\n` defect |
| `exports/agent_arch2` | repair | 2 | **green: `npx tsc --noEmit` exit 0** |

Final state: 9 files (376–2478 bytes each), strict TypeScript, independently verified `tsc_exit=0`.

## Finding
One-file-per-turn makes a multi-file build starve its step budget; `write_many` fixes that. The 27B still spends most turns verifying rather than writing, so budgets of ~14–20 steps per objective are realistic. The loop itself converges: every green came from acceptance, not from the model's claim.

## v2 build (schema + q8_0 KV + builder profile)
Implemented and verified:

| Change | Evidence |
|---|---|
| esponse_format: json_schema on every model call (tool enum) | Server test returned valid tool JSON; measured VRAM with q8_0 KV = **13,782 MiB (13.83 GiB)** |
| q8_0 KV for the coder lane (scripts/start-northstar-moe.ps1, bench) | 13.83 GiB at 64K, inside the 13�14 GiB envelope |
| Builder profile (--builder) + TS scaffold (--scaffold) | coding_runner.BUILDER_PREFIX, ensure_ts_scaffold; unit-tested |
| Acceptance checked even when the model call raises | coding_agent returns cceptance_recovered instead of "model call failed" |
| Failing files injected into the repair prompt | _note_failure + _failing_block (4 files � 6 KB) |
| Read-streak guard | 2 consecutive reads inject "STOP READING, write now" |
| Acceptance detail 300 ? 2000 chars | full tsc error list reaches the model |

Tests: **180 passed** (local model, runner, loop, guardrails, Tys routing, kernel, Tys assistant).

### Architect run, v2
| Workspace | Steps | Result |
|---|---|---|
| exports/agent_arch3 (schema + q8_0, no builder) | 6 | all 9 files written in one write_many; model-call failure; acceptance now recovered on that path |
| exports/agent_arch3 repair | 14 | writes happen (2 + 1 files); tsc still red |
| exports/agent_arch4 (schema + builder + scaffold) | 16 | 9/9 files written in one call; **6 errors left, all TS2300 duplicate identifier in pipeline.ts** |

The model's residual defect is systematic: it declares a class field **and** a constructor parameter property with the same name (private telemetry: T; plus constructor(private telemetry: T)). It repeats that pattern across rewrites even with the file content injected.

### Status
- Harness: complete, tested, Tys-wired.
- Model: converges on scoped tasks (3 steps, green) but does not self-converge on a 9-file build; the loop stops at the step budget with 6 duplicate-identifier errors.
- The only remaining lever that changes this is model class (needs =64 GB RAM for an 80B-A3B), not another harness tweak.
