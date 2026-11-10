// The shell chrome — one frame for every service route.
//
// Before this file, the chrome lived inline in App.jsx and only the ADVANCED
// view got the side rail (`{!simpleMode && <SuiteRail/>}`), so in the default
// Northstar view every room — Listings, Product Finder, the whole catalogue —
// rendered with a top bar and no navigation at all, and the rail was reachable
// only by switching view. The frame is now rendered BY ROUTE (a React Router
// layout route with a real <Outlet/>), so a new route cannot forget it: it is
// inside the layout by construction.
//
// What the shell owns:
//   • TopNav                     (top bar, search, quick create, account)
//   • WorkspaceTabBar            (ux-07: one tab per open service, see below)
//   • SuiteRail                  (side nav, grouped by role from nav-config)
//   • <main data-testid="workspace-outlet">  (the page keeps its own layout
//                                 and scroll container; the shell never
//                                 re-parents a room's content)
//   • MobileBottomNav + tools sheet + CommandPalette
//
// What it does NOT own: the page itself. The outlet is a slot — a room page
// still renders its own header, grids, panels and scrolling inside it.
//
// ux-07 — workspace tabs. An open workspace is kept MOUNTED (hidden, not
// unmounted) while another tab is showing, so scroll position, form input and
// already-loaded data survive the switch. The tab rules are pure and tested in
// tabRoutes.js; the strip is TabBar.jsx; the panels come from
// WorkspacePanels.jsx; the state hook is useWorkspaceTabs.js.
//
// A location that is not a workspace (the chat-first /home, admin, the
// customer rooms) renders through <Outlet/> as before and simply has no
// selected tab. Closing the LAST tab goes to /home — the documented rule in
// tabRoutes.closeTab, so the router is never left on a route whose tab is gone.
//
// Bojo: the shell publishes what it can actually see about the open tab
// (`data-tab-summary` on the shell frame, the same object on
// globalThis.__northstarWorkspaceTab, and a `northstar:workspace-tab` event).
// It deliberately does not invent page state it cannot read.
//
// ux-08 — the scene bed. The shell also owns the SCENE: `<SceneHost>` is
// mounted once, here, and pointed at the active service, so exactly one canvas
// exists per shell and switching tabs releases the previous scene instead of
// stacking a second one. The mode the engine settled on (`live` | `static` |
// `reduced`) is mirrored onto the frame as `data-scene-bed`, which is what the
// workspace veil in scene.css keys off. See sceneEngine.js for the lifecycle.
//
// Routes a signed-out visitor needs (see shellRoutes.js) are exempt: they render
// the outlet alone, with no top bar and no rail. They get no scene either.

import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import TopNav from '../components/TopNav.jsx'
import SuiteRail from '../components/SuiteRail.jsx'
import MobileBottomNav from '../components/MobileBottomNav.jsx'
import CommandPalette from '../components/CommandPalette.jsx'
import { NAV_GROUPS, canUseRole } from '../data/nav-config.js'
import { isShellExempt } from './shellRoutes.js'
import TabBar from './TabBar.jsx'
import WorkspacePanel from './WorkspacePanels.jsx'
import useWorkspaceTabs from './useWorkspaceTabs.js'
import SceneHost from './SceneHost.jsx'
import './tabs.css'

const MOBILE_ACTIVE = [
  { path: '/home', tab: 'home' },
  { path: '/product-finder', tab: 'sourcescout' },
  { path: '/golden-goose', tab: 'goose' },
  { path: '/profitability', tab: 'profitability' },
]

// Suspense boundary for the lazy route chunks. It sits INSIDE the shell so the
// top bar and rail stay painted while a page chunk loads. The app name is not
// the page heading (see App.jsx): it stays an sr-only paragraph.
export function ShellFallback() {
  return (
    <div className="route-loading" role="status" aria-live="polite"
      style={{ padding: 32, opacity: 0.55, fontSize: 14 }}>
      Loading…
    </div>
  )
}

const SR_ONLY = {
  position: 'absolute',
  width: 1,
  height: 1,
  padding: 0,
  margin: -1,
  overflow: 'hidden',
  clip: 'rect(0,0,0,0)',
  whiteSpace: 'nowrap',
  border: 0,
}

/**
 * @param {object} props
 * @param {string} props.role            UI display role (data/roles.js vocabulary)
 * @param {string} [props.mainClassName] extra class for <main> (chat-first frame)
 * @param {React.ReactNode} [props.children] explicit content; otherwise <Outlet/>
 */
