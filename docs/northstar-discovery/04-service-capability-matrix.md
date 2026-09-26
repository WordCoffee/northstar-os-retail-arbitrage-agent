# 04 — Service Capability Matrix

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNVERIFIED (U) / UNKNOWN (K). Tests were NOT executed in this phase.

## Status legend

VERIFIED_WORKING is used ONLY where runtime-validated in this audit (R) or supported by a clearly identified recent runtime artifact (H). Everywhere else the capability is classified by the strongest honest state. Test-code existence is NEVER proof of runtime behavior.

## 1. Operations Hub

| Capability | Status | Evidence |
|---|---|---|
| Backend aggregation endpoint | MISSING | No hub aggregate route; `dashboard_api.py:27-100` reads `products`/`transactions`/`campaigns` tables but nothing populates them from live ops (S) |
| Analyst's Desk Hub view | UI_ONLY | `static/northstar-os/js/hub.js` fixtures, zero network (S) |
| React SPA Hub | PARTIALLY_WORKING (proxy verified) | `northstar-os-ui/src/pages/Hub.jsx` calls `summary`/`models`/`credits`; proxy verified this audit (R) |
| Pinned panel | UI_ONLY (global, hard-coded) | `RightRail.jsx:5-16` local state; `static/northstar-os/index.html:830-834` bulletin board; no global persistence (S) |
| Gates & authorizations display | UI presentation | Gate pills render state from `/api/v1/models` `live_armed`; gates themselves are env-gated (S) |
| Production-readiness | 1/5 | Demo shell for flagship UI; no aggregation; no alerts aggregation |

## 2. Ledger

| Capability | Status | Evidence |
|---|---|---|
| Credit ledger engine | STATICALLY_CONFIRMED | `credit_ledger.py` append-only grant/reserve/commit/release, balance=derived sum; test_credit_ledger.py exists (S, NOT executed) |
| `/api/v1/credits/me` | RUNTIME_CONFIRMED (returns data) | `balance==allotment==5000, consumed 0`; main.py:1717 comment "Offline alpha: no consumption tracked yet" (R) |
| Usage metering wired to consumption | MISSING | `usage_meter.py` exists (S) but no code path debits ledger on a service action (S) |
| Billing/invoices/overage | MISSING | `COHORT_OPS.md:56-70` lists billing deferred (S) |
| React SPA Ledger | PARTIALLY_WORKING (proxy) | `Ledger.jsx` → credits+models (R proxy) |
| Production-readiness | 1/5 | Display-only credits; no consumption, invoices, or overage |

## 3. Prospector (SourceScout)

| Capability | Status | Evidence |
|---|---|---|
| Scan pipeline (cache-first) | CACHED_ONLY | `GET /api/kirkland/scanner` → `amazon_search.load_cached_candidates()` (product_analysis.py:178-179); RUNTIME_CONFIRMED response of 45 products from cache (R) |
| Live scan refresh | CONFIGURED_UNVERIFIED | `POST /api/kirkland/refresh` requires `live_gate.live_enabled()` (`SCANNER_LIVE_ALLOWED`) (S) |
| Fee/economics engine | STATICALLY_CONFIRMED | `fee_engine.py`, `amazon_us_fee_rules_2026.py`, tests exist (S, NOT executed) |
| Supplier matching / invoice status | PARTIALLY_WORKING | `suppliers` table + `invoice_verified_status` field; `costco_api_client` mapping ledger (S) |
| Broad (non-Kirkland) search | MISSING | search gated to `SEARCH_KEYWORDS=kirkland` default (S) |
| React SPA Prospector | PARTIALLY_WORKING (proxy) | `Prospector.jsx` → `api.scanner()` (R) |
| Production-readiness | 2/5 | Real economics pipeline + cache; live acquisition gated/unverified; no supplier-choice workflow in UI |

## 4. Golden Goose

| Capability | Status | Evidence |
|---|---|---|
| Mock scan pipeline | STATICALLY_CONFIRMED | `agents/golden_goose_finder/main.py` `_mock_scan`; scorer/economics modules + tests (S, NOT executed) |
| Live scan | CONFIGURED_UNVERIFIED | `/scan` requires `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1` (main.py:1188-1198) (S) |
| Two-gate enforcement | PARTIALLY_WORKING | `live_scan_gate.py` second gate (`GOLDEN_GOOSE_LIVE_AUTH_PHRASE`) NOT enforced by `/scan` route (S) |
| Opportunity score formula | STATICALLY_CONFIRMED | `opportunity_scorer.py` weighted composite (0.35 profit/0.20 demand/0.15 competition/…) (S) |
| Scan reports store | IMPORTED_DATA | `data/golden-goose-reports/goose_scan_*.json` (H: artifacts dated 2026-09-22..23) |
| React SPA GoldenGoose | PARTIALLY_WORKING (proxy) | `GoldenGoose.jsx` → `api.scanner()` (R) |
| Production-readiness | 2/5 | Solid mock + scoring engine; live gated; second gate not enforced; report-store, not a DB |

