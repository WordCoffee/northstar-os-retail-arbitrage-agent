# Attempt 2 — Guardrail Proof

**Verdict: the mapping guard works as designed.** Attempt 2 is accepted as a
successful proof of the guarded-batch title-conflict policy, not as a failed
run.

## What Attempt 2 demonstrated

1. **Expected title-conflict cases passed without a hard stop.**
   The two pre-registered conflict ASINs — `B01H40O42I` (source_rank 1) and
   `B08R2SRN88` (source_rank 2) — were fetched and mapped and routed to
   `expected_mapping_review`. They did **not** abort the batch. This confirms
   the corrected precedence (`classify_mapping`: pack-mismatch block →
   `title_conflict` → non-conflict title mismatch) is live in a real run.

2. **A genuine non-conflict mismatch hard-stopped correctly.**
   `B0CP6LXPLK` (source_rank 3, `title_conflict: false`, benchmark title
   `"Minoxidil Extra Strength (6-mo)"`) returned an incompatible title. The
   run aborted at `map(B0CP6LXPLK)` with `stop_reason = mapping_incompatible`
   (`STOP_MAPPING_MISMATCH`), `requests_used = 3`, before any spend on the
   remaining 17 ASINs.

3. **The behavior proves the policy distinguishes the two cases.**
   Expected *historical* title conflicts are isolated to human review; an
   *unexpected* identity mismatch on a non-conflict ASIN is a hard stop. The
   batch did exactly that.

## Failure manifest (Attempt 2)

- Run ID: `proof-batch-preflight-attempt-2-20260819T030931Z`
- Path: `data/batch/live-validation-runs/proof-batch-preflight-attempt-2-20260819T030931Z/failure-manifest.json`
- SHA-256: `42069974d7a86e2fb50093938c44f50e606726a94e0065bbf81572f10cd510d6`
- Stage: `map(B0CP6LXPLK)`; stop_reason: `mapping_incompatible`; ASIN: `B0CP6LXPLK`
- Budget: `requests_used = 3`, `credits_reported_used = 24`, `max_credits = 100`

## Decision: B0CP6LXPLK

The strict non-conflict title/product/pack mismatch policy is **not** weakened
for this ASIN, and it is **not** converted into a fourth
`expected_mapping_review` ASIN merely to get the batch through.

```text
identity_status: manual_resolution_required
purchase_status: blocked
provider_validation_status: unresolved_nonconflict_mapping_mismatch
```

A local-only manual mapping-resolution record was created at:

`data/batch/manual-mapping-review/B0CP6LXPLK-review.json`

It records the benchmark title, the `unexpected_mapping_mismatch` outcome, and
the reason — with **no purchase authorization** and **no
benchmark-mutation recommendation** until external/manual evidence resolves
which side (benchmark / provider / live listing) is correct. The record lists
six required evidence items (manual listing review, pack/strength/volume,
brand/manufacturer, UPC/EAN, screenshot/verification timestamp, and a future
trusted paid-provider result).

## Artifact preservation

- Attempt 1 evidence (`proof-batch-preflight-20260818T060549Z`) is preserved,
  unmodified. Its failure-manifest SHA-256 remains
  `d67bf5f33ce46a558f4285dd339fb9f93bcd0de775f213ec0dd21dd00cee3c28`.
- Attempt 2 evidence (its own run directory + failure manifest above) is
  preserved, unmodified.
- No Attempt 3 is approved.

## Easyparser credit usage (observed)

| Attempt | Requests | Provider-reported credits |
|---------|----------|---------------------------|
| Attempt 1 | 1 | 3 |
| Attempt 2 | 3 | 24 |
| **Total** | **4** | **27** |
| Remaining (user-reported balance) | — | **91** |

Attempt 2 cost ~8 credits/request, consistent with the operator-reported
24-credit total. The remaining 91 credits are **not** sufficient for a
comfortable 20-ASIN retry under the original 100-credit assumption.

## Future provider strategy

Do **not** spend more Easyparser credits on a third broad run. Pause
Easyparser and use the remaining 91 credits only for a narrow, manually
verified diagnostic if needed — not another 20-ASIN batch. The next provider
decision should be whether to adopt a paid, cache-first history source such as
**Keepa** for rank/price/Buy Box/offer-history intelligence, while keeping
seller/offers data as a narrower validation layer.

## Verification performed

- Focused offline test `test_manual_mapping_review.py` — passed (record
  schema, statuses, no purchase authorization / benchmark mutation).
- Protected-artifact byte-identity test `test_protected_artifacts_byte_identical`
  — all protected artifacts unchanged.
- No full live workflow, no provider/network calls, no runtime gates set, no
  protected or production artifacts modified.
