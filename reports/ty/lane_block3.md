# block3-workspaces — service workspaces, the core six

Lane C, 2026-11-11. Status: **DELIVERED**, with one environment action taken and
three pre-existing e2e failures found (not touched).

Acceptance (verbatim from the queue): *"Each core service has a workspace +
click-path test on desktop Chromium and iPhone 12 WebKit, scene events,
DevBanner, canUseService stub, open-tab context to Bojo."*

---

## 1. What the six are, and why these routes

The queue names the six by role, not by route. This is the mapping used, and it
is recorded in the file itself (`core_six`) rather than only here:

| role | service id | route | workspace |
|---|---|---|---|
| design | `design-studio` | `/design-studio` | Design Studio (12 sections) |
| listings | `listings` | `/listings` | Listing Guardian |
| ppc | `adpilot` | `/adpilot` | AdPilot (the PPC workbench) |
| golden-goose | `golden-goose` | `/golden-goose` | Golden Goose |
| research | `product-finder` | `/product-finder` | SourceScout |
| product-pictures | `product-pictures` | `/product-pictures` | **new route**, renders the studio's Listing Images surface |

`product-pictures` did not exist as a service before this lane. The blueprint
(`ty/TARGET_SPEC.md:579`) treats "product pictures in any seller situation" as a
first-class job, and the studio already ships the surface
(`pages/internal/design-studio/ListingImages.jsx`, `data-testid="listing-images-workspace"`).
It now has its own route, tab, scene and workspace spec instead of being a
section picker inside a twelve-section studio. Nothing was duplicated: the page
renders the existing component.

---

## 2. The artifact

`ty/northstar_workspaces.json` — the existing generated block is **untouched**;
this lane appended an additive block after it (`git diff` is +405 lines, 0
deletions):

- `:763` `scene_workspaces_schema` — `northstar.scene_workspaces.v1`
- `:764` `scene_workspaces_generated_by` — hand-authored, **not** produced by
  `tools/registry/build.py`
- `:766` `core_six` — the role → service table above
- `:792` `default_scene` — `{service: home, label: Deep Field, variant: orion-nursery}`
- `:798` `default_workspace` — the fallback every undescribed service gets
- `:830` `scene_workspaces[]` — one entry per core service, each with `id`,
  `core_role`, `label`, `service`, `route`, `page`, `page_title`, `page_anchor`,
  `click_path_view`, `scene {id,label,variant}`, `views {param, default,
  tabs_rendered_by, tabs[]}`, `bojo_tool {id,status,owner,source,note}`,
  `gate {entitlement_key, decided_by, dev, denied}` and a `why`.

Tool ids are the ones `ty/bojo_tool_list.json` actually reports as `wired`
(`generate_image`, `optimize_listing`, `plan_campaign`, `golden_goose_scan`,
`scan_products`). `product-pictures` has **no** tool of its own — `chat_tools`
carries no `product_picture` tool — so it declares the shared `generate_image`
lane and says so in `note`. It does not claim a tool it does not have.

**Known interaction, stated plainly:** `Northstar_backend/test_service_registry.py::test_generated_files_are_current`
compares `ty/northstar_workspaces.json` byte-for-byte with
`build.build_workspaces(registry)`, so a future `python -m tools.registry.build`
would drop this block. That test was **already failing before this lane**
(`assert build.check_actions(registry) == []` → a `hub:` route citation, `Northstar_backend/test_service_registry.py:273`),
so this lane turns no green test red — measured, see §6. The block is marked
`scene_workspaces_generated_by` so the next person cannot mistake it for
generated output.

---

## 3. The UI renders from that file

| file | what it does |
|---|---|
| `northstar-os-ui/src/data/workspaces.js` | the renderable mirror (`WORKSPACE_SPECS`), generated from the artifact |
| `northstar-os-ui/scripts/sync-workspaces.mjs` | the generator — `node northstar-os-ui/scripts/sync-workspaces.mjs` |
| `northstar-os-ui/src/lib/workspaceSpecs.js:20` | `MIRRORED_KEYS`, the keys the mirror must share with the artifact |
| `…workspaceSpecs.js:50` | `workspaceForService()` — `null` for anything not described (that is the fallback) |
| `…workspaceSpecs.js:71` | `resolveView()` — reads the room's own query key (`view`, or `section` for the studio) |
| `…workspaceSpecs.js:104` | `workspaceGate()` — delegates to `canUseService`, never invents an answer |
| `…workspaceSpecs.js:110` | `billingStubEnforced()` — the dev-only switch, `false` in a production build |
| `…workspaceSpecs.js:125` | `workspaceScene()` — the file's scene, else `default_scene` |
| `northstar-os-ui/src/workspaces/WorkspaceFrame.jsx:79` | **the one surface**: name, scene, Bojo tool, gate, active view, declared view list; `data-testid="ws-frame"` at `:112` |
| `northstar-os-ui/src/shell/WorkspacePanels.jsx:66` | the frame is mounted around each tab's panel — one place, not six |