## 5. OfferChisel (ListingForge)

| Capability | Status | Evidence |
|---|---|---|
| Listing copy generator | STATICALLY_CONFIRMED (template path) | `listing_forge.py` title/bullets/description/backend-terms, scoring + compliance; Ollama `_call_llm` (:419) with template fallback (S) |
| Runtime LLM listing generation | UNVERIFIED via dedicated endpoint | No route serves `listing_forge`; generic `/api/autothink/run` generation was validated (R) but not the ListingForge service layer |
| Listing publish (Amazon write) | MISSING | no Amazon write path (S) |
| React SPA OfferChisel | PARTIALLY_WORKING (proxy) | `OfferChisel.jsx` → `api.autothinkRun()` with prompt (R) |
| Production-readiness | 2/5 | Generator exists (template+LLM), not served, not published |

## 6. The Town Crier (SocialPulse)

| Capability | Status | Evidence |
|---|---|---|
| Caption generation | STATICALLY_CONFIRMED (template) | `social_pulse.py:58` `generate_caption`; brand voice from `memory_entries` (:35-51); platform limits/hashtags/CTA (:110-116) (S) |
| Runtime LLM caption | UNVERIFIED via dedicated endpoint | same as OfferChisel — no service route; generic run validated (R) |
| Scheduling/publishing | MISSING | calendar rows are `status:"draft"` (:180); no publisher (S) |
| Brand voice shared | PARTIALLY_WORKING | consumed from Memory Bank (S); duplicated in profile/docs/fixtures (S) |
| React SPA TownCrier | PARTIALLY_WORKING (proxy) | `TownCrier.jsx` → `api.autothinkRun()` (R) |
| Production-readiness | 1/5 | Draft-only; no publish; no OAuth; no asset library |

## 7. The Auctioneer (AdPilot)

| Capability | Status | Evidence |
|---|---|---|
| Rule engine (bids/keywords/budget/ACoS) | STATICALLY_CONFIRMED | `ad_pilot.py` pure functions (S) |
| Live Amazon Ads API | MISSING | `importers/ads_api_importer.py` orphaned; no route (S) |
| Keyword harvesting | UI_ONLY / IMPORTED_DATA | `detect_negative_keyword_candidates` (ad_pilot.py:164) + importers; no live pull (S) |
| ACoS formula duplication | STATICALLY_CONFIRMED (3 copies) | ad_pilot.py:327-355, word_coffee.py:47-66, Auctioneer.jsx:15-16 (S) |
| React SPA Auctioneer | PARTIALLY_WORKING (local calc) | no API calls; pure local calculator (S) |
| Production-readiness | 1/5 | Rule library only; no Ads connection; no data |

## 8. AutothinK

| Capability | Status | Evidence |
|---|---|---|
| Local Ollama generation | RUNTIME_CONFIRMED (local) | `/api/autothink/run` local T2 → `northstar-qwen3:rev1`, real output during this audit (R; evidence §R1 in `17` — local engine only, no external service) |
| Cloud (OpenRouter) | CONFIGURED_UNVERIFIED | `CLOUD_MODEL_LIVE=1` + key required; `cloud.live_armed=false` observed (S/R) |
| Model routing + consent | STATICALLY_CONFIRMED | `model_router.py` tier escalation + consent_prompt (S) |
| Tool-calling | MISSING | no function/tool dispatch in server or adapter (S) |
| Run persistence | PARTIALLY_WORKING | `session_store.py` (cap 50) + `audit/autothink-runs.jsonl` (S) |
| Artifacts/streaming/retry | PARTIAL | streaming=True local (llm_adapter.py:139); no artifact system; no retry (S) |
| AutothinK UI | FUNCTIONAL (local) | single-file UI; runs validated (R) |
| Production-readiness | 3/5 | Real local engine; agentic/tool layer missing; cloud gated |

## 9. The Watch / RankLedger / Rival Board (Monitoring)

