# D12 / gap-a — prospector and product-finder proven against the real app

Date: 2026-11-08
Branch: `ty/gap-a` (worktree `state/worktrees/gap-a`)
Scope: `Northstar_backend/test_prospector.py`, `Northstar_backend/test_product_finder.py`,
`Northstar_backend/test_sourcing.py`, this report.

## How the tests work

Each file imports the real `main` app and drives it through `fastapi.testclient.TestClient`.
No stub, no mock, no monkeypatched route. The only substitutions are environment-level and
legitimate for offline runs:

- `data_layer._SQLITE_PATH` → `tmp_path` and `_get_postgres_url()` → `None`, so every write goes
  to a throwaway SQLite warehouse (schema, migrations and `NorthstarDB` are the real ones).
- `SCANNER_SEARCH_CACHE_PATH` → a `tmp_path` cache file, so the finder reads a controlled candidate
  cache through the real `amazon_search._read_cache_file()` path.
- `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED` is deleted for the gate tests, so the free-tier router's
  real refusal path is exercised. **No test requests a live provider and none can reach Amazon.**

`/api/suppliers*`, `/api/products/*` and `/api/filters/universal*` are wrapped by the real
`BffEnvelopeMiddleware`; those tests assert the `bff/v1` envelope and then the payload.

## Routes exercised (method + path)

### prospector — 3 routes (the catalogue stream; no route is literally named prospector)

| Method | Path | Test |
|---|---|---|
| GET | `/api/v1/catalog/stocked` | serves only fresh `data_kind='live'` rows; demo and expired rows excluded; `limit` honoured; `bff/v1` envelope |
| GET | `/api/v1/catalog/pull` | stock-first hit (`source=stock`, `pulled=None`) and honest miss (`source=empty`, no invented rows) |
| POST | `/api/v1/catalog/stock` | §3 gate refusal for `live=false` **and** `live=true` without the operator env: `mode=blocked`, `stocked=0`, no `live_pulls` audit row, nothing written; missing `queries` → 422 |

### product-finder — 7 routes

| Method | Path | Test |
|---|---|---|
| GET | `/api/sourcescout` | manifest is self-consistent: `count == len(items)`, summary total equals count, every row has identity + a valid quantity verdict |
| GET | `/api/sourcescout/matches` | only `PASS` rows |
| GET | `/api/sourcescout/mismatches` | only `FAIL` rows |
| GET | `/api/sourcescout/review` | only `REVIEW` rows |
| GET | `/api/sourcescout/summary` | totals equal the three bucket counts, rates equal count/total |
| GET | `/api/products/finder` | scores the cache with the real universal filter (1 pass, 1 brand exclusion, 1 four-gate rejection), `min_roi_per_unit` override flips the verdict, live-stocked rows merge in and `seller_count` maps to `fba_sellers`, no-source case reports zeros honestly |
| POST | `/api/filters/universal/evaluate` | every failed gate is named in `reasons`, a qualified product passes with 4 gates, empty body → 400 |

The three SourceScout buckets are asserted to be a **disjoint partition** of the manifest: the
union of asins equals the manifest asins, no duplicates, and each bucket count equals the summary
component.

### sourcing — 7 routes (shared sourcing evidence for both services)

