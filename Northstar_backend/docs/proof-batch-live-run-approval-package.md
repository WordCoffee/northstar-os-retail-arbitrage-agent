# Proof Batch — Live-Run Approval Package

Local Northstar_backend project, T2 Holdings LLC.
Fixed 20-ASIN Easyparser provider-data-contract validation.

This package is the single hand-off for one future, separately approved, live
Easyparser validation run. It is **documentation only**. No command in this
file was executed. No provider/network/API/HTTP call was made. No credit was
consumed. No live snapshot, secret, or protected artifact was touched.

---

## 1. Exact fixed preflight path

```
data/batch/proof-batch-preflight-20260818T060549Z.json
```

Do not substitute, regenerate, or re-source the ASIN list. It is the only
authorized source of the 20 ASINs.

## 2. Exact preflight fingerprint

```
eb21a9877ce5b27c2aed55fe835d2a8712fbc28a44d2082ce30b6262b6b7478d
```

The run re-computes this fingerprint from the named preflight and refuses if it
drifts from the authorized value embedded in any persisted artifact.

## 3. Exact 20-ASIN list (canonical, in preflight order)

```
B01H40O42I
B08R2SRN88
B0CP6LXPLK
B00BISGJXA
B00BH3HPZW
B00GYZWNY6
B0045XGE9E
B002L4M4M0
B081THWMDK
B085F1QCB9
B00N54AJZE
B00QGMOJ4Y
B01LY71217
B07BZW88NY
B078B5N4DD
B007MWNFBA
B00OPQZJA6
B0C54GXFQ8
B0F7GTX962
B00BI33NU2
```

## 4. Provider

EASYPARSER only. No Keepa, Bright Data, Costco, Scavio, Canopy, Amazon search,
or browser automation.

## 5. Fields

`market_offers` only.

## 6. Request cap

20 provider requests maximum (exactly one ASIN per request). Retries: **zero**
by default.

## 7. Zero retry policy

No automatic retry. If a request fails (provider error / malformed / wrong or
missing ASIN / mapping incompatibility), the run hard-stops with a scrubbed
failure manifest.

## 8. Human-supplied credit cap requirement

The future run MUST be invoked with explicit finite `--max-requests` and
`--max-credits`. There is no default. The value `100` used below is the
documented dry-run/estimate figure (20 requests × ~5 credits/request). Approve
a concrete finite number at run time.

## 9. Estimated credit limitation

Estimated exposure is **~5 credits per ASIN** (documented `ESTIMATED_CREDITS_PER_REQUEST = 5.0`).
This is an estimate only. `actual_credits_used` is `null` unless the provider
returns it. Estimated credits are never reported as actual provider billing.

## 10. Expected mapping-review ASINs

```
B01H40O42I
B08R2SRN88
B00N54AJZE
```

These three have historical benchmark title-only conflicts. They are marked
`expected_mapping_review = true` in the comparison report. A historical title
conflict is **not** a provider failure and is never silently resolved to one
benchmark title.

## 11. All hard-stop conditions

A future live run hard-stops (scrubbed failure manifest, no completed result)
on any of:

- guard refused (`--live`, `SCANNER_LIVE_ALLOWED`, caps, or binding missing/inconsistent);
- binding invalid (fingerprint tampered, wrong purpose, wrong ASIN set);
- request budget exhausted before next request;
- credit budget exhausted before next request;
- returned ASIN differs from requested ASIN (or no ASIN returned);
- returned identity/product/pack incompatible with benchmark — **except** the
  three pre-registered `title_conflict` ASINs (`B01H40O42I`, `B08R2SRN88`,
  `B00N54AJZE`), which route to `expected_mapping_review` on a same-ASIN title
  mismatch with no pack mismatch and therefore do **not** hard-stop;
- BSR/category difference is **never** an execution hard stop — it is a report
  flag (`possible_market_drift`) when comparable; missing BSR/category is
  reported as unavailable, never as a failure;
- provider reported a request failure;
- provider response malformed/unparseable;
- normalization or `intel_schema` validation failure;
- secret-like key detected in result, snapshot, or adapter meta;
- atomic persistence failure (never a partial finalized artifact);
- adapter internal error or crash.

> **Narrow title-conflict policy.** Pre-registered benchmark title-conflict ASINs are expected mapping-review cases when the returned ASIN matches and no explicit pack mismatch exists. Title difference alone does not hard-stop those three pre-registered cases. Wrong ASIN, explicit pack mismatch, incompatible product evidence, malformed response, provider error, schema failure, budget breach, secret-like data, and persistence failure remain hard stops. BSR/category difference is never an execution hard stop.

## 12. Output artifact locations

