# Skill intake summary - all 5 approved packs (D-S1) - 2026-10-14

- **Security scan state (standing line):** **0 new / 0 known-active / 231 allowlisted** (exit 0). **Tests:** `tests/security` **219/219**.
- Intake ran exactly as proposed: pin commit SHA -> catalog -> select -> fetch -> read every file (automated full-content scan + excerpts) -> reject/adapt -> rules-blocked install (self-gated by the secret scanner) -> docs + tests + commit. No vendor installer script was ever run; vendor scripts/references were never taken.

## Packs

| # | Pack | Pinned commit | Catalog | Installed | Commit |
|---|---|---|---|---|---|
| 1 | wshobson/agents | `46891e7e60da0e52baf1050b7b6391b64e84c6d9` | 94 plugins / 202 agents / 184 skills | **24** (14 agents + 10 skills) | `1ffc7f4` |
| 2 | VoltAgent/awesome-claude-code-subagents | `408d3c9eee2d0c75c12a3abb5de29e53c2ca6b9e` | 161+ personas / 10 categories | **12** | `a5d4b62` |
| 3 | obra/superpowers | `bb92a77741419a4ab5f06e711a283343f1ada0c3` | 15 skills | **13** (2 system-meta skipped) | `d91a803` |
| 4 | mattpocock/skills | `49dd158d1076134a641b33efb035946536778336` | engineering/productivity/misc | **14** | `e7a93ec` |
| 5 | anthropics/skills | `dbd4588f9e1033efb41dad4bef2f7947c8993d44` | per-skill licensed; doc skills source-available | **1** (mcp-builder, Apache-2.0 LICENSE included) | `3f63b5b` |

**Total: 77 vendored skills (79 skill dirs incl. the 2 Northstar-authored).** Every skill carries the rules block, a service tag, required capabilities, per-skill adaptations, and pinned provenance; per-pack count + provenance tests enforce the invariants; evidence JSON per pack in `reports/*_intake_scan_20261014.json`; full chronicle in `docs/VENDORED_SKILLS.md`.

## Rejections & exclusions (consolidated, with reasons)

| Item | Reason |
|---|---|
| `mp-wizard` (mattpocock) | Generates secret-entry plumbing (hidden secret prompts, `.env` upserts, `gh secret` writes) - contradicts credential rules. |
| `mp-git-guardrails` (mattpocock) | Claude Code-specific hook setup; wrong harness (our git guardrails are stronger and already enforced). |
| `skill-creator` (anthropics) | Workflow hard-coupled to vendor `scripts/` + eval-viewer loops; would instruct executing vendor code we do not take. |
| `docx` / `pdf` / `pptx` / `xlsx` (anthropics) | Explicitly source-available, not open source - not redistributable. |
| `webapp-testing` + browser/dev-preview skills (anthropics, wshobson's excluded set) | Browser automation - outside the Chrome Connect policy. |
| `agency-multi-platform-publisher` (prior intake, still absent) | Remote-publishing/credentialing stack (from Intake 1). |

## Notes & follow-ups
- Selection principle: non-redundant coverage for our stack (Python/FastAPI, DB, testing/TDD, debugging, review, security/STRIDE, PowerShell, Docker, MCP, refactoring, docs, process/plans/worktrees).
- Both large catalogs retain >150 unselected personas/skills each; more picks available on request (same pipeline).
- **Owner decisions still open:** D-S2 tooling adds (trivy, pip-audit, semgrep, schemathesis, promptfoo, context7); D-S3 SDD pilot (spec-kit vs OpenSpec); D-S4 deep reviews (ECC, codegraph, OpenCode-native packs); **D1** Phase 3b completion slice (standing).