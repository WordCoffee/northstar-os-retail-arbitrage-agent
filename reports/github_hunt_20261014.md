# GitHub HUNT — candidates for NorthstarOS + AutothinK (2026-10-14)

- **Standing line:** 0 new / 0 known-active / 231 allowlisted (no repo content fetched — metadata + license paths only).
- **Scope:** 15 candidates across the 5 aim areas · 10 search queries · 25 repo profiles · read-only, **nothing installed/fetched into the repo**.
- **Evidence JSON:** `reports/github_hunt_evidence_20261014.json` (queries, search results, repo profiles).
- **Method notes:** pins via `git ls-remote`; license via GitHub API + `/license` path; **last-commit dates are GitHub `pushed_at` (proxy)**; stars informational only. **`mcp-hub-lab` could not be located via GitHub search (2026-10-14)** — no popularity cross-check possible; per directive it would never be an adoption reason (poisoned like-entries history).
- **Hard filters applied:** license ∈ {MIT, Apache-2.0, BSD-3-Clause} · maintenance ≤ ~6 months · no Amazon/stealth/captcha/login-bypass purpose · telemetry/crypto flags noted for intake · instruction packs n/a in this hunt.

## RANKED SHORTLIST — ADOPT-CANDIDATE (intake pending your approval)

| # | Repo | Area | License | Fit | Why ranked here |
|---|---|---|---|---|---|
| 1 | `scrapy/protego` | 3 data | BSD-3-Clause | robots compliance lib | Tiny drop-in library; modern robots conventions; complements/validates our gate. |
| 2 | `google/osv-scanner` | 5 sec | Apache-2.0 | dependency/SBOM vulns | Complements pip-audit across ecosystems; CLI like the D-S2 tools. |
| 3 | `zaproxy/zaproxy` | 5 sec | Apache-2.0 | DAST baseline | The explicit OWASP-baseline ask; OpenAPI scan mode fits our API. |
| 4 | `ory/kratos` | 4 commercial | Apache-2.0 | MFA/passkeys identity | Headless; exactly the approved MFA design (passkeys/authenticator). |
| 5 | `openfga/openfga` | 4 commercial | Apache-2.0 | fine-grained authz | Default-deny ReBAC; models tenant+task grants like our kernel semantics. |
| 6 | `openmeterio/openmeter` | 4 commercial | Apache-2.0 | metering/billing | Metering by tenant+task for the ledger; self-hostable. |
| 7 | `moj-analytical-services/splink` | 3 data | MIT | product matching | Probabilistic record linkage (DuckDB/Spark) for UPC/ASIN-style dedupe from allowed sources. |
| 8 | `opensandbox-group/OpenSandbox` | 1 workspace | Apache-2.0 | sandbox runtime | Self-hosted sandbox runtime for agent code execution (Linux runtime host assumed). |
| 9 | `e2b-dev/E2B` | 1 workspace | Apache-2.0 | sandbox infra | Alternative to #8 — pick ONE at intake (E2B = infra-heavy, SDK mature). |
| 10 | `langchain-ai/langgraph` | 2 brain | MIT | orchestration lib | Human-in-the-loop interrupts + checkpointing for product-side agents. |

## Candidates in full (grouped by aim area)