```
data/batch/live-validation-runs/<run_id>/
    run-manifest.json
    validated-result-envelopes.json
    benchmark-comparison-report.json
    benchmark-comparison-report.csv
    human-review-summary.md
    failure-manifest.json          (written only on hard stop)
```

No protected artifact (scanner caches, benchmark files, finance/fee/pricing
modules, CSV contracts, secret/configuration files) is read-modified-written.

## 13. Rollback / failure behavior

- On any hard stop, only `failure-manifest.json` is written (scrubbed: no
  secrets, no raw bodies, no normalized results).
- No completed result artifact is produced, so there is nothing to "roll back".
- No automatic resume. A re-run is a fresh, fully guarded invocation.
- `synthetic_fixture` is `false` for a real run; fixture runs are visibly labeled.

## 14. Benchmark limitations

- Benchmark capture time is unknown; price, rank/BSR, and review-count
  differences may be market drift, not provider failure.
- Benchmark absence remains `null`/`unavailable`, never `0`.
- Economics/demand in the report are labeled internal/model-based, not
  independently sourced.
- Raw provider responses are never persisted.

## 15. Purchase-authorization limitation

The run validates only data coverage, mapping plausibility, schema quality, and
benchmark-comparison behavior. It does **not** establish product profitability,
Amazon selling eligibility, invoice legitimacy, supply continuity, Buy Box
stability, fees, demand, or purchase readiness. It does not authorize a
purchase, test-buy, or sourcing decision.

Exact statement embedded in every report:

```
Passing provider-data validation does not authorize a purchase.
```

## 16. Exact commands (ALL NOT EXECUTED)

```text
NOT EXECUTED — final dry-run
python proof_batch_run.py dry-run --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100

NOT EXECUTED — environment-gate setup (perform manually, yourself; do not print secret values)
set SCANNER_LIVE_ALLOWED=1
set PROOF_BATCH_LIVE_ARMED=1
unset SCANNER_LIVE_ALLOWED (after the run)
unset PROOF_BATCH_LIVE_ARMED (after the run)

NOT EXECUTED — guarded live run (bounded)
python proof_batch_run.py run --live --preflight data/batch/proof-batch-preflight-20260818T060549Z.json --max-requests 20 --max-credits 100

NOT EXECUTED — post-run report
python proof_batch_run.py report --run-dir data/batch/live-validation-runs/proof-batch-preflight-20260818T060549Z
```

## 16b. Runtime arming controls

A real run requires **two independent gates** to be explicitly enabled in the
runtime environment, plus every runner guard:

1. `SCANNER_LIVE_ALLOWED=1` — the general live-provider opt-in.
2. `PROOF_BATCH_LIVE_ARMED=1` — the dedicated, non-secret, read-only Proof
   Batch arm gate. It is `OFF` by default and only the exact value `"1"`
   enables it. Absent, empty, `false`, `"0"`, `"no"`, or any other value keeps
   it disabled. It is read once inside the guarded execution branch
   (`proof_batch_armed()` in `proof_batch_easyparser_adapter.py`) and is never
   mutated by the code, never printed, and never flippable by a CLI flag, GET
   route, report command, dry-run, or fixture run. The gate must be set by the
   operator in their own shell; the code and tests never set it outside isolated
   `patch.dict` blocks.

PowerShell (NOT EXECUTED — do this yourself, do not print secret values):

```powershell
# Enable (run the live validation yourself, separately approved)
$env:SCANNER_LIVE_ALLOWED="1"
$env:PROOF_BATCH_LIVE_ARMED="1"

# ... run the guarded single run, then disable
Remove-Item Env:\SCANNER_LIVE_ALLOWED
Remove-Item Env:\PROOF_BATCH_LIVE_ARMED
```

Either gate alone (`SCANNER_LIVE_ALLOWED=1` without `PROOF_BATCH_LIVE_ARMED=1`,
or vice versa) refuses at the runner/adapter gate with a typed `GuardError`
and makes no provider call. The default-disabled posture is preserved.

---

## Final Live-Run Approval Checklist (for the human approver)

1. Confirm the named fixed preflight, exact 20-ASIN list, and canonical fingerprint.
2. Confirm Easyparser-only scope and `market_offers` as the sole field contract.
3. Confirm `max_requests = 20` and zero retries.
4. Confirm `B01H40O42I`, `B08R2SRN88`, and `B00N54AJZE` remain `expected_mapping_review`.
5. Approve a finite `max_credits` value; use 100 only if approximately 100 estimated credits is acceptable.
6. Review the final zero-network dry-run output.
7. Perform the documented environment-gate setup yourself (both `SCANNER_LIVE_ALLOWED=1` and `PROOF_BATCH_LIVE_ARMED=1`).
8. Explicitly approve one bounded live validation run.
9. Review the persisted comparison report before any sourcing, invoice, test-buy, or purchase decision.
