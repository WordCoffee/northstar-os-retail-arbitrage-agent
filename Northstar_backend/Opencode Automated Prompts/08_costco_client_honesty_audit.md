STATUS: PENDING

# BATCH 08 — Costco Client Honesty Audit (Offline Only, Pre-Live-Test Requirement)

Prerequisite: Batches 01–07 complete and approved. This batch specifically prepares
`costco_api_client.py` for a trustworthy live test — it was not covered by the
original Phase 0 swallow-pattern audit and must be checked before spending any more
Unwrangle credits.

## Step 1 — Audit `costco_api_client.py` for silent exception swallowing
- Read the entire file. Identify every `except Exception:` / bare `except:` site.
- For each one, determine: does it currently distinguish an auth failure (401/403)
  from "item not found" from a transport/timeout error from a malformed response?
- This matters directly because the last live attempt (item 424976) returned an
  HTTP 403, and the client must be able to clearly report "authorization rejected"
  rather than any ambiguous or generic error.

## Step 2 — Apply typed failure classification
- Using the same pattern established in Batch 02, ensure the Costco client raises or
  returns clearly typed results: `auth_error` (401/403), `rate_limited` (429),
  `not_found` (404 or explicit empty result), `transport_error` (timeout/connection),
  `malformed_response` (schema/parse failure), `success`.
- Never let `auth_error` be reported or logged in a way indistinguishable from
  `not_found`.
- Confirm the client still enforces zero automatic retries (per the existing
  documented "retries=0 / fail-closed" convention used elsewhere in this repo).

## Step 3 — Confirm no credential values are ever logged or persisted
- Check every log statement, print statement, and file-write in the Costco client
  path. Confirm none of them could accidentally write an API key, token, or header
  value into `server.log`, `server2.log`, or any run artifact.
- If any risk is found, fix it (redact/omit) — this is a security requirement, not
  optional.

## Step 4 — Add/extend offline tests
- Add fixture-based tests for the Costco client covering: 200 success, 401, 403, 404,
  429, malformed JSON, and connection timeout — all using mocked responses, zero real
  network calls.
- Confirm the existing `costco` lookup test that skips on missing `COSTCO_CSV_PATH`
  still skips correctly and is unaffected.

## Step 5 — Run and report
- Run: `python -m unittest test_costco_api_client.py test_costco_client.py -v`
  (adjust to actual test filenames if different — locate them first).
- Run the full suite once more.
- Report: is `costco_api_client.py` now confirmed to distinguish auth failures from
  "not found" and from transport errors? This is a precondition for Batch 09.

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`09_costco_credential_diagnostic.md`, append history, stop for approval.
