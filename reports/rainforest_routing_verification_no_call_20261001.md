# Rainforest Routing Verification — Local, No Network (2026-10-01)

**Scope:** local repository inspection only. **No external API calls; no credential validation; no secret values read/printed/copied/modified; no config changes; no live requests.** Only committed source, docs, and the committed `.env.example` (placeholder names only) were read.

## Headline
**There is no Rainforest adapter or client anywhere in this repository.** A repo-wide search for `rainforest` (case-insensitive) returned exactly one irrelevant hit — a Clorox product title ("…rainforest rush…") inside a Bright Data data snapshot — and **zero** code, config, or documentation references. Rainforest is **not** part of the provider registry or any routing path.

---

## 1. Does a Rainforest adapter/client exist?
**No.** No file, class, function, or module reference. Expected search terms — `rainforest`, `rainforestapi`, `RAINFOREST` — produced **no matches** in `Northstar_backend/**/*.py` or repo docs/config. The provider registry (`docs/northstar-discovery/provider-registry.json`) enumerates every provider and contains **no Rainforest entry**.

Existing Amazon/Costco providers (for contrast): `bright_data_client.py`, `bright_data_costco.py`, `brightdata_client.py` (deprecated), `chocodata` (inside `amazon_search.py`/`offer_enrichment.py`), `scavio_client.py`, `offer_enrichment.py` (Unwrangle), `easyparser_client.py`, `dataforseo_adapter.py`, `firecrawl_*`, `browserbase_amazon.py`, `scrapedo_amazon.py`, `rapidapi_client.py`/`rapidapi_router.py`, `canopy_client.py`. Adapter contract: `foundation/providers.py::ProviderAdapter` (+ `ProviderRegistry`, `FixtureAdapter`); `proof_batch_contracts.py::ProviderAdapter`; `costco_non_kirkland/providers.py::ProviderAdapter`/`SellerAmpProvider`.

## 2. Environment-variable NAMES it expects
**None.** No Rainforest variable is defined or referenced. (Names only, from committed `.env.example` / registry — never values): existing Amazon-search names are `SCANNER_SEARCH_SOURCE`, `SCANNER_SEARCH_FALLBACK`, `SCANNER_LIVE_ALLOWED`, `BRIGHTDATA_UNLOCKER_API_KEY`, `BRIGHTDATA_UNLOCKER_ZONE`, `BRIGHTDATA_REQUEST_URL`, `BRIGHTDATA_REQUEST_TIMEOUT_SECONDS`, `CHOCODATA_API_KEY`, `SCAVIO_API_KEY`, `SCAVIO_API_URL`, `UNWRANGLE_API_KEY`.

## 3. Is the required variable configured locally?
**NOT_CONFIGURED (not applicable)** for Rainforest — no such variable exists to configure. For the real providers, configuration state is **UNKNOWN/CONFIGURED_UNVERIFIED**; per policy I did **not** read environment values.

## 4. Operations Rainforest can perform in this repo
**None** — the adapter is absent, so it answers no capability:
Amazon search by title — NO · UPC/GTIN lookup — NO · MPN/model lookup — NO · ASIN product details — NO · offer/seller retrieval — NO · price/rank/reviews — NO · batch lookup — NO.

(For context, those operations are implemented by Bright Data/Chocodata/Scavio/Unwrangle/EasyParser/DataForSEO/Firecrawl/Browserbase/scrape.do/RapidAPI/Canopy modules — not Rainforest.)

## 5. Routing chain (code paths, no secrets)
Product Scout Amazon search:
`caller (POST /api/kirkland/refresh | npm pipeline) → amazon_search.search_products() → live_gate.live_enabled() [SCANNER_LIVE_ALLOWED] → if SCANNER_SEARCH_SOURCE == "BRIGHTDATA": _search_brightdata() → bright_data_client.search_products() → bright_data_client._fetch() [Web Unlocker transport]`; on failure → `SCANNER_SEARCH_FALLBACK` (`CHOCODATA → _search_chocodata()` or `SCAVIO → scavio_client.search_kirkland_products()`).
Foundation registry path: `foundation/api/state.py → ProviderRegistry(repos) → bind_adapter(...) → ProviderRegistry.execute_read(provider_key, request)` (disabled providers never execute; `FixtureAdapter` for offline/mocked).
Proof-batch path: `proof_batch_run._arm_live_adapter() → proof_batch_easyparser_adapter.EasyparserLiveAdapter` (double-gated).
**No Rainforest node exists in any chain.**

## 6. Which operation/provider/flags choose Rainforest?
**None.** No operation, provider key, or routing flag selects Rainforest. Selection keys are `SCANNER_SEARCH_SOURCE` (BRIGHTDATA default) / `SCANNER_SEARCH_FALLBACK` (CHOCODATA|SCAVIO) / `SCANNER_OFFER_ENRICHMENT` (BRIGHTDATA|CHOCODATA|UNWRANGLE|EASYPARSER|AUTO) / `SCANNER_LIVE_ALLOWED`; proof-batch uses `PROOF_BATCH_LIVE_ARMED`.

