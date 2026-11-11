# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Position, 2026-11-11 cycle 7 — a third form, and the sample is 20 briefs across five categories

Unit report: `reports/ty/pack01_rigid_cylinder.md`. Tag `ty-dir-pack-01`.

| # | job | result |
|---|---|---|
| 1 | `pack-01-rigid-cylinder-form` — the app printed a pouch and a carton; a mug, a bottle and a tub had no form | merged. `CYLINDER` is a declared form with its own plate brief, its own insets and a **physical** label band: the body's measured width gives px-per-mm, the design's declared label height gives the band height, and a label taller than the body is refused as `label_too_tall_for_body`. Four designs (`word-coffee-canister`, `word-coffee-mug`, `harbor-body-oil`, `pine-paws-joint`), label front/back renderers, `warp_cylinder` now takes the RGB panel the app produces, drawn cylinder body. 23 tests |
| 2 | the catalog | 12 prompt-only briefs wired through the app path (mug 4, skincare 4, pet 4); 5 uploaded-reference briefs left alone for want of a file |

**Published seller dimension: 96.9 over 32 outputs, 32 passed** (was 98.0 over 20).
The catalog pass alone: **20 scored, 20 passed, mean 96.0, five categories**
(ceramic_mug 90, food_jar 95, pet_product 90, skincare_bottle 95, supplement_pouch 100).
Coverage up 60 %, mean down 1.1 — the new pictures are a harder set.

**Checks that fail inside passing pictures:** ST-011/ST-027 are *infographic*
briefs that require margin ink and the app has no overlay layer (D-013); ST-029 is
a `food_jar` brief whose design is the Word Coffee gift box, so it misses a bundle
fill band (D-012). Both are stated in the report, not hidden.

**One command that changes the next number:** start ComfyUI, then
`python -m tools.seller_tester product --renderer comfy --skip-unavailable`.
Every plate stops being drawn — that is job rank 1 (`comfy-plate-live`).

**Next, in rank order:** `comfy-plate-live` → `pack-02-apparel-flat-print` →
`pack-03-boxart-forms` (small appliance + tool) → `sel-04-packaging` →
`fix-bundle-units` (D-012) → `ux-0610-live-verify` (still parked:
`python tools/ty_unlock_checks.py --status`).

## Position, 2026-11-11 cycle 6 — the sample is 20 outputs, and six product categories have no form

Reports: `reports/ty/sel_refs_designs.md`, `reports/ty/sel08_prompt_only_coverage.md`, and the
`sel-06`/`sel-07` corrections below.

| # | job | result |
|---|---|---|
| 1 | `sel-refs-designs` — the rubric had no source | merged. `tools/reference_scout.py`: Openverse, `cc0`/`by`/`by-sa` only, a landing URL to verify at, ≥700 px, a packaging word in the row's own text, and the file must open or it is deleted. **17 kept / 51 refused** over 7 packaging families, every row with creator, licence + version, licence URL and source page. 8 tests |
| 2 | `sel-08-prompt-only-coverage` — the seller sample was stuck at 12 | merged. 8 prompt-only briefs wired to the app path (**8/8, mean 97.5**); **24 refused** with one true reason: *"declares no product_line"* — ceramic mug, apparel, skincare bottle, small appliance, pet product, tool. A catalog pass now records a refusal and continues instead of dying on it |
| 3 | the media flag | fixed. `MEDIA_GEN_LIVE=1` **is** set in `.env`; `engine_status()` said "unarmed" in every tool run because only the API loads dotenv. It now loads the repo `.env` and reports the truth: **gate on, ComfyUI unreachable — start ComfyUI.** Four reports were corrected; 4 tests |
| 4 | `units` through the API | merged. `ProductPictureIn.units` 1–6, passed to `build`; 22 tests in `test_package_forms` |

**Published seller dimension: 20 outputs, mean 98.0, 20 passed** (judged + mechanical held-out + the
catalog pass, deduped by brief). design-studio **89.7**, 4 services at bar.

**Next unit is named, and it is not a brief edit:** the app prints `stand_up_pouch` and `gift_box`, and
the catalog asks for **eight** product categories. A rigid-cylinder form (jar/bottle/tube, via
`mockup_compositor.warp_cylinder`) is the smallest real addition; apparel flat-print and appliance
box-art follow. 24 of 32 prompt-only briefs are waiting on that, not on more testing.

**One command that changes the next number:** start ComfyUI, then
`python -m tools.seller_tester product --renderer comfy --skip-unavailable`. Every plate stops being
drawn.

## Position, 2026-11-11 cycle 5 — bundles measure as bundles

Report: `reports/ty/sel07_bundle_units.md`.

| # | job | result |
|---|---|---|
| 1 | `sel-07-bundle-and-body-shape` — PO-012 asked for three units and measured one | merged. `package_components` keeps every package-sized component (the single-subject mask held **1** component of 343,596 px — the first box only); `find_panel_quads` measures each on its own crop with the neighbours flattened; `build(units=3)` warps one panel per measured face and refuses `units_not_found: measured N of M`. PO-004/PO-012: **3 quads, fill 25.9 % (was 20.3 %), score 100**. The briefs' `body_prompt` said "one unit shown" against a three-unit prompt — corrected. |

**Also fixed, and worth remembering:** `stock_from_brief` matched colour words as substrings, so the
tagline "One Message at a Time" contains **sage** and every Word Coffee box was painted sage-green.
Word boundaries now.

**Judged pass: 12/12, mean 98.3** (was 11/12, 94.9). Seller dimension **98.3**, design-studio
**89.8**, 4 services at bar. The judge moved on PO-002 — the *lifestyle* brief — on the **same flat
sweep**, so its verdict tracked colour, not scene. It is weak evidence for colour and copy and no
evidence for a scene; recorded in the report.

