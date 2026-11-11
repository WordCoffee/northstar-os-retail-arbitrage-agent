# lane B (block4) — seller-tester beyond images, and D-019

Unit `block4-seller-tests` (queue rank 7), plus the D-019 decision assigned with it.
Bar: four non-image service paths exercised the way a seller walks them, each with a real
run on disk; the existing subcommands still work; scores recorded where the model applies;
and D-019 decided on evidence, not preference.

Nothing here contacted an Amazon host, opened a browser, spent money, or touched the GPU.
`state/vision/PAUSE` exists, so no browser was opened at all.

## What changed

| file | line | change |
| --- | --- | --- |
| `tools/seller_tester/services.py` | 1-633 | new: the four paths and their checks |
| `tools/seller_tester/services.py` | 97 | `score_checks` — share of graded checks; a skip is not a pass |
| `tools/seller_tester/services.py` | 139 | `run_listing` — `compose_listing` -> `reasoning_tasks.listing_proposal` |
| `tools/seller_tester/services.py` | 247-277 | `run_ppc` — the bulksheet API, in-process, temp sqlite |
| `tools/seller_tester/services.py` | 384 | `run_golden_goose` — `golden_goose_scan` (real fee stack + scorer) |
| `tools/seller_tester/services.py` | 461 | `run_research` — `research_graph.research` over a local corpus |
| `tools/seller_tester/services.py` | 552-633 | `parse_only`, `run_pass` (`--only`), proof file |
| `tools/seller_tester/service_briefs.json` | 1-… | new: offline fixtures for the four paths |
| `tools/seller_tester/cli.py` | 366-376, 401-418, 442 | `services` subcommand + `_cmd_services` |
| `tools/seller_tester/scorers.py` | 523-560 | `_components` (numpy union-find over run-lengths) |
| `tools/seller_tester/scorers.py` | 591 | `check_stray_marks` — the D-019 instrument |
| `tools/seller_tester/scorers.py` | 687-740 | `judge_constraint` — the question, scoped by population |
| `tools/seller_tester/scorers.py` | 1058 | `stray_marks` recorded as a diagnostic in `score_image` |
| `tools/seller_tester/harness.py` | 349, 385-391 | pass the generation's layout record; carry the diagnostic into the row |
| `tools/seller_tester/stray_report.py` | 1-237 | new: D-019 measured with code + the composed-page control |
| `tools/seller_tester/README.md` | 25-40, 130-200 | the four paths, the stray rule, the commands |
| `Northstar_backend/test_seller_services.py` | 1-215 | 13 tests (happy path + a control per path) |
| `Northstar_backend/test_seller_stray_marks.py` | 1-190 | 11 tests (the rule, the control, the score does not move) |
| `tests/e2e/seller/test_seller_cli_e2e.py` | 1-80 | 8 tests: the CLI run as an operator runs it |
| `ty/scorecards.json` | design-studio row | `89.7 -> 89.5`, `seller 98.0 (20 outputs) -> 96.2 (32)` |

## The four paths, as run

`python -m tools.seller_tester services` (exit 0; 1.82 s on the final run, 10:43:01):

| path | brief | score | passed | checks |
| --- | --- | --- | --- | --- |
| listing | LST-001 | 100.0 | yes | 9 graded (title/bullets/description limits, no prohibited phrase, copy audit, no invented number, reasons, provenance, never applied) |
| listing | LST-002 | 100.0 | yes | 9 graded |
| ppc | PPC-001 | 100.0 | yes | 10 graded (upload parsed, sheet detected, before/after bid, unblocked, approved, v1 written, round-trip, v2 is a new file, download hashes to the written checksum, original untouched) |
| golden_goose | GG-001 | 100.0 | yes | 8 graded (every candidate evaluated, REJECT dropped, descending rank, filters, economics, "why", thresholds) |
| research | RES-001 | 100.0 | yes | 8 graded (3 axes, evidence, distinct sources, corroboration, single-source labels, conflict, headline, no web crawl) |

