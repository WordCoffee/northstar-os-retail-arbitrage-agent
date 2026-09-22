# Northstar OS — DATA STREAMS: live free channels, wholesaler catalog, recommendations

Status: **2026-09-22**. Operator granted full approval to fire live data via free-tier
providers. Live pipeline is PROVEN (see Evidence). This doc is the operating map for
"stock the sources, then search/filter populates from stock, pull-from-stream to refresh."

## 1. The free-tier channel inventory (what's already wired)

All in `Northstar_backend/agents/golden_goose_finder/free_tier_registry.py`. Tasks:
`costco_search`, `sams_club_search`, `amazon_search`, `amazon_product`, `amazon_offers`,
`generic_scrape`. Dispatch order lives in `free_tier_router.py`.

| Provider | Quota | Tasks | Notes |
|---|---|---|---|
| **Bright Data Web Unlocker** | 5,000/mo | all 6 | WORKHORSE — the consistent Amazon/Catalog channel |
| **Firecrawl** | 1,000/mo | generic, product, costco | generic scrape fallback |
| **Scrape.do** | 1,000/mo | generic, product, costco | scrape fallback |
| **OpenWebNinja** | 100/mo | costco_search | Costco surface |
| **Unwrangle (Sam's)** | ~500 pool | sams, amazon_product | existing credit pool |
| **Chocodata** | ~200 searches | amazon_search | PROVEN live (see Evidence) |
| **Scavio** | ~500 | search, product | fallback |
| **RapidAPI pool** | ~600/mo | amazon_product | 6 hosts |
| **EasyParser** | 41 | amazon_offers | seller identity snapshots |
| **Scrapingdog** | 200 | search/product/offers | key obtained 2026-09-22 |
| **ScrapeBee** | 1,000 | search/product | key obtained 2026-09-22 |
| **ScrapeBadger** | 1,000 | product/search/offers | key obtained 2026-09-22 |
| **AmazonScraperApi** | 1,000 | search/product | key obtained 2026-09-22 |
| **APIclaw** | 1,000 | search/product/offers | key obtained 2026-09-22 |

Router behavior: waterfall (a provider failure falls through to the next), credit
ledger per provider, §3 gate (`GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1`), never invents
keys, typed failures.

## 2. Recommended consistent services (the "1–2" for the future)

1. **Bright Data Web Unlocker** (5,000 requests/mo free) — the one consistent,
   all-surface channel (Amazon search/product/offers, Costco, Sam's, generic). Make it
   the primary; everything else is fallback.
2. **Firecrawl** (1,000 pages/mo free) — the second workhorse for Costco + generic
   scrape when Bright Data is throttled.

Both are free-tier and already wired; the others exist as depth. If you ever want ONE
paid upgrade for reliability, Bright Data is the candidate (already the code path).

## 3. Wholesaler catalog (the Golden Goose sourcing engine)

Target: a wholesaler whose catalog we can pull, then compare their SKUs against Amazon
sell-through to find high-ROI Golden Goose candidates (tier A: clears every gate).

- **Primary candidate: Tundra (tundra.com)** — free B2B wholesale marketplace, no
  membership fee, public searchable catalog of thousands of brands/SKUs with wholesale
  prices. Scrapeable via `generic_scrape` (Firecrawl/Bright Data). This is the
  recommended wholesaler source to wire as `TASK_WHOLESALE_CATALOG`.
- Alternatives if Tundra is gated: **Alibaba.com** (search → generic scrape; huge but
  noisy, mostly B2B/China), **Faire** (requires buyer account — lower priority),
  **Wholesale Central / go4WorldBusiness** (indexes).
- Golden Goose flow: pull wholesaler catalog rows → filter by our selling criteria
  (net ≥ $11, seller count 1–3, category-allowlist, no restricted logistics) → enrich
  each SKU with Amazon search/product/offers → compute ROI → rank A/B/C/D. This is
  exactly the existing `golden_goose_finder` pipeline (breakdown economics, free-tier
  waterfall) — it just needs the catalog task + a stocked SKU list.

## 4. Stock-then-filter data flow (operator's model)

1. **Stock**: batch pulls from the free channels write into the backend data layer
   (`data_layer.py` ProductsDB/KeywordsDB, `data_kind='live'`) — a scheduled `stock`
   pass (e.g., catalog sweep + a few category searches).
2. **Search first from stock**: the Prospector/Golden Goose "search" reads the stocked
   DB first (fast, zero credits).
3. **Refresh on demand**: if the user searches a product absent from stock (or hits a
   "pull fresh" action), route a live `amazon_search`/`amazon_product` through the
   waterfall, store the result, and serve it.
4. **Honest states**: no fake zeros — missing data renders "—" / "needs pull", never a
   fabricated value.

## 5. Evidence (live pipeline proven)

- `python -c "from agents.golden_goose_finder.free_tier_router import run_task, TASK_AMAZON_SEARCH; from agents.golden_goose_finder.amazon_adapters import make_chocodata_search_caller; c = make_chocodata_search_caller('gift for mom', pages=1); r = run_task(TASK_AMAZON_SEARCH, c, live_armed=True)"`
  → `PROVIDER chocodata MODE live OK True ROWS 60` — 60 real Amazon products returned
  (titles, prices, ASINs), Bright Data fell back to Chocodata via the waterfall.

## 6. Next actions (in priority order)

- [ ] Wire `TASK_WHOLESALE_CATALOG` (Tundra) into the registry + a `stock` runner that
      writes to `data_layer` (ProductsDB) — then Golden Goose scans the stocked catalog.
- [ ] Add a "pull fresh" path in Prospector that routes a live search when the stocked
      DB misses, and stores the result.
- [x] Backfill the remaining free keys (Scrapingdog/Bee/Badger/AmazonScraperApi/APIclaw)
      — DONE 2026-09-22, written to `.env`; also `APIFY_API_TOKEN` stored for a future
      adapter (Apify Sam's Club was removed as a paid source — not wired into the router).
- [ ] Remove demo fixtures from services with live data available; keep honest empty
      states until stocked.
- [ ] Replace Kirkland-era fixtures with the stocked, non-Kirkland data.

## 7. Gates / safety

- Every live pull honors the §3 envelope (`GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1`);
  operator named approval stands for the free-tier channels listed above.
- The credit ledger prevents overrun; providers without keys are skipped, not guessed.
- Nothing here reads or writes `.env` values; the harness stays GREEN.