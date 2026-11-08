# D15 — independent verification, and what the Director did about it

The verifier ran in a separate session (`reports/ty/d15_verification.md`, 20 items). It built
none of this and reproduced every claim with its own command. Result: **17 agree, 2 FAILED,
1 BLOCKED**.

## The verdict table

| # | item | verdict |
|---|---|---|
| 1 | scorecards reproduce (29 services, 2 at bar, 6789 ids) | agree |
| 2 | D9 seller-tester (28 tests; 29 gaps, all artefacts real) | agree |
| 3 | D10 visual regression (41 tests; 6/6 fixtures) | agree |
| 4 | D11 intel (54 tests; 58 findings; 3 URLs re-checked) | agree |
| 5 | D16 leaderboard (15/18, +1 margin, keep incumbent) | agree |
| 6 | **D17 bake-off** | **FAILED** |
| 7 | V1 screen awareness | agree |
| 8 | V2 element read (20/20) | agree |
| 9 | V3 parity | **BLOCKED** |
| 10 | V4 verify-after-act | agree |
| 11 | V5 privacy | agree |
| 12 | V6 injection | agree |
| 13 | V7 kill switch + pause | agree |
| 14 | V8 resource budget | agree |
| 15 | **V9 dogfood** | **FAILED** |
| 16 | production bundle assertion (14 passed, 0 failed) | agree |
| 17 | six-point parity (all six verified) | agree |
| 18 | disk floor and digest | agree |
| 19 | scope enforcement | agree |
| 20 | launcher persistence | agree |

## What was done about each finding

**D17 FAILED — fixed as far as this machine allows.** The artefacts had been written to a
gitignored directory inside a worktree that was removed at merge, so the claim could not be
reproduced. It was re-probed: the OSS target was restored
(`state/vendor/todomvc`, shallow sparse clone), REA ran with exit 0 and 10/10 facts, and its
7.1 MB artefact is now tracked under `reports/ty/d17_artefacts/`. The hosted and local-app
targets still have no result (REA exits 1 on both; Craft Anything is not installed), and the
earlier three-target verdict is **withdrawn** in `reports/ty/d17_bakeoff_reprobe.md`. D17 is
therefore *partly* reproduced, not passed.

**Digest bug — fixed.** `ty_digest.py` read only `{"gaps": [...]}` and reported 0 for a bare
29-item list. It now counts both shapes, with a test
(`test_a_bare_list_and_a_wrapped_list_are_both_counted`), and the digest prints 29 seller
gaps and 58 intel findings.

**V9 FAILED — not fixable in this environment, and recorded as such.** V9 asks the
Seller-Tester to drive the real Northstar UI through the Vision Operator: generate a product
picture, then open it in the Design Studio. That needs a live UI to drive and a Vision
Operator that can act on a browser. Browser control is V3, and V3 is blocked on the CDP
endpoint (below). The pieces exist — `tools/seller_tester` generates and scores,
`tools/vision/live.py` narrates, `tools/vision/act.py` acts with verification — but nothing
has driven the real UI end to end, so V9 is **FAILED** and stays failed until V3 has an
endpoint. Calling it anything else would be the optimistic status the mandate forbids.

**V3 BLOCKED — one owner action.** Chrome is running without `--remote-debugging-port`, and
the standing rules forbid Ty from killing Chrome or creating a throwaway profile. The ten-task
suite therefore reports `not_run` for both backends (the Chrome Connect adapter also has no
runner CLI), and the quarantine gate correctly refuses. The exact command is in
`reports/ty/needs_you.md` (DIR-4). Chrome Connect remains the controller until then.

## What this means for the completion bar

| bar item | status |
|---|---|
| launcher survives reboot | task registered with a logon trigger, action proven to run (exit 0); a real reboot was not performed because it would end the owner's session |
| empty queue triggers re-plan, never idle | implemented and tested (D5); the launcher writes the re-plan note |
| ≥3 parallel bundles merged to staging with score before/after | **6 merged**; competitor-monitor +70, prospector/thewatch/rivalboard +60, 13 services +10 at the time |
| Seller-Tester filed real gaps | 29 gaps on the first pass, 57 after the second, all pointing at real artefacts |
| V1–V9 pass | V1/V2/V4–V8 pass; **V3 BLOCKED** (locked desktop / no CDP), **V9 FAILED** |
| Chrome Connect parity passed twice | six-point contract verified twice; ten-task suite **not run** |
| intel plane ≥10 findings | 58 findings, 58/58 URLs verified |
| model leaderboards re-run on GPU | router eval re-run; Bojo 15/18; no swap |
| verifier agree/FAILED per unit | 17 agree, 2 FAILED, 1 BLOCKED |

## Correction, 2026-11-08 (same day): the scorecard got stricter, so the numbers moved

The 2-at-bar result above came from a scorecard that credited tests and routes. The owner
then required Seller-Tester output scores in the model. With `seller` as a 0.13-weight
dimension, a `correct` of 60 for test-only evidence, and a five-output minimum:

| service | then | now | why |
|---|---|---|---|
| listings | 100.0 | **77.0** | tests + route + latency, no seller output scored |
| socialpulse | 100.0 | **77.0** | same |
| design-studio | 95.0 | **75.2** | its 30 scored outputs average 16.7 |
| all others | ≤ 95 | ≤ 77 | no seller evidence at all |

**No service is at the bar now, and 77 is the ceiling reachable on artefacts alone.** That is
the honest status the mandate asks for: the code paths run, the outputs are not yet worth
selling, and the scorecard says so.

