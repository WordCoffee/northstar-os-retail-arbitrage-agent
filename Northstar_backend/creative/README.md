# creative — Northstar image / text generation lane

Two lanes, one rule: **the AI makes the scene, the compositor makes the text.**

* `comfy_client.py` — local ComfyUI lane (Qwen-Image-2512 t2i, Qwen-Image-Edit-2511,
  FLUX fallback) + workflow builders + model resolution + `blank_panel` panel prep.
* `exact_text.py` — deterministic exact-text compositor (rectangle / quad /
  barrel curvature) with a brand-content guard and bundled brand fonts.
* `label_zone.py` — deterministic blank-label-zone detection for `align="auto"`.
* `presets.py` — reusable brand, container, product, surface-zone and style presets.
* `mogra_mockup.py` — one-call pipeline (`build_mockup`, `align`, `panel_prep`) + CLI.
* `routes.py` — `/api/creative/*` FastAPI routes + the `/mogra-mockup` UI page.
* `static/mockup.html` — beginner-friendly standalone UI.
* `assets/fonts/` — bundled brand fonts (Libre Baskerville + DM Sans, OFL 1.1).

React surface: **Creative Studio → Exact-Text Mockups** (`?view=mockups`),
component `northstar-os-ui/src/components/MockupStudio.jsx`.

Standard and run instructions: `docs/NORTHSTAR_IMAGE_TEXT_WORKFLOW.md`.

Tests: `Northstar_backend/test_creative_mockup.py`,
`Northstar_backend/test_creative_routes.py`.

CLI:

```powershell
python -m creative.mogra_mockup --list
python -m creative.mogra_mockup --product organic_turmeric_powder `
  --container mogra_5lb_clear_handled_pet_jar --generate --out out.png
```
