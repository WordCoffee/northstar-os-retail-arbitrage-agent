# AUDIT-SUMMARY — NorthstarOS + AutothinK Complete Product Audit

**Audit date:** 2026-10-08
**Auditor:** Principal engineering auditor / QA lead / product-design reviewer / release-readiness coordinator (AI agent, OpenCode harness)
**Method:** read-only code + config inspection, live local boot probes, network instrumentation, safe local test execution.
**No code was changed. No fix was implemented. No external action was taken.**

---

## 0. HEADLINE VERDICT (answers to §12)

### 1. Is all required creative work complete? — **NO**
**Scope of the verdict:** the suite's shipped React/Vite presentation layer (`northstar-os-ui`, 92 modules, `npm run build` = 0 errors) plus the three creative/media rooms (Creative Studio, SocialPulse, Product Designer Studio).

Evidence:
- The old shell is genuinely gone (SideNav/Sidebar/Dock/RightRail/Header removed; `DEAD_SURFACE_MANIFEST.md` §B). The current shell is a real presentation rebuild: `TopNav` + `SuiteRail` + `MobileBottomNav` + `CommandPalette` (`App.jsx:1-238`), Paper/bone + pine-forest tokens, Libre Baskerville + DM Sans (`northstar-os-ui/src/styles/tokens.css`).
- **But the shell is not the same thing as complete creative content.** Creative Studio and SocialPulse are 100% `localStorage`-backed shells with **zero backend wiring** (`CREATIVE_SOCIAL_LOCAL_STATUS.md` §1, §3). "Field Notes"/warm-neutrals/forest is the current shipped direction — the audit found **no approval evidence file superseding it**, so it is treated as the standing direction (not an unapproved one).
- Product Designer Studio (`/product-designer`, 16 files / 3,620 lines, `f232ef8`) landed **during** this audit and is **UNAUDITED**.
- Concrete unfilled creative gaps are listed in `CREATIVE_COMPLETENESS.md` (missing states, unlabeled hardcoded metrics in `PlanUsage.jsx`, static meters in `AdPilot.jsx`, dead controls, a11y defects).

### 2. Is all required non-creative (engineering) work complete? — **NO**
**Evidence:**
- **P0 defects found**, each independently reproduced:
  1. `/api/kirkland/scanner` — a plain **GET** performs **19 outbound live provider connections** (Bright Data, `3.232.71.244:443`) when `SCANNER_LIVE_ALLOWED=1`. This breaks the non-negotiable "standard UI loads = cache/database only" rule. See `TECHNICAL_COMPLETENESS.md` §6.
  2. Hosted-reasoning UI is disconnected from its backend: `foundation/api.js:175-179` calls `/api/v1/foundation/reasoning/*` which returns **404**; the real routes are `/api/v1/reasoning/*` (verified live: 404 vs 200).
  3. Hosted deployment serves a different API surface than local dev: `Dockerfile.api` runs `foundation.app:app` only — all `main.py` routes (status, sourcescout, products/finder, autothink, reasoning, noncreative) are absent from the hosted stack.
- Full-suite tests are **not green**: 9 failures (Python) + 1 failure (Node smoke harness) + 1 blocked harness.

### 3. Is AutothinK complete for its approved scope? — **NO**
**Evidence:**
- Local lane **works** (verified: real completion from `northstar-qwen3:rev1`, 14.2 s, content "READY").
- **Hosted lane is broken** (404 route wiring — see above), so the OpenCode Go lane is unusable from the UI.
- **Retrieval/grounding is not implemented**: `build_context()` runs but its output is never passed to the adapter (`server.py` contains 0 references to `build_system_prompt_with_context`).
- **No auth, no tenant scoping, no cancellation, no usage/cost accounting** on the `/api/autothink/*` routes (`main.py:1035-1063`, plain functions, no `Depends`).
- Details in `AUTOTHINK_AUDIT.md`.

