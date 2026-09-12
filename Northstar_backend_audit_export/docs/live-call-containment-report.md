# Live-Call Containment Report

Status: containment implemented + offline-verified; **NEEDS HUMAN BROWSER
VERIFICATION** (no headful browser is available in this sandbox — the
operator must start the server and confirm zero provider log lines).

Date: 2026-08-17

## Incident

`python -m uvicorn main:app --reload` + a browser load of
`http://127.0.0.1:8000/?ui_debug=1` produced live Bright Data traffic in
the server terminal:

```
[Bright Data] keyword='kirkland' page=1/10 ...
[Bright Data] keyword='kirkland' page=2/10 ...
```

A plain page load must never trigger outbound provider calls.

## Root cause (full trace from GET / to the provider)

1. `GET /` (`main.serve_scout`, main.py:64) serves `static/index.html` —
   read-only, not the culprit itself.
2. The UI's `init()` → `loadScanner()` fires
   `fetch('/api/kirkland/scanner')` on page load (static/index.html).
3. `GET /api/kirkland/scanner` (`main.get_kirkland_scanner`, main.py:434)
   calls `product_analysis.analyze_kirkland_products()` **unconditionally**.
4. `analyze_kirkland_products()` → `_candidates_for_mode()`
   (product_analysis.py:152): it reads the local cache **only** when
   `offer_enrichment._enrichment_mode() == "OFF"`. The user's `.env`
   enabled enrichment (`SCANNER_OFFER_ENRICHMENT`), so it took the live
   branch: `amazon_search.search_kirkland_products()` → `_search_brightdata()`
   → `bright_data_client.search_products('kirkland', pages=10)` — one
   Web Unlocker POST per page, i.e. the observed log lines.
5. Other GETs with the same defect: `GET /api/kirkland/live` (same
   analyze call), `GET /api/products/{asin}/offers` (Easyparser on cache
   miss, per explicit click), `GET /api/products/{asin}/canopy` (Canopy).

No imports, startup hooks, or module-level code make provider calls —
verified by tracing `main.py` imports and each provider module.

## Fix: single default-off gate `SCANNER_LIVE_ALLOWED`

New `live_gate.py`: `live_enabled()` = strict boolean
(`env_flags.env_flag`), so only `1/true/yes/on` enables live providers;
unset/anything else = **off**. Enforcement points:

| File | Change |
|------|--------|
| `live_gate.py` (new) | Gate module (`SCANNER_LIVE_ALLOWED`, `live_enabled()`, `live_disabled_note()`) |
| `amazon_search.py` | `search_kirkland_products` returns `[]` before any provider access when gate off (no error flags, no output) |
| `offer_enrichment.py` | `_enrichment_mode()` forced `"OFF"` when gate off (scans become cache-only); `get_seller_offer_contract` serves cache hits but refuses the live Easyparser fetch with honest `offer_data_status: "unavailable"` + note |
| `canopy_client.py` | `get_canopy_product` returns the offline shape (`data_gaps` notes the disabled gate) before any request |
| `main.py` | `POST /api/kirkland/refresh` — the ONLY route that may run a live scan, and only with the gate on (403 otherwise); `/api/kirkland/scanner` summary gains `live_allowed`; docstrings updated |

Boundary statement: with the gate off, **no route, static asset, import,
startup hook, or UI page load can reach any provider client** — the only
importers of the provider clients (`bright_data_client`, `brightdata_client`,
`scavio_client`, `easyparser_client`) are the gated entry points above.
Explicit operator commands (npm pipeline, `costco_api_client.py refresh`
via the weekly Scheduled Task, `enrich_cached_asins.py --live`) remain the
intentional live paths and are documented in README "Safe commands".

## Test results (offline, zero network)

New `test_live_containment.py` (17 tests) patches every provider client to
raise, forces the most permissive env
(`SCANNER_OFFER_ENRICHMENT=BRIGHTDATA`, `SCANNER_SEARCH_SOURCE=BRIGHTDATA`,
`SCANNER_SEARCH_FALLBACK=SCAVIO`, `PAGES_TO_SEARCH=10`), points all caches
at a temp dir, and proves zero provider calls from:

- `GET /` and `GET /?ui_debug=1` (the exact incident page load)
- `GET /health`
- `GET /api/kirkland/scanner` (asserts `live_allowed: false`,
  `scanner_mode: "cache_only"`)
- `GET /api/kirkland/live`
- static route mount (on-disk lookup only)
- `GET /api/products/{asin}/canopy` and `GET /api/products/{asin}/offers`
- `POST /api/kirkland/refresh` → 403 (never executed)
- direct calls: `search_kirkland_products` → `[]`,
  `_enrichment_mode()` → `"OFF"`, canopy offline shape

Gate-opt-in semantics are pinned too (`0/false/no/off/garbage` off;
`1/true/yes/on` on) plus one patched-provider dispatch proving the live
path is reachable only when opted in.

| Suite | Result |
|-------|--------|
| `python -m unittest test_live_containment` | 17 tests OK |
| Full explicit suite (28 modules, incl. live-path tests with the gate opted in via `setUpModule`) | **687 OK (skipped=3)** |
| `node test_ui_display.cjs` | **ALL UI DISPLAY TESTS PASSED** (756 assertions, unchanged — no JS edits) |

Test modules that exercise gated live paths now opt in explicitly
(`setUpModule`/`tearDownModule` setting and restoring `SCANNER_LIVE_ALLOWED`):
`test_amazon_search`, `test_bright_data_client`, `test_live_response`,
`test_product_analysis`, `test_offer_enrichment`, `test_offers_route`,
`test_scanner_endpoint`, `test_scanner_cache_only`. Offline/cache-only
modules were untouched (`test_manual_import`, `test_market_snapshot_merge`,
intel CLIs, etc.).

## Verification steps for the operator

1. `python -m uvicorn main:app --reload`
2. Load `http://127.0.0.1:8000/?ui_debug=1`
3. Confirm **no** `[Bright Data]` / `[Chocodata]` / `[Scavio]` /
   `[Easyparser]` / `[Canopy]` log lines appear, and
   `GET /api/kirkland/scanner` returns `summary.scanner_mode: "cache_only"`
   and `summary.live_allowed: false`.
4. Optional: `Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/kirkland/refresh`
   → expect HTTP 403 while `SCANNER_LIVE_ALLOWED` is unset.

## Constraints honored

No live/API/network calls during diagnosis or testing; no `.env`/secrets
read or modified; `test_scavio.py`/`test_scavio_client.py` never run;
`finance.py`, `pricing.py`, `product_analysis.py`, and the CSV contract
unchanged; no production data/cache files touched (tests use temp paths);
no commits.