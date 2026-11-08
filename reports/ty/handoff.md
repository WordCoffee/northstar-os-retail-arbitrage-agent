# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Position: D7 next

| unit | state | tag | note |
|---|---|---|---|
| D0 baseline | done | `ty-dir-D0` | measured suite GREEN: 6617 passed, 0 failed, 117 skipped, 125 subtests, 6736 ids |
| D1 probe | done | `ty-dir-D1` | 4/4 concurrent sessions; **Ollama runs 100% CPU** (see below) |
| D2 launcher | done | `ty-dir-D2` | killed pid 32556 → restarted pid 25644 in 5 s; heartbeat starts nothing |
| D3 queue | done | `ty-dir-D3` | overlap serialised; main refuses without the verifier |
| D4 scorecards | done | `ty-dir-D4` | 29 services, bar is **per dimension**, 0 of 29 at bar |
| D5 gaps | done | `ty-dir-D5` | gaps → bundles; empty queue writes a defect, never idles |
| D6 vision privacy | done | `ty-dir-D6` | V5 + V7 pass, including a real blocked window |
| D7 vision understanding | done | `ty-dir-D7` | V1 (llava, 0.8 s JSON), V2 (20/20 element reads), V8 (10.29 GB with Bojo) |
| **D8 control/browser** | **next** | — | risk classes, verify-after-act, Profile 6, Chrome Connect parity |
| D9–D15 | pending | — | seller-tester, visual regression, intel, builders, live mode, PC mode, verification |
| D16 model scout | continuous | — | per-role incumbents, benchmark, quarantine + restore |
| D17 bake-off | pending | — | REA vs Craft Anything on three targets |

## The D1 blocker is resolved — do not repeat the old conclusion

`reports/ty/director_probe.md` once said "Ollama cannot see this GPU". **That was wrong.**
Ollama was *told* not to look: `OLLAMA_LLM_LIBRARY=cpu` and `OLLAMA_NUM_GPU=0` were
pinned in the User environment, and `bojo:latest` additionally baked `PARAMETER num_gpu 0`
into its Modelfile. Cleared the pins, quarantined Bojo as `bojo:cpu-quarantine`, rebuilt
`bojo:latest` without the parameter. Discovery is now
`library=CUDA compute=12.0 name=CUDA0 driver=13.4 libdirs=ollama,cuda_v13`.

Full write-up: `reports/ty/d7_gpu_diagnosis.md`. No Ollama upgrade, no `llama-server`
switch and no llama.cpp build were needed — those steps remain unspent.

| role | model | processor | VRAM used | RAM free |
|---|---|---|---|---|
| Bojo router | `bojo:latest` | 100% GPU | 3.07 GB | 6.20 GB |
| planner/coder | `qwen3:8b` | 100% GPU | 6.63 GB | 6.20 GB |
| vision | `qwen2.5vl:7b` | 100% GPU | 7.41 GB | 6.41 GB |
| embeddings | `qwen3-embedding:0.6b` | 100% GPU | 2.08 GB | 6.55 GB |

Idle: 15.63 GB VRAM free, 7.23 GB RAM free. `OLLAMA_MAX_LOADED_MODELS=1` stays until a
two-model soak proves the UI stays responsive; Bojo + vision together measure 10.48 GB.

## D7 result — structure first, and a measured model choice

The UI Automation path is the primary read and it is deterministic: **V2 passed 20/20**
against a real WinForms window, including reading a field's value back. No model was
involved, which is the point.

The VLM path needed a model. Three installed candidates were measured
(`reports/ty/d7_vision_benchmark.md`): `qwen2.5vl:7b` degenerate, `moondream` degenerate,
**`llava:7b` correct** — valid JSON naming Visual Studio Code in 0.8 s at 100 % GPU. The
default is now `llava:7b` because it passed, not because it was listed first.

Two engineering fixes came out of it: frames are downscaled to 1280 wide before encoding
(a 2560×1600 frame made the encoder fail with `std::bad_alloc`), and vision keeps Bojo as
its only companion because all three residents starved the encoder.

**D8 next.** Note for D8: `free_comfy()` answers 200 but releases nothing on this build —
it is reported as `verified: false` until a reading actually moves. Do not trust the
acknowledgement.

## Numbers to keep in mind

- One real worker cycle measured 25,789 tokens (small fix) and 83,710–127,914 (scanner
  work); the daily cap is 3,000,000 with a stop at 90%.
- Screens: 1 monitor, 2560×1600. GPU 16,303 MB total, 16,003 MB free idle.
- Disk free: ~10.4 GB. The work order pauses GPU/download work below 10 GB.
- The old autonomy loop is halted; `scripts/tys_*` remain for their tests only.

## Rules that are easy to get wrong

- `state/` is gitignored: anything a fresh checkout needs must also live under `ty/`
  (that is why `ty/services.json` exists).
- A per-dimension bar means an 85 average is not a pass. `ty/scorecards.json` says so.
- The launcher's pid file is authoritative; the command-line scan is only a fallback.
- Never leave a debug script behind; every temporary tool in this session was removed.

- 2026-11-08T08:58:49+00:00 queue empty while 26 service(s) are below the bar (worst: prospector); re-plan, do not idle.

- 2026-11-08T08:58:59+00:00 launcher: director session ended (session 32136 gone; launcher restarting).

- 2026-11-08T08:59:36+00:00 queue empty while 26 service(s) are below the bar (worst: prospector); re-plan, do not idle.

- 2026-11-08T08:59:47+00:00 launcher: director session ended (session 27276 gone; launcher restarting).

- 2026-11-08T08:59:53+00:00 queue empty while 26 service(s) are below the bar (worst: prospector); re-plan, do not idle.
