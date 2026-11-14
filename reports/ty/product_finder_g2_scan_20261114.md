# Product Finder G2 — its own seller score on its own surface (2026-11-14)

**Outcome: closed. Product Finder's seller dimension is 100.0 over 5 of its own scan
briefs, and the service moves 77.0 → 90.0 (gap 7.2 → 0.0).** The ranked gap is now Listings
alone (7.2, an honest zero that belongs to ListingForge).

## Why this is the honest path, not the research sample

`seller_scores.json` already carried a `research` service-path sample (5 scored, 5 passed,
mean 100) and declared it **unattributed**, for a reason that still holds: no service in
`ty/services.json` declares a path that reaches `research_graph.research`. Nothing in the
backend or the UI calls it. Attributing that sample to Product Finder would have been
inventing an owner — the one thing the attribution block exists to prevent.

Product Finder does declare a tool: **`scan_products`** (`ty/services.json` → `tools:
[scan_products]`). That is its primary action, and `fix-product-finder-wiring` had already
given it a backend (contract: `GET /api/products/finder` → 200, 89 evaluated rows). So the
score is built on what the service actually produces.

## What was added

A new service path, **`scan`**, in `tools/seller_tester/services.py`:

- **5 briefs** (`service_briefs.json` → `scan`), each a recorded candidate cache: a fresh
  cache with two matches and one non-match, a stale cache matched through a keyword, a
  `limit=1` brief over three matches, a second stale cache, and a **refusal** brief (missing
  cache, no candidate sharing a term).
- **7 graded checks on a positive brief**, all the app's own rules:
  `scan_returned_rows`, `every_candidate_matches_the_query` (the tool's own `_matches`
  predicate), `respects_limit`, `cache_provenance_reported`, `source_is_the_cache` (no live
  request), `no_invented_fields` (the scan computes no economics — that is Golden Goose's
  job, and the check proves no field was added), `declared_non_match_excluded`.
- **3 checks on the refusal brief**: `refusal_is_named`, `refusal_reports_the_cache`,
  `no_live_request`.
- The scanner is **injected** with the fixture cache. A live search is a gated, paid action;
  the fake scanner raises if a live call is attempted, so "network: none" is measured, not
  asserted. No Amazon host is contacted at any point.

**Attribution is declared**: `service_briefs.json → service_attribution.scan` names
`product-finder`, gives the reason, and records that the cache is a fixture. The registry
test now pins `scan → scan_products` as Product Finder's declared tool.

## Measured

| item | value |
|---|---|
| scan path | **5 scored / 5 passed / mean 100.0 / 0 refused** |
| full services pass | **41 scored / 35 passed / 0 refused**, network none |
| Product Finder scorecard | **77.0 → 90.0**; seller **0.0 → 100.0**; gap **7.2 → 0.0**; weakest `seller → correct` |
| row-level diff vs HEAD | **only product-finder changed**, 28 services either side |
| at-bar (every dimension ≥ 85) | 4 of 28, unchanged; `correct` stays 60 by the artefact rule |

**Honest limit:** the candidate cache is a recorded fixture because a live search is a gated,
paid action. The score describes the app's filtering, limit, provenance reporting and
refusal — not a live Amazon result. The service's `correct` dimension stays 60 by design, so
it leaves the ranked gap list but is **not** "at bar on every dimension".

## A regression this unit found and fixed

Rebuilding `ty/seller_scores.json` (`tools/seller_scores.py --write`) **deleted AdPilot's
98.1 ad-copy row**. That row is written by a different command
(`tools/seller_tester/ad_copy_run.py`), and `build()` reconstructed `services` from image
passes only. The previous unit's score survived exactly one rebuild.

`build()` now folds `state/seller/ad_copy_proof.json` into `services.adpilot` (and never
reads the disk when sources are injected), and the generated totals are summed over
**generated** rows only, so a service-path row cannot enter them. AdPilot is back at 98.1
(path `ad_copy`), Design Studio's 32-picture pass is untouched (32/32 generated), and a test
pins both facts.

**Tests:** `pytest Northstar_backend/test_seller_services.py test_seller_scores.py
test_scorecards.py test_ad_copy_scorer.py test_picture_scorecard.py` → **81 passed**, exit 0.
The suite includes one control per scan check, each proving the check can fail.

## State

No Amazon request, no spend, no GPU work, no browser, no credential read. Soak,
quiet-window waiter and `state/vision/PAUSE` untouched.
