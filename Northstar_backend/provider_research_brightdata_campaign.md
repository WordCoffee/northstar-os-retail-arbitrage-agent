# Bright Data Costco - Identity-Enrichment Campaign (dry-run)

- Campaign ID: bd-costco-identity-20260927T231732Z
- Collector: gd_mkcbmac44j178pook · Costco products — Collect by URL
- Target identity-ready: 50-100
- Input cap: 150 URLs · credit cap: 250 free · paid cap: $0.0
- Manifest size: 48 · chunks: 2 × 25
- Network calls made: 0

## Filter counts
- eligible: 181
- kirkland_or_disallowed: 0
- no_brand: 0
- no_price: 0
- no_verified_url: 0
- previously_submitted: 7
- duplicate_url: 8
- excluded_category: 0
- food_beverage: 0
- high_cogs_over_100: 65
- oversized_poor_fit: 37
- after_filters: 64

## Diversification: {"apparel": 9, "cleaning": 7, "home": 5, "kitchen": 5, "other": 15, "outdoor": 2, "pet": 2, "sports": 2, "tools": 1}
- max brand count: 3 (cap 5)
- why fewer than cap: only 48 records pass Costco-side filters; 150 cap not reached

## Stop conditions
- paid_charge_or_billing_change
- credits_exceed_250
- collector_schema_change
- mapping_failure_over_20pct_in_chunk
- gtin_mpn_coverage_under_25pct_after_first_50
- 100_identity_ready_reached
- 150_inputs_exhausted