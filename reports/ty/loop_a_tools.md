# Loop A — Bojo sourcing tools (catalog_pull, golden_goose_scan)

Branch: `ty/loop-a` · worktree `state/worktrees/loop-a`
Code commit: `5b81739b` (this report is a follow-up commit on the same branch)

## Deliverable

Two plain, typed functions in `Northstar_backend/bojo_tools/sourcing.py`, exported as
`TOOLS = {"catalog_pull": catalog_pull, "golden_goose_scan": golden_goose_scan}`.
`bojo_tools/__init__.py` re-exports the same three names. `chat_tools.py` was not touched.

Result contract for both tools:

```python
{"ok": True,  "tool": "<name>", "data": {...}}
{"ok": False, "tool": "<name>", "reason": "<reason string>"}
```

Business failures (empty catalog, nothing above threshold, dependency/scorer error) return
`ok=False`. Only programmer errors in the tool's own contract raise (`TypeError` for a
wrong-typed required argument, e.g. `query=None`, `limit="50"`, `candidates=<dict>`).

## catalog_pull (prospector)

```python
def catalog_pull(
    query: str,
    limit: int = 50,
    category: Optional[str] = None,
    live: bool = False,
    catalog: Optional[Any] = None,
) -> Dict[str, Any]
```

- Calls the REAL path: `live_catalog.get_or_pull(query, category=, limit=, live=)` at
  `Northstar_backend/live_catalog.py:119`, which is the function behind
  `GET /api/v1/catalog/pull` (`Northstar_backend/main.py:1439`). No re-implementation:
  the stock-first / pull-on-miss decision, the A3 live gate and the `live_pulls` audit
  all stay inside `live_catalog`.
- `catalog` is the injectable dependency: anything with that `get_or_pull` signature.
  Defaults to the real `live_catalog` module (`_default_catalog()`); tests pass a fake,
  so no DB and no network.
- `data` = `{query, category, live, source, count, rows, pulled}`. `source` is passed
  through verbatim (`stock` | `empty` | `live` | `live_empty`), rows are verbatim, and
  `count == len(rows)`.
- Error paths: empty query, `limit < 1`, no rows (`"no catalog rows for ... (source=...)"`),
  dependency raising (`"catalog pull failed: <Type>: <msg>"`), non-mapping result.

## golden_goose_scan (goldengoose)

```python
def golden_goose_scan(
    candidates: List[Mapping[str, Any]],
    roi_floor: float = 10.0,
    min_monthly_sales: int = 1000,
    include_rejected: bool = False,
    limit: Optional[int] = 10,
    scorer: Optional[Any] = None,
) -> Dict[str, Any]
```

- Runs the REAL pipeline per candidate:
  `breakdown_economics.calculate_breakdown_economics(WholesalePack, IndividualListing)`
  (fee stack, COGS, ROI, undercut headroom) then
  `opportunity_scorer.score_batch(...)` (hard filters, 0-1 composite, HIGH/MEDIUM/LOW/REJECT,
  descending rank, REJECT dropped unless `include_rejected=True`). Summary comes from
  `opportunity_scorer.get_scoring_summary`.
- Candidate object keys: `asin, title, brand, category_slug, amazon_price, wholesale_price,
  pack_count, bsr, review_rating, review_count, fba_sellers, weight_oz,
  monthly_sales_estimate, seller_name, is_brand_seller, is_amazon_seller`. Missing values
  are left as `None` and fail closed inside the real scorer (no invented numbers).
- `data` = `{evaluated, returned, roi_floor, min_monthly_sales, include_rejected, summary,
  opportunities[]}`; each opportunity carries `asin, title, brand, tier, composite_score,
  scores{profit,demand,competition,listing_health,price_gap,ad_feasibility},
  filters{...all}, economics{unit_cogs,total_costs_per_unit,net_profit_per_unit,
  net_profit_per_pack,roi_per_unit,profit_margin_pct,undercut_headroom,max_undercut_price,
  confidence}, tags, notes`. No `ScoredOpportunity` object leaks into the payload.
- Error paths: no candidates (`"no candidates supplied"`), all REJECT-tier
  (`"no candidates survived Golden Goose selection (all REJECT-tier; roi_floor=..., min_monthly_sales=...)"`),
  scorer raising (`"scoring failed: ..."`), `limit < 1`.
- `scorer` is an injection seam that defaults to the real `score_batch`; the tests never
  use a fake scorer for the happy path (one test explicitly asserts the default is the
  real function object).

## Evidence

`python -m pytest Northstar_backend/test_bojo_sourcing_tools.py -q`

```
..................                                                       [100%]
18 passed in 0.17s
```

Tests pin real arithmetic, not stub output: `unit_cogs == wholesale_price / pack_count`,
`net_profit == amazon_price - total_costs_per_unit`, `roi == net / unit_cogs * 100`,
`net_profit_per_pack == net * pack_count`, and `composite == Σ weight·component` (rounded
to 4dp). Ordering, tier, filter flags, `include_rejected`, `limit`, JSON-serialisability
and one error path per tool are all asserted.

Can-fail check (mutation): hardcoding `pack_count=1` in the candidate builder made 3 tests
fail (`happy_path`, `ranks_descending`, `limit_keeps_only_the_best`) before the mutation was
reverted.

Real-module wiring check: `catalog_pull("tide pods", limit=3)` with no injected catalog
runs the real stock-first read (no network) and returns
`{"ok": false, "tool": "catalog_pull", "reason": "no catalog rows for 'tide pods' (source=empty)"}`
— i.e. the tool is genuinely attached to `live_catalog`, and an empty warehouse is reported
honestly instead of faked.

Demonstration (fake catalog for the deterministic rows, real Golden Goose scoring):

```
catalog_pull: {"ok": true, "tool": "catalog_pull", "data": {"query": "mr clean", "category": "household", "live": false, "source": "stock", "count": 2, "rows": [{"asin": "B001", "title": "Mr. Clean Magic Eraser 8 ct", "brand": "Mr. Clean"}, {"asin": "B002", "title": "Mr. Clean Multi-Surface Spray"}], "pulled": null}}
golden_goose_scan summary: {"total_evaluated": 2, "high": 1, "medium": 0, "low": 1, "rejected": 0, "avg_profit": 10.79, "avg_roi": 140.8, "top_tags": {"no_fba_competition": 2, "high_margin": 1, "premium_product": 1, "trending_up": 2, "bulk_goldmine": 2}, "best_asin": "B00GOOD001", "best_composite_score": 0.7281}
   B00GOOD001 HIGH 0.7281 net=$14.11 roi=169.39%
   B00MARG001 LOW 0.6298 net=$7.48 roi=112.21%
```

## Spec vs disk

`ty/services.json` was **not edited**. My base commit (`d968eacd`) predated the declaration
commit `0abf3944`, so the file in my starting tree still showed `prospector.tools: []`.
I rebased `ty/loop-a` onto `staging` (`fd84631c`), where the registry already declares
`catalog_pull` for `prospector` and `golden_goose_scan` for `goldengoose` and `golden-goose`.
Verified with `git show staging:ty/services.json`. Final branch head sits on that registry.

## Not done / out of scope

- No live catalog pull (`live=True`): it needs the armed A3 envelope and a provider call,
  which this lane deliberately did not exercise. The code path is the real one; only the
  offline branch was exercised.
- `chat_tools.py` wiring is deferred to the Director by instruction, so neither tool is
  reachable from Bojo until that one-line registration happens.
- No scorecard/UI verification — that is the Director's dimension check, not this lane.
