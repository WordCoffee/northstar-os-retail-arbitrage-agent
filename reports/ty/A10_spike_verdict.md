# A10 spike — verdict and what it changes (2026-11-06)

**Verdict: STOP. 0/5 solved, 0/15 candidates produced a patch.** Per the pre-registered matrix
(`M0.5_spike_plan.md`), that means: no local best-of-N, no hybrid build, no pretend evaluator.
Evidence: `reports/ty/spike_coding_lane.md`, `state/evidence/spike/` (206 files), commit `e805f0d1`.

| Case | Candidates | Patches produced | Solved |
|---|---|---|---|
| S1 cancel race | 3 | 0 (all three "passed" with 0-byte diffs) | 0/3 — **gate void** |
| S2 product_fidelity + product_box | 3 | 0 | 0/3 |
| S3 Documents AA contrast | 3 | 0 | 0/3 |
| S4 plate/copy guard | 3 | 0 (one timeout at 600 s) | 0/3 |
| S5 plate cleanliness | 3 | 0 | 0/3 |

## The three findings that matter more than the zero

1. **S1's gate is unusable as written.** The real bug reproduces at roughly 1 in 100 baseline runs,
   so a 20-run gate passes an unfixed tree. All three S1 "passes" had empty diffs — the check was
   measuring nothing. Any future case must prove it is red on the unfixed tree *first*.
2. **The zero is lane mechanics, not a reasoning ceiling.** A post-hoc arm using the loop's own
   `allowed_tools` knob (9 candidates, unscored) stopped the `list .` loop and produced the first
   patches. The remaining blocker is vocabulary: the AST tools cannot add a constant or a function,
   and the one patch it did produce gutted `score_case` and went red. That is a capability gap in the
   tool set, which is in-repo work — not a model limit.
3. **The lane ran CPU-only.** `size_vram: 0` on an idle RTX 5080, and `qwen2.5-coder:7b` cannot emit
   the agent's JSON protocol at all (so `qwen3:8b` was used). A CPU 8B asked to write patches is a
   measurement of the slowest possible configuration.

## What the programme does now

- The author lane is **not** built. `M1e` (ledger) and `M2-work-generator` still proceed: they are
  what turns a failure into a scoped, checkable contract — with the author left to a human or the
  DeepSeek lane, which is the honest reading of 0/5.
- Two retest units are queued before any author work is reconsidered: run the same probe with
  GPU inference, and widen the tool vocabulary to add a symbol. If both land and the score is still
  0/5, the answer is final and the loop stays detect-and-prepare.

## Retest preconditions (must all hold)

- inference on the GPU (`size_vram > 0` observed in `ollama ps`), model emitting the JSON protocol
- tool vocabulary able to add a function/constant and to run the target test
- every case proven **red on the unfixed tree** before it counts
- three candidates per case, each frozen and scored by the evaluator (A11/A12), not by the lane
