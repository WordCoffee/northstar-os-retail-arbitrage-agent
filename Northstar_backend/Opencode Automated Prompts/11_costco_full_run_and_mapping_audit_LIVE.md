STATUS: PENDING

# BATCH 11 — Costco Full 15-Item Live Run + Mapping Audit — LIVE AUTHORIZED

Prerequisite: Batch 10 succeeded (single-item retry confirmed working) AND operator
has explicitly approved this batch by name.

LIVE AUTHORIZED — up to 14 additional outbound requests permitted (item 424976 was
already completed in Batch 10 and must not be re-requested).

## Step 1 — Pre-flight
- Confirm run_id `20260828T021658Z` and manifest fingerprint
  `e325264fa989758d93c11b72eb7c12d833e7800dc28611bac7ed6ed8bd7de3db` still match.
- Confirm item `424976` is already recorded as complete from Batch 10 — skip it.
- List the remaining 14 item IDs to be requested:
  926628, 1586629, 1349614, 1493188, 1665191, 690843, 393914, 98268, 98501, 98211,
  1089787, 87507, 1652990, 1755436.

## Step 2 — Live requests (LIVE AUTHORIZED, max 14, zero retries)
- Run: `python costco_api_client.py details refresh --item-ids <the 14 remaining IDs>`
- One attempt per item. On any single-item failure (auth, rate-limit, malformed,
  identity mismatch): persist whatever items already completed successfully, record
  the failure in a scrubbed failure manifest, and STOP processing further items in
  this run. Do not skip-and-continue past a hard failure without reporting it first.

## Step 3 — Persist and normalize
- Same run directory, same normalized field contract as Batch 10.
- Every item gets its own raw + normalized record regardless of success/failure.

## Step 4 — Mapping / pack audit against the Amazon benchmark CSVs
For every successfully retrieved item, cross-check against the existing benchmark CSVs
and flag explicitly:
- Aller-Flo (1586629): confirm 5 bottles / 720 sprays matches Costco's actual pack
  description.
- Glucosamine & Chondroitin (1665191): confirm 280-tablet count; note the known
  220-count discrepancy against the Amazon-side benchmark product.
- Flex-Tech 13-gal trash bags (1089787): confirm 200-count and gallon rating.
- 10-gal Wastebasket Liner (87507): confirm 500-count and gallon rating vs. Amazon
  ASIN B01M7Y0NEX (from prior evidence).
- 18-gal Compactor & Kitchen Trash Bag (1755436): confirm 70-count and gallon rating.
- Baby Wipes (1493188) and Flushable Wipes (1652990): confirm exact wipe count and
  pack configuration (e.g., 9×100).
- For every other item, confirm title/brand/pack alignment; flag anything ambiguous
  as `manual_review_required`, never silently accepted.

## Step 5 — Final report
- Requests attempted / completed / errored / unattempted.
- Full table: item ID, returned title, price, pack/count, UPC, weight, availability,
  identity match status, missing fields.
- All pack/mapping warnings from Step 4, explicitly flagged.
- Provider-reported cost/credits if available; otherwise "not reported by provider."
- Explicit statement: "All Costco API output is discovery-only evidence. It does not
  establish invoice-backed sourcing, Amazon sellability, purchase authorization, or
  durable unit economics."
- Do NOT run any follow-up Amazon comparison, enrichment, export, or purchase workflow
  in this batch — that requires a separate future authorization.

## End of batch (final batch in this file system)
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`null` (no more batches queued), append a final history entry summarizing the entire
run from Batch 01 through Batch 11. Stop and wait for the operator's next instruction
— there is no automatic Batch 12.
