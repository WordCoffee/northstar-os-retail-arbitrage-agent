# ux-08 — scene engine wired to the shell

Branch `ty/ux-08-scene`, worktree `state/worktrees/ux-08`, base `d5ade863`.

## Lifecycle (one paragraph)

`ShellLayout` mounts `<SceneHost>` exactly once, as the first child of the app
frame, and points it at the **active tab id** (falling back to a path-derived
service for non-workspace routes, then to the `home` scene). `SceneHost` resolves
a descriptor from `src/scenes/sceneRegistry.js` (palette + poster + motion
numbers, one entry per tab service, posters are the existing
`src/assets/galactic/*.webp` plates via `galacticVariants.js` — nothing is
fetched). `SceneSurface` decides the mode **during render** with
`resolveSceneMode({ webgl2, reducedMotion })` → `live | static | reduced`, so the
first paint is already correct, then its effect gives the canvas to
`createSceneHost()`, which **disposes the resident scene before building the
next one**: `dispose()` cancels the pending `requestAnimationFrame`, drops the 2D
context reference and zeroes `canvas.width/height` (which frees the backing
store), decrementing the module-level `liveRenderers` counter. A tab switch is
therefore `live === 1` before and `live === 1` after — never 2 — and unmount is
`1 -> 0`. `visibilitychange` pauses/resumes the single loop, so a background tab
schedules no frames. The mode the engine settled on is mirrored onto the shell
frame as `data-scene-bed`, which is what `scene.css` keys the paper veil off.

## What the fallback actually renders

Either the single `<canvas class="scene-canvas">` (mode `live`) **or** the
service's own poster `<img class="scene-poster" src="…webp">` (mode `static` or
`reduced`). The mode is written to `data-scene-mode` on the bed, with
`data-scene-animated="true|false"`. In `static` and `reduced` there is **no**
`requestAnimationFrame` at all and the canvas is never even asked for a context —
the tests assert `canvas.contexts === []` and `scheduler.pending === 0`.

| mode | when | element | frames |
|---|---|---|---|
| `live` | WebGL2 present, motion allowed | one `<canvas>` | rAF loop |
| `static` | `webgl2` probe returns null, or no 2D context / no canvas / paint threw | poster `<img>` | none |
| `reduced` | `prefers-reduced-motion: reduce` (wins over WebGL2) | poster `<img>` | none |

The `webgl2` probe runs **once per document** on a detached canvas and releases
its probe context immediately (`WEBGL_lose_context`), so the probe never costs a
GPU context for the life of the tab. `SceneSurface` also accepts an
`environment` prop, which is how the tests force `{ webgl2: false }` without a
GPU.

## Commands and real output

```
$ npm ci
added 66 packages, and audited 67 packages in 3s

$ npm run build
dist/assets/index-cEssTj-m.js   194.19 kB │ gzip: 61.74 kB
dist/assets/DesignStudio-Dk0PUa9R.js 401.58 kB │ gzip: 117.85 kB
✓ built in 1.47s

$ npx vitest run src/scenes src/shell
 Test Files  7 passed (7)
      Tests  60 passed (60)
   Duration  283ms
```

(The `vitest` binary is not a dependency of this package — `npx` fetched
vitest 5.1.0 for the run. The three pre-existing shell suites
(`devBanner`, `shellRoutes`, `tabRoutes`) still pass alongside the four new
ones.)

## The counter that was asserted

`sceneRendererStats()` in `src/scenes/sceneEngine.js`:

* one mount → `{ live: 1, created: 1, disposed: 0 }`
* switch service → `{ live: 1, created: 2, disposed: 1 }` (`replaced: 'listings'`)
* unmount → `{ live: 0, created: 2, disposed: 2 }`, `canvas.width === 0`,
  `scheduler.pending === 0`

Both directions of the trap are covered: the host test proves a switch does not
stack a second loop, and the "release" test proves disposal frees the backing
store rather than leaving a zero-frame canvas allocated.

## Files

New:
- `northstar-os-ui/src/scenes/sceneEngine.js` — mode resolution, probes, the 2D
  paint, `createSceneRuntime` / `createSceneHost`, the renderer counter.
- `northstar-os-ui/src/scenes/sceneRegistry.js` — service → scene, path → service.
- `northstar-os-ui/src/scenes/SceneSurface.jsx` — the single canvas / poster.
- `northstar-os-ui/src/scenes/scene.css` — bed placement, paper veil.
- `northstar-os-ui/src/scenes/sceneEngine.test.js` (17 tests)
- `northstar-os-ui/src/scenes/sceneRegistry.test.js` (10 tests)
- `northstar-os-ui/src/scenes/SceneSurface.test.jsx` (7 tests)
- `northstar-os-ui/src/shell/SceneHost.jsx`, `SceneHost.test.jsx` (5 tests)

Changed:
- `northstar-os-ui/src/shell/ShellLayout.jsx` — mounts `SceneHost` once, adds
  `data-scene-bed`.

## Not done

* **No three.js.** It is not installed and no new dependency was added, so the
  "live" scene is a procedural canvas-2D plate (graded sky, three drifting
  nebula lobes, deterministic star field, orbit arcs), not a WebGL/3D scene.
  Correspondingly, `live` requires *WebGL2 to be available* (that is the gate the
  unit specifies) but the painting itself is 2D — a machine with WebGL2 disabled
  gets the poster, which is the required behaviour, though it is stricter than
  the renderer needs.
* **No browser/visual check.** No dev-server screenshot was taken in this lane;
  the bed is behind `.main-content`, which becomes a 0.93-alpha paper veil while
  a scene is mounted, so the scene reads at ~7%. Placement and contrast are
  argued in `scene.css` comments, not measured in a browser.
* The `home` scene also shows on admin and customer rooms that render inside
  `ShellLayout` (one bed per shell, by design); those routes were not given their
  own scenes.
* Paused state (background tab) is implemented and unit-tested on the runtime,
  but not asserted end-to-end in a browser.
