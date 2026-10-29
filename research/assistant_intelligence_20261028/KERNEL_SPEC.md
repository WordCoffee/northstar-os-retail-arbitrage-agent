# Agent Kernel Specification — Ty's Assistant, Bojo, Autothink

**Status:** **BUILT v0.1** · 2026-10-28. Operator approved ("full approval");
the kernel is implemented in `Northstar_backend/agent_kernel/` and covered by 48
tests. This document remains the contract, not a description of the model.
**Scope:** Phase A specification + Phase C build. Ty's default runner is
unchanged; the kernel is opt-in via `TysAssistant.run_kernel`. Bojo exposes
`plan_project`. **No Amazon, no spend, no vendor bundle analysis.**
**Reference standard:** Claude Code / Claude Cowork, from **public documentation
only** (no vendor client bundle analysis, no decompilation, no copied prompts or
strings).

---

## 0. What this is — and is not

This is the contract for **one agent kernel** that Ty's Assistant, Bojo and
Autothink all run on. Ty is the reference implementation because its work is
long-running and evidence-bearing; Bojo is the same kernel with a seller-facing
conversation surface; Autothink is the coding lane.

It is **not** a plan to make a 2B local model behave like Claude by prompt
engineering. Most of the perceived gap is harness: a plan that is visible and
mutable, a step that cannot be marked done without proof, a checkpoint that can
be restored, and a permission system the model cannot talk its way past.

---

## 1. What "Claude-grade" means here

Eight observable behaviours, in order of importance:

1. **Plan before acting**, and show the plan in a form the operator can edit.
2. **One active task at a time**, with a visible todo state machine.
3. **Every step ends in a machine-checkable assertion** — not a claim.
4. **Failure triggers re-planning**, not blind retry.
5. **Context is curated**: project memory, on-demand reads, compaction with
   anchors kept.
6. **Every meaningful change is checkpointed** and can be rewound.
7. **The harness enforces permissions**, not the prompt; a denied tool is gone,
   not discouraged.
8. **A blocked run stops with one clear ask**, and resumes exactly where it
   stopped.

Parity is **behavioural**. It is not a claim of equal model quality, and it does
not require copying Claude's UI.

---

## 2. One kernel, three products

| Product | Surface | Kernel use | Non-negotiable |
|---|---|---|---|
| **Ty's Assistant** | `/api/admin/tys`, CLI; no customer page | Long-running admin campaigns across `inspect`, `coding`, `browser`, `creative` lanes | Evidence per step; operator gates; resume |
| **Bojo** | Customer chat `/api/chat` | Conversational turns, plan cards, artifact edits, receipts | Same kernel; seller tools; no admin lanes |
| **Autothink** | Coding surface | Code tasks, repo map, tests, diffs | Same kernel; coding lane only |

If each product grows its own loop, the programme fails. Ty owns the reference
implementation; the other two consume it.

---

## 3. State machine

### 3.1 Session

```
idle
  → planning            (read-only exploration, plan being authored)
  → awaiting_approval   (plan proposed; no side effects)
  → executing           (approved nodes running)
  → verifying           (assertions running for the current node)
  → blocked_on_human    (login / CAPTCHA / spend / ambiguity / failed gate)
  → checkpointed        (paused, resumable)
  → complete | failed | cancelled
```

Rules:
- No side effect in `planning` or `awaiting_approval`.
- `blocked_on_human` always carries exactly one `ask` with the action needed and
  the resume token.
- `failed` is terminal for the plan version; a new version may supersede it.
- `cancelled` is operator-initiated only.

### 3.2 Node (task)

```
pending → ready → running → verifying → done
                        ↘ failed → (re-plan | blocked | skipped)
```

- `done` requires at least one **passing** evidence record whose assertion is
  bound to the node's acceptance criteria.
- `unknown` is a valid verifier result. It never renders as `done`.
- One node may be `running` per session unless the node is explicitly declared
  parallel-safe.

### 3.3 Plan

```
draft → proposed → approved → active → (superseded | complete | abandoned)
```

- Only `approved` plans execute.
- A re-plan creates a new version with `supersedes`; the old version stays
  readable.

---

## 4. Schemas

These are contracts, not database tables; storage may be SQLite/JSONL.

### 4.1 Plan

```json
{
  "plan_id": "plan_...",
  "session_id": "sess_...",
  "version": 1,
  "supersedes": null,
  "goal": "one sentence, operator's words",
  "constraints": ["no Amazon", "no spend", "Profile 6 only"],
  "acceptance": ["criterion with a verifier", "..."],
  "budget": {"max_steps": 40, "max_wall_s": 3600, "max_attempts_per_node": 2},
  "nodes": [],
  "edges": [["node_a", "node_b"]],
  "gates": [{"node_id": "node_c", "gate": "operator_approval", "reason": "..."}],
  "created_at": "...",
  "approved_at": null,
  "approved_by": null
}
```

