# TECHNICAL_COMPLETENESS — non-creative / engineering audit

**Audit date:** 2026-10-08 · **Baseline:** `2482048` · **Method:** source inspection + live local boot + network instrumentation + safe test execution.
**No code changed. No fix applied. No external action taken.**

---

## 0. Reproduced-by-anyone commands

```powershell
# 1. Build (0 errors verified)
npm run build

# 2. Boot the API locally (port 8000/8017) — CWD must be Northstar_backend
cd Northstar_backend
python -m uvicorn main:app --host 127.0.0.1 --port 8017 --log-level info

# 3. Route inventory
(Invoke-WebRequest http://127.0.0.1:8017/openapi.json).Content | ConvertFrom-Json

# 4. Prove/​disprove "zero live calls on a GET" (network instrumentation)
python $env:TEMP\opencode\ns_attr_probe.py      # attribute outbound connects per endpoint
```

---

## 1. Frontend

### 1.1 Routes and deep links
- `App.jsx` contains **51** `<Route path=` declarations (a foundation gate test asserts **48** — see §7).
- All `nav-config.js` routes resolve; no dead deep links from nav.
- **Gated correctly:** unauthenticated → `/sign-in`; `/beta-ops*` + `/admin` require `platform_admin` (`App.jsx:60-75`).
- **Not gated:** internal operator rooms are reachable by any authenticated customer by URL (see CREATIVE §B.2).
- Refresh/back behaviour is standard React Router; hash-free SPA served at `/ui` with an index fallback (`ui_serving.mount_ui`, `Caddyfile` `try_files {path} /index.html`).

### 1.2 Component wiring and interactive controls
- Full control audit in `CREATIVE_COMPLETENESS.md` §C. Summary: **~18 dead or broken controls** across AdPilot, ListingForge, SocialPulse, CreativeStudio, Monitoring, KeywordTracker, CompetitorMonitor, ProfitabilityDashboard, OrgsList.
- `ReasoningModelSelector.jsx:44` `.catch(() => null)` silently swallows the 404 → the selector permanently shows "No models" with no error surfaced. This is the failure mode that hid **P0-02**.

### 1.3 API contract handling
- Two clients: `services/signals.js` (18 endpoints, read-only) and `foundation/api.js` (78 endpoints). Both use a never-rejecting `settle()` wrapper → components render honest "unavailable" states.
- **P0-02:** `foundation/api.js:175-179` targets `/api/v1/foundation/reasoning/*`, which **does not exist**. The real routes are `/api/v1/reasoning/*`. Live-proven: `GET /api/v1/foundation/reasoning/models → 404`, `GET /api/v1/reasoning/models → 200`.
  - Affected UI: `ReasoningModelSelector` (all rooms), `AutothinK` hosted lane, `AdPilot` ad-copy panel, `ListingForge` proposal panel, `SpreadsheetLab` analysis.
- `foundation/api.js:107` calls `GET /api/v1/foundation/jobs` which only supports **POST** → `405` (verified live). The comment on that line already admits "list not exposed".
- `services/api.js` (deprecated legacy client) is imported by 10 unrouted pages; not part of the shipped bundle but still in the tree.

### 1.4 Build / type checks / linting / tests
- `npm run build` → **0 errors**, 92 modules, 1.66 s (`evidence/build-output.txt`).
- **No type checking** — the SPA is plain JSX, no TypeScript.
- **Linting is not wired:** `eslint.config.js` exists and is a real flat config, but neither `eslint` nor `globals` is installed and `node_modules/.bin` is empty. `npm run lint` = `echo 'Linting not implemented yet'` and exits 0 — it *looks* like a passing check.
- Test results in `TEST_RESULTS.md`.

### 1.5 Feature flags / legacy routes
- Legacy routes (`/hub`, `/prospector`, `/offerchisel`, `/towncrier`, `/auctioneer`, `/thewatch`, `/rankledger`, `/rivalboard`, `/foundation`, `/jobs`, `/keywords`, `/beta-signup`) survive only in the dead `src/data/services.js` palette. `DEAD_SURFACE_MANIFEST.md` §A flags this as an accidental-remount risk.

---

## 2. Backend and API

### 2.1 Endpoint inventory
- `/openapi.json` exposes **210** routes.
- UI-called: all 18 `signals.js` endpoints resolve.
- **6 UI-called endpoints do not exist** (P0-02 + jobs 405, see §1.3).
- Substantial backend surface has **no UI caller**: auth/register/login/refresh/me, plans, credits, support, invites/redeem, the whole `/api/kirkland/*` group, all 12 `/api/suppliers/*`, `/api/v1/catalog/*`, `/api/products/{asin}/canopy|offers`, `/api/dataforseo/validate`, `/api/filters/universal/evaluate`, and the memory/learning **write** routes.
- 126 foundation routes; a material subset unused (billing, demo, filesets, legal publish, schedules PUT, several keywords routes).

