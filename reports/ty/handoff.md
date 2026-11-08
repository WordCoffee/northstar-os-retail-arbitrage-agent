# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Position: units done, queue re-ranked, one product defect dominating

The queue is now ordered by the owner's instruction (2026-11-08): seller output quality first.

| # | job | what closes it |
|---|---|---|
| 1 | `sel-01-picture-modes` | product pictures in all three inputs: prompt only, stored reference, uploaded reference |
| 2 | `sel-02-design-studio` | Design Studio output quality (the 16.7 mean must move) |
| 3 | `sel-03-aplus` | A+ content modules, briefs + scored outputs |
| 4 | `sel-04-packaging` | packaging and mockups, dielines + scored outputs |
| 5 | `ux-05-render-routes` | **26 of 29 service routes render the chat shell** |

## The finding that matters most

`python -m tools.vision.ux_audit --run` → **renders 3 of 29**. Only `account`, `beta` and
`design-studio` render their own page. `listings`, `socialpulse`, `competitor-monitor`,
`product-finder`, `listingforge` and the rest open the generic Bojo shell. U12 of the UX work
order passes only if "every service is reachable by click and nothing renders blank"; today it
is not. Evidence: `ty/ux_audit.json` + `reports/ty/ux_audit_shots/`.

## Scoring (unchanged, and strict)

Six dimensions, bar 85 each: works 0.28, correct 0.25, complete 0.12, usable 0.12,
measured 0.10, seller 0.13. `seller` applies only to the ten seller-facing services. A passing
test is worth 60 on `correct`. **0 services at bar; 77 is the ceiling on artefacts alone.**

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