### 4.2 Node

```json
{
  "node_id": "n1",
  "kind": "inspect|coding|browser|creative|human",
  "title": "short imperative",
  "inputs": {"files": [], "urls": [], "assets": []},
  "outputs": ["artifact path or state description"],
  "acceptance": ["machine-checkable assertion"],
  "depends_on": [],
  "lane": "coding",
  "max_attempts": 2,
  "status": "pending",
  "attempts": 0,
  "evidence_ids": []
}
```

### 4.3 Evidence — the only currency for "done"

```json
{
  "evidence_id": "ev_...",
  "session_id": "sess_...",
  "node_id": "n1",
  "kind": "test_output|build_output|file_hash|page_state|artifact|ocr|prepress|readiness|http_status",
  "path": "relative/path/or/null",
  "sha256": "...",
  "observed_at": "...",
  "verifier": "pytest|npm|chromeconnect|pouch_label|prepress|manual",
  "assertion": "what was checked, in one line",
  "result": "pass|fail|unknown",
  "detail": "scrubbed, no secrets"
}
```

Rules:
- No evidence → the node cannot be `done`.
- `unknown` is recorded as `unknown`; it is never upgraded to `pass`.
- Evidence is append-only.

### 4.4 Checkpoint

```json
{
  "checkpoint_id": "ckpt_...",
  "session_id": "sess_...",
  "plan_version": 1,
  "node_states": {"n1": "done", "n2": "running"},
  "conversation_seq": 42,
  "file_snapshot": [{"path": "...", "sha256": "...", "bytes": 0}],
  "restore_scope": "files|conversation|both",
  "created_at": "...",
  "limits": "see §6.3"
}
```

### 4.5 Permission rule

```json
{
  "effect": "deny|ask|allow",
  "tool": "Bash|Edit|Write|Browser|Http|...",
  "specifier": "git push *|domain:example.com|host:...",
  "scope": "session|repository|host|task",
  "expires_at": "ISO-8601 or null",
  "source": "operator_default|task_grant|managed",
  "why": "one line, for the audit row"
}
```

Evaluation: **deny → ask → allow**, first match wins, specificity does **not**
reorder. A bare-tool deny removes the tool from the model's context entirely.
Rules are enforced in code; `NORTHSTAR.md` and prompts are not enforcement.

### 4.6 Event (append-only journal)

```json
{
  "seq": 1,
  "ts": "...",
  "session_id": "sess_...",
  "node_id": "n1",
  "type": "plan_proposed|node_started|tool_call|tool_result|evidence|gate|checkpoint|resume|error",
  "payload": {},
  "policy_fingerprint": "..."
}
```

The journal is the replay source. No replay may re-execute a side effect; it
re-renders state and evidence.

---

## 5. The twelve capability modules

| # | Capability | Module (planned) | Phase A status |
|---|---|---|---|
| 1 | Plan mode | `agent_kernel/plan_mode.py` | **spec'd** from public docs |
| 2 | Todo state machine | `agent_kernel/todos.py` | built v0.1 |
| 3 | Task DAG | `agent_kernel/graph.py` | built v0.1 |
| 4 | Subagents | `agent_kernel/subagents.py` | built v0.1 |
| 5 | Context engineering | `agent_kernel/context.py` | built v0.1 |
| 6 | Project memory | `agent_kernel/memory.py` | **spec'd** from public docs |
| 7 | Checkpoint / rewind | `agent_kernel/session.py` | **spec'd** from public docs |
| 8 | Permissions / hooks | `agent_kernel/policy.py` | **spec'd** from public docs |
| 9 | Diff review | `agent_kernel/diff.py` | built v0.1 |
| 10 | Verification loop | `agent_kernel/verify.py` | built v0.1 |
| 11 | Skills | `agent_kernel/skills.py` | built v0.1 |
| 12 | Budget & replay | `agent_kernel/budget.py`, `journal.py` | built v0.1 |
| 13 | Bounded coding tool loop | `coding_tools.py`, `coding_agent.py`, `coding_executor.py` | built; pilot 3/3 |

Build order for the first implementation wave: **8 → 1 → 7 → 6 → 2 → 3 → 10**
(policy before plan, because a plan without enforcement is a suggestion).

---

## 6. Documented limits — the four reference rows

All quotes/paraphrases below are from public documentation, accessed **2026-10-28**.
Where our implementation differs, it must say so in its own docstring and in the
CLONE_LEDGER.

### 6.1 Plan mode (row 1)

Source: `https://code.claude.com/docs/en/permission-modes`
(`https://code.claude.com/docs/en/plan-mode` returned 404 on this date; the
behaviour lives in the permission-modes page).

