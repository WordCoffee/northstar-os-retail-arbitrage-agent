# Vendored skills — provenance, review, and results (Phase 6)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **0 new / 0 known-active / 231 allowlisted** (the install self-gates: every written file is re-scanned before commit).
- **License (both repos):** MIT (per repository license).
- **Review method:** full-content automated scan of every candidate file (patterns: scripts/exec/remote-call/credential markers; heads; flagged excerpts with context) + flagged-context review; raw scan saved as `reports/vendoring_scan_20261011.json`. Only then installed, with the Northstar rules block prepended.

## Pinned sources

| Vendor | Repo | Commit (pinned) |
|---|---|---|
| marketingskills | https://github.com/coreyhaines31/marketingskills | `1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff` |
| agency-agents | https://github.com/msitarzewski/agency-agents | `f99f6aa910a442b0197b768ce0ea7751e35e2060` |

## Installed (14, each with rules block + service tag + Amazon adaptations + provenance)

| Skill ID | Source file | Service tag | Result |
|---|---|---|---|
| `mk-copywriting` | marketingskills `skills/copywriting/SKILL.md` | listing-forge | installed |
| `mk-seo-audit` | marketingskills `skills/seo-audit/SKILL.md` | listing-forge | installed |
| `mk-ad-creative` | marketingskills `skills/ad-creative/SKILL.md` | ad-pilot | installed (vendor CLI example annotated as reference-only) |
| `mk-analytics` | marketingskills `skills/analytics/SKILL.md` | ad-pilot | installed |
| `mk-competitor-profiling` | marketingskills `skills/competitor-profiling/SKILL.md` | source-scout | installed |
| `agency-security-ai-code-auditor` | agency-agents `security/...` | research | **installed + sanitized** (2 token-shaped teaching samples replaced) |
| `agency-test-automation-engineer` | agency-agents `testing/...` | research | installed (Playwright CI example annotated: runs only under Chrome Connect/gateway policy) |
| `agency-api-platform-engineer` | agency-agents `engineering/...` | research | installed |
| `agency-ui-designer` | agency-agents `design/...` | listing-forge | installed (specs-only note: UI rebuilt separately) |
| `agency-fpa-analyst` | agency-agents `finance/...` | research | installed |
| `agency-product-manager` | agency-agents `product/...` | research | installed |
| `agency-ppc-strategist` | agency-agents `paid-media/...` | ad-pilot | installed |
| `agency-search-query-analyst` | agency-agents `paid-media/...` | ad-pilot | installed |
| `agency-content-creator` | agency-agents `marketing/...` | social-pulse | installed |

## Rejected (1) — listed per directive

| Candidate | Reason |
|---|---|
| `agency-multi-platform-publisher` (agency-agents `marketing/...`) | Contains an executable remote-publishing stack: `curl` calls to a local publish API, background daemons (`headless=false`), MCP publish servers, and `Credential(sessdata=…)` cookie handling. **Rejected**: executes scripts / fetches remotely / credential plumbing — contradicts Northstar rules. Not installed. |

## Edits applied during install (all documented)

1. **Rules block + adaptations**: identical binding block (from `northstar.brain`) prepended to every skill; per-skill Northstar "Amazon adaptations" section added (targeted notes, not vendor-content rewrites); service tag + required capabilities (none — text-only personas).
2. **Sanitization**: `agency-security-ai-code-auditor` — the two token-shaped teaching samples (in its leaked-secret example) were regex-replaced with a clearly non-token placeholder; the lesson is preserved, no token shapes ship. Verified by the scanner-finding-free install gate and a dedicated test.
3. **No other packs** were fetched; only the 15 listed files (14 installed + 1 rejected) were downloaded from the two official repos at the pinned commits.

## Evidence
- Raw review scan: `reports/vendoring_scan_20261011.json` — **sanitized post-capture**: token-shaped vendor samples in the excerpts were replaced with the same `sk-<EXAMPLE-NOT-A-KEY>` placeholder used at install (the secret gate caught the captured excerpt; fixed, not allowlisted).
- Install gate: every written file re-scanned with the repo scanner (0 findings); `tests/security/test_vendored_skills.py` (5 tests) enforces the invariants.

## Intake 2 - wshobson/agents engineering pack (2026-10-14)

- **Pinned:** https://github.com/wshobson/agents @ commit `46891e7e60da0e52baf1050b7b6391b64e84c6d9` (MIT). Catalog: 94 plugins; **24 files selected** (14 agents + 10 skills) of ~202 agents / 184 skills - more remain available for future picks.
- **Review method:** full-content automated scan of every candidate (scripts/exec/remote-call/credential markers + URL inventory), excerpt review, then the repo's secret scanner over the set - **0 findings**; all pattern hits were domain prose (auth vocabulary, "Amazon Neptune" as a DB name, Playwright in tool lists - governed by adaptation notes). Scan evidence: `reports/wshobson_intake_scan_20261014.json`.
- **Installed (24):** agents - `wsh-python-pro`, `wsh-fastapi-pro`, `wsh-backend-architect`, `wsh-backend-security-coder`, `wsh-database-architect`, `wsh-test-automator`, `wsh-tdd-orchestrator`, `wsh-error-detective`, `wsh-code-reviewer`, `wsh-architect-review`, `wsh-security-auditor`, `wsh-threat-modeling-expert`, `wsh-performance-engineer`, `wsh-api-documenter`; skills - `wsh-python-structure`, `wsh-python-patterns`, `wsh-python-errors`, `wsh-async-python`, `wsh-fastapi-templates`, `wsh-pg-table-design`, `wsh-openapi-specs`, `wsh-stride-patterns`, `wsh-auth-patterns`, `wsh-sql-optimization`.
- **Edits applied at install:** rules block prepended; service tag `research`; required capabilities none; per-skill **Northstar adaptations** (browser automation only under the Chrome Connect policy for `wsh-test-automator` / `wsh-performance-engineer`; auth-flow build deferred to the UI session for `wsh-auth-patterns`; zero-outbound invariants for API/DB skills). Vendor frontmatter stripped; no vendor scripts, commands, hooks, or reference files were taken (SKILL.md bodies only).
- **Tests:** `tests/security/test_vendored_skills.py` extended (dir count = 2 + 14 + 24 = 40; pinned-provenance check for the new pack; banned-phrase sweep covers all 38 vendored skills).
## Intake 3 - VoltAgent awesome-claude-code-subagents (2026-10-14)

