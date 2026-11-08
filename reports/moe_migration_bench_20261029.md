# MoE migration + model bench — 2026-10-29

## Hardware (measured)
- GPU: RTX 5080 Laptop, 16,303 MiB VRAM, 896 GB/s
- RAM: 16 GB (2×8 GB)
- Disk before: 45.8 GiB free → after install: 21.3 GiB free

## Removed
- `northstaros-qwen3.8:27b` (Qwen3.8-27B GSQ-RCO IQ3_XXS-mtp, 9.73 GiB) and its `.cache`; llama-server PID 29288 stopped first (file lock).
- Ollama models untouched: bojo, qwen3.5:2b, qwen2.5vl:7b (vision), qwen3-embedding.

## Installed (`%USERPROFILE%\models\northstar-moe`)
| Lane | File | Size | License | Quant |
|---|---|---|---|---|
| coder | `Tiel-Coder-35B-A3B-MTP-UD-IQ3_S.gguf` | 13.10 GiB | MIT | UD-IQ3_S + MTP |
| creative | `Qwen3.6-35B-A3B-UD-IQ3_S.gguf` | 14.29 GiB | Apache-2.0 | UD-IQ3_S + MTP |

Both architectures: 35B total, ~3B active, 40 layers = 30 linear attention + 10 full attention, 2 KV heads × 256 dim.
**KV at 64K, q4_0 = 0.35 GiB** (hybrid attention makes context cheap; 128K adds only 0.35 GiB more).

## Runtime config
`scripts/start-northstar-moe.ps1 -Lane coder|creative [-Ctx 65536] [-Ncmoe 0]`

```
-ngl 99 -c 65536 -fa on -ctk q4_0 -ctv q4_0 -np 1 --jinja -b 2048 -ub 512
--spec-type draft-mtp --spec-draft-n-max 8 --spec-draft-p-min 0.8 --temp 0.35
```

Measured peak VRAM (creative): **14.76 GiB → 1.5 GiB headroom** at 64K.

## Bench — architect prompt (`tests/bench/architect_prompt.txt`)
Harness: `scripts/bench-northstar-moe.ps1 -Lane X -Workload architect [-Think]`, temp 0.2, n_predict 8192.

### Thinking ON (`enable_thinking=true`)
| Lane | decode t/s | prompt t/s | tokens | result |
|---|---|---|---|---|
| coder | 111.5 | 427.1 | 8192 | all tokens consumed as reasoning, empty answer |
| creative | 137.6 | 239.9 | 8192 | all tokens consumed as reasoning, empty answer |

`enable_thinking` needs a far larger budget (16–32K) or a reasoning token cap before any deliverable appears.

### Thinking OFF
| Lane | decode t/s | prompt t/s | tokens | answer chars | TS blocks | Jest calls | placeholder hits |
|---|---|---|---|---|---|---|---|
| coder | **123.8** | 436.3 | 3836 | 14,167 | 7 | 0 | 2 (self-admitted) |
| creative | **131.2** | 256.4 | 4630 | 17,836 | 2 | 6 | 0 |

### Quality vs the brief
- **Coder (Tiel):** delivered partial core — `CircuitBreaker` state machine, `ExponentialBackoff` with jitter, `BoundedQueue` with backpressure, pipeline wiring. Explicitly flagged that worker IPC plumbing and the retry loop are incomplete/placeholder and asked which direction to take. **Did not meet** "fully implemented, no placeholders, Jest suite".
- **Creative (Qwen3.6):** delivered an architecture document (overview, testing strategy, config, trade-offs, conclusion) with only 2 code blocks; no full engine, no real test suite. **Did not meet** the implementation requirements.
- Neither model one-shots an enterprise refactor of this size in ~4K output tokens. The task needs agentic multi-turn/file-based delivery.

### Operational findings
- Raw `/completion` on the Qwen3.6 instruct model returns `stop_type=eos` after 2 newline tokens — it requires `/v1/chat/completions` with the chat template. Harness now uses chat completions.
- Harness must read `message.reasoning_content` separately from `message.content`.

## Artifacts
- `scripts/start-northstar-moe.ps1` — lane launcher (64K, MTP, 64K KV q4_0)
- `scripts/bench-northstar-moe.ps1` — load + bench harness
- `tests/bench/architect_prompt.txt` — exact bench prompt
- `%USERPROFILE%\models\northstar-moe\out_*.md`, `bench_*.json` — raw outputs + timings

## Next options
1. Bench with thinking ON at 32K budget to see if either model completes the full deliverable.
2. Run the coder lane as an agentic loop (multi-turn, file writes) instead of one-shot.
3. 128K context for the coder lane (~1.3 GiB headroom); `-Ncmoe 2` fallback if a build OOMs.
