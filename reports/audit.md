# PHASE 0 AUDIT — NorthstarOS Secure Control-Layer Build
### (Lightpanda Connect + Master Brain Kernel + Data Layer)

- **Date:** 2026-10-10
- **Owner:** T2 Holdings LLC
- **Branch audited:** `feature/overnight-remediation-20261009` · **HEAD:** `d099b16` (design-studio commit; my earlier tool-scan report is `c91b4a0`)
- **Working tree:** **419 dirty entries** (2 deleted, 7 modified, 411 untracked) — parallel-session work in progress (design-studio + others). **No `.env` file is tracked or dirty.**
- **Method:** READ-ONLY inspection. No code changed, no files deleted, no live fetches, no browser runs, no provider calls, no Amazon access. Secret values were never read or printed; env **names** only. `.env` files were never opened.
- **Labels:** **VERIFIED** = inspected code/ran the command in this audit · **REPORTED** = from prior in-repo docs/state · **PROPOSED** = design proposal, not built · **UNKNOWN** = not determinable from this pass.
- **Spec note:** the Phase 3 section of the build spec was truncated at "Only the gateway is exposed." — the remainder is a needed owner input (see D1).

---

## 1. Repository map (VERIFIED)

Dual-era monorepo. Two coexisting codebases plus a separate UI session:

| Area | Path | What it is | State |
|---|---|---|---|
| Python backend (legacy app) | `Northstar_backend/` | FastAPI app (`main.py`), legacy services, provider clients, tests. **611 `.py` files excluding venv dirs** (2,225 raw incl. venvs). | Active for legacy/domain code |
| Foundation core (hosted product) | `Northstar_backend/foundation/` | Auth, orgs, jobs, scheduler, admin, keywords, economics, billing, beta ops, GG persistence. 41 top-level modules + `api/ beta/ billing/ economics/ keywords/ operations/ tests/`. | Active; 70 test files; migrations 001–012 |
| Golden Goose pipeline | `Northstar_backend/agents/golden_goose_finder/` | Real multi-phase scanner + adapters + its own tests (~20 files) | Active, live-gated |
| AutothinK | `autothink/` | Standalone FastAPI server (`127.0.0.1:8100`) + UI; also mounted/proxied from `main.py` | Active; cloud lane gated |
| UI (separate session) | `northstar-os-ui/` | React SPA (design-studio work ongoing) | **DO NOT TOUCH this build** |
| Machine truth | `master-brain/`, `docs/`, `reports/`, `00_STATE.json`, `tests/BASELINE.json` | Platform brain, build state, reports, baselines | Read-only inputs |
| Legacy Node pipeline | root `src/`, `scripts/`, `legacy/`, `northstar-os-retail-arbitrage-agent/` | Old 3-stage Bright Data→normalize→score pipeline + old UI | Superseded (stale npm scripts) |
| Deploy | `deploy/` (backup.sh, restore.sh, images.lock), `docker-compose*.yml`, `Dockerfile.api/.ui`, `Caddyfile` | Local + hosted (OCI-prep) posture | Hosting blocked on owner (DEPLOY-F2+) |

## 2. Git & environment state (VERIFIED)

- `python --version` on PATH → **3.14.5**, and backend deps import OK: `fastapi, uvicorn, bcrypt, jwt, requests, yaml` (VERIFIED via import test). `Northstar_backend/venv` python is also 3.14.5 but has **no pytest** (VERIFIED). `Northstar_backend/venv-wsl` exists (WSL-only).
- `.github/workflows` **does not exist**; `.pre-commit-config.yaml` **does not exist**; `gitleaks`, `pip-audit`, `pre-commit` **not detected** installed on PATH (VERIFIED via presence checks).
- Root `package-lock.json` and `northstar-os-ui/package-lock.json` exist; **no** `pyproject.toml`/`uv.lock` under `Northstar_backend` (VERIFIED). Backend `requirements.txt` is unpinned (REPORTED by `docs/SERVICE_GAPS.md`; not re-verified line-by-line).

## 3. Test infrastructure (VERIFIED commands this audit)

