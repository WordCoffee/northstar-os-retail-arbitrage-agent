# Ty autonomy — measured residency, model-authored work, recovery (2026-11-01)

**Directive:** continue the unfinished Ty autonomy programme. **Result: two of six
gates closed, one gate blocked with evidence, three gated by that block.**
No Amazon, no spend, no credential read, no browser, no external provider.
The operator's Ollama configuration was restored unchanged at the end.

---

## 1. Gate status

| # | Gate | Status | Evidence |
|---|---|---|---|
| 1 | Inspect existing autonomy work | **DONE** | report + `state/continuous_loop_state.json` + checkpoints |
| 2 | Resident-generation RAM measured, 3 GB floor enforced | **DONE** | `state/evidence/model_resident_*.json`; commit `dbf85b8e` |
| 3 | Three unassisted model-authored behavioural fixes | **BLOCKED** | transcripts in `state/runs/ty-*/result.json` |
| 4 | STOP / acceptance-failure restore / supervisor-crash recovery on the model path | **DONE** | §5 |
| 5 | Bounded campaign, then 120-minute soak | **NOT RUN** | gated by #3 (directive: only if preceding gates pass) |
| 6 | Boundaries preserved | **DONE** | §7 |

---

## 2. What the previous handoff claimed, and what the disk showed

`reports/autonomy_handoff_20261031.md` said `verdict: GO`, 17/17 checks, but in the
same file: *"Post-load RAM headroom is 2.09 GB"* — below the 3 GB floor the same
gate enforces as `ram-floor`. `state/autonomy_readiness.json` confirmed the gate
had only ever looked at **pre-load** free RAM (`ram-floor: 4.34 GB free`) and at a
disk-size estimate in `resolve_lane` (`2.25 GB × 0.9`). Nothing measured residency.

That is the contradiction. It is now resolved by measurement, and the floor was
not lowered.

## 3. Resident-generation RAM (gate 2)

New tool `tools/measure_model_resident.py` loads a lane, generates, samples
`psutil.virtual_memory().available` every 200 ms and Ollama `/api/ps` every second,
samples once more after the stream (a model that finishes inside one poll interval
is `UNMEASURED`, never a pass), then unloads and reports the **lowest** free RAM.

### Measured results

| Lane | Backend | Resident total | of which system RAM | Min free RAM | Verdict |
|---|---|---:|---:|---:|---|
| `bojo:gpu-orig` | CPU (`OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_NUM_GPU=0`) | 2.253 GB | 2.253 GB | **1.192 / 1.457 / 2.443 GB** | **FLOOR-MISSED** |
| `bojo:gpu-orig` | GPU (session only) | 2.244 GB | 0.0 GB | **3.777 / 4.092 / 4.642 GB** | **FLOOR-MET** |
| `qwen2.5-coder:3b` | GPU (session only) | 2.328 GB | 0.0 GB | **4.935 GB** | **FLOOR-MET** |
| `qwen2.5vl:7b` | GPU (session only) | 6.14 GB | 0.0 GB | 4.008 GB | FLOOR-MET (unusable output, see §4) |

Root cause found in `%LOCALAPPDATA%\Ollama\server.log`:

```text
OLLAMA_LLM_LIBRARY:cpu   OLLAMA_NUM_GPU:0
inference compute id=cpu library=cpu ... total="15.4 GiB"
warning: no usable GPU found, --gpu-layers option will be ignored
```

The user environment variable `OLLAMA_LLM_LIBRARY=cpu` (User scope, verified with
`[Environment]::GetEnvironmentVariable`) forces llama.cpp onto the CPU, so every
lane is paid for out of 15.4 GB of system RAM. With the GPU available the same
lane costs **0 GB of system RAM**.

### Enforcement (commit `dbf85b8e`)

* `--ready` gains a **`model-resident`** check that runs the probe and requires the
  measured figure. `resolve_lane` no longer presents its estimate as headroom — it
  is labelled `estimate_not_measurement`.
* Campaign dispatch refuses a `ty` task without fresh (≤ 60 min) `FLOOR-MET`
  evidence, refreshing once; `stop_reason=model_resident_no_go`.
* Tests: `Northstar_backend/test_autonomy_readiness.py` gained five cases (stale,
  missed, model-scoped, no-record, dispatch refusal). 12 passed.

### Verdict on the current machine as configured

```text
$ python scripts/continuous_loop.py --ready
NO-GO — autonomy readiness
  [PASS] ram-floor: 5.08 GB free                 <- the old gate stopped here
  [FAIL] model-resident: min free 2.443 GB (floor 3.0),
                          resident 2.253 GB (2.253 GB system / 0.0 GB VRAM)
```

The session-scoped GPU backend measured 3.78–4.94 GB and produced `GO`. The
difference is a backend setting, **not** the floor, and the persistent setting was
restored untouched: the operator must decide whether Ollama may use the GPU
(`OLLAMA_LLM_LIBRARY`, `OLLAMA_NUM_GPU`) before unattended campaigns are routine.

