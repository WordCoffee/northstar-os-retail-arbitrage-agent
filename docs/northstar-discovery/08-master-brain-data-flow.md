# 08 — Master Brain Data Flow

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I) / UNKNOWN (K).

## 1. Does a shared intelligence layer exist?

**Partially. The CONFIG layer is genuinely shared; the DATA layer is only partially shared.** The master plan's "one shared owned database" (`master-brain/northstar-os-master-plan.md:433-461`) is implemented only in part by `data_layer.py`.

### Genuinely shared (single source, multiple consumers) — S

1. Plan catalog / entitlements / usage caps / model suite / data requirements / GG entitlements (`shared/*.json`) → consumed by `auth.py:43`, `master_brain_subscribers.py:30`, `credit_ledger.py:25`, `cost_model.py:20`, `usage_meter.py:127`, `model_router.py:86-87`, `readiness.py:25`, `gg_entitlements.py:23`.
2. SQLite data layer (`data_layer.py`) — products, keywords, listings, campaigns, transactions, memory, suppliers, audit, live_pulls tables.
3. Supplier entity — `suppliers`/`supplier_products`/`supplier_cost_analysis` tables + `/api/suppliers*` routes.
4. Append-only audit — `shared/master-brain/audit.log.jsonl` (gateway), `audit_log` table, `live_pulls` table (three channels).
5. Memory Bank — `memory_entries` (22 rows); the only shared brand-voice store actually consumed by a service (`social_pulse.load_brand_voice`).

### Disconnected / duplicated (the core finding) — S

1. **No canonical product record.** Same ASIN can live in up to 4 stores with divergent freshness/fields.
2. Scanner/Prospector bypasses the `products` table entirely.
3. Golden Goose is a parallel product universe.
4. Keyword/SEO graph + campaign intelligence = schema-only (dormant).
5. Brand voice triplicated (memory_entries, profile markdown, SPA fixtures).
6. Embeddings/vector store = **MISSING** (no FAISS/chromadb/sentence-transformers; memory search is SQL `LIKE`, `memory_bank.py:59-78`).

## 2. The four ASIN stores — field-level comparison

| Dimension | `products` table | `scanner-search-cache*.json` | `sourcescout_manifest.json` | `goose_scan_*.json` reports |
|---|---|---|---|---|
| Identifier format | `asin` TEXT unique | `asin` | `asin` | `amazon_asin` |
| ASIN normalization | uppercase enforced? (not enforced at write — `products.upsert` stores as given) | per-provider normalized | uppercase | from wholesale match |
| Product-title source | seller/cache import | amazon_search parse | amazon_title | wholesale product name |
| Image source | none | none persisted | none | none |
| Price source | buy_box_price/amazon_price | provider price | price | breakdown price |
| Supplier source | costco_cost (+basis) | costco_client lookup | quantity_match.costco_sku | wholesale_price (per supplier) |
| Timestamp/freshness | fetched_at/fresh_until | fetched_at/generated_at | generated_at (2026-09-13) | meta.generated_at (2026-09-22..23) |
| Provenance label | data_kind/provider_id | source field | schema_version/kind | mode (mock/live/dry-run) |
| Dedup behavior | UNIQUE(asin) upsert | none | none | none |
| Read/write owner | live_catalog.stock, seed, migration | amazon_search.save | build_sourcescout_manifest (tool) | GG pipeline (report writer) |
| Consumers | dashboard_api, /api/v1/catalog/stocked, /api/products/finder | scanner pipeline, kirkland_discovery, autothink context | /api/sourcescout* | /api/golden-goose/opportunities |
| Conflicts | may not match cache price/age | different cost 0.0 vs known | 470 items incl. FAIL/REVIEW | different ASIN set (wholesale-derived) |
| Migration risk | HIGH — four owners, no shared key | HIGH | HIGH | HIGH |

**Only `/api/products/finder` (`main.py:2185-2192`) dedups two stores in-memory (`seen=set()` over stocked + cache).**

## 3. Canonical product identity strategy (PROPOSAL — no migration in Phase 0)