- `Northstar_backend/foundation/tests/` — **70 test files**; `python -m pytest Northstar_backend/foundation/tests --collect-only -q` **from repo root → 819 tests collected, 0 errors** (VERIFIED).
- Same command **from `Northstar_backend/`** → 59 collection errors: `ModuleNotFoundError: No module named 'Northstar_backend'` because tests import `from Northstar_backend.foundation import …` (VERIFIED). The canonical runner (`scripts/run_all_tests.ps1`) invokes pytest from `Northstar_backend/`; the exact combination that produced the recorded baselines is **UNKNOWN** — Phase 1 should pin one canonical invocation (from repo root is verified working).
- Canonical local runner: `scripts/run_all_tests.ps1` — 5 suites (backend full, GG module, UI contract, shell contract, Functions contract), diffed against `tests/BASELINE.json`; **local only, no CI** (VERIFIED). Line 21: "No CI integration — local runner only."
- `tests/security/` **does not exist** (VERIFIED) — Phase 1 target.
- Postgres-dependent tests are env-guarded (skip unless `DB_URL`/`FOUNDATION_DB_URL` set; disposable PG via `NORTHSTAR_PG_TEST_*`) (VERIFIED via conftest/test files).
- Recorded baselines (REPORTED, `00_STATE.json`): full-suite 3,423 passed / 65 skipped / 1 known failure (protected-hash drift); GG module 511; UI 1,122; admin/tenant subset 92/0.

## 4. Service inventory & classification (VERIFIED via code/docs)

Classification: **Implemented-ready** (works locally end-to-end) / **Implemented-internal** (real code, limited by gates/partial wiring) / **Prototype** (code exists but unwired/shell) / **Planned** / **Legacy**.

| Service | Key code | Invocation | Tests | Classification |
|---|---|---|---|---|
| **Product Finder** (scanner) | `amazon_search.py`, `scanner_data.py`, `filters/universal_filter.py` | `GET /api/products/finder` (`main.py` ~2388); cache-only default; live refresh 403 unless `SCANNER_LIVE_ALLOWED` | `test_scanner_endpoint.py`, `test_scanner_cache_only.py`, `test_scanner_completeness.py` | **Implemented-internal** (live-gated, paid provider) |
| **Golden Goose** | `agents/golden_goose_finder/*` (orchestrator, scorer, adapters, free-tier router) + `foundation/golden_goose_{decision,store,top5}.py` | `/api/golden-goose/*` (`/scan-mock`, `/dry-run`; `/scan` gated); CLI `python -m agents.golden_goose_finder.main`; foundation `/api/v1/foundation/golden-goose/**` | ~20 module + 4 foundation files | **Implemented-internal** (live = two-gate) |
| **SourceScout** | routes in `main.py` ~1740–1838 read `data/catalog/sourcescout_manifest.json`; tooling `tools/build_sourcescout_manifest.py`, `auto_update_sourcescout.py`, `quantity_match_validator.py` | `GET /api/sourcescout[/matches,/mismatches,/review,/summary]` | **no dedicated test files found** | **Implemented-internal** (static-manifest contract; refresh = operator-run tooling) |
| **ListingForge** | `listing_forge.py` (library; local-LLM copy + compliance + Rufus score) | **No route/CLI/importer found**; `api_docs.py` documents `/api/v1/listings/*` — no mounted route | none found | **Prototype / orphaned** |
| **AdPilot** | `ad_pilot.py` (bid tiers, keyword lifecycle; library) | No route/importer; exercised via fixture `word_coffee.py`; foundation classifies as LEGACY_ECON | only indirect | **Prototype / orphaned** |
| **SocialPulse** | `social_pulse.py` (brand-voice content generation; library) | No route/importer | none found | **Prototype / orphaned** |
| **Commerce Ops** | `noncreative_reads.py` `GET /api/v1/noncreative/commerce-ops/queue` (read-only, honest-empty) | Read-only projection; no dedicated backend (REPORTED `docs/NON_CREATIVE_REMAINING_WORK.md`) | `test_noncreative_reads.py` | **Prototype** |
| **AutothinK** | `autothink/backend/server.py`, `llm_adapter.py` (Ollama default; cloud gated `CLOUD_MODEL_LIVE` + key), `orchestration/router.py`, `memory/*`, `audit/*.jsonl` | Standalone `:8100`; mounted `/autothink` + proxied `/api/autothink/*` in `main.py` | 4 module + 2 backend files | **Implemented-internal** |
| **Master Brain** | `master_brain_gateway.py` (classifier + JSONL audit), `master_brain_learning.py` (+ `/api/v1/learning/*`), `master_brain_profiles.py` (CLI), `master_brain_subscribers.py` | Offline; wired learning routes | 6 test files | **Implemented-internal** |
| **Foundation core / Admin / Beta-Ops** | `foundation/api/router.py` (~100 endpoints), admin/orgs/jobs/audit/approvals | `/api/v1/foundation/*` | 70-file suite | **Implemented-ready (local)**; hosting blocked only |
| **Keyword Tracker** | `foundation/keywords/*` | foundation keyword routes substantial | 4 keyword test files | Backend **Implemented-internal**, room **Prototype** |
| **Monitoring** | `error_alerts` route | `GET /api/monitoring/error-alerts` | present | **Implemented-internal (partial)** |
| **Creative / Design Studio** | `design_studio_api.py` mounted; UI rebuild active in a separate session | `/api/v1/**` (design-studio) | tools/verify-design-studio.cjs etc. | **Prototype — do not touch (separate session)** |
| **Guardian / Listings room** | UI sample-only; Python listing code elsewhere | — | UI contract only | **Prototype (UI shell)** |
| **Legacy Node pipeline** | `src/`, nested repo copy | npm scripts stale vs `package.json` | — | **Legacy** |

