# Sources Plan — Agent Kernel (1,500 / 100 / 12)

**Status:** Phase B executed 2026-10-28. **Actual: 1,500 scored, 100 README
reads, 12 deep.** Sources: `SOURCES_1500.csv`, `TRIAGE.md`, `DEEP_12.md`,
`readmes/` (local evidence; not committed to avoid redistributing vendor docs).

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

## 3. The 1,500 scored — actual composition

| Lane | Count | Source | Method |
|---|---|---|---|
| GitHub search (20 query families, 100/page) | 746 | GitHub public API | metadata only |
| Existing local corpus, agent/kernel terms | 754 | `Northstar_backend/data/northstar.db` | metadata only |
| **Total scored** | **1,500** | | |
| README reads | 100 | `raw.githubusercontent.com` | public README, first 20 KB |
| Deep reads | 12 | public docs + public OSS | hand-written notes (`DEEP_12.md`) |

**Query families (20):** agent harness, coding agent, computer-use agent, browser
agent, plan mode, subagent, checkpoint, agent memory, repo map, agent eval,
human-in-the-loop, MCP framework, commerce copilot, seller assistant, voice agent,
autonomous agent, LLM agent framework, workflow automation, agent toolkit, AI
assistant desktop.

Every row has: `type, name, url, licence, stars, pushed_at, description,
capabilities, ty_score, bojo_score, rea_feasibility, read_target, source,
homepage, read_note`.

**Licence position:** 835 read/adapt candidates (permissive), 75 read-only
(copyleft), 590 **observe only** (no licence / NOASSERTION). An observe-only row
may inform a behavioural note; it is never copied.

**Triage:** deterministic rules + stars; no model judgement at this scale. The
metadata scoring surfaces candidates, not proof of quality — `TODOMVC` appearing
on a "todo" keyword is the kind of false positive the read step exists to catch.

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
