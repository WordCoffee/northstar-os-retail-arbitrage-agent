# Target spec — what production-ready means, per service

Derived 2026-11-08T09:18:52+00:00 from `state/director/services.json`, 6789 measured test ids and 1 readiness findings. **Scores are measured, never asserted**: a dimension with no artefact scores 0 and says why.

Bar: **85 on every dimension** (not an average). A service is at the bar only when its weakest dimension clears it. Impact weight is what a paying seller needs first; gap = impact x (bar - score).

| service | score | weakest | at bar | gap | impact |
|---|---|---|---|---|---|
| Golden Goose (`goldengoose`) | 75.0 | complete | no | 9.5 | 0.95 |
| Prospector (`prospector`) | 75.0 | complete | no | 9.0 | 0.9 |
| OfferChisel (`offerchisel`) | 75.0 | complete | no | 9.0 | 0.9 |
| Operations Hub (`hub`) | 75.0 | complete | no | 8.5 | 0.85 |
| The Ledger (`ledger`) | 75.0 | complete | no | 8.0 | 0.8 |
| Invite entry (`beta-signup`) | 75.0 | complete | no | 8.0 | 0.8 |
| The Auctioneer (`auctioneer`) | 75.0 | complete | no | 7.0 | 0.7 |
| Operations Hub (`foundation`) | 75.0 | complete | no | 7.0 | 0.7 |
| The Watch (`thewatch`) | 75.0 | complete | no | 6.0 | 0.6 |
| Keywords & SEO (`keywords`) | 75.0 | complete | no | 6.0 | 0.6 |
| RankLedger (`rankledger`) | 75.0 | complete | no | 5.5 | 0.55 |
| The Rival Board (`rivalboard`) | 75.0 | complete | no | 5.0 | 0.5 |
| Support (`beta-support`) | 75.0 | complete | no | 5.0 | 0.5 |
| The Town Crier (`towncrier`) | 75.0 | complete | no | 4.5 | 0.45 |
| Jobs & Schedules (`jobs`) | 75.0 | complete | no | 4.0 | 0.4 |
| AutothinK (`autothink`) | 85.0 | complete | no | 0.0 | 0.5 |
| Account (`account`) | 85.0 | complete | no | 0.0 | 0.8 |
| Onboarding & Plan (`beta`) | 85.0 | complete | no | 0.0 | 0.9 |
| Tester Dashboard (`beta-ops`) | 85.0 | complete | no | 0.0 | 0.4 |
| Design Studio (`design-studio`) | 95.0 | complete | no | 0.0 | 0.95 |
| SourceScout (`product-finder`) | 85.0 | complete | no | 0.0 | 0.9 |
| Golden Goose (`golden-goose`) | 85.0 | complete | no | 0.0 | 0.95 |
| Listing Guardian (`listings`) | 100.0 | works | yes | 0.0 | 0.9 |
| Keyword Tracker (`keyword-tracker`) | 85.0 | complete | no | 0.0 | 0.6 |
| Competitor Monitor (`competitor-monitor`) | 85.0 | complete | no | 0.0 | 0.5 |
| ListingForge (`listingforge`) | 85.0 | complete | no | 0.0 | 0.85 |
| AdPilot (`adpilot`) | 85.0 | complete | no | 0.0 | 0.7 |
| SocialPulse (`socialpulse`) | 100.0 | works | yes | 0.0 | 0.45 |
| Profitability (`profitability`) | 85.0 | complete | no | 0.0 | 0.75 |

At the bar today: **2 of 29**.

Repo-wide findings (not charged to any service):

- dead-module at `northstar-os-ui/src/lib/serviceGate.js`

## Golden Goose (`goldengoose`)

the high-margin finder: score an opportunity and say why.

- route `/goldengoose`, group Sourcing, kind workspace
- **score 75.0 / bar 85** (impact 0.95, gap 9.5)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 557 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/goldengoose' is not registered in the UI |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## Prospector (`prospector`)

find products worth selling, with demand and competition evidence.

