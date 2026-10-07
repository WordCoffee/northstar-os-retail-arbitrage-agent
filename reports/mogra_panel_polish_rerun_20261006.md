# Mogra Panel-Polish rerun (Edit-2511 prep + deterministic text)

**Date:** 2026-10-06
**Worktree:** `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
**Branch:** `feature/mogra-exact-text-mockup`
**Base commit:** `b041a64`
**Class:** controlled local batch (image only, one job at a time, no public exposure). Model: GLM-5.3-Flash (approved switch for rendered-image quality judgment).

---

## Assets rerun (3)

Same three finals, same containers and copy, all under
`generated_images/mogra_mockups/mogra_batch_20261006/rerun_panel_polish/`:

| # | File | Container | Net weight on pack |
|---|------|-----------|--------------------|
| 1 | `a1_turmeric_powder_5lb_jar.png` | 5 lb clear handled PET jar | `NET WT. 5 LB (2.27 kg)` |
| 2 | `a2_white_onion_powder_32oz_pouch.png` | 32 oz stand-up pouch | `NET WT. 32 OZ (2 LB)` |
| 3 | `a3_black_peppercorns_4oz_window_pouch.png` | 4 oz window pouch | `NET WT. 4 OZ (113 g)` |

Locked content preserved: `Mogra Organics` + `Fuel Your Focus.`, restrained design,
no sun mark, same containers, same product names, container-correct weights,
deterministic text-only final copy. No health/certification/regulatory/lot/UPC/sourcing
content added.

## Panel-prep outcomes

Quality gates were **deterministic image metrics**, applied per attempt (max 3):
post-prep auto-align must detect (conf ≥ 0.25), pixel-change fraction between the
original scene and the prepped scene ≤ 0.45, and detected-panel bbox IoU vs the
pre-prep panel ≥ 0.45.

* **a1 turmeric jar — prep ACCEPTED (attempt 1).**
  Pre conf **0.512** → post **0.584**; changed-frac **0.056**; panel IoU **0.931**.
  Composite then ran on the repaired panel.
* **a2 onion pouch — prep REJECTED ×3 → unprepared composite (fallback).**
  Each attempt Edit-2511 re-rendered the pouch with the panel in a different
  place (IoU ≈ 0.256 vs the original panel, changed-frac 0.18–0.21 — the panel was
  legitimate, tied to a re-generated pouch). Per the gate, all three attempts were
  rejected and the final used the existing unprepared scene.
* **a3 peppercorns window pouch — prep REJECTED ×3 → unprepared composite.**
  After prep the detector lost the panel entirely (preset_fallback, conf None)
  on all three attempts, i.e. repair without a trustworthy panel reference —
  rejected per gate; final used the unprepared scene, auto-align detected conf
  **0.725** as in the base batch.

Scene reuse: all three reused the existing batch scenes (no scene regeneration was
necessary; centre-frame scenes with clean panels).

## Pre / post alignment confidence

| Asset | pre-prep conf | post-prep conf | accepted |
|-------|--------------|----------------|----------|
| a1 | 0.512 | 0.584 | yes (attempt 1) |
| a2 | 0.829 | 0.339 / 0.394 / 0.365 | no — panel shift |
| a3 | 0.725 | n/a (detection lost) | no |

## Attempts and rejected outputs

* a1: 1 attempt, none rejected.
* a2: 3 attempts, all rejected by `panel_shift` (IoU 0.256/0.263/0.256 < 0.45).
* a3: 3 attempts, all rejected by `post_prep_align_fell_back`.
* Every attempt record (edit output, elapsed, conf, changed-frac, IoU, rejection
  reasons) is preserved in `rerun_manifest.json`; no rejected attempt is used as
  a final.

## Exact-text compositing results

All three finals are deterministic-compositor text (mogra_label_panel style, 2×
supersample) using auto-align on the accepted/fallback scene with the bundled
brand fonts. a1 via `qwen-image-edit-2511+composited`; a2/a3 via
`composited_only`.

## Outputs and sidecars

Under `rerun_panel_polish/` (git-ignored):

* Finals `a1/a2/a3_*.png` + editable JSON sidecars `a1/a2/a3_*.json`
* Prep intermediates for kept attempts (a1 `blank_*.png`)
* `rerun_manifest.json` — locked-content block, gate definitions, per-asset
  attempts with pre- and post-prep confidences, changed-fractions, IoUs, and
  outcomes (`prep_attempt_1_accepted` / `fallback_unprepared_composite`)

## Tests / builds run

| Check | Result |
|-------|--------|
| pytest (mockup + routes + productization) | **58 passed** |
| `git diff --check` | clean (exit 0) |
| `npm run build` | **0 errors** (91 modules) |
| `verify-smoke.cjs` | 46 / 0 |
| `verify-acceptance.cjs` | 36 / 0 |
| `verify-guards.cjs` | 11 / 0 |
| `verify-invite-flow.cjs` | 11 / 0 |
| `verify-mockup-lane.cjs` | 6 / 0 |
| Compliance-copy guard on all 3 sidecar specs | CLEAN (no forbidden tokens) |

## Known visual limitations

* a1's panel is clean and well-seated; a2/a3 keep the faint AI-drawn panel
  outline behind the composited panel (the original tradeoff — prep was rejected
  there by the gates, working as designed).
* Alignment/attempts are measured, but "does the prep look right" ultimately
  benefits from human review; the gates only prove no material pixel change and
  no panel shift.
* Edit-2511 panel prep is prompt-guided and can relocate panels on pouches;
  per-attempt seeds / multi-scene prep could improve throughput.

## Blocked items

* None. Generated outputs and screenshots remain unstaged.

## Recommended next action

* Owner review of the three rerun finals; the a2/a3 findings suggest tuning the
  Edit-2511 prep seed/prompt per container before the next mass batch.
