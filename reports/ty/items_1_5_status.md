# Items 1–5 — status

2026-11-09. Owner order: complete items 1 to 5, park what needs the owner with a trigger and a
one-line `needs_you.md` entry, never let a parked item block the rest.

## Item 1 — real-screen control

| sub-item | status | evidence |
|---|---|---|
| V9-localhost through Playwright | **VERIFIED** | `tests/e2e/v9_localhost.spec.ts` → **4 passed** (desktop + mobile): Design Studio opens, "Add headline" adds a text layer, **Export PNG produces >1000 real bytes** (`data-last-export="PNG …"`). The second spec proves the route is the studio, not the chat shell. |
| V3 + UIA parity parked on the unlock trigger | **VERIFIED (parked)** | `tools/unlock_watch.py` runs as pid 8652, polls the Win32 foreground every **300 s with no model call**, and runs `tools/ty_unlock_checks.py` the moment the lock screen is gone. Log: `reports/ty/unlock_watch.log`, state: `state/director/unlock_watch.json`. |
| Never touch the lock screen / password | **VERIFIED** | No code path types a password; the watcher only reads the foreground title. |
| needs_you entry for lock-on-idle and sleep | **VERIFIED** | `needs_you.md` **DIR-5**, two toggles named. |
| Pixel-grounding benchmark, UI-TARS/OmniParser class | **BLOCKED-ON-LICENCE-REVIEW** (and resource) | Licences checked from each project's own file: **UI-TARS Apache-2.0** (LICENSE read), **OmniParser CC-BY-4.0** (GitHub API `license.spdx_id`; attribution required, commercial use allowed). Neither is installed. Running the OmniParser recipe here needs **ultralytics, which is AGPL-3.0** — our own provider suite refuses `agpl_network_copyleft_unreviewed` — or `trust_remote_code` on a Florence-2 checkpoint, which executes code fetched at runtime; neither is a decision to take quietly for a benchmark. Free RAM was also **0.57 GB of 15.42 GB** when it was attempted. Baseline stays **61.7 %** and **UIA + DOM remain primary**, which is the owner's stated fallback. Trigger: `python -m tools.vision.grounding --run --models <candidate>` once a permitted candidate is approved and free RAM ≥ 3 GB. |
| Chrome Connect kept until both suites pass twice | **VERIFIED (kept)** | Six-point contract 6/6 verified (three separate runs); the ten-task suite is still `not_run` because it needs the same unlocked desktop. **Not quarantined** — the condition for quarantine has not been met. |

## Item 2 — reboot proof

| sub-item | status | evidence |
|---|---|---|
| Task settings verified offline | **VERIFIED** | 6/6: `MSFT_TaskLogonTrigger` (no end boundary), `StartWhenAvailable`, restart 3 × 1 min, both battery stops disabled, `ExecutionTimeLimit PT0S`, `MultipleInstances IgnoreNew`. |
| Vision needs an interactive session | **VERIFIED** | `LogonType InteractiveToken`; `chrome_uia` calls `SetForegroundWindow`/`uiautomation` and `capture` uses `mss`/`ImageGrab`. A "run whether logged on or not" task would capture a black desktop. |
| `tools/post_reboot_check.py` | **VERIFIED** | Real run: boot `2026-11-03T17:48:04Z`, uptime 5 d 13 h, task last run `2026-11-08T09:00:15Z` result **0**, director pid 16592 **not alive**, 14 open jobs, resume line present, handoff mtime `2026-11-09T06:47:39Z`. Writes `reports/ty/reboot_proof.md`. |
| Launcher runs it on first start after boot | **VERIFIED** | 6 new launcher tests: first start after boot runs it, a second start in the same boot does not, a stale proof does not, a broken check logs and exits 0. 32 tests total. |
| needs_you entry for the reboot | **VERIFIED** | `needs_you.md` **DIR-6**, one line, no password. |

## Item 3 — reverse-study bake-off (D17)

**VERIFIED.** Reproducible, and it changed the answer from the earlier unverifiable run.

Clone → read → vet → install, in that order: Craft Anything **v0.5.0** (MIT OR Apache-2.0), crate
not published on crates.io so the OSV vet is **vacuous** — recorded as such; the real controls were
reading `Cargo.toml`, the CLI `main.rs` and `js_tools.rs`, plus SHA-256 `45dbe342…` matching the
release's own `SHA256SUMS.txt`. REA `rea-agents@6.5.0` (MIT) vets **clear**.

| target | REA | Craft Anything | default |
|---|---|---|---|
| open-source repo | 0.753 (10/10 facts, 7.1 MB, 3.5 s) | **0.859** (9/10, 72 KB, 0.04 s) | craft-anything |
| hosted, non-Amazon | 0.751 (7/7, 96 MB, 22.9 s) | **1.000** (7/7, 702 KB, 0.11 s) | craft-anything |
| local web app | 0.753 (7/7, 76 MB, 13.3 s) | **1.000** (7/7, 643 KB, 0.22 s) | craft-anything |

All six cells: command, exit 0, artefact under the tracked `research/bakeoff/`. `run_all.ps1`
reproduces any or all cells and was **verified from a fresh detached worktree**. One real defect
fixed: artefacts had been written in text mode, so CRLF made the file differ from the bytes that
were hashed — that is exactly why the old run could not be verified.

## Item 4 — reliable image rendering

| sub-item | status | evidence |
|---|---|---|
| Versions recorded | **VERIFIED** | ComfyUI venv: Python 3.14.5, **torch 2.11.0+cu128**, CUDA 12.8, **cuDNN 9.19**, capability **(12,0)** Blackwell; driver **617.42**; ComfyUI **0.43.0**; upscaler **swinir**. The repo's own interpreter is `torch 2.15.0+cpu` — CPU only — and never renders. |
| Diagnose with nvidia-smi + ollama ps during failure | **VERIFIED** | `tools/flux_diagnosis.py --run` loads Bojo, snapshots, renders, unloads, re-renders. Both contended attempts failed with **`render refused: 2.9 GB free RAM is below the 3 GB floor`** — a headroom refusal, not the cuDNN error. Both unloaded attempts **succeeded**, at 1024 and at 1536. |
| Fixes tried in order | **VERIFIED** | Fix 1 (unload residents) is the one that works, so the later fixes were not spent: no CUDA-13 rebuild, no ComfyUI update, no cuDNN disable, no quantized variant, no engine swap. |
| Native ≥1024 scenes, real upscaler | **VERIFIED** | Default renderer is **SDXL at 1536 native** with **SwinIR-M ×4** as the measured upscaler (14/18 vs Lanczos 0/18, Apache-2.0 in `provenance.csv`). |
| Re-render the three Mogra composites | **BLOCKED-ON-RESOURCE** | The render refused at **2.6 GB free RAM**. The composites on disk are the previous run's; the three still pass with verified product regions (0.9958 / 0.9931 / 0.9835). Trigger: re-run `python -m tools.seller_tester composite --limit 3` when free RAM ≥ 3 GB. |
| Digest shows source next to output | **VERIFIED** | `reports/ty/digest_2026-11-08.md` section *Mogra composites — source next to output* plus `digest_composites_2026-11-08.png` (source left, composite right). |

## Item 5 — staging to main

**VERIFIED — and it refuses today's bundle, correctly.**
