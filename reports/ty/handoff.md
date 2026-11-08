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
| **D7 understanding** | **next** | — | structure-first (UIA + DevTools), then the VLM benchmark |
| D8 control/browser | pending | — | risk classes, verify-after-act, Profile 6, Chrome Connect parity |
| D9–D15 | pending | — | seller-tester, visual regression, intel, builders, live mode, PC mode, verification |
| D16 model scout | continuous | — | per-role incumbents, benchmark, quarantine + restore |
| D17 bake-off | pending | — | REA vs Craft Anything on three targets |

## The one blocker D1 found, which D7 inherits

**Ollama cannot see this GPU.** `qwen2.5vl:7b` loads 7.4 GB into *system RAM* at 100% CPU
and 0 VRAM; the server log says `library=cpu`, `driver=""`, "no usable GPU found" ×4.
A fresh server with `CUDA_VISIBLE_DEVICES=0` behaves identically, so it is not the
environment: the bundled runner cannot see the RTX 5080 (sm_120, driver CUDA UMD 13.4).
One 7B load leaves 0.5–0.9 GB of RAM free, so two models resident at once is impossible
today. `state/director/caps.json` records the consequence.

D7 must therefore start with **structure first** (UI Automation tree + browser DevTools
protocol), which is also what the work order asks for, and treat the VLM benchmark as a
runtime decision: upgrade Ollama to a CUDA-13 build, or use llama.cpp with CUDA, or keep
vision on CPU within an explicit latency budget. ComfyUI is the GPU path that works.

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
