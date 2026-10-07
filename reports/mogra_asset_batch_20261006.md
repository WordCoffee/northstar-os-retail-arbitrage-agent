# Mogra Organics — real asset batch (local exact-text lane)

**Date:** 2026-10-06
**Worktree:** `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
**Branch:** `feature/mogra-exact-text-mockup`
**Base commit:** `5292f75`
**Class:** controlled local batch (image only, one job at a time, no public exposure)

---

## Assets generated (3)

| # | File | Product | Container preset | Net weight on pack |
|---|------|---------|------------------|--------------------|
| 1 | `a1_turmeric_powder_5lb_jar.png` | Organic Turmeric Powder | `mogra_5lb_clear_handled_pet_jar` (5 lb clear handled PET jar) | `NET WT. 5 LB (2.27 kg)` |
| 2 | `a2_white_onion_powder_32oz_pouch.png` | Organic White Onion Powder | `mogra_32oz_standup_pouch` (32 oz stand-up pouch) | `NET WT. 32 OZ (2 LB)` |
| 3 | `a3_black_peppercorns_4oz_window_pouch.png` | Organic Black Peppercorns | `mogra_4oz_window_pouch` (4 oz window pouch) | `NET WT. 4 OZ (113 g)` |

**Copy note (decision disclosed).** The only net weight in the product presets is
`NET WT. 5 LB (2.27 kg)` (all three products carry it). Printing 5 LB on a 32 oz
or 4 oz container would be a false statement on the pack, so the weight was matched
to the **container** instead (5 lb jar → 5 LB; 32 oz pouch → 32 OZ (2 LB); 4 oz
window pouch → 4 OZ (113 g)). All three strings are container-derived, none are
health/certification/regulatory claims, and all pass the deterministic brand
guard. Asset 3 uses the 4 oz window pouch because whole peppercorns are best shown
through a window and it completes the three key formats; every pack's stated
weight matches its container.

Text used (all preset-safe): brand `Mogra Organics`, tagline `Fuel Your Focus.`,
product name + preset descriptor (`Earthy • Golden • Vibrant`,
`Smooth • Savory • Versatile`, `Whole • Aromatic • Bold`), and the net weight above.
No health claims, certifications, nutrition facts, regulatory copy, lot codes,
UPCs, marks, or sourcing/quality claims were added.

## Container / preset used

Container presets: 5 lb clear handled PET jar, 32 oz stand-up pouch, 4 oz window
pouch. Style preset `mogra_label_panel` (bone panel / pine ink). Label panel
supplied by the deterministic compositor; the scene model was prompted for a clean
blank label zone and no text.

## Model lane used

* Scene: **qwen-image-2512** (Qwen-Image-2512 Q4_K_M GGUF, local ComfyUI), 896×1152,
  20 steps. No cloud provider, no editing model needed for this batch.
* Text: deterministic compositor (`creative.exact_text`), bundled brand fonts
  (Libre Baskerville + DM Sans). No AI-rendered text is used as final copy.

## Auto-alignment results

`align="auto"` throughout. Detection ran on each raw scene; a metric-driven rule
re-rolls the scene (new seed, max 3 attempts) only while detection *falls back*.

| Asset | align source | confidence | detected quad (norm) |
|-------|--------------|-----------|----------------------|
| a1 turmeric jar | detected | **0.512** | 0.232–0.526 x, 0.424–0.769 y |
| a2 onion pouch | detected | **0.829** | 0.231–0.648 x, 0.276–0.776 y |
| a3 peppercorns window pouch | detected | **0.725** | 0.264–0.723 x, 0.273–0.607 y |

All three detected on **attempt 1** (no fallback taken). For reference, an earlier
run of the jar asset fell back to the preset quad and the panel sat visibly high —
that is exactly the weak-detection case the preset fallback exists for, and the
re-roll rule reproduced a detectable scene on the next batch.

## Exact-text compositing results

All three used the deterministic compositor (rectangle/quad warp, `mogra_label_panel`
style, 2× supersample). Composite step ≈ 4 s each; text is exact, crisp, and
brand-typed. Timings (scene generation): a1 131.1 s, a2 119.6 s, a3 133.4 s.

## Outputs and sidecars

Under `generated_images/mogra_mockups/mogra_batch_20261006/` (git-ignored):

* Finals: `a1_*.png`, `a2_*.png`, `a3_*.png`
* Sidecars (editable params + spec + align record): `a1_*.json`, `a2_*.json`, `a3_*.json`
* Source scenes: `scenes/scene_organic_*.png` (one per asset)
* Batch manifest: `batch_manifest.json` (lane, timing, resolution, preset,
  detection/fallback, quads, attempts)

## Tests / builds run

| Check | Result |
|-------|--------|
| pytest (mockup + routes + productization) | **58 passed** |
| `npm run build` | **0 errors**, 91 modules |
| `git diff --check` | **clean** (exit 0) |
| Compliance-copy guard on all 3 sidecars | **CLEAN** (no forbidden tokens) |
| `verify-smoke.cjs` | 43 / 0 |
| `verify-acceptance.cjs` | 33 / 0 |
| `verify-guards.cjs` | 11 / 0 |
| `verify-invite-flow.cjs` | 11 / 0 |
| `verify-mockup-lane.cjs` | 6 / 0 |

## Known visual limitations

* Alignment is a deterministic brightness/saturation heuristic; confidence 0.512
  on the jar is the weakest of the three (fine here, but shaded/shiny panels can
  fall back to the preset).
* The generated scenes show the model's own faint blank-panel outline behind the
  composited panel in places (cosmetic; `panel_prep="edit_blank"` can remove it).
* Container geometry is model-generated, not a fixed 3D template, so it varies
  scene to scene.
* Packaging is a visual mockup only — not print-ready, no dielines, no regulatory
  review; no certification/nutrition/UPC content by design.

## Blocked items

* None. Generated outputs and screenshots were left unstaged on purpose.

## Recommended next action

* Human visual review of the three finals; if approved, consider `panel_prep="edit_blank"`
  for a pristine panel, and generate the remaining products/formats. If a specific
  Mogra typeface exists, drop it into `creative/assets/fonts/`.
