# UX rebuild â€” handoff

**State:** U0â€“U10 done and verified on both targets. **U8 is complete** (`ns-ux-U8-complete`);
U10 is complete (`ns-ux-U10`). Last tag `ns-ux-U10`. Dev servers are up from `scripts/dev-start.ps1`
after `tailscale serve status` returned **No serve config**.

**Next action:** U11 (Golden Goose scene + workspace).

## U8 â€” done

**Bojo on the canvas.** `lib/canvasCommands.js` (bounded parse + apply); the workspace publishes
`summary.canvas` and registers one command entry point; the backend `canvas_edit` tool checks the
open canvas can satisfy an instruction (it never mutates) and `TurnIn.canvas` travels to
`worker_ctx`; `ChatSurface` sends the canvas, applies a tool result, and applies an unambiguous
sentence locally before the model (so it works even when the model lane is down). Proven:
"make the headline bigger" at Bojo moves the headline 9.0% â†’ 10.8%, read back from the panel.

**Package mode.** `switchPanel` keeps a layer tree per panel (`front` / `back` / `gusset`) without
clearing history; switching is an undoable, autosaved document change. The dieline overlay draws
bleed / trim / fold / safe from the SAME builder the print lane uses
(`POST /api/design-studio/print/dielines/geometry`), sizes the artboard to the panel at 4 px/mm,
toggles per guide kind, and is `pointer-events:none`.

**The overlay cannot be exported.** It is an SVG in the DOM, never a canvas draw, so the export path
cannot see it â€” proven by exporting a PNG with the overlay on and off and asserting the byte counts
are identical.

**Also fixed:** the Bojo dock/sheet composer was 0 px wide (the chat shell kept its 236 px rail
inside a 380 px dock). The rail is an overlay in both containers now.

Evidence: unit 189/189, backend 9 passed (`test_canvas_edit_tool` 6 + `test_dieline_geometry_api` 3),
7 e2e specs Ã— 2 targets â†’ 44 passed / 2 skipped / 0 failed, screenshot
`reports/ty/shots/u8-package-desktop.png`, build 1.42s.

Known limit: the phone's Bojo sheet composer is not reachable in the headless iPhone profile (under
the fixed bottom nav), so `bojo-canvas.spec.ts` skips mobile with that reason in the test.

## U9 â€” done

- `src/scene/asteroidField.js` â€” a deterministic field: 46 far rocks, 4 near rocks, dust, mode-reactive
  speed (`calm 1 / intense 2.2 / flare 1.7 / subdued 0.3`), a background gradient cached per size and
  mode, and `ASTEROID_MAX_COLOR = #cfc4b4` as the declared ceiling. `scenes.js` maps `ppc` to it.
- `Northstar_backend/adpilot_api.py` â€” `/api/adpilot/analyze`, `/bulk`, `/status` over the EXISTING
  `specialists.ppc_agent` + `ppc_bulk`. A wrong report is rejected with the missing column names; a
  malformed analysis is a refusal, not a 500; the bulk sheet is validated before it is encoded.
- `src/lib/ppcCsv.js` â€” the browser parser (quoted fields, BOM, CRLF). It refuses a ragged row or a
  repeated/empty header instead of repairing it.
- `src/pages/internal/ppc/PpcHarvest.jsx` â€” the lane: choose a CSV, see the change log (harvest /
  negate, each with its source row), build and download the validated `.xlsx`. Wired as an AdPilot
  subview (`?view=harvest` on its own route, `ap-tab-harvest` inside a workbench tab).
- AdPilot now keeps its subview in component state when embedded in a tab, so switching subviews no
  longer navigates the shell to `/adpilot`.

Evidence: unit 179/179, backend `test_adpilot_api.py` 6 passed, `ppc-harvest` 2 passed on both
targets (upload â†’ change log â†’ download, plus the rejection path), batch with the workbench trio +
studio-canvas green on both targets.

Honest limits: the bulk column layout is Northstar's own, not a verified Amazon template (said next
to the download); nothing is uploaded to any ad platform and no Amazon API is contacted.



## U10 â€” done

- `src/scene/blackHole.js` â€” event horizon (`#04050a`), photon ring, an accretion disk drawn far-half
  then near-half so it crosses the hole, two lensed arcs over/under, and stars pulled slightly toward
  the centre. Palette ceiling `#f0dcb4`, covered automatically by the scene-contrast test.
- `src/pages/internal/research/ResearchDesk.jsx` â€” query the local corpus (`GET /api/corpus/search`)
  with depth modes that change the record limit (10 / 20 / 50) and say so; the API's caveats are shown
  verbatim; an empty index and an unreachable API are stated, never filled with samples.
- `AutothinK` gains a **Research Desk** subview, keeps it in component state when embedded in a
  workbench tab, and is now **wired into the workbench** (it was `NotWired`).

Evidence: unit 195/195 (7 new), `research-desk.spec.ts` 2/2 on both targets, 8 specs Ã— 2 targets â†’
48 passed / 2 skipped / 0 failed, live query returned 20 records with 2 caveats, screenshot
`reports/ty/shots/u10-research-desktop.png`, build 1.45s.

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
  Wait â‰¥5.6 s before a shot.
- **`/api/chat/voice/voices` returns 503** in this dev session (no voice engine). Pre-existing,
  visible as one console error; not a U7 regression.
- **The dev servers can die mid-run.** After a long Playwright run Vite was gone (`ERR_CONNECTION_REFUSED`
  on 8101) while the backend stayed up. Check both `/health` endpoints before a browser run; restart
  the whole `dev-start.ps1` (never a bare Vite) rather than starting one side by hand.
- **API rate limit is real.** The backend puts callers in a 30/min anonymous bucket unless
  `X-User-Id` is sent. `Deliverables.jsx` sends it, honours `Retry-After` and retries behind a 4 s
  abort ceiling â€” copy that pattern.
- **Legacy workspace headings** are dark pine on dark glass; the shell re-inks `h1/h2` inside
  `.wb-outlet`. U7's surface uses `--wb-ink` directly.
- **WebKit sometimes reports `prefers-reduced-motion: reduce`** â€” the theme-shift test branches on it.
- **A Playwright assertion on a transient state needs a wait function** â€” `window.__northstarScene`
  exists only after the scene effect runs.
- **`smoke.spec.ts` has 2 known failures** and is fixed in U14 â€” do not chase it.

## Rules that must not slip

- `simple`/`advanced` ids are load-bearing (`html[data-shell-mode="simple"]`, `ns-shell-mode`).
- `AGENTS.md` is append-only.
- Tabs stay mounted when hidden; that is the state-preservation contract.
- `.wb-scene` is `pointer-events:none` at z-index 0; every panel sits above it.
- The canvas zone is flat `--wb-solid` â€” never the scene, never blurred.
- Dev servers: `scripts/dev-start.ps1` only. `tailscale serve status` must say `No serve config`
  before launching; otherwise write the exact output to `needs_you.md` and stop.