- **Pinned:** https://github.com/VoltAgent/awesome-claude-code-subagents @ commit `408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e` (MIT). **12 personas selected** for non-redundant coverage (PowerShell 7 + 5.1, API design, auth integration, Docker, penetration testing, PS security hardening, AI-writing audit, prompt engineering, DB optimization, MCP development, refactoring).
- **Review method:** full-content automated scan + secret scanner over the set - **0 findings**; flags were domain prose (auth vocabulary, Docker secret-injection notes, credential-pattern guidance - all adaptation-governed). No vendor installer (`install-agents.sh`) was run; files only. Scan evidence: `reports/volt_agents_intake_scan_20261014.json`.
- **Installed (12):** `volt-powershell-7`, `volt-powershell-51`, `volt-api-designer`, `volt-auth-integration-engineer`, `volt-docker-expert`, `volt-penetration-tester`, `volt-powershell-security`, `volt-ai-writing-auditor`, `volt-prompt-engineer`, `volt-database-optimizer`, `volt-mcp-developer`, `volt-refactoring-specialist`.
- **Edits applied at install:** rules block prepended; service tag `research`; capabilities none; per-skill Northstar adaptations (pen-test = owner-scheduled with local dry-runs only; MFA flows deferred to the UI session; MCP surface = the three gateway tools only; Windows hardening only with approval).
- **Remaining in the pack:** ~150 more personas (other languages/stacks/domains) - available for future picks on request.
## Intake 4 - obra/superpowers workflow skills (2026-10-14)

- **Pinned:** https://github.com/obra/superpowers @ commit `bb92a77741419a4ab5f06e711a283343f1ada0c3` (MIT). **13 of 15 skills selected** - the two skipped files (`using-superpowers`, `diagnosing-superpowers`) are system-meta for the vendor's own plugin machinery.
- **Review method:** full-content automated scan + secret scanner over the set - **0 findings**. Flags were inert process documentation (bash fences with git/npm example commands); one adaptation strengthened: push/PR workflows constrained to non-protected branches, never forced. Scan evidence: `reports/superpowers_intake_scan_20261014.json`.
- **Installed (13):** `sp-brainstorming`, `sp-dispatching-parallel-agents`, `sp-executing-plans`, `sp-finishing-a-development-branch`, `sp-receiving-code-review`, `sp-requesting-code-review`, `sp-subagent-driven-development`, `sp-systematic-debugging`, `sp-test-driven-development`, `sp-using-git-worktrees`, `sp-verification-before-completion`, `sp-writing-plans`, `sp-writing-skills`.
- **Why:** these codify the exact workflows this workstream runs by hand - subagent dispatch, worktree isolation, plan execution with ledgers, verification-before-completion, review handoff.
- **Edits applied at install:** rules block prepended; service tag `research`; capabilities none; per-skill Northstar adaptations (worktree-per-session under ns-worktrees/; local-commit discipline; gates = scanner + tests; authority order binds subagents).
## Intake 5 - mattpocock/skills engineering + productivity (2026-10-14)

- **Pinned:** https://github.com/mattpocock/skills @ commit `49dd158d1076134a641b33efb035946536778336` (MIT). **14 of the fetched 15 installed**; picks focus on the spec/tickets/implement loop, design vocabulary, research/retro/triage/wayfinder process, handoff and agent-writing craft.
- **Review method:** full-content automated scan + secret scanner - **0 findings**.
- **Rejected (1, listed):** `mp-wizard` - generates secret-entry plumbing (hidden secret prompts, `.env` upserts, `gh secret` writes) - contradicts Northstar credential rules (.env never written; values never handled). NOT installed.
- **Skipped (1, listed):** `mp-git-guardrails` - Claude Code-specific hook setup (wrong harness; our git guardrails are stronger and already enforced). NOT installed.
- **Installed (14):** `mp-to-spec`, `mp-to-tickets`, `mp-implement-spec`, `mp-codebase-design`, `mp-domain-modeling`, `mp-grill-with-docs`, `mp-grilling`, `mp-improve-architecture`, `mp-research`, `mp-retro`, `mp-triage`, `mp-wayfinder`, `mp-handoff`, `mp-writing-for-agents`.
- **Note:** `mp-grill-with-docs` composes `mp-grilling` + `mp-domain-modeling` (both now installed). Vendor `disable-model-invocation` hints are inert metadata (stripped with the vendor frontmatter).
- **Edits applied at install:** rules block prepended; service tag `research`; capabilities none; per-skill Northstar adaptations (no external issue tracker - specs/tickets are local files; research via approved sources only; retros feed state/lessons).
- **Remaining in the pack:** other engineering/productivity/misc skills (code-review, diagnosing-bugs, pr, prototype, teach, etc.) - available for future picks on request.