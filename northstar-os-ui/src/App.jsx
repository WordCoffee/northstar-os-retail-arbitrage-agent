import { useState } from 'react'
import { useNavigate, useLocation, BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CommandPalette from './components/CommandPalette.jsx'
import { NAV_GROUPS, canUseRole } from './data/nav-config.js'
import { fromBackendRole } from './data/roles.js'
import SuiteRail from './components/SuiteRail.jsx'
import TopNav from './components/TopNav.jsx'
import MobileBottomNav from './components/MobileBottomNav.jsx'
import VisionRing from './components/VisionRing.jsx'
import { SessionProvider, useSession } from './foundation/session.jsx'
import { LOCAL_DEV } from './foundation/dev.js'
import { TOAST_PROVIDER, useToast } from './components/ToastContext.jsx'
import { ModeProvider, useMode } from './context/ModeContext.jsx'
import { ShellProvider, useShell } from './shell/ShellContext.jsx'
import MasterBrainShell from './shell/MasterBrainShell.jsx'

import CommandCenter from './pages/internal/CommandCenter.jsx'
import ProductFinder from './pages/internal/ProductFinder.jsx'
import DesignStudio from './pages/internal/DesignStudio.jsx'
import WorkbenchShell from './shell/WorkbenchShell.jsx'
import { WorkspaceProvider } from './shell/WorkspaceTabs.jsx'
import GoldenGooseDesk from './pages/internal/GoldenGoose.jsx'
import ListingGuardian from './pages/internal/ListingGuardian.jsx'
import KeywordTracker from './pages/internal/KeywordTracker.jsx'
import CompetitorMonitor from './pages/internal/CompetitorMonitor.jsx'
import ListingForge from './pages/internal/ListingForge.jsx'
import AdPilot from './pages/internal/AdPilot.jsx'
import SocialPulse from './pages/internal/SocialPulse.jsx'
import ProfitabilityDashboard from './pages/internal/ProfitabilityDashboard.jsx'
import CommerceOps from './pages/internal/CommerceOps.jsx'
import Monitoring from './pages/internal/Monitoring.jsx'
import ChromeConnect from './pages/internal/ChromeConnect.jsx'
import AutothinK from './pages/internal/AutothinK.jsx'
import SpreadsheetLab from './pages/internal/SpreadsheetLab.jsx'
import MemoryBank from './pages/internal/MemoryBank.jsx'
import SharedDataLayer from './pages/internal/SharedDataLayer.jsx'
import ProviderAdapters from './pages/internal/ProviderAdapters.jsx'
import MasterBrain from './pages/internal/MasterBrain.jsx'
import PackifyDesign from './pages/internal/PackifyDesign.jsx'
import Improvement from './pages/internal/Improvement.jsx'
import GildedVoid from './pages/internal/GildedVoid.jsx'
import CustomerWorkspace from './pages/customer/Workspace.jsx'
import BetaOpsOverview from './pages/admin/Overview.jsx'
import OrgsList, { OrgDetail } from './pages/admin/OrgsList.jsx'
import InviteCreate, { InviteDetail } from './pages/admin/InviteCreate.jsx'
import Cohorts, { SupportOps, ReportsExports, AuditNotes, LifecycleModal, EligibilityChecklist } from './pages/admin/Cohorts.jsx'
import InternalAdmin from './pages/internal/Admin.jsx'
import CustomerSetup from './pages/customer/Setup.jsx'
import CustomerDocuments from './pages/customer/Documents.jsx'
import CustomerPlan from './pages/customer/PlanUsage.jsx'
import CustomerSupport, { TicketDetail as CustomerTicketDetail } from './pages/customer/Support.jsx'
import CustomerAccount from './pages/customer/AccountStatus.jsx'
import SignIn from './pages/public/SignIn.jsx'
import Recovery from './pages/public/Recovery.jsx'
import BetaLanding from './pages/public/BetaLanding.jsx'
import BetaInviteAccept from './pages/public/BetaInviteAccept.jsx'
import CustomerLegal from './pages/customer/Legal.jsx'
import AccountSuspended from './pages/customer/Suspended.jsx'
import AccountDowngraded from './pages/customer/Downgraded.jsx'
import CustomerReaccept from './pages/customer/Reaccept.jsx'
import NotFound from './pages/NotFound.jsx'
import GalacticDeck from './pages/internal/GalacticDeck.jsx'

// The session carries a BACKEND role (organization_owner, operator,
// internal_platform_admin...). The shell's checks below compare against the UI
// display vocabulary, so the value has to be translated first. Comparing the raw
// backend role matched nothing, which silently redirected every platform admin
// away from /beta-ops and /admin — see data/roles.js.
function currentRole(session) {
  if (!session.authenticated) return 'invitee'
  return (
    fromBackendRole(session.role) ||
    (session.permissions?.includes('platform_admin') ? 'platform_admin' : 'operator')
  )
}

// The pre-merge rooms carried their sub-view in ?view=. The merged route keeps
// it, so a deep link like /creative-studio?view=briefs must land on
// /design-studio?section=projects&view=briefs. A bare <Navigate> drops the
// query and silently resets the sub-view (found while embedding the merged
// studio), so the redirect carries it through.
function LegacyStudioRedirect({ section }) {
  const location = useLocation()
  const incoming = new URLSearchParams(location.search)
  const next = new URLSearchParams()
  next.set('section', section)
  const view = incoming.get('view')
  if (view) next.set('view', view)
  return <Navigate to={`/design-studio?${next.toString()}`} replace />
}

// Paths reachable without a session (public entry surfaces).
const PUBLIC_PATHS = ['/sign-in', '/recovery', '/beta', '/beta/accept', '/legal']

function GuardedRoutes({ role, authenticated, loaded }) {
  const location = useLocation()
  const path = location.pathname
  const isPublic = PUBLIC_PATHS.some(p => path === p || path.startsWith(p + '/'))
  // Wait for the session to resolve before enforcing the auth gate, otherwise a
  // dev-session user is briefly treated as signed-out and bounced to /sign-in
  // (which also drops the deep-link query string).
  if (!loaded) return null
  // Dev-only: LOCAL_DEV skips sign-in — /ui/sign-in redirects to /home after
  // SessionProvider bootstraps the demo session (X-User-Id headers).
  if (LOCAL_DEV && path === '/sign-in') {
    return <Navigate to="/home" replace />
  }
  // Internal (non-public) paths require authentication (F4).
  if (!authenticated && !isPublic) {
    return <Navigate to="/sign-in" replace />
  }
  const adminOnly = path === '/beta-ops' || path.startsWith('/beta-ops/') || path === '/admin'
  if (adminOnly && role !== 'platform_admin') {
    return <Navigate to="/home" replace />
  }
  return (
    <Routes>
      <Route path="/home" element={<CommandCenter />} />
      <Route path="/product-finder" element={<ProductFinder />} />
      <Route path="/product-finder/:id" element={<ProductFinder />} />
      <Route path="/design-studio/*" element={<DesignStudio />} />
      <Route path="/workbench" element={<WorkspaceProvider><WorkbenchShell /></WorkspaceProvider>} />
      <Route path="/product-designer" element={<LegacyStudioRedirect section="3d-scene" />} />
<Route path="/packify-design" element={<PackifyDesign />} />
      <Route path="/creative-studio" element={<LegacyStudioRedirect section="projects" />} />
      <Route path="/golden-goose" element={<GoldenGooseDesk />} />
      <Route path="/golden-goose/:id" element={<GoldenGooseDesk />} />
      <Route path="/listings" element={<ListingGuardian />} />
      <Route path="/keyword-tracker" element={<KeywordTracker />} />
      <Route path="/competitor-monitor" element={<CompetitorMonitor />} />
      <Route path="/listingforge" element={<ListingForge />} />
      <Route path="/adpilot" element={<AdPilot />} />
      <Route path="/socialpulse" element={<SocialPulse />} />
      <Route path="/profitability" element={<ProfitabilityDashboard />} />
      <Route path="/spreadsheet-lab" element={<SpreadsheetLab />} />
      <Route path="/commerce-ops" element={<CommerceOps />} />
      <Route path="/commerce-ops/:id" element={<CommerceOps />} />
      <Route path="/monitoring" element={<Monitoring />} />
<Route path="/chromeconnect" element={<ChromeConnect />} />
      <Route path="/autothink" element={<AutothinK />} />
      <Route path="/memory-bank" element={<MemoryBank />} />
      <Route path="/shared-data" element={<SharedDataLayer />} />
      <Route path="/provider-adapters" element={<ProviderAdapters />} />
      <Route path="/master-brain" element={<MasterBrain />} />
      <Route path="/improvement" element={<Improvement />} />
      <Route path="/galactic" element={<GalacticDeck />} />
      <Route path="/baroque" element={<GildedVoid />} />
      <Route path="/customer-workspace" element={<CustomerWorkspace />} />
      <Route path="/beta-ops" element={<BetaOpsOverview />} />
      <Route path="/beta-ops/orgs" element={<OrgsList />} />
      <Route path="/beta-ops/orgs/:id" element={<OrgDetail />} />
      <Route path="/beta-ops/invites" element={<InviteCreate />} />
      <Route path="/beta-ops/invites/:id" element={<InviteDetail />} />
      <Route path="/beta-ops/cohorts" element={<Cohorts />} />
      <Route path="/beta-ops/support" element={<SupportOps />} />
      <Route path="/beta-ops/reports" element={<ReportsExports />} />
      <Route path="/beta-ops/audit" element={<AuditNotes />} />
      <Route path="/beta-ops/lifecycle" element={<LifecycleModal />} />
      <Route path="/beta-ops/eligibility" element={<EligibilityChecklist />} />
      <Route path="/admin" element={<InternalAdmin />} />
      <Route path="/setup" element={<CustomerSetup />} />
      <Route path="/documents" element={<CustomerDocuments />} />
      <Route path="/plan" element={<CustomerPlan />} />
      <Route path="/support" element={<CustomerSupport />} />
      <Route path="/support/:id" element={<CustomerTicketDetail />} />
      <Route path="/account" element={<CustomerAccount />} />
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/recovery" element={<Recovery />} />
      <Route path="/beta" element={<BetaLanding />} />
      <Route path="/beta/accept" element={<BetaInviteAccept />} />
      <Route path="/legal" element={<CustomerLegal />} />
      <Route path="/suspended" element={<AccountSuspended />} />
      <Route path="/downgraded" element={<AccountDowngraded />} />
      <Route path="/reaccept" element={<CustomerReaccept />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

const MOBILE_ACTIVE = [
  { path: '/home', tab: 'home' },
  { path: '/product-finder', tab: 'sourcescout' },
  { path: '/golden-goose', tab: 'goose' },
  { path: '/profitability', tab: 'profitability' },
]

// In Northstar (the default view) these surfaces keep their real pages: account/legal/admin
// surfaces are not rooms, and the public entry points must never be replaced
// by the chat shell. Everything else becomes a focus inside the shell.
const SIMPLE_KEEP_ADVANCED = [
  /^\/beta-ops(\/|$)/, /^\/admin(\/|$)/, /^\/account(\/|$)/, /^\/plan(\/|$)/,
  /^\/support(\/|$)/, /^\/documents(\/|$)/, /^\/setup(\/|$)/, /^\/legal(\/|$)/,
  /^\/sign-in(\/|$)/, /^\/recovery(\/|$)/, /^\/beta(\/|$)/, /^\/suspended(\/|$)/,
  /^\/downgraded(\/|$)/, /^\/reaccept(\/|$)/,
  // The Gilded Void is a visual-system surface, not a room — it keeps its
  // real page in Northstar like the account/legal/admin surfaces above.
  /^\/baroque(\/|$)/,

  // The Design Studio is a tool workspace with its own sections (dielines,
  // packaging, A+ modules, the asset dashboard), not a chat focus. Replacing it
  // with the chat shell made every creative lane unreachable on the free tier,
  // where advanced_view is false — found by the dashboard e2e test.
  /^\/design-studio(\/|$)/,

  // The workbench is the shell itself: Bojo docked, services as tabs.
  /^\/workbench(\/|$)/,

  // The Improvement room carries the live Tys Assistant panel (queue, lanes,
  // task progress, memory). Replacing it with chat in Northstar hid the
  // operator's own automation state.
  /^\/improvement(\/|$)/,

  new RegExp("^/galactic(/|$)"),
]

function ModeGate({ children }) {
  const shell = useShell()
  // null while the shell context is still loading — the gate is enforced the
  // moment the real answer lands, never against an unknown.
  const advancedAllowed = shell.ready ? shell.advancedAllowed : null
  return <ModeProvider advancedAllowed={advancedAllowed}>{children}</ModeProvider>
}

// The Northstar view replaces the internal rooms, so it must carry the SAME auth
// gate GuardedRoutes enforces — a signed-out visitor hitting /golden-goose is
// redirected to sign-in, never shown the shell.
function SimpleShellRoutes({ role, authenticated, loaded }) {
  const location = useLocation()
  const path = location.pathname
  const isPublic = PUBLIC_PATHS.some(p => path === p || path.startsWith(p + '/'))
  if (!loaded) return null
  if (LOCAL_DEV && path === '/sign-in') {
    return <Navigate to="/home" replace />
  }
  if (!authenticated && !isPublic) {
    return <Navigate to="/sign-in" replace />
  }
  const adminOnly = path === '/beta-ops' || path.startsWith('/beta-ops/') || path === '/admin'
  if (adminOnly && role !== 'platform_admin') {
    return <Navigate to="/home" replace />
  }
  return <MasterBrainShell />
}

function Shell() {
  const session = useSession()
  const { toast } = useToast()
  const { mode } = useMode()
  const navigate = useNavigate()
  const location = useLocation()
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [toolsOpen, setToolsOpen] = useState(false)

  const role = currentRole(session)
  const authenticated = !!session.authenticated
  const loaded = !!session.loaded
  const path = location.pathname
  const mobileTab = MOBILE_ACTIVE.find(m => path === m.path || path.startsWith(m.path + '/'))
  const mobileActive = toolsOpen ? 'tools' : (mobileTab ? mobileTab.tab : '')
  // V3: Northstar is the main view; Advanced view is the room shell (tier-gated).
  const simpleMode = mode !== 'advanced'
  const keepAdvanced = SIMPLE_KEEP_ADVANCED.some(re => re.test(path))

  return (
    <div className={`app ${simpleMode ? 'shell-simple' : 'shell-advanced'}`}>
      {session.ownerTestMode && (
        <div
          className="owner-test-mode-banner"
          data-testid="owner-test-mode-banner"
          role="status"
          // zIndex 10 keeps this ABOVE the fixed .cosmic-canvas (position:fixed,
          // z-index:0). A static banner paints BELOW a positioned sibling, so the
          // warning div was in the DOM, correctly coloured and 100% covered by the
          // shader — elementFromPoint at its centre returned CANVAS.cosmic-canvas.
          // 10 sits above the canvas and below the sticky .top-nav (z-index:50).
          style={{ position: 'relative', zIndex: 10, background: '#5a3d12', color: '#fff', textAlign: 'center', padding: '4px 12px', fontSize: 13, letterSpacing: 0.3 }}
        >
          {session.ownerTestModeBanner || 'OWNER TEST MODE — bypasses are audited.'}
        </div>
      )}
      {(LOCAL_DEV || session.authMethod === 'dev_shim') && (
        <div data-testid="dev-banner" role="status"
          // Same paint-order fix as the owner-test banner above: `.cosmic-canvas`
          // is position:fixed/z-index:0, so a static banner is painted underneath
          // it. Measured 2026-10-28: the banner occupied (0,0,1760x33) with
          // background rgb(180,67,47) and elementFromPoint at its centre still
          // returned CANVAS.cosmic-canvas — present in the DOM, invisible on screen.
          style={{ position: 'relative', zIndex: 10, background: '#b4432f', color: '#fff', textAlign: 'center', padding: '6px 12px', fontSize: 14, fontWeight: 700, letterSpacing: 0.5 }}>
          DEV: AUTH DISABLED — local loopback only
        </div>
      )}
      <div className="app-scale">
      <TopNav
        role={role}
        paletteOpen={paletteOpen}
        setPaletteOpen={setPaletteOpen}
      />
      <div className="body-layout">
        {!simpleMode && <SuiteRail onNavigate={() => setToolsOpen(false)} />}
        <main className={`main-content ${simpleMode && !keepAdvanced ? 'main-content-simple' : ''}`}>
          <h1 style={{ position: 'absolute', width: 1, height: 1, padding: 0, margin: -1, overflow: 'hidden', clip: 'rect(0,0,0,0)', whiteSpace: 'nowrap', border: 0 }}>Northstar OS</h1>
          {session.suspended
            ? <AccountSuspended />
            : simpleMode && !keepAdvanced
              ? <SimpleShellRoutes role={role} authenticated={authenticated} loaded={loaded} />
              : <GuardedRoutes role={role} authenticated={authenticated} loaded={loaded} />}
        </main>
      </div>
      <MobileBottomNav active={mobileActive} onToolsClick={() => setToolsOpen(true)} />
      </div>
      {toolsOpen && (
        <div className="tools-sheet-overlay" onClick={() => setToolsOpen(false)}>
          <div className="tools-sheet" onClick={e => e.stopPropagation()}>
            <div className="tools-sheet-header">
              <span className="tools-sheet-title">Tools</span>
              <button onClick={() => setToolsOpen(false)} className="tools-sheet-close" aria-label="Close tools">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </div>
            <div className="tools-sheet-content">
              {NAV_GROUPS.filter(g => g.sections.some(s => canUseRole(s, role))).map(g => (
                <div key={g.id} className="tools-sheet-group">
                  <div className="tools-sheet-group-label">{g.label}</div>
                  {g.sections.filter(s => canUseRole(s, role)).map(s => (
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
      {paletteOpen && (
        <CommandPalette onClose={() => setPaletteOpen(false)} />
      )}
      <ToastContainer />
      <VisionRing />
    </div>
  )
}

function ToastContainer() {
  const { toasts } = useToast()
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast-item toast-${t.tone}`}>{t.msg}</div>
      ))}
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter basename="/ui">
      <SessionProvider>
        <TOAST_PROVIDER>
          <ShellProvider>
            <ModeGate>
              <Shell />
            </ModeGate>
          </ShellProvider>
        </TOAST_PROVIDER>
      </SessionProvider>
    </BrowserRouter>
  )
}