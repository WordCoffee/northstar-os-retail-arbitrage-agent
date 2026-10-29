# Agent kernel v0.1 + Phase B — 2026-10-28

**Verdict:** the spec is now working code. One kernel serves Ty, Bojo and
Autothink; Ty can opt into it without changing its default runner; Bojo can show
a validated project plan. The NS-PROJ-20 **harness validation** completes 20/20
(not a project result). The live
20-brief Ty baseline is **not** claimed — it needs the coding/creative models and
has not been run.

---

## 1. What shipped

| Piece | Where | Evidence |
|---|---|---|
| 12-capability kernel | `Northstar_backend/agent_kernel/` | 48 tests in `test_agent_kernel.py` |
| Ty opt-in path | `TysAssistant.run_kernel()` + `agent_kernel/tys_adapter.py` | `test_tys_kernel_integration.py` (2 tests) + a real inspect smoke run |
| Bojo project plan | `plan_project` tool in `chat_tools.py` | `test_plan_project_tool.py` (4 tests) |
| NS-PROJ-20 | `eval/projects/ns_proj_20.json`, `tools/proj_bench.py` | harness validation 20/20 (not a project result), evidence 1.0, resume pass |
| Phase B harvest | `SOURCES_1500.csv`, `TRIAGE.md`, `DEEP_12.md`, `SOURCES.md` | 1,500 scored / 100 README reads / 12 deep |
| State | `00_STATE.json` | `rea_program_20261028` + `agent_kernel_20261028` merged; backup in `backups/state/` |

### Kernel modules

`model` (schemas + validation), `policy` (deny→ask→allow, Amazon/spend hard
denies, expiring grants), `plan_mode`, `todos`, `graph` (DAG), `memory`
(`NORTHSTAR.md` + proposed auto-memory), `context` (repo map + compaction),
`session` (journal + checkpoints), `verify` (named verifiers, `unknown` never
passes), `subagents` (hash-checked reports), `diff`, `skills`, `budget`,
`journal`, `kernel`, `tys_adapter`.

**48 tests** cover: invalid plans, cycles, gates, policy precedence, bare-tool
removal, grant expiry, the single-`in_progress` todo rule, budget stops, journal
replay, file checkpoint/restore, symlink skip, memory imports, compaction
anchors, diff hunk selection, unknown verifiers, subagent hash mismatch, kernel
retry/gate/resume/deny, and the Ty adapter.

---

## 2. Ty integration — opt-in, verified

`TysAssistant.run_kernel(task_id)` builds a plan from the existing work order
(objective, scope, steps, limits), runs it through the kernel, and persists the
result. The default `run()` is untouched.

A real inspect work order was run end to end:

```
status: complete
nodes:  n1 -> done
evidence: reports/rea_probe/tys_kernel_live_smoke.json
```

The live smoke uses the real `InspectAdapter` and a real `README.md`; it does not
use a model, so it proves the wiring, not project quality.

## 3. Bojo — a visible plan, not a promise

`plan_project` returns the existing chat card shape:

```
rows: [{"label": "measure the plate", "value": "inspect · pending"},
       {"label": "compose the label", "value": "creative · pending"}]
```

It validates the plan before showing it and says explicitly that it is **a plan,
not an execution**. It is offered in the `system` and `creative` tool sets.

## 4. NS-PROJ-20 — harness validation (not a project result)

**This section is a harness validation, not a claim about Ty's project ability.**

```
briefs: 20
harness_validation_complete: 20
project_result: false
valid_plans: 20
mean_evidence_coverage: 1.0
total_interventions: 0
resume: first needs_human -> second complete, no duplicate step
```

This validates the *harness*: plans are valid, every node has evidence, a gate
blocks once, and resume does not repeat the completed node. It is **not** a
statement that Ty completes 20 projects; the live baseline is separate.

### 4.1 Live text-lane baseline — 2026-10-29 (separate from the harness validation)

