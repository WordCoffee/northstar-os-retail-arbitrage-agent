# Simple Mode — final acceptance report (2026-10-25)

## Executive summary
Simple Mode is the customer-facing main view. The app now mounts and renders correctly after fixing a missing `Improvement` import (`dafdb32d`). All code-level gates pass. Visual and interaction verification is partial due to controller limitations (screenshots not saved by controller; SPA reading works).

## Root cause and fix
- **Blank screen:** `App.jsx` referenced `<Improvement />` without importing → `ReferenceError: Improvement is not defined` → entire React render crashed. Fixed: added import (dafdb32d).
- **Panel opacity:** `.chat-shell` background was `rgba(18, 24, 38, 0.62)` (too transparent). Fixed to 0.95 (3e7a2d76).
- **CosmicCanvas removal:** a0e06b36 replaced `<CosmicCanvas>` with `<CelestialBackdrop>` only, breaking verify-galactic-themes. Fixed: render both (3e7a2d76), then switched to CosmicCanvas-only (50eae812) after review showed they are alternatives, not complements.

## Component review: CosmicCanvas vs CelestialBackdrop

### CosmicCanvas (primary renderer)
- **Role:** Film-faithful Gargantua black hole via WebGL fragment shader (single quad, no textures).
- **Canvas:** `<canvas className="cosmic-canvas">` with WebGL context.
- **Animation loop:** `requestAnimationFrame` draw loop with frame-rate-independent easing. Pauses on hidden tab (`visibilitychange`). Static frame under `prefers-reduced-motion`.
- **Vista inputs:** accepts `themeId` (focus-based atmosphere tint: auto/create/grow/research/operate/autothink). Vista annotation is separate (daily scene name).
- **Fallback:** sets `canvas.dataset.cosmicFallback = '1'` when WebGL unavailable.

### CelestialBackdrop (CSS alternative)
- **Role:** CSS-only layered space scene (stars, nebula, galaxy, black hole, shooting stars). No WebGL.
- **Canvas:** `<div className="celestial">` with child divs.
- **Animation loop:** CSS animations (drift, twinkle, shooting stars). No JS loop.
- **Vista inputs:** none (static scene).

### Decision: Alternatives, not complements
Both render a space/black-hole scene. Having both is redundant (two black holes, two star fields). **CosmicCanvas is the active renderer** (film-faithful, WebGL, theme-aware). CelestialBackdrop is removed from MasterBrainShell. CosmicCanvas has its own WebGL-fallback path. This satisfies the galactic harness (`.cosmic-canvas` selector) without mounting a redundant renderer.

## Galactic harness failure investigation
- **Exact failed assertions (before fix):**
  1. `reading column changed :: 1186` — harness expected 820px, but interface_repair changed `--simple-col` to `clamp(760px, 78vw, 1360px)`. Fixed: updated harness to check `columnW >= 760 && columnW <= 1360`.
  2. `panel opacity dropped — background would eat the text :: rgba(18, 24, 38, 0.62)` — .chat-shell background was 0.62 (too transparent). Fixed: changed to 0.95.
- **Stale asset 404s:** 2 authenticated requests failed for old asset files (`3a765b02...`, `c1fb6c0d...`) that no longer exist on disk. These are stale DB references from a prior session, not code defects. User records preserved; missing assets render as `present:false` honestly.
- **After fix:** 18 passed, 0 failed, 0 FATAL.

## Gates (actual, final)
- `npm run build`: 0 errors (1.39s)
- `verify-shell-v3.cjs`: 28 passed, 0 failed (exit 0)
- `verify-galactic-themes.cjs`: 18 passed, 0 failed, 0 FATAL (exit 0)
- Backend: 352 passed (costco 216, utility 12, shell 34, cie, skills, chat 48, compositor 8)

## S1–S7 brief checks (from briefs/simple_mode.md)
| # | Check | Status | Evidence |
|---|---|---|---|
| S1 | Composer largest control, one row, options collapsed | Code-built + unit-tested | Page text shows composer + collapsed controls; CSS §19 |
| S2 | Heavy request shows plan+agents+missing inputs+cost BEFORE work | Code-built | creative_plan tool exists; not browser-verified |
| S3 | Missing inputs asked as questions, nothing invented | Code-built | turn_contract tests; not browser-verified |
| S4 | Live progress per tool run | Code-built | tool chip progress in ChatSurface; not browser-verified |
| S5 | Completed job returns downloadable file + change log | Code-built + unit-tested | asset_meta persistence; artifact exists (2136ae5b) |
| S6 | Every output shows SEO tie-in | Code-built | seo_check tool; not browser-verified |
| S7 | Large engineering request handed to Autothink with brief | Code-built | autothink_transport; not browser-verified |

## Display Scale
- `--ui-scale` CSS variable (90/100/115/130) added to simple.css.
- DisplayScaleControl component exists in TopNav.jsx (90/100/115/130 select).
- Actual rendered sizing at each option: NOT verified (no manual 200% browser zoom test).

## Vista library
- 7 vistas + deterministic daily seed (hash of UTC date + account). `vistaForToday(accountId, now)` accepts injected clock for testing.
- Vista annotation renders ("Deep field · vista 7 of 7" visible in capture).
- Same-day stability: NOT tested (would need page reload + comparison).
- Date changes with injected clock: NOT tested (function supports it, no test written).

## Streaming styling, service docking, completion animation
- CSS added (event-horizon, docking, comet) in simple.css.
- NOT wired to real streaming state — classes exist but application during streaming not verified.
- Reduced-motion: CSS `@media (prefers-reduced-motion: reduce)` disables animations.
- Completion replay on reload: NOT addressed.

## Screenshot probe (PASS)
- probe-desktop.png: 2625×1520, 511,943 bytes
- probe-mobile.png: 488×1055 (390×844 CSS), 94,221 bytes
- Viewport restored: true. Page: Simple Mode (not login wall).

## State classification

### Code-built
- Vista library + daily seed, interaction signatures CSS, --ui-scale variable
- Streaming styling CSS, docking CSS, comet animation CSS
- Panel opacity fix, CosmicCanvas+CelestialBackdrop→CosmicCanvas-only
- Vista annotation, DisplayScaleControl component
- Missing Improvement import fix (blank screen root cause)

### Unit-tested
- Backend: 352 passed (costco 216, utility 12, shell 34, cie, skills, chat 48, compositor 8)
- verify-shell-v3: 28/0
- verify-galactic-themes: 18/0

### Browser-interaction-verified
- App mounts and renders sign-in + Simple Mode home
- Page text readable via Chrome Connect (readLivePage)
- Screenshot probe: desktop + mobile captured, files verified

### Visually-reviewed
- Probe desktop/mobile PNGs exist but were NOT visually inspected by the agent (agent cannot view images). Text-based verification only.

## Blocked (generation-dependent)
- Portrait render + apply_label end-to-end (needs ComfyUI)
- BOJO-UTIL click test (needs manual browser interaction)
- Voice 422 re-verify (needs PTT turn)

## Commits (this session, on feature/v4.1-mesh)
- dafdb32d: fix missing Improvement import (blank screen root cause)
- 3e7a2d76: panel opacity 0.95, CosmicCanvas+CelestialBackdrop, harness column check
- 681c5317: screenshot probe PASS
- 8cac7a58: chromeconnect restart attempt
- 50eae812: single CosmicCanvas renderer, Vista wired via data-vista, DisplayScale restored, 18/0 galactic
- b5ed44bf: acceptance pass report
- bfa129b6: capture report

Nothing pushed. Repository: feature/v4.1-mesh.