| Capability | Status | Evidence |
|---|---|---|
| BSR/price/seller store | STATICALLY_CONFIRMED (store) | `bsr_history.py` `data/bsr_price_history.json`; `record_snapshot` must be called externally (S) |
| Automatic capture loop | MISSING | no scheduler/cron; nothing populates snapshots automatically (S) |
| Demand estimator | STATICALLY_CONFIRMED | `demand_estimator.py` BSR→sales calibration, tests exist (S, NOT executed) |
| Rival/competitor analysis | CACHED_ONLY / COMPUTED | `competition_analytics.py` over local snapshots; no competitor-ASIN ingestion pipeline (S) |
| Analyst's Desk views | UI_ONLY (skeleton) | `thewatch`/`rankledger`/`rivalboard` schema previews (S) |
| React SPA views | PARTIALLY_WORKING (proxy) | compute from `api.scanner()` (R proxy) |
| Production-readiness | 0-1/5 | No data acquisition; no alerting; no thresholds UI |

## 10. Account / Auth / Back-office

| Capability | Status | Evidence |
|---|---|---|
| Auth (JWT, bcrypt, refresh) | STATICALLY_CONFIRMED | `auth.py`; tests exist (S, NOT executed) |
| RBAC roles (member/operator/owner/admin) | STATICALLY_CONFIRMED | `auth.py:88-96`, `auth_deps.py:86-114` (S) |
| Anonymous demo fallback | RUNTIME_CONFIRMED (code) | `auth_deps.py:39-48` returns demo user without token (S) |
| Rate limiter | STATICALLY_CONFIRMED | `rate_limiter.py` plan limits; prod posture guard (S) |
| Alpha gate | STATICALLY_CONFIRMED | `alpha_gate.py` fail-closed allowlist (S) |
| Billing | MISSING (engine only) | see Ledger |
| Supplier CRUD | STATICALLY_CONFIRMED (routes+DAO) | `main.py:1894-2119`, `data_layer.py:964`; tests exist (S, NOT executed) |
| Help/tours/onboarding | PARTIALLY_WORKING | Analyst's Desk onboarding modal + `prefers-reduced-motion`; no tour framework for other surfaces (S) |

## 11. Master Brain

| Capability | Status | Evidence |
|---|---|---|
| Gateway classifier + audit | STATICALLY_CONFIRMED | `master_brain_gateway.py` classify_task + JSONL audit; tests exist (S, NOT executed) |
| Learning loop L0–L3 | STATICALLY_CONFIRMED | `master_brain_learning.py`; learning/ contains only schema.json (no accumulated data) (S) |
| Memory bank | STATICALLY_CONFIRMED | `memory_bank.py` SQLite `memory_entries` (22 rows observed) (S/R counts) |
| Profiles/subscribers | STATICALLY_CONFIRMED | profiles manifest 1 profile; LIVE_GATES all off (S) |
| Embeddings/vector store | MISSING | none implemented (S) |
| Production-readiness | 2/5 | Shared config layer is real; shared data layer partial; embedding/recommendation layer absent |

## 12. Summary status matrix

| Service | Primary status | Runtime-confirmed this audit |
|---|---|---|
| Hub | UI_ONLY (shell) + partial SPA | SPA proxy (R) |
| Ledger | PARTIALLY_WORKING (engine; no consumption) | credits endpoint (R) |
| Prospector | CACHED_ONLY default; live gated | scanner endpoint returns cached 45 (R) |
| Golden Goose | MOCKED/STATICALLY_CONFIRMED; live gated | none |
| OfferChisel | STATICALLY_CONFIRMED generator; no route | generic autothink run (R) |
| Town Crier | STATICALLY_CONFIRMED draft-only | generic autothink run (R) |
| Auctioneer | STATICALLY_CONFIRMED rule library | none (local calc) |
| AutothinK | RUNTIME_CONFIRMED local | run + models + history (R) |
| Watch/Rank/Rival | UI_ONLY skeletons / CACHED_ONLY | SPA proxy (R) |
| Account/back-office | STATICALLY_CONFIRMED (unexecuted tests) | credits (R) |
| Master Brain | STATICALLY_CONFIRMED (offline) | none |

## 13. Counting methods

- Capability statuses derive from source reads (S), this-audit runtime calls (R), and dated artifacts (H). Test files counted via grep `def test_` (124 files / 2,368 funcs backend tree; 3 files / 25 funcs autothink) — commands in `17` §E. Tests NOT executed.
