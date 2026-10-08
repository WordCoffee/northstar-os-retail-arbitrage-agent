import { useState } from 'react'
import { useNavigate, useLocation, BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CommandPalette from './components/CommandPalette.jsx'
import { NAV_GROUPS, canUseRole } from './data/nav-config.js'
import SuiteRail from './components/SuiteRail.jsx'
import TopNav from './components/TopNav.jsx'
import MobileBottomNav from './components/MobileBottomNav.jsx'
import { SessionProvider, useSession } from './foundation/session.jsx'
import { TOAST_PROVIDER, useToast } from './components/ToastContext.jsx'

import CommandCenter from './pages/internal/CommandCenter.jsx'
import ProductFinder from './pages/internal/ProductFinder.jsx'
import GoldenGooseDesk from './pages/internal/GoldenGoose.jsx'
import ListingGuardian from './pages/internal/ListingGuardian.jsx'
import KeywordTracker from './pages/internal/KeywordTracker.jsx'
import CompetitorMonitor from './pages/internal/CompetitorMonitor.jsx'
import ListingForge from './pages/internal/ListingForge.jsx'
import AdPilot from './pages/internal/AdPilot.jsx'
import SocialPulse from './pages/internal/SocialPulse.jsx'
import CreativeStudio from './pages/internal/CreativeStudio.jsx'
import ProfitabilityDashboard from './pages/internal/ProfitabilityDashboard.jsx'
import CommerceOps from './pages/internal/CommerceOps.jsx'
import Monitoring from './pages/internal/Monitoring.jsx'
import AutothinK from './pages/internal/AutothinK.jsx'
import SpreadsheetLab from './pages/internal/SpreadsheetLab.jsx'
import MemoryBank from './pages/internal/MemoryBank.jsx'
import SharedDataLayer from './pages/internal/SharedDataLayer.jsx'
import ProviderAdapters from './pages/internal/ProviderAdapters.jsx'
import MasterBrain from './pages/internal/MasterBrain.jsx'
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

function currentRole(session) {
  return session.authenticated
    ? (session.role || (session.permissions?.includes('platform_admin') ? 'platform_admin' : 'operator'))
    : 'invitee'
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
      <Route path="/golden-goose" element={<GoldenGooseDesk />} />
      <Route path="/golden-goose/:id" element={<GoldenGooseDesk />} />
      <Route path="/listings" element={<ListingGuardian />} />
      <Route path="/keyword-tracker" element={<KeywordTracker />} />
      <Route path="/competitor-monitor" element={<CompetitorMonitor />} />
      <Route path="/listingforge" element={<ListingForge />} />
      <Route path="/adpilot" element={<AdPilot />} />
      <Route path="/socialpulse" element={<SocialPulse />} />
      <Route path="/creative-studio" element={<CreativeStudio />} />
      <Route path="/profitability" element={<ProfitabilityDashboard />} />
      <Route path="/spreadsheet-lab" element={<SpreadsheetLab />} />
      <Route path="/commerce-ops" element={<CommerceOps />} />
      <Route path="/commerce-ops/:id" element={<CommerceOps />} />
      <Route path="/monitoring" element={<Monitoring />} />
      <Route path="/autothink" element={<AutothinK />} />
      <Route path="/memory-bank" element={<MemoryBank />} />
      <Route path="/shared-data" element={<SharedDataLayer />} />
      <Route path="/provider-adapters" element={<ProviderAdapters />} />
      <Route path="/master-brain" element={<MasterBrain />} />
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

function Shell() {
  const session = useSession()
  const { toast } = useToast()
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

  return (
    <div className="app">
      {session.ownerTestMode && (
        <div
          className="owner-test-mode-banner"
          data-testid="owner-test-mode-banner"
          role="status"
          style={{ background: '#5a3d12', color: '#fff', textAlign: 'center', padding: '4px 12px', fontSize: 13, letterSpacing: 0.3 }}
        >
          {session.ownerTestModeBanner || 'OWNER TEST MODE — bypasses are audited.'}
        </div>
      )}
      <TopNav
        role={role}
        paletteOpen={paletteOpen}
        setPaletteOpen={setPaletteOpen}
      />
      <div className="body-layout">
        <SuiteRail onNavigate={() => setToolsOpen(false)} />
        <main className="main-content">
          {session.suspended
            ? <AccountSuspended />
            : <GuardedRoutes role={role} authenticated={authenticated} loaded={loaded} />}
        </main>
      </div>
      <MobileBottomNav active={mobileActive} onToolsClick={() => setToolsOpen(true)} />
      {toolsOpen && (
        <div className="tools-sheet-overlay" onClick={() => setToolsOpen(false)}>
          <div className="tools-sheet" onClick={e => e.stopPropagation()}>
            <div className="tools-sheet-header">
              <span className="tools-sheet-title">Tools</span>
              <button onClick={() => setToolsOpen(false)} className="tools-sheet-close">
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
          <Shell />
        </TOAST_PROVIDER>
      </SessionProvider>
    </BrowserRouter>
  )
}