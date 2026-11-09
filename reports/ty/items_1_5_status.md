# Items 1–5 — status

2026-11-09 (latest pass). Format: **VERIFIED** (with the command or artefact), **BLOCKED-ON-OWNER**
with the exact action, **BLOCKED-ON-RESOURCE** with the number that blocked it, or **FAILED** with
the diagnosis. Parked items carry a trigger and a `needs_you.md` line; none of them blocks the queue.

---

## Item 1 — real-screen control

| sub-item | verdict | evidence |
|---|---|---|
| V9-localhost through Playwright | **VERIFIED** | `tests/e2e/v9_localhost.spec.ts` → **4 passed**: Design Studio opens, "Add headline" adds a text layer, **Export PNG yields >1000 real bytes**; second spec proves the route is the studio and not the chat shell. |
| V3 + UIA parity | **BLOCKED-ON-OWNER** (parked) | Desktop locked. Trigger: `tools/unlock_watch.py` (pid 8652) polls the Win32 foreground every **300 s, no model call**, and runs `tools/ty_unlock_checks.py` on unlock. Action: **DIR-5** — turn off lock-on-idle and sleep (Settings → Accounts → Sign-in options; Power & battery). |
| Never touch the lock screen | **VERIFIED** | No code path types a password; the watcher reads the foreground title only. |
| Pixel grounding, UI-TARS | **BLOCKED-ON-RESOURCE** | Licence **Apache-2.0** (read). `UI-TARS-2B-SFT` downloaded (**9.11 GB**), CUDA stack prepared (`transformers 4.57.0` + `accelerate` into the ComfyUI venv, `torch 2.11.0+cu128`). **Model load killed during shard loading** at **3.0 GB** free RAM, no traceback. No hit rate produced, so the **61.7 % baseline stands** and **UIA + DOM stay primary**. Harness: `tools/vision/grounding_uitars.py` (`--probe` is the smallest retry). |
| Pixel grounding, OmniParser | **VERIFIED (grant only)** | Logged GRANT: `ultralytics` **AGPL-3.0, dev-only, local bench, never served, never shipped** — `reports/ty/grants.md`, tag `rollback/pre-grant-ultralytics-20261109`. Both `ultralytics` and OmniParser's **CC-BY-4.0** weights are in `replace_later.md` with the commercial-safe replacements to find. |
| Chrome Connect retained | **VERIFIED** | Six-point 6/6 (three runs). Ten-task suite `not_run` — same lock. **Not quarantined**; the condition is unmet. |

## Item 2 — reboot proof

**SETTINGS VERIFIED · BOOT PROOF PENDING (DIR-6).** Not closed, and it will not close until a
post-boot run is logged.

| sub-item | verdict | evidence |
|---|---|---|
| Task settings | **VERIFIED** | `MSFT_TaskLogonTrigger` (no end boundary), `StartWhenAvailable True`, restart 3 × 1 min, both battery stops disabled, `ExecutionTimeLimit PT0S`, `MultipleInstances IgnoreNew`. |
| Vision needs an interactive session | **VERIFIED** | `LogonType InteractiveToken`; `SetForegroundWindow`/`uiautomation` in `chrome_uia`, `mss`/`ImageGrab` in `capture`. A "run whether logged on or not" task would capture a black desktop. |
| `tools/post_reboot_check.py` | **VERIFIED (tool)** | Real run: boot `2026-11-03T17:48:04Z`, task last run `2026-11-08T09:00:15Z` result 0 — **that run predates the boot**, so it is not a post-boot proof — 14 open jobs, resume line present. 17 tests; launcher integration 6 tests. |
| Boot proof logged | **PENDING — DIR-6** | Action: **reboot once after saving work**. The launcher writes the section on its first start after boot; this row flips to VERIFIED then, and not before. |

## Item 3 — reverse-study bake-off (D17)