### 2.2 Authentication and authorization
- Two stacks: legacy JWT (`Northstar_backend/auth.py`, used by `main.py` routes) and the foundation session cookie stack (`foundation/authn.py`, cookie + CSRF double-submit + optional local-dev `X-User-Id` shim).
- **P0-04:** `/api/autothink/{models,run,history}` have **no auth dependency** (`main.py:1035-1063`). Verified live: `GET /api/autothink/history → 200` unauthenticated, returning 7,565 bytes of session history.
- `NORTHSTAR_JWT_SECRET` is unset in both `.env` files → `auth.py:31` generates `secrets.token_hex(32)` at import → all tokens silently invalidated on every restart, and the "shim" posture is not surfaced to the operator.
- `NORTHSTAR_PRIVATE_ALPHA` unset in both `.env` files → the private-alpha allowlist lock is **OFF** in the default local configuration.
- No JWKS / key rotation (documented as intentional, `foundation/tests/test_auth_hardening.py:299`).
- Authorization is enforced server-side on foundation routes (verified: 401 without a session on `/api/v1/foundation/*`), which is correct — the UI-only gating concern is limited to internal-room visibility, not data.

### 2.3 Input validation and error contracts
- Pydantic models with explicit constraints (`RunRequest`, `ScanRequest`, `DiscoveryFilters`, `ReasoningRunRequest`, …). ASIN shape validated (`main.py:1494-1499`).
- Envelope middleware (`bff_envelope.py`) normalizes legacy prefixes to `bff/v1`.
- Global exception handlers exist on both apps.
- **Gap:** error *classification* is inconsistent — several read endpoints collapse distinct failures into one indistinguishable payload (see §4).

### 2.4 Idempotency / duplicate-submission / retry / timeout / cancellation
- **Good:** `foundation/jobs_durable.py` implements idempotency keys, atomic claim, leases, recovery, usage reserve/settle with exactly-once semantics and driver-scoped audit of every transition. `foundation/billing/service.py` rolls back, re-checks idempotency and re-raises.
- **Gap:** no idempotency on `/api/autothink/run` — a double-click submits two model runs; the UI disables the button while submitting, but the API has no key.
- No cancellation path for a running generation (local lane has a 600 s timeout, hosted 120 s).

### 2.5 Job execution and scheduler behaviour
- Implemented and real: `foundation/jobs_state.py` (state machine + legal transitions), `jobs_durable.py` (durable queue), `jobs_worker.py` (`run_once`/`run_loop`/`drain`), `jobs_scheduler.py` (`tick()`, atomic occurrence claim, misfire window, org-active recheck, enqueue-only by design).
- **14 registered job handlers, 12 of which are deterministic simulation doubles** (`jobs_handlers.py:288-352`: `immediate_success`, `slow_success`, `transient_failure`, `permanent_failure`, `timeout`, `rate_limit`, `malformed_output`, `cancellable`, `cost_variance`, `needs_approval`, `fixture_reader`). Real work: `keyword_import`, `pipeline.ingest_identity`, `golden_goose.monthly_top5`. `provider_class ∈ {local, fixture}` for all — **no handler makes an outbound provider call**, by design and correctly labelled via `/jobs-durable/handler-registry` (`only_local_handlers: true`).
- **No worker/scheduler runs inside either FastAPI app** (`main.py` lifespan: rate-limit posture + DB init + Ollama probe only; `foundation/app.py` lifespan: state build + close).
- Docker defines `worker`, `scheduler`, `migrate` services; **neither worker nor scheduler has a healthcheck** (only postgres does).
- **Silent-loop defect:** `foundation/local_stack.py:89,103` are bare `except Exception: pass` inside the worker/scheduler loops; `foundation_worker.py:26-27` and `foundation_scheduler.py:21-22` only `print()`. A persistently failing worker runs forever producing no diagnostics.
- Golden Goose has its own separate **local scheduler stub** with an empty dotted path (`gg_workflow.py:195-201`) and a webhook stub that fires at `https://placeholder.invalid` when unconfigured (`agents/golden_goose_finder/main.py:886-891`).

