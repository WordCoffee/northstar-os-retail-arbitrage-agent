# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

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