**Next, in rank order:** `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (still parked: `python tools/ty_unlock_checks.py --status`).
Arming `MEDIA_GEN_LIVE` and running `--renderer comfy` remains the one thing that turns every plate
from drawn to real.

## Position, 2026-11-11 cycle 4 — the app prints two forms, and the seller number is the product's

Two jobs merged, both of them structural. Reports: `reports/ty/sel06b_second_brand.md`,
`reports/ty/sel06_product_pipeline.md`.

| # | job | result |
|---|---|---|
| 1 | `sel-06b-second-brand` — the app could print **one** packaging form for **one** brand | merged. `brand_art` is a dispatch layer; the folding-carton renderers are new; a brand is a data entry. Pouch output sha256 `e0160055bf0884c1` **unchanged**. 17 new tests, 55 packaging tests pass, OCR gate on both carton faces, local judge 4/4 at 95 |
| 2 | `sel-06-exercise-product-pipeline` (D-011) — the harness rendered its own lookalike | merged. `ProductPipelineGenerator` calls `product_picture.build` with a supplied plate; refusals carry the app's own reason. Prompt-only 12 held-out briefs, both brands: **12/12 mean 97.5** mechanical, **11/12 mean 94.9** judged |
| 3 | the seller dimension read the harness | merged. `seller_scores.py` publishes the app pass; harness pass not averaged beside it. design-studio **75.9 → 89.3**, seller 94.9 over 12 generated outputs; **4 services at bar** (hub, prospector, keyword-tracker, profitability 100) |

**What the 94.9 does not prove.** The plate is `drawn` (`synthetic_plate`) because
`studio_generation.engine_status()` reports `armed: False` — `MEDIA_GEN_LIVE` is not 1 and ComfyUI is
not reachable. The plate is named in the published record (`pipeline.plate_source: "drawn"`), and the
one judged failure (PO-002) is that plate: the judge's own reasons are "the counter is not a light oak
kitchen counter", "the lighting is not morning light". **Arming the lane and running
`python -m tools.seller_tester product --renderer comfy` is the next real measurement.**

**Next, in rank order:** `sel-07-bundle-and-body-shape` (PO-012 measures one unit of three; the pouch
prompts drew a box twice) → `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (still parked: `python tools/ty_unlock_checks.py --status`).

## Position, 2026-11-11 cycle 3 — prompt-only is honest now, and the label gap is named

Unit report: `reports/ty/rerender_prompt_only_20261111.md`. Six jobs merged, two defects closed.

| # | job | status |
|---|---|---|
| 1 | `rerender-prompt-only` — 12 briefs re-rendered at the same seeds: 9/12 mean 86.4 → 10/12 mean 93.9 | merged |
| 2 | `fix-shadow-frame-clip` — the contact shadow ran past the frame edge and was cut; the six "exactly 90.0" rows were this, not the flat() branch | merged |
| 3 | `fix-fill-and-judge-instruments` — `subject_fill` measured the corner colour on a scene; the judge rubric named the taxonomy slot instead of the product | merged |
| 4 | `fix-queue-mirror-divergence` — the store held 35 jobs while the resume mirror held 51; `mirror()` deleted the difference. 16 jobs recovered, 14 statuses refreshed, `rank` migrated | merged |
| 5 | `fix-launcher-heartbeat-red` (D-010) — heartbeat is red when the stream's last line is an error (243 such lines were on disk) | merged |
| 6 | `fix-dev-start-pids` (D-009) — the pid record is resolved from the listeners and pruned of the dead | merged |
| 7 | `ppc-upload-live` — upload → propose → approve → write v1 → write v2 → download, hash matches | merged |
| 8 | `sel-05-label-fidelity` — label composed and warped onto an unlettered body: judged **83.5 → 98.7**, 12/12 | merged |
| 9 | visual gate, first live run — 62 captures (31 views × desktop + iPhone 12 WebKit) at `/ui/`, no baseline without a passing scorecard; three views described by the local model as real workspaces (`reports/ty/visual_gate_and_views_20261111.md`) | evidence, no code change |

**The seller number, per mode, never blended:** prompt-only 12 scored / **12 passed / 98.3**
mechanically; with the local vision judge (`gemma3:4b`, loopback) **12 passed / 98.7**. Stored
12/11/91.8, uploaded 21/16/90.0 — 45 scored, 39 passed, mean 92.7. **All of it is the harness
pipeline, not the app's** (D-011 below).

**Next, in rank order:** `sel-06-exercise-product-pipeline` (D-011 — until it lands, every seller
number is a harness number) → `sel-07-bundle-and-body-shape` (PO-012 measures one unit of three; the
pouch prompts drew a box twice) → `sel-refs-designs` (21 stored rows are 2 product designs) →
`sel-04-packaging` → `ux-0610-live-verify` (desktop still locked: `tools/ty_unlock_checks.py
--status` says `no foreground window`).

**`sel-coverage-44` was blocked on a measuring error, not on missing work:** 32 of its 44 are
prompt-only briefs, which must *not* have a reference — a prompt-only brief with a stored reference
stops being prompt-only. The real gap is 12 uploaded-reference briefs with no file, plus design depth.

**Defects filed or closed this cycle:** D-008 closed (it was misdiagnosed; the proof carries the
correction), D-009 closed, D-010 closed, D-011 filed (the seller tester renders a lookalike
pipeline), plus three new ones in-repo: the queue/mirror divergence, the clipped shadow, and the two
invalid instruments.

## Queue lease, 2026-11-11T02:08Z — this session holds it (pid 24680, launcher-started)

Step (1) of the resume order, measured before any work:

| check | result |
|---|---|
| `state/director/director.pid` | pid 8864, written `2026-11-11T00:32:40+00:00` — **process gone** (`Get-Process -Id 8864` → nothing) |
| live `--agent director` session | **none** |
| `NorthstarTyDirector` scheduled task | **Running**, started `2026-11-09 09:59:35`, last result `267009` (0x41301, still running) |
| launcher child sessions | **every one dies in under a second with `Agent not found: "director"`** — `logs/ty_director_stream.jsonl` is 73 identical error lines; `logs/ty_director.log` shows a five-minute restart cadence since 2026-11-10T19:40 |
| `NorthstarTysWatchdog` task | Ready, last result `-1073741510` (control-C exit) — **not** keeping anything alive |
| queue lock | there is no separate lock file; the pid file is the lease (`scripts/ty_director.py:find_director`) |

**Conclusion: no other director holds the queue.** The lease is free, so this session claimed every
unclaimed job. The lease was held at the opencode process serving this session (pid 21844) so the
launcher's `find_director` saw a live director and stopped spawning dead children; it is **released at
the end of the unit** (the pid file is cleared) so the launcher resumes on its next tick — and now it
can, because the lane it starts exists.

**Defect found and being fixed:** `opencode.jsonc` defines `tys`, `verifier` and `research` — there is
no `director` agent, so the launcher's `opencode run --agent director` has been failing since it was
installed. The director lane was never actually alive outside a manual chat session. Fixing the config
is a one-line addition; the proof is a launcher tick that reports `running` with a real pid.

## Position, 2026-11-11 (cycle 2)

Unit report: `reports/ty/unit_20261111_security_and_fixes.md`. Nine units merged, three defects filed.