### 2.6 Health checks, logging, metrics, audit trails
- `/health` (simple) and `/health/detailed` (data-file presence, provider key presence, model availability, test-status file) exist. `Caddyfile` proxies only `/api/*`, so **bare `/health` is not routed in the hosted stack** — the container healthcheck depends on a path the edge does not expose.
- `logging_config.py` provides structured logging; `error_alerts.py` records an in-memory 5xx rate with a breach threshold and `/api/monitoring/error-alerts` exposes it.
- Audit: `foundation/audit` append-only with driver scoping; every durable-job transition and every authorization denial is audited (`foundation/app.py:51-89`).
- **Gap:** the error tracker is **in-memory** — restart loses the window. `MONITORING_SETUP.md` states delivery wiring is operator-side and not done.

### 2.7 Fake success responses / swallowed errors (material)
| Location | Effect |
|---|---|
| `noncreative_reads.py:32` (`_rows`) | Any SQL failure → `return []` → "0 rows" indistinguishable from genuinely empty |
| `noncreative_reads.py:41` (`_scalar`) | Same → `None`; downstream `evidence or 0` masks it |
| `main.py:907-916` | `/api/v1/status`: warehouse failure → `live_rows=fresh_rows=pulls=0`, mode `"demo"`; readiness failure → `ready:false, services:{}` with no reason |
| `main.py:744-745` | `/api/v1/models`: Ollama probe failure → `installed=[]` |
| `adapters/registry.py:14,20,26,32,38,44` | 6× `except ImportError: pass` — adapters silently absent from the registry |
| `adapters/__init__.py:13` | `except ImportError: pass` around `from . import registry` |
| `listing_forge.py:440-441` | `_call_llm` swallows everything → `[]`, silently falls back to templates |
| `social_pulse.py:49-50,102-103` | brand-voice load and caption generation silently degrade to defaults/templates |
| `main.py:2336-2341, 2354-2358` | foundation/noncreative routers mounted defensively; a mount failure is **logged only** → routes silently 404 |
| `alpha_gate.py:100-101` | unparseable token → `None` → fails closed to "not_allowlisted" (correct, but no audit trail) |

Honest (log/raise/rollback) sites are the majority in `foundation/`, `db*.py`, `jobs_durable.py`, `billing/service.py`, `offer_enrichment.py` (typed failure classification: `auth_error`/`transport_error`/`malformed_response`/`no_data_found`).

---

## 3. Deployment / operations

### 3.1 P0-03: hosted and local serve different APIs
- `Dockerfile.api` → `CMD ["uvicorn","foundation.app:app",...]`. The comment admits it: *"Full legacy main:app is mounted in later phases."*
- `docker-compose.yml:50-62` `api` builds `Dockerfile.api` and does not override the command → the hosted stack serves **only** `foundation_router` + `/ui`.
- Consequence in hosted: **all** `main.py` routes 404 — `/api/v1/status`, `/health`, `/health/detailed`, `/api/sourcescout*`, `/api/products/finder`, `/api/autothink/*`, `/api/golden-goose/*`, `/api/v1/reasoning/*`, `/api/v1/noncreative/*`, `/api/monitoring/error-alerts`.
- That means the hosted stack breaks: Command Center, SourceScout, Golden Goose, Profitability (foundation economics survives), Monitoring, AutothinK (all lanes), Listing Guardian, Competitor Monitor, Commerce Ops, Keyword Tracker, Spreadsheet Lab, Memory Bank, Shared Data, Master Brain, Provider Adapters.
- `docker-compose.local.yml` overrides the command to `main:app`, so **local dev sees a different API surface than hosted** — the exact condition under which "it works on my machine" ships.
- `Caddyfile` proxies only `/api/*` and serves `/ui/*`; bare `/health` is not routed.

### 3.2 Other operational gaps
- **Root `.env` line 98 is unparseable by python-dotenv** (`could not parse statement starting at line 98`) — it is a URL containing a colon but no `#`. Silent partial-load of the authoritative env file.
- **Duplicate `.env` files** with disjoint key sets (root 53 keys incl. `OPENCODE_GO_API_KEY`, `OPENROUTER_API_KEY`, `OPENCODE_GO_ENABLED=1`; backend 37 keys incl. `SCANNER_LIVE_ALLOWED=1`, `DATAFORSEO_*`). `main.py` loads **neither** — it relies on process env, so the root `.env`'s `OPENCODE_GO_ENABLED=1` never reaches the app (verified: the running API reports `configured:false, enabled:false, armed:false`, while loading the file directly reports `armed:true`). Config intent and runtime state disagree, fail-silently.
- **`requirements.txt` (both) are unpinned** — no versions.
- **No `.nvmrc`** (only `engines.node >= 16`, Docker uses `node:20-alpine`; the machine runs v24.15.0).
- **`run-agent.bat` is broken** — it calls `npm run pipeline`, which does not exist.
- **No automated DB backup** — only a manual `backups/northstar.db.bak` copy; `ROLLBACK_DRILL` is git-only.
- **No dependency/security scanning** anywhere in the repo or CI.
- **`00_STATE.json` `test_baseline` is dated 2026-09-22** and records "GO-LIVE READY / harness FULLY GREEN (2420 backend passed, 0 known, 0 unexpected)" — contradicted by today's 9 failures.
- **Docs drift:** `docs/SERVICE_READINESS_MATRIX.md` and `docs/LOCAL_RUNBOOK.md:191` both still describe Command Center as sample data and Keyword Tracker as a "Concept shell (0 API references)"; both now have live reads. Both files are dirty in the working tree from another session.
- **`/reference` mount** serves the entire `docs/` directory as static files (`main.py:160-162`) — includes research markdown, and is not auth-gated.

