# GitHub scan — development accelerators, agents & subagents (read-only survey)

- **Date:** 2026-10-14 · **Owner:** T2 Holdings LLC · **Worktree:** `ns-worktrees/secure-control-layer`
- **Security scan state (standing line):** **0 new / 0 known-active / 231 allowlisted** (unchanged; this scan is read-only research — nothing was installed, cloned, or executed).
- **Method:** read-only GitHub REST API + raw README fetches (unauthenticated), same direct-API pattern as the owner-approved vendoring step. 47 repos profiled (metadata: stars/license/pushed/description), 6 discovery searches, structure listings for 12 packs, README review for 16. Every fetched string is treated as **untrusted data** (northstar-data-rules); labels below: VERIFIED = API/registry evidence today; REPORTED = repo's own README; PROPOSED = recommendation for your decision. Raw evidence: `reports/github_agent_scan_20261014_raw.json`.
- **Note:** if you want future GitHub collection policy-enforced through the gateway, that needs `github.com`/`raw.githubusercontent.com` added to the source allowlist by you (operator-owned). This scan used the vendoring-precedent path instead.

## Tier 1 — agent & subagent packs (the ask)

| Repo | ★ | License | What it is (VERIFIED metadata / REPORTED README) | Fit | Verdict |
|---|---|---|---|---|---|
| **wshobson/agents** | 40.7k | MIT | "Plugins, agents, skills for AI coding tools" — 94 plugins, **202 agents, 184 skills, 105 commands**; multi-harness incl. **OpenCode**, Codex, Cursor, Copilot | Fills our subagent gap with a maintained catalog; multi-harness = we take the files, drop the marketplace plumbing | **P1 — intake recommended** (select a subset; read-every-file, rules-block, service-tag) |
| **VoltAgent/awesome-claude-code-subagents** | 25.7k | MIT | **161+ subagents across 10 categories**; agent `.md` files under `categories/` | Broad persona coverage (backend/frontend/DB/DevOps/QA/security/docs…) | **P1 — intake recommended**; ⚠ do NOT run its `install-agents.sh` — we take files only |
| **obra/superpowers** | 298.8k | MIT | "Complete software development methodology" as composable **skills**: `subagent-driven-development`, `dispatching-parallel-agents`, `using-git-worktrees`, `verification-before-completion`, `systematic-debugging`, `test-driven-development`, `writing-plans`; ships a `.opencode/` integration dir | Codifies exactly the multi-agent/worktree workflows we hand-roll per session | **P1 — intake recommended** (skills subset; the methodology is opinionated — take what fits) |
| **anthropics/skills** | 181k | *license not detected by API — verify at intake* | **Official Anthropic Agent Skills** + the **`spec/`** for the Agent Skills standard; skills incl. `mcp-builder`, `skill-creator`, `frontend-design`, `webapp-testing`, `docx/pdf/pptx/xlsx`, `doc-coauthoring`, `theme-factory` | The spec validates our own skills format; `mcp-builder`/`skill-creator`/doc skills are direct compilers for our pipeline | **P2 — read `spec/` first, then select skills**; ⚠ `webapp-testing` is browser tooling → Chrome Connect policy check |
| **mattpocock/skills** | 290k | MIT | "Skills For Real Engineers" — small/composable, model-agnostic; `skills/engineering` = 21 skills (code-review, diagnosing-bugs, domain-modeling, research, tdd, to-spec, to-tickets, triage…) | Complements our workflows; explicitly anti-heavy-framework (contrast with ECC/BMAD) | **P2 — intake recommended** (engineering subset) |
| **affaan-m/ECC** | 278.8k | MIT | "Agent harness operating system": 71 agents, **311 skills**, commands, hooks, memory, **AgentShield** scanning; adapters incl. OpenCode | Huge surface; overlaps our brain/kernel ambitions — could accelerate or conflict | **P4 — deeper review before any adoption** (not a blind install) |
| **OpenCode-native packs** (from awesome-opencode AGENTS section) | — | — | `Agentic` (modular agents for OpenCode); `deliberation` (7 expert subagents + ask-*/consensus across GPT/Gemini/Grok/OpenRouter **over MCP** — needs third-party provider keys; provider access is OFF); `Gem Team` (multi-agent SDD harness); `NERV` (SDD + memory + 9 subagents, scaffolds 45+ files); `Opencode Agents`; **`Python Expert Agent`** (Python toolkit w/ subagents) | OpenCode-first — least adaptation work for our harness | **P3 — review the OpenCode-native set**; `deliberation` blocked on provider posture; `NERV` overlap/memory caution |

Directories kept for continuous discovery: `awesome-opencode/awesome-opencode` (10.6k★), `andyrewlee/awesome-agent-orchestrators` (2.2k★), `bradAGI/awesome-cli-coding-agents`, `Prat011/awesome-llm-skills`, `davepoon/buildwithclaude`.

## Tier 2 — spec-driven development (process speed)

