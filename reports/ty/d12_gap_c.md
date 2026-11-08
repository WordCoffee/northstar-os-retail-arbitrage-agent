# D12 gap C — rivalboard and competitor-monitor

Worktree: `state/worktrees/gap-c` (branch `ty/gap-c`)
Date: 2026-11-08
Scope: `Northstar_backend/test_competitor.py`, `Northstar_backend/test_rival.py`,
`reports/ty/d12_gap_c.md` only.

## Why these two services scored 15/100

`tools/scorecards.py` maps a service to test ids by filename substring:
`rivalboard` ← `test_competitor`, `test_rival`; `competitor-monitor` ←
`test_competitor`. No file with either name existed, so both services had an
empty measured artefact and scored the "nothing proves this works" floor. The
two files below give both services real ids backed by route-level assertions.

## Routes found (grep of `main.py` + router modules for rival/competitor/compare/board)

| Service | Route | Definition |
|---|---|---|
| competitor-monitor | `GET /api/v1/noncreative/competitor/observations` | `noncreative_reads.py:261` |
| rivalboard | `GET /api/kirkland/scanner` — the route `RivalBoard.jsx` actually reads (`api.scanner()`) | `main.py:1842` |
| rivalboard (same family) | `GET /api/kirkland/live` | `main.py:627` |
| rivalboard (same family) | `POST /api/kirkland/refresh` — the only mutating route; 403 without the live gate | `main.py:635` |

Not counted as rival/competitor intelligence:

- `design_studio_api.py` `/variants/compare` and `/amazon-files/{uid}/compare`
  are design-studio image comparison routes, not competitor intel.
- `competitor_crowding.py` (`detect_crowding`) has no route and no importer in
  the backend. It is unrouted code; it was not tested (a test for it would be a
  test id for something no service can reach).

## Tests and what each proves

### `Northstar_backend/test_competitor.py` (5 tests) — competitor-monitor

| Test | Proves |
|---|---|
| `test_envelope_counts_agree_with_items` | `{kind, count, items, summary}` envelope; `count == len(items) == summary.products`; every returned item is exactly the 15-field projection and `data_kind == "live"` (a demo row can never be served as a market observation). |
| `test_summary_arithmetic_over_synthetic_source_rows` | `source_with_price`, `source_avg_price`, `distinct_brands` are computed over the source rows: 3 rows, 2 prices → avg 15.0; `Acme`/`acme` collapse to one brand; `unavailable` is `None` when the read succeeds. Uses the real route and real summary math; only the SQLite source is stubbed. |
| `test_summary_is_arithmetic_over_returned_rows` | The same arithmetic holds against the real local DB; the source projection has exactly the 10 selected columns; a missing table yields a non-empty reason and `source_avg_price is None`, never a confident `0.0`. |
| `test_limit_is_forwarded_to_the_stocked_read_and_projection_holds` | `?limit=7` reaches `live_catalog.get_stocked(limit=7)`; a synthetic stocked row is projected to exactly `ITEM_KEYS` and unknown fields (`fresh_until`, `internal_only`) are dropped. |
| `test_over_limit_is_rejected` | Error paths: `limit=501` → 422 with `loc == ["query", "limit"]`; non-integer `limit` → 422. |

### `Northstar_backend/test_rival.py` (9 tests) — rivalboard

The module pins `SCANNER_LIVE_ALLOWED=0`, so the scan is cache-only
(`data/scanner-search-cache.json`, committed) and deterministic.

| Test | Proves |
|---|---|
| `test_bff_envelope` | The scanner is served in the `bff/v1` envelope (`contract`, `req_*` request id, `status`, `data`, `error is None`, `meta.service`). |
| `test_scan_is_cache_only_and_contained` | `live_allowed is False`, `scanner_mode == "cache_only"`, `enrichment_source == "OFF"`; `status` is in the documented set and `ok` whenever rows exist — the Rival Board read can never become a live provider call. |
| `test_candidates_returned_matches_rows` | `summary.candidates_returned == len(products)`, `completeness_contract_version == 1`, all required summary keys present. |
| `test_only_allowlisted_fields_are_exposed` | Every row is a subset of `SCANNER_ALLOWED_KEYS + {completeness}`; the 15 forbidden financial-projection fields are absent. |
| `test_competitive_signals_are_real_values_or_honest_nulls` | The posture inputs (`roi_pct`, `net_profit`, `costco_cost`, `amazon_price`, `total_sellers`, `fba_sellers`, `sales_rank`, `buy_box_seller`) are numbers/strings or explicit nulls — no string-coerced numbers or fabricated zeros. |
| `test_rows_are_ranked_by_the_competitive_order` | Rows equal `sorted(rows, key=main._scanner_sort_key)` and economics groups are non-decreasing — the route serves the documented "who is winning" order, not insertion order. |
| `test_ranking_key_prefers_fewer_competitors_and_sorts_nulls_last` | On equal profit, fewer sellers ranks first; unknown economics/profit ranks last. |
| `test_no_scanner_row_is_purchase_ready` | Completeness payload has the full 10-key contract and all 6 categories; `status != "ready_for_test_buy"` (scanner rows carry no account-review approval); `score` is null or within `score_max`. |
| `test_live_refresh_is_refused_while_gate_is_off` | Error path: `POST /api/kirkland/refresh` → 403 and the detail names `SCANNER_LIVE_ALLOWED`; no provider call is executed. |

## Evidence

```
$ python -m pytest Northstar_backend/test_competitor.py Northstar_backend/test_rival.py -q
..............                                                           [100%]
=============================== warnings summary ===============================
Northstar_backend\design_studio_api.py:1455
  ... UserWarning: Field name "copy" in "APlusPackIn" shadows an attribute in parent "BaseModel"
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
14 passed, 1 warning in 9.22s
```

14 collected ids, all executed, none skipped. Offline controls: `network_guard`
is imported first (blocks real `requests`), the live gate is pinned off, and no
test touches Amazon or a paid provider.

## Honest gaps

1. **rivalboard has no dedicated endpoint.** `RivalBoard.jsx` reads the Kirkland
   scanner route, which is shared with Product Scout. The backend contract is
   proven; there is no rival-specific route to prove.
2. **The Rival Board page is not mounted.** `northstar-os-ui/src/data/services.js`
   advertises route `/rivalboard`, but `App.jsx` defines only
   `/competitor-monitor`; `RivalBoard.jsx` is imported nowhere. The service is
   provably backed at the API layer but not reachable from the UI.
3. **No change/diff payload.** The route returns a current landscape snapshot
   (price/ROI/seller counts). "What competitors changed" needs a history
   comparison that does not exist, so no test asserts it.
4. **`competitor_crowding.detect_crowding` is dead code** — seller-surge,
   price-war and buy-box-instability signals are implemented but routed and
   imported nowhere. Not tested on purpose.
5. **competitor-monitor is observation-only.** There is no tracked-competitor
   CRUD or feed endpoint; the page's "Add Competitor" is a gated toast and the
   page labels itself "cached catalog · observed, not live competitor tracking".
6. **Live-row assertion is conditional in this deployment.** The local DB has
   zero fresh live products, so the item-level `data_kind == "live"` loop is
   empty against real data. The same projection is proven deterministically by
   the monkeypatched stock-read test.
7. **Portability of the summary test.** `test_summary_is_arithmetic_over_returned_rows`
   follows whatever the local DB holds; on a deployment with the
   `costco_source_products` table populated it asserts the real arithmetic
   instead of the honest-empty branch.
