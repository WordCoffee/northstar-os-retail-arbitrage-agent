# UX rebuild — handoff

**State:** U0–U7 and U9 done and verified on both targets. **U8 is PARTIAL**: the canvas command
layer, the publishing, the backend `canvas_edit` tool and the Bojo click path are done and tested;
**package mode (front/rear panels with the dieline overlay) is not built.** Last tag `ns-ux-U8b`.
Dev servers are up from `scripts/dev-start.ps1` after `tailscale serve status` returned
**No serve config**.

**Next action:** U8's package mode, then U10 (Research scene + workspace).

## U8 — the model-facing half is done; package mode is not

Done (committed, tested):

- `src/lib/canvasCommands.js` — `parseInstruction` + `applyInstruction` (`set_text`, `scale_text`,
  `add_text`, `select`, `swap_asset`); every refusal names the reason.
- `WorkspaceTabs` publishes `summary.canvas` and registers exactly one command entry point;
  `CanvasWorkspace` registers it; `WorkbenchShell` mirrors `data-canvas-id/-layers`.
- **Backend:** `chat_tools.TOOLS["canvas_edit"]` — it only CHECKS that the open canvas can satisfy
  the instruction and refuses when there is no canvas or no such layer. `TurnIn.canvas` travels to
  `options` and into `worker_ctx`. `ChatSurface` sends the canvas, applies a `canvas_edit` tool
  result, and applies an unambiguous canvas sentence locally (before the model) so the feature works
  even when the model lane is down. `recognised:false` falls through, so a question is never hijacked.
- **Fixed:** the Bojo dock/sheet composer was 0 px wide (the chat shell kept its 236 px rail inside a
  380 px dock). The rail is an overlay in the dock and the phone sheet now.
- Tests: `bojo-canvas.spec.ts` desktop — typing "make the headline bigger" at Bojo moves the headline
  9.0% → 10.8%, read back from the properties panel; a refusal changes nothing. `test_canvas_edit_tool.py`
  6 passed. `studio-canvas.spec.ts` covers the same command layer on both targets.

Not done — the rest of U8:

1. **Package mode.** With the `package` content type, show front and rear panels with the dieline
   overlay, reusing `Dielines.jsx`'s SVG output and the print formats in `presets.js`. Do not
   re-implement the dieline geometry.

Known limit: the phone's Bojo sheet composer is not reachable in the headless iPhone profile (it sits
under the fixed bottom nav), so `bojo-canvas.spec.ts` skips mobile with that reason in the test.

## U9 — done

- `src/scene/asteroidField.js` — a deterministic field: 46 far rocks, 4 near rocks, dust, mode-reactive
  speed (`calm 1 / intense 2.2 / flare 1.7 / subdued 0.3`), a background gradient cached per size and
  mode, and `ASTEROID_MAX_COLOR = #cfc4b4` as the declared ceiling. `scenes.js` maps `ppc` to it.
- `Northstar_backend/adpilot_api.py` — `/api/adpilot/analyze`, `/bulk`, `/status` over the EXISTING
  `specialists.ppc_agent` + `ppc_bulk`. A wrong report is rejected with the missing column names; a
  malformed analysis is a refusal, not a 500; the bulk sheet is validated before it is encoded.
- `src/lib/ppcCsv.js` — the browser parser (quoted fields, BOM, CRLF). It refuses a ragged row or a
  repeated/empty header instead of repairing it.
- `src/pages/internal/ppc/PpcHarvest.jsx` — the lane: choose a CSV, see the change log (harvest /
  negate, each with its source row), build and download the validated `.xlsx`. Wired as an AdPilot
  subview (`?view=harvest` on its own route, `ap-tab-harvest` inside a workbench tab).
- AdPilot now keeps its subview in component state when embedded in a tab, so switching subviews no
  longer navigates the shell to `/adpilot`.

Evidence: unit 179/179, backend `test_adpilot_api.py` 6 passed, `ppc-harvest` 2 passed on both
targets (upload → change log → download, plus the rejection path), batch with the workbench trio +
studio-canvas green on both targets.

Honest limits: the bulk column layout is Northstar's own, not a verified Amazon template (said next
to the download); nothing is uploaded to any ad platform and no Amazon API is contacted.



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
- **U7** — the studio canvas workspace:
  - `src/pages/internal/design-studio/CanvasWorkspace.jsx` — content-type selector, glass tool
    rail, neutral canvas zone, properties/layers panel, asset list, library links.
  - `src/lib/studioCanvas.js` — content types resolved from the registries, layer factories,
    snapping, plain-value undo history, versioned autosave, PNG/PDF export helpers.
  - `src/styles/canvas.css`; `Stage` gained opt-in `snap`/`guides` props (default off).
  - `DesignStudio.jsx`: `canvas` is the first section and the default; the workspace gets
    `onNavigateSection` so the asset dashboard and dielines are **wired, not rebuilt**.