| sub-item | verdict | evidence |
|---|---|---|
| Hosted target a live public site | **VERIFIED** | Fresh GET of `https://opencode.ai/` → **200**, 194,113 B, `sha256 4b016d4d…3e378`, **byte-identical** to the tracked `index.html`. `research/bakeoff/targets/hosted/_fetch.json` is now tracked. The independent verifier repeated the fetch and got the same hash. |
| Accuracy against ground truth, not size or speed | **VERIFIED, with the caveat stated** | Each target declares a `facts` list read off the target; accuracy = facts found / total. Weights: **accuracy 0.40**, detail 0.25, speed 0.15, tokens 0.10, reliability 0.10 — **60 % is not accuracy**. Accuracy leaders: **oss-repo REA 10/10 vs craft-anything 9/10**; hosted **tie 7/7**; local **tie 7/7**. The composite leader on all three is craft-anything, i.e. **cheaper at equal accuracy**, and on the one target where accuracy differed **REA was more accurate**. `ty/bakeoff_results.json.accuracy_verdict`. |
| Verifier reproduced it | **VERIFIED** | `reports/ty/bakeoff_verification.md` (commit `9c8fb445`): **AGREE** on all five checks, two cells re-run from a detached worktree, the vacuous crates.io vet confirmed (404). It also caught a wrong sentence in my first accuracy verdict — corrected. |
| Six cells, tracked artefacts | **VERIFIED** | All six exit 0 with command, artefact and sha256 under `research/bakeoff/`; `run_all.ps1` reproduces any cell. |

## Item 4 — reliable image rendering

| sub-item | verdict | evidence |
|---|---|---|
| Versions | **VERIFIED** | ComfyUI venv: Python 3.14.5, **torch 2.11.0+cu128**, CUDA 12.8, **cuDNN 9.19**, capability **(12,0)**, driver **617.42**, ComfyUI **0.43.0**, upscaler **swinir**. Repo interpreter is CPU-only and never renders. |
| FLUX 3 retested with residents unloaded | **FAILED (the model path), diagnosis complete** | Contended 1024 and 1536 **succeeded**; unloaded 1024 **failed** with `hostbuf_file_reader_read failed` in `KSampler` node 107 — the **fp4 weight loader**, not cuDNN and not headroom. So fix 1 does not fix it; the fault is intermittent in the loader. |
| Measured need | **VERIFIED** | Isolated render: **89.5 s, peak 11.93 GB**. `MODEL_VRAM_GB["flux3"]` was claiming 12.4 GB at 1024 and refusing a render that works; now `(10.6, 1.3)`, and the lane waits for VRAM to settle after an unload. |
| Working path | **VERIFIED** | **SDXL at 1536 native** is the default and has produced every composite on disk; **SwinIR-M ×4** replaces Lanczos (14/18 vs 0/18, Apache-2.0). Later fixes (CUDA-13 rebuild, ComfyUI update, cuDNN disable, quantised variant) were not spent. |
| Composites re-rendered and verified | **VERIFIED** | **100 / 100 / 100**, product regions **0.9958 / 0.9928 / 0.9834**, source next to output in the digest. |

## Item 5 — staging to main

| sub-item | verdict | evidence |
|---|---|---|
| Promotion pipeline | **VERIFIED** | Three gates with evidence; 16 tests. |
| Slice promotion + review packs | **VERIFIED** | `--slice` classify/promote, per-service packs with 5–10 images, one promote and one revert command; **23 tests**. A visual refusal now writes its pack even under `--check` (a gate that refuses with nothing to show is a dead end). |
| Candidate frozen | **VERIFIED** | Annotated tag **`staging-candidate/20261109-0201`** at `269fa43a`. |
| Full suite on the candidate | **RUNNING then REPORTED** | `reports/ty/_fullsuite_candidate_20261109.txt`. The previous worktree run was **red with 32 failures**; one was a **real defect** — `roomAdapters.jsx` rendered an argument component as a JSX tag (and then spelled the tag in a comment the scanner also read) — fixed, `test_shell_role_contract` 9 passed. The rest were worktree artefacts (no `dist/`). |
| Promotion today | **BLOCKED — correctly** | `--check` refuses on **all three** gates: suite stale, **D17/V9 FAILED commits in the bundle**, **262 visual paths**. `main` untouched, no tag created. Action: **DIR-7**, read `reports/ty/staging_review_20261109.md`. |

---

## Engine-level changes in this pass

- **Free-RAM governor** (`tools/ram_governor.py`): ≥2 GB → 4 builders, <2 GB → 2, <1 GB → **pause**.
  Consulted by `claim()` and by the launcher before any session start; `caps.json` is a ceiling, not
  a target. It uses the **lower** of the psutil and Win32 readings — a governor that trusts the
  optimistic number is not a governor. 50 tests. The digest now prints free RAM and the allowance.
- **`sel-02` merged**: seller mean **22.1 → 93.5** on real generated outputs, **design-studio 75.9 →
  85.2**. It also separated the two populations honestly (generated 93.5 vs replay 29.2) and stated
  the ceiling: only **12 of 56 briefs** have a resolvable reference, so the whole-catalogue maximum
  is **21.4**.
- **At bar: 2** (`hub` 100, `prospector` 100).
