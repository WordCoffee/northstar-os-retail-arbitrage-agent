# 11 — Frontend Foundation (implemented)

React/Vite shell additions under `northstar-os-ui/src/foundation/`. Additive; existing
service pages and the Analyst's Desk reference surface are untouched.

## Delivered

| Requirement | Component | Notes |
|---|---|---|
| Authentication boundary | `foundation/session.jsx` | SessionProvider loads `/me`; **dev shim** documented (real JWT = Phase 1C) |
| Organization context | `session.jsx` + `OrgSelector.jsx` | org list; selector when >1; dev role/env context |
| Environment indicator | `EnvBadge.jsx` | PRODUCTION / SANDBOX (+ PREVIEW) |
| Role-aware navigation | `Sidebar.jsx` + `services.js` `perm` | items hidden when permission absent |
| Audited preview indicator | `PreviewBanner.jsx` | persistent, non-dismissable, read-only |
| Responsive application layout | existing `body` grid + `foundation.css` | drawer collapses on mobile |
| Collapsible navigation | `Sidebar.jsx` | groups collapsible (existing) |
| Collapsible Pinned drawer | `PinnedDrawer.jsx` | off by default; replaced persistent right rail |
| Saved drawer preference | `PinnedDrawer.jsx` → UI-pref API | persisted per user |
| Command/help entry point | `CommandPalette.jsx` (Ctrl+K), `HelpTour.jsx` | tour registry + overlay |
| Global notifications | `Notifications.jsx` | surfaces foundation error count |
| Provenance/status primitives | `StatusPrimitives.jsx` | ProvenanceBadge, ConfidenceChip, LastUpdated |
| Loading/error/empty/stale/partial/denied states | `StatusPrimitives.jsx:StateMessage` | standard components |
| API client | `foundation/api.js` | typed wrapper over `/api/v1/foundation/*` |
| Feature flags | `foundation/flags.js` | client gating; server-enforced too |
| Route guards | `RouteGuard.jsx` | `/foundation` guarded by `request_refresh` |
| Internal foundation page | `pages/FoundationStatus.jsx` | consumes real providers/products/usage/approvals APIs with honest empty/error states |

## Verification

- `npm run build` → **67 modules, 0 errors** (228.46 kB JS / 71.07 kB gzip; 25.31 kB CSS).
- Browser load of `/#/foundation`: shell renders without crashing; the only console errors
  are the expected `404` for `/api/v1/foundation/*` because the **running** backend has not
  been restarted to pick up the additive mount (no deployment was performed). The shell's
  error state is shown honestly.

## Not done (deliberately)

- Service pages were NOT rebuilt (owner decision 9). They continue to use the existing
  backend endpoints.
- Analyst's Desk was NOT deleted (owner decision 9).
- No fake operational data was placed on any page.