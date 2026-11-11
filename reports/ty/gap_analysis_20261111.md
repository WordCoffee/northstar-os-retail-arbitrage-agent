# Gap analysis, 2026-11-11 — what is actually left before "production ready"

Measured from `ty/scorecards.json` at the commit that merged block3 (`9cafbcbb`). Read-only:
no score was changed by this analysis.

## The number

**29 services · 16 at or above the 85 bar · 13 below.** The bar is per-dimension, so a 77
average is not a pass.

Ranked by the D5 formula, `gap = impact × (bar − score)`:

| rank | service | score | bar | impact | gap | weakest dimension |
|---|---|---|---|---|---|---|
| 1 | offerchisel | 67.0 | 85 | 0.90 | 16.20 | seller 0.0 |
| 2 | towncrier | 55.0 | 85 | 0.45 | 13.50 | seller 0.0 |
| 3 | adpilot | 67.0 | 85 | 0.70 | 12.60 | seller 0.0 |
| 4 | beta-support | 63.2 | 85 | 0.50 | 10.90 | complete 0.0 |
| 5 | beta | 74.7 | 85 | 0.90 | 9.27 | complete 0.0 |
| 6 | beta-signup | 74.7 | 85 | 0.80 | 8.24 | complete 0.0 |
| 7 | socialpulse | 67.0 | 85 | 0.45 | 8.10 | seller 0.0 |
| 8 | goldengoose | 77.0 | 85 | 0.95 | 7.60 | seller 0.0 |
| 9 | golden-goose | 77.0 | 85 | 0.95 | 7.60 | seller 0.0 |
| 10 | product-finder | 77.0 | 85 | 0.90 | 7.20 | seller 0.0 |
| 11 | listings | 77.0 | 85 | 0.90 | 7.20 | seller 0.0 |
| 12 | listingforge | 77.0 | 85 | 0.85 | 6.80 | seller 0.0 |
| 13 | beta-ops | 74.7 | 85 | 0.40 | 4.12 | complete 0.0 |

Dimension means across those 13:

| dimension | mean | reading |
|---|---|---|
| works | 100.0 | every service's code path runs |
| usable | 100.0 | every service renders |
| measured | 92.3 | almost every service has a scorecard |
| correct | 72.3 | the substance is where the gaps are |
| complete | 61.5 | declared Bojo tools without a callable handler |
| contract | 38.5 | the paid/dependency contract is unproven for most |
| **seller** | **0.0 (9 of 13)** | **no seller output has been scored for these** |

## Finding 1 — "seller 0.0" is a sample-size fact, not a quality verdict

`tools/seller_scores.py:score_for()` scores a service only at **≥ 5 generated outputs**
(`MIN_SCORED`), and returns a named zero below that. Nine services read 0.0 for one reason:
nothing of theirs has been produced and scored five times. That rule is correct — five lucky
pictures are not a service — so the fix is **more real briefs and more real runs**, not a
smaller sample.

Lane F is on exactly that for the four paths the seller-tester now has (listing, ppc,
golden_goose, research): at least 5 distinct briefs per path, run and scored, then wired
into `seller_scores` under the same `MIN_SCORED` rule with its own declared population.

**What that will not fix, and must not pretend to:** `offerchisel`, `towncrier` and
`socialpulse` have no service path at all — their seller dimension needs an offer/caption
scorer that does not exist yet.

## Finding 2 — one product surface is counted twice

`goldengoose` and `golden-goose` are two registry entries with the same label and the same
declared tool (`golden_goose_scan`), pointing at two different front-end routes:

| registry id | route | component |
|---|---|---|
| `golden-goose` | `/golden-goose` | `pages/internal/GoldenGoose.jsx` (the current desk) |
| `goldengoose` | `/goldengoose` | `pageAdapters.jsx → LegacyGoldenGooseRoom` (a legacy adapter) |

So the portfolio is **28 distinct product surfaces, not 29**, and 7.60 of the ranked gap above
is the same gap counted twice. The honest fix is to mark the legacy route as an alias of the
service (or retire it) rather than score it as a second product. Queued as
`retire-goldengoose-alias`.

## Finding 3 — `complete` and `contract` are the second wave

`beta`, `beta-signup`, `beta-support` and `beta-ops` sit between 63 and 75 with `complete` at
0: their declared Bojo tool has no callable handler. That is mechanical work (wire the tool
into the chat tool table) and it is worth 8.24–10.90 of ranked gap — more than several seller
gaps.

`contract` at 38.5 across the set is the dimension the *owner* bought with the contract work
on 2026-11-09: a service whose only actions need a paid model is never called, and that is
standing gate (a), not a bug.

## What this means for the finish line

The mandate's end state is every core service passing its bar **twice** on held-out sets with
the verifier reproducing it. Today: 16 of 28 surfaces pass once. The remaining work, in the
order the measurement supports:

1. `block5-production-hardening` (in flight) — the machinery that makes a release claim
   checkable at all.
2. `block7-verification` — the independent reproduction of whatever the scorecards say.
3. Seller sample depth per path (lane F) — moves up to four services off a 0.0 that is
   currently a measurement artefact.
4. `complete` for the beta family — wire four declared tools.
5. Offer/caption scorers for `offerchisel`, `towncrier`, `socialpulse`.
6. `retire-goldengoose-alias` — stop counting one surface twice.
3–6 are the actual programme; 1–2 are the gates that make its claims trustworthy.
