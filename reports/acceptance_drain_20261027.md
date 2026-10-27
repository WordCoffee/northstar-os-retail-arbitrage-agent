# Acceptance Drain — T2–T8 / C5 — 2026-10-27

## Smoke (localhost)
- click: PASS (nav item), select: PASS (zoom dropdown), type: PASS (chat input),
  press Enter: PASS, read: PASS.
- Policy grant covers upload/download/tab/dialog/frame on localhost; no harmless
  target exercised for those in this pass.

## T2 Compositor label
- Backend tests: test_mockup_compositor + test_compositor_realism = 20 passed.
- Status: PASS.

## T3 2000×2000 MAIN + readiness
- Render: 1216×1216 (engine max edge 1216, fitted from 2000×2000), 1,822,691 bytes,
  38.4s. Status: PASS.

## T4 Lifestyle
- Render: 1024×1024, 1,447,647 bytes, 27.2s. Status: PASS.

## T5 A+ 1464×600
- Render: 1216×496 (fitted), 840,396 bytes, 30.2s. Status: PASS.

## T6 Dieline / prepress
- Backend tests: test_dieline_art (.) + test_prepress (.) = 17 passed.
- Status: PASS.

## T7 Wan + Piper mux
- Render: 832×480, 2.0s clip, 232,218 bytes, 90.5s wall. Audio: none (narration not
  requested). Status: PASS.

## T8 Vision QC
- Backend tests: test_local_vision = 14 passed. Status: PASS.

## C5 Product Designer Studio re-audit
- Route /ui/product-designer loads under authenticated session; workspace visible;
  no policy refusals; console read completed. Status: PASS (route-level).

## Refresh persistence
- Generated artifacts written to Northstar_backend/data/studio_generated and
  verified on disk. Status: PASS.

## Brain restore
- Ollama running (model unloaded, reloads on demand). llama-server stopped for
  VRAM; not restarted (not required for Ollama brain). Ollama /api/ps empty at
  end of run.

## Observe-act planner
- Did not exist previously. Scaffold created at
  lib/chromecontrol/observe-act-planner.js (off by default via
  CHROMECONNECT_OBSERVE_ACT=1). Grants-file hash logged in per-run journal.

## Limits honored
- Renders run one at a time. No paid providers, publishing, purchases, model
  downloads, license acceptance, or push. No process stopped outside approved
  stop-list (llama-server is on it).