## 5. API surface & doc drift (VERIFIED)

- `Northstar_backend/main.py` — FastAPI app: mounts GG router, design-studio router, BFF envelope middleware, security headers, request tracing, rate limiter, auth deps; serves UI via `ui_serving.mount_ui`.
- **Doc drift finding:** `api_docs.py` documents `/api/v1/listings/*`, `/api/v1/ads/*`, `/api/v1/social/*` endpoints that **do not exist** in `main.py` (no mount for `listing_forge`/`ad_pilot`/`social_pulse`). Treat `api_docs.py` as aspirational; the new gateway contracts must come from mounted reality.

## 6. Migrations & data stores (VERIFIED via SQL headers + docs)

- **Older app:** root `migrations/` → `001_core_auth.sql`, `002_productivity.sql`, `003_golden_goose.sql`, `004_costco_non_kirkland.sql`.
- **Current (foundation):** `Northstar_backend/migrations_foundation/` → `001_foundation.sql` (57 tables) … `012_golden_goose_persistence.sql`, **additive-only** per headers, plus rollback companions for 002–007. Applied via `foundation/migrate.py` with `schema_migrations` + **checksum drift = fail closed**; startup asserts migrations current (`api/state.py`).
- **DBs:** SQLite `Northstar_backend/data/northstar.db` (+ dated backup) for local; Postgres for hosted path (`DB_URL`/`FOUNDATION_DB_URL`); backup record in `docs/BUILD_STATE.md` (SHA256 recorded; `backups/northstar.db.bak`); `deploy/backup.sh`/`restore.sh` exist for hosted (not executed — REPORTED).
- **Companion `products.db` (SellerSprite history) is NOT in this repo** — P0-T2 split says the companion dataset lives in the separate `fba-product-screener` repo (REPORTED). Treat cross-repo data work as UNKNOWN until verified there.
- Rule carried in: **do not mutate raw caches/benchmarks**; new modules/tables only.

## 7. Browser / Chrome Connect inventory — Phase 3 input (VERIFIED)

**In-repo:**
- `tools/chromeconnect_guard.py` — Python half of the "Chrome Connect is the controller" rule: (a) import hook refuses `playwright*` unless a controller instruction is active; (b) exclusive port-9222 lock in `.chromeconnect/`; (c) `cc_call()` hands tasks to the external controller (`CHROMECONTROL_ROOT`, default `C:\Users\T2Hol\OneDrive\Documents\Default Project`, CLI `scripts/chromecontrol-agent.js`). **No flag/env escape hatch.**
- **Gap: no in-repo module imports the guard** (grep: only self-references), and **`cc_call()` has no callers in-repo** (VERIFIED). Enforcement today is convention-level in this repo.
- `Northstar_backend/costco_playwright_scraper.py:6` — **direct `playwright.async_api` import, unguarded** (legacy; `.bak` also present). A live bypass path if ever run.
- `tools/browser_agent.py` — legacy local "browser-use + Ollama vision" agent (header documents account-signup/Cloudflare flows; operator-approval language). Not guard-wired.
- `tools/sourcescout_cdp.py` — screenshot helper against local UI (`127.0.0.1:8000/ui`). `tools/test_chrome.py`, `browserbase_amazon.py`, `costco_browser_scraper.py` — other browser-adjacent files.
- `.chromeconnect/` at repo root — lock dir (empty at audit).
- **External (REPORTED, not in this repo):** the controller project ("Default Project") holds `lib/chromecontrol/policy.js`, `config/chromecontrol_policy_owner.json`, and the selection-aware MCP launcher — the operator-owned allowlist/prohibited-action system referenced by `AGENTS.md`. Its live status/baseline fingerprint is outside this audit's scope.