`scored: 5, passed: 5, refused: 0`. Proof: `state/seller/services_proof.json`; artefacts:
`state/seller/services/<path>/` (including `bulk-20261111-change-v1.xlsx`, 1 854 bytes,
`PK` signature, sha256 equal to the change file's recorded checksum).

**The listing provider is a recorded fixture and is labelled as such** in the record
(`provider: "recorded-fixture"`, plus `recorded_provider_note` in the proof). A live
reasoning call is a paid action; what the score measures is the app's own deterministic
normalisation of that answer — limits, prohibited phrases, copy audit, provenance —
which is exactly what a seller's listing is judged on here.

Every path has a control that proves its checks can fail:

| control | result |
| --- | --- |
| listing copy with "Best Seller", "GUARANTEED" and an unsourced "500 mg" | `no_prohibited_phrase` **fail**, `no_invented_numbers` **fail** (`500 mg` named) |
| listing brief with no recorded answer | `ServiceRefused`, no score invented |
| PPC with the wrong expected before-bid | `proposal_before_after` **fail** |
| Golden Goose with the wrong first place | `best_row_is_first` **fail** |
| research with an empty corpus | `evidence_returned` **fail** — "no passage was retrieved" |

## D-019 — the verdict is two defects, not one

I looked at the pixels and at the code that drew them.

**(b) PO-007 is a scoring/acceptance bug, and it is fixed inside this manifest.** The two
marks the judge named are drawn by the harness itself, in `deterministic.infographic`:
the accent rule at `tools/seller_tester/deterministic.py:293-297`, the subtitle rule at
`:387`, the footer rule at `:286`, and the callout leader line and its anchor dot at
`:404-410`. The judge was asked "is the product free of stray marks" of a page whose rule,
heading, chips and dots live in the margin *by construction* (`deterministic.py:241-243`).
The page measured 2 000 x 2 500 and its own components sit exactly where the code draws
them: the accent rule at y 45-65, the heading glyphs at y 108-221, the photo panel at
y 821-1 779 — all outside the panel the product sits in.

Fix: `scorers.judge_constraint` asks the right question of the right population. A
**composed page** is judged on the photograph inside its panel, with the furniture named
as exempt; a **photograph** keeps the plain question; a **refused or absent layout** is
judged as a photograph, i.e. the stricter question, never the weaker one. `check_stray_marks`
makes the same distinction in code (frame = the panel, inset past its border), and it is
recorded as a **diagnostic** (`stray_marks`), never a weight, so no published score moved.

Proven by the control, not by the words: `stray_report.synthetic_page` composes a page with
the real layout, scores it, then pastes one detached stroke inside the panel and scores it
again.

```
synthetic clean_page:     ok=True  marks=0
synthetic page_with_dash: ok=False marks=174  1 stray mark(s) at (10,247)-(20,281)
```

**(a) PO-006 is an app bug, and I did not touch the file.** The failure is real: the
artefact carries a dashed streak below-left of the gift box, and it is not a scene object —
PO-006 is `series_consistency`, which takes no layout stage, and the picture is on a flat
255 field. The instrument finds four detached dashes at 271 / 361 / 668 / 869 px
(5.5-7.6 px thick) with the strict pass
(`state/seller/d019_stray_report.json`, `marks_hugging_the_silhouette` → PO-006, 4 marks,
2 169 px, largest at (316,1549)-(431,1612)). They are dropped only when the recorded
silhouette is honoured, and at least half of each dash's pixels lie within 3 px of it: the
silhouette the app saved already includes the streak's neighbourhood, which is why
`drop_detached_specks` and `drop_thin_runs` keep it.

The exact defect, for whoever owns the file:

> **D-019(a) — the cutout keeps a dashed streak that is attached to the product's own
> silhouette.** Measured on `renders/heldout_prompt_only10/PO-006.png`: four detached dash
> pieces (271 / 361 / 668 / 869 px, 5.5-7.6 px thick) survive on a flat #FFFFFF page below
> the gift box, and the recorded silhouette `PO-006.mask.png` reaches to within 3 px of at
> least half of each piece's pixels. `product_composite.drop_thin_runs` only deletes a
> leading or trailing run of **rows** thinner than 12 % of the median body width, so a
> diagonal stroke that spans many rows at a few pixels per row is never a "thin run"; and
> `drop_detached_specks` cannot drop a piece that the silhouette says is part of the body.
> The result is a scissor-cut line pasted with an otherwise clean product, and the recorded
> silhouette then hides it from the residue check (D-026). Owning file:
> `Northstar_backend/product_composite.py` (`drop_detached_specks`, `drop_thin_runs`), with
> the silhouette half in `Northstar_backend/product_cutout.py`. Touching it needs a
> cutout-quality lane; nothing in `tools/seller_tester/**` can fix it, and a harness change
> that hid it would be the precise mistake this verdict is written to prevent.

`python -m tools.seller_tester.stray_report` over the twelve stored artefacts: **12
artefacts, 8 measured, 4 skipped, 8 clean, 0 flagged**. The four skips say why rather than
passing quietly: PO-002 and PO-010 are scene photographs whose background is not a field
(corner levels span 52 and 168 levels), and PO-007/PO-008 are composed pages written before
the layout record carried a panel rect — their question is answered by the fresh synthetic
page above, not guessed from a stored file.

## Scores and the scorecard

The four paths' own scores live in `state/seller/services_proof.json` (above). They are
**not** published into the `seller` dimension of `listings`, `goldengoose`, `product-finder`
or `adpilot`, and I want that decision to be visible rather than silent: that dimension is
defined by `tools/seller_scores.py`, which reads **image** passes only
(`state/seller/product_*.json`), and a score typed into `ty/scorecards.json` by hand would
be reverted by the next `python tools/scorecards.py` run. That file is outside this lane's
manifest. The one-line change that would publish them — a `ServicePath` source in
`seller_scores._sources()` — is named here, not made.

What did genuinely change is the row my measurement disagreed with. `ty/scorecards.json`
said design-studio **89.7 / seller 98.0 over 20 outputs**; `tools.seller_scores` had been
regenerated later (`ty/seller_scores.json`, `at 2026-11-11T06:57:54Z`) from **32** outputs
at **96.2**, and the scorecard had not been re-run. I updated that one row to the measured
value — `89.5`, seller `96.2`, "32 Seller-Tester outputs … mean 96.2, 32 passed" — and
verified it equals a fresh `tools.scorecards.measure()` for every field. No other service
moved: `test_ids` is 7 465 on both sides.

## Tests

```
python -m pytest Northstar_backend/test_seller_tester.py \
  test_seller_tester_composite.py test_seller_scores.py test_seller_packaging.py \
  test_seller_label_warp.py test_seller_deterministic.py test_seller_tester_aplus.py \
  test_seller_tester_product_pipeline.py test_seller_services.py \
  test_seller_stray_marks.py test_amazon_files_primary_action.py -q
                                                   -> 183 passed in 45.72s
python -m pytest Northstar_backend/test_scorecards.py \
  test_product_composite_framing.py test_stage_guard.py -q
                                                   -> 32 passed in 1.19s
python -m pytest tests/e2e/seller -q                -> 8 passed in 2.13s
```

24 of those tests are new (13 service-path, 11 stray-mark), plus 8 end-to-end. No existing
assertion was weakened: the PPC route's proven test (`test_amazon_files_primary_action.py`)
is unchanged and green, and the new PPC path asserts the same properties (checksum of the
download equals the written file, version increments, a second write is a new file, the
original is untouched).

## Refused, and why

- **A live reasoning call for the listing path** — a paid action. Recorded fixture instead,
  labelled in every record.
- **The local vision judge** (`gemma3:4b`) — a GPU lane, and this lane is the one heavy
  lane. The D-019 evidence is the recorded judge output plus the code that drew the marks
  plus a deterministic re-measurement; the judge was not re-run and nothing here claims it
  was.
- **Any browser** — `state/vision/PAUSE` exists; the end-to-end test drives the CLI
  subprocess, not a page.
- **Publishing the four paths' scores into `ty/scorecards.json`** — the consumer is outside
  this manifest and a hand edit would be reverted (see above).

## What a verifier should re-run

```
python -m tools.seller_tester services --only listing,ppc,golden_goose,research
python -m tools.seller_tester.stray_report --json
python -m pytest Northstar_backend/test_seller_services.py \
  Northstar_backend/test_seller_stray_marks.py tests/e2e/seller -q
```

Then open `renders/heldout_prompt_only10/PO-006.png` and look below-left of the box: the
dashed streak is visible to the eye, which is why the verdict is (a) for it and not a rubric
argument.
