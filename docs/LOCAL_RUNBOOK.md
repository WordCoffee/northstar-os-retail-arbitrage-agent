# Northstar OS — LOCAL RUNBOOK

**Branch:** `audit/local-readiness` (Parallel Session A — audit/runbook/verification)
**Scope:** Run the repository locally, from a clean checkout, honestly.
**Status:** Verified for the local `main:app` (SQLite) stack. Hosted/Foundation
(Docker+Postgres) notes are provided for completeness but were not booted in
this session's offline-only mandate.

This runbook is **evidenced**: every command below was either executed during the
audit (marked *executed*) or read from the code (marked *verified by code*).
Anything not confirmed is explicitly flagged.

---

## 1. Prerequisites / local dependencies

| Tool | Minimum | Verified by |
|---|---|---|
| Python 3.12+ (3.14.5 used, venv `venv-phase1c02` works) | 3.12+ | `python --version` → 3.14.5; venv imports deps |
| Node.js ≥ 16 (v24.15.0 tested) | ≥16 | `package.json` `engines.node`; `npm --version` → 11.12.1 |
| npm (≥ 9) | — | `npm --version` |
| git | — | repo is a git worktree |
| OpenSSL / Postgres client (optional, Postgres-only paths) | — | `psql` only needed for manual product-DB migrations |
| Docker + Docker Compose (optional, hosted stack only) | — | `docker-compose*.yml` |
| Ollama (optional, local-LLM rooms) | — | `launch-all.ps1`, `docker-compose.local.yml` |
| A browser (UI) | — | FastAPI serves built SPA; dev server on :8101 |

**Python package installs (unpinned):**
```
Northstar_backend/requirements.txt   # 12 deps: fastapi, uvicorn, python-dotenv, requests, pydantic, bcrypt, PyJWT, httpx, aiofiles, croniter, cryptography, psycopg[binary]
autothink/requirements.txt           # AutothinK chat server deps
```
> These are **unpinned** — a fresh install pulls latest. Verified: the working
> venv (`venv-phase1c02`) already satisfies `import fastapi, uvicorn, httpx`.

**Create a clean venv (documented, not re-created during audit):**
```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
python -m venv venv-phase1c02
venv-phase1c02\Scripts\python -m pip install -r Northstar_backend\requirements.txt -r autothink\requirements.txt
```
`venv*/` is gitignored, so venvs never enter git.

**UI dependencies:** `npm --cwd northstar-os-ui install` (or root `npm install`;
root package.json forwards build/dev to the UI package). `northstar-os-ui/node_modules`
must be present before `npm run build` or `npm run dev`.

---

## 2. Exact start/build commands (clean checkout)

### Backend (FastAPI local `main:app`, port 8000) — *boot verified*
```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
# option A (direct)
cd Northstar_backend
..\venv-phase1c02\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
# option B (root npm wrapper)
npm start        # => python -m uvicorn Northstar_backend.main:app --host 127.0.0.1 --port 8000
```
Boot verification (executed via TestClient, offline): `/health` → 200; `/` → 307
redirect to `/ui`; `/openapi.json` → 200 with **185** routes; foundation router
(`/api/v1/foundation/*`), Golden Goose router (`/api/golden-goose/*`), and
monitoring router (`/api/monitoring/*`) all mounted.

### UI — production build (executed clean: 0 errors, 902ms)
```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
npm run build          # => vite build in northstar-os-ui; outputs to northstar-os-ui/dist
```
Verify: `dist/index.html` + `dist/assets/*.{css,js}` produced; 88 modules
transformed; `dist/` is gitignored (`northstar-os-ui/.gitignore`).

### UI — dev server (port 8101, proxies /api + /health + /autothink + /legal → :8000)
```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
npm --cwd northstar-os-ui run dev    # vite --port 8101 --strictPort
```
Open `http://localhost:8101` (Vite base path `/ui/`).

### Full local desktop stack (backend + AutothinK + optional Ollama)
```powershell
.\launch-all.ps1            # Northstar :8000 + AutothinK :8100, waits on /health
.\launch-all.ps1 -SkipOllamaCheck -NoBrowser
```
`START-NORTHSTAR-ALPHA.bat` → `scripts\launch_alpha.ps1` (adds optional Ollama +
Cloudflare tunnel; NOT needed for pure-local work).

