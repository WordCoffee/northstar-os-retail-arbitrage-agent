# Budget-Cap Patch — Offline Test Report
Run: 20260907T055957Z (post-live audit) · Date: 2026-09-07

## Scope / method
Code-and-test only. No provider calls. No reads of `.env`/credential values.
No edits to finance.py, pricing.py, product_analysis.py, fee_engine.py, CSV
truth files, provider client endpoints, retry behavior, or ASIN selection.
No modification of any completed run artifact. The 20260907T055957Z live run
is untouched. All tests are zero-network (network_guard installed process-wide;
collection forced to ignore 5 pre-existing `test_*.txt` junk files dated
Aug 20-22 that are NOT part of the suite).

## Changed files
1. `enrich_manifest_run.py` — code guard only:
   - added `WORST_CASE_REQUEST_CREDITS = 30` (module constant, documented);
   - pre-call guard changed from `credits_used >= max_credits`
     to `credits_used + WORST_CASE_REQUEST_CREDITS > max_credits`;
   - module docstring updated to state the reservation + post-call-stop semantics.
2. `test_enrich_manifest_runner.py` — tests:
   - `test_11_max_credits_cap_stops_with_reason` updated (cap 6 < reserve 30 ⇒
     0 calls, 10 skipped_cap, summary still reports max_credits);
   - added `WorstCaseBudgetGuardTests` with test_25..test_32.

## New behavior coverage (all passing)
| Test | Behavior verified |
|---|---|
| test_25 | cap 200, mock cost 30 ⇒ exactly 6 requests, 180 credits, 7th refused |
| test_26 | 7th ASIN refused before any provider call (skipped_cap, credits=0) |
| test_27 | cap 40 + reserve 30 ⇒ exactly 1 request |
| test_28 | cap < 30 ⇒ refuses before the FIRST call (0 calls, 10 skipped_cap) |
| test_29 | reported cost 29 recorded as 29 (not 30); total 174 |
| test_30 | reported cost 35 > 30 recorded honestly, then run stops (1 request) |
| test_31 | no automatic retry under cap pressure (6 unique calls, no repeats) |
| test_32 | request count never exceeds manifest limit (10 and 6 in two runs); every manifest ASIN appears once in the ledger |
| test_11 (updated) | implied-hard portability: reserve > cap ⇒ zero provider calls |

## Test results (real output)
Targeted suites:
`python -m pytest test_enrich_manifest_runner.py test_easyparser_client.py test_network_guard.py test_live_containment.py -q`
→ **71 passed** (Easyparser runner 39, client + network-guard + live-containment 32).

Full offline suite:
`python -m pytest -q --ignore=test_out.txt --ignore=test_output.txt --ignore=test_rerun.txt --ignore=test_run.txt --ignore=test_summary.txt`
→ **1429 passed, 3 skipped, 35 subtests passed** in 99.99s.

Skipped = 3 (pre-existing, unrelated; the canonical baseline skips).

## Exact new budget behavior
- Before each Easyparser request: if `credits_used + 30 > max_credits`, refuse the
  request (`stop_reason="max_credits"`), mark remaining manifest ASINs `skipped_cap`,
  and make **zero** further provider calls.
- After each successful call: provider-reported `credits_used` recorded verbatim
  (`credit_basis="reported"`); never replaced by 30. Missing/invalid reported cost
  still falls back to `ESTIMATED_CREDITS_PER_ASIN` (unchanged).
- `--max-requests` cap, zero retries, exact ASIN order all unchanged.
- No USD conversion anywhere in the guard (no verified pricing source; none added).

## Cap semantics statement
The new cap is a **worst-case pre-request reservation plus post-call stop** — it is
**NOT a true hard spend cap**. It guarantees no request is *issued* once the
worst-case reservation would push the run past `max_credits`, and that after an
over-cap spend a run stops and issues no further request. It does not guarantee the
reported cumulative spend can never exceed `max_credits` (a single in-flight call
may overshoot; e.g. observed 225 vs 200 in the prior run). With the reservation, a
200-credit cap now spends at most 180 reported credits (6 requests) at the 30-cost
level instead of overshooting to 225.

## Confirmations
- No provider/network calls occurred (all tests zero-network; guard refuses
  pre-call).
- No live command run; B085F1QCB9 was not requested and remains unqueried.
- Live artifacts of 20260907T055957Z unchanged.
