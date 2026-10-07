# Creative productization — exact-text mockup lane

**Date:** 2026-10-06
**Worktree:** `C:\Users\T2Hol\Desktop\northstar-wt-mogra`
**Branch:** `feature/mogra-exact-text-mockup`
**Base commit:** `4eb86ee`
**Code commit:** `ca29440`
**Class:** continuous, autonomous-local (no owner gates hit)

---

## What this pass changed

Turned the working local Mogra image/text lane into a cleaner, reusable Northstar
creative capability **without changing the truth boundary** (AI makes the scene;
the deterministic compositor makes every glyph) and **without widening exposure**
(local-only, no public service, no cloud generation).

### 1. Brand fonts (bundled, license-clear)

* Bundled **Libre Baskerville** (serif/display) and **DM Sans** (sans/UI) as
  variable TTFs with their **SIL Open Font License 1.1** texts.
* Locations: `Northstar_backend/creative/assets/fonts/` (compositor) and
  `northstar-os-ui/public/fonts/` (web UI, served at `/ui/fonts/`).
* The compositor now loads them and applies the correct **variable-font weight**
  (`font_source() == "brand"`); OS fonts are fallback only and this is reported
  by `brand_fonts()`.
* In the web app the fonts are registered under **scoped** family names
  (`NSBrandSerif` / `NSBrandSans`) and used only inside the mockup lane, so no
  other room's typography changed.

Honest note: there is **no separate Mogra typeface spec** in the repo — the
Northstar design-system fonts were adopted as the Mogra display/UI fonts. If a
specific Mogra typeface exists, drop the TTFs into `assets/fonts/` and the
compositor picks them up.

### 2. Deterministic label-zone alignment (`align="auto"`)

* New `creative/label_zone.py`: finds the model's blank label panel by
  brightness/saturation, removes border-connected background, dilates to bridge
  thin seams, and tightens the box against the raw mask — pure image analysis,
  no model, no randomness.
* `build_mockup`/`/api/creative/compose`/`/api/creative/mockup` gained
  `align="preset" | "auto"`; a **confidence floor (0.25)** falls back to the
  preset quad rather than trusting a weak guess.
* Measured improvement (real scenes): the fixed jar preset was visibly off; the
  detector returned conf **0.834** (jar raw), **0.877** (jar after prep),
  **0.677** (pouch).

### 3. Optional Edit-2511 blank-panel prep (`panel_prep="edit_blank"`)

* `comfy_client.blank_panel()` runs Edit-2511 as a controlled prep stage before
  compositing. The first prompt **removed the label entirely** (over-edit); it
  was corrected to a **panel-preserving** prompt ("do not remove/move/resize the
  existing label panel; repaint only its inside as a blank surface").

### 4. React Creative Studio wiring (local, operator-driven)

* New tab **Exact-Text Mockups** in Creative Studio (`?view=mockups`), rendered
  by `northstar-os-ui/src/components/MockupStudio.jsx`, calling the real
  `/api/creative/*`: base upload / local scene generation, preset dropdowns,
  exact-text fields, align + panel-prep options, preview, one primary button.
* Honest framing: local-only badge, lane/model health pills, truth-boundary
  notice; no readiness inflation.

### 5. API + docs + tests

* `POST /api/creative/detect-zone` added; `/health` reports bundled fonts;
  compose/mockup accept `align` and `panel_prep`.
* `docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md` updated (fonts, alignment, prep,
  React surface, validation evidence, limitations).
* +20 offline tests → **58 passed**.

---

## Validation evidence (real runs)

| Check | Result |
|-------|--------|
| Offline tests | **58 passed** (mockup, routes, productization) |
| `verify-smoke.cjs` | **43 / 0** (was 42; +1 deep-link `?view=mockups`) |
| `verify-acceptance.cjs` | **33 / 0** (+1 mockups deep link) |
| `verify-guards.cjs` | **11 / 0** |
| `verify-invite-flow.cjs` | **11 / 0** |
| `verify-mockup-lane.cjs` (new) | **6 / 0** — standalone page + React lane against the real API |
| `npm run build` | **0 errors**, 91 modules |
| Pouch: generate + auto-align via API | HTTP 200, **133.3 s**, lane `qwen-image-2512`, align `detected` (0.677) |
| Jar: prep + auto-align + composite | lane `qwen-image-edit-2511+composited`, prep applied, align `detected` (0.877) |

Artifacts (git-ignored) under `generated_images/mogra_mockups/`:
`aligned_turmeric_jar.png`, `mogra_organic_white_onion_powder_*.png` (auto-aligned
pouch), `prep/blank_organic_turmeric_powder_*.png` + `prep_aligned_turmeric_jar.png`
(prep chain).

---

## Bug found and fixed this pass

* **Edit-2511 panel prep over-edited** — the first prompt deleted the label panel;
  corrected to a panel-preserving prompt (verified: align confidence rose from
  **0.051 → 0.877** on the same scene).

---

## Guardrails / truth rules honored

* No public exposure beyond localhost; no cloud provider generation added; no
  video; exact-text stays deterministic and authoritative.
* Foundation router untouched; unrelated rooms not restyled (scoped fonts only).
* No credentials read/printed; no paid calls.
* No reset/restore/stash/rebase/merge/push. Generated outputs and screenshots not
  staged (three `northstar-os-ui/screenshots/59-*.png` were rewritten by the
  invite-flow harness and left unstaged, per commit rules).

---

## Remaining local-lane limits

* Label-zone detection is a deterministic heuristic; it can under-cover a panel
  with a strong shading gradient (the shaded right edge is excluded) and falls
  back to the preset when weak. The `edit_blank` prep mitigates this.
* Curvature remains a single-parameter cylindrical approximation (no vertical bow).
* The React lane is local-only and requires the backend (and ComfyUI for
  generation); it is not a public production service.
* Global UI typography still uses system fallbacks; switching the app-wide
  `--font-serif`/`--font-ui` to the bundled fonts is a deliberate, separate change.

## Blocked items

* None. (Three screenshot files under `northstar-os-ui/screenshots/` were
  rewritten by the invite-flow harness and intentionally left unstaged.)

## Recommended next action

* Adopt the lane for the next real Mogra asset set; if a specific Mogra typeface
  exists, drop the TTFs into `assets/fonts/`; optionally decide on the global
  font switch and on non-axis-aligned quad fitting for curved panels.
