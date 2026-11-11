# Lane F — the seller dimension for the service paths

Lane: builder F, 2026-11-11. Scope: `tools/seller_tester/**`, `tools/seller_scores.py`,
`Northstar_backend/test_seller_*.py`, `ty/seller_scores.json`, `ty/scorecards.json`.

The seller dimension was 0.0 for 9 of 29 services. That is a real measurement — the rule
is `MIN_SCORED = 5` outputs in one population — but it was also a measurement of a sample
that did not exist: the four non-image paths carried 5 briefs between them (2 listing, 1
ppc, 1 golden goose, 1 research), which is two short of a sample for even one path.

This lane grew the catalogue to 21 briefs, ran it, and taught the scorer to read the pass
per service in a population of its own.

## 1. The brief catalogue: 5 → 21 briefs

`tools/seller_tester/service_briefs.json`, version 2. Each path now carries at least five
distinct situations, ordered ordinary → awkward. No two briefs differ only by a colour word:
every one changes the product, the constraint, or the thing that can go wrong.

| path | before | after | new situations |
|---|---|---|---|
| `listing` | 2 | 6 | a draft carrying an unsupported claim that must be removed (LST-003); a title pushed to the 200-char ceiling with five factual bullets (LST-004); a multi-pack whose pack count, unit size and total must all be sourced (LST-005); a seller who supplied one fact and no description at all, where nothing may be invented (LST-006) |
| `ppc` | 1 | 5 | three campaigns, a bid *cut* deep in the sheet (PPC-002); a paused parent campaign with one enabled ad group (PPC-003); eight rows in one ad group, target at the top of the useful range (PPC-004); two portfolios, target on the last row (PPC-005) |
| `golden_goose` | 1 | 5 | one product offered by four sellers where Amazon and the brand owner are on the listing (GG-002); the fattest margin is 5.6 lb and over the size ceiling (GG-003); both floors raised to $20 and 3000/mo (GG-004); a case whose pack ROI is huge and whose per-unit profit is $4.81 (GG-005) |
| `research` | 1 | 5 | two sources that **agree** and one that is silent (RES-002); a three-way disagreement that must arrive as one conflict (RES-003); a percentage disagreement with a corroborated method (RES-004); two conflicts where the money is the only disagreement (RES-005) |

Two harness changes were needed so the new situations could be judged rather than merely
run — both are assertions added, none removed:

* `services.py::run_listing` gained **`draft_claims_removed`**. A brief can declare
  `must_not_keep` (the claim its own draft carries); the proposal must not repeat it, and a
  brief that declares a phrase its own draft does not carry **fails** rather than passing
  vacuously. Graded for LST-003; skipped, and said so, for the five briefs with no claim.
* `services.py::run_research` made `numeric_conflict_surfaced` **bidirectional**. A named
  value list means "these figures must arrive as one conflict" (unchanged); `[]` now means
  "these sources were declared to agree, so surfacing a conflict is the bug"; an absent key
  is a skip with a reason instead of a silent failure.

## 2. The pass: 21 scored, 19 passed, 0 refused

```
python -m tools.seller_tester services
```
```
listing      6 scored  6 passed  mean 100.0
ppc          5 scored  5 passed  mean 100.0
golden_goose 5 scored  3 passed  mean  95.6
research     5 scored  5 passed  mean 100.0
total       21 scored 19 passed  refused 0
summary: state/seller/services_proof.json
```
23 s of wall clock is not the story; 2 s is. Every path runs offline against local fixtures
and local code — no network, no model, no Amazon host, no GPU.

### The two briefs that fail, and why they stay

Both are Golden Goose, both are real findings about `opportunity_scorer.py`, and neither is
a fixture mistake. Neither was deleted, and neither was re-pointed at an easier candidate.

**GG-002 — `reject_tier_dropped`: "B0GG2002 is in the returned rows".**
The candidate whose seller is `Amazon.com` (`is_amazon_seller: true`) is returned as a
**MEDIUM** row with `filters.seller_identity = false` and the tag `amazon_seller_present`.
The brand-owner offer (`is_brand_seller: true`, seller "Harbor Brand Store") is returned the
same way. The module documents seller identity as a **HARD BLOCK**; `_assign_tier()` only
uses `passes_all_filters` to gate **HIGH**, so a hard-blocked row that clears `composite >=
0.4` and the profit floor comes back as MEDIUM and is presented to the seller anyway. A
seller reading that list can bid on a listing where Amazon itself is the seller.
Evidence: `state/seller/services/golden_goose/GG-002.json`.

