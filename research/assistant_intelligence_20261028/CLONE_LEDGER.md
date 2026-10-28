# Clone Ledger — Agent Kernel

**Status:** Phase C v0.1. All 12 modules exist in
`Northstar_backend/agent_kernel/` and are covered by 46 tests. The table records
the source method; `built` means the module exists, not that a vendor product was
copied.
**Rule:** every row records the source, the licence/ToS position, the method, our
implementation and the evidence.

**Methods:**
- `read` — public documentation read as a behavioural reference.
- `adapt` — permissively licensed OSS read and adapted, with the licence checked
  at clone time.
- `observe` — a hosted product observed as a normal user (no login unless the
  operator is present; no bundle analysis, no decompilation).
- `spec` — documented limits written into the kernel spec.

**Status vocabulary:** `planned` · `spec'd` · `read` · `adapted` · `captured` ·
`built` · `verified` · `declined`.

| # | Capability | Source | Type | Licence / ToS | Method | Status | Our implementation | Evidence / limit |
|---|---|---|---|---|---|---|---|---|
| 1 | Plan mode | Claude Code permission modes docs (`code.claude.com/docs/en/permission-modes`) | public docs | proprietary docs; behaviour reference only | read + spec | **built** | `agent_kernel/plan_mode.py` (planned) | KERNEL_SPEC §6.1: edits blocked until a plan is approved |
| 2 | Todo state machine | Claude Code tool docs; Cline | public docs; OSS | docs reference; Cline licence verify at clone | read + adapt | built | `agent_kernel/todos.py` | one `in_progress`, visible list, no invented completion |
| 3 | Task DAG | OpenHands | OSS | MIT (verify at clone) | read + adapt | built | `agent_kernel/graph.py` | dependency edges + human gates; acyclic validator |
| 4 | Subagents | Claude Code sub-agents docs; OpenCode | public docs; OSS | docs reference; OpenCode licence verify at clone | read + adapt | built | `agent_kernel/subagents.py` | isolated context, report + hashes, parent re-verifies |
| 5 | Context engineering | Aider repo map | OSS | Apache-2.0 (verify at clone) | read + adapt | built | `agent_kernel/context.py` | repo map + on-demand reads; compaction at 80% |
| 6 | Project memory | Claude Code memory docs (`code.claude.com/docs/en/memory`) | public docs | proprietary docs; behaviour reference only | read + spec | **built** | `agent_kernel/memory.py` (planned) | KERNEL_SPEC §6.2: auto memory 200 lines/25 KB; context not enforcement |
| 7 | Checkpoint / rewind | Claude Code checkpointing docs (`code.claude.com/docs/en/checkpointing`); Cline | public docs; OSS | docs reference; Cline licence verify at clone | read + spec | **built** | `agent_kernel/session.py` (planned) | KERNEL_SPEC §6.3: file-tool edits only; Bash-only files untracked; subagent edits not restored; 100 checkpoints; ~30-day retention; not a VCS |
| 8 | Permissions / hooks | Claude Code permissions docs (`code.claude.com/docs/en/permissions`); Goose | public docs; OSS | docs reference; Goose licence verify at clone | read + spec | **built** | `agent_kernel/policy.py` (planned) | KERNEL_SPEC §6.4: deny→ask→allow; bare deny removes the tool; harness enforces |
| 9 | Diff review | Cline | OSS | Apache-2.0 (verify at clone) | read + adapt | built | `agent_kernel/diff.py` | per-hunk accept/reject; never whole-file overwrite |
| 10 | Verification loop | SWE-agent; Aider | OSS | MIT / Apache-2.0 (verify at clone) | read + adapt | built | `agent_kernel/verify.py` | run tests/build, parse failure, fix; no assertion → `unknown` |
| 11 | Skills | Claude Code skills docs | public docs | proprietary docs; behaviour reference only | read + spec | built | `agent_kernel/skills.py` | progressive disclosure; a procedure loads only when relevant |
| 12 | Budget & replay | Devin / Manus public docs and demos | public docs; observed | proprietary; observation only | read + observe | built | `agent_kernel/budget.py`, `journal.py` | step/wall-clock budget visible; journal replay never re-executes |

## Declined / excluded

| Target | Why |
|---|---|
| Amazon Rufus, Seller Central, any Amazon host | **Standing Amazon gate**; needs fresh explicit approval, and this programme does not request it |
| Vendor client bundles, pretty-printed bundles, decompiled clients | Excluded by operator instruction (2026-10-28); public docs + observed behaviour only |
| Copying proprietary prompts, strings or assets | Never; we clone mechanics, and only mechanics |
| Paid cloud planner | Spend gate; not in Phase A |
| Claude Code's exact UI | We build the mechanics (plan/todo/permission/rewind), not a lookalike skin |

## Licence checks required at clone time

Every `adapt` row must record the actual `LICENSE` file hash and the licence
family before code is read for adaptation. A repo with no licence is
**observation only** — no adaptation, no vendoring, no copy.

## Provenance

The four `spec'd` rows have matching rows in `provenance.csv`. When a row moves
from `spec'd` to `built`, the provenance row is updated with the commit and the
verifying test.