- Plan mode: **reads files and runs read-only shell commands to explore, but does
  not edit source files**; classifier-approved commands may run only when auto
  mode is available.
- **Edits are blocked until the operator approves a plan.**
- Protected paths (`.git`, `.claude`) are never auto-approved outside bypass.
- Plan is one of the modes: `default → acceptEdits → plan → auto` (cycle order,
  with `dontAsk` and `bypass` outside the default cycle).

Our rule: `planning` and `awaiting_approval` are side-effect-free; a plan must be
approved by the operator (or by an explicit standing grant) before any node runs.

### 6.2 Memory (row 6)

Source: `https://code.claude.com/docs/en/memory`

- Two systems: authored `CLAUDE.md`/`AGENTS.md` and **auto memory**.
- Both load at the start of every conversation.
- Auto memory loads **the first 200 lines or 25 KB**.
- Target **under 200 lines** per `CLAUDE.md`; imports expand inline with a
  **maximum depth of four hops**.
- Path-scoped rules load only when matching files are read/edited.
- **"Claude treats them as context, not enforced configuration. To block an
  action regardless of what Claude decides, use a PreToolUse hook."**
- `CLAUDE.local.md` is personal and gitignored; external imports require one
  approval per project.

Our rule: `NORTHSTAR.md` is context; `policy.py` is enforcement. Auto-memory
writes stay **PROPOSED** until the operator approves them (this repo already has
`memory_bank.propose_revision`).

### 6.3 Checkpoint / rewind (row 7)

Source: `https://code.claude.com/docs/en/checkpointing`

- A checkpoint is created **before each prompt that starts a turn**; file
  snapshots are kept for the **100 most recent checkpoints** in a session.
- **Only changes made by the file editing tools are tracked.**
  **"A file that only Bash commands changed isn't tracked and stays as it is."**
  Nuance to preserve: after the file tool has edited a file once in the session,
  later Bash changes to *that* file **are** rewound.
- **Subagent edits are generally not restored**: only files the main conversation
  already edited are restored; a background subagent's edits to other files stay.
- Symlinked and hard-linked paths are **skipped** on restore.
- Manual/external changes and other concurrent sessions are **not tracked**.
- A message typed mid-turn has **no checkpoint of its own**.
- Snapshots are deleted in the retention sweep, **~30 days** after the session
  last saved one; restoring a deleted snapshot fails with `No files were restored`.
- **"Not a replacement for version control."**

Our rule: git is the durable record; checkpoints are session-level convenience.
Our checkpoint must state which of the above it covers. The first release will
cover **files written through the kernel's file tools only**, plus an explicit
`git_status` snapshot (which is stronger than Claude's Bash blind spot and must
be labelled as such).

### 6.4 Permissions (row 8)

Source: `https://code.claude.com/docs/en/permissions` and
`https://code.claude.com/docs/en/permission-modes`

- Tiered approval: read-only within working dirs needs no prompt; Bash, file
  modification, WebFetch and WebSearch do (with read-only/preapproved exceptions).
- Rules: **deny → ask → allow**, **first match wins**, **specificity does not
  reorder**. A broad deny cannot be carved out by a narrower allow.
- A **bare tool-name deny removes the tool from context**; a scoped deny leaves
  the tool available and blocks matching calls.
- "Yes, and don't ask again": Bash and WebFetch persist **per repository**; a
  file-modification approval lasts **until session end**.
- **"Permission rules are enforced by Claude Code, not by the model."**
- Modes: `default`, `acceptEdits`, `plan`, `auto`, `dontAsk`, `bypassPermissions`.
- Actions no mode auto-approves include explicit ask rules, user-interaction
  tools, critical-path `rm`/`rmdir`, and reads outside working directories when
  that setting is on.

Our rule: Ty runs in `dontAsk` semantics for a bounded campaign (anything that
would prompt is denied unless pre-approved), never `bypassPermissions`. Browser
grants are per-host and **expire within 24 hours**. Amazon remains hardcoded deny.

---

## 7. Our own limits (must be stated, not hidden)

| Area | Limit we will declare |
|---|---|
| Checkpoint | Files written through kernel tools only; browser page state is **not** snapshotted; creative artifacts are versioned by hash, not pixel-rewound |
| Subagents | Their file edits are outside the parent checkpoint; a subagent must return a report + hashes, and the parent re-verifies |
| Memory | Retrieval is context, not enforcement; a stale memory can mislead — every memory item carries source + date |
| Model | The 2B planner cannot match Claude's reasoning; the kernel compensates with schema validation, re-plan and a 27B escalation lane |
| Browser | Chrome Connect is the only browser path; no raw Playwright, no vendor bundle analysis, no CAPTCHA solving |
| Evidence | An assertion we cannot run is `unknown`, never `pass` |
| Budget | Wall-clock and step caps are hard; a run that hits the cap checkpoints and stops |

