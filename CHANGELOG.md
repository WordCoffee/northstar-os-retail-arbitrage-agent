# Changelog

## 2026-09-07 — Easyparser budget guard: worst-case pre-request reservation

**Files changed**
- `Northstar_backend/enrich_manifest_run.py`
- `Northstar_backend/test_enrich_manifest_runner.py`
- `Northstar_backend/data/enrich/easyparser-runs/20260907T055957Z/audit/budget-patch-test-report.md` (new)

**Change**
Replaced the Easyparser enrichment runner's credit-cap pre-check
(`budget["credits_used"] >= max_credits`, a plain trip-wire that could overshoot by
one call's cost — observed 225 vs a 200 cap in live run 20260907T055957Z) with a
**worst-case pre-request reservation plus post-call stop**:

- `WORST_CASE_REQUEST_CREDITS = 30` (covers the observed 21–29 reported per OFFER
  request; no stricter provider-confirmed max exists in project config).
- Before every call: refuse when `credits_used + WORST_CASE_REQUEST_CREDITS >
  max_credits` → `stop_reason = "max_credits"` and no further request is issued.
- Provider-reported `credits_used` is still recorded verbatim (never replaced by
  the reservation); estimated fallback and the `--max-requests` cap unchanged.
- Retry behavior unchanged (structurally zero retries).
- ASIN manifest selection, provider endpoints, and all prior run artifacts unchanged.

**Semantics statement**
This is a **worst-case pre-request reservation plus post-call stop**, not a true
hard spend cap: a single in-flight call can still consume more than expected, after
which the run stops and issues no further request. It guarantees no request is
*issued* once the reservation would exceed the cap; it cannot undo an in-flight
overspend.

**Tests**
`test_enrich_manifest_runner.py` +8 new (test_25..test_32); test_11 updated for the
new semantics. Targeted suites + full offline suite: 1429 passed, 3 skipped, 35
subtests passed.
