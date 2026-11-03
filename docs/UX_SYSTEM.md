# Northstar UX system

The shell, the service registry, the theme tokens, the scene engine, and how to add a service.
This is the map for anyone (human or agent) changing the UI after the U0–U14 rebuild.

## 1. The shell

- **Route:** `/workbench` renders `WorkspaceProvider` → `WorkbenchShell`.
- **Frame:** Bojo dock (left, collapsible, 380 px) + tab bar + outlet. On a phone the dock becomes a
  bottom sheet (peek / half / full) and the tab strip collapses behind a switcher button.
- **Tabs stay mounted** when hidden (`hidden` attribute, not unmount) — that is the
  state-preservation contract. Lazy-mount on first open, never mount every tab at once.
- **Class names are load-bearing.** The outlet's tab panels are `.wb-tabpanel`, **not** `.wb-panel`:
  `chat.css` already owns `.wb-panel` as the floating AutothinK aside, and reusing it made every
  workspace a fixed 372 px box (U7 measured a 26 px canvas).
- **z-index:** `.wb-scene` is `pointer-events:none` at 0; panels are 1+. Every tapped control in the
  e2e is hit-tested with `elementFromPoint`, because a fixed scene layer can swallow a click while
  still reporting visible.

## 2. Service registry

`src/data/serviceRegistry.js` is the single list. Each entry carries `id`, `label`, `group`, `route`,
`kind`, `scene`, `theme`, `workspaceType`, `tools`, and `source` (`catalogue` | `app-route`).

- `INTERACTIVE_SERVICES` is what the picker offers.
- `src/shell/WorkbenchShell.jsx` maps a service id to a page component in `WORKSPACES`. A service
  without an entry renders `NotWired`, which says whether it is an app-route service (has a page) or
  a catalogue-only entry (has none) — never a blank panel.
- `tests/e2e/service-coverage.spec.ts` reads the picker from the DOM and opens every service, so a
  new registry entry is covered automatically.

## 3. Theme tokens

`src/lib/serviceThemes.js` emits `--wb-*` variables per service (`themeVars(themeId)`), applied by the
shell as `data-wb-theme` + inline custom properties. The glass kit (`src/kit/Glass.jsx`,
`src/styles/kit.css`) reads only those variables, so a service switch re-skins every panel.

- Contrast is measured against **glass over the worst frame the scene may paint**, not the flat panel
  (`src/lib/serviceThemes.test.js`, `src/lib/sceneContrast.test.js`).
- Every scene exports its brightest colour (`SCENE_MAX_COLOR`); the contrast test iterates that table,
  so a new palette cannot ship without proving AA.

## 4. Scene engine

- One canvas for the whole shell (`src/scene/SceneHost.jsx`); the controller owns one frame handle
  (`sceneController.js`), pauses on `visibilitychange`, and the tier sets the fps cap
  (`src/lib/sceneTiers.js`): `cinematic` 60, `reduced` 30, `still` one frame + repaint on resize.
- `src/scene/scenes.js` is the factory: `studio` (gas giant), `ppc` (asteroid field), `research`
  (black hole), `goose` (comet), `default` (starfield with a drifting planet and shooting stars).
  An unknown id falls back to the starfield.
- Workspaces emit `idle | working | done | error` on `sceneBus`; the scene re-tones. A `done` earns a
  single **nova** (rate-limited to one a minute, skipped under `prefers-reduced-motion`).
- Measured (1280×720 Chromium, 2 s windows): studio 45 fps, ppc 60, research 60.5, goose 60,
  default 60.5; the reduced tier sits at its 30 fps cap. The studio scene is the one below budget;
  caching the planet disc did not help (45.0 → 44.5), so the next lever is baking the backdrop.

## 5. Workspaces

| Workspace | Where | Notes |
|---|---|---|
| Design Studio canvas | `pages/internal/design-studio/CanvasWorkspace.jsx` | content types, layers, snapping, autosave, PNG/PDF; package panels + dieline overlay |
| Studio shell | `pages/internal/DesignStudio.jsx` | sections; embedded mode keeps the section in component state inside a tab |
| AdPilot PPC | `pages/internal/AdPilot.jsx` + `ppc/PpcHarvest.jsx` | report → change log → validated bulk file (`/api/adpilot/*`) |
| Research desk | `pages/internal/AutothinK.jsx` + `research/ResearchDesk.jsx` | local corpus search with depth modes (`/api/corpus/search`) |
| Golden Goose | `pages/internal/GoldenGoose.jsx` | existing finder, unchanged |

**Embedded vs routed.** A room that also runs in a tab must not own the URL. `DesignStudio`,
`AdPilot` and `AutothinK` all read `location.pathname` and keep the subview in component state when
embedded, because `RoomTabs` navigates to the room's own route.

## 6. Adding a service

1. Add one entry to `serviceRegistry.js` (id, label, group, route, kind, scene, theme,
   workspaceType, tools, source).
2. Add the page component to `WORKSPACES` in `WorkbenchShell.jsx` — or leave it out and let
   `NotWired` state the truth.
3. If it needs a new scene: write `src/scene/<name>.js` with `draw/resize/speed/paletteMax`, export a
   `MAX_COLOR`, register it in `scenes.js` (factory + `SCENE_MAX_COLOR`). The contrast test covers it.
4. If it needs a new theme: add tokens in `serviceThemes.js`; the contrast test and the snapshot cover
   it.
5. Add a click-path spec under `tests/e2e/` and run it on both projects.

## 7. Testing

- Unit: `cd northstar-os-ui && npm run test:ui` (node --test over `src/lib/*.test.js`).
- e2e: `npx playwright test <spec> --project=chromium-desktop|chromium-mobile` (localhost only;
  Playwright Test is the sanctioned path for `tests/e2e` against 127.0.0.1).
- Backend: `cd Northstar_backend && python -m pytest <file> -q`.
- Dev servers: `scripts/dev-start.ps1` only. `tailscale serve status` must say `No serve config`.
- The API files anonymous callers in a 30/min bucket; lanes that call it retry once behind
  `Retry-After` and say so when they cannot.