- route `/prospector`, group Sourcing, kind workspace
- **score 75.0 / bar 85** (impact 0.9, gap 9.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 17 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/prospector' is not registered in the UI |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## OfferChisel (`offerchisel`)

turn a product into an offer: price, title, bullets, images.

- route `/offerchisel`, group Listings, kind workspace
- **score 75.0 / bar 85** (impact 0.9, gap 9.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 111 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/offerchisel' is not registered in the UI |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## Operations Hub (`hub`)

the room a seller lands in: today's work, the numbers that matter, and Bojo.

- route `/hub`, group Workspace, kind workspace
- **score 75.0 / bar 85** (impact 0.85, gap 8.5)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 844 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/hub' is not registered in the UI |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet

## The Ledger (`ledger`)

money in, money out, fees and margin per SKU without a spreadsheet.

- route `/ledger`, group Workspace, kind workspace
- **score 75.0 / bar 85** (impact 0.8, gap 8.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 70 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/ledger' is not registered in the UI |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet

## Invite entry (`beta-signup`)

invite entry that a real invitee can complete unaided.

- route `/beta-signup`, group Private Beta, kind onboarding
- **score 75.0 / bar 85** (impact 0.8, gap 8.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 17 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/beta-signup' is not registered in the UI |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## The Auctioneer (`auctioneer`)

PPC bids and budgets that spend only where they return.

- route `/auctioneer`, group Advertising, kind workspace
- **score 75.0 / bar 85** (impact 0.7, gap 7.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 8 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/auctioneer' is not registered in the UI |

Seller scenarios:
- `backed` — hold ROAS while doubling spend on the winner
- `backed` — cut the keywords that only cost money
- `backed` — show me what the campaign did last week

## Operations Hub (`foundation`)

Operations Hub.

- route `/foundation`, group Internal, kind workspace
- **score 75.0 / bar 85** (impact 0.7, gap 7.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 844 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/foundation' is not registered in the UI |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## The Watch (`thewatch`)

watch the account for the things that quietly cost money.

- route `/thewatch`, group Monitoring, kind workspace
- **score 75.0 / bar 85** (impact 0.6, gap 6.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 6 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/thewatch' is not registered in the UI |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## Keywords & SEO (`keywords`)

keyword research and SEO workbench.

- route `/keywords`, group Internal, kind workspace
- **score 75.0 / bar 85** (impact 0.6, gap 6.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 77 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/keywords' is not registered in the UI |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## RankLedger (`rankledger`)

rank, impressions and conversion over time, per keyword.

- route `/rankledger`, group Monitoring, kind workspace
- **score 75.0 / bar 85** (impact 0.55, gap 5.5)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 15 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/rankledger' is not registered in the UI |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## The Rival Board (`rivalboard`)

what competitors changed, and what it means for us.

- route `/rivalboard`, group Monitoring, kind workspace
- **score 75.0 / bar 85** (impact 0.5, gap 5.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 14 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/rivalboard' is not registered in the UI |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## Support (`beta-support`)

support inside the beta without a human in the loop.

- route `/beta#support`, group Private Beta, kind onboarding
- **score 75.0 / bar 85** (impact 0.5, gap 5.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 17 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/beta#support' is not registered in the UI |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## The Town Crier (`towncrier`)

seller-side social output that does not read like a robot.

- route `/towncrier`, group Social, kind workspace
- **score 75.0 / bar 85** (impact 0.45, gap 4.5)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 28 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/towncrier' is not registered in the UI |

Seller scenarios:
- `backed` — post about a restock without sounding automated
- `backed` — keep the voice consistent across three posts

## Jobs & Schedules (`jobs`)

long-running work that survives a reload and reports honestly.

- route `/jobs`, group Internal, kind workspace
- **score 75.0 / bar 85** (impact 0.4, gap 4.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 89 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 0.0 | 0.1 | route '/jobs' is not registered in the UI |

Seller scenarios:
- `backed` — the work survives a reload and tells me when it failed

## AutothinK (`autothink`)

the memory plane: what the seller told us, recalled at the right time.

- route `/autothink`, group AutothinK, kind workspace
- **score 85.0 / bar 85** (impact 0.5, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 68 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /autothink -> northstar-os-ui\src\pages\internal\AutothinK.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — remember my brand voice and use it later

## Account (`account`)

the seller's own account: plan, entitlements, security, preferences.

- route `/account`, group Account, kind account
- **score 85.0 / bar 85** (impact 0.8, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 141 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /account -> northstar-os-ui\src\pages\customer\AccountStatus.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — change my plan without losing data
- `backed` — see exactly what I am entitled to

## Onboarding & Plan (`beta`)

onboarding and plan selection for a private beta seller.

- route `/beta`, group Private Beta, kind onboarding
- **score 85.0 / bar 85** (impact 0.9, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 17 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /beta -> northstar-os-ui\src\pages\public\BetaLanding.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — an invitee signs up without help
- `backed` — a tester reports a bug and sees it acknowledged

## Tester Dashboard (`beta-ops`)

the tester dashboard: who is in, what they did, what broke.

- route `/beta-ops`, group Beta Operations, kind onboarding
- **score 85.0 / bar 85** (impact 0.4, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 76 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | no Bojo tool declared, so Bojo cannot drive it |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /beta-ops -> northstar-os-ui\src\pages\admin\Overview.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — see who is active and what broke

## Design Studio (`design-studio`)

product pictures in any seller situation, and A+ content, from a prompt, stored references, or uploads - Canva-grade to use.

- route `/design-studio`, group Create, kind studio
- **score 95.0 / bar 85** (impact 0.95, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 166 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 66.7 | 0.15 | 2/3 declared Bojo tools wired: build_dieline, generate_image, list_templates |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /design-studio -> northstar-os-ui\src\pages\internal\DesignStudio.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — white-background main image from a phone photo
- `backed` — lifestyle scene with a scale reference
- `backed` — an A+ module set that matches the brand

## SourceScout (`product-finder`)

SourceScout: match a product idea to suppliers and landed cost.

- route `/product-finder`, group Sourcing, kind workspace
- **score 85.0 / bar 85** (impact 0.9, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 21 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: scan_products |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /product-finder -> northstar-os-ui\src\pages\internal\ProductFinder.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## Golden Goose (`golden-goose`)

the high-margin finder: score an opportunity and say why.

- route `/golden-goose`, group Sourcing, kind workspace
- **score 85.0 / bar 85** (impact 0.95, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 557 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: golden_goose_scan |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /golden-goose -> northstar-os-ui\src\pages\internal\GoldenGoose.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — find a product in a category I have never sold
- `backed` — compare landed cost across three suppliers
- `backed` — tell me the margin at my fee tier

## Listing Guardian (`listings`)

Listing Guardian: keep live listings compliant and correct.

- route `/listings`, group Listings, kind workspace
- **score 100.0 / bar 85** (impact 0.9, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 35 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 100.0 | 0.15 | 1/1 declared Bojo tools wired: optimize_listing |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /listings -> northstar-os-ui\src\pages\internal\ListingGuardian.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## Keyword Tracker (`keyword-tracker`)

which keywords are worth owning, measured not guessed.

- route `/keyword-tracker`, group Monitoring, kind workspace
- **score 85.0 / bar 85** (impact 0.6, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 77 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: track_keywords |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /keyword-tracker -> northstar-os-ui\src\pages\internal\KeywordTracker.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## Competitor Monitor (`competitor-monitor`)

the competitor feed behind Rival Board.

- route `/competitor-monitor`, group Monitoring, kind workspace
- **score 85.0 / bar 85** (impact 0.5, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 5 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: watch_competitor |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /competitor-monitor -> northstar-os-ui\src\pages\internal\CompetitorMonitor.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — tell me what changed before I lose the buy box
- `backed` — show rank over the last 90 days
- `backed` — alert me when a competitor undercuts me

## ListingForge (`listingforge`)

create and version listings with the copy that converts.

- route `/listingforge`, group Listings, kind workspace
- **score 85.0 / bar 85** (impact 0.85, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 35 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: compose_listing |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /listingforge -> northstar-os-ui\src\pages\internal\ListingForge.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — turn this product into a listing that will not be suppressed
- `backed` — rewrite the bullets for a different audience
- `backed` — fix the listing that lost its buy box

## AdPilot (`adpilot`)

campaign control: budget, bids, and the report behind them.

- route `/adpilot`, group Advertising, kind workspace
- **score 85.0 / bar 85** (impact 0.7, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 13 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: plan_campaign |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /adpilot -> northstar-os-ui\src\pages\internal\AdPilot.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — hold ROAS while doubling spend on the winner
- `backed` — cut the keywords that only cost money
- `backed` — show me what the campaign did last week

## SocialPulse (`socialpulse`)

schedule and judge social posts against a brand voice.

- route `/socialpulse`, group Social, kind workspace
- **score 100.0 / bar 85** (impact 0.45, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 28 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 100.0 | 0.15 | 1/1 declared Bojo tools wired: plan_social |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /socialpulse -> northstar-os-ui\src\pages\internal\SocialPulse.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — post about a restock without sounding automated
- `backed` — keep the voice consistent across three posts

## Profitability (`profitability`)

per-SKU profitability after fees, ads and returns.

- route `/profitability`, group Workspace, kind workspace
- **score 85.0 / bar 85** (impact 0.75, gap 0.0)

| dimension | score | weight | evidence |
|---|---|---|---|
| works | 100.0 | 0.3 | 4 test id(s) prove it |
| correct | 100.0 | 0.3 | its tests passed in the D0 measured run |
| complete | 0.0 | 0.15 | 0/1 declared Bojo tools wired: margin_report |
| usable | 100.0 | 0.15 | no readiness finding names this service |
| measured | 100.0 | 0.1 | route /profitability -> northstar-os-ui\src\pages\internal\ProfitabilityDashboard.jsx; app p95 3.0 ms |

Seller scenarios:
- `backed` — start the day knowing what needs doing
- `backed` — see margin per SKU without a spreadsheet