| # | job | status |
|---|---|---|
| 1 | `sec-classify-history` — 88 URLs / 535 assignments / 674 emails / 319 phones, counts only | merged |
| 2 | `sec-wordcoffee-repos` — nine other public repos scanned, Pages listed | merged |
| 3 | `sec-rewrite-plan-extended` — commit map, quiet window, re-point, remap, recreate-private evaluation | merged |
| 4 | `sec-keys-rotated-watcher` — 5-minute model-free poll, then retire + gitleaks + promotion test | merged, running |
| 5 | `fix-stage-refused` — typed `StageRefused`; `ValueError`/`RuntimeError` now abort | merged, 17 tests |
| 6 | `fix-ppc-primary-action` — AdPilot's toast replaced by the real upload→bulk flow | merged, e2e 2/2 |
| 7 | `fix-rescan-main-ef9cad1d` — fixed config, no size cap, 5 findings | merged |
| 8 | `score-prompt-only-rescore` — 90.0 explained; per-mode n/pass/mean | merged |
| 9 | `fix-launcher-director-agent` — the missing lane existed; that is why nothing ran | merged |

**Headline numbers, stated per mode and never blended:** prompt-only n 12 / pass 9 / mean 86.4;
stored-reference 12 / 11 / 91.8; uploaded-reference 21 / 16 / 90.0. Seller reference coverage is
still **12 of 56 briefs** — the rank-1 blocker is unchanged and is job 1 of the next cycle.

**Next cycle, in rank order:** `sel-coverage-44` → `fix-alpha-matte-route` (D-008) →
`ppc-upload-live` → `ux-0610-live-verify` (parked on a locked desktop, verified as locked) →
`fix-launcher-heartbeat-red` (D-010) → `fix-dev-start-pids` (D-009) → `sel-04-packaging`.

## Position, 2026-11-09

| # | job | status |
|---|---|---|
| 1 | `sel-01c-cutout-provenance` | **merged** — the generator saves `<artefact>.cutout.png` + a sidecar; product region verified at 0.9958 / 0.9931 / 0.9835 |
| 2 | `ux-05-render-routes` | **merged** — 29/29 routes render; 60 Playwright tests pass |
| 3 | `reg-01-service-registry` | **merged** — 29 services in `ty/service_registry.json`, tool list and workspaces generated |
| 4 | `sel-02-design-studio` | queued |
| 5 | `sel-03-aplus` | queued |
| 6 | `sel-04-packaging` | queued |
| 7 | `ux-06-shell` | queued |
| 8–10 | `ux-07-tabs`, `ux-08-scene`, `ux-09-design-studio-canvas` | queued |

Both completed prerequisite units sit **ahead of ux-06 shell** in the ranking, which is stored in
`jobs.rank` rather than inferred from insertion order.

## Registry confidence (new)

Every entry now carries `evidence.confidence`: **high 4 · low 21 · none 4**. High means a live
page described with three or more controls; low means a committed screenshot; none means backend
only. A later walk that could not go live **cannot downgrade** a recorded live observation — the
blocked retry goes in `evidence.latest_attempt_blocked` instead.

## Waiting on an unlocked desktop — one command

```
python tools/ty_unlock_checks.py
```

It runs the live walk over every route, applies it to the registry, then runs V3 (ten-task parity
twice) and V9 (dogfood), and refuses by name while the desktop is locked — which it is right now
(`foreground is 'Windows Default Lock Screen'`). `--status` answers the question without running
anything.

## In flight

- **reg-01** (rank 5, ahead of the UX chain) — the **service registry as the single source of
  truth**: walk every advanced-view route with Ty's Vision plus the backend, record purpose,
  inputs, outputs, actions and Bojo tool per service, then generate the Bojo tool list and the
  default Northstar workspaces from it. Advanced view is **not** rebuilt; gaps are recorded in
  `ty/registry_gaps.json` only where a service has no controls.

## Composites: verified at last

The product-region check now runs on the real artefacts and passes:

| brief | score | region (masked SSIM) | passed |
|---|---|---|---|
| MG-C01 white main (flat 255 canvas, 2000 px) | **100** | 0.9958 | yes |
| MG-C02 greenhouse | **81** | 0.9931 | yes |
| MG-C03 forest mockup | **100** | 0.9835 | yes |

**3 passed, mean 93.7, 3 verified.** Two unit bugs had to be fixed to get there: `place_product`
records `[left, top, right, bottom]` and the check took `[x, y, w, h]`, and the audit was
re-implementing a comparison the repo already had — `product_composite.identity_check` was right
all along at 0.9958.

Seller dimension is still 22.1 from the **40-output stored pass**; the three composites are below
the five-output floor, so they inform the proof but not the score yet.

## The reference check changed on 2026-11-08

`tools/seller_tester/reference_check.py` decides by **printed text (OCR, fuzzy token match)**
then **meaning (local embeddings, cosine)**, and reports colour agreement as a **diagnostic
only** — the 0.60 proxy is no longer a gate. `cannot_verify` is still a failure. 44 tests.

## sel-01 landed, and here is exactly how far

56 briefs across the three modes (32 prompt-only, 12 stored-reference, 12 uploaded-reference),
a per-mode summary, and a reference check. A real pass scored **40 outputs: prompt-only 16
(mean 26.4), stored 12 (22.6), uploaded 12 (16.0); 0 passed in any mode.** Seller mean across
the service moved **16.7 → 22.1**, design-studio 75.2 → 75.9.

Three limits the builder stated and I am not going to paper over:

1. **No generator produces *from* an input.** The stored lane replays existing artefacts, so no
   mode is really "covered" — that is what `sel-01b` exists for.
2. **`uploaded_reference` never saw a real upload** — all twelve are `cannot_verify` by
   construction.
3. **The reference proxy has a measured overlap**: a genuine pouch crop fails at 0.603 while
   three dark-green UI screenshots pass at 0.637, so it fails conservatively and cannot be the
   only gate. The local vision judge stays off by default until it is measured.

## The finding that matters most

`python -m tools.vision.ux_audit --run` → **renders 3 of 29**. Only `account`, `beta` and
`design-studio` render their own page. `listings`, `socialpulse`, `competitor-monitor`,
`product-finder`, `listingforge` and the rest open the generic Bojo shell. U12 of the UX work
order passes only if "every service is reachable by click and nothing renders blank"; today it
is not. Evidence: `ty/ux_audit.json` + `reports/ty/ux_audit_shots/`.

## Scoring, 2026-11-09

Seven dimensions, bar 85 each: works 0.23, correct 0.25, complete 0.12, usable 0.07,
measured 0.10, seller 0.13, **contract 0.10** (new, paid for from `works` and `usable`).

**2 services at bar: `hub` 100, `prospector` 100.** Twelve at 86.2, held back by `complete`
because their declared Bojo tool has no handler.

