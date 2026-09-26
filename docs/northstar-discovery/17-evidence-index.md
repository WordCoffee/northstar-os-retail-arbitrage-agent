# 17 — Evidence Index

Central citation index. Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNKNOWN (K).

## §R — Runtime-confirmed evidence (this audit)

| ID | Command / action | Result | Route/model/artifact | Date |
|---|---|---|---|---|
| R1 | `POST http://127.0.0.1:8000/api/autothink/run` body `{query:"Write a 60-word Amazon listing bullet set…", provider:"local", tier:"T2"}` | Generated content returned; `model: northstar-qwen3:rev1`, `elapsed_ms≈10,738`, `tokens{prompt:134,completion:555}`, `ok:true` | `/api/autothink/run` (main.py:1025) → `autothink/backend/server.py` | 2026-09-23 |
| R2 | `GET http://127.0.0.1:8000/health` | `{"status":"ok","service":"northstar-backend","version":"1.0.0"}` | `/health` (main.py:747) | 2026-09-23 |
| R3 | `GET http://127.0.0.1:8000/api/sourcescout/summary` | `{"total":470,"pass":245,"fail":20,"review":205}` | `/api/sourcescout/summary` (main.py:1585) | 2026-09-23 |
| R4 | `GET http://127.0.0.1:8000/api/v1/models` | `bff/v1` envelope; local installed `qwen3:4b, northstar-qwen3:rev1, qwen3:14b, qwen2.5vl:7b`; `cloud.key_present=true`, `cloud.live_armed=false` | `/api/v1/models` (main.py:753) | 2026-09-23 |
| R5 | `GET http://127.0.0.1:8000/api/kirkland/scanner` | 45 products with full economics (e.g., Minoxidil $53.99 / $19.79 / ROI 87.52 / score 87) | `/api/kirkland/scanner` (main.py:1117) | 2026-09-23 |
| R6 | `GET http://127.0.0.1:8000/api/v1/credits/me` | `balance 5000, allotment 5000, consumed 0, plan foundation` | `/api/v1/credits/me` (main.py:1694) | 2026-09-23 |
| R7 | Browser session on `northstar-os-ui` (Vite :8101 proxy) | Rendered live Prospector table (42 rows), real generated OfferChisel listing, real Town Crier caption, AutothinK run result | Vite proxy `vite.config.js:10-28` → :8000 | 2026-09-23 |

**Scope note:** R1/R7 validate the local-engine and SPA-proxy paths. They do NOT validate Golden Goose live scans, Ads API, supplier live discovery, Unwrangle, or any paid provider.

## §E — Counting commands (evidence for numeric claims)

| Claim | Count | Command | Paths included | Excluded | Method |
|---|---|---|---|---|---|
| main.py routes | 69 | `Select-String -Path Northstar_backend\main.py -Pattern '@app\.(get|post|put|delete|patch)'` | main.py | — | decorator grep |
| GG router routes | 7 | `Select-String -Path Northstar_backend\agents\golden_goose_finder\main.py -Pattern '@router\.(get|post|put|delete|patch)'` | GG main.py | — | decorator grep |
| AutothinK routes | 5 | same pattern on `autothink\backend\server.py` | server.py | — | decorator grep |
| Backend test files / fns | 124 / 2,368 | recursive `Select-String '^\s*def test_'` over `Northstar_backend\test_*.py` | Northstar_backend (incl. agents) | autothink | per-file count |
| Autothink test fns | 3 / 25 | same over `autothink\tests\test_*.py` | autothink/tests | — | per-file count |
| JS asserts | 1,396 | `Select-String 'assert\('` over 4 files (296+1052+23+25) | test_shell.cjs, test_ui_display.cjs, test_functions_contract.cjs, test_ui_autothink.cjs | — | per-file count |
| Workbench size | 735,352 B | `Get-Item Northstar_backend\static\index.html .Length` | — | — | file stat |
| DB tables/rows | 16 tables / 1,024 products | read-only sqlite (`mode=ro`) `SELECT COUNT(*)`, `PRAGMA table_info(products)` | northstar.db | sqlite_sequence | read-only query |
| Provider rows | 31 | module enumeration + registry read | provider modules + GG free_tier_registry | — | source inventory |
| Frontend surfaces | 4 | enumeration of Analyst's Desk / northstar-os-ui / workbench / autothink UI | — | Cloudflare Pages counted separately | source inventory |
| Fees/formula locations | — | grep for function defs | fee_engine.py, fee_calculator.py, ad_pilot.py, word_coffee.py, Auctioneer.jsx | — | source grep |

**Database counts were obtained from the ACTIVE database (read-only `mode=ro`), NOT from a copy. No writes occurred.**
**Generated artifacts excluded from counts: `dist/`, `node_modules/`, gitignored `data/snapshots`, `data/scored`, `data/normalized`, `Northstar_backend_audit_export/`, `.playwright-mcp/`.**

## §F — Historical evidence (labeled, not current)

