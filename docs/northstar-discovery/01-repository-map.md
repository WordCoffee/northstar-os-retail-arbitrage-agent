# 01 — Repository Map

Evidence states: STATICALLY_CONFIRMED unless noted. Paths relative to repo root `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`.

## 1. Top-level layout

| Path | Purpose | Notes |
|---|---|---|
| `Northstar_backend/` | FastAPI backend (primary app `main.py`) | ~200 `.py` modules; static/, data/, agents/ subpackages |
| `northstar-os-ui/` | React + Vite SPA ("SIGNAL" design), dev on :8101 | separate package.json; proxies to :8000 |
| `autothink/` | AutothinK brain (own FastAPI app `backend/server.py` on :8100 + single-file UI `ui/index.html`) | mounted by main.py at `/autothink` |
| `public/` + `functions/` | Cloudflare Pages static dashboard + Pages Functions | `wrangler.toml` build output |
| `data/` | Root data artifacts: costco catalogs, caches, Node pipeline outputs | mixed: caches + imported + computed |
| `docs/` | Documentation; `docs/OPERATING_CONSTITUTION.md`, `docs/PRODUCTION_BLUEPRINT.md` | served read-only at `/reference` |
| `master-brain/` | Platform brain: README, master plan, profiles, service-plans | specs + profile registry |
| `shared/` | Shared config: plans, caps, model suite, design tokens, master-brain packs | single-source config |
| `scripts/` | PS/Node ops tooling (launch, test runner, rollback drill) | — |
| `migrations/` | 3 PostgreSQL/Supabase SQL migrations | NOT APPLIED |
| `tests/` | Only `tests/BASELINE.json` (runner canary) | — |
| `config/` | `provider_config.example.json` only | — |
| `learning/` | `schema.json` only (L0–L3 loop schema) | experience/playbooks files created on demand |
| `components/` | Voice widgets (voice-conversation.js, chat-voice.js, universal-voice.js) | not a frontend |
| `src/` | Legacy Node pipeline (scrapers/normalizers/analyzers/pipelines) + dead prototype web layer | superseded |
| `tools/` | Helper scripts (test_endpoints.py, test_chrome.py, generate_images.py) | some contain hardcoded test credentials (see `12`) |
| Root HTML files | `index.html`, `northstar.html`, `golden-goose.html`, `kirkland-data-console.html`, `voice-test.html`, `chat-voice-test.html` | legacy/dev; not FastAPI-routed except where noted |
| `Northstar_backend_audit_export/` | Code snapshot export of backend sources | gitignored artifact |

## 2. Backend boundary (`Northstar_backend/`)

