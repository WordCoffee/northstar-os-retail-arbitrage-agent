# MOGRA "Forest Dusk" mockup — text-safe render (2026-10-16)

## Deliverable

- **PNG:** `renders/mogra-forest-dusk-mockup.png` — 1216×832 RGB, 1.49 MB
- **Sidecar:** `renders/mogra-forest-dusk-mockup.json` — machine record of the run

## What it shows (verified visually + by OCR)

Two cosmetic-grade matte stand-up doypacks side by side on a warm oak surface
against a softly blurred botanical-greenhouse backdrop, late-afternoon light:
left pouch deep forest green, right pouch warm charcoal; gold engraved-style
line art (lion's mane form left, mushroom cluster right); cream circular badge
emblems with mortar-and-pestle icon; rows of four tiny cream dots low on each
face. Matte finish, soft edge specular, no hands/people/loose powder, both
pouches fully in frame.

**Zero lettering** — OCR verdict `text_free`, 0 text boxes (rapidocr, CPU,
offline). No retry was needed; the pre-render guard suppressed the brief's
typographic demands and appended the blank-surface suppression phrase.

## How — the studio's own lane (same code path as `POST /api/design-studio/generate`)

- Script: `scripts/render_mogra_forest_dusk.py`
- `text_fidelity.render_with_text_guard(render_fn=studio_generation.generate_image, brief, text_safe=True)`
- Engine: FLUX.2 klein 4B Q8 via the operator's local ComfyUI on `:8199`
  (`MEDIA_GEN_LIVE=1` mirrors the launcher's armed state), tier `final`,
  fixed seed `20261016`; 20.2 s warm render, 1 attempt.

## Pipeline bug found + fixed (blocking)

The first run crashed **after burning a real render**:
`UnboundLocalError: used_brief` in `render_with_text_guard` — `used` was only
bound on the retry branch, so every clean first render crashed at the return.
Fixed (bind before the non-retry return) + added the missing regression test
for the no-retry `text_safe` path. Commit `f16e2b0`;
`test_text_fidelity.py` 12/12 passed.

## Commits

| Commit | What |
|---|---|
| `cf80b36` | Production-tooling research scan + this render script |
| `f16e2b0` | text-fidelity guard fix + regression test |
| this commit | render artifacts + this report + state entry |

## Honest scope (the operator's own frame)

The text-safe lane delivers clean, unlettered base art — OCR-enforced. Full
print fidelity (wordmark, exact weights, icon glyphs, Supplement Facts) lands
via the vector text layer / deterministic compositor, the studio's next build
step for this layout.

## Reproduce

```
python scripts/render_mogra_forest_dusk.py
```

Different seed / more variants: edit `_render()` in the script (width, height,
`tier="final"`, `seed`).