| ID | Artifact | Meaning |
|---|---|---|
| H1 | `tests/BASELINE.json` | Prior green baseline (backend 2,425 pass / 3 skip / 48 subtests; GG 511; shell 307; UI display 1,122; functions 31) — HISTORICAL, current status UNVERIFIED |
| H2 | `00_STATE.json` known_issues | e.g., `unwrangle_amazon_detail_403_quota_rejection` (Unwrangle 403) — HISTORICALLY_FAILED 2026-09-13; CURRENTLY_UNVERIFIED |
| H3 | `00_STATE.json:761,765,767,773,785,791` | Approved live Bright Data / Costco runs (Bright Data ACTIVE_HISTORICALLY_RECORDED) |
| H4 | `shared/master-brain/standing-approvals.json` | `easyparser_brightdata_backfill_20260913` active (EASYPARSER 174 + BD 45, budget 189) |
| H5 | `00_STATE.json:161-166` | Open issue `credential_exposure_in_test_failure_diff` (DataForSEO import-time credential capture) |
| H6 | `data/enrich/easyparser-runs/`, `data/costco-discovery-runs/` | Approved live-run evidence artifacts (dated 2026-08..09) |

## §S — Key static citations (files of record)

- Backend app: `Northstar_backend/main.py` (app :127, lifespan :90-124, middleware :199-237, routes table in `03`).
- Data layer: `data_layer.py` (SQLite path :35, schema :74-350, DAOs :414-1257).
- Auth: `auth.py` (:31-34 JWT, :88-96 roles, :151-158 bcrypt), `auth_deps.py` (:28, :31-83, :86-136), `alpha_gate.py`, `rate_limiter.py`.
- Fees: `fee_engine.py` (:180 referral, :263 FBA, :406 unit economics), `amazon_us_fee_rules_2026.py`, `fee_calculator.py`, `finance.py`, `unit_economics.py`, `cost_model.py`.
- Golden Goose: `agents/golden_goose_finder/main.py` (router :1057, mock :499, live :424, gates :1188-1198), `opportunity_scorer.py` (weights :127-136), `breakdown_economics.py`, `live_scan_gate.py`.
- Master Brain: `master_brain_gateway.py`, `master_brain_learning.py`, `master_brain_profiles.py`, `master_brain_subscribers.py`, `memory_bank.py`, `model_router.py`.
- AutothinK: `autothink/backend/server.py`, `llm_adapter.py`, `orchestration/router.py`, `memory/session_store.py`.
- Frontends: `static/northstar-os/engine.js` (router :86-112, zero-network :5), `northstar-os-ui/src/App.jsx` (routes :47-62), `static/index.html` (workbench), `autothink/ui/index.html`.
- Shared config: `shared/subscription-plans.json`, `usage-caps.json`, `model-suite.json`, `data-requirements.json`, `gg-entitlements.json`, `design-tokens.json`.
- Protected: `fixtures/protected_hashes.json`, `data/benchmarks/`.

## §G — Omitted / withheld

- Tests: NOT executed (see `10`). Sanctioned command documented, requires separate approval.
- Providers: no paid/cloud/external calls made; the ONLY model execution was a **local Ollama** call (§R1), disclosed fully below. Validation methods documented in `06`.
- `.env`: never read; env names only.
- Git: `git status --short` and `git ls-files docs/northstar-discovery` WERE executed (read-only) during package validation. `git diff`, `git diff --stat`, `git log`, and any `git add`/`git commit` were NOT executed.

## §R1 — Ollama runtime execution disclosure (local, not external)

The only model execution in this audit was a **local** Ollama call. It was performed **during this audit session** (2026-09-23) as evidence R1:

- **Command (equivalent):** `POST http://127.0.0.1:8000/api/autothink/run` with body `{"query":"Write a 60-word Amazon listing bullet set for Kirkland Signature whole bean coffee, dark roast 2.5lb. Tone: bold, clear, premium.","provider":"local","tier":"T2"}` (issued via PowerShell `Invoke-RestMethod`).
- **Route:** `/api/autothink/run` (`main.py:1025`), delegated to `autothink/backend/server.py` via `_autothink_server()`.
- **Model:** `northstar-qwen3:rev1` (local Ollama), resolved by `model_router.resolve("local","T2")`.
- **Timestamp:** 2026-09-23 (session date).
- **Output evidence:** `ok:true`, `model:"northstar-qwen3:rev1"`, `elapsed_ms≈10,738`, `tokens{prompt:134, completion:555}`, generated bullet set text (60 words). Full response observed in terminal during this session.
- **External service consumed?** NO. Local Ollama instance only; no cloud/paid provider, no quota consumption, no network egress to a third party. It is disclosed because the constitution requires accurate disclosure of ANY execution; local model execution is not a paid provider call but is recorded here for completeness.
- **Explicitly NOT validated this audit:** cloud provider calls (OpenRouter `live_armed=false` observed), any live enrichment provider, or any write path.
