# Rainforest API Adapter (opt-in, offline-tested)

Status: **built, mock-tested, inert by default.** No live Rainforest request
has been made. No `.env` value was read, printed, copied, or modified — only
the variable *name* `RAINFOREST_API_KEY` is referenced.

Module: `Northstar_backend/rainforest_client.py`
Tests:  `Northstar_backend/test_rainforest_client.py` (26 tests, fully mocked)

## What it is

A typed, explicitly-selected adapter for the [Rainforest Product Data API](https://docs.trajectdata.com/rainforestapi/product-data-api/overview)
that can (once an operator opts in) look up Amazon products and offers and
normalize them into **candidate** records. Every record is
`CANDIDATE_UNVERIFIED`; unknown fields stay `UNKNOWN`; the adapter never
asserts an exact match.

## Official documentation cross-checked

Parameter and response shapes were taken from the official docs (fetched as
documentation only — no API request was made while building this):

| Topic | URL |
| --- | --- |
| Product parameters | https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/product |
| Search parameters | https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/search |
| Offers parameters | https://docs.trajectdata.com/rainforestapi/product-data-api/parameters/offers |
| Product results | https://docs.trajectdata.com/rainforestapi/product-data-api/results/product |
| Search results | https://docs.trajectdata.com/rainforestapi/product-data-api/results/search |
| Offers results | https://docs.trajectdata.com/rainforestapi/product-data-api/results/offers |
| GTIN/UPC/EAN → ASIN | https://docs.trajectdata.com/rainforestapi/product-data-api/reference/gtin-upc-ean-to-asin |
| Supported Amazon domains | https://docs.trajectdata.com/rainforestapi/product-data-api/reference/amazon-domains |
| Response codes | https://docs.trajectdata.com/rainforestapi/response-codes |

Confirmed request facts (from the docs, not guessed):

- Endpoint: `GET https://api.rainforestapi.com/request`, key param `api_key`.
- `type=product` accepts `asin` (+ `amazon_domain`), `gtin` (any
  GTIN/ISBN/UPC/EAN, auto-converted to an ASIN), or `url`.
- `type=search` accepts `search_term` (+ `amazon_domain`). **There is no
  dedicated MPN/model parameter**, so MPN lookup is implemented as a keyword
  `search_term` search.
- `type=offers` accepts `asin`/`gtin` (+ `amazon_domain`) and returns an
  `offers` array of seller offers.
- A plain product/search/offers request is **1 credit**; surcharge flags
  (`skip_gtin_cache`, `include_*`) raise that. This adapter sends **none** of
  them.

Documented response fields used by the normalizer:

- Product: top-level `product{}` with `asin`, `title`, `brand`, `gtin`,
  `buybox_winner{price{value,currency},seller{name,id,rating}}`.
- Search: `search_results[]` with `asin`, `title`, `brand`, `price{value,currency}`,
  `is_prime`.
- Offers: `offers[]` with `price{value,currency}`, `seller{name,id,rating}`,
  `is_prime`, `buybox_winner`, `offer_id`, `condition{is_new}`, plus
  `product{title,asin,brand}`.

## Interface

`RainforestClient` (typed result `RainforestResult`, receipt
`RainforestReceipt`):

| Method | Rainforest request | Purpose |
| --- | --- | --- |
| `product_by_asin(asin)` | `type=product&asin=` | product detail by ASIN |
| `product_by_gtin(gtin)` / `search_by_upc(upc)` | `type=product&gtin=` | search by UPC/GTIN/EAN |
| `search_by_title(title)` | `type=search&search_term=` | title search |
| `search_by_mpn(mpn)` | `type=search&search_term=` | MPN/model keyword search (no dedicated param) |
| `offers_by_asin(asin)` | `type=offers&asin=` | offers / seller view |

## Activation (explicit opt-in only)

Rainforest is selected **only** when explicitly requested:

- Call with `provider="rainforest"`, **or**
- set the explicit routing flag `RAINFOREST_ENABLED=1`.

`rainforest_selected()` gates this. The scanner default
(`SCANNER_SEARCH_SOURCE=BRIGHTDATA`) is **not** changed, and the provider
registry entry is created **disabled by default** (`enabled=False`), so
`ProviderRegistry.execute_read` will refuse it until an operator enables it.

Configuration (variable *names* only):

| Name | Required | Default | Notes |
| --- | --- | --- | --- |
| `RAINFOREST_API_KEY` | yes | — | Missing → `NOT_CONFIGURED`, **no call** |
| `RAINFOREST_REQUEST_URL` | no | `https://api.rainforestapi.com/request` | |
| `RAINFOREST_AMAZON_DOMAIN` | no | `amazon.com` | |
| `RAINFOREST_TIMEOUT_SECONDS` | no | `60` | |
| `RAINFOREST_MAX_REQUESTS` | no | `10` | per-run request cap |

## Safety controls

- **Request cap** (default 10, per client/run) enforced *before* any HTTP call.
- **Dry-run** (`dry_run=True`): plans the request(s) and reports estimated
  credits (1 per request) **without calling** and without consuming the cap.
- **Timeout** on every request; **no automatic retries** (exactly one attempt).
- **Scrubbed receipt**: `provider, operation, status, request_count, dry_run,
  estimated_credits, field_names, notes`. Field **names** only; **never** the
  key, never the request URL/query (which carries the key).
- **No fallback**: a failure is returned as a failure. The adapter does not
  import or call Bright Data, Scavio, Chocodata, or a browser path.

Status vocabulary: `OK`, `NOT_CONFIGURED`, `DRY_RUN`, `HTTP_ERROR`,
`TRANSPORT_ERROR`, `MALFORMED_RESPONSE`, `REQUEST_CAP_REACHED`,
`UNKNOWN_OPERATION`.

## Normalization and hard filters

Each candidate carries: `asin, title, brand, price, price_currency,
buybox_winner, seller_name, seller_id, seller_rating, is_prime, is_new,
offer_id, amazon_is_seller, verification, match_basis, flags`.

- `verification` is always `CANDIDATE_UNVERIFIED`.
- Missing text → `UNKNOWN`; missing price → `None` (never fabricated as `0`).
- `amazon_is_seller`: `True` only for an Amazon-named seller, `False` for a
  known non-Amazon seller, `None` when the seller is unknown.

Hard filters **flag, never drop**:

- `AMAZON_RETAIL_SELLER` — Amazon is the seller.
- `BRAND_DIRECT_SELLER` — seller name matches the product brand.
- `PACK_COUNT_MISMATCH` — title pack/count differs from an expected count
  supplied by the caller.

## Registry integration

`register_rainforest(registry, client=None)` registers a
`ProviderDefinition` (key `rainforest`, `enabled=False`, credential ref
`RAINFOREST_API_KEY` — name only) and binds `RainforestAdapter`. It is
**deliberately not called at startup**, so no existing behavior changes.

## Tests (mock-only)

`test_rainforest_client.py` proves: selection only on explicit request;
default scanner routing untouched; no network contacted (mock client + real
`requests` tripwire); missing key → `NOT_CONFIGURED` with zero calls; request
cap enforced; no fallback and exactly one attempt; dry-run makes no call;
secrets never appear in receipts/results/logs; normalization → unverified
candidates with `UNKNOWN` preserved; hard filters flag without dropping;
registry binds the adapter disabled by default.

Run:

```
cd Northstar_backend
python -m unittest test_rainforest_client -v
```

## Not done (by design)

No live call, no key validation, no `.env` edits, no scanner-routing change.
Enabling live use is a separate, explicitly-approved step.