## Evidence at this handoff

| Check | Result |
|---|---|
| `npm run test:ui` | **157 passed, 0 failed** (17 new in `studioCanvas.test.js`) |
| `npm run build` | **✓ built in 1.48s** |
| `studio-canvas.spec.ts`, desktop | **4 passed, 1 skipped** (phone-only case) |
| `studio-canvas.spec.ts`, mobile | **5 passed** |
| stress `--repeat-each 2`, both targets | **18 passed, 2 skipped (58.9s)** |
| workbench trio + canvas, both targets | **31 passed, 1 skipped (1.2m)** |
| zone proof | `rgb(22, 29, 39)` = `--wb-solid`, `backdrop-filter: none`, **1** canvas inside, topmost at its centre |
| screenshots | `reports/ty/shots/u7-canvas-{desktop,mobile}.png` |

The click path is the pass criterion and it runs end to end: create → add text (typed) → upload an
image through the real file input → undo → export PNG → wait for the autosave record to hold the
post-undo document → reload → the text is back and the undone image is gone.

## Next: U10 (Research scene + workspace)

U8's only remaining item is package mode (above). U10 is the next unit in the order: a black hole
with accretion-disk lensing at the edges, a research workspace (query, sources panel, depth modes)
reusing the existing research module, and a click path plus a contrast check.

## Hazards found this session (do not rediscover)

- **`.wb-panel` was a class collision.** `chat.css` owns `.wb-panel` as a **fixed 372px floating
  aside** (the AutothinK panel). U3's shell reused the name, so every workspace rendered as a
  floating box over the outlet and the studio's canvas was 26px wide. Fixed by renaming the shell's
  panel to `.wb-tabpanel`; `workbench.css` now carries a comment so it is not re-introduced. Any new
  shell class must be checked against `chat.css`/`simple.css` first.
- **`workbench-scene.spec.ts` counted every canvas on the page.** The studio artboard is a real
  second canvas, so the assertion is now scoped to `[data-testid="scene-host"] canvas`. Keep scene
  assertions scoped; a page-wide count will keep breaking as workspaces get canvases.
- **`page.addInitScript` runs on reload.** Clearing `localStorage` there erased the autosave the
  reload test asserts. Clear once through a real navigation in `beforeEach`.
- **Autosave must not write on mount.** Restoring and immediately re-saving made the status line
  say "Saved" a heartbeat after "Restored". `dirtyRef` gates the write.
- **Toast TTL is 5 s** (`ToastCenter`); a screenshot 4.2 s after an action still catches the toast.
  Wait ≥5.6 s before a shot.
- **`/api/chat/voice/voices` returns 503** in this dev session (no voice engine). Pre-existing,
  visible as one console error; not a U7 regression.
- **The dev servers can die mid-run.** After a long Playwright run Vite was gone (`ERR_CONNECTION_REFUSED`
  on 8101) while the backend stayed up. Check both `/health` endpoints before a browser run; restart
  the whole `dev-start.ps1` (never a bare Vite) rather than starting one side by hand.
- **API rate limit is real.** The backend puts callers in a 30/min anonymous bucket unless
  `X-User-Id` is sent. `Deliverables.jsx` sends it, honours `Retry-After` and retries behind a 4 s
  abort ceiling — copy that pattern.
- **Legacy workspace headings** are dark pine on dark glass; the shell re-inks `h1/h2` inside
  `.wb-outlet`. U7's surface uses `--wb-ink` directly.
- **WebKit sometimes reports `prefers-reduced-motion: reduce`** — the theme-shift test branches on it.
- **A Playwright assertion on a transient state needs a wait function** — `window.__northstarScene`
  exists only after the scene effect runs.
- **`smoke.spec.ts` has 2 known failures** and is fixed in U14 — do not chase it.

## Rules that must not slip

- `simple`/`advanced` ids are load-bearing (`html[data-shell-mode="simple"]`, `ns-shell-mode`).
- `AGENTS.md` is append-only.
- Tabs stay mounted when hidden; that is the state-preservation contract.
- `.wb-scene` is `pointer-events:none` at z-index 0; every panel sits above it.
- The canvas zone is flat `--wb-solid` — never the scene, never blurred.
- Dev servers: `scripts/dev-start.ps1` only. `tailscale serve status` must say `No serve config`
  before launching; otherwise write the exact output to `needs_you.md` and stop.
