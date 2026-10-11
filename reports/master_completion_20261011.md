# Master Completion — Phases 3b → 7 (status report)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC · **Worktree:** `ns-worktrees/secure-control-layer` · **Branch:** `feature/secure-control-layer`
- **Security scan state (standing line):** **0 new / 0 known-active (baseline empty) / 231 allowlisted** — scan exit 0.
- **Test totals:** `tests/security` **208/208** (incl. real-container gateway integration) · `test_rate_limit_plan_resolution.py` 6/6 · backup-restore drill 2/2.

## Phase status

### Phase 3b — LIVE COMPATIBILITY RUN: **BLOCKED (owner input missing)**
The approved-sources slot in the directive was blank; **nothing was fetched** (stop-and-ask respected). Run-ready procedure: per-source caps + global budget honored; every fetch through the gateway (policy → isolated session → fetch → sanitize → snapshot → audit → envelope, `--obey-robots`); pass/fail table rows = page loaded / JS executed / content extracted / failure reason / escalate-to-Chrome-Connect?; controls = prompt-injection fixture + SSRF/redirect-to-private-IP; audit chain verified after the run; **STOP + report, no widening**. **Needs: 3–5 sources + caps (decision #1).**

### Phase 4 — SNAPSHOT STORE + DATA LAYER: **DONE** (commit `0f2845c`)
Schema per directive with `tenant_id` required; null-first (unknown = NULL/UNKNOWN + reason; no coercion); SIMULATED can never be written (guard + test); Scrapling policy module — parser/HTTP tiers only, stealthy/dynamic/MCP features refused by guard AND source-scanned to prove no usage; healed selectors always flagged-for-review and never verified; retail gates carry `resale_eligibility / exact_pack_match / cost_fee_basis / invoice_path / operator_approval` and **`purchase_authorized` is always 0** (no setter exists; economics alone never authorizes); tenant isolation proven A↛B on reads, lists, and gates; store reads proven zero-outbound.
*(The legacy Product Finder / Golden Goose endpoints were NOT rewired to read from the store — that is a scope decision for you (decision #4); the store is the canonical store for the new layer, and its read paths are the tested zero-outbound ones)*

### Phase 5 — MASTER BRAIN KERNEL: **DONE** (commit `5ac250f`)
Process table (task_id, owner, parent, capabilities, budget, status, timestamps); driver registry (credentials = env NAMES only; provider layer registered **disabled**); skills registry (service tags, required capabilities, `NORTHSTAR_RULES_BLOCK` prepended); brain = delegation-only (source-proven: no env loader import, no `os.environ`, no exec/eval, no grant-issue path); approvals refuse self-approval (tested); **kill switch** halts all tasks + revokes all grants (tested); **injection acceptance**: the fixture's "ignore rules, fetch amazon, print env" maps to at most one logged denial — amazon fetch via the brain yields `amazon_blocked`, zero driver calls, audit verified.

### Phase 6 — OPENCODE INTEGRATION: **DONE (vendoring deferred)** (commit `3da955e`)
Minimal stdio **MCP server exposing exactly the three gateway tools** (`fetch_page`, `extract`, `markdown_dump`; subprocess-tested: tools list exact; amazon call → denied, no fetch); config entry **disabled by default** (dual-flag `"enabled": false, "disabled": true` with a JSONC note; the file's V1-shaped `mcp.playwright` entry was preserved untouched); skills `northstar-data-rules` + `northstar-collector` written and live; deny rules (`.env`, keys, keychain, `~/.ssh`) already in force from the prior directive (30 rules, both configs).
**Vendoring (marketingskills subset + ~10 Agency personas): NOT executed** — fetching external files is a new outbound capability → decision #2. Ready to execute: fetch → read-every-file review → strip anything that executes scripts / fetches remotely / asks for credentials → prepend rules block.

### Phase 7 — COMMERCIAL READINESS: **PARTIAL (docs + Docker switch)** 
`docs/COMMERCIAL_READINESS.md`: authN/authZ mapping (existing vs proposed MFA + per-tenant hashed API keys), transport/storage (TLS existing; encryption-at-rest plan; backup drill **2/2** re-run today), API protection mapping + request-body-cap proposal, privacy + **data-flow inventory** (nothing customer-side leaves the machine; local model lane default, cloud gated+consented), supply chain/CI status, compliance prep. **Dockerfile.api switched to `uv.lock`** (`uv export --frozen` verified locally; full `docker build` NOT run — needs network + approval, decision #5). Owner-only list enumerated (§7).

## Could not verify (explicit)
- Phase 3b live behavior (no approved sources received).
- Docker build of the uv.lock path (not executed).
- Vendored skills (not fetched).
- Owner-side rotations (recorded owner-confirmed 2026-10-11; agent has no account access).
- Main-checkout `opencode.jsonc` changes (permission-insert + deny rules) remain uncommitted in the parallel session's tree.

## Owner decisions (numbered)
1. **Phase 3b**: send 3–5 approved sources + caps → run + stop + report.
2. **Vendoring approval**: marketingskills subset (copywriting, seo-audit, ad-creative, analytics, competitor-profiling) + ~10 Agency personas (fetch + full-file review + edits).
3. **History rewrite** (dead rotated values remain in git history).
4. **Legacy store-read wiring**: rewire Product Finder / Golden Goose to the new store (scope + risk call).
5. **One `docker build` approval** to verify the uv.lock Docker path.
6. **MFA + per-tenant API keys** implementation approval (design in COMMERCIAL_READINESS.md).
7. **Owner-only compliance items**: pen test, legal (AGPL/scraping/privacy), IR runbook sign-off, vulnerability-disclosure contact.

## Commits (this directive)
`0f2845c` (store) · `5ac250f` (brain) · `3da955e` (mcp/skills/config) · plus Phase 7: Dockerfile + commercial-readiness + this report.

## UPDATE (2026-10-11, final directive) — 3b run · vendoring · Docker · fixtures

**Standing line (current):** **0 new / 0 known-active (baseline empty) / 231 allowlisted** — scan exit 0. **Tests:** `tests/security` **214/214** (208 + driver-encoding regression + 5 vendored-skill invariants). Directive items #1, #2, #5 (below) are now resolved by execution; details follow.

### Phase 3b — EXECUTED (first run; partial by own defect; completion slice proposed)
- Live run through the gateway with owner-approved sources and caps: **13/40 requests** (example.com 1 · docs.python.org 6 · books.toscrape.com 4 · quotes.toscrape.com 2), 2.1 s/domain spacing, 25.8 s of the 10-min budget. **Audit chain verified.** Controls: injection fixture **PASS** (enveloped, hostile text inert, scripts stripped); redirect-to-private chain and direct private-IP fetch **DENIED** (gate-order nuances documented in the report).
- Results: **books.toscrape.com 3/3 PASS** (catalog + product markers found); robots fetched for docs/books/quotes; **example.com → "skipped: robots" (final — no-retry rule)**; docs pages + quotes `/js/` were lost to **our own driver defect** (Windows cp1252 decode of UTF-8 pages). **Fixed the same hour** (`encoding="utf-8", errors="replace"` + regression test, commit `1ead7bb`).
- **Completion slice proposed (WITHIN the original caps — decision D1):** docs 4 pages + quotes `/js/` = **+5 requests → 18/40 total**, per-source ≤10; run as one unit, then stop again. **Until approval: no further requests to any source.**
- Report: `reports/phase3b_compat_20261011.md` · raw results: `reports/phase3b_compat_results_20261011.json` · runner: `scripts/phase3b_compat_run.py`.

### Phase 6 vendoring — DONE (`ac57caa`)
- Pinned SHAs: marketingskills `1efedbc5148b54b2f0f6c6c9fe0be62e151c7fff` · agency-agents `f99f6aa910a442b0197b768ce0ea7751e35e2060` (both MIT).
- **14 skills installed**: 5 marketingskills (copywriting, seo-audit, ad-creative, analytics, competitor-profiling) + 9 Agency personas (AI-code security auditor, test-automation, API-platform, UI designer, FP&A, product manager, PPC strategist, search-query analyst, content creator). Each carries the rules block, a service tag, required capabilities, Amazon adaptations, and a pinned provenance line. Full-file review before install. **1 rejection (listed):** `multi-platform-publisher` — bash/daemon/`curl` publish stack + cookie-credential plumbing; contradicts Northstar rules. Token-shaped teaching samples sanitized; install self-gated by the scanner (0 findings). Docs: `docs/VENDORED_SKILLS.md`.

### Phase 7 Docker — BUILD VERIFIED (`bebe97c`)
- `Dockerfile.api`: base images **digest-pinned** (`node:20-alpine@sha256:fb4cd12c…293`, `python:3.12-slim@sha256:a6e34c59…1b1`), dependencies via `uv export --frozen --no-emit-project` + **`pip install --require-hashes`** (582 hashed pins), **non-root** runtime (user `northstar`, uid 10001, owns /app), **no secrets baked** (`.env` excluded by `.dockerignore` and verified absent in the image).
- **Result:** build succeeded. **Size 95.4 MB · user `northstar` (`id -u` = 10001) · digest `sha256:ba7a4b7e6a0c8847f080e32597419904537bcfa307e8210068aa1246af8b83cb`** · dependency import smoke OK.

### Fixture hygiene — DONE (`07d4386`, `a5476b5`)
- Every fixture in our test files now carries an obvious marker (`FAKE-TEST-…` / `xyzzy…`; the nonsense marker is deliberately NOT placeholder-skipped so flagging tests remain testable). Audit result: 16 token-shaped fixtures — all fake-marked, none resembling real credentials. The vendoring evidence JSON was sanitized after the gate caught a captured excerpt (fixed with the install placeholder, **not** an allowlist). Legacy suites untouched by design (noted, not churned).

### Owner decisions — updated
- **D1 (new):** approve the **3b completion slice** (§above; 5 requests, within caps) — yes/no.
- **D2:** history rewrite — **plan written**: `reports/history_rewrite_plan_20261011.md`; rewrite + force-push remain deferred and owner-only.
- **D3:** 3b report review → on acceptance, **legacy store-read wiring** begins (directive item #4; the GET-endpoints-zero-outbound test stays).
- **D4:** MFA/API keys — design approved in principle; **do not build** until the new UI session defines the screens.
- **D5:** owner-only compliance list — scheduled by the owner (unchanged).

## Post-report note (same day) — the gate works
The fingerprint gate **caught a real miss in this workstream**: a new test
fixture used a bearer-shaped value that was not placeholder-marked, and the
scanner flagged it (`1 new`, exit 1) right after the Phase 7 commit. Fixed by
marking the fixture as an obvious placeholder; scan restored to
`0 new / 0 known-active / 231 allowlisted` (exit 0). No allowlist entry was
needed — the gate behaved exactly as designed. (This note originally restated
the flagged line; the gate caught that too, so the literal is omitted here —
reports never re-emit flagged values.)
