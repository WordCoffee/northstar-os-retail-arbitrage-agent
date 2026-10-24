# Rainforest Adapter — Build Report

**Task:** Build a Rainforest API adapter, offline and mock-only.
**Status:** DONE. No live call made. No `.env` value read/printed/copied/modified.
**Commit:** `665be71` on `feature/creative-social-local` (3 files, +1209).

## Deliverables

| File | Purpose |
| --- | --- |
| `Northstar_backend/rainforest_client.py` | Typed, opt-in adapter (697 lines) |
| `Northstar_backend/test_rainforest_client.py` | 26 mock-only tests |
| `docs/RAINFOREST_ADAPTER.md` | Adapter docs + doc URLs |

## Hard rules — how they are met

- **No network / no live request / no key validation:** every test uses an
  injected mock HTTP client; a real-`requests` tripwire (network guard)
  confirms an unmocked path raises rather than reaching the network.
- **No `.env` value touched:** only the *name* `RAINFOREST_API_KEY` is
  referenced. `.env` not edited.
- **No change to Bright Data / scanner defaults:** `SCANNER_SEARCH_SOURCE`
  remains `BRIGHTDATA` (asserted in tests). Rainforest is **opt-in only** —
  `rainforest_selected()` requires `provider="rainforest"` or
  `RAINFOREST_ENABLED=1`.
- **Explicit provider name `rainforest`:** `register_rainforest(registry)`
  registers a disabled-by-default `ProviderDefinition` and binds
  `RainforestAdapter`. Not called at startup.
- **Required config:** missing `RAINFOREST_API_KEY` → `NOT_CONFIGURED`, zero
  calls.
- **No silent fallback:** failures return an error; exactly one attempt, no
  retry; module imports no other provider.
- **Safety controls:** per-run cap (default 10) enforced before any call;
  dry-run plans requests + estimated credits without calling; timeout on every
  request; scrubbed receipt (`provider, operation, status, request_count,
  dry_run, estimated_credits, field_names, notes`) — never the key.
- **Normalizer:** `CANDIDATE_UNVERIFIED` always; unknown → `UNKNOWN`; missing
  price → `None` (never 0); `amazon_is_seller` True/False/None.
- **Hard filters:** `AMAZON_RETAIL_SELLER`, `BRAND_DIRECT_SELLER`,
  `PACK_COUNT_MISMATCH` — flagged, never dropped.

## API contract source (documentation only, no API request)

Field/param names confirmed against official Traject Data docs:
product/search/offers parameters and results, GTIN→ASIN guide, response codes.
Full URL list in `docs/RAINFOREST_ADAPTER.md`. No field names were guessed.

## Verification

- `python -m unittest test_rainforest_client -v` → **26 tests, OK**.
- Regression batch (`test_network_guard`, `test_bright_data_client`,
  `test_amazon_search`, `test_scavio_client`, `test_universal_search`) →
  **96 tests, OK**.

## Not done (by design)

No live Rainforest call. Enabling live use (owner sets a well-formed
`RAINFOREST_API_KEY`, enables the provider, approves a named request count) is
a separate explicit step.