Integrity fix landed with the contract work: `complete` used to mean "this tool's name appears
somewhere in the backend source", which a comment or a test satisfies — `keyword-tracker` and
`profitability` were scoring 100 with no handler at all. It now means a **callable handler
exists** in the chat tool table or the domain registry: the same gate that decides what Bojo is
offered.

Contract check: **20 of 29 pass, 4 persist, 3 gaps, 6 fail** (`reports/ty/contract_01.md`). A
service that only has paid-model actions is never called — that is standing gate (a), not a
skip.

**Today: 2 services at bar (`hub` 100, `prospector` 100), twelve at 86.2.** The ceiling was 77
this morning. `measured` is 28 of 29 after ux-05.

## Verified today

- **D17 complete.** Craft Anything 0.5.0 installed (checksum verified, `doctor` healthy) and the
  bake-off ran all six cells: craft-anything 0.859 / 0.353 / 1.000 vs REA 0.752 / 0.133 / 0.753.
  Craft Anything is the default on all three targets. `reports/ty/d17_bakeoff_final.md`.
- **BASELINE.json** updated from the measured 7,067 run (+450 passed vs 6,617; names +451/−1).
- **V3/V9 run.** V9: design-studio passes the seller task, the other three fail by rendering the
  shell. V3: UIA scores 5/10 because Chrome exposes no renderer accessibility tree; page content
  comes from pixels (`understand.describe_page`), which reads Design Studio correctly.
- **Disk 215 GB free**, worktrees removed.

## What is still open

