# 02 — Runtime and Deployment

Evidence states: STATICALLY_CONFIRMED unless noted.

## 1. Application entry points

| Entry point | File | How it runs |
|---|---|---|
| FastAPI backend | `Northstar_backend/main.py:127` `app = FastAPI(...)` | `python -m uvicorn main:app --host 0.0.0.0 --port 8000` |
| AutothinK brain app | `autothink/backend/server.py:176-179` | `uvicorn.run(app, host="127.0.0.1", port=8100)` |
| React SPA (dev) | `northstar-os-ui` (Vite) | `npm run dev` → port 8101 (package.json:8) |
| Legacy Express | `server.js` (root) | `node server.js` → port 8000 (legacy, conflicts with FastAPI on same port) |

## 2. Launchers

| Launcher | File | Starts |
|---|---|---|
| `launch-all.ps1` | repo root | AutothinK :8100 + Northstar :8000; opens `http://127.0.0.1:8000/static/northstar-os/index.html` |
| `START-NORTHSTAR-ALPHA.bat` | repo root | wraps `scripts/launch_alpha.ps1` (Cloudflare tunnel + Ollama + backend + AutothinK) |
| `launch_offline_server.py` | `Northstar_backend/` | forces offline env then uvicorn :8000 |
| `refresh-costco-catalog.ps1` | `Northstar_backend/` | Windows Scheduled Task `NorthstarCostcoCatalogRefresh`, weekly Sun 03:00 |

## 3. Deployment config

| Config | File | Notes |
|---|---|---|
| Dockerfile | `Northstar_backend/Dockerfile` | `CMD uvicorn main:app ... --port 8000`; default env `SCANNER_LIVE_ALLOWED=false`, `DATAFORSEO_ENABLED=false` |
| docker-compose | `docker-compose.yml` | 6 services: ollama (11434), autothink (8100), northstar (8000), postgres (5432), redis (6379), n8n (5678) |
| Procfile | `Procfile` | `web: cd Northstar_backend && uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Cloudflare Pages | `wrangler.toml` | `pages_build_output_dir="public"`, KV `DEALS_KV`; `functions/api/*` |
| `.env` | root (untouched) | loaded via python-dotenv at module import in provider modules |

## 4. FastAPI app details (STATICALLY_CONFIRMED)

- `main.py:127-138` — title "Northstar OS API", docs at `/docs`, OpenAPI at `/openapi.json`.
- `main.py:90-124` — lifespan: `assert_prod_posture()` (rate-limiter production guard), `data_layer.get_database()`, Ollama `/api/tags` ping.
- Middleware order (`main.py:199-237`): SecurityHeaders → RequestTracing → RateLimit (60s token bucket, plan limits 30/60/120/300) → BffEnvelope (wraps legacy JSON in `bff/v1`) → error-rate tracker → CORS (`CORS_ORIGINS` env, default `localhost:8000,localhost:3000`) → AlphaGate (outermost).
- Static mounts: `/static` (main.py:140), `/autothink` → repo `autothink/` (148-150), `/reference` → `docs/` (153-155), `/northstar-os` → `static/northstar-os` html=True (184-188), `/golden-goose/static` (244-250).
- Root `/` → landing page, or 307 → `/northstar-os/` when `NORTHSTAR_ROOT_TO_APP=1` or private-alpha on (main.py:158-170).

## 5. Background jobs / schedulers (STATICALLY_CONFIRMED)

- **No in-process scheduler** (no APScheduler/celery/asyncio background tasks found).
- Only external scheduled task: Windows Task Scheduler weekly Costco catalog refresh.
- `tasks/` modules are offline-capable task runners (brand_blacklist_updater behind `BRAND_RECHECK_LIVE_OPERATOR_APPROVED=1`, supplier_pipeline), not schedulers.
- Concurrency: provider runners use `asyncio.to_thread` (rapidapi_router.py:358), GG pipeline uses `asyncio.run` in CLI.

## 6. Frontend serve paths (see also `03`)

| Surface | Serve path | Backend connectivity |
|---|---|---|
| Analyst's Desk SPA | FastAPI `/northstar-os` (html=True); launcher URL `http://127.0.0.1:8000/static/northstar-os/index.html` | Zero network by design; only `/api/v1/status` + `/api/v1/models` (live-status.js:44, brain.js:115) |
| React SPA (northstar-os-ui) | Vite dev/preview :8101 (not served by FastAPI) | Vite proxy `/api`, `/health`, `/autothink`, `/legal` → :8000 (vite.config.js:10-28) |
| Workbench | FastAPI `/workbench` (main.py:191-194) | `/api/kirkland/scanner`, `/api/kirkland/refresh`, `/api/golden-goose/opportunities`, `/api/products/{asin}/offers` |
| AutothinK UI | FastAPI `/autothink` mount + standalone :8100 | `/api/autothink/models`, `/api/autothink/run`, `/api/autothink/history` |
| Cloudflare Pages | `public/` via wrangler | Pages Functions `/api/latest-deals` etc. |

## 7. Observed runtime facts (this audit, RUNTIME_CONFIRMED)

- `GET http://127.0.0.1:8000/health` → `{"status":"ok","service":"northstar-backend","version":"1.0.0"}`.
- `GET http://127.0.0.1:8000/api/sourcescout/summary` → `{"total":470,"pass":245,"fail":20,"review":205,...}`.
- `GET http://127.0.0.1:8000/api/v1/models` → contract `bff/v1`, providers local/cloud, local installed models `qwen3:4b`, `northstar-qwen3:rev1`, `qwen3:14b`, `qwen2.5vl:7b`; `cloud.key_present=true`, `cloud.live_armed=false`.
- `POST http://127.0.0.1:8000/api/autothink/run` (local, T2) → generated content, model `northstar-qwen3:rev1`, `elapsed_ms≈10,738`, tokens (prompt 134 / completion 555). Evidence §R1 in `17`.
- `GET http://127.0.0.1:8000/api/kirkland/scanner` → 45 products with full economics (STATICALLY + RUNTIME_CONFIRMED response shape; returns within ~seconds).
- `GET http://127.0.0.1:8000/api/v1/credits/me` → `balance 5000, allotment 5000, consumed 0`.

## 8. Ports in use (observed this session, RUNTIME_CONFIRMED)

| Port | Owner |
|---|---|
| 8000 | FastAPI backend (python PID 39468 at session start) |
| 8100 | unrelated python process (avoided) |
| 8101 | Vite dev server for northstar-os-ui (started in a prior session) |

## 9. Counting methods

- Route counts: grep `@app.(get|post|put|delete|patch)` on `main.py` (69) and `autothink/backend/server.py` (5); `@router.*` on GG `main.py` (7). Commands in `17` §E.
