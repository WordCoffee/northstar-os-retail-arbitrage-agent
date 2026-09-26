# 06 — API / Provider Registry

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNKNOWN (K).

**No paid/cloud/external provider was invoked during this audit. The only model execution was a LOCAL Ollama call (evidence R1, disclosed in `17` §R1) — no external service, no quota consumption. Env values were not read — only names. Unwrangle is classified HISTORICALLY_FAILED (403 at 2026-09-13) and CURRENTLY_UNVERIFIED, not "dead".**

## Provider table

| # | Provider | Module | Purpose | Env var NAMES (redacted) | R/W | Rate/retry/timeout | Cache | Fallback | Gate | Cost tracking | Sandbox | Classification |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Bright Data Web Unlocker | `bright_data_client.py` | Amazon search + ASIN detail | BRIGHTDATA_UNLOCKER_API_KEY, BRIGHTDATA_UNLOCKER_ZONE, BRIGHTDATA_REQUEST_URL, BRIGHTDATA_REQUEST_TIMEOUT_SECONDS | R | 120s; 0 retries; in-mem 15-min TTL | in-memory | chocodata→scavio (caller) | SCANNER_LIVE_ALLOWED (caller) | request counter (credits_remaining=None) | none | ACTIVE_HISTORICALLY_RECORDED (H: runs in 00_STATE) |
| 2 | Bright Data legacy dataset | `brightdata_client.py` | offer data via dataset | BRIGHTDATA_API_KEY, BRIGHTDATA_DATASET_ID | R | — | — | — | none | — | — | DEPRECATED (S) |
| 3 | Bright Data Costco | `bright_data_costco.py` | Costco item detail (Unwrangle drop-in) | BRIGHTDATA_COSTCO_DETAIL_ENABLED, BRIGHTDATA_REQUEST_DELAY_SECONDS | R | 2.0s pacing; 0 retries; circuit breaker | — | firecrawl_costco | BRIGHTDATA_COSTCO_DETAIL_ENABLED=1 | 1 credit/req | — | ACTIVE_HISTORICALLY_RECORDED (H: runs) |
| 4 | Costco CSV | `costco_client.py` | local cost basis | COSTCO_CSV_PATH | R | offline | file | — | — | — | — | ACTIVE (S) |
| 5 | Costco catalog client | `costco_api_client.py` | Kirkland catalog (OpenWebNinja) | COSTCO_CATALOG_SOURCE, OPENWEBNINJA_API_KEY, COSTCO_CATALOG_MAX_PAGES, COSTCO_CATALOG_QUERY, COSTCO_CATALOG_SNAPSHOT_PATH, COSTCO_CATALOG_DETAIL_ENABLED, COSTCO_API_COST_BUFFER_PERCENT, COSTCO_FRESHNESS_THRESHOLD_DAYS, COSTCO_AMAZON_MAPPING_PATH, COSTCO_DELIVERY_ZIP, COSTCO_BUSINESS_CENTER | R | request delay; stop-on-block | JSONL archive | — | COSTCO_CATALOG_DETAIL_ENABLED=1 (layer2) | credits/page | — | ACTIVE (catalog, S); live layer CONFIGURED_UNVERIFIED |
| 6 | Costco live runner | `costco_live_runner.py` | provider failover detail | BRIGHTDATA_COSTCO_DETAIL_ENABLED, FIRECRAWL_COSTCO_DETAIL_ENABLED, FIRECRAWL_API_KEY | R | per-provider | — | BD→Firecrawl | per-provider gate | — | — | ACTIVE_HISTORICALLY_RECORDED (H) |
| 7 | OpenWebNinja | via costco_api_client + adapters/open_web_ninja.py (orphaned) | Costco search | OPENWEBNINJA_API_KEY | R | delay | — | — | COSTCO_CATALOG_SOURCE=OPENWEBNINJA | 10 credits/page | — | CONFIGURED_UNVERIFIED (default OFF) |
| 8 | Unwrangle | `offer_enrichment.py` (amazon_detail) | per-ASIN enrichment | UNWRANGLE_API_KEY, UNWRANGLE_URL | R | — | seller cache | — | SCANNER_OFFER_ENRICHMENT=UNWRANGLE | 1 credit/ASIN | — | **HISTORICALLY_FAILED (403, 2026-09-13) / CURRENTLY_UNVERIFIED** |
| 9 | DataForSEO | `dataforseo_adapter.py` | Amazon merchant validation | DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, DATAFORSEO_ENABLED, DATAFORSEO_TRANSPORT_ENABLED, DATAFORSEO_LABS_AUTO_SUBMIT, NORTHSTAR_ENV_PATH | R | 60s; 120s max poll; never auto-retry | budget ledger | — | dual flag+transport+creds | 1c canary→100c ceiling | — | ACTIVE_HISTORICALLY_RECORDED (adapter build H; no live spend) |
| 10 | EasyParser | `easyparser_client.py` | Amazon OFFER roster | EASYPARSER_API_KEY | R | 60s; 0 retries | seller cache | — | live_gate caller; token DEPRECATED | credits_used/remaining | — | ACTIVE_HISTORICALLY_RECORDED (H: backfill 2026-09-13 under standing approval) |
| 11 | Scavio | `scavio_client.py` | Amazon search | SCAVIO_API_KEY, SCAVIO_API_URL | R | 30s; 0 retries | — | — | SCANNER_SEARCH_FALLBACK | — | — | CONFIGURED_UNVERIFIED |
| 12 | Chocodata | in `amazon_search.py`/`offer_enrichment.py` | Amazon search + product | CHOCODATA_API_KEY, CHOCODATA_TIMEOUT, CHOCODATA_MAX_RETRIES, CHOCODATA_RETRY_SLEEP_SECONDS, CHOCODATA_SEARCH_URL, CHOCODATA_PRODUCT_URL | R | 502-retry x2, 8s | — | — | SCANNER_SEARCH_SOURCE/SCANNER_OFFER_ENRICHMENT | 5 credits/page | — | CONFIGURED_UNVERIFIED |
| 13 | Firecrawl (Costco) | `firecrawl_costco.py` | Costco detail | FIRECRAWL_API_KEY, FIRECRAWL_COSTCO_DETAIL_ENABLED, FIRECRAWL_COSTCO_REQUEST_URL/DELAY/TIMEOUT | R | 60s; 2.0s delay | — | — | FIRECRAWL_COSTCO_DETAIL_ENABLED=1 | free tier 1000 pages/mo | — | ACTIVE_HISTORICALLY_RECORDED (H) |
| 14 | Firecrawl (Amazon) | `firecrawl_amazon.py` | Amazon dp | FIRECRAWL_API_KEY, FIRECRAWL_AMAZON_DETAIL_ENABLED, FIRECRAWL_AMAZON_REQUEST_URL/DELAY/TIMEOUT | R | — | — | — | gate | — | — | CONFIGURED_UNVERIFIED |
| 15 | Browserbase | `browserbase_amazon.py` | Amazon dp (last-resort) | BROWSERBASE_API_KEY, BROWSERBASE_AMAZON_DETAIL_ENABLED, BROWSERBASE_AMAZON_REQUEST_URL/DELAY/TIMEOUT | R | 90s; 3.0s delay | — | — | gate | free 1000 calls | — | CONFIGURED_UNVERIFIED |
| 16 | scrape.do | `scrapedo_amazon.py` | Amazon dp | SCRAPE_DO_API_KEY, SCRAPEDO_AMAZON_DETAIL_ENABLED, SCRAPEDO_AMAZON_REQUEST_URL/DELAY/TIMEOUT | R | 90s; 2.0s delay | — | — | gate | — | — | CONFIGURED_UNVERIFIED |
| 17 | RapidAPI | `rapidapi_client.py`, `rapidapi_router.py` | amazon-product-data4 + 6-host pool | RAPIDAPI_KEY, RAPIDAPI_HOST, RAPIDAPI_HOST_BDC/REALTIME/AXESSO/PRICING/ONLINE/SCOUT, RAPIDAPI_PATH_*, RAPIDAPI_ASIN_FILE, RAPIDAPI_RESULTS_PATH, RAPIDAPI_NORMALIZED_PATH, RAPIDAPI_POOL_LIVE | R | drain-on-403/429; max 8 attempts/ASIN | files | — | RAPIDAPI_POOL_LIVE=1 | estimated 100c fallback | — | CONFIGURED_UNVERIFIED (module self-documents unverified paths) |
| 18 | Canopy | `canopy_client.py` | Amazon product detail | CANOPY_API_KEY | R | — | — | — | live_gate | — | — | CONFIGURED_UNVERIFIED |
| 19 | Amazon SP-API | `adapters/amazon_api.py`, `importers/sp_api_importer.py` | orders/inventory/fees | SP_API_REFRESH_TOKEN, SP_API_CLIENT_ID, SP_API_CLIENT_SECRET | R/W (unwired) | ~1 req/s doc | — | — | (orphaned) | — | — | REFERENCED_UNIMPLEMENTED (no route/runner) |
| 20 | Amazon Ads API | `importers/ads_api_importer.py` | campaigns/search terms | ADS_CLIENT_ID, ADS_CLIENT_SECRET, ADS_REFRESH_TOKEN | R/W (unwired) | — | — | — | (orphaned) | — | — | REFERENCED_UNIMPLEMENTED |
| 21 | Ollama (local) | `autothink/backend/llm_adapter.py`, `model_router.py` | local generation | OLLAMA_BASE_URL, OLLAMA_HOST, AUTOTHINK_NUM_PREDICT, AUTOTHINK_NUM_CTX | R | stream=True; no retry | — | — | default local | credit_weight (60 T2) | — | **RUNTIME_CONFIRMED local (this audit)** |
| 22 | OpenRouter (cloud) | `llm_adapter.py`, `model_router.py` | cloud generation | OPENROUTER_API_KEY, CLOUD_MODEL_LIVE, (legacy OPENAI_API_KEY) | R | — | — | — | CLOUD_MODEL_LIVE=1 | credit weight | — | CONFIGURED_UNVERIFIED (`live_armed=false` observed) |
| 23 | ComfyUI / HF / CF Workers AI | `tools/generate_images.py` | image gen | COMFYUI_URL, HF_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN | R | — | — | — | offline default | — | — | CONFIGURED_UNVERIFIED (standalone tool) |
| 24 | Google/Gemini | `tools/browser_agent.py` | browser agent driver | GOOGLE_API_KEY, GEMINI_API_KEY | — | — | — | — | presence-only | — | — | REFERENCED_UNIMPLEMENTED |
| 25 | Groq (voice) | `components/voice-conversation.js` | transcription | NS_GROQ_API_KEY, NS_VOICE_MODEL, NS_OLLAMA_ENDPOINT, NS_OLLAMA_MODEL | R | — | — | — | env-passed frontend | — | — | REFERENCED_UNIMPLEMENTED |
| 26 | Piloterr | `data/costco-costs.json` (script) | Costco costs | PILOTERR_API_KEY | R | — | — | — | none | — | — | REFERENCED_UNIMPLEMENTED (no gate/wiring) |
| 27-31 | GG free-tier registry | `agents/golden_goose_finder/free_tier_registry.py` | scrapingdog/scrapingbee/scrapebadger/amazonscraperapi/apiclaw + others | SCRAPINGDOG_API_KEY, SCRAPINGBEE_API_KEY, SCRAPEBADGER_API_KEY, AMAZONSCRAPERAPI_API_KEY, APICLAW_API_KEY (+ shared) | R | registry metadata | — | — | GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1 | ledger | — | CONFIGURED_UNVERIFIED (metadata-only) |

