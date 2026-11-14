# Target spec — what production-ready means, per service

Derived 2026-11-14T01:33:47+00:00 from `state/director/services.json`, 7465 measured test ids and 1 readiness findings. **Scores are measured, never asserted**: a dimension with no artefact scores 0 and says why.

Bar: **85 on every dimension** (not an average). A service is at the bar only when its weakest dimension clears it. Impact weight is what a paying seller needs first; gap = impact x (bar - score).

| service | score | weakest | at bar | gap | impact |
|---|---|---|---|---|---|
| SourceScout (`product-finder`) | 77.0 | seller | no | 7.2 | 0.9 |
| Listing Guardian (`listings`) | 77.0 | seller | no | 7.2 | 0.9 |
| OfferChisel (`offerchisel`) | 79.5 | contract | no | 5.0 | 0.9 |
| Support (`beta-support`) | 77.0 | measured | no | 4.0 | 0.5 |
| AdPilot (`adpilot`) | 79.8 | contract | no | 3.6 | 0.7 |
| The Town Crier (`towncrier`) | 79.0 | contract | no | 2.7 | 0.45 |
| SocialPulse (`socialpulse`) | 79.7 | contract | no | 2.4 | 0.45 |
| Operations Hub (`hub`) | 100.0 | works | yes | 0.0 | 0.85 |
| The Ledger (`ledger`) | 86.2 | complete | no | 0.0 | 0.8 |
| Prospector (`prospector`) | 100.0 | works | yes | 0.0 | 0.9 |
| The Auctioneer (`auctioneer`) | 86.2 | complete | no | 0.0 | 0.7 |
| AutothinK (`autothink`) | 86.2 | complete | no | 0.0 | 0.5 |
| The Watch (`thewatch`) | 86.2 | complete | no | 0.0 | 0.6 |
| RankLedger (`rankledger`) | 86.2 | complete | no | 0.0 | 0.55 |
| The Rival Board (`rivalboard`) | 86.2 | complete | no | 0.0 | 0.5 |
| Account (`account`) | 86.2 | complete | no | 0.0 | 0.8 |
| Foundation (`foundation`) | 86.2 | complete | no | 0.0 | 0.7 |
| Jobs & Schedules (`jobs`) | 86.2 | complete | no | 0.0 | 0.4 |
| Keywords & SEO (`keywords`) | 86.2 | complete | no | 0.0 | 0.6 |
| Onboarding & Plan (`beta`) | 88.5 | contract | no | 0.0 | 0.9 |
| Invite entry (`beta-signup`) | 88.5 | contract | no | 0.0 | 0.8 |
| Tester Dashboard (`beta-ops`) | 88.5 | contract | no | 0.0 | 0.4 |
| Design Studio (`design-studio`) | 89.5 | correct | no | 0.0 | 0.95 |
| Golden Goose (`golden-goose`) | 90.0 | correct | no | 0.0 | 0.95 |
| Keyword Tracker (`keyword-tracker`) | 100.0 | works | yes | 0.0 | 0.6 |
| Competitor Monitor (`competitor-monitor`) | 88.5 | contract | no | 0.0 | 0.5 |
| ListingForge (`listingforge`) | 90.0 | correct | no | 0.0 | 0.85 |
| Profitability (`profitability`) | 100.0 | works | yes | 0.0 | 0.75 |

At the bar today: **4 of 28**.

Repo-wide findings (not charged to any service):

- dead-module at `northstar-os-ui/src/lib/serviceGate.js`

## SourceScout (`product-finder`)

SourceScout: match a product idea to suppliers and landed cost.

- route `/product-finder`, group Sourcing, kind workspace
- **score 77.0 / bar 85** (impact 0.9, gap 7.2)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 25 test id(s) prove it |
| correct | 60.0 | 0.25 | 25 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 0.0 | 0.13 | no Seller-Tester output scored for this service |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: scan_products |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /product-finder -> northstar-os-ui\src\pages\internal\ProductFinder.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/products/finder -> 200; 89 row(s) under 'evaluated' |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## Listing Guardian (`listings`)

