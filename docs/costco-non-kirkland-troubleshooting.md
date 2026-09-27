# Costco Non-Kirkland Pipeline — Troubleshooting

## Network calls must be zero

Every command prints `Network calls made: 0`. If you ever see a nonzero count
(or a command that attempts network access), stop — the offline invariant is
broken. The package never crawls Costco, SellerAmp, or Amazon, and
never uses browser automation.

## Import reports all rows as `identity_ambiguous`

- The ASIN column was missing or invalid. ASINs must be exactly 10 alphanumeric
  characters (`^[A-Z0-9]{10}$`).
- Confirm your export actually contains an `asin` column and that it's not empty.

## Import reports `needs_mapping`

- A column/key wasn't recognized by the provider schema. Add it to
  `costco_non_kirkland/provider_imports/schemas.py` (the CSV/JSON mapping dict
  for the provider) and re-import.
- If provider detection was ambiguous, pass `--provider selleramp` explicitly.
  (Retired `sellersprite` files are rejected as unsupported.)

## Import reports `missing_required_fields`

- Identity fields (`asin`, `title`) are missing, or strict mode found a missing
  required qualification field.
- Re-export from the provider with the full field set, or use `--allow-partial`
  to save rows as `needs_enrichment` instead.

## Everything is `stale`

- The snapshot's observed time is older than the configured freshness window
  (`market_snapshot_max_age_minutes`, default 60; `source_price_max_age_minutes`,
  default 60). Re-export fresh data from the provider.

## Duplicates on re-import

That's correct behavior: the same file (same SHA-256 + row) reports
`duplicate` rather than creating new snapshots. Idempotency is by design.

## Candidates all `needs_enrichment`

- Required marketplace fields are unknown (Amazon Retail, FBA/MFN counts,
  sellability, restriction, buy-box price). Unknown is never favorable — the
  candidate cannot qualify without provider-reported completeness.

## Candidates blocked

- Amazon Retail active, brand-owner seller active, active FBA competition,
  too few MFN sellers, overweight, restricted, or a hard identity/policy issue.
- Check the `reason_codes` and `risk_flags` on the candidate decision.

## Approval grant fails

Possible causes (all fail-closed):
- candidate is blocked / needs enrichment / manual review / not grant-eligible,
- identity is not exact,
- source price is stale,
- provider snapshot is stale,
- economics is not `complete`,
- quantity exceeds `approval_max_quantity` (default 200).

## I need to change thresholds

Edit `costco_non_kirkland/settings.py` (`DEFAULT_SETTINGS`) or set
`NORTHSTAR_<NAME>` env vars (non-secret). Thresholds include MFN/FBA counts,
weight, profit, ROI, and freshness windows.

## Provider licensing / account limits

- You are responsible for SellerAmp account terms and keeping
  credentials secret. The pipeline never authenticates.
- Provider exports may omit fields; missing values remain `not_reported`.
- Do not purchase based solely on an automated recommendation — always use the
  human approval record.