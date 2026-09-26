# 01 — Policy and Compliance

## Faire is discovery-only

Faire's retailer guidance states it cannot fulfil orders for sellers using
Amazon and that goods purchased through Faire cannot be listed on third-party
marketplaces. This workflow therefore treats Faire strictly as a **product and
brand discovery source**.

References (operator-supplied):
- https://www.faire.com/support/articles/31169832450971
- https://www.faire.com/support/articles/32636987402651
- https://www.faire.com/support/articles/360059304192

## Hard rules encoded in `Northstar_backend/faire_research/`

| Rule | Enforcement |
|---|---|
| Faire is not a sourcing route | `CandidateAssessment.faire_is_only_sourcing_route` → hard disqualifier `faire_is_only_sourcing_route` (`qualification.py`) |
| Faire price is benchmark only | `FAIRE_SOURCING_LABEL` constant; schema field `wholesale_pricing_label` |
| Brand prohibits Amazon | `brand_permission == NO` → `brand_prohibits_amazon` |
| Direct supplier prohibits Amazon | `BrandRiskState.BRAND_POLICY_RESTRICTS_MARKETPLACES` → disqualifier |
| Eligibility restricted | `RESTRICTED` / `NOT_ELIGIBLE` → disqualifier |
| "Not on Amazon" is a risk, not an opportunity | mapped to `BRAND_POLICY_RESTRICTS_MARKETPLACES` |
| No purchase/listing/contact | no code path performs these; `research-batch-contract.json` fixes counts to 0 |

## A candidate becomes a sourcing candidate ONLY when a separate direct route:

- Explicitly permits Amazon resale.
- Provides legitimate wholesale invoices (supplier legal name + address; buyer
  = T2 Holdings LLC; quantities; traceable descriptions).
- Provides authentic, unaltered goods.
- Respects marketplace, territorial, MAP and distribution restrictions.
- Supports repeatable replenishment.
- Can provide written marketplace authorization when needed.

A Faire order confirmation or receipt is **never** treated as sufficient for
Amazon authenticity review.

## Data-access rules

No bypassing of authentication, CAPTCHAs, rate limits, robots, anti-bot, paywalls,
account/marketplace restrictions, terms or API restrictions. Live read of
authenticated Faire is permitted only with operator authorization, an eligible
account, permitted automation, protected credentials and **no account-changing
action**. Ordinary GET routes must not trigger external calls. Every live run
must be an explicit, recorded research job.

## Prohibited in this phase

Purchase, add-to-cart, account creation, applications, brand contact, listing,
or any Amazon marketplace write. This phase is research, normalization,
comparison and candidate qualification only.
