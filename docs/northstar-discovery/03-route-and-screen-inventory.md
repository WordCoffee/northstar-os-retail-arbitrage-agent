# 03 — Route and Screen Inventory

Evidence states: STATICALLY_CONFIRMED unless noted. Four frontend surfaces audited.

## 1. Frontend surface definitions

| Surface | Path | Build status | Serve path | Route ownership | Backend connectivity | Reachable from launcher | Classification | Data source |
|---|---|---|---|---|---|---|---|---|
| Analyst's Desk SPA | `Northstar_backend/static/northstar-os/` | Static, no build step | FastAPI `/northstar-os` (html=True) | Hand-rolled hash router `engine.js:86` | Zero network by design (`engine.js:5`); only `/api/v1/status`, `/api/v1/models` | Yes (launch-all.ps1) | Primary legacy; offline-fixture shell | `demo-data.js` fixtures |
| React/Vite SPA | `northstar-os-ui/` | Vite build (dist/) | Dev/preview :8101 (not served by FastAPI) | react-router HashRouter `App.jsx:47-62` | Vite proxy `/api` → :8000 | No (manual `npm run dev`) | Experimental/parallel | Live backend via proxy |
| Workbench | `Northstar_backend/static/index.html` | Static, single file (735,352 B) | FastAPI `/workbench` (main.py:191-194) | `data-view` pills in-file | `/api/kirkland/scanner`, `/api/kirkland/refresh`, `/api/golden-goose/opportunities`, `/api/products/{asin}/offers` | Not by default launcher | Legacy power-tool | Live backend + fixtures |
| AutothinK UI | `autothink/ui/index.html` | Static, single file (868 lines) | FastAPI `/autothink` mount + standalone :8100 | Single page (no router) | `/api/autothink/*` | Yes (launch-all.ps1 starts :8100) | Primary AutothinK surface | Live engine |
| Cloudflare Pages | `public/` + `functions/` | wrangler build | Pages deployment | static + Functions routes | `/api/latest-deals` etc. via KV | Independent | Legacy static dashboard | KV + JSON |

**Analyst's Desk "zero network" intent:** evidenced by (a) explicit source comment `engine.js:5` "Zero network calls by design"; (b) all service data from `demo-data.js` fixtures; (c) shell contract test `test_shell.cjs:176-181` asserts no fetch/XHR. Classification is **offline-fixture demo shell (legacy primary implementation)** — the real API surface lives behind the FastAPI routes, and the workbench + React SPA consume them. This is INFERRED as a temporary fixture mode rather than an explicit product requirement: the master plan and `docs/PRIVATE_ALPHA_DEPLOY.md` describe it as the alpha shell, while live capabilities exist behind the same app.

## 2. Backend route inventory (STATICALLY CONFIRMED)

### 2a. `main.py` — 69 route decorators

**Static/UI:** `GET /` (158), `GET /landing` (173), `GET /workbench` (191), `GET /golden-goose`, `GET /golden-goose/` (253-254).

**Kirkland scan/discovery:** `POST /api/kirkland/scan` (378), `GET /api/kirkland/live` (393), `POST /api/kirkland/refresh` (401), `GET /api/kirkland/scanner` (1117), `GET /api/kirkland/discovery` (1226), `POST /api/kirkland/discovery/run` (1333), `GET /api/kirkland/discovery/categories` (1351), `GET /api/kirkland/discovery/meta` (1382).

**Monitoring/health:** `GET /api/monitoring/error-alerts` (725), `GET /health` (747), `GET /health/detailed` (1045).

**Brain/models:** `GET /api/v1/models` (753).

**Memory/learning:** `POST /api/v1/memory/ingest` (829), `POST /api/v1/memory/search` (840), `POST /api/v1/learning/capture` (850), `POST /api/v1/learning/route` (862), `GET /api/v1/learning/playbooks` (875), `POST /api/v1/learning/distill` (885), `POST /api/v1/learning/unlearn` (893).

**Catalog/status:** `GET /api/v1/status` (920), `GET /api/v1/catalog/stocked` (946), `POST /api/v1/catalog/stock` (954), `GET /api/v1/catalog/pull` (968), `POST /api/v1/catalog/wholesale/stock` (975), `GET /api/v1/catalog/wholesale/products` (983).

**AutothinK:** `GET /api/autothink/models` (1014), `POST /api/autothink/run` (1025), `GET /api/autothink/history` (1038).

**Products/offers:** `GET /api/products/{asin}/canopy` (1392), `GET /api/products/{asin}/offers` (1410), `GET /api/products/finder` (2150).

**DataForSEO:** `POST /api/dataforseo/validate` (1453).

**Sourcescout:** `GET /api/sourcescout` (1502), `GET /api/sourcescout/matches` (1522), `GET /api/sourcescout/mismatches` (1543), `GET /api/sourcescout/review` (1564), `GET /api/sourcescout/summary` (1585).

**Auth:** `POST /api/v1/auth/register` (1607), `POST /api/v1/auth/login` (1632), `POST /api/v1/auth/refresh` (1645), `GET /api/v1/auth/me` (1655).

