# Mogra Panel-Polish rerun — final (Edit-2511 prep gated; deterministic pristine panels)

**Date:** 2026-10-07
**Worktree:** `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
**Branch:** `feature/mogra-exact-text-mockup`
**Base commit:** `0ee7385`
**Class:** controlled local batch (image only, one job at a time, no public exposure). Model: GLM-5.3-Flash (approved switch for rendered-image quality judgment).

---

## Outcome in one line

Running the Edit-2511 blank-panel prep **with the quality gates exposed the real
defect**: panel **detection** was wrong (it fused the label with the bright product
window and stopped short of the shaded panel edge). Fixing detection — plus a
vertical text auto-fit — made all three assets genuinely pristine **deterministically**,
and the AI prep was correctly rejected on every asset by the gates.

## Assets (final set)

`generated_images/mogra_mockups/mogra_batch_20261006/rerun_panel_polish/` (base-batch
finals were refreshed identically in the parent folder):

| # | File | Container | Net weight |
|---|------|-----------|------------|
| 1 | `a1_turmeric_powder_5lb_jar.png` | 5 lb clear handled PET jar | `NET WT. 5 LB (2.27 kg)` |
| 2 | `a2_white_onion_powder_32oz_pouch.png` | 32 oz stand-up pouch | `NET WT. 32 OZ (2 LB)` |
| 3 | `a3_black_peppercorns_4oz_window_pouch.png` | 4 oz window pouch | `NET WT. 4 OZ (113 g)` |

Locked content preserved (brand, tagline, no sun mark, containers, product names,
container-correct weights, deterministic text only). No health/certification/
regulatory/lot/UPC/sourcing content.

## Panel-prep outcomes (gated)

Edit-2511 prep was attempted (max 3 attempts per asset) with a panel-preserving
prompt and these deterministic gates: post-prep detection ≥ 0.25; panel bbox IoU vs
the pre-prep panel ≥ 0.45; **change outside the union of panel boxes ≤ 0.05**;
total changed fraction ≤ 0.45.

| Asset | attempts | result | dominant reason |
|-------|---------|--------|-----------------|
| a1 | 3 | rejected | outside-panel change 0.058 + panel lost (attempts 2–3) |
| a2 | 3 | rejected | outside-panel change 0.058–0.084 **and** panel shift IoU 0.015–0.031 |
| a3 | 3 | rejected | panel lost after prep (preset_fallback) + outside-panel change 0.055–0.057 |

The `outside_panel_change` gate is the one that catches what a global pixel diff
missed: an earlier version **removed the product window** on a2 while passing the
0.45 total-change check. Edit-2511 re-renders the whole frame, so a legitimate prep
still perturbs ~5–6% of pixels outside the panel; because that is already at the
gate limit, no prep attempt survived. **Per the quality gate the finals use the
UNPREPARED scene with deterministic compositing.**

## Root-cause fix: label-zone detection

The real reason panels looked "not perfect" was detection, not the compositor:

1. **Merged-region splitting** — dilation used to *find* the candidate is now undone
   on the raw mask, splitting on full-width gaps **and on the strongest internal
   horizontal edge** (labels are bounded by crisp edges; product fill is not).
2. **Nearest-edge snapping** — after scoring, the box extends outward to the nearest
   strong straight edge (bounded margin), recovering panel area that shading pushed
   below the brightness threshold.
3. **Smoothness scoring** — among plausible sub-regions the flattest wins, so a
   grainy window never beats a blank panel.

Measured effect (raw scenes):

| Asset | before | after | conf |
|-------|--------|-------|------|
| a1 jar | x 0.266–0.526 | x **0.258–0.614** | 0.63 |
| a2 pouch | y 0.276–**0.776** (bled into window) | y **0.236–0.597** | **0.979** |
| a3 window pouch | y 0.273–0.776 | y **0.263–0.571** | 0.821 |

## Exact-text compositing (final)

Deterministic compositor (`mogra_label_panel`, bundled fonts), auto-align on the
repaired detection, plus a new **analytic vertical auto-fit** so type and gaps shrink
until the whole block fits the panel. This fixed a2, whose shorter (correct) panel
had clipped the descriptor. Text is exact; no AI-rendered text.

## Outputs and sidecars

* Finals `a1/a2/a3_*.png` + editable JSON sidecars in `rerun_panel_polish/`
* `rerun_manifest.json` — the gated prep attempts (pre/post confidence, changed
  fraction, **outside-panel change**, IoU, rejection reasons)
* `final_manifest.json` — final lane/align/quad per asset + prep evidence carried forward
* `detect_overlays/detect_a{1,2,3}.png` — the detected quad drawn on each scene (QA evidence)

## Tests / builds run

| Check | Result |
|-------|--------|
| pytest (mockup + routes + productization) | **60 passed** (+2 regression tests for merge-split and edge-snap) |
| `npm run build` | 0 errors |
| `git diff --check` | clean |
| `verify-smoke` / `verify-acceptance` / `verify-guards` / `verify-invite-flow` / `verify-mockup-lane` | 51/0 · 36/0 · 11/0 · 11/0 · 6/0 |
| Compliance-copy guard on all 3 sidecars | CLEAN |

## Known visual limitations

* Detection still needs *some* edge or gap; a panel with no crisp boundary would
  fall back to the preset.
* Edit-2511 is not usable as a "blank panel" tool on these scenes — it re-renders
  the pack; the gates reject it, which is the intended safe behaviour.
* Mockups only — not print-ready; no dielines, no regulatory review.

## Blocked items

* None. Generated outputs and screenshots remain unstaged.

## Recommended next action

* Approve the three finals for use; if a print path is wanted later, replace the AI
  scene with a real photograph and reuse the same detected-zone + compositor pipeline.