- The render defect above (ranked 5th by the owner's ordering).
- V3's remaining half: either `--force-renderer-accessibility` or `--remote-debugging-port=9222`
  needs one Chrome relaunch by the owner.
- D17's hosted target: neither tool found the site's facts (0/7 each) — recorded, not hidden.

## Numbers to keep in mind

- 29 services, 0 at bar, best 77. Weakest dimension: 17 `complete`, 10 `seller`, 2 `measured`.
- Router: Bojo 15/18. Vision: qwen2.5vl:7b, page reading works, app reading works, grounding 61.7 %.
- Full suite: 7,067 passed, 0 failed, 117 skipped, 125 subtests, 18:49.
- The dev stack is running on 8101/8000 for the audit; stop it with the recorded pids when idle.

| unit | state | tag | note |
|---|---|---|---|
| D0–D7 | done | `ty-dir-D*` | baseline, probe, launcher, queue, scorecards, gaps, privacy, structure |
| D8 control/browser | done | `ty-dir-D8` | risk classes, verify-after-act (V4), injection (V6), Profile 6 lease, CDP layer; six-point parity 6/6 twice |
| D9 seller-tester | done | `ty-dir-D9` | 32 briefs, 28 tests, 30 artefacts scored, 29 gaps |
| D10 visual regression | done | `ty-dir-D10` | 31 views, frozen scenes, 6/6 fixtures, 41 tests |
| D11 intel plane | done | `ty-dir-D11` | 5 connectors, 58 findings, 58/58 URLs verified |
| D12 parallel bundles | done | `ty-dir-D12` | 6 merged; competitor-monitor 15→85, three services 15→75, 13 × +10 |
| D13 live mode | done | `ty-dir-D13` | narration + Q&A, blocked windows yield no pixels |
| D14 computer mode | done | `ty-dir-D14` | scope + grants; outside-scope write refused |
| D15 verification | done | `ty-dir-D15` | 17 agree, 2 FAILED (D17, V9), 1 BLOCKED (V3) |
| D16 model scout | continuous | `ty-dir-D16` | router eval fixed; Bojo 15/18; qwen3.5:4b +1 (no swap) |
| D17 bake-off | partial | `ty-dir-D17` | REA on the OSS target only; other two no result |
| Chrome via UIA | done | see batch report | CDP unavailable; Profile 6 driven through UIA + pixels |
| Seller dimension | done | — | `seller` 0.13 with a 5-output minimum; a passing test is worth 60, not 100 |

## Scoring changed on 2026-11-08 — read this before trusting a score

Six dimensions: works 0.28, correct 0.25, complete 0.12, usable 0.12, measured 0.10,
seller 0.13. **No service is at the bar, and the ceiling on artefacts alone is 77.** That is
the honest reading: `listings` and `socialpulse` dropped 100 → 77 the moment seller scores
entered the model, because no seller output has been scored for them.

## Blocked, and what unblocks it

1. **V3 parity and V9 dogfood: the desktop is locked** (`foreground = LockApp.exe`). The UIA
   route is built and refuses by name; the dogfood harness is built and refuses by name.
   Unlock the session and run:
   `python -m tools.vision.dogfood --services competitor-monitor,listings,socialpulse`
   then `python -m tools.vision.parity --twice --base http://127.0.0.1:8101/ui/`.
   No password is needed by Ty and none will be used.
2. **D17** needs Craft Anything installed and `northstar-os-ui/dist` built to complete the
   three-target bake-off.

## Queue now

Four bundles were queued by the re-plan (`raise complete` for goldengoose, offerchisel,
prospector, hub) and their Bojo tools are declared. Two builders are implementing them; after
that, re-score and re-plan again. Empty queue means re-plan, never idle.

## Numbers to keep in mind

- 29 services, **0 at bar**, best 77. Weakest dimension across the set: 17 `complete`,
  10 `seller`, 2 `measured`.
- **Full suite on `7fd881cc`/`d2c29a55`: 7,067 passed, 0 failed, 117 skipped, 125 subtests,
  18:49.** Baseline was 6,617 passed / 117 skipped / 125 subtests. Names: +451, −1 (the −1
  has no file and no git history).
- Router: Bojo 15/18. Vision: qwen2.5vl:7b on a clean server, grounding 61.7 % on 40 screens.
- Disk 8.5 GB free; floor 5 GB. ComfyUI is not resident. The 27B needs a lease.

## Rules that are easy to get wrong

- `state/` is gitignored: anything a fresh checkout needs must live under `ty/`.
- A per-dimension bar means an 85 average is not a pass.
- The launcher's pid file is authoritative; the logon task is `NorthstarTyDirector`.
- A bake-off result without an artefact on disk is "did not run". D17 proved that the hard way.
- Never leave a debug script behind; this session's temporary tools were removed.

- 2026-11-09T20:51:18+00:00 launcher: director session ended (session 16592 gone; launcher restarting).

- 2026-11-09T20:56:19+00:00 launcher: director session ended (session 8564 gone; launcher restarting).

- 2026-11-09T21:01:22+00:00 launcher: director session ended (session 23616 gone; launcher restarting).

- 2026-11-09T21:06:25+00:00 launcher: director session ended (session 1936 gone; launcher restarting).

- 2026-11-09T21:11:27+00:00 launcher: director session ended (session 548 gone; launcher restarting).

- 2026-11-09T21:16:30+00:00 launcher: director session ended (session 22168 gone; launcher restarting).

- 2026-11-09T21:21:31+00:00 launcher: director session ended (session 19380 gone; launcher restarting).

- 2026-11-09T21:26:35+00:00 launcher: director session ended (session 22680 gone; launcher restarting).

- 2026-11-09T21:31:36+00:00 launcher: director session ended (session 12080 gone; launcher restarting).

- 2026-11-09T21:36:37+00:00 launcher: director session ended (session 21196 gone; launcher restarting).

- 2026-11-09T21:41:39+00:00 launcher: director session ended (session 18412 gone; launcher restarting).

- 2026-11-09T21:46:41+00:00 launcher: director session ended (session 21780 gone; launcher restarting).

- 2026-11-09T21:51:43+00:00 launcher: director session ended (session 7760 gone; launcher restarting).

- 2026-11-09T21:56:46+00:00 launcher: director session ended (session 24328 gone; launcher restarting).

- 2026-11-09T22:01:48+00:00 launcher: director session ended (session 24288 gone; launcher restarting).

- 2026-11-09T22:06:50+00:00 launcher: director session ended (session 22820 gone; launcher restarting).

- 2026-11-09T22:11:53+00:00 launcher: director session ended (session 22448 gone; launcher restarting).

- 2026-11-09T22:16:56+00:00 launcher: director session ended (session 20600 gone; launcher restarting).

- 2026-11-09T22:21:58+00:00 launcher: director session ended (session 17500 gone; launcher restarting).

- 2026-11-09T22:27:00+00:00 launcher: director session ended (session 7400 gone; launcher restarting).

- 2026-11-09T22:32:01+00:00 launcher: director session ended (session 20736 gone; launcher restarting).

- 2026-11-09T22:37:03+00:00 launcher: director session ended (session 17584 gone; launcher restarting).

- 2026-11-09T22:42:04+00:00 launcher: director session ended (session 24288 gone; launcher restarting).

- 2026-11-09T22:47:06+00:00 launcher: director session ended (session 23292 gone; launcher restarting).

- 2026-11-09T22:52:07+00:00 launcher: director session ended (session 21264 gone; launcher restarting).

- 2026-11-09T22:57:09+00:00 launcher: director session ended (session 9400 gone; launcher restarting).

- 2026-11-09T23:02:10+00:00 launcher: director session ended (session 16296 gone; launcher restarting).

- 2026-11-09T23:07:12+00:00 launcher: director session ended (session 6344 gone; launcher restarting).

- 2026-11-09T23:12:13+00:00 launcher: director session ended (session 18132 gone; launcher restarting).

- 2026-11-09T23:17:14+00:00 launcher: director session ended (session 12760 gone; launcher restarting).

- 2026-11-09T23:22:16+00:00 launcher: director session ended (session 4788 gone; launcher restarting).

- 2026-11-09T23:27:17+00:00 launcher: director session ended (session 3408 gone; launcher restarting).

- 2026-11-09T23:32:19+00:00 launcher: director session ended (session 19876 gone; launcher restarting).

- 2026-11-09T23:37:23+00:00 launcher: director session ended (session 4952 gone; launcher restarting).

- 2026-11-09T23:42:25+00:00 launcher: director session ended (session 22740 gone; launcher restarting).

- 2026-11-09T23:47:27+00:00 launcher: director session ended (session 3288 gone; launcher restarting).

- 2026-11-09T23:52:29+00:00 launcher: director session ended (session 13500 gone; launcher restarting).

- 2026-11-09T23:57:30+00:00 launcher: director session ended (session 22036 gone; launcher restarting).

- 2026-11-10T00:02:36+00:00 launcher: director session ended (session 17620 gone; launcher restarting).

- 2026-11-10T00:07:37+00:00 launcher: director session ended (session 13080 gone; launcher restarting).

- 2026-11-10T00:12:38+00:00 launcher: director session ended (session 15864 gone; launcher restarting).

- 2026-11-10T00:17:40+00:00 launcher: director session ended (session 24012 gone; launcher restarting).

- 2026-11-10T00:22:41+00:00 launcher: director session ended (session 21468 gone; launcher restarting).

- 2026-11-10T00:27:42+00:00 launcher: director session ended (session 3996 gone; launcher restarting).

- 2026-11-10T00:32:44+00:00 launcher: director session ended (session 7456 gone; launcher restarting).

- 2026-11-10T00:37:46+00:00 launcher: director session ended (session 4260 gone; launcher restarting).

- 2026-11-10T00:42:47+00:00 launcher: director session ended (session 16324 gone; launcher restarting).

- 2026-11-10T00:47:48+00:00 launcher: director session ended (session 7808 gone; launcher restarting).

- 2026-11-10T00:52:50+00:00 launcher: director session ended (session 9176 gone; launcher restarting).

- 2026-11-10T00:57:51+00:00 launcher: director session ended (session 16540 gone; launcher restarting).

- 2026-11-10T01:02:53+00:00 launcher: director session ended (session 21004 gone; launcher restarting).

- 2026-11-10T01:07:54+00:00 launcher: director session ended (session 22356 gone; launcher restarting).

- 2026-11-10T01:12:55+00:00 launcher: director session ended (session 15108 gone; launcher restarting).

- 2026-11-10T01:17:57+00:00 launcher: director session ended (session 9360 gone; launcher restarting).

- 2026-11-10T01:22:58+00:00 launcher: director session ended (session 17264 gone; launcher restarting).

- 2026-11-10T01:27:59+00:00 launcher: director session ended (session 18396 gone; launcher restarting).

- 2026-11-10T01:33:01+00:00 launcher: director session ended (session 20040 gone; launcher restarting).

- 2026-11-10T01:38:02+00:00 launcher: director session ended (session 9008 gone; launcher restarting).

- 2026-11-10T01:43:03+00:00 launcher: director session ended (session 20016 gone; launcher restarting).

- 2026-11-10T01:48:05+00:00 launcher: director session ended (session 12040 gone; launcher restarting).

- 2026-11-10T01:53:06+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T01:58:07+00:00 launcher: director session ended (session 19364 gone; launcher restarting).

- 2026-11-10T02:03:09+00:00 launcher: director session ended (session 10552 gone; launcher restarting).

- 2026-11-10T02:08:11+00:00 launcher: director session ended (session 14664 gone; launcher restarting).

- 2026-11-10T02:13:13+00:00 launcher: director session ended (session 22500 gone; launcher restarting).

- 2026-11-10T02:18:15+00:00 launcher: director session ended (session 23632 gone; launcher restarting).

- 2026-11-10T02:23:16+00:00 launcher: director session ended (session 18132 gone; launcher restarting).

- 2026-11-10T02:28:18+00:00 launcher: director session ended (session 6104 gone; launcher restarting).

- 2026-11-10T02:34:09+00:00 launcher: director session ended (session 21552 gone; launcher restarting).

- 2026-11-10T02:39:13+00:00 launcher: director session ended (session 3240 gone; launcher restarting).

- 2026-11-10T02:44:33+00:00 launcher: director session ended (session 23564 gone; launcher restarting).

- 2026-11-10T02:50:06+00:00 launcher: director session ended (session 9540 gone; launcher restarting).

- 2026-11-10T02:55:09+00:00 launcher: director session ended (session 21920 gone; launcher restarting).

- 2026-11-10T03:00:16+00:00 launcher: director session ended (session 23636 gone; launcher restarting).

- 2026-11-10T03:05:20+00:00 launcher: director session ended (session 12768 gone; launcher restarting).

- 2026-11-10T03:10:28+00:00 launcher: director session ended (session 2924 gone; launcher restarting).

- 2026-11-10T03:15:29+00:00 launcher: director session ended (session 8484 gone; launcher restarting).

- 2026-11-10T03:20:31+00:00 launcher: director session ended (session 3380 gone; launcher restarting).

- 2026-11-10T03:25:35+00:00 launcher: director session ended (session 6996 gone; launcher restarting).

- 2026-11-10T03:30:38+00:00 launcher: director session ended (session 9912 gone; launcher restarting).

- 2026-11-10T03:35:39+00:00 launcher: director session ended (session 8144 gone; launcher restarting).

- 2026-11-10T03:40:41+00:00 launcher: director session ended (session 7760 gone; launcher restarting).

- 2026-11-10T03:45:43+00:00 launcher: director session ended (session 10688 gone; launcher restarting).

- 2026-11-10T03:50:45+00:00 launcher: director session ended (session 3220 gone; launcher restarting).

- 2026-11-10T03:55:49+00:00 launcher: director session ended (session 22564 gone; launcher restarting).

- 2026-11-10T04:00:54+00:00 launcher: director session ended (session 21784 gone; launcher restarting).

- 2026-11-10T04:06:03+00:00 launcher: director session ended (session 3768 gone; launcher restarting).

- 2026-11-10T04:11:08+00:00 launcher: director session ended (session 25496 gone; launcher restarting).

- 2026-11-10T04:16:11+00:00 launcher: director session ended (session 22408 gone; launcher restarting).

- 2026-11-10T04:21:13+00:00 launcher: director session ended (session 21072 gone; launcher restarting).

- 2026-11-10T04:26:15+00:00 launcher: director session ended (session 8868 gone; launcher restarting).

- 2026-11-10T04:31:17+00:00 launcher: director session ended (session 4604 gone; launcher restarting).

- 2026-11-10T04:36:18+00:00 launcher: director session ended (session 18320 gone; launcher restarting).

- 2026-11-10T04:41:21+00:00 launcher: director session ended (session 9024 gone; launcher restarting).

- 2026-11-10T04:46:23+00:00 launcher: director session ended (session 20896 gone; launcher restarting).

- 2026-11-10T04:51:25+00:00 launcher: director session ended (session 25260 gone; launcher restarting).

- 2026-11-10T04:56:26+00:00 launcher: director session ended (session 13804 gone; launcher restarting).

- 2026-11-10T05:01:31+00:00 launcher: director session ended (session 3548 gone; launcher restarting).

- 2026-11-10T05:06:33+00:00 launcher: director session ended (session 24692 gone; launcher restarting).

- 2026-11-10T05:11:35+00:00 launcher: director session ended (session 25452 gone; launcher restarting).

- 2026-11-10T05:16:36+00:00 launcher: director session ended (session 22600 gone; launcher restarting).

- 2026-11-10T05:21:38+00:00 launcher: director session ended (session 1656 gone; launcher restarting).

- 2026-11-10T05:26:39+00:00 launcher: director session ended (session 18804 gone; launcher restarting).

- 2026-11-10T05:31:40+00:00 launcher: director session ended (session 21592 gone; launcher restarting).

- 2026-11-10T05:36:42+00:00 launcher: director session ended (session 24068 gone; launcher restarting).

- 2026-11-10T05:41:44+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T05:46:45+00:00 launcher: director session ended (session 14016 gone; launcher restarting).

- 2026-11-10T05:51:46+00:00 launcher: director session ended (session 24612 gone; launcher restarting).

- 2026-11-10T05:56:48+00:00 launcher: director session ended (session 20060 gone; launcher restarting).

- 2026-11-10T06:01:49+00:00 launcher: director session ended (session 23700 gone; launcher restarting).

- 2026-11-10T06:06:51+00:00 launcher: director session ended (session 22652 gone; launcher restarting).

- 2026-11-10T06:11:53+00:00 launcher: director session ended (session 17844 gone; launcher restarting).

- 2026-11-10T06:16:55+00:00 launcher: director session ended (session 21288 gone; launcher restarting).

- 2026-11-10T06:22:00+00:00 launcher: director session ended (session 17936 gone; launcher restarting).

- 2026-11-10T06:27:01+00:00 launcher: director session ended (session 19360 gone; launcher restarting).

- 2026-11-10T06:32:02+00:00 launcher: director session ended (session 16408 gone; launcher restarting).

- 2026-11-10T06:37:04+00:00 launcher: director session ended (session 19428 gone; launcher restarting).

- 2026-11-10T06:42:06+00:00 launcher: director session ended (session 23284 gone; launcher restarting).

- 2026-11-10T06:47:08+00:00 launcher: director session ended (session 11716 gone; launcher restarting).

- 2026-11-10T06:52:10+00:00 launcher: director session ended (session 24344 gone; launcher restarting).

- 2026-11-10T06:57:12+00:00 launcher: director session ended (session 12656 gone; launcher restarting).

- 2026-11-10T07:02:15+00:00 launcher: director session ended (session 16596 gone; launcher restarting).

- 2026-11-10T07:07:28+00:00 launcher: director session ended (session 22712 gone; launcher restarting).

- 2026-11-10T07:12:31+00:00 launcher: director session ended (session 2520 gone; launcher restarting).

- 2026-11-10T07:17:32+00:00 launcher: director session ended (session 24944 gone; launcher restarting).

- 2026-11-10T07:22:34+00:00 launcher: director session ended (session 12856 gone; launcher restarting).

- 2026-11-10T07:27:36+00:00 launcher: director session ended (session 3608 gone; launcher restarting).

- 2026-11-10T07:32:38+00:00 launcher: director session ended (session 9008 gone; launcher restarting).

- 2026-11-10T07:37:48+00:00 launcher: director session ended (session 15924 gone; launcher restarting).

- 2026-11-10T07:42:51+00:00 launcher: director session ended (session 7916 gone; launcher restarting).

- 2026-11-10T07:47:53+00:00 launcher: director session ended (session 20836 gone; launcher restarting).

- 2026-11-10T07:52:54+00:00 launcher: director session ended (session 4804 gone; launcher restarting).

- 2026-11-10T07:57:56+00:00 launcher: director session ended (session 21752 gone; launcher restarting).

- 2026-11-10T08:02:57+00:00 launcher: director session ended (session 25408 gone; launcher restarting).

- 2026-11-10T08:07:59+00:00 launcher: director session ended (session 15072 gone; launcher restarting).

- 2026-11-10T08:13:00+00:00 launcher: director session ended (session 20064 gone; launcher restarting).

- 2026-11-10T08:18:02+00:00 launcher: director session ended (session 13240 gone; launcher restarting).

- 2026-11-10T08:23:03+00:00 launcher: director session ended (session 25256 gone; launcher restarting).

- 2026-11-10T08:28:04+00:00 launcher: director session ended (session 12812 gone; launcher restarting).

- 2026-11-10T08:33:05+00:00 launcher: director session ended (session 7152 gone; launcher restarting).

- 2026-11-10T08:38:07+00:00 launcher: director session ended (session 21344 gone; launcher restarting).

- 2026-11-10T08:43:08+00:00 launcher: director session ended (session 7576 gone; launcher restarting).

- 2026-11-10T08:48:10+00:00 launcher: director session ended (session 6828 gone; launcher restarting).

- 2026-11-10T08:53:12+00:00 launcher: director session ended (session 7400 gone; launcher restarting).

- 2026-11-10T08:58:13+00:00 launcher: director session ended (session 25152 gone; launcher restarting).

- 2026-11-10T09:03:15+00:00 launcher: director session ended (session 22652 gone; launcher restarting).

- 2026-11-10T09:08:16+00:00 launcher: director session ended (session 4120 gone; launcher restarting).

- 2026-11-10T09:13:18+00:00 launcher: director session ended (session 9324 gone; launcher restarting).

- 2026-11-10T09:18:19+00:00 launcher: director session ended (session 20252 gone; launcher restarting).

- 2026-11-10T09:23:20+00:00 launcher: director session ended (session 20500 gone; launcher restarting).

- 2026-11-10T09:28:22+00:00 launcher: director session ended (session 16832 gone; launcher restarting).

- 2026-11-10T09:33:23+00:00 launcher: director session ended (session 12048 gone; launcher restarting).

- 2026-11-10T09:38:25+00:00 launcher: director session ended (session 13268 gone; launcher restarting).

- 2026-11-10T09:43:26+00:00 launcher: director session ended (session 2728 gone; launcher restarting).

- 2026-11-10T09:48:28+00:00 launcher: director session ended (session 21204 gone; launcher restarting).

- 2026-11-10T09:53:29+00:00 launcher: director session ended (session 3824 gone; launcher restarting).

- 2026-11-10T09:58:31+00:00 launcher: director session ended (session 21076 gone; launcher restarting).

- 2026-11-10T10:03:33+00:00 launcher: director session ended (session 13772 gone; launcher restarting).

- 2026-11-10T10:08:34+00:00 launcher: director session ended (session 19728 gone; launcher restarting).

- 2026-11-10T10:13:35+00:00 launcher: director session ended (session 3500 gone; launcher restarting).

- 2026-11-10T10:18:37+00:00 launcher: director session ended (session 2416 gone; launcher restarting).

- 2026-11-10T10:23:39+00:00 launcher: director session ended (session 1496 gone; launcher restarting).

- 2026-11-10T10:28:40+00:00 launcher: director session ended (session 19304 gone; launcher restarting).

- 2026-11-10T10:33:41+00:00 launcher: director session ended (session 23132 gone; launcher restarting).

- 2026-11-10T10:38:43+00:00 launcher: director session ended (session 3708 gone; launcher restarting).

- 2026-11-10T10:43:44+00:00 launcher: director session ended (session 24432 gone; launcher restarting).

- 2026-11-10T10:48:46+00:00 launcher: director session ended (session 21476 gone; launcher restarting).

- 2026-11-10T10:53:47+00:00 launcher: director session ended (session 6236 gone; launcher restarting).

- 2026-11-10T10:58:48+00:00 launcher: director session ended (session 24356 gone; launcher restarting).

- 2026-11-10T11:03:50+00:00 launcher: director session ended (session 4408 gone; launcher restarting).

- 2026-11-10T11:08:51+00:00 launcher: director session ended (session 18688 gone; launcher restarting).

- 2026-11-10T11:13:53+00:00 launcher: director session ended (session 23684 gone; launcher restarting).

- 2026-11-10T11:18:56+00:00 launcher: director session ended (session 13548 gone; launcher restarting).

- 2026-11-10T11:23:57+00:00 launcher: director session ended (session 21320 gone; launcher restarting).

- 2026-11-10T11:28:58+00:00 launcher: director session ended (session 1492 gone; launcher restarting).

- 2026-11-10T11:34:00+00:00 launcher: director session ended (session 4196 gone; launcher restarting).

- 2026-11-10T11:39:02+00:00 launcher: director session ended (session 8504 gone; launcher restarting).

- 2026-11-10T11:44:03+00:00 launcher: director session ended (session 23132 gone; launcher restarting).

- 2026-11-10T11:49:04+00:00 launcher: director session ended (session 23128 gone; launcher restarting).

- 2026-11-10T11:54:07+00:00 launcher: director session ended (session 22212 gone; launcher restarting).

- 2026-11-10T19:35:22+00:00 launcher: director session ended (session 20356 gone; launcher restarting).

- 2026-11-10T19:40:24+00:00 launcher: director session ended (session 12192 gone; launcher restarting).

- 2026-11-10T19:45:27+00:00 launcher: director session ended (session 17768 gone; launcher restarting).

- 2026-11-10T19:50:29+00:00 launcher: director session ended (session 3708 gone; launcher restarting).

- 2026-11-10T19:55:31+00:00 launcher: director session ended (session 228 gone; launcher restarting).

- 2026-11-10T20:00:34+00:00 launcher: director session ended (session 25964 gone; launcher restarting).

- 2026-11-10T20:05:37+00:00 launcher: director session ended (session 18440 gone; launcher restarting).

- 2026-11-10T20:10:39+00:00 launcher: director session ended (session 24140 gone; launcher restarting).

- 2026-11-10T20:15:40+00:00 launcher: director session ended (session 23228 gone; launcher restarting).

- 2026-11-10T20:20:42+00:00 launcher: director session ended (session 8176 gone; launcher restarting).

- 2026-11-10T20:25:45+00:00 launcher: director session ended (session 24988 gone; launcher restarting).

- 2026-11-10T20:30:47+00:00 launcher: director session ended (session 20428 gone; launcher restarting).

- 2026-11-10T20:35:49+00:00 launcher: director session ended (session 5272 gone; launcher restarting).

- 2026-11-10T20:40:51+00:00 launcher: director session ended (session 11568 gone; launcher restarting).

- 2026-11-10T20:45:54+00:00 launcher: director session ended (session 26172 gone; launcher restarting).

- 2026-11-10T20:50:56+00:00 launcher: director session ended (session 5576 gone; launcher restarting).

- 2026-11-10T20:55:59+00:00 launcher: director session ended (session 21644 gone; launcher restarting).

- 2026-11-10T21:01:01+00:00 launcher: director session ended (session 14444 gone; launcher restarting).

- 2026-11-10T21:06:04+00:00 launcher: director session ended (session 17852 gone; launcher restarting).

- 2026-11-10T21:11:06+00:00 launcher: director session ended (session 25292 gone; launcher restarting).

- 2026-11-10T21:16:08+00:00 launcher: director session ended (session 16004 gone; launcher restarting).

- 2026-11-10T21:21:10+00:00 launcher: director session ended (session 21852 gone; launcher restarting).

- 2026-11-10T21:26:11+00:00 launcher: director session ended (session 20692 gone; launcher restarting).

- 2026-11-10T21:31:14+00:00 launcher: director session ended (session 11232 gone; launcher restarting).

- 2026-11-10T21:36:16+00:00 launcher: director session ended (session 21920 gone; launcher restarting).

- 2026-11-10T21:41:19+00:00 launcher: director session ended (session 2104 gone; launcher restarting).

- 2026-11-10T21:46:22+00:00 launcher: director session ended (session 3132 gone; launcher restarting).

- 2026-11-10T21:51:24+00:00 launcher: director session ended (session 22776 gone; launcher restarting).

- 2026-11-10T21:56:26+00:00 launcher: director session ended (session 15080 gone; launcher restarting).

- 2026-11-10T22:01:28+00:00 launcher: director session ended (session 15588 gone; launcher restarting).

- 2026-11-10T22:06:31+00:00 launcher: director session ended (session 9160 gone; launcher restarting).

- 2026-11-10T22:11:34+00:00 launcher: director session ended (session 404 gone; launcher restarting).

- 2026-11-10T22:16:36+00:00 launcher: director session ended (session 8148 gone; launcher restarting).

- 2026-11-10T22:21:38+00:00 launcher: director session ended (session 5772 gone; launcher restarting).

- 2026-11-10T22:26:39+00:00 launcher: director session ended (session 21984 gone; launcher restarting).

- 2026-11-10T22:31:41+00:00 launcher: director session ended (session 2872 gone; launcher restarting).

- 2026-11-10T22:36:47+00:00 launcher: director session ended (session 14080 gone; launcher restarting).

- 2026-11-10T22:41:51+00:00 launcher: director session ended (session 3044 gone; launcher restarting).

- 2026-11-10T22:46:52+00:00 launcher: director session ended (session 24840 gone; launcher restarting).

- 2026-11-10T22:51:55+00:00 launcher: director session ended (session 14228 gone; launcher restarting).

- 2026-11-10T22:56:56+00:00 launcher: director session ended (session 6504 gone; launcher restarting).

- 2026-11-10T23:01:59+00:00 launcher: director session ended (session 11156 gone; launcher restarting).

- 2026-11-10T23:07:01+00:00 launcher: director session ended (session 21804 gone; launcher restarting).

- 2026-11-10T23:12:03+00:00 launcher: director session ended (session 21352 gone; launcher restarting).

- 2026-11-10T23:17:06+00:00 launcher: director session ended (session 25792 gone; launcher restarting).

- 2026-11-10T23:22:09+00:00 launcher: director session ended (session 15080 gone; launcher restarting).

- 2026-11-10T23:27:12+00:00 launcher: director session ended (session 23100 gone; launcher restarting).

- 2026-11-10T23:32:14+00:00 launcher: director session ended (session 3168 gone; launcher restarting).

- 2026-11-10T23:37:17+00:00 launcher: director session ended (session 19888 gone; launcher restarting).

- 2026-11-10T23:42:19+00:00 launcher: director session ended (session 26400 gone; launcher restarting).

- 2026-11-10T23:47:20+00:00 launcher: director session ended (session 16912 gone; launcher restarting).

- 2026-11-10T23:52:22+00:00 launcher: director session ended (session 10040 gone; launcher restarting).

- 2026-11-10T23:57:26+00:00 launcher: director session ended (session 16224 gone; launcher restarting).

- 2026-11-11T00:02:27+00:00 launcher: director session ended (session 14876 gone; launcher restarting).

- 2026-11-11T00:07:29+00:00 launcher: director session ended (session 14224 gone; launcher restarting).

- 2026-11-11T00:12:31+00:00 launcher: director session ended (session 7876 gone; launcher restarting).

- 2026-11-11T00:17:33+00:00 launcher: director session ended (session 4504 gone; launcher restarting).

- 2026-11-11T00:22:35+00:00 launcher: director session ended (session 13788 gone; launcher restarting).

- 2026-11-11T00:27:38+00:00 launcher: director session ended (session 16696 gone; launcher restarting).

- 2026-11-11T00:32:40+00:00 launcher: director session ended (session 20632 gone; launcher restarting).

- 2026-11-11T00:37:42+00:00 launcher: director session ended (session 8864 gone; launcher restarting).

- 2026-11-11T00:42:44+00:00 launcher: director session ended (session 25480 gone; launcher restarting).

- 2026-11-11T00:47:46+00:00 launcher: director session ended (session 15316 gone; launcher restarting).

- 2026-11-11T03:43:57+00:00 launcher: director session ended (session 24680 gone; launcher restarting).

- 2026-11-11T05:14:38+00:00 launcher: director session ended (session 26360 gone; launcher restarting).
