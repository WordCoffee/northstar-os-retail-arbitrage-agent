# Local-model benchmarks, re-measured on GPU (2026-11-07)

Every earlier local-model benchmark in this repository was measured while Ollama was
pinned to the CPU. Those numbers are real, but they describe a different machine. This
file is the replacement baseline; the old artifacts carry a banner pointing here.

Raw data: `reports/ty/local_bench_gpu_20261107.json`,
`reports/ty/model_bench_bojo_gpu_20261107.json`.

## Throughput and time-to-first-token, per role (GPU)

`python tools/local_bench.py` — three repeats, median, `num_predict` 128, measured from
Ollama's own `eval_count` / `eval_duration` fields.

| role | model | device | tokens/s | TTFT | wall |
|---|---|---|---|---|---|
| Bojo router | `bojo:latest` | **100% GPU** | **218.4** | 0.020 s | 0.64 s |
| planner / coder | `qwen3:8b` | **100% GPU** | **111.3** | 0.010 s | 1.20 s |
| vision | `qwen2.5vl:7b` | **100% GPU** | **128.6** | 0.009 s | 0.26 s |
| embeddings | `qwen3-embedding:0.6b` | **100% GPU** | — | — | 868 ms/text |

The embeddings figure is per-text round trip including the HTTP call, not a batches-per-
second number; 5 texts took 4.34 s in total.

## Bojo manager capability, re-run on GPU

`python tools/model_bench.py --model bojo:latest` — the same three manager prompts and
deterministic scoring the blueprint defines, unchanged.

| model | device | score | mean latency |
|---|---|---|---|
| `bojo:latest` | **100% GPU** | **6/18 (33.3 %)** | 3.0 s |

No earlier run of this harness against the current Bojo exists, so this is a **baseline**,
not a replacement. The score is a capability number: moving to the GPU changes latency,
not whether the model answers correctly. 33 % on the manager rubric is a capability gap
worth a D5 job; it is not a GPU problem.

## What was measured on CPU before, and is now superseded

| artifact | model | old result (CPU) | disposition |
|---|---|---|---|
| `bench_full.md` | `northstaros-qwen3.8:27b` | 5 tasks, pass 0.60, avg 19.28 s, total 96.4 s | superseded — the 27B now runs on `llama-server` at `-ngl 99`; re-run belongs to D8's browser suite |
| `bench_coder.md` | `qwen3.8-27b-coder:latest` | pass 0.60, avg 17.85 s, total 89.2 s | superseded, same reason |
| `bench_ctx64k.md` | `northstaros-qwen3.8:27b-ctx64k-orig` | pass 0.667, avg 15.80 s, total 47.4 s | superseded, same reason |
| `00_STATE.json` → `ty_repair_readiness_20261101` | `qwen2.5-coder:3b` | blocked at 4.57 GB available; "GPU 16 GB free and unused" | **cause removed** — the 3B now measures 2.08-3.07 GB of *VRAM* per role, not RAM |
| `reports/ty/A10_spike_verdict.md` | local coding lane | 0/5 patches authored | **unchanged, deliberately** — the verdict was about capability, not speed. A faster CPU-bound engine does not make the lane able to author patches, and re-running it on GPU would produce the same 0/5 for the same reason |

The 27B's three ChromeConnect benches are **not** re-run here on purpose. They measure a
browser task through a controller that D8 is replacing, against a model served by a
different engine (`llama-server`, not Ollama). Re-running them against the old harness
would produce a number nobody can compare to anything.

## The one number that matters for the programme

The autonomy loop stalled for a week on a RAM floor (`4.57 GB available`, "GPU 16 GB free
and unused"). With the pins removed, the same roles occupy **VRAM** — 2.08 GB for
embeddings, 3.07 GB for Bojo, 6.63 GB for the coder, 7.41 GB for vision — and leave
**5.4-7.7 GB of system RAM free**. The floor that blocked the work is gone, and it was
never a hardware limit.
