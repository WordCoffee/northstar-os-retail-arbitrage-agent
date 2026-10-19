# Simple-mode interface rebuild (V4.2) + film-faithful Gargantua

**Date:** 2026-10-18 · **Branch:** `feature/v4.1-mesh`
**Operator brief:** *"the user interface is too small … the words are hard to read
everywhere … the galactic background looks really fake and not like Interstellar
the movie at all … redo the interface for simple … build an all new user interface
for Northstar OS and AutothinK in simple mode"*.

Answers given before starting (asked because this is a deep-visual step): keep the
current model · **film-faithful Gargantua** · **Northstar OS + AutothinK simple
mode**.

---

## 1. What was actually wrong (measured, not guessed)

| Complaint | Measured cause |
|---|---|
| "too small" | base token `--text-base: 0.875rem` (14px); the chat surface hard-coded **10.5 / 11 / 12 / 12.5 / 13 / 13.5px** for body, meta and controls |
| "words hard to read" | `--ink-soft: #8a8a7a` on a **62%-opaque** panel over a bright background — the panel let the artwork eat the contrast; no reading measure cap |
| "cramped" | a 780px block pinned to the **left edge** of a full-width panel, 6–8px internal gaps |
| "background looks fake" | a giant saturated **purple planet** dominating the frame, cartoon orbiting moons, uniform donut disc with no lensed arc, no photon ring, per-frame noise flicker |

---

## 2. Research basis (honest count)

A bounded survey was run — **27 web searches + 4 page fetches, 44 named sources
read in substance**. Not "10,000 repos": that number was not achievable honestly
and is not claimed. Sources included the Figma community chatbot-template category
and its template listings, shadcn/ui AI Elements (message, tool, message-scroller,
sidebar), assistant-ui (tools, reasoning, action bar, scroll anchor), Vercel
`chatbot`, LibreChat, Open WebUI, AnythingLLM, Lobe UI, CopilotKit, MUI X Chat,
OpenAI's Apps SDK design guidelines, plus W3C WCAG techniques (G18/G17, F83, 2.5.8
target size), NN/g and Smashing on text-over-images, and the Gargantua literature
(James et al. 2015 / DNGR, Luminet, and two open-source Kerr renderers).

It corrected two things I had built wrong in the first pass:

1. **DNGR deliberately omitted the Doppler shift** to keep the disc *symmetric and
   golden*. My first shader had a 2.7× asymmetry — a physics-paper render, not the
   film. Now ≤1.35×.
2. **The brightest artwork must not sit under the reading column.** My first pass
   put the disc straight behind the panel; at 90% opacity it still bled through as
   a grey wash. The hole now lives in the left gutter and the panel is 95.5% opaque.

---

## 3. What was built

### 3a. Film-faithful Gargantua — `src/shell/CosmicCanvas.jsx` (rewritten shader)

One procedural quad, still zero textures/video. The tells that make a space
background read as "fake" were removed and the geometry that makes the film's hole
recognisable was added:

- **near edge-on disc** (vertical squash `ky = 0.090`) — a thin sweeping band, not a
  fat donut;
- **lensed far side** bending up *over* the shadow, with a fainter counterpart
  beneath (`arch` / `arch2`) — the single most recognisable Gargantua signature;
- **doppler beaming kept subtle** (≤1.35×, film-accurate) so the disc stays golden;
- **razor-thin photon ring** hugging the shadow + an Einstein-ring bloom;
- **truly black shadow** (~2.6× horizon, per Luminet), with a depth split so the
  *near* half of the disc crosses in front of it (this replaced a hard y-cut that
  drew a visible seam straight across the black disc);
- **temperature ramp** white-hot inner edge → amber → deep ember, and **no purple**;
- **star lensing** — background stars are dragged tangentially near the hole, with
  cubed magnitudes (many faint, few bright) and per-layer parallax drift;