---

## 4. Model-authored fixes (gate 3) — BLOCKED

Three tasks were filed with **independent probes outside the model's write scope**
(`state/probes/`), so the model can read the contract and run it but cannot edit it.
All acceptance probes were confirmed failing on HEAD before dispatch.

### Probes filed

| Task | Probe | What it asserts | HEAD result |
|---|---|---|---|
| `ty-budget-stop` | `t4_budget_stop.py` | a hard budget stops AT `max_steps` / `max_tokens` | FAIL 2 (limit +1) |
| `ty-hitl-skip-report` | `t5_hitl_corrupt.py` | unreadable HITL records are counted as `skipped` | FAIL 1 (silent drop) |
| `ty-diff-select-headers` | `t6_diff_select_headers.py` | `select_hunks` keeps `---`/`+++` headers | FAIL 2 (headerless fragment) |
| `ty-dpi-image-guard` | `t1_dpi_image_guard.py` | DPI gate rejects a quad that cannot match the image | FAIL 3 (ignores `image_size`) |
| `ty-frame-fill-guard` | `t2_frame_fill_guard.py` | framing refuses fill outside (0,1] and an empty cutout | FAIL 4 |
| `ty-hero-fill-guard` | `t3_hero_fill_guard.py` | hero refuses an impossible fill | FAIL 5 |

### Attempts through the real supervisor + `ty_task_runner`

| Lane | Task | Attempts | Duration | Result |
|---|---|---|---:|---|
| `bojo:gpu-orig` (2B) | `ty-dpi-image-guard` | 3 | 63.8 s, 37.7 s, 28.2 s | `max_steps` ×3 |
| `qwen2.5-coder:3b` | `ty-dpi-image-guard` | 1 | 20.9 s | Ollama HTTP 500 |
| `qwen2.5-coder:3b` | `ty-budget-stop` | 2 | 24.6 s, 21.5 s | `max_steps` |
| `qwen2.5-coder:3b` | `ty-hitl-skip-report` | 2 | ~14 s, 21.5 s | `max_steps` |
| `qwen2.5vl:7b` | (direct edit probe) | 1 | 26.4 s | non-JSON garbage |

Transcript evidence (`state/runs/*/result.json`), for example:

```text
read print_prep.py            ok
write_many                    ok   (wrote 1 file)
acceptance                    FAIL "raised AttributeError, wanted ValueError"
write  state/probes/t1...     REFUSED (outside write scope)
write  state/probes/t1...     REFUSED (repeated)
```

The 2B lane produced a *correct* `replace_function_body` when prompted with one
function, one tool and one contract in isolation (verified), but inside the loop it
rewrites whole files and repeatedly tries to edit the read-only probe. The 3B coder
lane emits valid single tool calls (verified: `qwen2.5-coder:3b` medium prompt →
exact JSON) but degrades to malformed responses in the multi-turn loop
(`missing argument 'path'`, `Invalid response` ×6 in ten steps). The 7B vision lane
is not a coder.

**No model-authored fix was committed. Gate 3 is blocked on local lane capability,
not on the harness.** Per the directive the bounded campaign and the 120-minute
soak were **not** substituted with deterministic work.

### Harness defects found and fixed while trying (commit `8ad91edd`)

1. **`--resume <id>` started an unattended campaign.** It fell through into
   `run_campaign()` with the default 8-task bound and dispatched an unrelated task
   (`format-quad-guard`, which then failed its no-op precheck). Resume now repairs
   state and exits.
2. **A post-write acceptance failure was invisible.** The verdict went to the
   "failing files" block but never to the observation history, so the model saw only
   `wrote 1 file(s)` and rewrote the same file until the budget ran out.
3. **A refused write was retried indefinitely.** The prompt now states that files
   outside the write scope are read-only and a refused write is never retried.
4. **The residency probe could pass with no resident sample** — a fast model that
   finished inside one poll interval. It is `UNMEASURED` unless a resident sample and
   a real cost exist.
5. **A task restoration reverted a commit made during the run** (`coding_agent.py`),
   because its baseline predated the commit. Re-applied; recorded here as a known
   hazard: do not commit while a task is in flight.

---

## 5. Recovery on the real model execution path (gate 4)

All three were exercised with a real `ty_task_runner` worker, in the disposable
worktree `C:\Users\T2Hol\Desktop\NS-autonomy-wt` (branch `worktree/ty-autonomy`).

### STOP mid-run

```text
supervisor start → worker pid 17916 running ty-hitl-skip-report
STOP written at 06:26:26Z
→ task failed "STOP requested"; restoration ok; commit null
→ worker tree count after: 0
→ HEAD unchanged (fe98d687)
```

### Supervisor crash → interrupted → resume

```text
supervisor pid 25460 + worker 18496 running ty-budget-stop
supervisor killed -9  → worker 18496 SURVIVED (orphan)
next --status:
  COUNTS: interrupted=1
  task: {"status":"interrupted","reason":"stale heartbeat or dead owner process"}
  workers after recovery: 0            (orphan terminated)
--resume ty-budget-stop → {"ok": true, "resumed": ...}
  task pending; budget.py clean; commit null; HEAD unchanged
```

