# Ty autonomy — resource qualification and repair handoff (2026-11-01)

Continues `reports/ty_autonomy_final_run_20261101.md` on commit `990e6cd9`.
The resource blocker was not cleared inside this session: the host has **4.57 GB
available** and the declared precondition for the qwen profile is **6.0 GB**. No
model was loaded, nothing was stopped or freed, and no gate was pressed to pass.

---

## 1. VERDICT

**BLOCKED** on gate 1 (resource/profile readiness). Verified operating scope:

* readiness and dispatch now share one execution profile (model + `num_ctx`);
* a low-memory host is refused **before** a model is loaded, so no starved
  measurement is produced or repeated;
* a model task is stopped after two consecutive sub-floor samples during execution;
* a tested foreground launcher exists and refuses cleanly;
* three app-level, probe-backed task contracts are frozen and ready;
* the worker's own budget control was repaired as bootstrap maintenance, outside
  any model task scope.

Model-authored engineering is **not** qualified: no Ty fix has been accepted in the
repository.

---

## 2. GATES

| Gate | Status | Evidence |
|---|---|---|
| 1. Resource / profile readiness | **FAIL — RESOURCE BLOCKED** | `state/autonomy_readiness.json` (NO-GO 2026-11-01T18:01:45Z); `state/checkpoints/20261101T180145Z-ready` |
| 2. First accepted model-authored fix | **NOT RUN** | gated on 1 |
| 3. Three-fix qualification | **NOT RUN** | gated on 1 |
| 4. 120-minute soak | **NOT RUN** | gated on 3 |
| 5. Regression batch | **PASS** | 148 passed in 5.61 s |
| 6. Initial repair campaign | **NOT RUN** | gated on 1–3 |

`--ready` now prints, in order:

```text
[PASS] ram-floor: 5.08 GB free
[PASS] policy-fingerprint: 5/5 policy files match HEAD
[PASS] rollback-checkpoint: state\checkpoints\20261101T180145Z-ready (7 files)
[PASS] sandbox-restore: {"ok": true, "bytes_match": true, "created_removed": true}
[FAIL] model-preload: free 4.57 GB; qwen2.5-coder:3b needs 6.0
[FAIL] model-resident: qwen2.5-coder:3b ctx8192: pre-load 4.57 GB < 6.0 GB required - probe not run
```

---

## 3. MEMORY

| Item | Value |
|---|---|
| Model / profile | `qwen2.5-coder:3b`, `num_ctx=8192`, CPU runtime (`OLLAMA_LLM_LIBRARY=cpu`, unchanged) |
| Host | 15.42 GB total, **4.57 GB available**, 10.85 GB used, 1.78 GB swap used |
| Resident models | 0 |
| GPU | 16303 MiB total, 0 MiB used (not used by this profile) |
| Pre-load requirement | **6.0 GB** (declared precondition for this profile; unchanged) |
| Resident floor | **3.0 GB** (unchanged) |
| Measured lane cost (earlier evidence) | 1.62 GB at ctx 8192 · 2.35 GB at default ctx |
| Shortfall now | **1.43 GB** below the pre-load requirement |
| Sampling method | `psutil.virtual_memory().available`, 200 ms during generation; 1 s RAM watch during dispatch |

**Arithmetic vs measurement.** A 3.0 GB floor plus a 1.62 GB drop needs ≈4.6 GB
free — an *arithmetic minimum*. The declared **6.0 GB** precondition adds margin for
KV growth, the post-task test phase and sampling noise, and it is the number this
gate enforces. The 3.0 GB floor is untouched; the 6.0 GB precondition is untouched.

Process ownership (no secrets collected): the OpenCode controller tree for this
session (`opencode.exe` 23172 and 22880, ~0.90 GB, plus their `node` children
~0.17 GB) is the only session-owned block. It is **the active controller** and was
deliberately not terminated. `MemCompression` 0.50 GB, Edge WebView 0.35 GB,
Defender 0.34 GB are unrelated. No process owned by this run was left running: all
work was short-lived foreground commands.

---

## 4. WHAT WAS BUILT THIS ROUND (commit `990e6cd9`)

**Profile-accurate readiness.** The queue's `(model, num_ctx)` is resolved once and
used for the pre-load gate, the resident probe and the dispatch check. Evidence is
now context-scoped: an 8192-context measurement cannot authorise a 32768-context
dispatch. A lane that does not match the task stops the campaign with
`profile_mismatch`.

**Pre-load gate before loading.** `evaluate_profiles` refuses when free RAM is below
the profile minimum and **does not run the probe**. This ends the previous pattern of
loading a model into a starved host to obtain a NO-GO reading.

**Runtime floor watch.** A `ty` task is terminated after two consecutive sub-floor
samples (`ram_floor_breach`), with the threshold unchanged at 3.0 GB and the reason
written to the heartbeat.

