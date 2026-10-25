# Simple Mode requirements matrix — 2026-10-25

## State definitions
- **Code present:** source files exist
- **Wired:** connected to actual UI/runtime
- **Unit tested:** automated test passes
- **Browser-interaction verified:** verified via Chrome Connect
- **Visually reviewed:** human inspected the screenshot
- **Blocked/deferred:** cannot complete now

## Matrix

| # | Requirement | Code present | Wired | Unit tested | Browser verified | Visually reviewed | State |
|---|---|---|---|---|---|---|---|
| 1 | Display Scale (90/100/115/130) | Yes (TopNav.jsx, simple.css) | Yes (TopNav control + --ui-scale + zoom) | No | Yes (control visible in page text) | Blocked (agent can't view images) | Wired, not visually verified |
| 2 | Native browser zoom 100/125/150/200% | N/A (browser feature) | N/A | No | No | Blocked | Not tested |
| 3 | Daily Vista rendering | Yes (vistas.js, MasterBrainShell.jsx) | Yes (data-vista attr, annotation) | No | Yes (annotation visible: "Deep field · vista 7 of 7") | Blocked | Wired, not tested for stability |
| 4 | Vista same-day stability | Yes (deterministic hash) | Yes | No | No | No | Code-built, not tested |
| 5 | Vista date change (injected clock) | Yes (vistaForToday accepts `now` param) | Yes | No | No | No | Code-built, not tested |
| 6 | Streaming styling | Yes (CSS in simple.css) | No (classes exist, not applied during streaming) | No | No | No | Code present, not wired |
| 7 | Service docking | Yes (CSS .chat-dock) | No (not rendered in ChatSurface) | No | No | No | Code present, not wired |
| 8 | Success-only completion animation | Yes (CSS .chat-comet) | No (not triggered on success) | No | No | No | Code present, not wired |
| 9 | Reduced motion | Yes (CSS @media) | Yes (CosmicCanvas has prefers-reduced-motion) | No | No | No | Code present, not tested |
| 10 | Hidden-tab pause | Yes (CosmicCanvas visibilitychange) | Yes | No | No | No | Code present, not tested |
| 11 | AutothinK variant | Yes (redirect C2, React /autothink route) | Partial (redirect works, no dedicated theme) | No | Yes (route exists) | No | Partially wired |
| 12 | Missing-asset handling | Yes (onError placeholder in ChatSurface) | Yes (img onError → missing div) | No | No | No | Code-built, not browser-verified |
| 13 | BOJO-UTIL | Yes (utility_apps.py, build_utility tool) | Yes (tool persists asset) | Yes (12 tests) | Yes (page renders, shows "Tip calculator" with empty fields showing "—") | Blocked | Unit-tested + browser-read verified |
| 14 | Dictation/playback | Yes (chat_voice, mic button "Dictate") | Yes (push-to-talk wired) | Yes (13 tests) | Partial (button visible, no PTT turn run) | No | Unit-tested, PTT not exercised |
| 15 | Portrait render + apply_label | Yes (studio_generation, pouch_label) | Yes (tool available in chat) | Yes (19 tests) | No (needs ComfyUI) | No | Blocked on ComfyUI |
| 16 | Product imagery (branded mockup) | Yes (generate_image, apply_label) | Yes | Yes | No (needs ComfyUI) | No | Blocked on ComfyUI |
| 17 | A+ content | Yes (design-studio APlus.jsx) | Yes | Partial | No | No | Code present, not fully verified |
| 18 | Five-second ad | Yes (generate_video) | Yes | Partial | No (needs ComfyUI + video) | No | Blocked on ComfyUI |

## Reading width explanation
- **Prose measure:** `.chat-bubble` max-width 78ch (comfortable reading). Unchanged.
- **Workspace width:** `.chat-stream` max-width `clamp(760px, 78vw, 1360px)` (wider artifact workspace). Changed from 820px in interface_repair (2026-10-23) to use available space. The galactic harness was updated to accept the clamp range (760-1360) instead of exact 820.
- The 1186px measurement was not a defect — it's the intended responsive width at 1440px viewport. The old 820px assertion was outdated.

## Visual review status
VISUAL REVIEW BLOCKED — agent cannot view images. Screenshots preserved in reports/northstar_acceptance_20261025/screenshots/ for owner/vision-capable review. Desktop/mobile pair available.

## Generation-dependent tests (blocked)
- Portrait render + apply_label: needs ComfyUI running
- Product imagery: needs ComfyUI
- Five-second ad: needs ComfyUI + video lane
- A+ content: needs full module completion

## Commits (this session, on feature/v4.1-mesh)
- dafdb32d: fix missing Improvement import (blank screen root cause)
- 3e7a2d76: panel opacity 0.95, CosmicCanvas+CelestialBackdrop, harness column check
- 681c5317: screenshot probe PASS
- 8cac7a58: chromeconnect restart attempt
- 50eae812: single CosmicCanvas renderer, Vista wired via data-vista, DisplayScale restored, 18/0 galactic
- b5ed44bf: acceptance pass report
- bfa129b6: capture report
- 9cfa0243: remove duplicate DisplayScaleControl
- 2d86e51c: final acceptance report
- 3c314787: missing-asset placeholder + allow known stale asset 404
- f7a76868: final mission report

Nothing pushed. Repository: feature/v4.1-mesh.