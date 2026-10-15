# GitHub HUNT verdicts — every profiled repo (2026-10-14)

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. **Candidates only — nothing installed, nothing vendored.**
- **Scope:** every repo profiled in the hunt (25 via metadata batches + notable search-discovered repos) plus the owner-directed verdicts for repos named in the completion directive.
- **Method recap:** read-only GitHub API + `git ls-remote` + search; **last-commit = `pushed_at` (proxy)**; licenses via API + `/license` path; stars informational. Evidence: `reports/github_hunt_evidence_20261014.json` (plus the earlier hunt report `reports/github_hunt_20261014.md`).
- **`mcp-hub-lab`:** not located via GitHub search (2026-10-14) — no popularity cross-check possible; per directive it would never be an adoption reason.
- **Apply-with-overrides:** verdicts below follow the owner directive; where our license-file check contradicts, it is flagged. Anything with license terms outside {MIT, Apache-2.0, BSD-3-Clause} is REJECT per the hard filter.

---

## A. SHORTLIST — Phase-2 deep-read queue (GO/NO-GO pending)

| Repo | License (+path) | Last push | ★ | Verdict |
|---|---|---|---|---|
| `scrapy/protego` | BSD-3-Clause (`LICENSE`) | 2026-10-08 | 94 | ADOPT-CANDIDATE → deep-read (robots lib for the gateway) |
| `dedupeio/dedupe` | MIT (`LICENSE`) | 2025-07-28 | 4.5k | ADOPT-CANDIDATE → deep-read (**stale >6mo — deep-read re-confirms; splink is the live alternative**) |
| `moj-analytical-services/splink` | MIT (`LICENSE`) | 2026-10-14 | 2.5k | ADOPT-CANDIDATE → deep-read (record linkage for product matching) |
| `pgrls/pgrls` | MIT (per search result; deep-read verifies) | 2026-09-26 | 29 | ADOPT-CANDIDATE → deep-read (Postgres RLS lint/test matrix for Phase-7 tenant isolation) |
| `openmeterio/openmeter` | Apache-2.0 (`LICENSE`) | 2026-10-14 | 2.4k | ADOPT-CANDIDATE → deep-read (per-tenant+task metering) |
| `ory/kratos` | Apache-2.0 (`LICENSE`) | 2026-07-29 | 13.9k | ADOPT-CANDIDATE → deep-read (MFA/passkeys identity) |
| `openfga/openfga` | Apache-2.0 (`LICENSE`) | 2026-10-13 | 6.0k | ADOPT-CANDIDATE → deep-read (fine-grained authz, default-deny) |
| `anchore/grype` | Apache-2.0 (`LICENSE`) | 2026-10-13 | 13.0k | ADOPT-CANDIDATE → deep-read (image/FS vuln scanner; CI advisory alongside trivy) |
| `google/osv-scanner` | Apache-2.0 (`LICENSE`) | 2026-10-14 | 11.2k | ADOPT-CANDIDATE → deep-read (dependency/SBOM vulns) |
| `zaproxy/zaproxy` | Apache-2.0 (`LICENSE`) | 2026-10-08 | 15.9k | ADOPT-CANDIDATE → deep-read (baseline DAST against the local stack) |

## B. STUDY — study-only, never vendor or embed

**Policy-kernel interface inspiration (HITL approvals, budget enforcement, audited decisions):**
- `Justin0504/Aegis` — MIT, 542★, 2026-10-08 — runtime policy enforcement for agents; interface inspiration only.
- `jamjet-labs/jamjet` — Apache-2.0, 22★, 2026-10-10 — small "safety layer"; interface inspiration only.

**AutothinK workspace reference:**
- `cloudflare/cloudflare-os` — Apache-2.0, 11.4k★, 2026-10-14 — the referenced workspace pattern; Workers-locked → designs only.
- `cloudflare/agents` — MIT, 5.8k★, 2026-10-14 — agent SDK patterns; Workers deploy target.
- `cloudflare/agentic-inbox` — Apache-2.0, 8.3k★, 2026-04-23 — self-hosted agent app patterns.
- `rivet-dev/rivet` — Apache-2.0, 6.3k★, 2026-10-14 — stateful actor primitive; overlaps Temporal eval.

**Sandbox runtime candidates (deep-read only, per directive):**
- `e2b-dev/E2B` — Apache-2.0, 14.4k★, 2026-10-14.
- `opensandbox-group/OpenSandbox` — Apache-2.0, 15.9k★, 2026-10-14.
- `wasmerio/wasmer` — MIT, 21.2k★, 2026-10-14.