---

## 4. Data

### 4.1 Two divergent data layers
- `Northstar_backend/data_layer.py`: Postgres-or-SQLite selector, but **the Postgres branch is dead** — `_init_sqlite()` runs unconditionally (`:55-56`); `_mode` is written but never used to connect. Consumed by `noncreative_reads.py`, `memory_bank.py`, `social_pulse.py`, `auth.py`.
- `foundation/db.py` (real SQLite, 59 tables, single spec generating both SQLite and Postgres DDL) and `foundation/db_postgres.py` (real psycopg v3, `dict_row`, `?`→`%s` translation) — selected by `DB_URL`/`FOUNDATION_DB_URL`. **Both `.env` files lack these**, so the foundation defaults to a **temp file** (`tempfile.mkstemp("ns_foundation_")`, `foundation/db.py:618-621`) — disposable by default.
- Consequence: local runs silently use two unrelated stores with different durability guarantees. Postgres migration was documented as validated only in ephemeral/staging reports; **no Postgres run was possible in this audit** (no `FOUNDATION_DB_URL`).

### 4.2 Migrations
- 12 forward + 6 rollback in `migrations_foundation/`; runner records `(filename, sha256)` in a ledger and **refuses on checksum drift** (`foundation_migrate.py:47-49`). This is correct behaviour.

### 4.3 Tenant isolation
- Foundation repos are org-scoped (golden-goose routes are org-scoped and verified persisted).
- **Gaps:** `/api/autothink/*` has no org scoping at all (single global history file); `data_layer.py`'s SQLite connection is process-wide and serialized by `self._lock` — fine locally, not multi-process.
- No raw-SQL string interpolation was found in the audited foundation/data paths (parameterized).
- One **protected-artifact drift** issue exists in test fixtures (`data/scanner-search-cache.json` is 194 B on disk, 76,668 B at HEAD, and the fixture demands 38,331 B — three mutually inconsistent states; see `TEST_RESULTS.md` §1).

---

## 5. Security and privacy (beyond §2.2)

- **Secret handling is compliant.** Adapters read presence only (`key_present()`), never log values; `provider-adapters` UI shows names only; reasoning status exposes `configured/enabled/armed` booleans. **No credential value was printed by this audit.**
- **Session lifecycle:** hosted uses HttpOnly cookie + CSRF double-submit (`foundation/api.js:41-63`). Logout route exists. Token refresh exists in the legacy stack.
- **Authorization denials are audited** server-side (`foundation/app.py:51-89`).
- **Cross-user/workspace:** foundation routes are org-scoped and fail 401; AutothinK is the exception (P0-04).
- **Prompt-injection posture:** `reasoning_tasks.py` instructs the model to treat spreadsheet content as untrusted data (`:302`) and to never invent product facts, with deterministic post-validation (length limits, prohibited-phrase scan, JSON shape). This is a genuinely strong design. The local lane (`llm_adapter.SYSTEM_PROMPT`) has an equivalent "never invent data points" rule but **no deterministic post-validation** and **no retrieval/grounding**.
- **`/reference` static mount** of the whole `docs/` tree is unauthenticated (noted §3.2).
- **Rate limiting:** in-memory token bucket, anonymous 30/min. `prod_posture_ok()` correctly refuses to boot when `NORTHSTAR_DISABLE_RATE_LIMIT=1` and `ENVIRONMENT=production`.

---

## 6. Live-call safety (the P0)

### 6.1 The rule
> "GET requests and ordinary page loads must make zero live provider calls." — `docs/northstar-phase1/00-owner-decisions.md` §5, §6.7–6.8.

