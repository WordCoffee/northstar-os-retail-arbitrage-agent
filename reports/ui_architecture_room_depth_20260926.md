# UI Architecture Correction Pass — Room Depth Implementation

**Date:** 2026-09-26
**Scope:** Implement the approved execution priorities from the structural audit — service-local navigation, role protection, removal of dashboard repetition, truth/sample-data discipline, wired actions, cleanup, Customer Workspace refactor.

## What shipped

### Service-local navigation (RoomTabs)
- New `RoomTabs` component (tabs driven by `?view=` search param → deep-linkable, e.g. `/profitability?view=scenario`).
- Applied to **15 rooms** — every internal service room plus Customer Workspace. Each room falls back to its primary tab; `:id` routes drive detail views (`/product-finder/:id`, `/golden-goose/:id`, `/commerce-ops/:id`).

### Authorization + role visibility
- `GuardedRoutes` in App.jsx: `/beta-ops*` and `/admin` redirect to `/home` for non-`platform_admin`.
- Tools sheet role-filtered via `canUseRole(section, role)`; SuiteRail uses the same filter; mobile active state synced from the route (`MOBILE_ACTIVE` map).

### Removed dashboard repetition (10 flat rooms → distinct structures)
Each of the 10 previously cloned rooms now has a distinct purpose and subview set:
| Room | Tabs |
|---|---|
| Listing Guardian | Alerts / Tracked Entities / Guardian Rules |
| Keyword Tracker | Rankings / Tracked Terms / Reports |
| Competitor Monitor | Landscape / Price Changes / Watchlist |
| SocialPulse | Content Calendar / Campaigns / Performance |
| Creative Studio | Library / Templates / Asset Health |
| Memory Bank | Topics / Recent Entries / Revision & Unlearn |
| Shared Data Layer | Sources / Readiness / Provenance |
| Provider Adapters | Adapters / Health / Configuration |
| Master Brain | Sessions / Decision Flow / Reasoning / Control |
| Monitoring | Alerts / Health / Sync |

### Truth / sample-data discipline
- `DataNotice` component with tones: sample, cached, concept, internal, assumption, unknown.
- Every room carries a truth banner. Unverified figures are labeled UNKNOWN / UNAVAILABLE / NOT CALCULATED / ASSUMPTION / CACHED. No fabricated seller counts, buy box, sales, fees, or purchase authorization.

### Wired primary actions
- SourceScout: Search / Saved Sets / Coverage / Send to Commerce Ops / Open Golden Goose.
- Golden Goose: Open SourceScout / Send to Commerce Ops.
- ListingForge: Create Listing → editor; Templates.
- AdPilot: Create Campaign → planner.
- Profitability: Export Report.
- Commerce Ops: New Workflow; Open → `/commerce-ops/:id`.
- AutothinK: New Research Run → Composer.
- Customer Workspace: entitled services launch real rooms; View Plan → /plan; Support → /support.

### Cleanup
- Deleted 5 dead shell components: SideNav, Sidebar, Dock, RightRail, Header (zero imports confirmed).
- Dropped the nested metric-grid wrapper (MetricTiles renders own grid) and the dead `simple`/local-Table props.
- Restored customer routes (/setup, /documents, /plan, /support, /account) and public routes (/sign-in, /recovery, /beta) in App.jsx.

## Verification
- `npm run build` → 0 errors (81 modules, 723ms).
- 26 fresh screenshots captured on preview :8104 → `northstar-os-ui/screenshots/` (desktop rooms + subview variants + mobile SourceScout + mobile Tools sheet).
- Single console error: expected `/api` 500 (FastAPI :8000 not running) — not a UI defect.

## Files touched
- New: `src/components/RoomTabs.jsx`
- Rewritten: `src/App.jsx`, `src/components/Shared.jsx` (MetricTiles/DataNotice), `RouteGuard.jsx`, `SuiteRail.jsx`, `MobileBottomNav.jsx`, `src/data/nav-config.js`
- Rewritten rooms: ProductFinder, GoldenGoose, ListingForge, AdPilot, ProfitabilityDashboard, CommerceOps, AutothinK, ListingGuardian, KeywordTracker, CompetitorMonitor, SocialPulse, CreativeStudio, MemoryBank, SharedDataLayer, ProviderAdapters, MasterBrain, Monitoring, customer/Workspace
- Deleted: SideNav, Sidebar, Dock, RightRail, Header
- Updated: `src/styles/app.css` (room-tabs, metric-tiles, DataNotice, room-toolbar), `take-screenshots.cjs`

## Next
Operator visual review under a working VL model (Ling 3.0 Flash VL) using the 6-request / 2-screenshot template; apply approved corrections afterward.