Listing Guardian: keep live listings compliant and correct.

- route `/listings`, group Listings, kind workspace
- **score 77.0 / bar 85** (impact 0.9, gap 7.2)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 35 test id(s) prove it |
| correct | 60.0 | 0.25 | 35 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 0.0 | 0.13 | no Seller-Tester output scored for this service |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: optimize_listing |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /listings -> northstar-os-ui\src\pages\internal\ListingGuardian.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/noncreative/listings/health -> 200; 2 row(s) under 'items' |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## OfferChisel (`offerchisel`)

turn a product into an offer: price, title, bullets, images.

- route `/offerchisel`, group Listings, kind workspace
- **score 79.5 / bar 85** (impact 0.9, gap 5.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 114 test id(s) prove it |
| correct | 60.0 | 0.25 | 114 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 96.4 | 0.13 | 5 Seller-Tester service-path outputs (population: service-path; paths offer_copy), mean 96.4, 3 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: offer_recommendation |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /offerchisel -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | fail: every action is an external paid-model call |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## Support (`beta-support`)

support inside the beta without a human in the loop.

- route `/beta#support`, group Private Beta, kind onboarding
- **score 77.0 / bar 85** (impact 0.5, gap 4.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 17 test id(s) prove it |
| correct | 100.0 | 0.25 | 17 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: submit_support_ticket |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/beta#support' is not registered in the UI |
| contract | 0.0 | 0.1 | no_primary_action: registry records no actions for this service |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## AdPilot (`adpilot`)

campaign control: budget, bids, and the report behind them.

- route `/adpilot`, group Advertising, kind workspace
- **score 79.8 / bar 85** (impact 0.7, gap 3.6)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 13 test id(s) prove it |
| correct | 60.0 | 0.25 | 13 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 98.1 | 0.13 | 6 Seller-Tester service-path outputs (population: service-path; path ad_copy), mean 98.1, 5 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: plan_campaign |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /adpilot -> northstar-os-ui\src\pages\internal\AdPilot.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | empty_payload: payload has no measured rows or fields (keys: uploads,note) |

Seller scenarios:
- `backed` — hold ROAS while doubling spend on the winner
- `backed` — cut the keywords that only cost money
- `backed` — show me what the campaign did last week

## The Town Crier (`towncrier`)

seller-side social output that does not read like a robot.

- route `/towncrier`, group Social, kind workspace
- **score 79.0 / bar 85** (impact 0.45, gap 2.7)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 28 test id(s) prove it |
| correct | 60.0 | 0.25 | 28 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 92.1 | 0.13 | 5 Seller-Tester service-path outputs (population: service-path; paths caption), mean 92.1, 2 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: write_content |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /towncrier -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | fail: every action is an external paid-model call |

Seller scenarios:
- `backed` — post about a restock without sounding automated
- `backed` — keep the voice consistent across three posts

## SocialPulse (`socialpulse`)

schedule and judge social posts against a brand voice.

- route `/socialpulse`, group Social, kind workspace
- **score 79.7 / bar 85** (impact 0.45, gap 2.4)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 28 test id(s) prove it |
| correct | 60.0 | 0.25 | 28 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 98.0 | 0.13 | 5 Seller-Tester service-path outputs (population: service-path; paths social_caption), mean 98.0, 4 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: plan_social |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /socialpulse -> northstar-os-ui\src\pages\internal\SocialPulse.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | no_primary_action: registry records no actions for this service |

Seller scenarios:
- `backed` — post about a restock without sounding automated
- `backed` — keep the voice consistent across three posts

## Operations Hub (`hub`)

the room a seller lands in: today's work, the numbers that matter, and Bojo.

- route `/hub`, group Workspace, kind workspace
- **score 100.0 / bar 85** (impact 0.85, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 844 test id(s) prove it |
| correct | 100.0 | 0.25 | 844 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: hub_status |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /hub -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/sourcescout/summary -> 200; 6 measured field(s) (total,pass,fail,review,pass_rate,fail_rate,review_rate) |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet

## The Ledger (`ledger`)

money in, money out, fees and margin per SKU without a spreadsheet.

- route `/ledger`, group Workspace, kind workspace
- **score 86.2 / bar 85** (impact 0.8, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 70 test id(s) prove it |
| correct | 100.0 | 0.25 | 70 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /ledger -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/credits/me -> 200; 5 measured field(s) (balance,allotment,consumed,class,plan,period) |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet

## Prospector (`prospector`)

find products worth selling, with demand and competition evidence.

- route `/prospector`, group Sourcing, kind workspace
- **score 100.0 / bar 85** (impact 0.9, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 17 test id(s) prove it |
| correct | 100.0 | 0.25 | 17 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: catalog_pull |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /prospector -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/kirkland/scanner -> 200; 89 row(s) under 'products' |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## The Auctioneer (`auctioneer`)

PPC bids and budgets that spend only where they return.

- route `/auctioneer`, group Advertising, kind workspace
- **score 86.2 / bar 85** (impact 0.7, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 8 test id(s) prove it |
| correct | 100.0 | 0.25 | 8 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /auctioneer -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/v1/foundation/economics/compute -> 200; 9 measured field(s) (formula_version,currency,marketplace,readiness,missing_inputs,purchase_ready,explanation,gross_revenue) |

Seller scenarios:
- `backed` — hold ROAS while doubling spend on the winner
- `backed` — cut the keywords that only cost money
- `backed` — show me what the campaign did last week

## AutothinK (`autothink`)

the memory plane: what the seller told us, recalled at the right time.

- route `/autothink`, group AutothinK, kind workspace
- **score 86.2 / bar 85** (impact 0.5, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 68 test id(s) prove it |
| correct | 100.0 | 0.25 | 68 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /autothink -> northstar-os-ui\src\pages\internal\AutothinK.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/autothink/models -> 200; 98 measured field(s) (local_available,cloud_available,cloud_provider,cloud_live_armed,default_local_model,default_cloud_model,models,catalog) |

Seller scenarios:
- `backed` — remember my brand voice and use it later

## The Watch (`thewatch`)

watch the account for the things that quietly cost money.

- route `/thewatch`, group Monitoring, kind workspace
- **score 86.2 / bar 85** (impact 0.6, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 6 test id(s) prove it |
| correct | 100.0 | 0.25 | 6 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /thewatch -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/kirkland/scanner -> 200; 89 row(s) under 'products' |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## RankLedger (`rankledger`)

rank, impressions and conversion over time, per keyword.

- route `/rankledger`, group Monitoring, kind workspace
- **score 86.2 / bar 85** (impact 0.55, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 16 test id(s) prove it |
| correct | 100.0 | 0.25 | 16 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /rankledger -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/kirkland/scanner -> 200; 89 row(s) under 'products' |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## The Rival Board (`rivalboard`)

what competitors changed, and what it means for us.

- route `/rivalboard`, group Monitoring, kind workspace
- **score 86.2 / bar 85** (impact 0.5, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 15 test id(s) prove it |
| correct | 100.0 | 0.25 | 15 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /rivalboard -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/kirkland/scanner -> 200; 89 row(s) under 'products' |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## Account (`account`)

the seller's own account: plan, entitlements, security, preferences.

- route `/account`, group Account, kind account
- **score 86.2 / bar 85** (impact 0.8, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 141 test id(s) prove it |
| correct | 100.0 | 0.25 | 141 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /account -> northstar-os-ui\src\pages\customer\AccountStatus.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/foundation/entitlements -> 200; 3 measured field(s) (tier,max_jobs_per_month,export_enabled,advanced_reports,seat_limit,support_level,override_allowed) |

Seller scenarios:
- `backed` — change my plan without losing data
- `backed` — see exactly what I am entitled to

## Foundation (`foundation`)

Foundation.

- route `/foundation`, group Internal, kind workspace
- **score 86.2 / bar 85** (impact 0.7, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 844 test id(s) prove it |
| correct | 100.0 | 0.25 | 844 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /foundation -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/foundation/providers -> 200; 2 row(s) under 'items' |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## Jobs & Schedules (`jobs`)

long-running work that survives a reload and reports honestly.

- route `/jobs`, group Internal, kind workspace
- **score 86.2 / bar 85** (impact 0.4, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 89 test id(s) prove it |
| correct | 100.0 | 0.25 | 89 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /jobs -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/v1/foundation/jobs-durable -> 201; 1 row(s) under 'runs'; read back 76b3213b-5c1d-41ee-9442-63dbbcbec094 via /api/v1/foundation/jobs-durable/76b3213b-5c1d-41ee-9442-63dbbcbec094 |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## Keywords & SEO (`keywords`)

keyword research and SEO workbench.

- route `/keywords`, group Internal, kind workspace
- **score 86.2 / bar 85** (impact 0.6, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 77 test id(s) prove it |
| correct | 100.0 | 0.25 | 77 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 0.0 | 0.12 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /keywords -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/v1/foundation/keywords/imports -> 202; 5 measured field(s) (job_id,state,source_file_id,file_name,status,executes_in_worker); read back 965ed449-f2a8-4324-a6af-f5dd80721707 via /api/v1/foundation/jobs-durable/965ed449-f2a8-4324-a6af-f5dd80721707 |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## Onboarding & Plan (`beta`)

onboarding and plan selection for a private beta seller.

- route `/beta`, group Private Beta, kind onboarding
- **score 88.5 / bar 85** (impact 0.9, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 17 test id(s) prove it |
| correct | 100.0 | 0.25 | 17 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: onboarding_status |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /beta -> northstar-os-ui\src\pages\public\BetaLanding.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | no_primary_action: registry records no actions for this service |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## Invite entry (`beta-signup`)

invite entry that a real invitee can complete unaided.

- route `/beta-signup`, group Private Beta, kind onboarding
- **score 88.5 / bar 85** (impact 0.8, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 17 test id(s) prove it |
| correct | 100.0 | 0.25 | 17 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: redeem_invite |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /beta-signup -> northstar-os-ui\src\pages\roomAdapters.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | permission_denied: HTTP 403 - signup is not available at this time |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## Tester Dashboard (`beta-ops`)

the tester dashboard: who is in, what they did, what broke.

- route `/beta-ops`, group Beta Operations, kind onboarding
- **score 88.5 / bar 85** (impact 0.4, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 76 test id(s) prove it |
| correct | 100.0 | 0.25 | 76 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: beta_cohort |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /beta-ops -> northstar-os-ui\src\pages\admin\Overview.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | permission_denied: HTTP 403 - role_operator_lacks_platform_admin |

Seller scenarios:
- `backed` — see who is active and what broke

## Design Studio (`design-studio`)

product pictures in any seller situation, and A+ content, from a prompt, stored references, or uploads - Canva-grade to use.

- route `/design-studio`, group Create, kind studio
- **score 89.5 / bar 85** (impact 0.95, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 166 test id(s) prove it |
| correct | 60.0 | 0.25 | 166 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 96.2 | 0.13 | 32 Seller-Tester outputs (generated/composite), mean 96.2, 32 passed; 40 replayed artefact(s) excluded as context (mean 22.1); 5 service-path output(s) (mean 100.0) are a separate population and are not averaged in here |
| complete | 100.0 | 0.12 | 3/3 declared Bojo tools wired: build_dieline, generate_image, list_templates |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /design-studio -> northstar-os-ui\src\pages\internal\DesignStudio.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/design-studio/assets/upload -> 200; 10 measured field(s) (id,asset,file_url); read back 78fbb038-e23f-4323-95e8-5b7912410382 via /api/design-studio/assets |

Seller scenarios:
- `backed` — white-background main image from a phone photo
- `backed` — lifestyle scene with a scale reference
- `backed` — an A+ module set that matches the brand

## Golden Goose (`golden-goose`)

the high-margin finder: score an opportunity and say why.

- route `/golden-goose`, group Sourcing, kind workspace
- **score 90.0 / bar 85** (impact 0.95, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 567 test id(s) prove it |
| correct | 60.0 | 0.25 | 567 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 100.0 | 0.13 | 5 Seller-Tester service-path outputs (population: service-path; paths golden_goose), mean 100.0, 5 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: golden_goose_scan |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /golden-goose -> northstar-os-ui\src\pages\internal\GoldenGoose.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/v1/foundation/golden-goose/evaluate -> 200; 17 measured field(s) (item_id,decision,resale_score) |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## Keyword Tracker (`keyword-tracker`)

which keywords are worth owning, measured not guessed.

- route `/keyword-tracker`, group Monitoring, kind workspace
- **score 100.0 / bar 85** (impact 0.6, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 77 test id(s) prove it |
| correct | 100.0 | 0.25 | 77 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: track_keywords |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /keyword-tracker -> northstar-os-ui\src\pages\internal\KeywordTracker.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/noncreative/keywords -> 200; 10 row(s) under 'items' |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## Competitor Monitor (`competitor-monitor`)

the competitor feed behind Rival Board.

- route `/competitor-monitor`, group Monitoring, kind workspace
- **score 88.5 / bar 85** (impact 0.5, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 6 test id(s) prove it |
| correct | 100.0 | 0.25 | 6 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: watch_competitor |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /competitor-monitor -> northstar-os-ui\src\pages\internal\CompetitorMonitor.jsx; app p95 3.4 ms |
| contract | 0.0 | 0.1 | empty_payload: payload has no measured rows or fields (keys: kind,count,items,summary) |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## ListingForge (`listingforge`)

create and version listings with the copy that converts.

- route `/listingforge`, group Listings, kind workspace
- **score 90.0 / bar 85** (impact 0.85, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 35 test id(s) prove it |
| correct | 60.0 | 0.25 | 35 test id(s) prove the code path; output quality is judged by the Seller-Tester, not by the tests |
| seller | 100.0 | 0.13 | 6 Seller-Tester service-path outputs (population: service-path; paths listing), mean 100.0, 6 passed |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: compose_listing |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /listingforge -> northstar-os-ui\src\pages\internal\ListingForge.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | POST /api/design-studio/listing-records -> 200; 6 measured field(s) (id,record); read back adad0461-16cd-4966-a146-69d94d9f9097 via /api/design-studio/listing-records |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## Profitability (`profitability`)

per-SKU profitability after fees, ads and returns.

- route `/profitability`, group Workspace, kind workspace
- **score 100.0 / bar 85** (impact 0.75, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.23 | 4 test id(s) prove it |
| correct | 100.0 | 0.25 | 4 test id(s) prove behaviour; this service produces no seller-facing artefact, so tests are the evidence |
| seller | None | 0.13 | this service does not produce a seller-facing artefact, so there is nothing to score |
| complete | 100.0 | 0.12 | 1/1 declared Bojo tools wired: margin_report |
| usable | 100.0 | 0.07 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /profitability -> northstar-os-ui\src\pages\internal\ProfitabilityDashboard.jsx; app p95 3.4 ms |
| contract | 100.0 | 0.1 | GET /api/v1/foundation/economics/contract -> 200; 10 measured field(s) (formula_version,money_type,rounding,readiness_states,metrics) |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet
