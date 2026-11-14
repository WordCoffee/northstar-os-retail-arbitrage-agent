# `on-staging` audit — 13 queue jobs vs. the tree

Date: 2026-11-14 · Branch under test: `staging` · Audit started at `31334ea4`, finished at
`2a0dbba4`. The only commit in between (`2a0dbba4`, PPC G4 contract) touches no audited code path
and adds one unrelated queue entry; the 13 jobs below are unchanged between the two. Auditor:
read-only subagent. Only write: this file.

## Method (what was executed, not just read)

1. Read each job's `title`, `write_paths`, `acceptance`, `note` from `reports/ty/director_queue.json`.
2. Located the named deliverable and its `file:line` in the working tree.
3. Ran the narrow tests for each job. Backend: `pytest` with
   `--basetemp=C:\Users\T2Hol\AppData\Local\Temp\opencode\onstaging_pt`. UI: `node --test` on the
   `node:test` suites, and — because **vitest is not installed** (`node_modules/vitest` absent,
   not in `package.json`, global npm has none) — the repo's own vitest files were run **unmodified**
   under `node --test` with a temp-only loader (`C:\Users\T2Hol\AppData\Local\Temp\opencode\vtshim`)
   that maps `import 'vitest'` to `node:test` + a minimal `expect`, `import.meta.env` to a literal,
   and CSS/asset imports to stubs. Nothing in the repo was touched.
4. Called **all seven** tool handlers **through the same `chat_tools` adapter Bojo uses** (not the
   domain function directly).
5. Ran two measurement CLIs without `--write`: `tools/seller_scores.py --ceiling` and
   `tools/seller_scores.py`.

Not run, by rule or by environment: Playwright e2e (browser), the full suite, any Amazon host, any
credential read, any service restart.

## Verdicts

| id | verdict | evidence (file:line) | tests run — exact counts | what is missing |
|---|---|---|---|---|
| **sel-02-design-studio** | **IMPLEMENTED** | `tools/seller_scores.py:500` `ceiling()`, `:630-631` argparse; `tools/seller_tester/harness.py:189` `_placement_xywh`; `tools/seller_tester/generators.py:457` `flat()`; commit `88706b14` | pytest 28 + 26 + 54 = **108 passed**; CLI `--ceiling` reproduces 56 briefs / 12 resolvable / 32 prompt-only / 12 unresolved / 21.4 %; CLI (no `--write`) reproduces `design-studio: mean 96.2, scored 32, passed 32` | the 3 failures its own report lists (ST-035 text, ST-038/044 4:5 aspect) have **no rows in any current `state/seller/*.json`**, so whether they closed is unverified; published mean covers 21.4 % of the catalogue (by design, stated in the report) |
| **sel-03-aplus** | **IMPLEMENTED** | `tools/seller_tester/aplus.py:856` `run_aplus_family`; `tools/seller_tester/deterministic.py:419,426` band/copy variants; `northstar-os-ui/src/studio/aplus/AplusModules.jsx`; `src/pages/internal/design-studio/APlus.jsx:65` | pytest `test_seller_tester_aplus.py` **13 passed**; `node --test aplusMetrics` **5 passed**; artefacts on disk: 47 PNGs in `renders/aplus/`, `state/seller/aplus_proof.json` (6/6 briefs, `determinism_proved: true`) | renders + proof are gitignored, so a fresh checkout cannot reproduce without the Mogra uploads; no diffusion scene (AP-004 downgraded `generated`→`flat`, declared) |
| **ux-06-shell** | **PARTIAL** | `northstar-os-ui/src/shell/ShellLayout.jsx:192-223` (SceneHost, TopNav, SuiteRail, `workspace-outlet`), `src/App.jsx:179` single layout route, `src/App.jsx:361` DevBanner above the route switch; commit `ad86d8b3` | `node --test devBanner` **4 passed**; `node --test shellRoutes` **4 passed, 1 FAILED**: `shellRoutes.test.js:22` “App.jsx registers 72 routes” → `expected length 72, got 73` (App.jsx has 73 `<Route path=…>`; block3 added `/product-pictures`) | the lane's own suite is **red on staging**: the route-count pin was not updated. Chrome itself is present on every route; the failing assertion is a stale constant, not a missing feature |
| **ux-07-tabs** | **IMPLEMENTED** | `src/shell/ShellLayout.jsx:197-199,214`; `src/shell/tabRoutes.js:182` `tabSummary()`; `src/shell/WorkspacePanels.jsx:25` `TAB_PANELS`; `src/chat/ChatSurface.jsx:627-638`; `Northstar_backend/chat_router.py:820` (`tab` field), `:1020-1027` (prompt line), `:1211`; commits `693fdd24`, `a5608616`+ | `node --test tabRoutes` **12 passed**; `node --test turnBody` **5 passed**; pytest `test_chat_tab_context.py` **5 passed** = **22 passed** | e2e `tests/e2e/workspace-tabs.spec.ts` (5 tests) exists, not run (browser). Nothing known missing: the ux-07b gap (backend dropped `tab`) is closed by `chat_router.py:820` |
| **ux-08-scene** | **IMPLEMENTED** | `src/scenes/sceneEngine.js:116` mode resolution, `:269` runtime, `:422` host, `:53` renderer counter; `src/scenes/SceneSurface.jsx:39,127`; `src/shell/ShellLayout.jsx:204-208`; commit `2c777714` | `node --test` sceneEngine **17**, sceneRegistry **10**, SceneSurface **7**, SceneHost **5** = **39 passed** | e2e `workbench-scene.spec.ts` (6 tests) not run. No three.js by design; `live` is a 2D plate gated on WebGL2 — declared in the report |
| **ux-09-design-studio-canvas** | **IMPLEMENTED** | `src/pages/internal/design-studio/CanvasWorkspace.jsx:526` `doExport`, `:657,661` PNG/PDF buttons, `:453` `loadDieline`, `:88` Assets panel; `src/studio/engine/doc.js`, `snap.js`; `src/lib/studioCanvas.js`; commit `99411a70` | `node --test` studioCanvas **17**, dielineOverlay **10**, canvasCommands **11**; + snap **10**, doc **7**, workspace **8** = **63 passed** | the export **download** and the drag/select click path are proven only by `tests/e2e/studio-canvas.spec.ts` (6 tests, not run). Rotated-layer snapping, keyboard nudge, top-left resize handle: declared out of scope, still absent |
| **tool-scan-products** | **IMPLEMENTED** | `Northstar_backend/bojo_tools/sourcing_extra.py:96`; spec `chat_tools.py:1961`; offered-tool merge `chat_tools.py:2719-2722`; commit `1734b043` | pytest `test_bojo_tools_sourcing_extra.py` **12 passed** (+ registry 7, offering 12 shared); **live probe through `chat_tools.TOOLS['scan_products']['handler']`: `ok=True`, 2 candidates from the 89-row cache, `live_requested: false`** | a query with no cache hit refuses (`no candidates (cache=fresh; no live request made)`) — correct, but the catalogue Bojo can drive is only the 89 cached rows until a live envelope is armed |
| **tool-compose-listing** | **IMPLEMENTED — live path BLOCKED-ENV** | `bojo_tools/publishing.py:110`; spec `chat_tools.py:1909` | pytest `test_bojo_tools_publishing.py` **15 passed** (compose+dieline share the file) | **probe: `ok=False`, “listing composer refused: OpenCode Go is not configured (OPENCODE_GO_API_KEY missing)”** — every offered call refuses in this environment. Handler is correct (refuses, never fabricates) but “ListingForge can compose from Bojo” is not demonstrable here |
| **tool-build-dieline** | **IMPLEMENTED** | `bojo_tools/publishing.py:221`; spec `chat_tools.py:1892` | pytest 15 shared (above); **probe: `ok=True`** with `template_id: tuck_end`, returns `template_id/width_mm/height_mm/elements/layers/audit` | no persistence by design (domain tools have no DB session); storage left to the caller |
| **tool-track-keywords** | **PARTIAL** | `bojo_tools/keywords.py:84`, refusal path `:123-126`; spec `chat_tools.py:1994-2008` (properties: `listing`, `brand_key` only) | pytest `test_bojo_tools_keywords.py` **11 passed**; **probe: `ok=False`, “no brand SEO profile supplied (pass profile, or profile_store + brand_key)”** | **the offered tool cannot succeed**: `profile` is not in the spec and `_bojo_handler` (`chat_tools.py:1858-1873`) injects only `account_id`/`project_id`, never a `profile_store`. Every call Bojo can make hits the no-profile branch, whatever `brand_key` it passes. The 11 tests inject a profile directly, which the chat path cannot |
| **tool-watch-competitor** | **IMPLEMENTED** | `bojo_tools/competitors.py:102`; spec `chat_tools.py:2009`; commit `1734b043` | pytest `test_bojo_tools_competitors.py` **7 passed**; **probe: `ok=False`, “no stored competitor observation for B0TEST12345”** (correct) | spec's `stage` has no `enum`, so an invalid stage produces a caught `ValueError: stage must be one of offers, sales, identity` as the summary instead of a business refusal; empty store means it reports nothing until the monitor populates one |
| **tool-margin-report** | **IMPLEMENTED** | `bojo_tools/economics.py:63`; engine `foundation/economics/engine.py:20`, inputs `foundation/economics/inputs.py:34-40`; spec `chat_tools.py:1928` | pytest `test_bojo_tools_economics.py` **9 passed**; **probe: `ok=True`** with `selling_price, acquisition_cost, referral_fee_amount, fba_fulfillment_fee, advertising_cost, total_revenue` (data under `data.economics`) | **key-name trap**: the spec description says “cost, price, fees, quantity” and the refusal names `referral_fee`, but the engine accepts `referral_fee_amount`/`referral_fee_rate` and drops `referral_fee` silently. A model following the message loops. Function works once the real keys are used |
| **tool-plan-campaign** | **IMPLEMENTED** | `bojo_tools/campaigns.py:71`; spec `chat_tools.py:1942` | pytest `test_bojo_tools_campaigns.py` **9 passed**; **probe: `ok=True`**, `no_spend: true` in payload | nothing found; budget/ACoS guards proven in tests |

**Totals actually executed:** 13 backend files, **208 tests passed, 0 failed**; 15 UI files, **133 cases — 132 passed, 1 failed** (the ux-06 route pin); 7 live adapter probes; 2 measurement CLIs.

## Defects found (all reproducible, none fatal to a job except where noted)

1. **`shellRoutes.test.js:22` is red on `staging`** — pins 72 routes, App.jsx has 73. Found by running the lane's own suite, not by grep.
2. **`track_keywords` is offered but unreachable** — no `profile` property, no store injection. This is the one job whose stated purpose (“Keyword Tracker can track from Bojo”) is not met by the shipped wiring.
3. **`margin_report` names keys it does not accept** — spec description (“cost, price”) and the missing-input label (`referral_fee`) both differ from `selling_price`/`acquisition_cost`/`referral_fee_amount`. Self-correcting only for a caller that guesses.
4. **`compose_listing` cannot run here** — `OPENCODE_GO_API_KEY` missing; the refusal is honest, the capability is absent in this checkout.
5. **`watch_competitor` `stage` has no enum** — invalid values surface as a `ValueError` string.

## What this proves / what it does not prove

**Proves**

- All 13 jobs have a **commit trace on `staging`**, and the deliverables are in the tree at `31334ea4`:
  `1734b043` (all seven handlers), `ad86d8b3` (ux-06), `693fdd24` (ux-07), `2c777714` (ux-08),
  `99411a70` (ux-09), `803cd38d` (sel-03), `88706b14` (sel-02). The earlier audit's “no branch/commit
  trace for 11” is a **branch-name lookup artefact**: the queue's `branch` column names
  `ty/tool-*` / `ty/sel-02-design-studio` / `ty/sel-03-aplus`, none of which exist; the work landed
  under `ty/reg-03-handlers`, `ty/sel-02`, `ty/sel-03` or as direct staging commits.
- `on-staging` is therefore **true as “present in staging HEAD”** for 12 of 13 jobs, and true-with-a-gap
  for `track_keywords` (present, but not usable from Bojo).
- For the seven tool jobs the wiring is not just a spec: the same adapter Bojo calls was exercised and
  three of them returned real work (`scan_products` 2 candidates, `build_dieline` a real dieline,
  `plan_campaign` a plan), while the rest refused with a named reason.
- Score claims I could reproduce: `seller 96.2 / 32 scored / 32 passed`, ceiling `12/32/12 = 21.4 %`.

**Does not prove**

- **No browser proof was produced here.** Every click-path claim for ux-06/07/08/09 rests on specs I
  did not run (`shell-chrome` 6, `workspace-tabs` 5, `workbench-scene` 6, `studio-canvas` 6 tests).
  A component that renders correctly in a unit test is not a component whose buttons work.
- **The vitest suites ran under a compatibility shim, not vitest.** 89 of the 90 shell/scene/studio/chat
  cases passed under it and one failed on a plain length assertion; I judge the shim sound for
  these files, but a vitest run remains the authoritative number.
- **sel-02's 93.5-over-12 is not re-derivable now**: no current `state/seller/*.json` carries the
  ST-033…ST-044 rows, so the three declared failures' present status is unknown. Only the current
  aggregate (96.2/32) reproduces.
- **Nothing about output quality.** Passing tests say the code path runs; they do not say the picture
  is good. That judgement belongs to the Seller-Tester populations, which cover 21.4 % of the brief
  catalogue.
- **Nothing about Amazon-facing behaviour**: no live search, no purchase, no listing submission was
  exercised, and `scan_products` live mode was deliberately not armed.