**Phase 3 implication (PROPOSED):** Lightpanda Connect gateway becomes the single browser-egress path for agents; the legacy browser scripts above need an owner ruling: guard, quarantine, or archive. `chromeconnect_guard.py` remains the agent-facing controller rule until the operator decides how Lightpanda Connect coexists with Chrome Connect (§4 truncated — see D1).

## 8. Provider / cache layer (VERIFIED inventory, summary)

- **Provider clients (~25):** Bright Data family (`bright_data_client`, `brightdata_client`, `bright_data_costco*` ×5), Costco (`costco_api_client`, `costco_client`(CSV), `costco_browser_scraper`, `costco_playwright_scraper`, `costco_live_runner`), DataForSEO (`dataforseo_adapter`), RapidAPI pool (`rapidapi_client`, `rapidapi_router` 6-host pool, `rapidapi_compare`), Scavio, Canopy, Rainforest, Firecrawl (amazon+costco), Easyparser, scrape.do, Browserbase, OpenWebNinja (adapters), Amazon search dispatch (`amazon_search.py`).
- **Infra:** `rate_limiter.py` (FastAPI per-plan windows + prod posture assert), `quota_tracker.py` (RapidAPI + DataForSEO header-driven), `credit_ledger.py`, `provider_waterfall_router.py` (RapidAPI→DataForSEO with warning gates + audit), `provider_mappers.py`, `adapters/` registry pattern.
- **Caches/assets:** root `data/` (snapshots/normalized/scored — output dirs now git-ignored; `costco-items.csv`; costco-*.json), `Northstar_backend/data/` (`scanner-search-cache.json`, `seller-offer-cache.json`, catalog manifests, `northstar.db`, golden-goose-reports). **Do not mutate** — new modules/tables only.

## 9. Secrets, config, auth, logging (VERIFIED where marked)

- **Where secrets live:** root `.env`, `Northstar_backend/.env`, `northstar-os-retail-arbitrage-agent/.env` (nested legacy repo). Only `.env.example` variants are tracked (`git ls-files` VERIFIED); all three `.env` paths are **git-ignored** (root `.gitignore` line 2 `.env`, plus `Northstar_backend/.gitignore`) — `git check-ignore` VERIFIED; **zero `.env` entries in git status** (VERIFIED).
- **Prior full-history scan** (`NO_LEAK_AUDIT.md`, 2026-09-20, REPORTED): PASS — no Northstar credential committed in 200 commits. Two open hygiene items: **F2** — historical pipeline-output blobs at commit `009ac85` embed a third-party JWT-shaped URL token (not a Northstar credential); output dirs now ignored; **history rewrite = owner decision (still open)**. **F5** — `localhost:3001` dev hint in shipped landing snippet.
- **Config loading:** direct `os.environ` reads per module; no central config loader (VERIFIED in foundation; legacy modules use `load_dotenv()` at import). Test conftests scrub credential-shaped env vars (VERIFIED). Env **names** referenced (sample): `BRIGHTDATA_*`, `DATAFORSEO_LOGIN/PASSWORD`, `RAPIDAPI_KEY`, `CANOPY_API_KEY`, `SCAVIO_API_KEY`, `CHOCODATA_API_KEY`, `OPENWEBNINJA_API_KEY`, `UNWRANGLE_API_KEY`, `OPENCODE_GO_API_KEY`, `NORTHSTAR_JWT_SECRET`, `DB_URL`/`FOUNDATION_DB_URL`, `POSTGRES_*`, `ENVIRONMENT`, `SCANNER_LIVE_ALLOWED`, `CLOUD_MODEL_LIVE`, `MEDIA_GEN_LIVE`, `NORTHSTAR_OWNER_TEST_MODE`.
- **Auth:** legacy `auth.py`/`auth_deps.py` (users/plans/roles) + foundation `authn.py`/`auth_session.py`/`api/deps.py` (HS256 JWT, HttpOnly cookie + CSRF double-submit, session revocation, per-process→shared login throttle, dev shim loopback-only, fail-closed postures).
- **Logging:** `logging_config.py` — structured JSON/dev formatter + `log_provider_call`; **no redaction filter at the logging layer** (VERIFIED by read). Redaction exists **only inside foundation** (`observability.redact()`, `audit._scrub()`). Phase 1's global log-redaction filter is needed (R4).

