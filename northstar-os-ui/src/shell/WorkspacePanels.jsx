// The page behind each workspace tab.
//
// Tabs have to stay MOUNTED when another tab is showing — that is the whole
// point of a tab bar: scroll position, half-typed form input and already-loaded
// data survive a switch. The shell therefore renders each open tab's page
// itself, from this one map, instead of letting the shared `<Outlet/>` swap
// pages out.
//
// The map is keyed by service id and is pinned to `tabRoutes.js` by
// `tabRoutes.test.js`: adding a tab route without a panel (or a panel without a
// route) fails the unit test rather than rendering an empty tab.
//
// Each panel is rendered through `<Routes location={tab path}>` with the tab's
// own location provided above it, so a hidden tab keeps ITS URL — `useParams`,
// `useLocation` and `useSearchParams` inside a background tab do not silently
// start reporting the tab in front.

import { lazy } from 'react'
import { Route, Routes, UNSAFE_LocationContext } from 'react-router-dom'
import { TAB_ROUTE_PATTERNS } from './tabRoutes.js'
import WorkspaceFrame from '../workspaces/WorkspaceFrame.jsx'

// Lazy so a tab strip with five open workspaces does not pay for five pages on
// first paint. Same modules App.jsx routes to; nothing new is loaded.
export const TAB_PANELS = {
  'design-studio': lazy(() => import('../pages/internal/DesignStudio.jsx')),
  'product-pictures': lazy(() => import('../pages/internal/ProductPictures.jsx')),
  'product-finder': lazy(() => import('../pages/internal/ProductFinder.jsx')),
  'golden-goose': lazy(() => import('../pages/internal/GoldenGoose.jsx')),
  listings: lazy(() => import('../pages/internal/ListingGuardian.jsx')),
  listingforge: lazy(() => import('../pages/internal/ListingForge.jsx')),
  adpilot: lazy(() => import('../pages/internal/AdPilot.jsx')),
  socialpulse: lazy(() => import('../pages/internal/SocialPulse.jsx')),
  profitability: lazy(() => import('../pages/internal/ProfitabilityDashboard.jsx')),
  autothink: lazy(() => import('../pages/internal/AutothinK.jsx')),
  'keyword-tracker': lazy(() => import('../pages/internal/KeywordTracker.jsx')),
  'competitor-monitor': lazy(() => import('../pages/internal/CompetitorMonitor.jsx')),
}

function pinnedLocation(tab) {
  return {
    pathname: tab.path,
    search: tab.search || '',
    hash: '',
    state: null,
    // A stable key: pages that key effects on `location.key` must not see the
    // tab re-created every time the shell re-renders.
    key: `tab-${tab.id}`,
  }
}

/**
 * One mounted workspace. The panel is not keyed by path: navigating inside a
 * tab (list -> detail) reuses the mounted page, exactly like a browser tab.
 */
export default function WorkspacePanel({ tab }) {
  const Panel = TAB_PANELS[tab.id]
  if (!Panel) return null
  const location = pinnedLocation(tab)
  const patterns = TAB_ROUTE_PATTERNS[tab.id] || []
  return (
    <UNSAFE_LocationContext.Provider value={{ location, navigationType: 'POP' }}>
      {/* The workspace frame reads the spec for this service. A service with no
          spec gets its page unwrapped — the frame is chrome for a workspace the
          file can argue for, not for every room. */}
      <WorkspaceFrame serviceId={tab.id}>
        <Routes location={location}>
          {patterns.map((pattern) => (
            <Route key={pattern} path={pattern} element={<Panel />} />
          ))}
          {/* Safety net: a route variant App.jsx adds before this map is updated
              still renders the workspace instead of a blank tab. */}
          <Route path="*" element={<Panel />} />
        </Routes>
      </WorkspaceFrame>
    </UNSAFE_LocationContext.Provider>
  )
}