### Acceptance-failure restoration

Every failed attempt above restored its task-owned file byte-for-byte:
`git status -- <write_path>` empty after each run, `restoration: "ok"` recorded in
`state/continuous_loop_state.json`, no commit created.

---

## 6. The creative-test failure — identified, not waved away

Two failures remain red on this tree. Both reproduce **identically on the baseline
commit `846d9ba8` with the A+ work stashed**, so neither is caused by the creative
renderer.

| Test ID | Assertion | Actual | Root cause |
|---|---|---|---|
| `test_mockup_compositor.py::test_compose_endpoints` | unauthenticated POST `/api/design-studio/compose/mockup` → **401** | **422** (`plate_asset_id` min_length) | FastAPI validates the request body **before** the `studio_account` dependency raises 401 |
| `test_text_fidelity.py::test_text_check_endpoint_auth_and_404` | unauthenticated POST `/api/design-studio/text-check/whatever` → **401** | **404** (`{"detail":"Asset not found"}`) | the endpoint's asset lookup answers before the session is required |

Baseline evidence: `git stash push --include-untracked -- creative_flow.py
specialists/image_aplus.py test_creative_flow.py` → both tests still fail. They are
a real product defect (auth ordering), which is why the previous session filed
`blocked-auth-text-check`; that block is respected here and the diagnosis is
recorded instead of "unrelated".

---

## 7. Boundaries

* No Amazon request, no browser, no paid provider, no credential read, no spend.
* Model download: `qwen2.5-coder:3b` (Qwen2.5-Coder licence, **Apache-2.0**, 1.9 GB,
  local, pulled in 38 s) — recorded here as provenance, used only for the Ty lane.
* No persistence installed. No service, scheduler or task registered.
* The operator's Ollama configuration was **restored**: the manual GPU-backend
  `ollama serve` was stopped and `ollama app.exe` restarted, so the persistent
  `OLLAMA_LLM_LIBRARY=cpu` / `OLLAMA_NUM_GPU=0` applies again (verified: the same
  measurement now returns `FLOOR-MISSED`).
* `00_STATE.json` is operator-deny; the registry entry is a queued fragment.
* The A+ renderer work and its evidence are untouched: `ca6c45cb`, `f3a930d9`,
  `reports/aplus_render_20261031.md`, `renders/aplus_live_20261031/`.

---

## 8. Commits, commands, evidence

| Commit | What |
|---|---|
| `dbf85b8e` | measured resident-RAM gate, campaign dispatch refusal, three Ty tasks |
| `8ad91edd` | resume fix, acceptance-verdict observation, scope rule, coder lane, small-file tasks |
| `worktree/ty-autonomy` | `f945abc1`, `ecff21da`, `1b9937cb`, `54fb80c8`, `fe98d687` — the isolated runs |

```powershell
python tools/measure_model_resident.py --model bojo:gpu-orig --floor 3.0
python scripts/continuous_loop.py --ready                       # NO-GO on CPU backend
python scripts/continuous_loop.py --task ty-budget-stop --max-tasks 1
python scripts/continuous_loop.py --stop                        # mid-run probe
python scripts/continuous_loop.py --status                      # marks interrupted
python scripts/continuous_loop.py --resume ty-budget-stop
python -m pytest Northstar_backend/test_continuous_loop.py Northstar_backend/test_autonomy_readiness.py Northstar_backend/test_autonomy_recovery.py Northstar_backend/test_coding_agent.py Northstar_backend/test_agent_kernel.py -q
```

Evidence paths:

```
state/evidence/model_resident_bojo_20261101.json                 CPU: 1.192 GB
state/evidence/model_resident_bojo_gpu_session_20261101.json     GPU: 4.092 GB
state/evidence/model_resident_qwen25coder_3b_20261101b.json      GPU: 4.935 GB
state/evidence/model_resident_bojo_cpu_restored_20261101.json    restored: 1.457 GB
state/evidence/model_resident_bojo_gpu_orig_20261101T063056Z.json  final --ready: 2.443 GB
C:\Users\T2Hol\Desktop\NS-autonomy-wt\state\runs\              model transcripts
state/autonomy_readiness.json                                  final NO-GO + reasons
state/probes/                                                  the six independent probes
```

## 9. What has to be true before this is autonomy

1. **A lane that can edit code.** A 2B chat model and a 3B coder model both fail the
   multi-turn tool contract on this box; a 7B+ coder lane is the missing component.
   The gate instrumentation is ready — the work is the lane, not the harness.
2. **A decision on the Ollama backend.** CPU-only makes every lane a 2.2 GB system
   RAM cost and cannot meet the 3 GB floor on a 15.4 GB box with 11 GB in use.
3. **The auth-ordering defect** (`401` before body validation and before asset
   lookup) needs the operator authorization the registry already asks for.