### Area 1 — AutothinK workspace
**1. e2b-dev/E2B** · `https://github.com/e2b-dev/E2B` · SHA `62a17dfc3f11…` · Apache-2.0 · `LICENSE` · pushed 2026-10-14 · 14.4k★
- WHAT: open-source infrastructure/SDK for secure sandboxed environments for AI-generated code.
- GAP: per-user sandboxed workspaces for AutothinK runs.
- INTEGRATE: sandbox driver behind the AutothinK backend (self-hosted); egress must be caged by the policy kernel; needs a Linux runtime-host decision (operator machine is Windows).
- RISKS (verify at intake): egress defaults; telemetry flags; infra weight.
- **VERDICT: ADOPT-CANDIDATE** (alternate to #8 — choose one at intake).

**2. opensandbox-group/OpenSandbox** · `https://github.com/opensandbox-group/OpenSandbox` · SHA `51cabc49e410…` · Apache-2.0 · `LICENSE` · pushed 2026-10-14 · 15.9k★
- WHAT: "Secure, Fast, Extensible Sandbox runtime for AI agents".
- GAP: sandbox runtime for AutothinK code execution / per-user workspaces.
- INTEGRATE: sandbox driver; container/Linux runtime; pair with our approval queue.
- RISKS (verify at intake): new org provenance; egress; runtime host.
- **VERDICT: ADOPT-CANDIDATE** (preferred over E2B if its self-host story is cleaner).

**3. cloudflare/cloudflare-os** · `https://github.com/cloudflare/cloudflare-os` · SHA `fd13354df50a…` · Apache-2.0 · `LICENSE` · pushed 2026-10-14 · 11.4k★
- WHAT: agent workspace app built on Cloudflare Workers (the referenced "cloudflare-os pattern").
- GAP: workspace UX + approval-flow patterns for AutothinK.
- INTEGRATE: **patterns/reference only** (Workers runtime ≠ our stack); optionally adapt UI/permission flows.
- RISKS: Cloudflare account binding if ever run as-is; workers lock-in.
- **VERDICT: STUDY** (mine patterns; no intake).

**4. OpenHands/OpenHands** · `https://github.com/OpenHands/OpenHands` · SHA `e4775b4ba61a…` · MIT · `LICENSE` · pushed 2026-10-14 · 90.9k★
- WHAT: full agent development platform (workspace UI + sandboxed runtime + confirmation/permission flows).
- GAP: reference architecture for approval queues, event streams, per-task confirmation UX.
- INTEGRATE: patterns/reference (embedding the platform would duplicate our brain/OpenCode stack).
- RISKS: big surface if adopted wholesale; containers/runtime; telemetry verify.
- **VERDICT: STUDY**.

### Area 2 — Brain / sub-agent orchestration
**5. langchain-ai/langgraph** · `https://github.com/langchain-ai/langgraph` · SHA `5eb60aef6f38…` · MIT · `LICENSE` · pushed 2026-10-14 · 43.3k★
- WHAT: stateful graph orchestration with interrupts (human approval) and checkpointing.
- GAP: orchestration + approval-handoff patterns for AutothinK product agents.
- INTEGRATE: **library** in the AutothinK backend (NOT the control-layer kernel — kernel stays homegrown).
- RISKS: ecosystem churn; keep isolated behind our interfaces.
- **VERDICT: ADOPT-CANDIDATE**.

**6. temporalio/temporal** · `https://github.com/temporalio/temporal` · SHA `10791698da37…` · MIT · `LICENSE` · pushed 2026-10-14 · 23.7k★
- WHAT: durable execution/workflow engine (retries, timeouts, cancellation, full event history = audit).
- GAP: long-running task scheduling + kill/cancel semantics + audit trail for AutothinK jobs.
- INTEGRATE: infrastructure behind a brain driver (self-host; Postgres backend).
- RISKS: ops weight; overlaps our kernel process table — only if jobs outgrow it.
- **VERDICT: STUDY**.

**7. openai/openai-agents-python** · `https://github.com/openai/openai-agents-python` · SHA `24ebf1cb0f4b…` · MIT · `LICENSE` · pushed 2026-10-14 · 30.0k★
- WHAT: lightweight multi-agent framework (handoffs, guardrails, sessions).
- GAP: agent-to-agent handoff + guardrail patterns (lighter than langgraph).
- INTEGRATE: library option — **pick one of {langgraph, this}** at design time.
- RISKS: OpenAI-centric defaults.
- **VERDICT: STUDY** (pick-one with #5).

### Area 3 — Provider / data layer
**8. scrapy/protego** · `https://github.com/scrapy/protego` · SHA `53d6df88ea74…` · BSD-3-Clause · `LICENSE` · pushed 2026-10-08 · 94★
- WHAT: pure-Python robots.txt parser (modern conventions, wildcards/crawl-delay).
- GAP: robots compliance for the gateway's RobotsGate (validated edge cases).
- INTEGRATE: **library** inside the gateway (tiny, embeddable).
- RISKS: small maintainer base (but simple, tested, backed by the Scrapy org).
- **VERDICT: ADOPT-CANDIDATE** (rank 1).

**9. treeverse/dvc** · `https://github.com/treeverse/dvc` · SHA `56e59829512f…` · Apache-2.0 · `LICENSE` · pushed 2026-10-12 · 15.9k★
- WHAT: data versioning (hash-addressed artifacts, git-linked lineage, remote storage).
- GAP: provenance/lineage patterns for the snapshot store.
- INTEGRATE: patterns first (our store already hash-chains); possibly a tool for dataset workflows.
- RISKS: heavyweight; remote configs can carry location info.
- **VERDICT: STUDY**.

**10. moj-analytical-services/splink** · `https://github.com/moj-analytical-services/splink` · SHA `12aee3fd1fac…` · MIT · `LICENSE` · pushed 2026-10-14 · 2.5k★
- WHAT: probabilistic record linkage at scale (DuckDB/Spark backends).
- GAP: product-data normalization / entity matching (UPC/ASIN-style) from ALLOWED sources.
- INTEGRATE: **library** in the data layer (offline matching jobs, local data only).
- RISKS: none material; keep datasets local.
- **VERDICT: ADOPT-CANDIDATE**.

### Area 4 — Commercial-readiness plumbing
**11. ory/kratos** · `https://github.com/ory/kratos` · SHA `b86338da04a0…` · Apache-2.0 · `LICENSE` · pushed 2026-07-29 · 13.9k★
- WHAT: headless identity server (passwords, passkeys/WebAuthn, TOTP MFA, OIDC).
- GAP: **MFA for all accounts + passkeys/authenticator app** (the approved design); invite-only flows.
- INTEGRATE: self-hosted service behind the foundation; consumed by the UI session's screens.
- RISKS: Go service ops; SPA integration design (screens are the UI session's call).
- **VERDICT: ADOPT-CANDIDATE**.

**12. openfga/openfga** · `https://github.com/openfga/openfga` · SHA `526995eb2024…` · Apache-2.0 · `LICENSE` · pushed 2026-10-13 · 6.0k★
- WHAT: fine-grained authorization (ReBAC) engine (CNCF).
- GAP: per-tenant/per-task permissions, default-deny modeling, auditable checks (mirrors capability-grant semantics).
- INTEGRATE: service/library alongside the foundation; model tenant+task grants.
- RISKS: duality with the kernel's own grants — keep kernel grants for agents, FGA for customer tenants.
- **VERDICT: ADOPT-CANDIDATE**.

**13. openmeterio/openmeter** · `https://github.com/openmeterio/openmeter` · SHA `35dc8cb55d45…` · Apache-2.0 · `LICENSE` · pushed 2026-10-14 · 2.4k★
- WHAT: metering + usage-based billing (collect/aggregate usage events per tenant).
- GAP: **billing/metering by tenant+task** (the ledger ask).
- INTEGRATE: self-hosted service; emit task usage events; feeds invoicing.
- RISKS: verify deployment footprint at intake (historically Kafka/ClickHouse-heavy).
- **VERDICT: ADOPT-CANDIDATE**.

### Area 5 — Offensive/security tooling for our repo
**14. zaproxy/zaproxy** · `https://github.com/zaproxy/zaproxy` · SHA `38ffe34a1b03…` · Apache-2.0 · `LICENSE` · pushed 2026-10-08 · 15.9k★
- WHAT: OWASP ZAP — DAST scanner (baseline scans; OpenAPI-driven scanning).
- GAP: DAST baseline for the API (explicit ask); complements static tooling.
- INTEGRATE: CLI scans of the locally running API (like the D-S2 audit pass), later CI.
- RISKS: needs a running app; run headless/containerized; never against third-party hosts.
- **VERDICT: ADOPT-CANDIDATE**.

**15. google/osv-scanner** · `https://github.com/google/osv-scanner` · SHA `f45535354688…` · Apache-2.0 · `LICENSE` · pushed 2026-10-14 · 11.2k★
- WHAT: vulnerability scanner using the OSV database (lockfiles/SBOMs/containers).
- GAP: dependency-version vulns across ecosystems (complements pip-audit; pairs with trivy).
- INTEGRATE: CLI in the audit pipeline.
- RISKS: minimal.
- **VERDICT: ADOPT-CANDIDATE**.

## Already adopted (D-S2 status — listed for completeness, not re-evaluated)
| Tool | License | Status |
|---|---|---|
| trivy 0.76.0 | Apache-2.0 | adopted 2026-10-14 (checksum-verified) |
| pip-audit 2.10.1 | Apache-2.0 | adopted (uv tool) |
| **semgrep 1.181.0** | **LGPL-2.1 — NOTE:** outside this hunt's embed allowlist; fine as a standalone dev CLI, must NOT be embedded in the product | adopted as CLI |
| schemathesis 4.31.1 | MIT | adopted (uv tool) |
| promptfoo 0.124.1 | MIT | adopted (npm) |
| context7 (MCP, upstash/context7 repo MIT) | hosted service | adopted + connected |

## NOT-CHOSEN (near-misses — one line each, so we don't re-evaluate)
- `keycloak/keycloak` — Apache-2.0 but heavyweight Java IAM; Kratos is the headless fit.
- `zitadel/zitadel`, `getlago/lago` — AGPL-3.0 (hard filter).
- `unkeyed/unkey`, `windmill-labs/windmill`, `humanlayer/humanlayer` — license NOASSERTION (hard filter).
- `daytonaio/daytona` — no LICENSE detected (hard filter).
- `dedupeio/dedupe` — MIT but stale (2025-07-28); splink preferred.
- `lastmile-ai/mcp-agent` — Apache-2.0 but stale (2026-01-25).
- `anchore/grype` — Apache-2.0; trivy already covers image scanning; revisit only if a second scanner is wanted.
- `cloudflare/agents` — MIT but Workers-locked; cloudflare-os covers the pattern.
- `wasmerio/wasmer` — MIT; general wasm runtime; OpenSandbox/E2B closer to the ask.
- `rivet-dev/rivet` — Apache-2.0; actor primitive overlaps the Temporal evaluation.
- `google/robotstxt` — Apache-2.0 but C++/Java; protego chosen for our Python stack.
- `seomoz/reppy` — MIT but last push 2024-01; protego more current.
- `J535D165/recordlinkage` — BSD-3 but stale (2024-02); splink current.
- `pgrls/pgrls` — MIT, tiny (29★) Postgres-RLS linter; watch item.
- `Justin0504/Aegis`, `jamjet-labs/jamjet` — MIT/Apache runtime policy gates; small/single-maintainer; watch.
- `praetorian-inc/hadrian` — Apache-2.0 API sec fuzzing; ZAP first.
- `ComposioHQ/composio` — MIT toolkit platform; cloud tiers/third-party auth flows; not needed now.
- `bytedance/deer-flow` — MIT; another full agent harness; overlaps our stack.
- `deepset-ai/haystack` — Apache-2.0; RAG-centric; langgraph closer to the ask.
- `blst-security/cherrybomb`, `openclarity/apiclarity` — Apache-2.0 but stale (2024); ZAP first.
- `mcp-hub-lab` — could not be located via GitHub search (2026-10-14); no cross-check possible.

## STOP
Per the directive: **candidates only — nothing installed, nothing vendored.** Owner decision per candidate before any intake (each would run the standard pipeline: pin → read every file → filters → self-gated install → tests → commit).
