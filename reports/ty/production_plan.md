# Production plan — Northstar OS

Made 2026-11-05 from a full read of the repo, the test suite, the backlog, the
reports directory and the running services. Revised every 10 cycles.

**Ranking key:** `priority = impact (1-10) x gap (0-100)`. Gap is *measured
where an instrument exists* and recorded as an estimate with its basis where one
does not — an estimate is labelled so it cannot be mistaken for a measurement.

**Bar convention:** every workstream has a numeric bar, a held-out set fixed
before tuning, and a dwell rule. Nothing is declared ready by Ty; the
independent verifier must reproduce the scorecard (C5).

| Rank | Workstream | Impact | Gap (basis) | Priority | Dwell |
|---|---|---|---|---|---|
| 1 | W2 Listing optimization | 9 | 80 (no instrument) | 720 | until-production-ready |
| 2 | W3 PPC / ad creative | 8 | 85 (no instrument) | 680 | bounded 6 |
| 3 | W1 Product pictures | 10 | 65 (measured) | 650 | until-production-ready |
| 4 | W4 Research / sourcing | 8 | 75 (partial: freshness only) | 600 | bounded 6 |
| 5 | W5 Golden Goose finder | 8 | 60 (suite green, no precision) | 480 | bounded 5 |
| 6 | W7 Packaging creator | 8 | 55 (gates exist, no print round-trip) | 440 | bounded 5 |
| 7 | W13 Billing stubs | 6 | 70 (blocked on owner) | 420 | parked |
| 8 | W6 Design studio | 9 | 45 (lanes verified) | 405 | until-production-ready |
| 9 | W10 Performance | 6 | 60 (no budget) | 360 | bounded 4 |
| 10 | W11 Onboarding | 7 | 50 (first-run exists, no score) | 350 | bounded 4 |
| 11 | W9 Auth + security | 10 | 30 (suite green) | 300 | bounded 3 |
| 12 | W12 Observability | 6 | 50 | 300 | bounded 3 |
| 13 | W14 Docs | 4 | 40 | 160 | bounded 2 |
| 14 | W8 Northstar UX rebuild | 7 | 20 (16/16 units done) | 140 | bounded 2 |

---

## W1 Product pictures — **in flight, instrument built**

**Goal.** A seller can produce any product picture they need from (1) a prompt,
(2) a reference they made earlier, (3) a photo/logo/packaging they upload — and
the system refuses a picture that would embarrass them on a marketplace.

**Scenarios (60 fixed cases, 20 per mode, already frozen in
`eval/product_pictures/cases.json`, sha256 `b49e8c95…`):** main on pure white,
lifestyle, infographic callouts, scale comparison, feature close-up, multi-angle
set, bundle/variety, before/after, seasonal, A+ module, packaging mockup
(front/rear), background swap, consistent series, upscale/export, ingredient
detail, gift pack, countertop context, secondary benefit. Split: 45 dev, 15
held out (every fourth case), fixed before any tuning.

**Scorecard** (`Northstar_backend/picture_scorecard.py`, config
`config/picture_scorecard.json`): instruction fidelity, product fidelity,
photographic quality, marketplace compliance, text accuracy, set consistency,
speed, failure recovery. Bar: **every measured dimension >= 85 and compliance
100%**, twice in a row on the held-out set.

**Measured now** (12 dev cases, 4 per mode, `state/evidence/picture_bench_*.json`):

| dimension | before cycle 1 | after cycle 1 |
|---|---|---|
| marketplace compliance | 0.0% (0/2) | **100% (3/3)** |
| speed | 100 | 100 |
| text accuracy | 50 | 50 |
| set consistency | 0.0 | 34.7 |
| product fidelity | 24.9 (4 measured) | 0.0 (8 measured) |
| instruction fidelity | unmeasured | unmeasured |
| photographic quality | unmeasured | unmeasured |
| stored-reference cases | 4 failed (`reference_missing`) | 4 rendered |

**Known defects to fix next:** fidelity is measured whole-image, so a lifestyle
scene against a front packshot scores 0 by construction — it must compare the
product region, or only score where framing is comparable; text is drawn by the
model on reference renders (`KERT& SLATE`); instruction fidelity and photographic
quality need the model axes enabled (`--models`) and a second run.

**Dependencies:** ComfyUI + gateway up; >= 4 GB free RAM before each render;
reference library seeded. **write_paths:** `Northstar_backend/picture_scorecard.py`,
`Northstar_backend/reference_library.py`, `Northstar_backend/listing_render.py`,
`Northstar_backend/product_picture.py`, `tools/run_picture_bench.py`,
`tools/probe_image_lanes.py`, `eval/product_pictures/`, `config/picture_scorecard.json`.

## W2 Listing optimization — rank 1

**Goal.** Turn a product and a supplier sheet into a listing that passes a
marketplace rubric: title, five bullets, description, backend keywords, A+ copy,
with no prohibited claims and correct units.