---

## 3. Required environment variables (names only — never values)

Create `.env` from the example (`Copy-Item .env.example .env`) **or** set the
following in your shell. Everything is optional **for pure-local/offline run**
(the app falls back to cached/local data); credentials are required only when
you enable a live external provider. `conftest.py` scrubs credential-shaped
env vars during tests.

**Local runtime / scanner:**
`BRIGHTDATA_UNLOCKER_API_KEY`, `BRIGHTDATA_UNLOCKER_ZONE`, `BRIGHTDATA_API_KEY`,
`BRIGHTDATA_DATASET_ID`, `BRIGHTDATA_REQUEST_TIMEOUT_SECONDS`,
`BRIGHTDATA_REQUEST_DELAY_SECONDS`, `BRIGHTDATA_COSTCO_DETAIL_ENABLED`,
`SEARCH_KEYWORDS`, `DEFAULT_MARKETPLACE`, `PAGES_TO_SEARCH`,
`SCANNER_SEARCH_SOURCE`, `SCANNER_SEARCH_FALLBACK`, `CHOCODATA_API_KEY`,
`SCANNER_OFFER_ENRICHMENT`, `UNWRANGLE_API_KEY`, `MIN_PROFIT_MARGIN_PERCENT`,
`MIN_ROI_PERCENT`, `MAX_SELLER_RANK`, `COSTCO_CATALOG_SOURCE`,
`OPENWEBNINJA_API_KEY`, `COSTCO_CATALOG_MAX_PAGES`, `COSTCO_API_COST_BUFFER_PERCENT`,
`COSTCO_CSV_PATH`, `TOP_DEALS_COUNT`, `SCANNER_LIVE_ALLOWED`.

**DataForSEO (narrowly-routed, offline by default):**
`DATAFORSEO_LOGIN`, `DATAFORSEO_PASSWORD`, `DATAFORSEO_ENABLED`,
`DATAFORSEO_TRANSPORT_ENABLED`.

**Local auth / model flags (read by runtime):**
`NORTHSTAR_UI_MODE`, `NORTHSTAR_OWNER_TEST_MODE`, `ENVIRONMENT`,
`GOLDEN_GOOSE_DEBUG`, `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED`,
`NORTHSTAR_DISABLE_RATE_LIMIT`, `NORTHSTAR_PRIVATE_ALPHA`, `NORTHSTAR_ALPHA_ALLOWLIST`.