### 6.2 What the code does (correctly)
`live_gate.live_enabled()` gates `amazon_search.search_kirkland_products` (:352), `offer_enrichment._enrichment_mode()`, `offer_enrichment.get_seller_offer_contract`, and `canopy_client.get_canopy_product` (:60). The gate is a strict boolean via `env_flags.env_flag`.

### 6.3 What the environment does (violates the rule)
`Northstar_backend/.env` contains **`SCANNER_LIVE_ALLOWED=1`**. `amazon_search.py:44` calls `load_dotenv()`, which resolves `Northstar_backend/.env` (the calling file's directory) and arms the gate.

Instrumented sweep of 33 GET endpoints (`evidence/live-call-attribution.txt`):

```
GET /api/kirkland/scanner  -> 19 NON-LOOPBACK CONNECTS to ['3.232.71.244']
GET /api/kirkland/discovery, /discovery/meta, /discovery/categories, /kirkland/live,
    /api/sourcescout, /api/sourcescout/summary, /api/products/finder,
    /api/v1/catalog/stocked, /api/golden-goose/health, /api/v1/status,
    /api/monitoring/error-alerts                     -> 0 outbound connects
```

`/api/kirkland/scanner` reached the live Bright Data search path (`amazon_search.py:356-370`) and returned HTTP 200 with products. **A plain GET performed paid provider traffic.**

### 6.4 Honest disclosure
This audit's own read-only sweep caused those 19 connections. The probe was stopped after one attribution run; no retry was attempted; no further provider-touching endpoint was called. This is recorded as an audit-side incident and as the evidence for P0-01.

### 6.5 Residual risk
- The Codebase's `sunrise` docstring in `amazon_search.py:338-343` states the containment boundary clearly; the environment simply overrode it.
- No automated guard prevents `SCANNER_LIVE_ALLOWED=1` in a dev/audit `.env`. A startup assertion (analogous to `assert_prod_posture()` for the rate limiter) is the natural control — **proposed, not implemented**.

---

## 7. Test-relevant technical findings (detail in `TEST_RESULTS.md`)

1. `foundation/tests/test_frontend_gate.py::test_v3_shell_invariants` fails: `assert 50 == 48` — the App route table grew (now 51) and the frozen assertion was not updated. Either the assertion or the route table is canonical; this must be decided, not asserted-passed.
2. `tests/test_reasoning_routes.py` — 2 failures caused by **cross-module env pollution**: `test_provider_seller_probe.py:50` calls `load_dotenv(<root>/.env)` at import, putting the real `OPENCODE_GO_API_KEY` into `os.environ`; `test_reasoning_routes.py:21` uses `setdefault`, which is then a no-op, so the "configured" assertion fails. Reproducible with `python -m pytest test_provider_seller_probe.py tests/test_reasoning_routes.py`.
3. `test_proof_batch*.py` — 3 protected-hash failures on `data/scanner-search-cache.json` (disk 194 B ≠ HEAD 76,668 B ≠ fixture 38,331 B).
4. `test_env_hygiene.py::test_env_example_tracked_but_is_placeholder` — `.env.example` contains the literal `"Bearer "` (a documented auth-header example), which the placeholder scan rejects.
5. `test_owner_test_mode_non_bypass.py::test_frozen_file_boundary_is_a_static_rule` — path double-prefixed (`Northstar_backend/Northstar_backend/...`); the file is untracked.
6. `foundation/tests/test_jobs_durable_lifecycle.py::test_cancel_leased_job_cooperative` — unhandled thread exception, `JobStateError: illegal transition cancel_requested -> running`.
7. Node: `verify-smoke.cjs` — 40 passed / **1 failed**: deep link `/commerce-ops/CO-01` marker "Sourcing Validation" not found.
8. `verify-live-signin.cjs` — **BLOCKED** (needs `NS_TEST_EMAIL` / `NS_TEST_PASSWORD`; fails closed by design).
9. `verify-admin.cjs` — 33 passed vs a recorded 34 (one assertion retired).

---

## 8. Verdict

**All required non-creative work complete? — NO.**

Verified working: build, foundation durable jobs/audit/approvals, canonical economics, Golden Goose persistence, env-var hygiene discipline, provider fail-closed logic, honest-state UI patterns, and the live-gate *code*.

Blocked by: **5 P0 defects** (live-call leak on GET, hosted-reasoning route breakage, hosted/local API divergence, unauthenticated AutothinK routes, concurrent modification), **19 P1** items (silent error swallowing, silent adapter loss, ephemeral JWT secret, dead data-layer branch, no worker health, lint not running, `.env` corruption, stale baselines/docs), and the fact that two spec'd services are not implemented at all.