## 10. Existing security controls Phase 2 can build on / must not break (VERIFIED summary)

- Foundation: field-level redaction (`observability.py`), scrubbed audit events (`audit.py`), denial-audit middleware (`app.py`), JWT hardening + startup posture (`authn.py`), CSRF (`auth_session.py`), login throttle (`login_throttle.py`), permissions matrix (`permissions.py`), approval requirements (`approvals.py`), jobs runtime re-authorization/budget rechecks (`jobs_durable.py`), data-rights register + enforcement (`data_rights.py`), freshness policy, owner test-mode fail-closed (`owner_test_mode.py`), webhook HMAC constant-time compare (`billing/processor.py`), security headers (`app.py`).
- Legacy app: security headers + tracing (`security.py`), rate limiter middleware, BFF envelope, offline test network guards (`network_guard.py`, `sitecustomize.py` block real `requests` during test runs).
- **Absent (Phase 2 targets):** SSRF/DNS-rebinding defense, per-domain robots/rate/byte/time budgets, capability grants with expiry, hash-chained tamper-evident audit log, redirect/IP re-checks. No `tests/security/` suite exists.

## 11. Frozen / protected assets (do-not-touch list for this build)

- Frozen 25-ASIN benchmark manifest + fixtures (`benchmark_25asin_manifest.py` states "Do not edit without a new frozen revision + fingerprint bump"); `test_proof_batch*` protected-hash drift is a **known pre-existing failure** — do not "fix" by editing fixtures.
- Frozen Costco discovery run `20260828T021658Z` (`bright_data_costco*.py` defaults reference it read-only).
- `tests/BASELINE.json`, `backups/northstar.db.bak`, `data/snapshots|normalized|scored` outputs, `data/catalog/sourcescout_manifest.json`.
- UI (`northstar-os-ui/`) and the old Northstar shell — out of scope entirely (§0.8).

## 12. Risks register (open) — severity for THIS build

| # | Risk | Severity | Notes / target phase |
|---|---|---|---|
| R1 | `costco_playwright_scraper.py` direct Playwright import (unguarded) contradicts "one controller" rule | High | Quarantine/guard/archive decision (D4); Phase 3 |
| R2 | `chromeconnect_guard.py` has no importers; `cc_call()` unwired — enforcement is convention-level in-repo | High | Phase 3 gateway must wire real enforcement |
| R3 | No central env/config loader; import-time `load_dotenv()` in legacy modules | Medium | Phase 1 config loader; keep foundation behavior |
| R4 | Logging layer lacks redaction filter (foundation-only redaction) | Medium | Phase 1 log-redaction filter |
| R5 | Historical git blobs (F2) third-party URL token; history rewrite still owner-decision | Low | Owner decision; do not rewrite unilaterally |
| R6 | Supply chain: no CI, no secret scanning, unpinned Python deps, no pre-commit | High | Phase 1 (all of it) |
| R7 | Legacy `tools/browser_agent.py` contains account-signup helper flows; conflicts with "no login bypass/stealth" rule if ever run | Medium | Quarantine decision (D4) |
| R8 | `api_docs.py` documents endpoints that don't exist (listings/ads/social) | Low | Gateway contracts must use mounted reality |
| R9 | Test invocation ambiguity: foundation tests import `Northstar_backend.*`; failing collection from `Northstar_backend/` cwd (host python) | Medium | Phase 1: pin canonical invocation + CI |
| R10 | 419 dirty entries incl. parallel-session work — collision risk | Medium | Work in NEW modules only; small commits; never `git add -A` |
| R11 | Companion `products.db` not in this repo; cross-repo data path unverified | Low | Verify in `fba-product-screener` before Data Layer phase |
| R12 | `python` PATH = 3.14.5 while repo venvs differ; env drift across machines | Low | Phase 1: pin runtime + lockfiles |

