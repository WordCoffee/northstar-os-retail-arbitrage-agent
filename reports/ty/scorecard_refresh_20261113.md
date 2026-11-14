# Scorecard refresh — AdPilot's measured seller score reaches the scorecard (2026-11-13)

**Outcome: the top-ranked gap was stale by two days, and it is now measured.** The scorecard
read AdPilot's seller dimension as **0.0** ("no Seller-Tester output scored for this service")
while `ty/seller_scores.json` had carried **98.1 over 6 scored / 5 passed** since
2026-11-13T10:11:42Z. Nothing was built; the measurement was reconciled.

## Why this was the first unit

`python tools/director_gaps.py --rank` put **adpilot at gap 12.6** — the largest gap in the
portfolio — on a seller score of 0.0. The digest claimed PPC's G2 was proved on 2026-11-13;
the scorecard said the opposite. One of the two was false, and only a measurement could say
which.

## What was measured

| item | value |
|---|---|
| scorecard at HEAD | generated `2026-11-11T19:35:56Z` |
| seller score at HEAD | adpilot `0.0`, "no Seller-Tester output scored for this service", gap `12.6`, weakest `seller` |
| seller_scores on disk | `2026-11-13T10:11:42Z`: adpilot `mean 98.1`, `scored 6`, `passed 5`, `population: service-path`, `path: ad_copy`, proof `state/seller/ad_copy_proof.json` |
| after `python tools/scorecards.py` | adpilot **79.8**, seller **98.1**, gap **3.6**, weakest **contract** |

**AdPilot is its own owner of that number.** The score is AdPilot's own ad copy, judged by the
app's own sponsored-products rules (`tools/seller_tester/ad_copy.py`, 6 fixtures, AD-006 kept
as a real failure). It is not borrowed from Design Studio's bulksheet path, and Design Studio's
image score (89.5 / 96.2 over 32 generated pictures) is untouched.

## The row-level diff, against HEAD

- **Only one row changed:** `adpilot 67.0 → 79.8` (+12.8 = 0.13 weight × the 98.1 seller score),
  `gap 12.6 → 3.6`, `weakest seller → contract`.
- **Every other row is byte-identical.** 28 services before and after; no id added or removed.
- Portfolio: services scoring **≥ 85**: **21 of 28** before and after (AdPilot is still below
  the bar). Services with **every dimension ≥ 85**: **4 of 28**, unchanged (the scorecard's
  per-dimension rule). Sum of scores 2,421.7 → 2,434.5.

## A second, independent drift the refresh exposed

`ty/TARGET_SPEC.md` was derived at `2026-11-11T18:02:03Z` — **93 minutes older than the JSON**
it is supposed to mirror. It still carried the pre-copy-context values: offerchisel 67.0,
towncrier 55.0, socialpulse 67.0, golden-goose 89.4, a duplicate `goldengoose` row and "4 of
29". The JSON had already held 79.5 / 79.0 / 79.7 / 90.0 over 28 services. Regenerating the
spec reconciles it to the JSON; **no JSON score changed** for those services in this unit.

## An evidence label that was wrong, fixed

`score_for` labelled every row in the `services` block as "(generated/composite)". AdPilot's
row lives there but declares `population: service-path`, so the scorecard would have published
"6 Seller-Tester outputs (generated/composite)" — a false population on the one row this unit
touches. The evidence now names the row's own population and path:

```
6 Seller-Tester service-path outputs (population: service-path; path ad_copy), mean 98.1, 5 passed
```

A test pins it (`test_a_service_path_row_in_the_services_block_is_labelled_as_such`).

## Tests

`python -m pytest test_seller_scores.py test_scorecards.py test_ad_copy_scorer.py
test_picture_scorecard.py -q --basetemp=…` → **57 passed**, exit 0.

## A third defect, found while resuming, fixed in the same pass

`python tools/director_queue.py --import-mirror` (run to adopt nine mirror-only jobs) rewrote
every store row into the resume mirror, and `mirror()` built those rows **from the store only**.
Two `blocked_on` reasons and the `note` explaining why a job sits on staging had no store column,
so they vanished from `reports/ty/director_queue.json` — the file a resume reads.
`mirror()` now keeps any key a row already carried that the store does not hold; a test pins it
(`test_the_mirror_preserves_fields_the_store_does_not_hold`). The three known fields were
restored and survive a rewrite: 22 queue tests pass.

## Finding filed, not fixed here

`tools/scorecards.py --json` is documented as "measurement only" but **writes both**
`ty/scorecards.json` and `ty/TARGET_SPEC.md` (lines 472–473 run unconditionally). A measurement
command silently republishes scores. Filed in the queue as `fix-scorecards-json-write`.

## State

No Amazon request, no spend, no GPU work, no browser, no credential read. Soak,
quiet-window waiter and `state/vision/PAUSE` untouched. The next ranked gap is **7.2**, tied
between `listings` (seller 0.0 — an honest zero, its product belongs to listingforge) and
`product-finder` (seller 0.0 — the research path is scored but declared unattributed).
