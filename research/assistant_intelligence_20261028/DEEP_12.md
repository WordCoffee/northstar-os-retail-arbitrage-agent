# The 12 deep reads — what each authority actually says

**Status:** Phase B deep-read notes. Sources are public documentation or public
OSS READMEs, accessed **2026-10-28**. No vendor client bundles, no decompilation,
no login-only material.

Each entry records: the source, the verified mechanism, the **documented limit**,
and the decision for our kernel (`KERNEL_SPEC.md`).

| # | Capability | Authority | Licence / ToS | Our module |
|---|---|---|---|---|
| 1 | Plan mode | Claude Code permission modes | docs (behaviour reference) | `plan_mode.py` |
| 2 | Todo state machine | Claude Code tools reference | docs (behaviour reference) | `todos.py` |
| 3 | Task DAG / delegation | OpenHands Agent Canvas + Cline teams | MIT / Apache-2.0 (README) | `graph.py` |
| 4 | Subagents | Claude Code sub-agents | docs (behaviour reference) | `subagents.py` |
| 5 | Context engineering | Claude Code costs/context + Cline project reading | docs / Apache-2.0 | `context.py` |
| 6 | Project memory | Claude Code memory | docs (behaviour reference) | `memory.py` |
| 7 | Checkpoint / rewind | Claude Code checkpointing | docs (behaviour reference) | `session.py` |
| 8 | Permissions / hooks | Claude Code permissions | docs (behaviour reference) | `policy.py` |
| 9 | Diff review | Cline | Apache-2.0 | `diff.py` |
| 10 | Verification loop | Cline + SWE-agent ACI | Apache-2.0 / MIT | `verify.py` |
| 11 | Skills | Claude Code skills | docs (behaviour reference) | `skills.py` |
| 12 | Budget & replay | Claude Code costs + OpenHands events | docs / MIT | `budget.py`, `journal.py` |

---

## 1. Plan mode

**Source:** `https://code.claude.com/docs/en/permission-modes` (accessed 2026-10-28).

**Verified:** Plan mode reads files and runs read-only shell commands to explore,
but **does not edit source files**; edits are **blocked until a plan is approved**.
The mode is one of `default → acceptEdits → plan → auto`; protected paths are
never auto-approved outside bypass.

**Documented limit:** the plan gate is a permission mode, not a suggestion. A
classifier-approved command may run only when auto mode exists.

**Decision:** our `plan_mode.py` makes `planning`/`awaiting_approval` side-effect
free and requires an approved plan before activation. We do **not** copy Claude's
UI or mode-cycle labels.

## 2. Todo state machine

**Source:** `https://code.claude.com/docs/en/tools-reference` (accessed 2026-10-28).

**Verified:** Claude Code exposes `TaskCreate`, `TaskGet`, `TaskList`,
`TaskUpdate`; `TaskUpdate` changes status, **dependencies** and details.
`TodoWrite` is disabled by default in favour of the task tools
(`CLAUDE_CODE_ENABLE_TASKS=0` re-enables it).

**Documented limit:** the task list is session-scoped and model-managed; it is
not durable project state.

**Decision:** our `todos.py` is a strict state machine with **one** running task;
`graph.py` owns dependencies. Durable state is the journal/checkpoint, not the
todo list.

## 3. Task DAG / delegation

**Sources:** `https://github.com/OpenHands/OpenHands` (MIT, README accessed
2026-10-28); `https://github.com/cline/cline` (Apache-2.0, README accessed
2026-10-28).

**Verified (OpenHands):** an Agent Server runs multiple agents; Agent Canvas
connects to multiple backends; an Automation Server runs agents on a schedule or
webhook; the system is split into frontend, agent SDK/server, TypeScript client
and automation repositories. The orchestration is service-level, not a single
chat loop.

**Verified (Cline):** a coordinator agent breaks work into subtasks and delegates
to specialist agents with their own tools and context; team state persists across
sessions; scheduled agents run on cron.

**Documented limit:** neither README specifies a formal DAG schema; both delegate
by task ownership. A cycle-free dependency graph is our addition.

**Decision:** `graph.py` implements a strict DAG (cycle detection, ready set,
parallel-safe groups); `subagents.py` owns delegation. A "team" is a set of nodes
with declared dependencies, not a second scheduler.

## 4. Subagents

**Source:** `https://code.claude.com/docs/en/sub-agents` (accessed 2026-10-28).

**Verified:** a subagent runs in **its own context window** with its own system
prompt, tool access and permissions; the parent sees only the final result, not
intermediate tool calls. Subagent descriptions count against context; a warning
appears when non-built-in descriptions exceed **15,000 tokens**. Background is
the default; foreground subagents show permission prompts inline. `maxTurns`
caps a subagent; reaching it returns partial output and the subagent can be
resumed.

**Documented limit:** the parent does not see the subagent's intermediate work,
and a subagent's file edits are not reliably part of the parent's checkpoint.

**Decision:** `subagents.py` requires a report with file hashes; the parent
re-verifies every hash and never trusts the summary alone. No shared mutable
state between workers.

## 5. Context engineering

**Sources:** `https://code.claude.com/docs/en/costs` (accessed 2026-10-28);
`https://github.com/cline/cline` README.

**Verified:** Claude Code tracks token usage per session, supports a
`--max-budget-usd` cap, and treats context management as a first-class cost lever
(compaction, model selection, preprocessing). Cline reads the project structure
and the relationships between files before editing.

**Documented limit:** the docs do not publish a universal compaction percentage;
our **80%** trigger is a design choice, not a copied constant.

**Decision:** `context.py` builds a repo map (path, size, hash, symbols), reads on
demand, and compacts with explicit anchors (goal, constraints, acceptance,
decisions). The compaction marker states how many messages were dropped.