## 13. Owner decisions needed (before/alongside Phase 1)

- **D1 — Spec remainder:** §4 was truncated at "Only the gateway is exposed." Paste the full Phase 3 (Lightpanda Connect) + Master Brain Kernel + Data Layer sections before Phase 3 planning.
- **D2 — Browser-legacy ruling:** for `costco_playwright_scraper.py`, `browser_agent.py`, `sourcescout_cdp.py`, `browserbase_amazon.py`, `costco_browser_scraper.py`: guard / quarantine / archive? (R1, R7)
- **D3 — Supply-chain tooling:** gitleaks install method (pip/standalone binary) + CI choice (none exists; local pre-commit first vs GitHub Actions) — Phase 1 can default to pre-commit + local runner if silent.
- **D4 — Dependency pinning strategy:** pin exact versions in `requirements.txt` vs adopt `uv` + `uv.lock` for `Northstar_backend` (Phase 1 spec says lockfiles-with-hashes; needs a tooling pick).
- **D5 — Chrome Connect vs Lightpanda Connect relationship:** how the existing operator-owned Chrome Connect guardrails (`policy.js`, owner config) and the new gateway coexist/supersede — draft policy diff only (per §0.9), never applied by the agent.
- **D6 — Canonical test invocation + Python runtime:** confirm repo-root pytest invocation + which interpreter (3.14.5 verified working for foundation collection; venvs lack pytest) (R9, R12).
- **D7 — History rewrite (F2):** keep flagged-and-ignored (status quo) — confirm.

## 14. Phase 1 readiness (PROPOSED — nothing started)

Given the audit, Phase 1 "Security Baseline" can be built entirely additively without touching the 419 dirty entries or frozen assets:
1. `tests/security/` pytest suite skeleton + pinned invocation (repo root).
2. Log-redaction filter wired into `logging_config.py` (foundation redaction reused) + tests.
3. `.gitignore`/gitleaks config + pre-commit hook + baseline scan results (historical F2 allowlisted as known/ignored).
4. Env-name inventory doc + config-loader shim (names only; no value handling).
5. SBOM + `pip-audit`/`npm audit` scripts; lockfile generation decision (D4).
6. STRIDE threat model draft → `reports/threat_model.md` for owner review.

---

## Appendix A — commands run (all read-only; no live fetches)
`git branch --show-current`, `git log --oneline -8`, `git ls-files` (filtered), `git check-ignore` (3 paths), `git status --porcelain` (counts only), dir listings (`server/ shared/ migrations/ deploy/ .chromeconnect/ tests/ foundation/`), file reads (paths logged above), `python --version`, `python -c "import fastapi,…"`, `python -m pytest … --collect-only` (foundation tests; 819 collected from repo root; 59 collection errors from Northstar_backend cwd), env-NAME extraction from `.env.example` (key names only, values never printed), existence checks (`.pre-commit-config.yaml`, `.github/workflows`, lockfiles, `tests/security`, tool availability). Two read-only explore subagents for breadth (no writes).

## Appendix B — key paths index
- Foundation: `Northstar_backend/foundation/` (+ `api/router.py`, `migrations_foundation/001–012`)
- Services: `Northstar_backend/agents/golden_goose_finder/`, `Northstar_backend/{amazon_search,scanner_data,listing_forge,ad_pilot,social_pulse,noncreative_reads}.py`, `autothink/`
- Browser: `tools/chromeconnect_guard.py`, `tools/browser_agent.py`, `Northstar_backend/costco_playwright_scraper.py`, `.chromeconnect/`; external controller per `CHROMECONTROL_ROOT`
- State/docs: `00_STATE.json`, `docs/BUILD_STATE.md`, `docs/SERVICE_READINESS_MATRIX.md`, `docs/SERVICE_GAPS.md`, `NO_LEAK_AUDIT.md`, `tests/BASELINE.json`, `scripts/run_all_tests.ps1`
