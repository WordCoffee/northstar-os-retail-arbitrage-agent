# Sources Plan — Agent Kernel (1,500 / 100 / 12)

**Status:** Phase A plan. **Honest counts today: 0 scored, 0 read, 0 deep.**
This file defines the pool and the method; Phase B fills it. Any claim of a
completed count before the CSV exists would be false.

**Constraints (operator, 2026-10-28):**
- No static bundle analysis, no decompilation, no vendor-client reverse-engineering.
- Public docs, public OSS code (licence-checked), observed behaviour only.
- Operator windows: **one 45-min Claude Code, one 45-min Cowork. Nothing else.**
- No Amazon; no spend; no paid cloud planner.
- Cap: **1,500 scored / 100 read / 12 deep.**

---

## 1. The 12 deep reads — one canonical authority per capability

| # | Capability | Canonical authority | Type | Why this one |
|---|---|---|---|---|
| 1 | Plan mode | Claude Code permission-modes + Cowork help | public docs | the reference itself; approval gate + read-only semantics |
| 2 | Todo state machine | Claude Code tool docs + Cline plan/act | docs + OSS | visible task list, one active task |
| 3 | Task DAG | OpenHands architecture | OSS (MIT, verify) | event stream + delegation + runtime isolation |
| 4 | Subagents | Claude Code sub-agents docs | public docs | isolated context, report-back contract |
| 5 | Context engineering | Aider repo map + Claude Code compaction notes | OSS + docs | the smallest correct repo-map implementation |
| 6 | Project memory | Claude Code memory docs | public docs | `CLAUDE.md` / auto-memory split and its documented limits |
| 7 | Checkpoint / rewind | Claude Code checkpointing docs | public docs | the exact tracking limits we must match or exceed |
| 8 | Permissions / hooks | Claude Code permissions docs + Goose | docs + OSS | deny→ask→allow, bare-tool removal, harness enforcement |
| 9 | Diff review | Cline diff/checkpoint docs | OSS | per-hunk accept/reject |
| 10 | Verification loop | SWE-agent ACI + Aider test loop | OSS + paper | run → parse → fix, with a trajectory |
| 11 | Skills | Claude Code skills docs | public docs | progressive disclosure, not a prompt dump |
| 12 | Budget & replay | Devin / Manus public docs + demos | docs + observed | long-run budget, replay, "knowledge" capture |

Each deep read produces a note with: URL/clone hash, licence, access date, the
claims it supports, and the exact limit we will adopt or reject.

---

## 2. The 100 reads — 8 per capability

Families, not a fixed list; Phase B picks the best 8 per row and records why.

| Family | Examples | Capabilities served |
|---|---|---|
| Claude Code docs | plan, memory, checkpoint, permissions, subagents, skills, hooks, settings, tools, CLI | 1, 2, 4, 6, 7, 8, 11 |
| Cowork help / demos | computer use, folder scope, handoff | 1, 3, 7 |
| Cline / Roo Code | plan-act, checkpoints, diff, MCP | 2, 7, 9 |
| Aider | repo map, edit formats, git integration | 5, 10 |
| OpenHands | controller, event stream, delegation, runtime | 3, 4 |
| SWE-agent | ACI, trajectories, evaluation | 10 |
| Goose | recipes, extensions, permissions | 8, 11 |
| OpenCode | agents, permissions, sessions, tools | 2, 8, 9 |
| Public engineering posts | Devin, Manus, Cursor, Warp, Sourcegraph | 3, 7, 12 |
| Eval literature | SWE-bench, GAIA, WebArena, OSWorld, AgentBench | 10, 13 (acceptance) |
| Seller-facing analogues (Bojo) | Shopify Sidekick, Canva Magic Studio, Packify (done) | plan cards, artifact edit, receipts |
| Voice (later) | OpenAI Realtime, ElevenLabs Agents, Gemini Live | Bojo duplex voice |

---

## 3. The 1,500 scored — pool composition

| Lane | Count | Source | Method |
|---|---|---|---|
| OSS agent harnesses / frameworks | 600 | GitHub API (topics, stars, licence, pushed_at) | metadata only until shortlisted |
| Public docs / help centres / changelogs | 350 | `corpus_learner.py` (robots-honouring, throttled, provenance) | static fetch |
| Papers / benchmarks / evals | 250 | arXiv / ACL / papers-with-code | metadata + abstract |
| HF models / spaces / datasets | 150 | HF API | metadata |
| Videos / transcripts | 100 | public transcripts (existing 884 + new) | transcript only |
| Product marketing / pricing pages | 50 | public pages | static fetch |

**Query families (~30), grouped:**
- agent harness, coding agent, computer-use agent, browser agent, plan mode,
  todo list, subagent, checkpoint, rewind, permission, hooks, memory,
  compaction, repo map, skills, diff review, trajectory, eval harness,
  human-in-the-loop, approval, runbook, session replay, budget, sandbox,
  worktree, tool gateway, MCP, commerce copilot, seller assistant, voice agent.

Every row gets: `id, type, url/repo, licence, stars/downloads, pushed_at,
capability_tags[], ty_score, bojo_score, rea_feasibility, read? (y/n), deep?
(y/n), notes`.

**Triage:** deterministic rules + local `qwen3-embedding:0.6b` against the 12
capability rubrics. No model decides at this scale; a model only writes notes for
the 100 shortlisted reads.

---

## 4. Exclusions (hard)

| Excluded | Reason |
|---|---|
| Amazon hosts / APIs / Rufus / Seller Central | standing Amazon gate |
| Vendor client bundles, decompiled clients, pretty-printed JS | operator instruction |
| Login-only surfaces without the operator present | no credential entry |
| Paid sources / paid model runs | spend gate |
| Repos with no licence for adaptation | observation only, never copied |
| Anything that requires solving a CAPTCHA | never |

---

## 5. Operator windows (only two)

| Window | Target | What we capture (read-only) | Deliverable |
|---|---|---|---|
| 1 × 45 min | Claude Code | plan approval, todo rendering, permission card, checkpoint/rewind, compaction notice | `captures/claude_code.md` + screenshots |
| 1 × 45 min | Cowork | folder-scoped task, parallel agent handoff, blocked-state card, resume | `captures/cowork.md` + screenshots |

No other signed-in capture is in scope. Chrome Connect is the only browser path;
Profile 6 only; no credentials entered by the agent.

---

## 6. Outputs

```
research/assistant_intelligence_20261028/
  KERNEL_SPEC.md          (this phase)
  CLONE_LEDGER.md         (this phase)
  SOURCES.md              (this file)
  SOURCES_1500.csv        (Phase B — does not exist yet)
  TRIAGE.md               (Phase B — counts + method)
  captures/               (Phase C — two operator windows)
```

A row may only appear as `deep` when its note exists and cites a URL/hash and an
access date. A count without the CSV is not a result.