**Hosted/Postgres/auth (only for the Docker/Foundation stack):**
`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `FOUNDATION_DB_URL`,
`NORTHSTAR_JWT_SECRET`, `NORTHSTAR_JWT_ISSUER`, `NORTHSTAR_JWT_AUDIENCE`,
`NS_FOUNDATION_ALLOW_REMOTE_DEV`, `DOMAIN`, `HTTP_PORT`.

> **Credential hygiene:** never commit `.env` values; `.env*` is gitignored
> (only `.env.example` is kept).

---

## 4. DB migration & seed/demo behavior

There are **two independent migration systems.** Do not confuse them.

### A. Local SQLite (default local stack) — *verified by code*
- Data file: `Northstar_backend/data/northstar.db` (`db-shm`/`db-wal` are
  transient WAL files). SQLite is the default when `DATABASE_URL`/`SUPABASE_DB_URL`
  are unset.
- The data layer creates its schema **inline on first run**; **no manual
  migration is required** for the local stack. Verified: `/health` booted clean
  on the existing local DB with all routers mounted.

### B. Repo-root `migrations/*.sql` (product DB, Postgres) — *prepared, NOT applied*
- Files: `001_core_auth.sql`, `002_productivity.sql`, `003_golden_goose.sql`,
  `004_costco_non_kirkland.sql`.
- Applied **manually only** (see `MIGRATION_GUIDE.md`):
  `psql "$DATABASE_URL" -f migrations/002_productivity.sql` (etc.).
- **Not auto-applied at startup.** Only needed if you point Northstar at Postgres.

### C. Foundation/hosted migrations — *sha256-ledgered, drift-refusing*
- Files in `Northstar_backend/migrations_foundation/*.sql` (001–012) plus
  rollback files and **`010_demo_dataset.sql`** (the demo/seed dataset).
- Runner: `Northstar_backend/foundation_migrate.py` (exists: verified). It keeps
  a sha256 ledger and **refuses to run on drift**. Executed by the Docker
  Compose `migrate` service (depends on healthy `postgres`; api/worker/scheduler
  depend on migrate success). Uses `DB_URL`/`FOUNDATION_DB_URL`.
- Whether `010_demo_dataset.sql` auto-loads vs. is opt-in is **NOT verified** in
  this offline session — treat demo data as opt-in until confirmed.

---

## 5. Local persistence / restart expectations

- **SQLite persists across restarts.** `data/northstar.db` holds scanner cache,
  golden-goose review/decision state (persisted, org-scoped), credit ledger,
  and foundation shadow-state. Restarting uvicorn does **not** wipe it.
- Backend startup is **non-destructive** — it mounts routers and waits on Ollama
  (logging a warning if unreachable); it does not drop/rewrite tables.
- **UI build artifacts do not persist as a source of truth** — `dist/` is
  gitignored and regenerated by `npm run build`.
- In-memory state (error-rate telemetry, rate limiter window) resets on restart
  by design.

---

## 6. Validating each room locally

All room routes are guarded by `GuardedRoutes` (unauth → `/sign-in`; admin →
`platform_admin`). In the SPA, enable the **local-dev identity shim** (see
`northstar-os-ui/src/foundation/dev.js`) to satisfy auth with headers instead of
a real OAuth flow.

| Room | Route | How to validate locally |
|---|---|---|
| Command Center | `/home` (CommandCenter.jsx) | Renders briefing/task/portfolio from **sample data** (banner: `tone="sample"`). No live provider call. |
| Product Finder (SourceScout) | `/product-finder` | Reads cached scanner result (`Northstar_backend/data/scanner-search-cache.json`); `/api/search*` routes exist. Live scan needs `SCANNER_LIVE_ALLOWED=1` + a provider key. |
| Golden Goose | `/golden-goose` | Wires `foundation/api.js` → `/api/v1/foundation/golden-goose/*`; persisted, org-scoped queue/review/decisions. `GET /api/golden-goose/health`, `/dry-run`, `/scan-mock` all present. |
| Creative Studio | `/creative-studio` | **Concept shell** — sample UI only; no image/video provider wired. |
| SocialPulse | `/socialpulse` | **Concept shell** — sample publishing UI; `social_pulse.py` backend logic exists but no live posting. |
| Listing Guardian | `/listings` | **Sample UI** — local listing-health mock; no live listing data. |
| Keyword Tracker | `/keyword-tracker` | **Concept shell** UI; foundation keyword routes (`/api/v1/foundation/keywords/*`) DO exist backend-side. |
| Monitoring | `/monitoring` | Backend `/api/monitoring/error-alerts` exists; dashboard page is largely sample/local. |
| Admin | `/admin` | Backed by `/api/v1/foundation/admin/*` (dashboard, orgs, export, history, plans). |
| Beta-Ops | `/beta-ops` (+ `/-ops/orgs[:id], invites[:id], cohorts, support, reports, audit, lifecycle, eligibility`) | Backed by foundation admin routes; `platform_admin` only. |

**Backend API surface (verified via `/openapi.json`, 185 paths):** foundation
router (`/api/v1/foundation/**`, incl. `admin`, `organizations`, `invites`,
`golden-goose`, `keywords`, `jobs`, `jobs-durable`, `billing`, `legal`,
`usage`, `audit`), golden-goose finder router (`/api/golden-goose/**`), and
monitoring (`/api/monitoring/error-alerts`). Unauthenticated foundation reads
return **401 (fail-closed)** — correct posture, not a break.

---

## 7. Backup / restore

- **Existing:** `backups/northstar.db.bak` (SQLite backup) and
  `ROllBACK_DRILL.md`/`scripts/rollback_drill.ps1` (git tag → worktree →
  boot-probe offline rollback to `v0.1.0-alpha`). **No automated DB hot-backup
  script was found** in this session.
- **SQLite backup (manual, safe):** stop the backend, then
  `copy Northstar_backend\data\northstar.db backups\northstar.db.bak` — or use
  the sqlite online backup:
  `venv-phase1c02\Scripts\python -c "import sqlite3; c=sqlite3.connect('Northstar_backend/data/northstar.db'); c.backup(sqlite3.connect('backups/northstar.db.bak')); c.close()"`
- **Postgres:** standard `pg_dump`/`pg_restore` (not exercised this session).
- **Restore:** stop backend, replace `data/northstar.db` from backup, restart.

---

## 8. Known limitations / expected non-working external integrations

| Feature | Local state |
|---|---|
| General image generation | **Not implemented** (planned only); no provider client. See SERVICE_GAPS.md. |
| Short video / clip generation | **Not implemented** at all. |
| Reference-image / asset generation | **Not implemented** (Creative Studio is a shell). |
| Live Amazon product search | Needs external paid provider (Bright Data unlocker/chocodata/scavio) + `SCANNER_LIVE_ALLOWED=1`; offline uses cache. |
| Watch / RankLedger / RivalBoard live rank | Parked post-launch; needs SP-API. Skeletons only. |
| Stripe billing + Postgres | Parked post-launch; before first PAID cohort. |
| n8n / webhook / email | Requires Docker services; not part of local SQLite stack. |
| AutothinK chat | Needs Ollama + model; local LLM otherwise shows "offline" lamp. ListingForge + AutothinK expect `northstaros-qwen3.8:27b` (sole local model; single-survivor policy 2026-10-13). |
| `run-agent.bat` | **Broken** — it calls `npm run pipeline`, which does **not** exist in root `package.json` (only dev/build/preview/test/start/lint/format). Do not rely on it. |

### Local LLM lanes (2026-10-13)

- **App lane (default):** native Ollama on `127.0.0.1:11434`, sole model
  `northstaros-qwen3.8:27b` (GSQ-RCO IQ3_XXS + MTP head; capsule SYSTEM baked;
  temp 0.35 / num_ctx 64576). ~43 tok/s warm on the RTX 5080 Laptop 16GB.
- **Performance/vision lane:** llama.cpp — `scripts\start-northstar-llm.ps1`
  serves an OpenAI-compatible API on `127.0.0.1:8080` with MTP speculative
  decoding (`--spec-type draft-mtp`). Model: Qwen3.8-27B UD-Q3_K_XL (Unsloth
  imatrix, 13.1GB — best quality on RTX 5080). Full GPU offload 99/99 layers.
  ~50 tok/s gen. Context 16384. Kills background GPU processes before launch.
  Unload Ollama before starting it (both want the 16GB card) — see the script header.

---

## 9. Oracle handoff checklist (documents only)

Before handing off to Oracle hosting — **no destination changes made here**:
- [ ] Build SPA: `npm run build` → `northstar-os-ui/dist` (0 errors verified).
- [ ] Boot backend: `npm start` → `/health` 200 (verified). Ensure Foundation
      router mounts (log line `foundation router not mounted` must be absent).
- [ ] Provide `FOUNDATION_DB_URL`/`POSTGRES_*` and run `foundation_migrate.py`
      (drift-refusing ledger) against target Postgres.
- [ ] Decide demo seed: confirm whether `010_demo_dataset.sql` should load in
      the hosted env (NOT verified as auto).
- [ ] Ship real credentials ONLY in host secrets (`.env` never committed):
      list of names in §3 above.
- [ ] Pin `requirements.txt`/Node version for reproducible production builds
      (currently unpinned).
- [ ] Resolve `run-agent.bat` (broken `npm run pipeline`) or document removal.
- [ ] Oracle-hosting-blocked gaps: image/video generation, media storage,
      moderation (§9 of SERVICE_GAPS.md) require product decisions first.

---

## 10. Verification evidence (this audit)

| Check | Result |
|---|---|
| Backend boot (TestClient, offline) | `/health` 200; `/` 307→`/ui`; `/openapi.json` 200 (185 routes) |
| Router mount | foundation /api/v1/foundation/** ✓; golden-goose /api/golden-goose/** ✓; monitoring ✓ |
| Unauthenticated foundation read | 401 (fail-closed, expected) |
| UI production build | `npm run build` → **0 errors**, 88 modules, 464 KB bundle |
| Env used | `venv-phase1c02` (fastapi/uvicorn/httpx OK); Node v24.15.0 |
| Helper added | `Northstar_backend/_audit_bootcheck.py` (rerunnable, offline) |