**Foreground launcher** (`scripts/ty_foreground.py`, `scripts/ty_foreground.cmd`):
reuses the existing supervisor, lock, log, checkpoint and recovery; runs `--check`
first; refuses with exit 3 and the measured shortfall; installs nothing.

**Control repair (bootstrap, not a Ty fix).** `agent_kernel/budget.py` bounded the
agent kernel's own steps/tokens with `>`, so the tracker reported itself usable after
its last permitted step. `>=` now stops exactly at the limit. This is the worker's
own control, so it was repaired outside any model task, with the evaluator in
`test_budget_limits.py` and `state/probes/t4_budget_stop.py`. The `ty-budget-stop`
task is **blocked with that reason** and does not count toward qualification.

**Frozen queue** (three app-level, independently probed):

| Task | File | Probe | Pre-fix state |
|---|---|---|---|
| `ty-artifact-jpeg` | `agent_kernel/artifacts.py` | `state/probes/t7_artifact_jpeg.py` | FAIL 2 (valid JPEG → `binary`) |
| `ty-hitl-skip-report` | `agent_kernel/hitl_counts.py` | `state/probes/t5_hitl_corrupt.py` | FAIL 1 (silent drop) |
| `ty-diff-select-headers` | `agent_kernel/diff.py` | `state/probes/t6_diff_select_headers.py` | FAIL 2 (headerless fragment) |

All three: one writable file, read-only probe outside the write scope,
`allowed_tools=[read,ast_edit,run,finish]`, `max_steps=8`, one repair attempt,
600 s timeout, `num_ctx=8192`.

---

## 5. RECOVERY

Not re-demonstrated: the evidence on the current executor is unchanged and applies
to HEAD (`3669f651` introduced the executor; `990e6cd9` did not touch `coding_agent`,
`coding_tools`, the supervisor's STOP path, or the restore path). Tests that cover
them pass in the batch below. Existing artefacts:

* STOP mid-model-run — worker killed, `restoration: ok`, no commit;
* supervisor crash → `interrupted` on next start, orphan terminated, `--resume`
  restores and returns the task to pending;
* acceptance-failure restore — byte-for-byte, verified every failed run.

Fresh checkpoint `state/checkpoints/20261101T180145Z-ready` (7 files) and
`bytes_match: true` / `created_removed: true` in a disposable sandbox.

---

## 6. Tests

```text
148 passed in 5.61s
```

Suites: `test_tool_protocol` (28), `test_coding_agent` (22), `test_agent_kernel`,
`test_continuous_loop`, `test_autonomy_readiness` (18, six new for pre-load,
profile scoping, mismatch and the runtime watch), `test_autonomy_recovery`,
`test_autonomy_supervisor_crash`, `test_foreground_launcher` (6, all refusal and
GO paths), `test_budget_limits` (4).

New regression coverage required by the directive:

* insufficient pre-load memory refuses and **does not call the probe**;
* insufficient resident memory refuses GO;
* resident evidence is context-scoped (8192 evidence cannot authorise a 32768 run);
* a lane/task profile mismatch stops the campaign before execute;
* the runtime watch needs two consecutive sub-floor samples;
* on a low-memory host the launcher exits 3 **without invoking Ty**.

No pre-existing failures were introduced; the two long-standing creative endpoint
tests (`test_mockup_compositor.py::test_compose_endpoints`,
`test_text_fidelity.py::test_text_check_endpoint_auth_and_404`) are outside this
batch and unchanged.

---

## 7. CURRENT STATE

* **Running:** nothing. No supervisor, no worker, no resident model, no lock, no STOP.
* **Queue:** 3 authorized app tasks; 4 blocked with reasons.
* **Eligible work:** the three frozen tasks, awaiting a host that meets 6.0 GB.
* **Exact blocker:** 4.57 GB available vs 6.0 GB required for
  `qwen2.5-coder:3b` at `num_ctx=8192`; shortfall 1.43 GB.

---

## 8. OPERATOR ACTION (one)

Close the OpenCode session attached to
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`
(controller PIDs 23172 / 22880 at measurement time), then run in a visible terminal:

```bat
cd /d "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
scripts\ty_foreground.cmd
```

The launcher checks the 6.0 GB pre-load precondition **before** loading anything and
refuses with the measured shortfall if the host is still short. If it proceeds, it
runs the full readiness gate, then the qualification campaign
(`--max-tasks 3 --deadline-minutes 120 --max-consecutive-failures 2`).

Monitor / stop from another terminal:

```powershell
python scripts/continuous_loop.py --status
Get-Content reports\autonomy_log_20261101.log -Tail 40 -Wait
python scripts/continuous_loop.py --stop
```

Nothing in this run requires a service, scheduler, elevation, network or download.
