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