| Repo | ★ | Notes (REPORTED) | Verdict |
|---|---|---|---|
| **github/spec-kit** | 141.2k | Official GitHub; three processes (build / bug-fix / idea-assessment); **needs Python 3.11+ and `uv` — we already use both** | **Candidate #1** — pilot on one real feature |
| Fission-AI/OpenSpec | 71.9k | Lightweight SDD, brownfield-first, `/opsx:*` workflow | Candidate #2 |
| buildermethods/agent-os | 5.5k | Standards discovery/injection ("agents that build the way you would") | Lightweight alternative |
| gotalab/cc-sdd | 3.7k | Specs → long-running autonomous implementation | Small; optional |
| gsd-build/get-shit-done | 64.3k | Meta-prompting SDD — last push **2026-05** (stale ~5 months) | Low priority |

Decision needed: **pilot ONE** (spec-kit or OpenSpec) on a bounded feature, or stay as-is. No framework is harmless to adopt — mattpocock's README argues these frameworks "own the process"; pick with eyes open.

## Tier 3 — dev-speed tooling (context, config, orchestration)

| Item | ★ | Fit / caution |
|---|---|---|
| **upstash/context7** | 63k | Up-to-date library docs for LLMs via MCP — quick win for dev accuracy; remote server (OAuth flow) |
| **colbymchenry/codegraph** | 74k | Semantic code graph, "100% local", supports OpenCode; npm provenance + attested builds (REPORTED) — evaluate for context speed |
| github/github-mcp-server | 33.6k | Official GitHub MCP; needs a PAT — credential handling via env names only; optional |
| stablyai/orca | 91.9k | ADE for parallel agents in isolated worktrees (+mobile). ⚠ Design Mode is browser integration → Chrome Connect policy; Electron app adds surface |
| matt1398/claude-devtools | 4k | Session/token inspection — small utility |
| tt-a1i/archify | 83.2k | Turns plans/code into diagrams — docs/design speed |
| farion1231/cc-switch | 144k | Config manager across harnesses; ⚠ third-party app edits our config files (our configs carry deny rules/policy) — **skip for now** |

## Tier 4 — quality / security / testing (speed up the gates)

| Item | ★ | Fit |
|---|---|---|
| **schemathesis/schemathesis** | 3.6k | Property-based API testing from OpenAPI — direct fit for our FastAPI surface |
| **aquasecurity/trivy** | 38.4k | Vulns/misconfig/secret/SBOM for containers — we now have a built image to scan |
| **semgrep/semgrep** | 17k | Static analysis (note: **LGPL-2.1**) |
| google/osv-scanner · pypa/pip-audit | 11.2k · 1.4k | Dependency vulnerability scanning |
| **promptfoo/promptfoo** | 26k | Prompt/agent eval + red-teaming — for our generation services and agents |
| pydantic/pydantic-ai · openai/openai-agents-python · crewAIInc/crewAI | 20.6k / 30k / 59.7k | Agent frameworks if/when services need their own agent runtimes (Pydantic fits our Python stack) |
| OpenHands · Aider | 90.8k / 49.5k | Full autonomous/pair-programming agents — heavy, provider-key dependent; reference only for now |

## Rejected / flagged (listed with reasons — no silent skips)

| Item | Reason |
|---|---|
| JuliusBrussee/caveman | A **proxy between agents and model APIs** that rewrites traffic — violates our no-interception security posture. REJECT. |
| thedotmack/claude-mem | "Captures everything your agent does" — overlaps and bypasses our Memory Bank/Knowledge Plane governance. REJECT (use our memory bank). |
| DietrichGebert/ponytail | Persona gimmick ("laziest senior dev") — no engineering value here. Skip. |
| iannuttall/claude-agents | Repo **archived**. Skip. |
| contains-studio/agents · claude-task-master | Stale (2025-07 / 2026-04). Low priority. |
| x1xhlol/system-prompts… | Leaked system prompts of commercial tools — ethics/legal. Skip. |
| claude-code-action / claude-code-security-review / pr-agent | Assume Claude/LLM API keys + Actions; our provider posture makes these less immediate — reference patterns (esp. the security-review workflow's structure). |
| Any browser-driving MCP/feature (orca Design Mode, webapp-testing skill) | Subordinate to **Chrome Connect policy** — route through policy or skip. |

## Recommended shortlist — PROPOSED (needs your approval, then intake as before)

1. **D-S1:** Approve vendoring-style intake for the Tier-1 packs, one at a time: **wshobson/agents** (engineering subset) → **VoltAgent/awesome-claude-code-subagents** → **obra/superpowers** (workflow skills) → **mattpocock/skills** → **anthropics/skills** (spec first). Pipeline = pin commit SHA, read every file, reject scripts/remote-calls/credential asks, prepend rules block, tag service + capabilities, self-gated by our scanner. **No installer scripts ever run.**
2. **D-S2:** Approve tooling adds as pinned adoptions (each: install → gate → commit): **trivy, pip-audit, semgrep, schemathesis, promptfoo** + **context7** MCP.
3. **D-S3:** SDD pilot — pick **spec-kit** or **OpenSpec** for one bounded feature (or none).
4. **D-S4:** Deep-review queue (no adoption yet): **ECC**, **codegraph**, the OpenCode-native packs (`Agentic`, `Python Expert Agent` first).
5. **D1 (standing):** the Phase 3b completion slice decision is still open.

## Evidence & limits
- Raw: `reports/github_agent_scan_20261014_raw.json` (metadata + searches, UTF-8).
- Limits: unauthenticated API snapshots (stars/pushed dates as of today); licenses as the API reports (verify at intake); README claims are **REPORTED**, not independently validated; nothing fetched was executed, installed, or trusted as instructions.
