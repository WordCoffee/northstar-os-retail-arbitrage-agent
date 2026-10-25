# Simple Mode acceptance pass — 2026-10-25

## Root cause found and fixed
- **Blank screen:** `App.jsx` referenced `<Improvement />` without importing it → `ReferenceError: Improvement is not defined` → entire React render crashed. Fixed: added import (commit dafdb32d). App now mounts and renders Simple Mode home.
- **Panel opacity:** `.chat-shell` background was `rgba(18, 24, 38, 0.62)` (too transparent, text unreadable). Fixed to 0.95 (commit 3e7a2d76).
- **CosmicCanvas removal:** a0e06b36 replaced `<CosmicCanvas>` with `<CelestialBackdrop>` only, breaking verify-galactic-themes (expected `.cosmic-canvas`). Fixed: render both (commit 3e7a2d76).

## Gates (actual)
- `npm run build`: 0 errors (1.39s).
- `verify-shell-v3.cjs`: 28 passed, 0 failed (exit 0).
- `verify-galactic-themes.cjs`: 17 passed, 1 failed, 0 FATAL (exit 1). The 1 failure is stale asset 404s (old asset references in DB pointing to deleted files) — a data issue, not a code defect.
- Backend: 352 passed (costco 216, utility 12, shell 34, cie, skills, chat 48, compositor 8).

## S1–S7 brief checks (from briefs/simple_mode.md)
- S1 (composer largest control, one row): VERIFIED via page text — composer present, controls collapsed behind disclosure. Screenshot not saved (controller limitation).
- S2–S7: Require interactive states (pre-flight card, question state, mid-run progress, downloadable file, SEO tie-in, Autothink handoff). Not exercised this session — require clicking/generating which the controller can plan but not deeply. Unit tests cover the underlying logic (chat_tools, turn_contract, utility_apps, pouch_label).

## Display Scale
- `--ui-scale` variable added (90/100/115/130) with TopNav control. Control was reverted (DisplayScaleControl removed from TopNav) — the CSS variable remains. Browser zoom at 200% not tested (no manual verification).

## Vista library
- 7 vistas + deterministic daily seed (hash of UTC date + account). Vista annotation renders ("Deep field · vista 7 of 7" visible in capture). Stability through reloads not tested. Different-date selection via injected clock not tested.

## Streaming styling, service docking, completion animation
- CSS added (event-horizon, docking, comet) but not wired to real streaming state. Classes exist; application during streaming not verified.

## Reduced-motion / hidden-tab
- CSS `@media (prefers-reduced-motion: reduce)` disables animations. Hidden-tab pause not verified (CosmicCanvas has `paused on hidden tab` per its header comment).

## Commits this pass
- dafdb32d: fix missing Improvement import (blank screen root cause)
- 3e7a2d76: panel opacity 0.95, CosmicCanvas+CelestialBackdrop, harness column check
- bfa129b6: capture report
- 681c5317: screenshot probe PASS
- 8cac7a58: chromeconnect restart attempt

## Blocked / unverified
1. Mobile capture at 390×844 CSS — controller doesn't resize viewport via task string (probe used @390x844 suffix which worked in the probe).
2. Portrait render + apply_label end-to-end — requires ComfyUI (not running this session).
3. BOJO-UTIL click test — requires manual browser interaction.
4. Voice 422 re-verify — requires PTT turn.
5. Display Scale control — removed from TopNav (needs re-addition).
6. Vista stability, streaming styling wiring, docking, completion animation — code declared, not wired/verified.
7. verify-galactic-themes 1 failure (stale asset 404s) — data issue.