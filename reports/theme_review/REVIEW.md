# Galactic theme — review set

**Date:** 2026-10-30 · **Branch:** `feature/chrome-connect-3.0`
**Source of truth:** `northstar-os-ui/src/shell/galacticShader.js` (one shader, one copy)

---

## What you are looking at

| File | What it shows |
|---|---|
| `reports/theme_review/00-current.png` | The theme as it shipped before this pass |
| `reports/theme_review/CONTACT_SHEET.png` | All 10 variants, full UI, with the chrome on top |
| `reports/theme_review/SCENE_SHEET.png` | All 10 scenes with **no UI** — the art alone |
| `reports/theme_review/01…11-*.png` | Individual full-resolution UI shots (1440×900) |
| `reports/theme_review/scenes/<id>.png` | Individual scene renders (800×450) |

Live switching, no rebuild:

```
http://127.0.0.1:8101/ui/?galactic=gargantua
http://127.0.0.1:8101/ui/?galactic=6          # or 1..10 by index
```

The choice is remembered in `localStorage` (`ns-galactic-variant`); `?galactic=`
always wins for that load.

---

## What actually differs between variants

Each variant sets three independent layers, which is why they are not recolours:

1. **Scene** — shader uniforms: disk temperature multiplier, exposure, camera
   inclination, camera distance (apparent size of the hole), galaxy brightness,
   colour grade. So the hole is a different size, angle and temperature.
2. **Surface** — panel alpha, blur radius, corner radius, border, accent, glow:
   obsidian glass vs smoked sheet vs matte vs ice.
3. **Layout** — header alignment, chip geometry (pill vs rect), rail width,
   density.

---

## The ten

| # | id | Intent |
|---|---|---|
| 1 | `event-horizon` | The Interstellar frame itself: gold disk, obsidian glass, quiet chrome |
| 2 | `gargantua` | Closer, larger, hotter. The hole dominates and the UI floats in its halo |
| 3 | `sagittarius` | Cooler, redder, dimmer — the real thing at 4 million suns, not a movie |
| 4 | `andromeda` | The galaxy is the hero; the hole is a distant companion. Wide, teal, airy |
| 5 | `photon-ring` | Almost nothing: black field, one bright ring, ice accents. Instrument, not poster |
| 6 | `nebula-bloom` | Luminous and soft: heavy nebula, magenta wash, deep glass, generous curves |
| 7 | `quasar` | Extreme Doppler asymmetry, blue-white disk, electric accent, compact density |
| 8 | `void-architecture` | No visible disk: shadow, starfield, hard architectural edges. Neutral |
| 9 | `solar-ash` | Ember light: high temperature, burnt-orange surfaces, small hole |
| 10 | `observatory` | Documentary register: muted, desaturated, thin rules. The UI steps back |

---

## Honest notes

* The shader integrates null geodesics (`d²u/dφ² + u = 1.5u²`, RK4). The shadow
  radius is the real critical impact parameter, 2.598 Rs; the disk's inner edge
  sits at the ISCO. It is a physical frame, not a painted one.
* There is a visible **fold line** where the near-side and far-side images of
  the disk meet. That is a real feature of a thin disk viewed near edge-on, but
  ours reads slightly harder than the film. It is present in every variant and
  is the one thing I would tune next if the winner depends on it.
* The plate is rendered **once** per size/theme change, then panned by CSS. A
  1600×900 frame measured 2.1 s headless; the GPU is idle while you read. This
  is deliberate — the box shares one GPU with ComfyUI and Ollama.
* Nothing here calls the network, touches Amazon, or spends money.
* `npm run build` — 0 errors.