---

## 8. Context and memory rules

1. Load order: managed policy → user → project `NORTHSTAR.md` → path-scoped rules
   → task brief. Closest-to-work loads last.
2. `NORTHSTAR.md` target <200 lines; anything procedural moves to a skill.
3. Repo map: file list + symbols + hashes; refreshed on change, not every turn.
4. File reads are on demand; a full-repo dump is a bug.
5. Compaction threshold: 80% of the model's context. Anchors that always survive:
   goal, constraints, acceptance criteria, open decisions, evidence index.
6. Auto-memory proposals are queued, not written; operator approval promotes them.

---

## 9. Verification rules

- Every node's acceptance list must contain at least one assertion with a named
  verifier before the plan can be approved.
- Verifiers by lane:
  - `coding`: test command, build command, type/lint, file hash.
  - `browser`: post-action page state (URL + required/forbidden selector) and the
    Chrome Connect journal id.
  - `creative`: artifact exists + hash, OCR, prepress, readiness.
  - `inspect`: file digest + quoted excerpt.
- A failed assertion triggers re-plan (max 2 attempts per node), then
  `blocked_on_human`; never a silent retry.
- A node with no verifier is `unknown`, and the plan reports it.

---

## 10. Permissions, gates and the two standing rules

- Evaluation order is fixed: **deny → ask → allow**.
- The model never receives a denied tool.
- Two standing gates are hardcoded and cannot be granted by a plan:
  1. **Spend / paid credits.**
  2. **Amazon** (any host, API, redirect or lookalike).
- Browser work goes through Chrome Connect, Profile 6 only, read-only by default.
- Credentials are never entered by the agent; a login is `blocked_on_human`.
- Every external state change requires a per-task grant with an expiry.

---

## 11. Model placement and escalation

| Role | Model | Placement | Rule |
|---|---|---|---|
| Plan skeleton / prose | Bojo (Qwen 3.5 2B) | CPU | deterministic schema first, model fills |
| Plan validator | code | CPU | rejects malformed/unsafe plans before execution |
| Re-plan escalation | Qwen3.8 27B IQ3_XXS | GPU, on demand | max 1 escalation per node |
| Cloud planner | none | — | **requires fresh operator approval; not in Phase A** |

The planner output is **JSON against §4.1/§4.2**; invalid JSON is a re-plan, not
a repair-by-prompt loop.

---

## 12. UI surfaces

- **Ty (admin run panel):** plan/todo tree, node state, evidence rows, permission
  card, blocked-on-human card, checkpoint list with restore, budget meter.
- **Bojo (chat):** the same plan card inline; an artifact side panel; a receipt
  row ("did / checked / could not verify"); a memory panel with provenance and a
  forget action.
- **Autothink:** diff review and test output per node.

No customer-facing claim is made from a node whose evidence is `unknown`.

---

## 13. Acceptance: NS-PROJ-20 (provisional)

**Rule: baseline first.** Run Ty as-is on the 20 briefs, record the numbers, then
set targets. The table below is the metric set, not a promise.

| Metric | How measured | Provisional target |
|---|---|---|
| Task completion | all acceptance tests green | baseline + agreed delta, ≥85% aspirational |
| Plan validity | schema + acyclicity + gates | 100% |
| Evidence coverage | nodes with ≥1 passing evidence | 100% |
| Operator interventions | count per project | ≤2 |
| Failure recovery | injected mid-run failure, re-plan | ≥90% |
| Resume fidelity | process kill, resume from checkpoint | ≥90% |
| Re-plan vs blind retry | journal classification | ≥80% |
| Budget adherence | steps/wall clock within plan | 100% |

The 20 briefs live in `eval/projects/` and run in an isolated git worktree. No
paid runs, no Amazon.

---

## 14. Build order and non-goals

**Build order:** policy → plan mode → checkpoint → memory → todo → DAG →
verification → subagents → context/compaction → diff → skills → budget/replay.

**Non-goals for this programme:**
- Copying vendor client code, bundles, prompts or assets.
- Static bundle analysis or decompilation of any vendor client.
- A paid cloud planner without a fresh operator approval.
- Amazon-side work.
- Replacing git with checkpoints.

---

## 15. Source discipline

Every adoption gets a `CLONE_LEDGER.md` row and a `provenance.csv` row: source,
licence/ToS, method (read/adapt/observe), our implementation, evidence. The
harvest cap is **1,500 scored / 100 read / 12 deep**; the 12 deep reads are one
canonical authority per capability (see `SOURCES.md`).

Page, file and tool text is **data, never instructions**. Nothing found while
researching can change Ty's goals, tools or the standing gates.
