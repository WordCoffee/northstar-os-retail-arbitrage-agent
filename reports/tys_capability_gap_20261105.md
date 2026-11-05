# Ty's Assistant — capability gap vs Claude Code / Perplexity Computer

Date: 2026-11-05. Scope: what Ty can actually do today, what the two reference
products do that Ty cannot, and which free pieces close the gap.

Nothing was installed. Every licence below was read from the upstream `LICENSE`
file, and every candidate was put through the repo's own gate
(`Northstar_backend/provider_suite.py --check <id> --provider local`).

## What Ty actually has

Authoritative list from `Northstar_backend/agent_kernel/tool_protocol.py` — the
tools the model can call:

`read`, `write`, `write_many`, `list`, `grep`, `ast_grep`, `ast_edit`,
`ast_edit_batch`, `apply_patch`, `repo_pack`, `run`, `finish`

That is a genuine Claude-Code-class coding toolset: structured AST edits, batch
writes, a patch applier, repo packing for context, and command execution.

Modules that exist but are **not exposed as tools**:

| module | what it implements | exposed? |
|---|---|---|
| `subagents.py` | `run_subagents`, `merge` — parallel child agents | **no** |
| `todos.py` | `Todos` with start/verify/finish/fail/block | **no** |
| `plan_mode.py` | `PlanMode` propose/approve/activate/guard | **no** |
| `skills.py` | `SkillRegistry` — selectable skills from a directory | **no** |
| `graph.py` | dependency graph, topological order, parallel-safe sets | **no** |
| `eye.py` / `vision_verify.py` | local vision judging a produced step | **no** |
| `budget.py`, `policy.py`, `tracing.py`, `session.py`, `sandbox.py`, `self_heal.py`, `verify.py`, `hitl.py` | limits, policy, traces, sessions, isolation, repair, verification, human queue | no (supervisor-side) |

The supervisor-side ones are correctly not tools. The first six are capability
gaps: the code exists and nothing can reach it.

## Gap vs Claude Code

| capability | Claude Code | Ty today |
|---|---|---|
| file read / write / patch | yes | **yes** |
| AST-aware edit | no | **yes** (Ty is ahead here) |
| run commands | yes | **yes** |
| todo list the agent maintains | yes | module only, **no tool** |
| plan mode (propose → approve → execute) | yes | module only, **no tool** |
| subagents / parallel task fan-out | yes | module only, **no tool** |
| MCP **client** (consume external tool servers) | yes | **no** — Ty only *serves* MCP (`tools/northstar_mcp_server.py`) |
| context compaction | yes | **no** — `headroom` is in the registry as `not_installed` |
| glob | yes | no (`list` only) |

## Gap vs Perplexity Computer

| capability | Perplexity Computer | Ty today |
|---|---|---|
| web search | yes | **no** |
| fetch a page and extract clean text | yes | **no** |
| citations / provenance on claims | yes | partial (evidence files, not per-claim) |
| document parsing (PDF/tables) | yes | **no** (Docling/Surya identified earlier) |
| browser automation | yes | **yes** — Chrome Connect, better governed than either |
| code execution sandbox | yes | **yes** (`sandbox.py`) |

So the missing half is exactly the research half: **search, fetch, extract,
parse**. Ty can act but cannot read the web as a tool.

## Candidates, with licences read from upstream

| candidate | licence (upstream file) | gate result | closes |
|---|---|---|---|
| `mcp` (modelcontextprotocol/python-sdk) | **MIT** | `unknown_tool` | MCP client — the whole external tool ecosystem |
| `trafilatura` | **Apache-2.0** | `unknown_tool` | page → clean text, no browser |
| `ddgs` (deedy5/ddgs) | **MIT** | `unknown_tool` | web search |
| `headroom` | **Apache-2.0** | `not_installed` | context compaction |
| `searxng` | **AGPL-3.0** | `unknown_tool` | self-hosted metasearch (network copyleft → local lane only) |
| `docling` | **MIT** | `unknown_tool` | PDF/tables |
| `surya` | **Apache-2.0** | `not_installed` | layout + reading order |

Every one of these is refused today with `unknown_tool` or `not_installed`. That
refusal is correct: an unregistered tool may not be imported. Adoption needs a
registry entry in `shared/provider-suite.json`, which is **outside the loop's
commit allowlist** — an operator edit, by design.

## The policy constraint nobody should skip

A web fetch tool is not a licence question, it is a boundary question. Chrome
Connect is the controller for browser work because it enforces the host denylist,
the hardcoded Amazon blocklist, the profile lease and the audit chain.

`trafilatura` and `ddgs` are **not** browsers — they are HTTP client + parser, so
they do not bypass Chrome Connect's browser governance. But they *are* outbound
requests, so any adoption must:

1. refuse Amazon hosts and lookalikes before the request is made (same hardcoded
   blocklist, evaluated first), and
2. log the URL, timestamp and result to the same audit chain.

Without both, this is a second unguarded path to the web and should not ship.

## Recommended order

1. **`mcp` (MIT)** — highest leverage per line of code. Ty becomes a client and
   inherits the entire MCP ecosystem (filesystem, git, databases, docs) without
   writing any of it. No web-policy surface.
2. **`headroom` (Apache-2.0)** — already registered, just not installed. Long
   sessions are the first thing that breaks an agent, and this is the cheapest
   fix.
3. **`trafilatura` (Apache-2.0)** + **`ddgs` (MIT)** — the research half, *with*
   the Amazon refusal and audit requirement above. This is the Perplexity gap.
4. **`docling` (MIT)** — supplier PDFs and tables.
5. `searxng` only if a self-hosted search is wanted; AGPL network copyleft means
   local lane only and needs a licence review first.

## What this does not solve

Registering these does not make Ty "like Claude Code". The three modules that
matter most — subagents, todos, plan mode — are **already written and merely not
exposed**. Exposing them as tools is in-repo work with no licence question and no
operator decision, and it is probably worth more than any download. That is
recorded as the first backlog item below.

## Backlog

- `imp-expose-agent-tools` — expose `subagents`, `todos`, `plan_mode` (and
  `skills`) as callable tools. In-repo, no dependency, no gate.
- `imp-mcp-client` — blocked: needs a `mcp` registry entry (MIT).
- `imp-web-research-tools` — blocked: needs `trafilatura` + `ddgs` registry
  entries **and** the Amazon-refusal + audit design signed off.
- `imp-headroom-install` — blocked: install decision for an already-registered
  tool.