**Orchestration frameworks — reference only; our kernel exists:**
- `langchain-ai/langgraph` — MIT, 43.3k★, 2026-10-14.
- `temporalio/temporal` — MIT, 23.7k★, 2026-10-14.
- `deepset-ai/haystack` — Apache-2.0, 26.7k★, 2026-10-14 (from searches).
- `openai/openai-agents-python` — MIT, 30.0k★, 2026-10-14.
- `OpenHands/OpenHands` — MIT, 90.9k★, 2026-10-14.
- `lastmile-ai/mcp-agent` — Apache-2.0, 8.6k★, 2026-01-25 (stale — reference only).
- `ComposioHQ/composio` — MIT, 30.6k★, 2026-10-14 (search-discovered).
- `spring-ai-playground` — owner-directed STUDY (not profiled).
- `treeverse/dvc` — Apache-2.0, 15.9k★, 2026-10-12 — provenance patterns (our store already hash-chains).
- `littletool` — owner-directed: deep-read only, no adoption (not profiled).

## C. REJECT — with reasons

**Purpose violations (standing policy):**
- `jo-inc/camofox-browser` — MIT, 11.6k★ — stealth headless browser / bypass purpose. REJECT.

**License outside allowlist (verified):**
- `getlago/lago` — AGPL-3.0. REJECT.
- `zitadel/zitadel` — AGPL-3.0. REJECT.
- `edwinkys/phantasm` — GPL-3.0 + stale (last push 2024-11-27). REJECT.
- `microfeed`, `escapeboy/agent-fleet-o`, `Fame510/SHACKLE` — AGPL per owner directive (not profiled). REJECT.

**No/undetected license (verified where profiled):**
- `daytonaio/daytona` — no LICENSE detected (owner: archived). REJECT.
- `humanlayer/humanlayer` — license detection NOASSERTION (custom/unrecognized terms → outside allowlist). REJECT.
- `unkeyed/unkey` — NOASSERTION. REJECT.
- `windmill-labs/windmill` — NOASSERTION. REJECT.
- `Tencent CloudCubeSandbox` — owner-directed (not profiled); NOASSERTION-class. REJECT.
- `mksglu/context-mode` — NOASSERTION (from search profile). REJECT.
- `NevaMind/memU` — owner-directed (not profiled). REJECT.

**Search-spam / zero-star mcp-hub-lab results (owner directive):**
- `UmemotoLab/UmemotoLab-MCP-Hub` — 0★, no license. REJECT.
- `respectevery01/mcp-hub` — 0★, no license. REJECT.
- `lingxiaoyiyu-hub/open-secagent-marketplace` — NOASSERTION. REJECT.
- `cirosantilli/china-dictatorship` — search spam. REJECT (not profiled).
- `sonuoffsec/AI-Security-Hub` — MIT but AI-security payload dump; not relevant to any aim area. Not selected.

## D. NOT SELECTED — near-miss one-liners (do not re-evaluate)

- `keycloak/keycloak` — Apache-2.0 but heavyweight Java IAM; Kratos is the headless fit.
- `google/robotstxt` — Apache-2.0, C++/Java; protego chosen for our Python stack.
- `seomoz/reppy` — MIT but last push 2024-01; protego more current.
- `J535D165/recordlinkage` — BSD-3 but stale (2024-02); splink current.
- `praetorian-inc/hadrian` — Apache-2.0 API sec fuzzing; ZAP first.
- `blst-security/cherrybomb`, `openclarity/apiclarity` — Apache-2.0 but stale (2024); ZAP first.
- `bytedance/deer-flow` — MIT; another full agent harness; overlaps our stack.
- `sagents`, `Deuz-SDK`, `pi-plans`, `Vibe-Skills`, `gemini-gpt-hybrid`, `ai-runtime-lab` — small/role-specific orchestration experiments; not needed.
- `Emmimal/context-engine`, `Ruthwik000/tokenfirewall`, `Inebrio/Routerly` (AGPL anyway) — context/cost middleware; watch list only.
- `supercrawler`, `Parsero`, `robots-parser`, `record-linkage-resources`, `entity-embed`, `pseudopeople`, `spindle-token`, `aws-saas-factory-postgresql-rls`, `rlsgrid`, `micro-saas`, `fencer`, `mapi-action` — search-discovered, none beats the chosen candidates on license+maintenance+fit.

## E. Notes carried forward
- Deep-read queue (Phase 2, per directive): the 10 repos in section A → `reports/github_hunt_deep_20261014.md` with GO/NO-GO; **STOP for owner sign-off before any Phase-3 adoption.**
- Phase-3 priority order (from the directive, adopted-by-explicit-GO-only): (1) pgrls → RLS plugin/CI lint; (2) grype + osv-scanner → advisory CI; (3) zaproxy → baseline DAST script (not committed until reviewed); (4) protego → gateway robots parser (unit-tested against google/robotstxt fixtures); (5) dedupe + splink → 50-pair spike; (6) openmeter → design note; (7) kratos + openfga → design note.