The live run used the local 27B to write each node's text; the harness persisted
it. Three runs: **20/20 artifacts each**, **18/20 format-valid** each, p50
**4.82–6.27 s**, p95 **11.17–14.08 s**, 180 model calls total. Content validators
put the text lane at **17/20 (0.85)** each run (p11 label, p13 social, p14 ad).
Fences are stripped at persistence; the 13 fenced nodes from run 1 were rerun and
none remain. With validators **enforced in the kernel**, the run completed
**17/20** (evidence 0.95, p50 5.08 s, p95 12.90 s). Tool nodes make p11, p13 and
p14 valid (tool-lane content **20/20**). **Ty-as-is is 0/20**: its coding lane has
no tools and no context, so it refused every artifact. **MTP off** is pinned
because the MTP runs aborted at 46 and 49 calls. It is **not a quality claim**.
Reports: `reports/ns_proj_20_live_baseline_20261029.md` and
`reports/tys_as_is_baseline_20261029.md`.

**Coding-tool run (2026-10-29):** the read-only lane was replaced by a bounded
`list/read/grep/write/apply_patch/run` loop. The 3-brief pilot was 3/3
(p01/p02/p05; real `pytest` and `py_compile` passes), then the hybrid 20-brief
runs scored **20/20, 19/20 and 18/20** (p50 7.3–8.5 s, p95 15.7–25.6 s; thresholds
p50 10.2 s, p95 30.7 s, completion 0.90). Ty p01–p05 is **5/5 content-valid**;
p01’s Ty status is `needs_human` on a retry assertion even though its artifact is
valid. Reports: `reports/coding_agent_pilot_20261029.md` and
`reports/coding_hybrid_20_20261029.md`. `run_kernel(coding_agent=True)` is the
default when `scope.workspace` is set; without it the old lane is used.

## 5. Phase B — 1,500 / 100 / 12

| Metric | Actual |
|---|---|
| Scored | **1,500** (746 GitHub search + 754 local corpus) |
| Read | **100** public READMEs (notes in the CSV; `readmes/` is local evidence) |
| Deep | **12** public docs / OSS notes in `DEEP_12.md` |
| Licences | 835 read/adapt, 75 copyleft read-only, 590 **observe only** |

The 12 deep notes record the documented limits that matter: file-tool-only
checkpoints, Bash-only files untracked, subagent edits not restored, 200-line/25KB
auto-memory, four-hop imports, deny→ask→allow with bare-tool removal, plan mode
blocking edits until approval, skills loading only when used.

## 6. Verification run

```
pytest test_agent_kernel test_plan_project_tool test_chat_tools \
       test_pouch_label test_pouch_label_geometry \
       test_tys_assistant test_tys_kernel_integration
  -> 144 passed
python tools/proj_bench.py --limit 20
  -> harness validation 20/20 (not a project result), 20/20 valid,
     evidence 1.0, resume pass
python tools/rea_regress.py --quick --with-tests
  -> PASS
```

## 7. What is left — explicitly

| Item | Why it is not done |
|---|---|
| Live 20-brief text-lane baseline | **3 runs 2026-10-29** — 20/20 artifacts, 18/20 format-valid, content 17/20 each; enforced run 17/20; tool lane 20/20 |
| Ty-as-is project baseline | **0/20 content-valid** — coding lane has no tools/context; see `reports/tys_as_is_baseline_20261029.md` |
| Two operator windows (Claude Code, Cowork) | Requires the operator present; no unattended substitute |
| Phase 3 U1 (auto-chain `apply_label`) | Not built; it changes the chat turn contract and needs a live UI check |
| Phase 3 V1 (`studio_video_assemble.py`) | The probe proves the FFmpeg chain; the production module is not promoted yet |
| Bojo UI verification | The card uses the existing renderer; no live browser click was performed |

## 8. Gates held

No Amazon. No spend. No vendor bundle analysis or decompilation. No credentials
entered. No CAPTCHA. Chrome Connect remains the only browser path.

## 9. Commits

- `203ac6ba` — L2 geometry + item 1 acceptance + 2048 record + `verify-rea`
- `6c39b74a` — Phase A spec, clone ledger, source plan, provenance rows
- `8d356a3a` — provenance repair
- kernel v0.1 commit (this change) — kernel, Ty adapter, Bojo tool, benchmark,
  Phase B, state merge