### 4. Is the entire suite ready to begin a full-service test? — **NOT READY**
Blocking gaps (see `READINESS_GATES.md`): P0 live-call leak on a GET; P0 hosted-reasoning route breakage; P0 hosted/local API-surface divergence; 2 phase-1 spec services (Watch, RankLedger, RivalBoard) unimplemented; the suite is being concurrently modified (a new service landed mid-audit).

### 5. Has the suite passed release-exit criteria? — **NOT TESTED**
The full-service suite has not been run. Verdict is explicitly **NOT TESTED**, not "failed".

---

## 1. Repository / commit / environment audited

| Item | Value |
|---|---|
| Path | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent` |
| Commit at audit start | `2482048` — "hosted reasoning hardening: fail-closed model selection …, 65 tests" |
| Branch at audit start | `feature/creative-social-local` |
| Commit at audit end | `f232ef8` — "feat(studio): Product Designer service …" (16 files, +3,620 lines) |
| Branch at audit end | `feature/product-designer-studio` |
| Working tree | 33 dirty entries at start → **203** at end (concurrent session active) |
| Python | 3.14.5 · fastapi 0.140.0 · uvicorn present |
| Node | v24.15.0 · npm 11.12.1 · vite 5.4.21 |
| Local LLM | Ollama reachable; models `qwen3:4b`, `northstar-qwen3:rev1`, `qwen3:14b`, `qwen2.5vl:7b` |
| App entry points | API: `Northstar_backend/main.py` (`main:app`, port 8000) · SPA: `northstar-os-ui` (vite, 8101) · AutothinK: `autothink/backend/server.py` (8100) |
| Hosted entry | `Dockerfile.api` → `uvicorn foundation.app:app` + Caddy (port 80) |

### CONCURRENT-MODIFICATION NOTICE (audit integrity)
A parallel session created branch `feature/product-designer-studio` off `2482048` and committed `f232ef8` **while this audit was running**. `northstar-os-ui/src/App.jsx` gained `/product-designer` (route #82) and `nav-config.js` gained `product-designer`. Untracked `goose_scan_2026100*` files show another agent actively running Golden Goose scans. **Any finding below that touches those files was captured pre-commit and must be re-verified.**

---

## 2. Complete service inventory (19 discovered surfaces)

Full detail in `SERVICE_INVENTORY.csv`. Summary:

| # | Service (canonical) | Aliases | Status | Verification |
|---|---|---|---|---|
| 1 | Command Center | Hub (legacy) | IMPLEMENTED (live reads) | VERIFIED |
| 2 | SourceScout / Product Finder | Prospector (legacy) | PARTIAL (cached; UI static, no API call) | VERIFIED |
| 3 | Golden Goose Finder | — | IMPLEMENTED | VERIFIED |
| 4 | Product Designer Studio | — | **UNAUDITED (landed mid-audit)** | UNKNOWN |
| 5 | Listing Guardian | Guardian | PARTIAL | VERIFIED |
| 6 | Keyword Tracker | — | PARTIAL (backend real, room thin) | VERIFIED |
| 7 | Competitor Monitor | Rival Board (partial alias) | PARTIAL | VERIFIED |
| 8 | ListingForge | OfferChisel (legacy) | STUB/MOCK + real reasoning panel (broken) | VERIFIED |
| 9 | AdPilot | Auctioneer (legacy) | STUB/MOCK + real reasoning panel (broken) | VERIFIED |
| 10 | SocialPulse | Town Crier (legacy) | STUB/MOCK (localStorage only) | VERIFIED |
| 11 | Creative Studio | — | STUB/MOCK (localStorage only) | VERIFIED |
| 12 | Profitability Dashboard | Ledger (partial alias) | PARTIAL (economics engine real) | VERIFIED |
| 13 | Spreadsheet Lab | — | IMPLEMENTED (CSV I/O real; analysis broken) | VERIFIED |
| 14 | Commerce Ops | Operations Hub (target alias) | IMPLEMENTED | VERIFIED |
| 15 | Monitoring | — | PARTIAL | VERIFIED |
| 16 | AutothinK | AutothinK Brain, Master Brain Gateway | PARTIAL (local lane works) | VERIFIED |
| 17 | Memory Bank / Shared Data Layer / Provider Adapters / Master Brain | Systems rooms | IMPLEMENTED (internal read-only) | VERIFIED |
| 18 | Beta Operations + Admin | — | IMPLEMENTED | VERIFIED |
| 19 | Customer workspace (Workspace, Setup, Documents, Plan/Usage, Support, Account, Legal, Suspended/Downgraded/Reaccept) + Public (Beta landing, Sign-in, Recovery, Invite accept) | — | PARTIAL | VERIFIED |

**Retired / not implemented in the shipped suite:** The Watch, RankLedger, RivalBoard — legacy pages exist unrouted (`src/pages/TheWatch.jsx`, `RankLedger.jsx`, `RivalBoard.jsx`) but are documented parked, needing SP-API (`SERVICE_GAPS.md` §non-feature gaps; `00_STATE.json` "PARKED C").

---

## 3. Coverage and test-result counts

| Dimension | Discovered | Inspected/Verified |
|---|---|---|
| Frontend routes (`App.jsx`) | 51 `<Route path=>` | 51 (static); 6 Node harnesses exercised a subset against a live preview |
| API routes (`/openapi.json`) | 210 | 32 GET-probed live + 210 inventoried |
| Services | 19 + 3 retired | 18 audited + 1 unaudited (Product Designer) |
| AutothinK capabilities (§7 checklist) | 19 applicable | 9 verified, 10 verified-not-implemented or broken |
| Creative surfaces | 3 creative rooms + 19 routed screens | 3 rooms + 16 routed screens code-inspected |
| Roles exercised | 6 | 2 (unauthenticated + authenticated-mocked via harness stubs). **No real signed-in session was created.** |
| Python tests | 3,586 collected | 3,586 executed: **3,512 passed / 9 failed / 65 skipped** |
| Node harnesses | 7 | 6 run + 1 blocked |

Exact commands and outputs: `TEST_RESULTS.md`. Raw captures: `evidence/`.

---

## 4. Critical findings (P0)

| ID | Finding | Evidence |
|---|---|---|
| **P0-01** | A plain **GET** to `/api/kirkland/scanner` makes **19 live outbound provider connections** (Bright Data, `3.232.71.244:443`) in this environment. Breaches the "zero live calls on ordinary page loads" rule. | `evidence/live-call-attribution.txt`; `amazon_search.py:352` gate + `SCANNER_LIVE_ALLOWED=1` in `Northstar_backend/.env` |
| **P0-02** | Hosted-reasoning UI is fully disconnected from its backend. `foundation/api.js:175-179` → `/api/v1/foundation/reasoning/*` = **404**. Real routes are `/api/v1/reasoning/*`. | Live probe: 404 vs 200 · `evidence/reasoning-route-probe.txt` |
| **P0-03** | Hosted stack serves a different (smaller) API than local dev. `Dockerfile.api` CMD = `foundation.app:app`; `main.py`'s 200+ routes are absent. Caddy proxies only `/api/*`. | `Dockerfile.api`, `docker-compose.yml:50-62`, `Caddyfile` |
| **P0-04** | No auth on `/api/autothink/*` (run/models/history). Unauthenticated caller can drive model runs and read all history. `main.py:1035-1063`. | Live probe: 200 unauthenticated on `/api/autothink/history` |
| **P0-05** | Concurrent mid-audit commit changed the audited surface; a second session is running scans and committing. | reflog `2482048 → f232ef8`; untracked `goose_scan_20261009_*.json` |

---

## 5. Creative gaps (top)

- **Product Designer Studio unaudited** (landed mid-audit; 3,620 LOC, 3D packaging view, mockups, provider-gated queue). Must be re-audited.
- **Creative Studio** (783 lines): zero backend. "Storyboard Save" and "Upload Asset" are toast-only (`CreativeStudio.jsx:516, 655`); "Assets in library = 87" is a static sample sum (`:753`).
- **SocialPulse** (674 lines): zero backend. `New Campaign` cannot create (line 347, `setCampaigns` missing); "Generate Variants"/"Schedule" toast-only (`:210-211`).
- **AdPilot**: `Bulk Actions` button has **no onClick at all** (`AdPilot.jsx:149`); tab badge `count: 8` vs 5 rendered rows (`:10`).
- **ListingForge**: 5 dead buttons with no handler (`:249, 250, 312, 345, 366`); badge `count: 24` vs 4 rows.
- **SourceScout** (`ProductFinder.jsx`): default view shows prices/ranks/seller counts **with no DataNotice** (`:13-53` hardcoded); only subviews carry sample disclaimers.
- **PlanUsage**: static `width:'68%'` meter and hardcoded `$299.00` billing rows (`:83, 96-100`) — labeled "sample" but easily skimmed as live.
- **Monitoring**: "Configure Alerts" toast admits "(sample)" (`:235`).
- **a11y**: `TopNav` brand is a clickable `<div>` with no role/keyboard (`:21`); `CommandPalette` input lacks `aria-label`; `DataTable` renders empty `<th>` for action columns; `MemoryBank` search input unlabeled.
- Full list with line references in `CREATIVE_COMPLETENESS.md`.

---

## 6. Technical and operational gaps (top)

- Live-call leak on GET (P0-01).
- Hosted/local API divergence (P0-03).
- Silent error swallowing in every `/api/v1/noncreative/*` endpoint (`noncreative_reads.py:32,41` — any SQL failure returns `[]`/`None`, indistinguishable from real emptiness).
- `adapter/registry.py` drops adapters on `ImportError: pass` (6 sites) — the registry can be silently incomplete.
- `auth.py:31` generates an **ephemeral random JWT secret** when `NORTHSTAR_JWT_SECRET` is unset (both `.env` files lack it) → every token invalidated on restart.
- `data_layer.py` Postgres branch is dead code (`_init_sqlite()` runs unconditionally, `:55-56`) while `foundation` has a real Postgres backend → **two divergent data layers**.
- No worker/scheduler runs inside either FastAPI app; `foundation/local_stack.py:89,103` swallow worker exceptions with `except Exception: pass` → a wedged worker is silent. Docker `worker`/`scheduler` have **no healthchecks**.
- `npm run lint` is a stub (`echo 'Linting not implemented yet'`); eslint is configured but **not installed** → zero linting runs.
- Root `.env` line 98 is unparseable by python-dotenv (breaks `.env` loading for the whole file).
- Root `.env` carries `OPENCODE_GO_ENABLED=1` + a key, but `main.py` never loads root `.env` → the running API reports `configured:false / enabled:false / armed:false`. **Config intent and runtime state disagree** (the app is fail-silent, not fail-loud).
- Duplicate `.env` files (root 53 keys, backend 37) with non-overlapping key sets (the documented `dual_dotenv_divergence_backend_shadowing` issue).
- `00_STATE.json` `test_baseline` is dated **2026-09-22** (16 days stale) and its "GO-LIVE READY / harness FULLY GREEN" claim is contradicted by today's run.
- Docs drift: `SERVICE_READINESS_MATRIX.md` (stale: says Command Center and Keyword Tracker are "UI/shell only"; they now have live reads) and `docs/LOCAL_RUNBOOK.md:191` (same) — both contradicted by current code.

---

## 7. AutothinK gaps

| Capability (§7) | Status | Evidence |
|---|---|---|
| Conversation/task interface | IMPLEMENTED | `AutothinK.jsx` composer + history + output tabs |
| Local inference | **VERIFIED working** | probe: real completion, `northstar-qwen3:rev1`, 14.2 s |
| Hosted (OpenCode Go) inference | **BROKEN (P0-02)** | route 404 from UI |
| Cloud (OpenRouter) inference | GATED by design | `CLOUD_MODEL_LIVE` absent from both `.env` |
| Retrieval / grounding | **NOT IMPLEMENTED** | `build_context` result never reaches adapter |
| Service/workspace context | NOT IMPLEMENTED | no org/session plumbing |
| Task history / saved results / continuation | PARTIAL | global JSON file, no continuation, no org scope |
| Long-running task state, queues, workers | NOT IMPLEMENTED for AutothinK | generic `jobs-durable` exists, unused by AutothinK |
| Cancellation / retry / timeout / recovery | NOT IMPLEMENTED in UI | blocking POST, no cancel |
| Approval checkpoints for consequential actions | NOT APPLICABLE (read-only reasoning) — but **no approval gate exists** for paid cloud runs either |
| Model configuration & routing | IMPLEMENTED for hosted (fail-closed), PARTIAL for local/cloud | `reasoning_provider.resolve_model` is genuinely fail-closed |
| Usage/cost accounting & caps | MISSING for local & cloud lanes | no ledger write on `/api/autothink/run` |
| Memory scope/retention/workspace isolation | MISSING | single-file global store, no tenant key |
| Citations / evidence links / data freshness | MISSING | no citations emitted |
| Security (auth, cross-workspace) | **P0-04** | unauthenticated `/api/autothink/*` |
| Prompt-injection defenses | PARTIAL | spreadsheet prompt says "treat as untrusted data" (`reasoning_tasks.py:302`); listing/ad prompts enforce no-invention rules |

---

## 8. Full pending-work list

`PENDING_WORK.csv` — **63 items**, deduplicated, each with ID, service, category, current state, missing work, evidence path, impact, priority, blocks-full-test / blocks-release, dependencies, owner role, acceptance criteria, verification method, approval needed, effort.

Blocker summary: **7 P0**, **19 P1**, **22 P2**, **15 P3**. 34 items block a full-service test; 21 block release.

---

## 9. Dependency-ordered remediation sequence

1. **Safety first (P0-01, P0-04, P0-05):** set `SCANNER_LIVE_ALLOWED` to a non-opt-in value for the audited environment, add an auth dependency to `/api/autothink/*`, and freeze/coordinate the concurrent session.
2. **Restore the API contract (P0-02, P0-03):** either repoint `foundation/api.js` to `/api/v1/reasoning/*` or mount the reasoning router under `/api/v1/foundation/reasoning/`; decide and document one canonical entrypoint (`main:app` vs `foundation.app:app`) for hosted.
3. **Close the silent-failure class (P1):** distinguish "no rows" from "query failed" in `noncreative_reads.py`; stop swallowing adapter `ImportError`; set `NORTHSTAR_JWT_SECRET`; fix root `.env` line 98.
4. **Finish the rooms (P1):** wire SourceScout to `/api/sourcescout`; build dedicated backends or honest-disabled bodies for Profitability portfolio, Monitoring alerts, Beta-Ops cohorts/reports/eligibility, Customer plan/usage; implement Golden Goose evaluate 10-gate input UI.
5. **Deepen AutothinK (P1):** wire `build_context` → adapter; add usage/cost ledger + caps; add tenant scoping; add cancellation.
6. **Creative completion (P1/P2):** dead controls, false metric labels, missing states, a11y fixes.
7. **Ops & docs (P2):** lint actually running, `SERVICE_READINESS_MATRIX`/`LOCAL_RUNBOOK` truth refresh, delete dead surface, rollback/backup evidence.
8. **Re-audit Product Designer Studio** and only then enter full-service test.

---

## 10. Full-service test entry requirements still unmet

See `READINESS_GATES.md`. Unmet: scope fully defined (Product Designer unaudited; Watch/RankLedger/RivalBoard scope undecided); creative assets/screens to testable acceptance criteria (3 rooms still shells); technical paths implemented (hosted reasoning broken); test environment/data/accounts ready (no isolated test accounts, no signed-in session exercised); critical safety guards verified (P0-01 open); no unresolved blocker (P0-02/03/04 open).

---

## 11. Owner approvals / access needed

| # | Approval / access | Why | Blocking |
|---|---|---|---|
| A1 | Live provider decision for `/api/kirkland/scanner`: confirm whether a GET may ever search live, and if not, flip `SCANNER_LIVE_ALLOWED` to non-opt-in | P0-01 | Full-service test entry |
| A2 | Hosted API surface decision: `main:app` or `foundation.app:app` as the canonical entrypoint | P0-03 | Release |
| A3 | Auth policy for `/api/autothink/*` (who may run a model / read history) | P0-04 | Full-service test entry |
| A4 | OpenCode Go operator authorization for one bounded live hosted-reasoning smoke call (≤1 call, `step-5-preview-free`, free tier) | Only after P0-02 is fixed | Live test tier |
| A5 | Cloud (OpenRouter) decision: arm `CLOUD_MODEL_LIVE` or keep closed, + a per-run cost cap | Currently unbounded | Release |
| A6 | Scope decision: retire or revive The Watch / RankLedger / RivalBoard | Legacy unrouted pages exist | Scope definition |
| A7 | Isolated test accounts + a signed-in session for internal/customer/admin roles | Only 2 of 6 roles exercised | Full-service test entry |
| A8 | Media/creative provider decision (image/video) or explicit "stay concept" sign-off | `SERVICE_GAPS.md` §1-3 | Release |
| A9 | Freeze coordination: no concurrent commits during the full-service test window | P0-05 | Full-service test entry |

---

## 12. Audit artifacts

All under `reports/audit-2026-10-08/`:

| Artifact | Path |
|---|---|
| This summary | `AUDIT_SUMMARY.md` |
| Service inventory | `SERVICE_INVENTORY.csv` (19 rows) |
| Requirements traceability | `REQUIREMENTS_TRACEABILITY.csv` (38 rows) |
| Creative completeness | `CREATIVE_COMPLETENESS.md` |
| Technical completeness | `TECHNICAL_COMPLETENESS.md` |
| AutothinK audit | `AUTOTHINK_AUDIT.md` |
| Pending work | `PENDING_WORK.csv` (63 rows) |
| Full-service test plan | `FULL_SERVICE_TEST_PLAN.md` (54 cases) |
| Test results | `TEST_RESULTS.md` |
| Readiness gates | `READINESS_GATES.md` |
| Evidence folder | `evidence/` (7 files) |

---

## 13. Limitations (stated plainly)

1. **Concurrent modification.** A second agent committed to this repo during the audit and another is actively running scans. Findings were captured against `2482048`; anything touching `f232ef8` (Product Designer Studio) or later is unverified.
2. **No real authenticated session.** Only the unauthenticated role and harness-stubbed authenticated roles were exercised. Invite/redeem, login, admin and cross-workspace journeys were **not** run. `verify-live-signin.cjs` was **BLOCKED** (missing `NS_TEST_EMAIL`/`NS_TEST_PASSWORD`).
3. **No live hosted/cloud model call.** The OpenCode Go and OpenRouter lanes were exercised only via mocks and config probes. The single real completion verified was **local Ollama** (free, no credential).
4. **Incidental live provider calls occurred.** The read-only GET sweep of `/api/kirkland/scanner` produced 19 outbound Bright Data connections because `SCANNER_LIVE_ALLOWED=1` in this environment. This is the evidence for P0-01 and also means **~19 metered requests were consumed during the audit**. No retry was attempted; that probe was stopped after one attribution run.
5. **No browser DOM inspection of the running app.** Visual/creative review is code-level plus the repo's own Playwright harnesses; no screenshots were captured by this audit (the latest repo screenshots date from 2026-10-04).
6. **Performance targets are absent.** No approved performance budget exists in the repo, so no performance verdict is given (recorded as a missing requirement, not invented).
7. **No Postgres run.** Postgres integration tests are documented but were not run (no `FOUNDATION_DB_URL`); SQLite only.
8. The backlog is **not exhaustive** — it covers what was discovered in the inspected scope; the concurrent session's work is outside it.