1. Single master record keyed `(marketplace, asin)`; add `marketplace` to the uniqueness constraint.
2. Promote `products` table to the canonical store; treat cache files as ingestion inputs with explicit provenance columns (`data_kind='cache_snapshot'`, `provider_id`).
3. Route scanner pipeline to upsert into `products` after each scan (write path owner = scanner service).
4. Golden Goose reports link to `products` via `amazon_asin` and store derived fields (`opportunity_score`) as attributes, not a parallel product row.
5. Add `idempotency`/`etag` on ingestion to prevent divergence.
6. Backfill reconciliation = a Phase-1 owned task with a dry-run diff report; never automatic.

## 4. Data flow between the 11 services (what feeds what TODAY)

| Service | Today's data source |
|---|---|
| Hub | SPA fixtures (Analyst's Desk); SPA proxy → summary/models/credits (northstar-os-ui) |
| Ledger | SPA fixtures; credits endpoint (display-only) |
| Prospector | `/api/kirkland/scanner` → cache files + costco + enrichment caches; `/api/products/{asin}/offers`; `/api/kirkland/discovery` |
| Golden Goose | GG report files → `/api/golden-goose/opportunities`; wholesale_scanner (mock default) |
| OfferChisel | SPA fixtures; `listing_forge.py` (unserved) |
| Town Crier | SPA fixtures; `social_pulse.py` ← `memory_entries` brand voice (the only memory-bank consumer) |
| Auctioneer | SPA fixtures; `ad_pilot.py` pure library; `word_coffee.py` ← fixture export |
| AutothinK | `/api/autothink/run` ← llm_adapter (Ollama/OpenRouter) + context from local caches |
| The Watch | skeleton fixtures; `bsr_history.py` store (no automatic capture) |
| RankLedger | skeleton fixtures |
| Rival Board | skeleton fixtures; competition_analytics over local snapshots |

**Cross-service feeds that actually exist:** (1) live_catalog → products → stocked/finder; (2) wholesale_catalog → supplier_products → suppliers API; (3) social_pulse ← memory_entries (brand voice); (4) GG reports → opportunities → workbench seam; (5) gateway audit → audit JSONL. **Everything else is fixtures or schema-only.**

## 5. Master Brain orchestration flow (S)

- Bootstrap `master_brain_profiles.bootstrap()` (:313) → resolve profile (only LocalDefaultResolver active; login/IP/2FA are registered stubs :65-131) → `master_brain_gateway.classify_task` (rules-based, :79-109) → `master_brain_learning.route_request` (L0→L1→L2→L3; live tasks always L3 approval-required :550-608) → `model_router.resolve(provider,tier)` (:153-181) → LLM generation → append-only audit (:112-148).
- Model catalog `shared/model-suite.json` + `service-model-map.json` consumed by `model_router`.
- Cloud lane requires `OPENROUTER_API_KEY` + `CLOUD_MODEL_LIVE=1` (`model_router.py:128-135`); `live_armed=false` observed this audit (R).
- Tier consent: `requires_consent`/`consent_prompt` for upward T1→T2→T3 moves (`model_router.py:300-317`).

## 6. Shared entities summary

| Entity | Shared? | Where |
|---|---|---|
| Product | NO (4 stores) | see §2 |
| Keyword/SEO | Schema only (dormant) | keywords/keyword_performance/search_query_performance |
| Supplier | YES | suppliers tables + routes |
| Brand voice | Partially (memory_entries + duplicated docs) | memory_bank, social_pulse |
| Campaign intelligence | Schema only (dormant) | campaigns/keyword_performance |
| Recommendations | NO (recomputed per row) | product_analysis, portfolio_analytics, competitor_crowding |
| Events | NO (no event bus) | — |
| Embeddings | NO | — |
| Agent memory | YES (SQLite) | memory_entries |
| Permissions | YES (auth roles) | auth.py/auth_deps.py |
| Audit log | YES (3 channels) | gateway JSONL + audit_log + live_pulls |
