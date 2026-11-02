# UX rebuild — handoff

**State:** U0–U6 done and verified on both targets. **U7 (Design Studio workspace) is next and not
started.** Last tag `ns-ux-U6`. Dev servers were started through `scripts/dev-start.ps1` after
`tailscale serve status` returned **No serve config**.

## Done

- **U0** — `ns-ux-baseline` at `a2d12f5e`; baselines in `ux_queue.json`.
- **U1** — `src/lib/shellMode.js`: ids stay `simple`/`advanced`, display names **Northstar** /
  **Advanced view**, legacy values migrate. `AGENTS.md` appended (647 chars).
- **U2** — `src/data/serviceRegistry.js` (29 services) + `src/lib/serviceGate.js`.
- **U3** — workbench shell: Bojo dock, service tabs, outlet, `/workbench`, top-nav entry.
- **U4** — `src/lib/serviceThemes.js` (per-service tokens + WCAG maths), `src/kit/Glass.jsx`,
  `src/kit/useThemeShift.js`, `src/styles/kit.css`; shell sets `data-wb-theme` + `--wb-*`.
- **U5** — `src/scene/SceneHost.jsx`, `sceneController.js`, `starfield.js`; `src/lib/sceneTiers.js`,
  `sceneBus.js`. One canvas, tiers, fps cap, visibility pause, event bus.
- **U6** — `src/scene/gasGiant.js` + `scenes.js` factory; studio scene wired to `design-studio`.

## Evidence at this handoff

| Check | Result |
|---|---|
| `npm run test:ui` | **140 passed, 0 failed** |
| `npm run build` | **✓ built in 1.34s** |
| workbench trio, desktop | **11 passed (10.7s)** |
| workbench trio, mobile | **11 passed (33.7s)** |
| frame cost (Chromium 1280×720, cinematic) | **121 frames / 2008 ms = 60.3 fps** |
| frame cost (Chromium 390×844, reduced) | **60 frames / 2015 ms = 29.8 fps** |
| screenshots | `reports/ty/shots/u6-studio-chromium-{desktop,mobile}.png` |

Headless WebKit reports ~3.9 fps — that is a headless rAF throttle, **not** a device measurement.
Do not quote it as performance.

## Next: U7 (Design Studio workspace) [MAX-GRADE]

The repo already ships the engine — do not rebuild it:

- `src/studio/engine/doc.js` (document model, undo/layers), `compose.js`, `presets.js`, `assets.js`
- `src/studio/components/{StudioShell,Stage,Chrome,Fields}.jsx`
- `src/pages/internal/DesignStudio.jsx` already has an **embedded mode** (section lives in component
  state when mounted outside `/design-studio`) — keep that.
- Existing asset dashboard (`Deliverables.jsx`) and dielines: wire, don't duplicate.

Plan that fits the order:

1. Extend the embedded studio with a glass tool rail (`ToolRail` from `src/kit/Glass.jsx`), a
   content-type selector, a neutral canvas zone (`.glass-panel-canvas` = opaque, never the scene),
   and a right properties/layers panel.
2. Keep the scene out of the canvas: the canvas area must be flat `--wb-solid`.
3. Click-path test: create a design → add text → add an image → undo → export → reload → restored,
   on desktop and iPhone/WebKit.

## Hazards found this session (do not rediscover)

- **API rate limit is real.** The backend puts callers in a 30/min anonymous bucket unless
  `X-User-Id` is sent. Raw `fetch` modules that skip the dev-shim header will trip 429 and then
  report it as an empty state. `Deliverables.jsx` now sends the header, honours `Retry-After` and
  retries behind a 4 s abort ceiling — copy that pattern.
- **Legacy workspace headings** are dark pine on dark glass (studio h1 measured **1.28:1**). The
  shell re-inks `h1/h2` inside `.wb-outlet`; U7 replaces the studio properly.
- **WebKit sometimes reports `prefers-reduced-motion: reduce`** — the theme-shift test branches on it
  rather than asserting the animation.
- **The 600 ms `is-shifting` class is not a stable e2e assertion**; it is unit-tested instead.
- **A Playwright assertion on a transient state needs a pre-installed observer or a wait function** —
  `window.__northstarScene` exists only after the scene effect runs; use `waitForFunction`.
- **`smoke.spec.ts` has 2 known failures** and is fixed in U14 — do not chase it.

## Rules that must not slip

- `simple`/`advanced` ids are load-bearing (`html[data-shell-mode="simple"]`, `ns-shell-mode`).
- `AGENTS.md` is append-only.
- Tabs stay mounted when hidden; that is the state-preservation contract.
- `.wb-scene` is `pointer-events:none` at z-index 0; every panel sits above it.
- Dev servers: `scripts/dev-start.ps1` only. `tailscale serve status` must say `No serve config`
  before launching; otherwise write the exact output to `needs_you.md` and stop.
