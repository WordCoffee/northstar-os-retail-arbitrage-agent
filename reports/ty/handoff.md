# Ty Director — handoff

A fresh session continues from this file plus `ty/MANDATE.md`, `ty/TARGET_SPEC.md` and
`reports/ty/director_queue.json`.

## Resume line

> Hi, I'd like to give a work order to Ty. Resume the director program. Read
> `reports/ty/director_work_order.md`, `ty/MANDATE.md`, `reports/ty/director_queue.json`,
> and `reports/ty/handoff.md`, then continue from the first unfinished unit. No
> questions, no reports between cycles. Idle means re-plan.

## Position: D0–D17 complete; the gap-driven loop has four bundles queued

| unit | state | tag | note |
|---|---|---|---|
| D0–D7 | done | `ty-dir-D*` | baseline, probe, launcher, queue, scorecards, gaps, privacy, structure |
| D8 control/browser | done | `ty-dir-D8` | risk classes, verify-after-act (V4), injection (V6), Profile 6 lease, CDP layer; six-point parity 6/6 twice; **V3 not run** |
| D9 seller-tester | done | `ty-dir-D9` | 32 briefs, 28 tests, 30 artefacts scored, 29 gaps |
| D10 visual regression | done | `ty-dir-D10` | 31 views, frozen scenes, 6/6 fixtures, 41 tests |
| D11 intel plane | done | `ty-dir-D11` | 5 connectors, 58 findings, 58/58 URLs verified |
| D12 parallel bundles | done | `ty-dir-D12` | 6 merged; competitor-monitor 15→85, three services 15→75, 13 × +10; 2 at bar |
| D13 live mode | done | `ty-dir-D13` | narration + Q&A, blocked windows yield no pixels |
| D14 computer mode | done | `ty-dir-D14` | scope + grants; outside-scope write refused; PC mode needs flag **and** grant |
| D15 verification | done | `ty-dir-D15` | 17 agree, 2 FAILED, 1 BLOCKED (`reports/ty/d15_summary.md`) |
| D16 model scout | continuous | `ty-dir-D16` | router eval fixed; Bojo 15/18; qwen3.5:4b +1 (no swap) |
| D17 bake-off | done (partial) | `ty-dir-D17` | REA on OSS target only; other two no result; earlier verdict withdrawn |

## Two things are not done, by name

1. **V3 / Chrome Connect parity.** Chrome has no `--remote-debugging-port`, so Ty's Vision
   cannot attach, the ten-task suite reports `not_run`, and the quarantine gate correctly
   refuses. Chrome Connect stays the controller. One owner action, `needs_you.md` **DIR-4**:
   close Chrome, reopen with
   `--profile-directory="Profile 6" --remote-debugging-port=9222`.
2. **V9 dogfood.** Driving the real UI needs V3. The Seller-Tester, live mode and verify-
   after-act all exist; nothing has driven the real UI end to end. It stays FAILED until V3.

## Queue now

`python tools/director_gaps.py --replan` has queued four bundles, all `raise complete`:
goldengoose, offerchisel, prospector, hub (+10 each). Next session: claim them, one worktree
each, gates, merge to `staging`, re-score.

## Numbers to keep in mind

- 29 services scored, **2 at bar** (listings 100, socialpulse 100), 27 below; worst gap 9.5.
- Router: Bojo 15/18; best candidate qwen3.5:4b 16/18, inside the swap margin.
- Vision: qwen2.5vl:7b on a clean server (f16 KV, ctx 8192); grounding 61.7 % on 40 screens.
- Disk 10.8 GB free; floor 5 GB. GPU: ComfyUI is not resident — a render lane starts and stops
  its own instance.
- The 27B is off unless `gpu_budget.heavy_lease('27b', reason=...)` is called.

## Rules that are easy to get wrong

- `state/` is gitignored: anything a fresh checkout needs must live under `ty/`.
- A per-dimension bar means an 85 average is not a pass.
- The launcher's pid file is authoritative; the logon task is `NorthstarTyDirector`.
- A bake-off result without an artefact on disk is "did not run". D17 proved that the hard way.
- Never leave a debug script behind; this session's temporary tools were removed.
