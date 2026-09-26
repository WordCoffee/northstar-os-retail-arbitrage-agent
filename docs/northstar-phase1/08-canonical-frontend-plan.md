# 08 — Canonical Frontend Plan

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). Specification only — migration NOT performed.

## 1. Decision (owner decision `00` §4)

- **React/Vite SPA (`northstar-os-ui`) = target public-facing product.**
- **FastAPI = API backend.**
- Analyst's Desk = labeled fixture/design reference until migrated.
- Single-file workbench = experimental/internal surface pending evidence.
- Legacy HTML = legacy.
- AutothinK UI = candidate for integration into the React app.

## 2. Migration mapping

| Analyst's Desk component | Decision |
|---|---|
| Ribbon header (search, brain switch, theme, account) | Rebuild in React shell (exists as `Header.jsx`) |
| Drawer nav (collapsible groups) | Rebuild (exists as `Sidebar.jsx`) |
| Work surface 12 views | Rebuild as React pages (already scaffolded in `northstar-os-ui/src/pages/*`) |
| Bulletin board (Pinned) | Rebuild as collapsible drawer (see `10`; Phase 0 R: persistent rail must not waste space) |
| Command palette (Ctrl+K) | Rebuild (React command palette component) |
| Onboarding modal | Rebuild via help/tour module |
| Paperclip assistant | Rebuild or deprecate (design decision) |
| Service data fixtures (`demo-data.js`) | **Replace with real API calls** to canonical backend — fixtures never treated as production data |
| Gates/authorization display | Rebuild against real gate/approval API (Phase 0 R: presentation-only badges) |

| Workbench component | Decision |
|---|---|
| Scout data-view (scanner) | Adopt logic → React Prospector |
| Calculator/profit/risk/cycle/portfolio views | Adopt formulas → React pages (single ACoS/margin formula per Phase 0 R13/R14) |
| GG seam | Adopt → React Golden Goose |
| Hidden v2 workspaces | Fold into React services |

| AutothinK UI | Decision |
|---|---|
| Galaxy canvas, composer, quick-ask, achievements | Keep as reference; rebuild composer as React brain surface; achievements as tour/activity |
| Chiptune audio | Deprecate (gaming aesthetic out of scope for professional OS) |

## 3. Routing

- react-router HashRouter (current) → consider BrowserRouter behind FastAPI SPA fallback once served; Phase 1B keeps HashRouter for simplicity behind static serving.
- Route table mirrors the 11 services + Account + nested sub-routes (e.g., `/prospector`, `/prospector/:productId`).

## 4. Build and deploy

| Option | Phase 1B recommendation |
|---|---|
| Serve compiled `dist/` via FastAPI static mount | PREFERRED for single-origin simplicity (mount `northstar-os-ui/dist` at `/app` with SPA fallback) |
| Dedicated static host (Cloudflare Pages / CDN) | Alternative; requires CORS + API base config |
| Dev proxy | Vite proxy to :8000 retained for dev (exists) |

## 5. Auth + API base + environment + feature flags

- **Auth:** access token (short) + refresh; token stored securely (httpOnly cookie or memory + refresh rotation); `/api/v1/auth/*`.
- **API base:** single `VITE_API_BASE` (default `/api` same-origin); all calls via a typed API client (extend `src/services/api.js`).
- **Environment selection:** explicit app-level environment context (sandbox/production) from auth/session — surfaced in a mode indicator; never a free-form toggle (see `05`).
- **Feature flags:** `FEATURE_FLAG_*` from `/api/v1/status`; flags gate UI features client-side but are always enforced server-side.

## 6. Auth guard + error/loading boundaries

- Route guards per role/plan; `PermissionDenied` state per service spec.
- Global error boundary; per-view loading/empty/error/stale states (design system `09`).

## 7. What this resolves

- Phase 0 R20 (four surfaces) and R6 (SPA untested, not served) → single canonical surface, served by FastAPI, with test framework added in Phase 1B.
