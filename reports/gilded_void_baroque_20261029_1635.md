# Gilded Void — Baroque Hyperrealism Theme

**Date:** 2026-10-29 · **Branch:** `feature/chrome-connect-3.0` · **Commit:** `7330ab3a`
**Spec:** `reports/baroque_hyperrealism_spec_20261029_153346.md` (Tys work order `tys_f3d848058579`, done)

## Objective
Implement the "Gilded Void" Baroque Hyperrealism theme in `northstar-os-ui`: master
stylesheet, 5 manifest components, hover/focus/click-ripple interactivity, live
integration into the app layout, and `npm run build` with 0 errors.

## Delivered
| File | Role |
|---|---|
| `src/styles/baroque.css` | Master stylesheet: chiaroscuro gradients, gilded box shadows, keyframe animations, micro-surface filter properties (§b), texture data-URI custom properties, `prefers-reduced-motion` fallback |
| `src/components/baroque/baroque.js` | `LightSourceTracker` (rAF-throttled `--mouse-x/y` + document-level `--light-source-x/y`), `RippleEffect`, `useBaroqueInteractive`, `useBaroqueModal` (panel stays mounted through the ~850 ms closing curtain) |
| `src/components/baroque/BaroqueBackdrop.jsx` | Component 3: fixed ambient backdrop (z-index -1) + inline SVG filter bank (`BaroqueFilters`) |
| `src/components/baroque/ControlFrame.jsx` | Component 1: gilded control frame |
| `src/components/baroque/StatusBanner.jsx` | Component 2: status banner |
| `src/components/baroque/ActionTrigger.jsx` | Component 4: CTA with hover/focus/ripple states |
| `src/components/baroque/NotificationModal.jsx` | Component 5: modal with sibling-overlay curtain (not panel `::before` — panel transform would create a containing block and shrink a fixed pseudo-element) |
| `src/pages/internal/GildedVoid.jsx` | Showcase page at `/baroque` mounting backdrop, frame, banner, CTA, modal, light-source readout |
| `src/App.jsx` | `/baroque` route + `SIMPLE_KEEP_ADVANCED` entry (`/^\/baroque(\/|$)/`) |
| `src/data/nav-config.js` | "Gilded Void" nav section (roles operator/platform_admin, status Internal) |
| `src/main.jsx` | `baroque.css` import after `celestial.css` |
| `verify-gilded-void.cjs` | Playwright verification harness |

## Design constraints honored
- Pure CSS + inline SVG textures/filters — **no WebGL**, so it never competes with
  ComfyUI/Ollama for GPU.
- Coexists with the celestial system (`celestial.css` v6); `.main-content:has(.baroque-stage)
  { background: transparent; }` lets the fixed backdrop (z-index -1) show through.
- Hover states use `animation: none` (not `animation-play-state: paused`); `dust-drift`
  uses `alternate`; ripple uses explicit 14 px size + `-7px` margin.
- Reduced-motion fallback included.

## Verification evidence
**Harness `node verify-gilded-void.cjs` → PASS:**
```json
{
  "backdrop": 1, "shaft": 1, "filters": 1, "frame": 1, "banner": 1, "cta": 2,
  "title": "The Gilded Void",
  "curtain": 1, "modalTitle": "Theatrical Notification", "dimmed": 1,
  "modalAfter": 0, "dimmedAfter": 0,
  "readout": "Light source: 48.5% , 46.3%Stage pulses: 0",
  "errors": []
}
PASS
```
- All 5 manifest components render; modal opens (curtain + dimmed backdrop) and
  closes cleanly (both removed after close); light-source tracking live (readout
  updates with cursor position).
- Screenshots: `C:\Users\T2Hol\AppData\Local\Temp\opencode\gilded-void-stage.png`
  (589,401 B) and `gilded-void-modal.png` (611,469 B).

**Build:** `npm run build` → 174 modules transformed, **0 errors** (only pre-existing
dynamic-import/chunk-size warnings).

## Root cause of the render failure (pre-existing, not baroque)
The `/baroque` page initially bounced into a `/sign-in` ↔ `/home` Navigate loop with
403s on `/me`, `/environment`, `/preview/active`. Diagnosis:
1. Frontend dev shim sends `X-User-Id: demo-t2` + `X-Org-Id: org-t2`.
2. Backend `get_context` → `_resolve_org_and_role` → 403
   `cross_organization_access_denied` because `demo-t2` had no active membership
   visible to the running backend.
3. `seed_dev_shim.py` confirmed the active membership exists in
   `Northstar_backend/data/foundation.db` (`membership=existing`).
4. **Root cause:** `main.py` builds state with
   `FoundationState.build(os.environ.get("FOUNDATION_DB_PATH") or None)`; with no
   `FOUNDATION_DB_PATH`, `FoundationDB(None)` creates a **tempfile DB**
   (`tempfile.mkstemp`), so the backend read an empty store, not the persistent one.
5. **Fix:** restarted the backend with
   `FOUNDATION_DB_PATH=C:\...\Northstar_backend\data\foundation.db`
   (+ `ENVIRONMENT=development`). `/me` then returned 200 with
   `active_organization_id: org-t2`, `role: operator`, full permission set.
   Page rendered at `/ui/baroque` with 0 errors.

Note: the Navigate loop itself is a pre-existing app bug that occurs whenever the
session bootstrap fails in LOCAL_DEV; it is not caused by the baroque changes
(frontend-only).

## Cleanup
- `debug-baroque.cjs` deleted.
- Dev server (port 8101) stopped.
- Backend left running on `127.0.0.1:8000` with `FOUNDATION_DB_PATH` pinned.
- Local commit only — **no push** (branch `feature/chrome-connect-3.0` is
  non-protected; push not required for this task).
- Pre-commit leak scan: 0 leaks found.

## Status
**DONE.** Theme is live at `/baroque` in the app shell, verified end-to-end,
committed as `7330ab3a`.