**Provider count: 31 rows catalogued above; ~20 distinct providers/integrations when counting the free-tier registry sub-entries as one group. The count used in this package = 31 registry rows (see §Counting).**

## Orphaned adapter/import layer

- `adapters/` (7 files: amazon_api, base, brightdata, easy_parser, firecrawl, open_web_ninja, registry, scrape_do) — NO application importer (S).
- `importers/` (7 files: sp_api, ads_api, search_term, brand_analytics, advigator, costco, tryholo) — only reachable via orphaned `adapters/amazon_api.py` (S).

## Credential-exposure risk

- No hardcoded credentials found in frontend JS (scan of `static/**`, `northstar-os-ui/src/**`, `src/**`, `public/**`, `components/**` → zero matches) (S).
- `tools/browser_agent.py` and `tools/test_chrome.py` contain hardcoded test credentials (email/password literals) — flagged in `12` and `13`.
- Open issue `credential_exposure_in_test_failure_diff` (`00_STATE.json:161-166`): DataForSEO captures credentials at import time; a unittest diff previously rendered real values; transport flag now false (H, OPEN).

## Safest later validation method (no calls made)

- Use each provider's gated, budgeted test harnesses (`--live --limit --max-requests --max-credits` CLIs; `POST /api/dataforseo/validate` with approval token) under an operator-approved §3 envelope. Do not probe from GET routes.
