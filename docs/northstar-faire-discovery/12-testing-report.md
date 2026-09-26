# 12 — Testing Report

All tests are **offline** (MODE 1): no network, no `.env`, no provider clients,
no `SCANNER_LIVE_ALLOWED`.

## Run

```
cd Northstar_backend
python -m pytest faire_research/tests -q
```

Result: **45 passed**.

| File | Coverage |
|---|---|
| `faire_research/tests/test_economics.py` | landed unit cost; unknown-component-not-zero; zero/None units unresolved; contribution/ROI/margin distinct; not faire-minus-amazon; FEE_UNKNOWN cannot pass; unknown fee component unresolved; negative profit reported; below-min flagged; cents quantization; downside scenarios scale referral |
| `faire_research/tests/test_matching_packs.py` | exact GTIN; MPN+brand; wrong pack qty/size/color; similar title missing GTIN not exact; ambiguous; insufficient data; variation material mismatch; GTIN-match-but-brand-differs; pack classification (case/multipack/seller-created/bundle/inner/unknown); case-break allowed/denied ("not for individual sale", no supplier Amazon permission) |
| `faire_research/tests/test_qualification.py` | Faire-only sourcing hard reject; brand-prohibits-Amazon; "Not on Amazon" is risk not opportunity; eligibility restricted; unknown authorization blocks purchase; invoice path missing; unknown eligibility blocks purchase; direct-supplier-authorized → QUALIFIED_FOR_MANUAL_REVIEW; SOURCE_READY requires verified supplier; ambiguous → MATCH_REVIEW; unresolved economics → ECONOMICS_INCOMPLETE; score bounds & never-assume-missing |

## Required test families (spec) vs coverage

- IDENTITY — covered (exact UPC/MPN, wrong pack/size/color, similar-title, ambiguous, missing GTIN, variation mismatch).
- PACKS — covered (case of singles, manufacturer/seller multipack, bundle, inner pack, "not for individual sale", unknown).
- ECONOMICS — covered (landed cost, shipping allocation, referral, FBA fee presence, missing fee, missing cost, price decline, Decimal precision, negative profit, ROI vs margin). Note: peak/non-peak period is **not** yet exercised (canonical engine pending).
- COMPLIANCE — covered (Faire-only rejected, brand prohibits, authorization unknown, direct supplier confirmed, invoice path missing, eligibility unknown/restricted, "Not on Amazon" as risk).
- DATA — partially covered (unknown weight/dimension handling via unresolved economics); stale-cache/duplicate-import/conflicting-source tests are **contract-only** (no live ingestion yet).
- SECURITY — cross-org denial, viewer-write, GET-triggered provider, secret
  redaction are **contract-only** here; they are enforced by the existing
  `foundation` suite (`foundation/tests/test_auth_org_scope.py`,
  `test_permissions.py`, `test_live_containment.py`) and must be extended when the
  Faire routes are implemented.

No test contacts Faire, Amazon, or any provider.