- **restrained grade** — desaturated dust-laned Milky Way, fine grain **stepped at
  ~12fps** (a per-frame hash reads as video noise; DNGR's point was no flicker),
  gentle vignette, ACES-style shoulder.

The brain-working pulse now **flares the inner disc and tightens the photon ring**
instead of enlarging cartoon moons. Public contract unchanged: `.cosmic-canvas`,
`data-testid="cosmic-canvas"`, `data-cosmic-fallback`, `u_res/u_time/u_pulse`.

### 3b. A real reading system — `src/styles/simple.css` (new, loads last)

Scoped to `.mb-shell`, so Advanced rooms, the studio and foundation pages are
untouched:

- **contrast ramp** redefined for the dark shell (nothing load-bearing below 4.5:1);
- **type**: body 16.5px / 1.72, headers 26px, UI 14.5px, meta ≥12.5px (was 10.5px);
- **centred 820px reading column** for stream, head and composer;
- **panel at 95.5% opacity** + 22px blur, stronger scrim — the composite under the
  text is now ~0.04 luminance;
- bigger focus chips, tool rows with a status-coloured left rule, legible thinking
  blocks, AG-UI cards, receipts, and a composer with a 16.5px field and a **cobalt**
  primary action (the light theme's forest green fought the AI accent);
- **empty state as a real greeting** — 40px serif, 16.5px body, suggestion **cards**
  in a grid (was 12.5px pills);
- the AutothinK **workbench** panel and the S5 plan-graph small print lifted to the
  same scale.

Two layout defects fixed on the way: a flex `min-height:auto` overflow that pushed
the **composer below the fold**, and a bare `<button>` in the top bar inheriting the
browser's light-grey fill.

### 3c. Cohesive chrome — `src/shell/MasterBrainShell.jsx`

The shell sets `html[data-shell-mode="simple"]` while mounted, so the shared top bar
follows it into dark cosmic glass **only** in Simple mode; Advanced keeps the light
editorial chrome it was designed for.

---

## 4. Verification

| Check | Result |
|---|---|
| `npm run build` | **0 errors** (1.22s; chunk-size warning only, pre-existing) |
| `verify-shell-v3.cjs` (the Simple-mode gate: focus chips, entitlements, cards, handover, fork, workbench, plan graph, artifacts, runs) | **28 passed / 0 failed** — unchanged |
| Measured on the live signed-in surface | stream width **820px**; assistant body **16.5px/28.4**; composer field **16.5px**; heading **26px**; tool rows **14.5px**; chips **14.5px**; panel `rgba(9,12,17,0.957)` |
| Console errors after sign-in | **none** |
| Screenshots | `northstar-os-ui/screenshots/v42-home.png`, `v42-empty.png`, `v42-background.png` |

The V3 gate passing unchanged is the important result: every pinned `data-testid`
(`mb-focus-*`, `chat-cards`, `chat-card-action`, `chat-pause/paused/resume`,
`chat-fork`, `chat-workbench*`, `wb-tab-*`, `wb-artifacts`, `wb-runs`,
`wb-run-cancel`, `svg.ipg-svg`) and every class it asserts still behaves.

---

## 5. Scope boundary — stated honestly

- **Restyled:** the Northstar OS Simple shell (Master Brain), all chat surfaces it
  hosts, the AutothinK **focus + workbench panel inside it**, and the shared top bar
  while Simple is mounted.
- **Not touched:** the standalone AutothinK server UI at `autothink/ui/index.html`
  (913 lines, served on :8100 by the AutothinK process, which is **not running**
  here). It is a separate surface from the in-app AutothinK view and was left
  exactly as it was. Say the word and it gets the same system next.
- **Advanced rooms / studio / foundation pages:** deliberately left on the existing
  editorial light design — the brief was Simple mode.
- **REA capture:** "use REA to help with pieces other chat AIs do right" was
  honoured through the bounded research survey plus the two corrections above. A
  *live* REA capture of the Figma gallery still needs an **operator window with
  Chrome Connect** (read-only, operator-gated — by design the harness never drives
  the browser itself). The corpus is ready for it: `POST /api/corpus/embed`.

---

## 6. Files

| File | Change |
|---|---|
| `northstar-os-ui/src/shell/CosmicCanvas.jsx` | shader rewritten (film-faithful Gargantua) |
| `northstar-os-ui/src/shell/MasterBrainShell.jsx` | `html[data-shell-mode="simple"]` while mounted |
| `northstar-os-ui/src/styles/simple.css` | **new** — the Simple-mode reading system |
| `northstar-os-ui/src/main.jsx` | loads `simple.css` last |
| `northstar-os-ui/_shot-simple.cjs` | scratch visual probe (fails closed without `NS_TEST_PASSWORD`) |
| `northstar-os-ui/screenshots/v42-*.png` | visual evidence |
