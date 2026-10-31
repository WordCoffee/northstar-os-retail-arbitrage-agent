# Galactic Command Deck — architecture (Phase 2)

## Goal

Give Northstar OS a visual layer that shows what the multi-agent system is doing
without inventing telemetry: node topology, KV-cache pressure, the unified event
stream, and tactile micro-animations, all local-only and reduced-motion safe.

## Component hierarchy

```
GalacticDeck (page, /galactic)
├─ CelestialBackdrop            CSS starfield; no GPU shader on this surface
└─ CommandDeck                  owns the snapshot, event bus, selection, pulse
   ├─ StatusRail                node lamps from snapshot.nodes
   ├─ NodeTopology              SVG; orchestrator centre, workers on a ring
   ├─ SelectedNodePanel         role/model/context/KV + Focus/Pulse/Replay
   ├─ KVCacheHeatmap            one row per lane; unknown usage is hatched
   └─ EventStream               filterable ordered bus view
```

Pure logic lives in `src/lib/galacticState.js` (no React, no DOM, no network):

| export | responsibility |
|---|---|
| `createEventBus` | ordered ring buffer, subscribe/publish/replay, broken-subscriber isolation |
| `layoutTopology` | deterministic 0..1000 × 0..600 layout; orchestrator at centre |
| `topologyLinks` | only links whose endpoints exist; coordinates from the layout |
| `heatmapCells` | per-lane cells; known ratio or explicit `unknown` |
| `pulseFor` | severity → CSS pulse class/level |
| `summarizeEvents` | ok/info/warn/error counts |
| `formatContext` | 17.4k / 1.2M / — |

## Data flow

```
shared/model-suite.json ─┐
lane_policy.describe()  ─┼─> GET /api/v1/galactic/state ──> CommandDeck (poll fallback)
hardware_guard.snapshot()┤                                      │
/health probes           ┘                                      ├─> snapshot state
                                                                └─> bus.publish("telemetry.snapshot")
GET /api/v1/galactic/events (SSE) ──> EventSource ──> same snapshot/bus path
UI actions ──> bus.publish("deck.focus" / "deck.pulse") ──> EventStream + pulse layer
```

The preferred transport is a Server-Sent Events stream (`/api/v1/galactic/events`):
one `snapshot` event every 8 s. `CommandDeck` subscribes with `EventSource` and
only falls back to the 8 s poll when EventSource is unavailable or the stream
errors. Both paths publish into the same in-browser bus, so the event audit view
has one source of truth.

The backend endpoint is read-only and fast: model-suite read, lane-policy
describe, a 0.7 s health probe for Ty (`:8080`) and FLUX (`:8188`), an optional
0.8 s `/slots` read for Ty's real `n_past`, and `hardware_guard.snapshot()`.
`context_used` is `null` when `/slots` does not answer; the heatmap renders that
lane as **unknown**, never as 0%.

The bus is the in-browser event bus. The SSE snapshot and UI events share the
same ordered stream, so the audit view has one source of truth. The stream is
snapshot-level; token-level agent events can be added to the same bus later
without changing the components.

## Interaction and accessibility

- Nodes are SVG `<g role="button" tabIndex=0>` with Enter/Space activation and
  `aria-pressed`; the selected node gets a gold ring.
- The status row is `role="status" aria-live="polite"`; the event list is
  `aria-live="polite"`.
- Filters are buttons with `aria-pressed`; no hover-only controls.
- `prefers-reduced-motion: reduce` disables the scan, halo and transitions.
- The deck has no animation loop: pulse is a CSS keyframe on a keyed element,
  the cursor light is two CSS variables updated on pointer move.

## Performance budget

| concern | rule |
|---|---|
| GPU | no WebGL on this page; `CelestialBackdrop` is CSS layers |
| polling | 8 s snapshot; no per-token polling |
| event memory | ring buffer 240; UI keeps the last 80 |
| DOM | one SVG with 7 nodes; heatmap is 16 cells × lanes |
| build | Vite; new CSS is scoped under `.gx-` |

## Integration

- `App.jsx`: `import GalacticDeck`, `<Route path="/galactic" ...>`, and
  `SIMPLE_KEEP_ADVANCED` includes the route so Simple mode keeps the real page.
- `nav-config.js`: `Galactic Deck` under **Admin & Systems**, role
  operator/platform_admin.
- Backend: `GET /api/v1/galactic/state` in `main.py`, inserted with the Python
  AST engine (`agent_kernel.ast_edit.add_after`).
- JSX integration: `scripts/ast_edit_js.cjs` (Babel AST offsets + re-parse)
  because the Python `ast_edit` engine is Python-only by design. New component
  files are additive; the two existing JS files were changed only at AST-derived
  insertion points.

## Verification contract

1. `npm run test:ui` — 73 node tests, including 11 new pure-state tests.
2. `npm run test:contrast` — 11 WCAG AA pairs.
3. `npm run verify:galactic` — every new JSX/JS parses, route/nav/state/CSS
   contracts present, no `fetch` in the pure module.
4. `npm run build` — 0 errors.
5. `pytest Northstar_backend/test_galactic_state.py` — endpoint shape, real
   lanes, KV capacity, null-or-int usage, GPU block, and the first SSE frame.

## Known limits (next cycles)

- The SSE stream is snapshot-level, not token-level agent events.
- `/slots` is optional; Bojo context usage is not instrumented by Ollama's API.
- The deck does not yet render A+ modules or creative assets; it is the
  systems/agent view.
- A browser screenshot is not part of this cycle; component syntax, build and
  pure logic are verified, and the route is wired.