export default function ShellLayout({ role = 'invitee', mainClassName = '', children = null }) {
  const navigate = useNavigate()
  const location = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)
  // Which mode the scene engine settled on. Published on the frame so the
  // workspace veil and a browser lane can both read it.
  const [sceneMode, setSceneMode] = useState('off')

  const {
    tabs: openTabs, activeId, activeTab, visited, mainRef, summary,
    activate: activateTab, close: closeTab,
  } = useWorkspaceTabs(location, navigate)
  const summaryJson = JSON.stringify(summary)

  // The shell -> Bojo contract. One object, three ways to read it: the DOM
  // attribute (a browser lane or a test can read it without a React handle),
  // the global (the chat surface can read it on the next turn), and the event
  // (a listener can react to a switch). It is only published when it changes.
  useEffect(() => {
    const detail = JSON.parse(summaryJson)
    globalThis.__northstarWorkspaceTab = detail
    try {
      document.dispatchEvent(new CustomEvent('northstar:workspace-tab', { detail }))
    } catch { /* CustomEvent unavailable */ }
  }, [summaryJson])

  const path = location.pathname
  const mobileTab = MOBILE_ACTIVE.find((m) => path === m.path || path.startsWith(m.path + '/'))
  const mobileActive = toolsOpen ? 'tools' : (mobileTab ? mobileTab.tab : '')

  const outlet = (
    <main
      ref={mainRef}
      tabIndex={0}
      data-testid="workspace-outlet"
      className={['main-content', mainClassName].filter(Boolean).join(' ')}
    >
      {/* The app name is not the page heading. This used to be an <h1>, which
          meant every route announced "Northstar OS" as its heading to a screen
          reader and the real page <h1> was the second one in the DOM. Measured
          by tests/e2e/ux_scorecard.spec.ts on 2026-11-05. */}
      <p className="sr-only" style={SR_ONLY}>Northstar OS</p>
      <Suspense fallback={<ShellFallback />}>
        {/* Open workspaces stay mounted; only the selected one is laid out.
            Non-workspace routes (and /home) render through the outlet. */}
        {openTabs.map((tab) => {
          const selected = tab.id === activeId
          return (
            <div
              key={tab.id}
              id={`wst-panel-${tab.id}`}
              role="tabpanel"
              aria-labelledby={`wst-tab-${tab.id}`}
              tabIndex={0}
              hidden={!selected}
              className="wst-panel"
              data-testid={`tab-panel-${tab.id}`}
              data-tab-path={tab.path}
            >
              {visited.has(tab.id) ? <WorkspacePanel tab={tab} /> : null}
            </div>
          )
        })}
        {!activeTab && (children || <Outlet />)}
      </Suspense>
    </main>
  )

  // Defensive: a route declared exempt must never render chrome even if it is
  // reached through the layout route by mistake.
  if (isShellExempt(path)) {
    return (
      <div className="app-scale" data-shell-chrome="exempt">
        {outlet}
      </div>
    )
  }

  return (
    <div
      className="app-scale"
      data-testid="shell-chrome"
      data-shell-chrome="full"
      data-active-tab={activeId || ''}
      data-active-tab-label={activeTab?.label || ''}
      data-tab-summary={summaryJson}
      data-scene-bed={sceneMode}
    >
      {/* One bed for the whole shell. Pointed at the active service, never at a
          page: a hidden tab keeps its DOM, not its animation loop. */}
      <SceneHost
        serviceId={activeId}
        pathname={path}
        onModeChange={setSceneMode}
      />
      <TopNav
        role={role}
        paletteOpen={paletteOpen}
        setPaletteOpen={setPaletteOpen}
      />
      <TabBar
        tabs={openTabs}
        activeId={activeId}
        onActivate={activateTab}
        onClose={closeTab}
      />
      <div className="body-layout">
        <SuiteRail onNavigate={() => setToolsOpen(false)} />
        {outlet}
      </div>
      <MobileBottomNav active={mobileActive} onToolsClick={() => setToolsOpen(true)} />
      {toolsOpen && (
        <div className="tools-sheet-overlay" onClick={() => setToolsOpen(false)}>
          <div className="tools-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="tools-sheet-header">
              <span className="tools-sheet-title">Tools</span>
              <button onClick={() => setToolsOpen(false)} className="tools-sheet-close" aria-label="Close tools">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="tools-sheet-content">
              {NAV_GROUPS.filter((g) => g.sections.some((s) => canUseRole(s, role))).map((g) => (
                <div key={g.id} className="tools-sheet-group">
                  <div className="tools-sheet-group-label">{g.label}</div>
                  {g.sections.filter((s) => canUseRole(s, role)).map((s) => (
                    <button
                      key={s.id}
                      className="tools-sheet-item"
                      onClick={() => { navigate(s.route); setToolsOpen(false) }}
                    >
                      {s.label}
                      {s.status && <span className={`pill pill-${s.statusTone || 'muted'}`} title={s.readinessTitle || ''}>{s.status}</span>}
                    </button>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
      {paletteOpen && <CommandPalette onClose={() => setPaletteOpen(false)} />}
    </div>
  )
}