## 7. When does the router choose Bright Data / browser / fixture / other fallback?
- **Bright Data:** `SCANNER_SEARCH_SOURCE=BRIGHTDATA` (default) → `_search_brightdata`; or `SCANNER_OFFER_ENRICHMENT=BRIGHTDATA`; or `BRIGHTDATA_COSTCO_DETAIL_ENABLED=1` for Costco detail.
- **Fallback (Chocodata/Scavio):** only when the primary fails AND `SCANNER_SEARCH_FALLBACK` is set (`amazon_search.search_products` lines ~356–370).
- **Fixture/mock:** foundation `FixtureAdapter` (offline, `cost_kind="local_free"`, never touches network); proof-batch `FixtureAdapter`; tests inject fake clients via `LIVE_CLIENT_FACTORY`.
- **Browser path:** separate (`tools/browser_agent.py`, Google/Gemini) — not part of the Amazon-search provider dispatch.
- **Hard gate:** when `SCANNER_LIVE_ALLOWED` is not an explicit `1/true/yes/on`, `search_products()` returns `[]` with zero provider calls and zero outbound traffic (cache-only).

## 8. Is provider routing deterministic and testable?
**Yes for the existing providers.** Selection is driven by `SCANNER_SEARCH_SOURCE`/`SCANNER_SEARCH_FALLBACK` env constants and a single `live_gate.live_enabled()` check, and dispatched through one function (`amazon_search.search_products`). **Rainforest routing is N/A** (no such route exists).

## 9. Mocked test proving a request resolves to Rainforest without contacting it?
**No — and none should be added.** No test can prove resolution to Rainforest because **no Rainforest adapter exists**; adding one would require new adapter code and/or config (out of the stated constraint). Existing **mock-only** routing tests already prove the analogous property for the real provider:
- `Northstar_backend/test_universal_search.py` — patches `amazon_search.SCANNER_SEARCH_SOURCE` and `bright_data_client.search_products` and asserts dispatch **without network** (`test_brightdata_passes_match_all_through`, `test_bright_data_client_match_all_bypasses_kirkland_filter`).
- `Northstar_backend/test_bright_data_client.py` — "dispatcher routing/fallback for SCANNER_SEARCH_SOURCE" with `requests` mocked.
- `test_full_pull_rehearsal.py` — REAL runner/adapters with `bright_data_client._fetch` and `requests.post` mocked.

## 10. Risk that a requested Amazon lookup could go elsewhere or to a live browser
- **Different provider:** possible **by design** — if Bright Data returns nothing/errors and `SCANNER_SEARCH_FALLBACK` is set, the call falls through to **Chocodata or Scavio**. Not Rainforest.
- **Live browser path:** the Amazon-search dispatch does **not** invoke any browser; `tools/browser_agent.py` is separate. A lookup cannot silently become a Playwright/browser call through `amazon_search`.
- **Accidental live calls:** strongly bounded — `search_products()` returns `[]` unless `SCANNER_LIVE_ALLOWED` is an explicit opt-in; off-gate GET/static/import paths cannot reach a provider.
- **Offer enrichment divergence:** `SCANNER_OFFER_ENRICHMENT` can route to Chocodata/Unwrangle/EasyParser instead of Bright Data — a same-class routing divergence (not Rainforest).
- **No Rainforest risk exists** because the provider is absent.

## Governance
No external calls; no credential validation; no values read/printed; no config modified; no live requests. Only local files inspected.

## Mock-only test run (no network)
Run from `Northstar_backend/`:
- `python -m pytest test_universal_search.py -q` → **7 passed** (patches `SCANNER_SEARCH_SOURCE` + `bright_data_client.search_products`; asserts provider dispatch with no network).
- `python -m unittest test_bright_data_client` → **44 tests, OK** (includes "dispatcher routing/fallback for SCANNER_SEARCH_SOURCE" with `requests` mocked; no network).
Both are fully mocked; **no external call made**. (No Rainforest test exists or was added — impossible without a Rainforest adapter, and adding one would require production code/config changes, which are out of scope.)

## Addendum — operator root `.env` check (names/structure only; values never printed)
Operator reported a Rainforest API key in `…\Northstar OS Retail Arbitrage Agent\.env`. Safe check (no value surfaced):
- Root `.env` contains a comment line `#Rainforest API:` immediately followed by **one malformed line**: `Rainforest: <value>` — a **colon-separated** entry with **no `=`**, so it is **NOT a usable environment variable** (`Rainforest` is not an env key; python-dotenv expects `KEY=value`).
- **Zero** properly-formed `RAINFOREST*` keys in either file (`ROOT .env`: 0 proper / 1 malformed; `Northstar_backend/.env`: 0 / 0).
- No Rainforest value was read, printed, logged, copied, or modified; `.env` was not edited.

Implications: (a) even if reformatted to `RAINFOREST_API_KEY=<value>`, **it would be unused** — there is no Rainforest adapter/routing in the repo; (b) the root `.env` also has a known malformed line (~L98) unrelated to this. Any actual Rainforest integration would be **new work** (adapter + registry + env var + tests), requiring explicit approval.

## Conclusion
Rainforest is **not present** in this repository: no adapter, no env var, no routing flag, no test. Amazon/Costco lookups route only through the documented providers (Bright Data primary; Chocodata/Scavio fallback; Unwrangle/EasyParser/DataForSEO/Firecrawl/Browserbase/scrape.do/RapidAPI/Canopy per their own flags), behind `SCANNER_LIVE_ALLOWED`, with `FixtureAdapter`/mocks for offline. **A requested Amazon lookup cannot resolve to Rainforest.**