| Subdir/File | Purpose |
|---|---|
| `main.py` (2,220+ lines) | FastAPI app, 69 route decorators, middleware, static mounts, lifespan |
| `agents/golden_goose_finder/` | Golden Goose pipeline package (router `main.py:1057` prefix `/api/golden-goose`), 7 routes |
| `static/` | `northstar-os/` (Analyst's Desk SPA), `landing/`, `auth/`, `index.html` (workbench) |
| `data/` | `northstar.db`, caches, catalogs, run evidence, benchmarks |
| `adapters/` | **ORPHANED** — 7 files (amazon_api, base, brightdata, easy_parser, firecrawl, open_web_ninja, registry, scrape_do) |
| `importers/` | **ORPHANED** — 7 files (sp_api, ads_api, search_term, brand_analytics, advigator, costco, tryholo) |
| `ops/`, `tasks/`, `analysis/`, `scrapers/` | schemas, offline task modules, supplier analysis, supplier discovery |
| ~45 provider/service modules at package root | see `06` |

## 3. Duplicate implementations (STATICALLY_CONFIRMED)

1. **Costco clients (5):** `costco_client.py` (CSV), `costco_api_client.py` (canonical 3-layer), `costco_live_runner.py` (gated live detail), `costco_browser_scraper.py` (orphaned), `costco_playwright_scraper.py` (orphaned).
2. **Bright Data (3):** `bright_data_client.py` (Web Unlocker, primary), `brightdata_client.py` (legacy dataset API), `adapters/brightdata.py` (orphaned).
3. **Costco detail adapters (2 parallel):** `bright_data_costco.py` and `firecrawl_costco.py` share a normalized record contract.
4. **Firecrawl (3):** `firecrawl_amazon.py`, `firecrawl_costco.py`, `adapters/firecrawl.py` (orphaned).
5. **EasyParser (3):** `easyparser_client.py` (used), `easyparser_seller_enrich.py` (orphaned CLI), `adapters/easy_parser.py` (orphaned).
6. **Amazon search scanners:** `amazon_search.py` dispatches bright_data/scavio/chocodata; orphaned: `scrapedo_amazon.py`, `firecrawl_amazon.py`, `browserbase_amazon.py`.
7. **RapidAPI (multiple):** `rapidapi_client.py` (used), `rapidapi_router.py` (6-host pool), plus probes (`probe_*.py`, `capture_real_time.py`, `run_3asin_realtime.py`).
8. **Enrichment orchestrators (7+ overlapping CLIs):** `enrich_cached_asins.py`, `enrich_manifest_run.py`, `enrich_seller_data.py`, `easyparser_seller_enrich.py`, `brightdata_enrich_compliant.py`, `rerun_enrichment_v2.py`, `run_enrichment_pipeline.py`.
9. **Provider waterfall executors:** `provider_waterfall_router.py`, `waterfall_run.py`, `validation_run.py`, `pipeline_dry_run.py`, `proof_batch_run.py`.
10. **Break-even ACoS formula duplicated:** backend `ad_pilot.py:327-355`, `word_coffee.py:47-66`, and frontend `northstar-os-ui/src/pages/Auctioneer.jsx:15-16`.

## 4. Dead / orphaned / unused (STATICALLY_CONFIRMED)

- `adapters/` package — no application importer (grep `import adapters` → no match).
- `importers/` package — only reachable through orphaned `adapters/amazon_api.py`.
- `costco_browser_scraper.py`, `costco_playwright_scraper.py` — doc-only.
- `scrapedo_amazon.py`, `firecrawl_amazon.py`, `browserbase_amazon.py` — only via orphaned `enrich_seller_data.py`.
- `verified_matches.py` — hardcoded module-level list, no function.
- `src/tests/navigation-test.js` — broken (undefined `navigationService`), wired to root `npm test`.
- Root `index.html` + `src/components/Layout/` + `src/services/NavigationService.js` — legacy prototype (superseded).
- `northstar.html`, `golden-goose.html` (root), `voice-test.html`, `chat-voice-test.html` — legacy/dev.
- `data/costco-costs.json` — misnamed; actually a Node.js script reading `PILOTERR_API_KEY`.

## 5. Conflicting sources of truth

| Concern | Conflict |
|---|---|
| Product records | `products` table vs `scanner-search-cache*.json` vs `sourcescout_manifest.json` vs GG report JSONs (see `08`) |
| Plan catalog | `shared/subscription-plans.json` canonical; mirrored in `static/northstar-os/js/demo-data.js:295` and `shared/gg-entitlements.json` |
| ACoS formula | three implementations (backend ad_pilot, word_coffee, frontend Auctioneer) |
| DB schema | `data_layer.py` SQLite schema vs `migrations/*.sql` (Postgres) vs `ops/schema.sql` vs `views.sql` — four schema descriptions |
| Frontend | four surfaces with no single source for service screens |

## 6. Oversized files (STATICALLY CONFIRMED, byte sizes)

| File | Bytes |
|---|---|
| `Northstar_backend/static/index.html` (workbench) | 735,352 |
| `Northstar_backend/main.py` | ~85 KB (2,220+ lines) |
| `Northstar_backend/costco_api_client.py` | ~2,073 lines |
| `Northstar_backend/dataforseo_adapter.py` | ~1,453 lines |
| `Northstar_backend/data_layer.py` | ~1,257 lines |
| `Northstar_backend/static/northstar-os/index.html` | 67,258 |
| `autothink/ui/index.html` | 868 lines single-file |
| `scanner.json` (root) | 1.38 MB artifact |
| `data/costco-discovery-catalog.json` | 979 KB (800 records) |

## 7. Files dangerous to modify / must-split during rebuild

- **Dangerous:** `Northstar_backend/main.py` (monolithic app: routes, models, middleware, static mounts, auth wiring all in one file); `data_layer.py` (single DAO file for 16 tables); `fee_engine.py` + `amazon_us_fee_rules_2026.py` (financial correctness, protected by `fixtures/protected_hashes.json`); `fixtures/protected_hashes.json`, `data/benchmarks/*` (protected fixtures); `shared/*.json` (single-source config, many consumers).
- **Split during rebuild:** `main.py` → routers/app factory/middleware; `data_layer.py` → per-domain repositories; `static/index.html` workbench (735 KB) → component tree; `autothink/ui/index.html` → componentized UI.

## 8. Circular dependencies / import risk

- No confirmed import cycles found; the main risk is the monolithic `main.py` importing ~20 modules at module scope and `_autothink_server()` dynamic import (`main.py:1004-1011`).

## 9. Counting methods for this map

- File counts and byte sizes: `Get-ChildItem` / `Get-Item .Length` (PowerShell), commands recorded in `17-evidence-index.md` §E.
- Orphan detection: grep for `import adapters`, `import importers`, and per-file importer scans (see `06`/`17`).