**GG-003 — `best_row_is_first`: "first row B0GG3001, best reported B0GG3001".**
A 90 oz blender ($33.65 net/unit, `filters.size = false`, tier MEDIUM) is ranked first and
is the scan's own `best_asin`. The only row that passes **every** hard filter — the 26 oz
body lotion, $15.75 net, tier HIGH — is second. `composite` weights profit, demand,
competition, health, price gap and ad feasibility and contains no size term at all, so the
"best opportunity" the scanner names can be a product its own filters disqualified.
Evidence: `state/seller/services/golden_goose/GG-003.json`.

Consequence: `golden_goose` scores **95.6**, not 100. Two of five briefs lose one check of
nine (88.9 each). That penalty is the point — a path that cannot fail a brief is not being
measured.

## 3. Who owns which path (declared, not inferred)

Attribution is declared once, in the fixture: `service_attribution` in
`service_briefs.json`. `tools/seller_scores.py` reads that block; it does not parse
filenames.

| path | service | evidence in the repo |
|---|---|---|
| `listing` | `listingforge` | the path calls `bojo_tools.publishing.compose_listing` → `reasoning_tasks.listing_proposal`; `ty/services.json` gives **listingforge** the `compose_listing` tool ("ListingForge copy") |
| `golden_goose` | `goldengoose`, alias `golden-goose` | the path calls `bojo_tools.sourcing.golden_goose_scan`; `ty/services.json` declares `golden_goose_scan`, and the **same purpose text**, for both ids |
| `ppc` | `design-studio` | upload → proposal → approve → write → download are the `/api/design-studio/amazon-files/*` endpoints in `design_studio_api.py`, and the surface is Design Studio → Ads → Amazon files (`northstar-os-ui/src/pages/internal/design-studio/AmazonFiles.jsx`). **AdPilot only reads** the imported bulksheets (`AdPilot.jsx:75`), so it is not the producer |
| `research` | **none** | nothing in `ty/services.json` or the backend reaches `research_graph.research`; only its own test does. Measured, reported, attributed to nobody |

**The alias, stated plainly.** `goldengoose` and `golden-goose` both declare the
`golden_goose_scan` tool and the same purpose in `ty/services.json` — they are one product
under two registry ids, so they receive the identical five-brief sample.
`test_each_path_names_the_one_service_that_produces_it` asserts that an alias declares the
*same tools* as its owner, so the alias cannot be used to attach a sample to an unrelated
service. If the director prefers one id, deleting `aliases: ["golden-goose"]` from the
fixture leaves `golden-goose` at 0.0 and changes nothing else.

**`ppc` is never blended into Design Studio's published score.** Design Studio's seller
number is its 32 generated product pictures (96.2). The five PPC rows are a separate
population; `score_for` reports the picture mean and says the service-path rows exist and
are not averaged in. That is the never-mix rule exercised on a service that has both.

## 4. Scorer: a third population, same floor, never mixed

`tools/seller_scores.py`:

* `service_attribution()` reads the declared block; `service_path()` buckets the pass per
  service under population **`service-path`**, with `paths`, `scored`, `passed`, `mean`,
  `at`, `command`, and `refused` (a refusal is recorded with the engine's words and is
  **not** counted as a sample — a refusal must never be silently worth a zero);
* `MIN_SCORED = 5` is unchanged and applies **per population**. A service gets a score from
  one population: its picture pass when it has ≥5 of those, otherwise its service-path pass
  when it has ≥5 of those, otherwise 0 with the counts of both named. The two are never
  added: 3 pictures + 3 listing briefs is two samples of three, so nothing is scored;
* `build()` emits a `service_path` block beside `services` and adds
  `pass.service_path`. The disk proof is read **only** when no image pass is injected, so a
  test that supplies its own rows stays hermetic.

## 5. Before / after, per service

Before: `ty/scorecards.json` at `2026-11-11T05:04:46+00:00`, 29 services, 16 at or above the
85 score, 13 below, **9 with `seller = 0.0`**, mean 81.67.
After: **6 with `seller = 0.0`**, mean 82.97. Four services are at the bar before and after
(`hub`, `prospector`, `keyword-tracker`, `profitability`); the `correct` dimension is capped
at 60 for seller-facing services by design, so a seller score alone cannot carry anyone to 85.

