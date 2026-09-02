STATUS: PENDING

# BATCH 04 — BSR Evidence Contract & Comparison Engine (Offline Only)

Prerequisite: Batches 01–03 complete and approved. Test suite should be clean or
near-clean at this point.

## Step 1 — First-class BSR evidence contract
- Implement or extend the appropriate schema module so BSR is a structured field set,
  not a loose string:
  `bsr_primary_rank`, `bsr_primary_category`, `bsr_secondary_rank`,
  `bsr_secondary_category`, `bsr_raw`, `bsr_capture_status`, `bsr_source`,
  `bsr_captured_at`.
- Valid `bsr_capture_status` values: `verified`, `missing_live`,
  `missing_csv_reference`, `provider_not_supported`, `parse_error`,
  `identity_conflict`, `unavailable`.
- Never infer BSR from price, reviews, or category. Never convert
  "Not listed on page" or an absent value into rank zero.
- Preserve the raw source text separately from any parsed numeric rank.

## Step 2 — Normalized snapshot contract
- Ensure a single provider-neutral snapshot shape can hold: identity fields, price,
  reviews, fulfillment, BSR (as above), seller/offer evidence, Buy Box evidence,
  timestamps, provider metadata, raw response reference, normalized reference, and
  error/reconciliation state.
- Add field-completeness classification per field: `captured`, `unavailable`,
  `provider_not_supported`, `parse_error`, `identity_conflict`, `not_requested`.
- A missing field must never be treated as zero or a negative signal on its own.

## Step 3 — Offline comparison engine
- Build or extend a comparison function that takes a benchmark record and a
  (synthetic, for now) normalized live snapshot and produces:
  `identity_match_status`, `title_similarity`, `pack_match`, price delta
  (absolute + percent), reviews delta, fulfillment match status, BSR comparison
  status, and an overall disposition: `matched`, `normal_market_drift`,
  `provider_field_gap`, `mapping_conflict`, `provider_error`, `insufficient_data`,
  `needs_manual_review`.
- Price drift within a reasonable, documented tolerance = `normal_market_drift`,
  not a failure.
- BSR rank comparison only when both sides share the same category; otherwise mark
  drift/missing rather than inventing a delta.
- The benchmark CSV data must never be overwritten by comparison output.

## Step 4 — Offline tests
- Add fixture-based tests covering: full capture, missing BSR, BSR
  provider_not_supported, wrong ASIN, title/pack conflict, provider rejection, no raw
  evidence, parse error, normal price drift, abnormal price delta, review growth,
  review decrease, BSR same-category drift, BSR category mismatch, benchmark BSR
  missing, live BSR missing.
- No live calls — all fixtures are synthetic/hardcoded test data.

## Step 5 — Run and report
- Run the relevant new/updated test file(s) plus the full suite:
  `python -m unittest discover -s . -p "test_*.py"`
- Confirm no protected file (CSV/benchmark/cache/catalog) was modified — only new
  schema/comparison code and new test fixtures were added.

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`05_ui_evidence_polish.md`, append history, stop for approval.