Why a mirror instead of importing the artifact: the Vite root is
`northstar-os-ui/`, so `server.fs.allow` refuses a file above it in dev, and
`Dockerfile.ui` builds from that directory alone where `ty/` does not exist.
`src/lib/workspaceSpecs.test.js` compares the two copies key by key, so the
mirror cannot drift — it is a checked mirror, not a second source of truth.

The frame deliberately does **not** draw a second tab strip. Every one of the six
rooms already owns its own strip (`RoomTabs`, or the studio's section picker) and
owns the click; the frame declares the same list and reports which view is
active, so a room that renames a view without updating the file fails the
click-path test.

Wiring added for the new service:
`App.jsx:185` (route), `shell/tabRoutes.js:27` (tab pattern),
`shell/WorkspacePanels.jsx:27` (panel), `data/serviceRegistry.js:32,77` (scene id
+ entry), `scenes/sceneRegistry.js:26` (scene), `data/nav-config.js:13` (rail),
`pages/internal/ProductPictures.jsx:17` (page).

---

## 4. Scene events

`northstar-os-ui/src/scenes/SceneSurface.jsx:29` `SCENE_EVENT = 'northstar:scene'`,
dispatched at `:99` **only when the scene identity changes** (deps `[scene.id]`),
with `{serviceId, sceneId, variantId, label, mode, swappedFrom, at}` and mirrored
on `globalThis.__northstarScene`. `data-scene-id` / `data-scene-variant` on the
bed remain the state; the event is the transition. Every click-path spec records
the event through `addInitScript` and asserts the id **and** the variant.

## 5. DevBanner, gate, open-tab context

- **DevBanner** — asserted present exactly once and painted *above* the workspace
  (bounding boxes) in every workspace spec. The production negative cannot be
  produced by a local dev run (a dev session is `dev_shim` by construction), so
  it is proved where it is provable: `src/shell/devBanner.test.js` under
  `npm run test:ui`.
- **canUseService stub** — the frame renders `data-ws-gate="denied"` and replaces
  the page with `data-testid="ws-gate-denied"` (naming the entitlement key and
  `no studio credit`) when the gate refuses. Reached in a browser through the
  dev-only `?billing=enforce`, which `billingStubEnforced()` returns `false` for
  unless `LOCAL_DEV` — a production build compiles it out. **No billing runs and
  no credit is spent.**
- **Bojo** — `ShellLayout.jsx:120` publishes `{…tabSummary, view: <resolved
  workspace view>, workspace, tool}` on `data-tab-summary`,
  `globalThis.__northstarWorkspaceTab` and the `northstar:workspace-tab` event;
  `shell/tabRoutes.js:202` carries the two new fields; `chat/turnBody.js:32`
  forwards them into `state.workspace` / `state.tool`, which is what a turn
  sends.

---

## 6. Evidence — exact commands and real output

Dev stack (no GPU, no media lane):

```
$env:NORTHSTAR_NO_MEDIA="1"; powershell -File scripts/dev-start.ps1
Running dev safety gate: …\scripts\check_dev_safety.py
dev safety gate: OK
backend PID=…, ui PID=…
backend ready: {"status":"ok","service":"northstar-backend","version":"1.0.0"}
ui ready: …
```

(First attempt, before the Tailscale step in §8: gate exit 2, nothing started.)

Workspace click paths, one run, both named projects:

```
npx playwright test tests/e2e/workspaces --project=desktop-chromium --project=iphone-12-webkit --reporter=line --workers=1
  56 passed (40.5s)
```

Per project (same specs, run separately first):

```
npx playwright test tests/e2e/workspaces --project=desktop-chromium --reporter=line --workers=1
  28 passed (14.1s)
npx playwright test tests/e2e/workspaces --project=iphone-12-webkit --reporter=line --workers=1
  28 passed (18.9s)
```

`iphone-12-webkit` is `devices['iPhone 12']`, whose `defaultBrowserType` is
**webkit** — WebKit 27.2 / playwright build v2370, already installed at
`%LOCALAPPDATA%\ms-playwright\webkit-2370`. Nothing was downloaded for this lane.

UI unit tests (221 before this lane):

```
cd northstar-os-ui && npm run test:ui
  tests 231 / pass 231 / fail 0
```

Production build:

```
cd northstar-os-ui && npm run build
  ✓ built in 1.42s   (four runs: 1.51s / 1.46s / 1.53s / 1.42s; 0 errors, 0 warnings)
```

Backend registry tests, **before** the artifact edit and **after** — identical:

```
python -m pytest Northstar_backend/test_service_registry.py -q
  before: 2 failed, 14 passed
  after : 2 failed, 14 passed
  failed: test_every_action_citation_still_resolves
          test_generated_files_are_current   (assert build.check_actions(registry) == [])
```

Existing browser specs re-run on `chromium-desktop` (the project that existed
before this lane), because the frame now sits inside five existing rooms:

```
npx playwright test tests/e2e/{workspace-tabs,shell-chrome,service-coverage,ux_service_routes,smoke,workbench-scene}.spec.ts --project=chromium-desktop
  49 passed / 1 failed   → shell-chrome "72 routes" pin (I added one route)
  after updating the pin to 73 (and SHELL_ROUTES 66 → 67):
  6 passed (1.2m)

npx playwright test tests/e2e/{ppc_primary_action,research-desk,goose-desk,product_finder_contract}.spec.ts --project=chromium-desktop
  7 passed (11.3s)
```

---

## 7. Per-core-six status

| role | route | click-path (Chromium) | click-path (iPhone 12 WebKit) | scene event | DevBanner | gate refusal | Bojo tab context |
|---|---|---|---|---|---|---|---|
| design | `/design-studio` | PASS | PASS | PASS | PASS | PASS | PASS |
| listings | `/listings` | PASS | PASS | PASS | PASS | PASS | PASS |
| ppc | `/adpilot` | PASS | PASS | PASS | PASS | PASS | PASS |
| golden-goose | `/golden-goose` | PASS | PASS | PASS | PASS | PASS | PASS |
| research | `/product-finder` | PASS | PASS | PASS | PASS | PASS | PASS |
| product-pictures | `/product-pictures` | PASS | PASS | PASS | PASS | PASS | PASS |
| **default scene** (non-core: `/hub`, `/keywords`) | – | PASS | PASS | PASS | – | – | – |

4 tests per core service × 6 + 4 default-scene tests = 28 per project.

---

## 8. Refused, blocked, and found

1. **Tailscale serve on port 8000 — I closed it, and you should know.**
   `scripts/dev-start.ps1` refused twice: *"tailscale funnel status is non-empty /
   tailscale serve config targets port 8000"*. The config was
   `https://msi.tail4b3dfd.ts.net (tailnet only) → / proxy http://127.0.0.1:8000`,
   i.e. the local dev backend (and its loopback dev login bypass) reachable from
   every device on the tailnet. Nothing was listening on 8000 at the time, so no
   surface was live. I ran `tailscale serve reset` → `No serve config`, then the
   safety gate passed. I did **not** restore it: `reports/ty/needs_you.md` #1
   records "no serve config" as the wanted state. To put tailnet access back:
   `tailscale serve --bg --https=443 http://127.0.0.1:8000`. This is the one
   action in this lane outside the repo — everything else is in the tree.
   (The prior UX lane hit the same gate on 2026-11-02 and chose to block instead
   of touching Tailscale; the owner directive of 2026-10-28 says to decide, log
   and continue, and the gate itself asks for the condition to be fixed.)
2. **Not run: `service-screens.spec.ts`.** It writes screenshot baselines into the
   tree; running it would leave capture artefacts behind for a lane that is not
   about visuals.
3. **Three e2e failures found and NOT touched — they are pre-existing and outside
   this lane's subject:**
   - `ux_scorecard.spec.ts` "ux: creative" and "ux: research": axe
     `aria-required-children` on `.wst-list` (the workspace tab bar) — a
     `role="tablist"` containing `button[aria-label="Close … tab"]` inside
     `role="presentation"` wrappers. `src/shell/TabBar.jsx` is unmodified by this
     lane (verified: `git status` shows it clean). **Real accessibility defect,
     worth a queue entry of its own.**
   - `ux_scorecard.spec.ts` "ux: scene readability": the chat stream on `/home` is
     already scrolled (`stream_scroll_top = 634`) so the empty state is scrolled
     away on load. The chat surface is untouched by this lane.
4. **`chromium-mobile` is a misnomer, not a bug in this lane.** `chromium-mobile`
   is `devices['iPhone 12']`, which runs **WebKit**. That is why this lane added
   two honestly-named projects (`desktop-chromium`, `iphone-12-webkit`) rather
   than reusing it. The two new projects are `testMatch`-limited to
   `workspaces/**`, so the rest of the suite is not quadrupled; the two older
   projects still collect the workspace specs and skip them with a named reason.

---

## 9. Verification pending / not claimed

- The gate refusal is proved through a **stub**. The production decision belongs
  on the server and there is no billing: no charge was made, no credit spent.
- The DevBanner's production-negative is proved by unit test, not by a browser
  run (a local dev run cannot produce a JWT session). Not overclaimed.
- `product-pictures` has no `product_picture` tool in `chat_tools`; it opens the
  shared `generate_image` lane and the file says so.

## 10. One command a verifier should re-run

```
npx playwright test tests/e2e/workspaces --project=desktop-chromium --project=iphone-12-webkit --reporter=line --workers=1
```

Expected: **56 passed**. If the stack is not up, start it first with
`$env:NORTHSTAR_NO_MEDIA="1"; powershell -File scripts/dev-start.ps1` — the
safety gate now passes (`tailscale serve status` → `No serve config`); the e2e
config also reuses an existing server on 127.0.0.1:8101.