| service | score before | score after | seller before | seller after | why |
|---|---|---|---|---|---|
| `listingforge` | 77.0 | **90.0** | 0.0 | **100.0** | 6 listing briefs, 6 passed. 77 + 0.13 × 100 |
| `goldengoose` | 77.0 | **89.4** | 0.0 | **95.6** | 5 golden-goose briefs, 3 passed (GG-002, GG-003 above). 77 + 0.13 × 95.6 |
| `golden-goose` | 77.0 | **89.4** | 0.0 | **95.6** | the same declared service under the registry's second id |
| `design-studio` | 89.5 | 89.5 | 96.2 | 96.2 | unchanged: its published population is its 32 product pictures. Its 5 PPC service-path rows are reported and not blended |
| `listings` | 77.0 | 77.0 | 0.0 | 0.0 | **no path exists.** Its tool is `optimize_listing` (a deterministic rubric rewrite in `chat_tools._t_optimize_listing`); the seller-tester has no runner for it. Nothing was borrowed from the listing path — a score must come from outputs the service actually produces |
| `offerchisel` | 67.0 | 67.0 | 0.0 | 0.0 | **no path exists.** Its tool is `offer_recommendation` (`bojo_tools_ops.py:159`) |
| `adpilot` | 67.0 | 67.0 | 0.0 | 0.0 | **no path exists.** Its tool is `plan_campaign` → `ad_pilot.generate_campaign_structure`; the PPC bulksheet path AdPilot *reads* belongs to Design Studio, so lending it here would be a false attribution |
| `socialpulse` | 67.0 | 67.0 | 0.0 | 0.0 | **no path exists.** Its tool is `plan_social` |
| `product-finder` | 77.0 | 77.0 | 0.0 | 0.0 | **no path exists.** Its tool is `scan_products`; the research path does not call it, so the research sample is unattributed rather than reassigned |
| `towncrier` | 55.0 | 55.0 | 0.0 | 0.0 | **no path and no tool**: `ty/services.json` declares none, so `complete` is 0.0 as well. The seller dimension cannot be the only gap here |

The other 19 services are unchanged (their seller dimension does not apply, or is not
seller-facing). Full diff: `git diff ty/scorecards.json`.

**What would move the remaining six**: one runner per tool, five briefs each, in
`tools/seller_tester/services.py` — `optimize_listing` (listings), `offer_recommendation`
(offerchisel), `plan_campaign` (adpilot), `plan_social` (socialpulse), `scan_products`
(product-finder). Each is deterministic and offline, so each is buildable exactly like the
four here. Towncrier needs a tool before it needs a brief. That work is a lane of its own;
it was not attempted here rather than faked with an attribution that does not hold.

## 6. Exact commands

```
python -m tools.seller_tester services
python tools/seller_scores.py --write
python tools/scorecards.py
python -m pytest Northstar_backend/test_seller_scores.py Northstar_backend/test_seller_services.py \
    Northstar_backend/test_scorecards.py Northstar_backend/test_seller_tester.py \
    Northstar_backend/test_seller_packaging.py Northstar_backend/test_seller_deterministic.py \
    -q -p no:cacheprovider --basetemp C:\Users\T2Hol\AppData\Local\Temp\opencode\laneF\pytest2
```
`134 passed, 1 warning in 21.93s`. Also `test_ty_digest.py` + `test_director_gaps.py`:
`13 passed in 3.98s`. `python tools/scorecards.py` reports `services 29, at_bar 4`.

### Tests added (not weakened)

`test_seller_services.py`: the fixture must carry ≥5 briefs per path; no path may repeat an
id/sku/query; every path must be attributed or explicitly declared unowned, and an
attributed service must declare the tool that path exercises (a registry cross-check); a
kept draft claim must fail; a stale `must_not_keep` must fail; sources declared to agree must
**not** report a conflict, and a planted disagreement in that same corpus must be caught.
The stale `summary["scored"] == 1` assertion became `== len(fixtures["golden_goose"])`,
because the catalogue grew.

`test_seller_scores.py`: per-service bucketing with its own population; the 5-output floor
applies to the service-path population; a full path sample names its population; pictures +
path are never added; the picture population wins where it is the service's own output, and
says the path rows exist; an alias reads the same bucket and says it is an alias; a refusal
is recorded and is not a sample; an unowned path lends its sample to nobody; `build()` is
hermetic under injection; the live block matches its proof file.

Two of those are the anti-self-grading controls the brief asked for: the sample floor and
the never-mix rule are each proven by a case that must return 0.0.

## 7. Files written (and the two side effects)

Manifest files: `tools/seller_tester/service_briefs.json`, `tools/seller_tester/services.py`,
`tools/seller_scores.py`, `Northstar_backend/test_seller_services.py`,
`Northstar_backend/test_seller_scores.py`, `ty/seller_scores.json`, `ty/scorecards.json`,
this report.

Side effects of the required commands, not edits: `state/seller/services_proof.json` and
`state/seller/services/**` (the pass's own output — the input the scorer reads; `state/` is
untracked here), and `ty/TARGET_SPEC.md` (`python tools/scorecards.py` renders the spec from
the scores it just wrote; leaving it stale would make the two disagree). `tools/scorecards.py`
was **not** modified — its CLI needed no flag.

Nothing under `northstar-os-ui/**`, `docs/**`, `tools/registry/**`, `Northstar_backend/main.py`
or `Northstar_backend/rate_limiter.py` was touched, and no other `reports/ty/*` file was
edited. No Amazon host, no credential, no login, no spend, no GPU, no browser.
