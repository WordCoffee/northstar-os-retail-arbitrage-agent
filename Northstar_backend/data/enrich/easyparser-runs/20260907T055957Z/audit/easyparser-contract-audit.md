# Easyparser Contract Audit — 10-ASIN Run

Run: `20260907T055957Z` · Determined from the existing `easyparser_client.py` and the
prior live run `manifest-20260822T080742Z-9e71` evidence (raw + normalized files).
No guesswork; anything not evidenced is marked `not_verified`.

## 1. Transport contract (established, prior-live-evidenced)

| Aspect | Verified fact |
|---|---|
| Endpoint | `https://realtime.easyparser.com/v1/request` (GET) |
| Auth | `api_key` query param; value sourced from env `EASYPARSER_API_KEY` via `load_dotenv()`; never logged |
| Platform / operation | `platform=AMZ`, `operation=OFFER`, `domain=.com` |
| Granularity | one ASIN per request (`asin` param) |
| Timeout | `REQUEST_TIMEOUT_SECONDS = 60` |
| Retries | none in client; zero in runner (no `--retries`, loop never re-calls) |
| Polling | none |
| Response envelope | `request_info{success, credits_used, credits_remaining, address.zipCode}`, `request_metadata{created_at, processed_at}`, `result{product, offer.offer_results}` |
| Normalized result | `source="easyparser"`, `asin`, `provider_asin`, `request_id`, `title`, `offer_count`, `offers_returned_count`, `buy_box_*`, `observed_*` counts, `offers[]`, `request_zip_code`, `observed_at`, `credits_used`, `credits_remaining`, `data_gaps` |
| Cost metadata | provider-reported `credits_used` / `credits_remaining` per response |
| Fail-closed | missing key → gap `"Easyparser API key is not configured."`; no network call made |
| Identity | `provider_asin` must equal requested ASIN; mismatch now recorded as `mapping_error` and rejected (raw preserved) |

## 2. Prior live evidence (2026-08-22, retained read-only)

- 9 real requests (`manifest-20260822T080742Z-9e71`), stopped by credit cap.
- Provider-reported credits per request: 10, 11, 12, 13, 14, 15 (varied; internally
  not perfectly self-consistent with the `credits_remaining` series — treated as
  provider-reported metadata only, never assumed).
- ZIP `19805`; seller-level offers with ratings, FBA/FBM flags, shipping text.

## 3. Fields Easyparser OFFER supplies live

title · offer_count · offers_returned_count · per-offer: position, buybox_winner,
price (raw/symbol/value), condition, seller_id, seller_name, seller_rating,
seller_positive_percentage, seller_ratings_total, is_prime, is_fba, is_fbm, is_sba,
fulfilled_by_amazon, shipping_text, shipping_is_free, ships_from, min/max order qty ·
Buy Box: price, seller, seller_id, is_fba, is_fbm, is_prime, condition ·
observed FBA/FBM/Amazon offer counts · request_zip_code · observed_at · credits_used/remaining.

## 4. Fields Easyparser OFFER does NOT supply

- Amazon **BSR / sales rank** (comparison uses "provider does not supply BSR").
- **Review count** (comparison uses `reviews_live = "Unknown"`; never zero-filled).
- UPC / EAN / GTIN, brand, item weight, monthly sales, seller wrapper counts.

## 5. Mapping/identity handling

Wrong or missing ASIN → `mapping_error=True`, data gap, snapshot forced to
`unavailable`, ledger flag set; raw response still persisted for evidence. No retry.

## 6. Contract defects found

None. `load_and_validate_manifest` enforces the 10-ASIN hard limit, approved-set
membership, canonical order, unique ASINs, and required CSV fields before any network
path is reachable. See `easyparser-field-capability-matrix.json` for the field map.