**Scenarios:** title length and keyword placement; bullet benefit/feature split;
prohibited-word screen (cure, treat, FDA, best-seller); numeric claims that must
match the label (2000 mg, 85 servings); unit and size conversions; category
mismatch; duplicate/variant listings; non-English supplier sheet; A+ six-module
copy.

**Scorecard:** rubric compliance (programmatic, 0-100), claim safety (must be
100%: zero prohibited claims shipped), factual grounding (every number traceable
to the input sheet), readability (grade level + sentence length), keyword
coverage against a fixed held-out query set, and human-preference win rate on a
blind A/B against the current output.

**Held-out set:** 40 listings written by the owner's own hand or taken from
published top-seller listings before any tuning. Bar: 85 overall, 100% claim
safety, two consecutive runs.

**Dependencies:** none technically; needs a copy of the owner's preferred
listing style as a reference set (see `needs_you.md`).
**write_paths:** `Northstar_backend/specialists/listing_optimizer.py`,
new `Northstar_backend/listing_scorecard.py`, `eval/listings/`,
`Northstar_backend/test_listing_scorecard.py`.

## W3 PPC / ad creative — rank 2

**Goal.** Campaign structure, keyword harvest, negative-keyword hygiene, and ad
copy that a seller can paste into a campaign without editing.

**Scenarios:** exact/phrase/broad split from a search-term report; negative
harvest from zero-conversion terms; bid suggestions from a cost model; ad copy
within character limits with a compliant claim set; seasonal budget shift;
placement modifiers; a campaign with no data (must refuse to invent).

**Scorecard:** structural validity (100% required), waste removed (share of
spend on zero-conversion terms before/after), coverage of converting terms,
copy compliance (100%), and a simulated ACoS delta on a fixed historical report.
**Held-out:** three historical search-term reports never used during tuning.
**Dependencies:** point-in-time fixtures (already in `data/`), no live Amazon.
**write_paths:** `Northstar_backend/specialists/` (ad paths), `eval/ppc/`,
`Northstar_backend/ppc_scorecard.py`.

## W4 Research / sourcing — rank 4

**Goal.** Find products worth selling: cost at the source, price at the
marketplace, fees, net, ROI, competition, and a freshness stamp that cannot lie.

**Scenarios:** fresh catalog vs stale; missing fee data (must say so); pack-size
mismatch; multi-pack vs single; discontinued; price outside band; category with
default fee; a source with no API (must refuse, not scrape Amazon).

**Scorecard:** data completeness (fraction of candidates with every field
measured), freshness correctness (a stale record must be labelled stale —
100%), arithmetic correctness on a hand-checked set (100%), and precision of the
"worth buying" verdict against a hand-labelled set of 50 candidates.
**Held-out:** 50 hand-labelled candidates. **Dependencies:** Costco data path
(fixtures only), no Amazon. **write_paths:** `Northstar_backend/scanner*`,
`Northstar_backend/specialists/*sourc*`, `eval/sourcing/`.

## W5 Golden Goose finder — rank 5

**Goal.** Find mispriced/undervalued items from a catalog with a defensible
reason, not a hunch.

**Scenarios:** single match, ambiguous match, no match, brand blocklist,
rights-filtered record, duplicate, missing dimensions.
**Scorecard:** match precision/recall on a labelled fixture set, refusal
correctness on unlabelled/ambiguous items (must abstain), and rights-filter
compliance (100%). Bar: precision >= 0.90, recall >= 0.75, zero rights leaks.
**Held-out:** 120 labelled fixtures. **Dependencies:** existing 511-test suite.
**write_paths:** `agents/golden_goose_finder/`, `eval/golden_goose/`.

## W6 Design studio — rank 8

**Goal.** Dielines, print files, mockups and composed artwork that a printer can
use, with the measurement done on the file, not on a promise.

**Scenarios:** 8 dieline templates; label fit on a measured pouch face;
prepress TAC/gamut; bleed and safe zones; PDF/SVG/ZIP export; text legibility
after warp; a brand-new plate with no preset (must measure, not assume).
**Scorecard:** prepress pass rate (100% under TAC 300 and in gamut), legibility
pass rate, geometry validity (valid SVG/PDF magic + closed paths), and print
round-trip on a real die drawing when one exists.
**Held-out:** three dielines not used for template development.
**Dependencies:** fonts/assets present. **write_paths:**
`Northstar_backend/design_studio_print.py`, `mockup_compositor.py`,
`pouch_label.py`, `prepress.py`, `eval/design_studio/`.

## W7 Packaging creator — rank 6

**Goal.** From "a 6 oz stand-up pouch for lion's mane coffee" to a printable
pack: dieline, panel layout, copy, mockup, and a package-readiness verdict.

