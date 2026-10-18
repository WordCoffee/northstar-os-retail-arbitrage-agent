# V3 S5 — AutothinK premium surface (UI): the workbench panel

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, harness green, local commit.

## What this closes

The S5 backend (plan graph · artifact browser · run panel) is now reachable from
the Simple shell. A single **Workbench** control in the chat head opens a drawer
with three honest views of the current session: **Plan · Artifacts · Runs**.

## Design rules honoured

- **Honest states.** No plan / no artifacts / no runs each say so plainly. A
  missing asset file is marked (`file missing`). A run that cannot be stopped is
  not given a pretend cancel.
- **The plan is a chain on purpose.** The tool loop is bounded and sequential, so
  the functional view draws the true shape — `prompt → step 0 → … → answer` — and
  carries the backend caveats. The immersive node-link graph is a **deep-visual**
  upgrade left for a stronger visual model (see below).
- **Same transport rules** as the rest of the suite (same-origin, cookie auth,
  CSRF); no new dependencies.

## Pieces

| Piece | Where | What |
|---|---|---|
| Client | `src/chat/api.js` | `plan / artifacts / runs / cancelRun`. |
| Panel | `src/chat/WorkbenchPanel.jsx` | Plan chain, artifact grid (preview + download), run list with cancel; proof the design system holds (`wb-*` in `styles/chat.css`). |
| Mount | `src/chat/ChatSurface.jsx` | `⌥ Workbench` toggle in the chat head; panel shows for any focus, labelled "AutothinK workbench" under the autothink focus. |
| Styles | `src/styles/chat.css` | Paper/pine/bone surfaces, `--spark` as the only AI-state accent; responsive (bottom sheet < 900px). |

## Evidence

```
cd northstar-os-ui && npm run build                                  → ✓ built, 0 errors
node verify-shell-v3.cjs  (HARNESS_BASE_URL=http://127.0.0.1:8101/ui/) → 28 passed, 0 failed
```

Scenario F (new) verifies: the **Workbench** control is offered; the drawer
opens; the plan view renders the reconstructed chain and its tool steps; the
artifact browser lists session artifacts; the run panel lists runs with a cancel
control. Scenarios A–E continue to pass (28 total, was 22).

## Deep-visual note (model switch)

The plan graph is currently a **functional** linear chain — correct, accessible,
on-brand, and honest. The plan's *deep-visual* treatment (an animated node-link
graph woven into the cosmic shell) is best done in a dedicated visual pass with a
stronger visual model. This is the point in the roadmap to switch for that work;
everything before and after it is functional and needs no switch.

## Honest limits / next

- The run panel surfaces chat turns; per-tool run rows are the next refinement.
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
