# Budget Enforcement Audit — run 20260907T055957Z (CLI manifest-20260907T061811Z-98b7)

Audit method: offline read of `request-log.jsonl`, `live/raw`, `live/normalized`, `live-run-metadata.json`, `review/run-summary.json`, and the runner source `enrich_manifest_run.py`. No provider calls, no credential reads, no live-artifact edits.

## 1. Configured caps
- `--max-requests 10`, `--max-credits 200` (frozen manifest, single run).
- `ESTIMATED_CREDITS_PER_ASIN = 5.0` (used ONLY when a response carries no reported credit cost).

## 2. Per-request ledger (provider-reported)
| seq | asin | credits_this_call (reported) | cumulative BEFORE | cumulative AFTER | reported remaining |
|---|---|---:|---:|---:|---:|
| 1 | B01H40O42I | 21 | 0.0 | 21.0 | 79 |
| 2 | B08R2SRN88 | 22 | 21.0 | 43.0 | 78 |
| 3 | B0CP6LXPLK | 23 | 43.0 | 66.0 | 77 |
| 4 | B00BISGJXA | 24 | 66.0 | 90.0 | 76 |
| 5 | B00BH3HPZW | 25 | 90.0 | 115.0 | 75 |
| 6 | B00GYZWNY6 | 26 | 115.0 | 141.0 | 74 |
| 7 | B0045XGE9E | 27 | 141.0 | 168.0 | 73 |
| 8 | B002L4M4M0 | 28 | 168.0 | 196.0 | 72 |
| 9 | B081THWMDK | 29 | 196.0 | 225.0 | 71 |
| 10 | B085F1QCB9 | — (no call) | 225.0 | 225.0 | — |

## 3. Why 225 credits were allowed against a 200 cap
The runner checks the cap BEFORE each call and adds the reported cost AFTER the call (`enrich_manifest_run.py` line 593: `if budget['credits_used'] >= caps['max_credits']: break`, lines 600-609: `budget['credits_used'] += used` after `_fetch_offers`).

Sequence: before call 9 the cumulative was 196.0 (< 200), so the call was allowed; its reported cost was 29 → cumulative 225.0. Before call 10 the check (225.0 >= 200) fired, so B085F1QCB9 was `skipped_cap`. Net effect: the effective spend overshot the 200 cap by one call's cost (29 reported).

## 4. Hard cap vs pre-request cap
- The current implementation provides a **pre-request (soft) cap**: it refuses to *start* a new call once `credits_used >= max_credits`, but it cannot prevent a single in-flight call from consuming more than the remaining budget. Overshoot of up to one call's cost is structurally possible (observed here: 25 over).
- There is **no post-call hard cap**: spend already incurred is not reversible, and no further call is made after the check fires.
- The request cap (10) and the credit cap are both pre-request checks; the credit cap fired first.

## 5. Recommended smallest change (described only — no code edited in this audit)
Target: refuse a request when worst-case cost would exceed the remaining budget, never exceed the configured hard cap, preserve reported usage, no auto-retry, no alteration of existing run artifacts.

1. Add an explicit worst-case-per-request figure, e.g. `WORST_CASE_CREDITS = 30` near the other budget constants (or a `--max-credits-per-request` CLI flag; 30 covers the observed 21-29 range).
2. Change the pre-call guard (line 593) from
   `if budget['credits_used'] >= caps['max_credits']:`
   to
   `if budget['credits_used'] + WORST_CASE_CREDITS > caps['max_credits']:`
   With cap=200 and worst-case reserve=30, `cumulative + 30 > 200` allows calls 1-8 (cumulative after 8 = 196) and refuses call 9 (196 + 30 = 226 > 200): spend stops at 196, never exceeding 200. Exact count depends on the reserve constant; the invariant is `cumulative + reserve > cap → stop`.
3. Keep the post-call accumulation exactly as-is (`credit_basis='reported'`, `credits_reported`) so provider-reported usage is preserved verbatim; optionally append `reserved_worst_case` and `pre_check_cumulative` to the ledger for future auditability.
4. Add one offline/mocked test (pattern of `test_enrich_manifest_runner.py::test_21..24`): each mock response reports 30 credits, cap=200 with reserve 30 → assert the run makes 6 requests (180 total), stops with `stop_reason='max_credits'`, ledger preserves reported 30/request, and no ASIN is retried.

## 6. Credit-usage reconciliation
- Sum of per-call reported credits: 21+22+23+24+25+26+27+28+29 = **225**, matching every artifact (`run-summary.md` credits_used=225.0, `live-run-metadata.json` credits_reported_used=225, run-index, CLI stdout).
- Provider-reported `credits_remaining` series (79,78,...,71) implies a 100-point balance dropping 1/call — **inconsistent** with credits_used (21-29/call). Both values are provider metadata recorded verbatim; the true ledger is unknowable without provider-side account data. USD cost remains unverified (no rate table).

Conclusion: 225 is *internally* reconciled (sum of reported per-call costs, everywhere consistent), but the provider series are self-contradictory, so it is **not independently verifiable**; the configured cap should be treated as a trip-wire, not a hard budget.