**Scenarios:** pouch/box/bottle/can; front/back/side; nutrition panel; barcode
and UPC placement; net-weight and ingredient statements; multi-language; a
supplier-supplied die drawing; a format with no template (must refuse).
**Scorecard:** readiness verdict correctness on a labelled set (100% — a false
"ready" is the failure mode), copy accuracy (OCR of the produced panel matches
the brief, 100%), and prepress pass rate.
**Held-out:** 10 packs the operator has already produced by hand.
**Dependencies:** W6. **write_paths:** `Northstar_backend/package_design.py`,
`package_readiness.py`, `eval/packaging/`.

## W8 Northstar UX rebuild — rank 14

**Goal.** The default experience (Northstar) is usable by a first-time seller;
the advanced view is reachable and does not regress.

**Scenarios:** first run, sign-in, recovery, setup, documents, plan, support,
account, every internal room, mobile bottom nav, command palette, empty states,
error states, a11y names.
**Scorecard:** e2e pass rate (desktop Chromium + iPhone 12 WebKit), a11y
violations (0 critical), console errors (0), and task completion time on three
scripted journeys.
**Measured now:** `reports/ty/ux_queue.json` **16/16 units done**; probe spec
passes on both projects. Gap is verification depth, not feature work.
**Held-out:** the three journeys, written before the next UI change.
**write_paths:** `northstar-os-ui/src/`, `tests/e2e/`.

## W9 Auth + security — rank 11

**Goal.** No dev bypass in a production build; sessions, roles and tenant
isolation hold; secrets never leak.

**Scenarios:** dev-shim denied outside development/loopback; session cookie
contract; role gate per route; tenant isolation; rate limiting; secret scan.
**Scorecard:** security suite pass (100%), production-bundle assertion (no
`DEV: AUTH DISABLED` / demo session in `dist/`), secret scan clean, and a
reproduced tenant-isolation test.
**Measured now:** foundation suites green; the production-bundle assertion is a
**checklist item, not an automated gate** — that is the gap.
**write_paths:** `Northstar_backend/foundation/`, `scripts/security_checks.ps1`,
new `scripts/assert_production_bundle.py`.

## W10 Performance — rank 9

**Goal.** A render, a listing and a scan finish inside a seller's patience
budget on this box.

**Scenarios:** 1024 render, 2000 px export, video 15 s, listing generation,
scan of 200 candidates, cold start vs warm.
**Scorecard:** p50/p95 seconds per operation against a fixed budget (render
<= 90 s p95, listing <= 20 s, scan <= 60 s), memory peak, and failure rate under
concurrency 2.
**Measured now:** 1024 render 36.3 s (draft), reference render 48.7-75.8 s,
vision 17 s — but no budget is enforced anywhere.
**write_paths:** `Northstar_backend/studio_generation.py`, `scripts/`,
`eval/performance/`.

## W11 Onboarding — rank 10

**Goal.** A new seller reaches their first useful output without a human.

**Scenarios:** first run with no data, sample data, missing provider, missing
GPU, expired session, returning user with work in progress.
**Scorecard:** steps to first artifact (target <= 5), completion rate on a
scripted journey, and error-recovery rate (does the UI explain the fix).
**Held-out:** five first-time-user transcripts.
**write_paths:** `northstar-os-ui/src/pages/`, `Northstar_backend/onboarding*`.

## W12 Observability — rank 12

**Goal.** Any failure is visible before the seller reports it.

**Scenarios:** engine down, model evicted, disk low, RAM low, queue blocked,
render refused, provider unarmed.
**Scorecard:** detection rate on injected faults (100%), time to detect,
false-positive rate, and whether the message names the fix.
**write_paths:** `Northstar_backend/*health*`, `Northstar_backend/ops_status.py`,
`eval/observability/`.

## W13 Billing stubs — rank 7, **parked**

**Goal.** Credits meter, reserve, commit and release without a real processor.
**Status:** the ledger and the meter-only mode exist; a real top-up needs an
owner-configured processor (see `needs_you.md`). Nothing here blocks a
workstream, so it is parked rather than ranked by effort.
**write_paths:** `Northstar_backend/usage_meter.py`, `credit*`.

## W14 Docs — rank 13

**Goal.** A new engineer can run, test and extend the system from the docs.
**Scorecard:** a scripted "fresh clone to green suite" run with no undocumented
step; every claim in `docs/` checked against a command.
**write_paths:** `docs/`, `README.md`.

---

## Standing constraints that shape every cycle

- No Amazon host, ever; no spend; dev bypass stays dev-only.
- A render needs >= 4 GB free RAM and the brain drained; the flow is
  drain -> verify -> render -> restore -> health-check, in a `finally`.
- `tests/BASELINE.json` moves only from a measured full run, compared by test
  name, never by count alone.
- A cycle that cannot lift a dimension by 5 points or close 3 gaps is not
  shipped; it becomes discovery instead.
