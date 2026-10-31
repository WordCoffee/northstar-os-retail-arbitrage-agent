# Cycle 2 — Galactic UI & Immersive Experience Engine

- date: 2026-10-31
- commit: `511f3fd2`
- scope: Phase 2 visual layer, local-only, no Docker, AST-guided structural edits.

## Architecture delivered

Full hierarchy and data flow are documented in
`docs/GALACTIC_DECK_ARCHITECTURE.md`. Summary:

```
GalacticDeck (/galactic)
├─ CelestialBackdrop          CSS starfield, no WebGL on this surface
└─ CommandDeck                snapshot + event bus + selection + pulse
   ├─ StatusRail              node lamps
   ├─ NodeTopology            SVG, orchestrator centre, workers on a ring
   ├─ SelectedNodePanel       role/model/context/KV + Focus/Pulse/Replay
   ├─ KVCacheHeatmap          16 cells per lane; unknown usage is hatched
   └─ EventStream             filterable, aria-live ordered bus
```

Pure logic is in `src/lib/galacticState.js`: `createEventBus`,
`layoutTopology`, `topologyLinks`, `heatmapCells`, `pulseFor`,
`summarizeEvents`, `formatContext`. No React, DOM, network or timers in that
module, so the node test runner pins the behaviour.

## Built modules

| file | what it does |
|---|---|
| `src/lib/galacticState.js` | deterministic bus/layout/heatmap/pulse helpers |
| `src/lib/galacticState.test.js` | 11 node tests (ring buffer, broken subscriber, deterministic layout, unknown KV, severity, summary) |
| `src/galactic/CommandDeck.jsx` | 8 s telemetry poll, unified bus, status rail, selected-node panel, pulse layer |
| `src/galactic/NodeTopology.jsx` | keyboard-focusable SVG nodes, gold selection ring, link layer |
| `src/galactic/KVCacheHeatmap.jsx` | per-lane context cells; `unknown` is hatched, never 0% |
| `src/galactic/EventStream.jsx` | filter chips, timestamps, severity edges, replay |
| `src/galactic/galactic.css` | obsidian/nebula glass, grid, cursor light, scan pulse, reduced-motion |
| `src/pages/internal/GalacticDeck.jsx` | page mount with `CelestialBackdrop` |
| `Northstar_backend/main.py` | `GET /api/v1/galactic/state` |
| `northstar-os-ui/scripts/ast_edit_js.cjs` | Babel AST offset editor for the JSX/nav integration |
| `northstar-os-ui/scripts/verify-galactic-deck.cjs` | 28 static contract checks |

## Structural edits (AST, not text diffs)

- **Python:** `agent_kernel.ast_edit.add_after` inserted the new endpoint after
  `live_status` in `main.py`. The existing 4,000-line module kept every comment
  and formatting outside the insertion.
- **JSX/JS:** the Python engine refuses non-Python files by design, so
  `scripts/ast_edit_js.cjs` parses with `@babel/parser`, inserts at AST offsets,
  and re-parses the result. It added the `GalacticDeck` import, the
  `/galactic` route and the `SIMPLE_KEEP_ADVANCED` entry in `App.jsx`, plus the
  **Admin & Systems → Galactic Deck** item in `nav-config.js`.
- **New components are additive files**; no existing JSX component was
  rewritten.

## Backend telemetry

`GET /api/v1/galactic/state` returns:

- nodes for master, Ty, Bojo, FLUX 3, Chrome Connect, Memory Bank, AST engine;
- links for the deck's topology;
- KV rows with `context_total` from `shared/model-suite.json` (Ty 17,408;
  Bojo 8,192) and `context_used` only when llama-server `/slots` answers;
- `lane_policy.describe()` installed/missing lanes;
- `hardware_guard.snapshot()` GPU block;
- `telemetry: live|offline`.

A lane that is down is reported `idle`/`offline`; unknown usage is `null`. The
test asserts the shape, real capacities, null-or-int usage, and the GPU block.

## Verification

```
cd northstar-os-ui
npm run test:ui       # 73 passed, 0 failed
npm run test:contrast # 11/11 WCAG AA pairs
npm run verify:galactic # 28/28 static checks
npm run build         # ✓ built in 1.32 s, 0 errors
python -m pytest Northstar_backend/test_galactic_state.py -q  # 1 passed
```

`npm test` now chains all three UI checks. The build's only output is the
pre-existing chunk-size warning; no new error.

## Honest limits

- The bus is **poll + local events**, not a token-level SSE stream. The
  architecture leaves an SSE endpoint as the next cycle.
- `/slots` is optional; Bojo context usage is not exposed by Ollama, so that row
  stays hatched.
- No browser screenshot was produced; component syntax, build, pure logic and
  the static contract are verified. The route is wired.
- The Python AST engine is Python-only; the JSX edit uses the Babel AST
  counterpart and is explicitly validated by re-parse.
- No Amazon request, no paid provider call, no credential read.

## Next cycle (selected immediately)

**Cycle 3 — Unified event bus SSE + live stream contract.** Add
`GET /api/v1/galactic/events` (SSE) that emits a snapshot heartbeat and real
system events, subscribe from `CommandDeck` via `EventSource`, keep the poll as
a fallback, and verify reconnect/cleanup plus no duplicate event storms. HITL
Matrix remains blocked on AgentTeams/Matrix being absent.
