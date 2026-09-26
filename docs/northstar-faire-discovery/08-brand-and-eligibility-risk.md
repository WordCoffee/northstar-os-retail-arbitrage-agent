# 08 — Brand and Eligibility Risk

Do **not** claim a brand is "not gated" based on general reputation.

## Brand-risk states

`AMAZON_ELIGIBILITY_CONFIRMED`, `BRAND_AUTHORIZATION_CONFIRMED`,
`DIRECT_WHOLESALE_CONFIRMED`, `INVOICE_PATH_CONFIRMED`,
`IP_RISK_LOW_WITH_EVIDENCE`, `APPROVAL_REQUIRED`,
`BRAND_POLICY_RESTRICTS_MARKETPLACES`, `EXCLUSIVE_AMAZON_DISTRIBUTION_SUSPECTED`,
`IP_RISK_REVIEW_REQUIRED`, `UNKNOWN`.

## Investigate where legitimately available

Seller-account approval result; brand marketplace policy; direct supplier terms;
MAP policy; Brand Registry presence; known exclusivity; internal IP-complaint
history; internal listing-removal history; whether the brand or Amazon dominates
the offer; whether the brand advertises "not on Amazon"; whether the Faire page
or brand terms restrict Amazon.

## "Not on Amazon" handling

A "Not on Amazon" label is **not** an opportunity. It may indicate intentional
channel separation and therefore **higher** marketplace-policy risk. Mapped to
`BRAND_POLICY_RESTRICTS_MARKETPLACES`, which is a hard disqualifier.

## Existing Northstar gating capability (limited)

| Capability | Status |
|---|---|
| Static brand blacklist (`config/brand_policy.json`, `filters/universal_filter.py`) | exists |
| `tasks/brand_blacklist_updater.check_brand_gating_sp_api` | **stub — always `unknown`, no live call** |
| `goose_report._gating_status` FBA-count display heuristic | display only |
| Per-ASIN live eligibility lookup | **does not exist** |

Consequence: eligibility defaults to `ELIGIBILITY_UNKNOWN`; it can never be
inferred from the presence of other sellers. A real check requires an
authorized seller-account (SP-API) integration, which is out of current scope.
