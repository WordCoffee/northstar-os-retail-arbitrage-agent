# V3 S5 — Immersive plan graph (deep-visual pass)

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, harness green, local commit.

## What this closes

The S5 AutothinK workbench (fork · plan/artifact/run backends · Plan/Artifacts/Runs drawer) had a **functional linear chain** for the plan view. The plan's deep-visual upgrade — an animated node-link constellation woven into the cosmic shell — is now built.

## Design (cosmic shell aesthetic, Interstellar-inspired)

The plan graph renders as a `ImmersivePlanGraph` component inside the workbench drawer:

- **Background:** deep-space radial gradient (pine-ink dark) with an animated CSS twinkling starfield, echoing the WebGL `CosmicCanvas` palette (`#0a0a22` deep space, purple nebula wash).
- **Nodes:** glowing orbs — forest green = prompt, cobalt spark (`--spark`, the sole AI accent) = AI tool step, pine = answer — with a status dot (ok/running/error) and a pulse ring on the active step.
- **Edges:** self-drawing lines (`stroke-dashoffset` animation) connecting prompt → step → … → answer.
- **Sequential reveal:** nodes fade/scale in one at a time, mirroring how the bounded tool loop actually ran.
- **Typography:** DM Sans labels, serif-free clean look; title styling consistent with the shell.
- **Accessibility / honesty:** `prefers-reduced-motion` renders a static chain; no edges or dependencies are invented (the graph is the same honest linear chain from `build_plan`); SVG + CSS only, dependency-free.

## Pieces

| Piece | Where | What |
|---|---|---|
| Component | `src/chat/ImmersivePlanGraph.jsx` | Animated node-link graph: nodes/edges, glow filters, sequential reveal, pulse, empty state. |
| Styles | `src/styles/chat.css` `.ipg-*` | Dark-glass panel, radial space bg, animated starfield, reduced-motion fallback. |
| Mount | `src/chat/WorkbenchPanel.jsx` | Plan tab renders `ImmersivePlanGraph` (replaced the linear chain). |
| Harness | `verify-shell-v3.cjs` scenario F | Graph renders (SVG + nodes) and shows tool steps from the stubbed `/api/chat/sessions/{sid}/plan`. |

## Evidence

```
cd northstar-os-ui && npm run build                                  → ✓ built, 0 errors
node verify-shell-v3.cjs  (HARNESS_BASE_URL=http://127.0.0.1:8101/ui/) → 28 passed, 0 failed
```

Scenario F verifies: the **Workbench** control; the drawer opens; the **immersive plan graph renders** (SVG node-link constellation); the graph shows the tool steps; the artifact browser lists session artifacts; the run panel lists runs with cancel. All 28 scenarios pass (was 22 before the visual pass).

## Honest limits / next

- The graph is a **visual treatment** of the existing honest plan — no new data, no fabricated edges.
- Remaining S7: §5.4 **embeddings drift** (`qwen3-embedding:0.6b` + sqlite-vec) — needs that model lane.
- Item 8 (operator-window REA captures, Packify first) needs you present with live Chrome Connect.
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
