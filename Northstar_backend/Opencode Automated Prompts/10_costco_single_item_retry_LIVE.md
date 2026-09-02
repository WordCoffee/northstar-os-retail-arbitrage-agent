STATUS: PENDING

# BATCH 10 — Costco Single-Item Retry — LIVE AUTHORIZED (1 request only)

Prerequisite: Batch 09 complete. Operator has confirmed, outside this session, that
the credential/config issue identified in Batch 09 has been fixed. Do NOT run this
batch on an approval message alone — the approval must explicitly state the fix is in
place. If it doesn't, stop and ask before proceeding.

LIVE AUTHORIZED — exactly ONE outbound request to the Costco/Unwrangle API is
permitted in this batch, targeting item `424976` only.

## Step 1 — Pre-flight confirmation (no network call yet)
- Confirm presence-only (not values) of the required env var(s) identified in
  Batch 09. Report `SET` / `NOT SET` for each.
- Confirm the frozen manifest at `data/costco-discovery-runs/20260828T021658Z/` still
  matches fingerprint `e325264fa989758d93c11b72eb7c12d833e7800dc28611bac7ed6ed8bd7de3db`.
- If any required variable is `NOT SET`, STOP — do not attempt the call. Report this
  and wait for the operator.

## Step 2 — Single-item live call (LIVE AUTHORIZED)
- Run the existing verified client path for exactly ONE item:
  `python costco_api_client.py details refresh --item-ids 424976`
- Zero retries. If it fails again (any non-2xx), stop immediately — do not attempt a
  second call in this session.

## Step 3 — Persist result
- Store the result under the SAME run directory:
  `data/costco-discovery-runs/20260828T021658Z/raw/` and `.../normalized/`
  (do not create a new run_id for this confirmation retry — it belongs to the same
  frozen batch).
- Required normalized fields per the original authorization: requested_item_id,
  returned_costco_item_id, exact_title, brand, listed_price, currency, unit_price,
  quantity_or_pack, size_or_weight, UPC_GTIN_EAN, availability, product_url,
  captured_at, provider=UNWRANGLE_COSTCO, source=costco_api,
  sourcing_status=discovery_only, purchase_authorized=false,
  raw_response_reference, normalized_response_reference, missing_fields,
  identity_match_status.

## Step 4 — Report
- Success or failure, exact HTTP status, whether identity fields (title, pack) came
  back and match the requested "Adult 50+ Mature Multi, 400 Tablets."
- Provider-reported cost/credits if exposed; otherwise "not reported by provider."
- Explicit statement: "This Costco result is discovery-only evidence. It does not
  establish invoice-backed sourcing or purchase authorization."

## Step 5 — Gate the next batch
- If Step 2 succeeded: state "Credential issue resolved. Ready for Batch 11
  (full 15-item live run) pending explicit operator approval."
- If Step 2 failed: state "Credential/config issue NOT resolved. Do not proceed to
  Batch 11. Recommend re-running Batch 09's diagnostic with the new error evidence."
  Do not retry automatically.

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches` ONLY if Step 2
succeeded; otherwise leave `next_batch` unchanged and add this batch to
`blocked_batches` with the reason. Append history either way. Stop for approval.
