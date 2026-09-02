STATUS: COMPLETE

# BATCH 02 — Provider Safety & Data Honesty (Account Safety + Honesty Risk)

Prerequisite: Batch 01 complete and approved.

## Step 1 — Fix `_enrichment_mode()` silent remap (highest-risk item in this whole plan)
- Show the current function body before changing anything.
- The docstring says DEPRECATED/DISABLED provider tokens (including `EASYPARSER` and
  generic truthy values) should map to OFF. The code currently remaps them to
  `RAPIDAPI` instead — meaning a "disabled" config could silently enable a live,
  credit-spending provider.
- Fix the function to match the docstring's intent: OFF means OFF.
- Before changing, check whether any currently-passing test relies on the incorrect
  remap behavior. If one does, flag it explicitly — do not just delete or rewrite that
  test without noting it.
- Update `test_scanner_cache_only.py` so `test_provider_tokens_remain_explicit_optins`
  and all 7 `test_boolean_values_enable_default_provider` cases assert the corrected,
  safe behavior.
- Run: `python -m unittest test_scanner_cache_only.py -v`

## Step 2 — Fix silent exception swallowing (data honesty)
Apply this pattern everywhere below: never let an authentication/authorization failure
(401/403), a transport error, or a malformed response look identical to "no data found."

- `offer_enrichment.py`: `_fetch_chocodata_product` and `_fetch_unwrangle_amazon_detail`
  currently use `except Exception: return {}`. Replace with typed failure classification
  (e.g., `auth_error`, `transport_error`, `malformed_response`, `no_data_found`) and
  propagate that classification to the caller instead of swallowing it into an empty dict.
- `scavio_client.py:81` and `bright_data_client.py:435` use
  `except Exception as e: print(...)`. Replace the bare print-and-swallow with the same
  typed classification approach — raise or return a typed result, don't just log and drop it.
- `dataforseo_adapter.py` — inspect the 4 `except Exception:` sites (approx. lines
  55, 60, 203, 297). For each one, show the current behavior. Only change the ones that
  actually swallow a failure silently; leave any that already raise `GuardError` or
  `AmbiguousTransportError` correctly alone.

## Step 3 — Fix `enrichment_status` conflating "offline" and "failed"
- `test_offer_enrichment.py::test_failed_fetch_is_never_cached` expects
  `enrichment_status="failed"` but the code currently returns `"offline"`.
- Introduce distinct, explicit statuses: `no_provider_configured`, `provider_rejected`,
  `pending`, `offline_mode`. A provider-side rejection must never be reported the same
  way as "no provider is configured right now."
- Update the test to assert the corrected, more precise status vocabulary.
- Run: `python -m unittest test_offer_enrichment.py -v` and note how many of the 12
  original failures in this file are now resolved (some may require Batch 03 as well —
  that's expected, just report the count here).

## Step 4 — Re-run the affected suites
- `python -m unittest test_scanner_cache_only.py test_offer_enrichment.py -v`
- Report before/after failure counts for these two files specifically.

## Step 5 — Full suite check
- `python -m unittest discover -s . -p "test_*.py"`
- `node test_ui_display.cjs`
- Compare totals against Batch 01's ending totals (not the original baseline).

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`03_remaining_test_failures.md`, append history, stop for approval.