**Plans:** `GET /api/v1/plans` (1672), `GET /api/v1/plans/{plan_id}` (1846).

**Admin/credits:** `GET /api/v1/admin/accounts/{user_id}` (1679), `GET /api/v1/credits/me` (1694).

**Support:** `POST /api/v1/support/tickets` (1740), `GET /api/v1/support` (1754), `PATCH /api/v1/support/{ticket_id}` (1761).

**Invites:** `POST /api/v1/invites` (1783), `GET /api/v1/invites/{code}` (1796), `POST /api/v1/invites/redeem` (1806).

**Legal:** `GET /legal/{name}` (1831).

**Suppliers:** `GET /api/suppliers` (1894), `GET /api/suppliers/analytics` (1919), `GET /api/suppliers/analyses` (1938), `POST /api/suppliers/discover` (1950), `POST /api/suppliers/analyze` (1985), `POST /api/suppliers` (2002), `POST /api/suppliers/import-csv` (2012), `GET /api/suppliers/{sid}` (2044), `DELETE /api/suppliers/{sid}` (2069), `GET /api/suppliers/{sid}/products` (2079), `POST /api/suppliers/{sid}/products` (2089).

**Universal filter:** `POST /api/filters/universal/evaluate` (2122).

### 2b. Golden Goose router — 7 routes (`agents/golden_goose_finder/main.py`, prefix `/api/golden-goose`, mounted main.py:241)

`POST /scan-mock` (1151), `POST /scan` (1176), `GET /opportunities` (1227), `GET /categories` (1296), `GET /dry-run` (1309), `GET /entitlements` (1328), `GET /health` (1339).

### 2c. AutothinK app — 5 routes (`autothink/backend/server.py`)

`GET /` (71), `GET /health` (76), `GET /api/autothink/models` (81), `POST /api/autothink/run` (100), `GET /api/autothink/history` (165).

## 3. Screen inventory (frontend)

### Analyst's Desk SPA — 12 routes (`engine.js:86`)

| Route | Screen | Status | Data source |
|---|---|---|---|
| `hub` | Operations Hub | Functional shell | fixtures |
| `sourcescout` | Prospector (3 tabs: Product Finder / Golden Goose / Find a Supplier) | Functional shell | fixtures |
| `goldengoose` | Golden Goose | Functional shell | fixtures |
| `listingforge` | OfferChisel (7 sub-nav tabs) | Functional shell | fixtures |
| `adpilot` | The Auctioneer | Functional shell | fixtures |
| `socialpulse` | The Town Crier | Functional shell | fixtures |
| `autothink` | AutothinK workspace (iframe `../../autothink/ui/index.html`) | Functional (embeds real engine) | iframe |
| `theledger` | The Ledger (P&L) | Functional shell | fixtures |
| `thewatch` | The Watch | Skeleton | schema preview only |
| `rankledger` | RankLedger | Skeleton | schema preview only |
| `rivalboard` | The Rival Board | Skeleton | schema preview only |
| `account` | Account & Plans | Functional shell | fixtures |

### React/Vite SPA — 12 routes (`App.jsx:47-62`)

`/`+`/hub` Hub, `/ledger` Ledger, `/prospector` Prospector, `/goldengoose` GoldenGoose, `/offerchisel` OfferChisel, `/towncrier` TownCrier, `/auctioneer` Auctioneer, `/autothink` Autothink, `/thewatch` TheWatch, `/rankledger` RankLedger, `/rivalboard` RivalBoard, `/account` Account, `*` NotFound.

Page→API mapping (see `17` §E for the full table): Prospector/GoldenGoose/Watch/RankLedger/RivalBoard → `api.scanner()`; OfferChisel/TownCrier → `api.autothinkRun()`; Autothink → `models`+`history`+`run`; Hub → `summary`+`models`+`credits`; Ledger/Account → `credits`+`models`; Auctioneer → none (local calc).

### Workbench — views (`static/index.html`)

scout/calculator/profit/risk/cycle/portfolio + hidden v2 workspaces (goldengoose, sourcescout, listingforge, adpilot, socialpulse, autothink) via `data-view` pills (in-file, ~4774-4877).

### AutothinK UI — single screen

Composer + output panel + quick-ask buttons + widget + achievement system (localStorage `northstaractivity`).

## 4. Per-screen state (representative)

For each screen: state source = local fixtures (Analyst's Desk), per-page React `useState/useEffect` (SPA), or backend fetch (workbench). Loading states, empty states, and error states are implemented in the React SPA (`.toast`, loading text); Analyst's Desk has toasts + onboarding but errors are fixture-limited. Accessibility: Analyst's Desk uses aria labels/current/hidden and `aria-live` toasts (see `11`).

## 5. Counting methods

- Backend route counts: grep decorators (69 + 7 + 5). Commands in `17` §E.
- Frontend screens: enumerated from source (engine.js ROUTES, App.jsx Routes, workbench data-view pills, autothink UI).
