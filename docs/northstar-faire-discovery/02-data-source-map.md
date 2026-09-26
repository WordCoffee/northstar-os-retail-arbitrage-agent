# 02 — Data Source Map

Preference order for each source (per spec DATA-ACCESS RULES).

## Faire (discovery)

1. Authorized official APIs — none available.
2. Existing Northstar adapters — none for Faire.
3. Operator-supplied exports (line sheets, catalog files) — **preferred**.
4. Operator-approved authenticated browser session — permitted (operator must authorize).
5. Publicly accessible product/brand pages.
6. Cached data with explicit timestamp.

Observed Faire surface (this session, authenticated, discovery only):
- Product search (JSON): `POST https://www.faire.com/api/v3/search/products` body `{"query","page_number","page_size"}` → `product_tiles[].{product{token,name,brand_token}, min_option_wholesale_price, min_option_retail_price, brand_review_count, ...}`. Pricing visible only when authenticated → `AUTHENTICATED_FAIRE_REFERENCE`.

## Amazon (matching)

Authorized Amazon SP-API / seller reports / Amazon calculators / approved third
party providers / existing timestamped Northstar caches / operator files /
public pages where permitted. **No unauthorized scraping.**

Existing Northstar Amazon evidence (reusable, timestamped):
| Cache | ASINs | Fields |
|---|---|---|
| `data/seller-offer-cache.json` | 247 | total_sellers, fba_sellers, fbm_sellers, amazon_sellers, buy_box, offers, title |
| `data/enriched-offer-cache.json` | 263 | amazon_price, buy_box_price, fba_fee, buy_box_seller, buy_box_fulfillment, title |
| `Northstar_backend/data/scanner-search-cache.enriched-candidate.json` | 10 | full: price, sellers, weight_lbs, net_profit, roi_pct |

Live Amazon provider adapters available in-repo: `bright_data_client`
(`search_products`, `get_product_detail`), `offer_enrichment`
(`get_seller_offer_contract`), EasyParser. All honour `SCANNER_LIVE_ALLOWED`
and/or the Golden Goose envelope.

## Provider registry / cost

Reuse `foundation/providers.py` (definitions/capabilities/health; fixtures only)
and the existing free-tier registry. Bright Data Web Unlocker ≈ 1 credit/request
(free 5,000/month pool). Full per-ASIN enrichment ≈ 2–3 requests
(search + detail + optional offers).

## Provenance

Every record carries: org_id, source, source_record_id, capture time, effective
time, provenance class, confidence, staleness, created/updated by, correlation
id (see `faire-discovery-schema.json`). Faire wholesale values are stamped
`AUTHENTICATED_FAIRE_REFERENCE` / `DISCOVERY_BENCHMARK_ONLY`.
