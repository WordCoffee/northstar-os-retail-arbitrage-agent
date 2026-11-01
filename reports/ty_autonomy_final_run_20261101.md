# Ty autonomy — resource-gated final run (2026-11-01)

Baseline: executor commit `3669f651`, `reports/ty_executor_20261101.md`, lanes
resolved through the local Ollama API. Operator precondition (≥ 6 GB free at idle)
was declared as already satisfied; it was **not** satisfied when the gate ran, so
this run stopped at gate 1 by design.

---

## 1. Per-gate result

| Gate | Status | Evidence |
|---|---|---|
| 1. Resident-RAM probe + `--ready` | **FAIL — NO-GO** | measured min **2.085 GB** (gate) / **2.478 GB** (task ctx) against the 3.0 GB floor |
| 2. One-file repo task on `qwen2.5-coder:3b` | **BLOCKED** | not dispatched: the readiness gate refuses, per the directive's stop rule |
| 3. Bounded campaign (3 fixes) | **BLOCKED** | gated on gate 2 |
| 4. 120-minute soak | **BLOCKED** | gated on gate 3 |
| 5. 132-test protocol/coding/kernel/loop/readiness/recovery batch | **PASS** | `132 passed in 5.62s` |
| Verdict | **PARTIALLY READY** | not all four gates pass on measured evidence |

---

## 2. Gate 1 — the measurement

Host at the gate: 15.42 GB total, **4.14 GB available**, 11.28 GB used, **0 models
resident**. The declared ≥ 6 GB precondition was not in force.

| Measurement | Baseline free | Min free while resident | Resident (system) | Verdict |
|---|---:|---:|---:|---|
| Probe, task context (`num_ctx=8192`) | 4.096 GB | **2.478 GB** | 2.052 GB | FLOOR-MISSED |
| `--ready` (model default context, 32768) | 4.43 GB | **2.085 GB** | 2.052 GB | FLOOR-MISSED |

Evidence:

```
state/evidence/model_resident_coder_gate1_20261101.json      probe at task ctx
state/evidence/autonomy_readiness_20261101T172049Z.json      --ready transcript
state/checkpoints/20261101T172042Z-ready/                    rollback checkpoint
```

Top consumers at the time (read-only measurement, nothing stopped): `opencode` 0.98
+ 0.41 GB, `MemCompression` 0.50 GB, `msedgewebview2` 0.35 GB, `MsMpEng` 0.34 GB,
one `python` 0.33 GB — no single reclaimable block; the remainder is spread across
the session, the live backend and the parallel work.

**Not changed to pass:** the gate measures at the model's default context while the
task runs at 8192; both figures are below the floor today, so the verdict is robust
to that difference. The floor, the gate and the task contract are unchanged. No
memory was freed, no process stopped, no Ollama setting touched, nothing downloaded.

---

## 3. Gates 2–4 — what did not happen, and why

The directive is explicit: if `--ready` reports `model-resident` NO-GO, stop and
report; do not proceed; do not weaken the floor. The gate reported NO-GO with 2.085
GB measured. Therefore:

* the repository task `ty-budget-stop` was **not dispatched** (`attempted: null`,
  `stop_reason: readiness_no_go` if started; the campaign function was not invoked
  manually to avoid bypassing the same gate);
* no campaign, no soak, no commit;
* the task-owned file is clean (`git status -- Northstar_backend/agent_kernel/budget.py`
  empty) and the task state remains `pending`.

This is a clean stop, not a failed run: the model path is untouched since the last
recorded evidence.

---

## 4. What the last run proved, unchanged by this one

* The executor (`3669f651`) refuses or normalises every bad turn: one JSON action,
  canonical names, scope before execution, argv-only commands, whole-file writes of
  existing source refused, bounded repair then `protocol_failed`.
* A real `qwen2.5-coder:3b` authored `return a + b` through that executor in a
  disposable workspace; behavioural acceptance `add(2,3)==5` passed (6 steps, 5
  refusals, 15.9 s) — `state/evidence/executor_proof_qwen2.5-coder_3b.json`.
* Recovery is unchanged: STOP, supervisor crash → `interrupted` → explicit resume,
  acceptance-failure restore, staged-work preservation.

Those remain the system's proven capability. What is missing for a first committed
model-authored fix is **host memory**, not protocol or model behaviour.

---

## 5. What would clear gate 1

The CPU lane's resident cost is ~1.6–2.4 GB (weights + KV) and the drop is stable;
the floor is 3.0 GB. Passing needs roughly:

* **≥ 5.2 GB free at dispatch** with `num_ctx=8192` (measured drop 1.62 GB), or
* **≥ 5.4 GB free** at the model's default context (measured drop 2.35 GB).

The operator's ≥ 6 GB precondition would clear either figure comfortably. It needs
to hold **at the moment of dispatch**, because the gate re-measures there.

---

## 6. Commands

```powershell
cd C:\Users\T2Hol\Desktop\NS-autonomy-wt
python tools/measure_model_resident.py --model qwen2.5-coder:3b --num-ctx 8192 --floor 3.0 ^
       --out state/evidence/model_resident_coder_gate1_20261101.json
python scripts/continuous_loop.py --ready
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
python -m pytest Northstar_backend/test_tool_protocol.py Northstar_backend/test_coding_agent.py ^
  Northstar_backend/test_agent_kernel.py Northstar_backend/test_continuous_loop.py ^
  Northstar_backend/test_autonomy_readiness.py Northstar_backend/test_autonomy_recovery.py ^
  Northstar_backend/test_autonomy_supervisor_crash.py -q
```

Boundaries: no Amazon, spend, credentials, external network, browser, production
data, downloads, or persistence. No process stopped, no memory freed, no Ollama
service or backend change, no policy/task/acceptance edit.