| Method | Path | Test |
|---|---|---|
| POST | `/api/suppliers/analyze` | unit COGS = 18.50/6, landed cost = COGS + inbound, net profit = retail − landed − referral − FBA (checked against the response's own arithmetic), ROI/margin recomputed from returned values, `viable` verdict; missing retail price → `needs_manual_review` naming the reason; missing wholesale price → `needs_manual_review`; unprofitable deal → `reject`; empty body → 400 |
| POST | `/api/suppliers/discover` | offline seed mode, `live_armed=False`, non-empty supplier profiles carrying the requested category, nothing persisted |
| POST | `/api/suppliers` | creates the supplier used by the workflow test |
| POST | `/api/suppliers/{sid}/products` | persists the SKU and returns a `viable` cost-benefit analysis; unknown supplier → 404; empty list → 400 |
| GET | `/api/suppliers/{sid}/products` | the persisted SKU is readable back |
| POST | `/api/v1/catalog/wholesale/stock` | with no wholesaler caller, refuses for `live=false` and `live=true`: `mode=no_caller`, `added=0`, `ok=false`, `supplier_id=tundra` |
| GET | `/api/v1/catalog/wholesale/products` | the refused pull left the supplier warehouse empty |

## What each file proves

- **test_prospector.py** (7 test ids, 6 functions + 1 parametrised): the stock-first read really
  reads the warehouse and really applies freshness; a pull hit never dispatches; a pull miss is
  reported as empty instead of fabricated; the live gate blocks dispatch even when `live=true`,
  leaves no audit record and writes nothing; request validation is enforced.
- **test_product_finder.py** (10 test ids): the SourceScout dataset and its three status buckets
  are internally consistent, the universal filter's verdicts and rejection reasons are real, a
  threshold override changes a verdict, the finder merges warehouse + cache with the documented
  field mapping, and an empty environment yields zeros rather than invented candidates.
- **test_sourcing.py** (10 test ids): landed-cost maths are self-consistent, every non-computable
  case is flagged for manual review with a reason, an unprofitable deal is rejected, supplier
  discovery is offline and seeded, the wholesale path refuses to invent rows without a caller, and
  the supplier → product → analysis workflow round-trips through SQLite with 404/400 edges.

No test asserts `True`, mocks a call, or checks a status code without checking the body. Every
success assertion names concrete values derived from the fixture that would differ if the
implementation changed.

## Exact result

```
$ python -m pytest Northstar_backend/test_prospector.py Northstar_backend/test_product_finder.py Northstar_backend/test_sourcing.py -q
...........................                                              [100%]
27 passed, 1 warning in 6.48s
```

(The single warning is the pre-existing `APlusPackIn.copy` shadowing warning from
`design_studio_api.py:1455`, unrelated to these routes.)

Test ids by substring used by `tools/scorecards.py`:

- `test_prospector`: 7
- `test_product_finder`: 10
- `test_sourcing`: 10 (counted for both prospector and product-finder by design)

## Gaps (features that do not exist — deliberately not tested, not skipped)

1. **No prospector route.** No path in `main.py` contains "prospector". The service exists only as
   the catalogue stream (`/api/v1/catalog/{stocked,pull,stock}`) and one docstring line
   (`main.py:1441`, "Prospector pull path"). There is no `/api/prospector*` API to test.
2. **No competition-evidence endpoint.** The registry PURPOSE is "find products worth selling, with
   demand and competition evidence". Demand and competition exist only as flat columns
   (`monthly_sales_estimate`, `seller_count`) on stocked rows and as filter reasons in
   `/api/products/finder`; no route returns a scored demand/competition evidence record.
3. **No gated live refresh for the finder.** The route docstring says "a live refresh is an
   explicit, gated action", but only `GET /api/products/finder` exists. There is no POST/refresh
   route, so nothing can be tested for that claim.
4. **SourceScout matching is a frozen dataset, not a live capability.** `/api/sourcescout*` reads
   `data/catalog/sourcescout_manifest.json` (`generated_at` 2026-09-13, 470 rows). No route accepts
   a product idea/query, re-runs quantity matching, or refreshes the manifest. "Match a product idea
   to suppliers" is therefore pre-computed data, not an implemented matcher.
5. **No wholesaler caller.** `/api/v1/catalog/wholesale/stock` returns `mode=no_caller` ("Tundra
   scraper pending") with or without `live`, so wholesaler SKUs can never actually be stocked by
   that route today. Proven as a refusal, not faked as success.
6. **Manifest rows are not schema-uniform.** Some SourceScout items carry `title`/`price`, others
   `product_title`/`product_price`; `brand`, `rating`, `reviews_count`, `bsr_text` and
   `buybox_price` are null on a subset. Consumers must tolerate both shapes; the test asserts the
   common identity keys (470/470 rows have `asin`, `title`, `quantity_match`) and requires the full
   retail schema on at least one row rather than pretending it is uniform.
7. **Uncovered (in-scope-adjacent, not claimed as passing):** supplier list, analytics, analyses,
   detail, delete and `POST /api/suppliers/import-csv` were not exercised here — they belong to the
   suppliers surface rather than the two scorecard services. Listed as coverage debt, not proof.

```json
[
  {"id": "gap_a_01", "service": "prospector", "kind": "missing_api", "detail": "No /api/prospector* route exists; the service is the catalogue stream plus a docstring reference (main.py:1441)."},
  {"id": "gap_a_02", "service": "prospector", "kind": "missing_feature", "detail": "No route returns scored demand/competition evidence; only monthly_sales_estimate and seller_count columns plus filter reasons."},
  {"id": "gap_a_03", "service": "product-finder", "kind": "missing_route", "detail": "No gated live-refresh route for /api/products/finder despite the handler docstring claiming one."},
  {"id": "gap_a_04", "service": "product-finder", "kind": "static_data", "detail": "SourceScout matching is a precomputed 470-row manifest (generated_at 2026-09-13); no route re-runs matching or accepts a product idea."},
  {"id": "gap_a_05", "service": "sourcing", "kind": "not_implemented", "detail": "Wholesale stock has no caller (mode=no_caller, 'Tundra scraper pending'); the route can never add rows."},
  {"id": "gap_a_06", "service": "product-finder", "kind": "data_quality", "detail": "SourceScout manifest rows use two field shapes (title/price vs product_title/product_price) and null optional fields."},
  {"id": "gap_a_07", "service": "sourcing", "kind": "coverage_debt", "detail": "Supplier list/analytics/analyses/detail/delete and import-csv are not exercised in this lane; recorded as uncovered, not as passing."}
]
```