## 6. Project memory

**Source:** `https://code.claude.com/docs/en/memory` (accessed 2026-10-28).

**Verified:** two systems — authored `CLAUDE.md`/`AGENTS.md` and auto memory; both
load at session start; auto memory loads the **first 200 lines or 25 KB**;
`CLAUDE.md` target is **<200 lines**; imports expand inline up to **four hops**;
path-scoped rules load only for matching files. **Memory is context, not
enforcement**; a `PreToolUse` hook is what blocks.

**Documented limit:** instructions can be ignored; they do not constrain tools.

**Decision:** `memory.py` loads `NORTHSTAR.md`/`AGENTS.md` with the same caps and
import depth. Auto-memory writes are **proposals** until approved. Enforcement
lives in `policy.py`.

## 7. Checkpoint / rewind

**Source:** `https://code.claude.com/docs/en/checkpointing` (accessed 2026-10-28).

**Verified:** a checkpoint is created before each turn; **100 most recent
checkpoints** per session; snapshots are deleted ~**30 days** after the session
last saved one. **Only file-tool edits are tracked**: a file only Bash changed is
untracked, while a file the file tool edited once is tracked and later Bash
changes to it are rewound. Subagent edits are generally not restored; symlinks
and hardlinks are skipped; manual/external changes and mid-turn messages are not
tracked. **"Not a replacement for version control."**

**Decision:** `session.py` snapshots only kernel file-tool writes, skips
symlinks/hardlinks, records a `git_status` snapshot as an explicit extra, and
states the scope on every restore. Git remains the durable record.

## 8. Permissions / hooks

**Source:** `https://code.claude.com/docs/en/permissions` (accessed 2026-10-28).

**Verified:** deny → ask → allow, **first match wins**, specificity does not
reorder; a broad deny cannot be carved out by a narrow allow. A bare-tool deny
**removes the tool from context**; a scoped deny leaves it available and blocks
matches. File-edit approval lasts the **session**; Bash/WebFetch persist **per
repository**. **"Permission rules are enforced by Claude Code, not by the
model."**

**Decision:** `policy.py` implements the same order and bare-tool removal, plus
two hardcoded gates (Amazon, spend). `bypassPermissions` is deliberately
unsupported. Grants are task-scoped and expire.

## 9. Diff review

**Source:** Cline README (Apache-2.0, accessed 2026-10-28).

**Verified:** every edit appears as a diff the user can **review, modify or
revert**; all changes are tracked with checkpoints so the agent's work can be
undone.

**Documented limit:** the README does not specify hunk-level selection semantics;
our parser is conservative and only exposes selected hunks.

**Decision:** `diff.py` parses unified diffs, counts additions/removals and
selects whole hunks. Applying a hunk is a separate, explicit step.

## 10. Verification loop

**Sources:** Cline README; SWE-agent README and paper
(`https://arxiv.org/abs/2405.15793`), MIT (accessed 2026-10-28).

**Verified (Cline):** it monitors linter and compiler errors while editing and
fixes missing imports/type errors before the user sees them; it runs tests and
watches command output.

**Verified (SWE-agent):** the Agent-Computer Interface is the contribution — the
tool surface and feedback shape determine performance; behaviour is governed by
a single YAML file; trajectories are the evaluation unit. SWE-agent notes that
**mini-swe-agent** has superseded it (65% on SWE-bench verified in ~100 lines).

**Documented limit:** benchmark success is measured against hidden tests; a green
local test is not proof of the benchmark.

**Decision:** `verify.py` requires a named verifier, records `unknown` when it
cannot measure, and treats an executor self-report as the **weakest** evidence
(`kind: executor`). No assertion, no `done`.

## 11. Skills

**Source:** `https://code.claude.com/docs/en/skills` (accessed 2026-10-28).

**Verified:** a `SKILL.md` body **loads only when the skill is used**, unlike
`CLAUDE.md`; skills follow the Agent Skills open standard; `!` command injection
runs before the model sees the content; skills can be scoped to enterprise,
personal, project, nested or added directories.

**Documented limit:** skill descriptions are always in context; the body is not.
A skill is instructions, not enforcement.

**Decision:** `skills.py` exposes metadata only until `load(name)`; selection is
deterministic token overlap, not a model call. A skill cannot grant a tool.

## 12. Budget & replay

**Sources:** `https://code.claude.com/docs/en/costs` (accessed 2026-10-28);
OpenHands Agent Server README; Claude Code checkpointing docs.

**Verified:** Claude Code reports per-session token usage and cost, supports a
per-run dollar cap (`--max-budget-usd`), and resets totals on `/clear`.
OpenHands separates the agent server from the automation scheduler, and stores
conversation/workspace state; checkpoints persist with the conversation and can
be rewound after resume.

**Documented limit:** token counts are estimates; the authoritative bill is the
provider console. Replay is state reconstruction, not re-execution.

**Decision:** `budget.py` enforces steps, wall clock and optional tokens as hard
stops. `session.Journal` is append-only; `replay()` reconstructs node state and
evidence and never re-runs a tool.

---

## What the twelve changed in the spec

1. **Policy before plan.** A plan without enforcement is a suggestion.
2. **Checkpoint scope is declared, not implied.** We match Claude's file-tool
   limit and add a git snapshot; we do not claim browser state is rewindable.
3. **Memory stays context.** Auto-memory is proposed, not written.
4. **Subagent reports are hash-checked.** A summary alone is not evidence.
5. **Verification is the product.** The executor's own `ok` is the weakest row.
6. **Budgets are stops.** No silent overrun, no retry past the cap.
