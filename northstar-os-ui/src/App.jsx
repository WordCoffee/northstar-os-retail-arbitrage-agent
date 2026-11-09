import { lazy } from 'react'
import { useLocation, BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { fromBackendRole } from './data/roles.js'
import VisionRing from './components/VisionRing.jsx'
import { SessionProvider, useSession } from './foundation/session.jsx'
import { LOCAL_DEV } from './foundation/dev.js'
import { TOAST_PROVIDER, useToast } from './components/ToastContext.jsx'
import { ModeProvider, useMode } from './context/ModeContext.jsx'
import { ShellProvider, useShell } from './shell/ShellContext.jsx'
import MasterBrainShell from './shell/MasterBrainShell.jsx'
import { WorkspaceProvider } from './shell/WorkspaceTabs.jsx'
import ShellLayout from './shell/ShellLayout.jsx'
import DevBanner from './shell/DevBanner.jsx'
import { isPublicPath } from './shell/shellRoutes.js'

// Route entry points are code-split: every page (and therefore the studio engine
// behind the creative rooms) is fetched on first navigation instead of being
// paid for on initial load. `lazyNamed` handles the modules that export a named
// component alongside their default (admin Lists/Details, Support ticket detail).
const lazyNamed = (loader, name) => lazy(() => loader().then(m => ({ default: m[name] })))

const CommandCenter = lazy(() => import('./pages/internal/CommandCenter.jsx'))
const ProductFinder = lazy(() => import('./pages/internal/ProductFinder.jsx'))
const DesignStudio = lazy(() => import('./pages/internal/DesignStudio.jsx'))
const WorkbenchShell = lazy(() => import('./shell/WorkbenchShell.jsx'))
const GoldenGooseDesk = lazy(() => import('./pages/internal/GoldenGoose.jsx'))
const ListingGuardian = lazy(() => import('./pages/internal/ListingGuardian.jsx'))
const KeywordTracker = lazy(() => import('./pages/internal/KeywordTracker.jsx'))
const CompetitorMonitor = lazy(() => import('./pages/internal/CompetitorMonitor.jsx'))
const ListingForge = lazy(() => import('./pages/internal/ListingForge.jsx'))
const AdPilot = lazy(() => import('./pages/internal/AdPilot.jsx'))
const SocialPulse = lazy(() => import('./pages/internal/SocialPulse.jsx'))
const ProfitabilityDashboard = lazy(() => import('./pages/internal/ProfitabilityDashboard.jsx'))
const CommerceOps = lazy(() => import('./pages/internal/CommerceOps.jsx'))
const Monitoring = lazy(() => import('./pages/internal/Monitoring.jsx'))
const ChromeConnect = lazy(() => import('./pages/internal/ChromeConnect.jsx'))
const AutothinK = lazy(() => import('./pages/internal/AutothinK.jsx'))
const SpreadsheetLab = lazy(() => import('./pages/internal/SpreadsheetLab.jsx'))
const MemoryBank = lazy(() => import('./pages/internal/MemoryBank.jsx'))
const SharedDataLayer = lazy(() => import('./pages/internal/SharedDataLayer.jsx'))
const ProviderAdapters = lazy(() => import('./pages/internal/ProviderAdapters.jsx'))
const MasterBrain = lazy(() => import('./pages/internal/MasterBrain.jsx'))
const PackifyDesign = lazy(() => import('./pages/internal/PackifyDesign.jsx'))
const Improvement = lazy(() => import('./pages/internal/Improvement.jsx'))
const GildedVoid = lazy(() => import('./pages/internal/GildedVoid.jsx'))
const CustomerWorkspace = lazy(() => import('./pages/customer/Workspace.jsx'))
const BetaOpsOverview = lazy(() => import('./pages/admin/Overview.jsx'))
const OrgsList = lazy(() => import('./pages/admin/OrgsList.jsx'))
const OrgDetail = lazyNamed(() => import('./pages/admin/OrgsList.jsx'), 'OrgDetail')
const InviteCreate = lazy(() => import('./pages/admin/InviteCreate.jsx'))
const InviteDetail = lazyNamed(() => import('./pages/admin/InviteCreate.jsx'), 'InviteDetail')
const Cohorts = lazy(() => import('./pages/admin/Cohorts.jsx'))
const SupportOps = lazyNamed(() => import('./pages/admin/Cohorts.jsx'), 'SupportOps')
const ReportsExports = lazyNamed(() => import('./pages/admin/Cohorts.jsx'), 'ReportsExports')
const AuditNotes = lazyNamed(() => import('./pages/admin/Cohorts.jsx'), 'AuditNotes')
const LifecycleModal = lazyNamed(() => import('./pages/admin/Cohorts.jsx'), 'LifecycleModal')
const EligibilityChecklist = lazyNamed(() => import('./pages/admin/Cohorts.jsx'), 'EligibilityChecklist')
const InternalAdmin = lazy(() => import('./pages/internal/Admin.jsx'))
const CustomerSetup = lazy(() => import('./pages/customer/Setup.jsx'))
const CustomerDocuments = lazy(() => import('./pages/customer/Documents.jsx'))
const CustomerPlan = lazy(() => import('./pages/customer/PlanUsage.jsx'))
const CustomerSupport = lazy(() => import('./pages/customer/Support.jsx'))
const CustomerTicketDetail = lazyNamed(() => import('./pages/customer/Support.jsx'), 'TicketDetail')
const CustomerAccount = lazy(() => import('./pages/customer/AccountStatus.jsx'))
const SignIn = lazy(() => import('./pages/public/SignIn.jsx'))
const Recovery = lazy(() => import('./pages/public/Recovery.jsx'))
const BetaLanding = lazy(() => import('./pages/public/BetaLanding.jsx'))
const BetaInviteAccept = lazy(() => import('./pages/public/BetaInviteAccept.jsx'))
const CustomerLegal = lazy(() => import('./pages/customer/Legal.jsx'))
const AccountSuspended = lazy(() => import('./pages/customer/Suspended.jsx'))
const AccountDowngraded = lazy(() => import('./pages/customer/Downgraded.jsx'))
const CustomerReaccept = lazy(() => import('./pages/customer/Reaccept.jsx'))
const NotFound = lazy(() => import('./pages/NotFound.jsx'))
const GalacticDeck = lazy(() => import('./pages/internal/GalacticDeck.jsx'))

// Catalogue rooms that predate the router shell. Their pages exist; only the
// <Route> entries were missing, so /hub, /ledger and friends fell through to
// NotFound (or, in Northstar, to the chat shell). The adapter supplies the
// toast/navigate props those pages were written against.
const HubRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'HubRoom')
const LedgerRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'LedgerRoom')
const ProspectorRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'ProspectorRoom')
const LegacyGoldenGooseRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'LegacyGoldenGooseRoom')
const OfferChiselRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'OfferChiselRoom')
const TownCrierRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'TownCrierRoom')
const AuctioneerRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'AuctioneerRoom')
const TheWatchRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'TheWatchRoom')
const RankLedgerRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'RankLedgerRoom')
const RivalBoardRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'RivalBoardRoom')
const FoundationStatusRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'FoundationStatusRoom')
const JobsRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'JobsRoom')
const KeywordsRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'KeywordsRoom')
const BetaSignupRoom = lazyNamed(() => import('./pages/roomAdapters.jsx'), 'BetaSignupRoom')

// An entitlement gate must render a real page, not bounce to the chat shell.
// Redirecting /beta-ops to /home made a role gate indistinguishable from the
// shell defect measured 2026-11-08 ("renders the home shell"). This keeps the
// gate (no data, no controls) while giving the route its own, honest surface.
function AccessDenied({ needed }) {
  return (
    <div className="page" data-testid="route-access-denied" data-required-role={needed}>
      <div className="page-head">
        <div className="title-block">
          <h1 className="text-glow">Access restricted</h1>
          <p>
            This room requires the <strong>{needed}</strong> role. Your current session
            does not hold it, so no data or controls are shown here.
          </p>
        </div>
      </div>
    </div>
  )
}

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

// Public entry surfaces live in src/shell/shellRoutes.js: five of them
// (/beta, /beta/accept, /sign-in, /recovery, /legal) are reachable without a
// session AND render outside the shell chrome; /beta-signup is reachable
// without a session but is a catalogue room, so it renders inside the shell.

function GuardedRoutes({ role, authenticated, loaded }) {
  const location = useLocation()
  const path = location.pathname
  const isPublic = isPublicPath(path)
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
    // Still a shell route: the denial is the room's own page, inside the chrome.
    return (
      <ShellLayout role={role}>
        <AccessDenied needed="platform admin" />
      </ShellLayout>
    )
  }
  return (
    <Routes>
      {/* ONE layout route carries the chrome for every service route. A new
          route added as a child of this element cannot be missing the top nav,
          the side nav or the outlet — that is the point of the layout route. */}
      <Route element={<ShellLayout role={role} />}>
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

        {/* Catalogue rooms: the pages existed but had no <Route>, so the route
            silently fell through. Registered in data/serviceRegistry.js. */}
        <Route path="/hub" element={<HubRoom />} />
        <Route path="/ledger" element={<LedgerRoom />} />
        <Route path="/prospector" element={<ProspectorRoom />} />
        <Route path="/goldengoose" element={<LegacyGoldenGooseRoom />} />
        <Route path="/offerchisel" element={<OfferChiselRoom />} />
        <Route path="/towncrier" element={<TownCrierRoom />} />
        <Route path="/auctioneer" element={<AuctioneerRoom />} />
        <Route path="/thewatch" element={<TheWatchRoom />} />
        <Route path="/rankledger" element={<RankLedgerRoom />} />
        <Route path="/rivalboard" element={<RivalBoardRoom />} />
        <Route path="/foundation" element={<FoundationStatusRoom />} />
        <Route path="/jobs" element={<JobsRoom />} />
        <Route path="/keywords" element={<KeywordsRoom />} />
        <Route path="/beta-signup" element={<BetaSignupRoom />} />

        <Route path="/setup" element={<CustomerSetup />} />
        <Route path="/documents" element={<CustomerDocuments />} />
        <Route path="/plan" element={<CustomerPlan />} />
        <Route path="/support" element={<CustomerSupport />} />
        <Route path="/support/:id" element={<CustomerTicketDetail />} />
        <Route path="/account" element={<CustomerAccount />} />
        <Route path="/suspended" element={<AccountSuspended />} />
        <Route path="/downgraded" element={<AccountDowngraded />} />
        <Route path="/reaccept" element={<CustomerReaccept />} />
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* Outside the shell chrome on purpose (shellRoutes.js
          SHELL_EXEMPT_PATHS): the entry surfaces a signed-out visitor must reach
          without a top bar or rail. ShellLayout's exempt branch still renders
          the outlet container (so the page keeps its scroll frame) and the
          DevBanner is drawn above this switch, so the notice survives. */}
      <Route path="/sign-in" element={<ShellLayout role={role}><SignIn /></ShellLayout>} />
      <Route path="/recovery" element={<ShellLayout role={role}><Recovery /></ShellLayout>} />
      <Route path="/beta" element={<ShellLayout role={role}><BetaLanding /></ShellLayout>} />
      <Route path="/beta/accept" element={<ShellLayout role={role}><BetaInviteAccept /></ShellLayout>} />
      <Route path="/legal" element={<ShellLayout role={role}><CustomerLegal /></ShellLayout>} />
    </Routes>
  )
}

// Northstar is Bojo's home, not a replacement for every room.
//
// Until 2026-11-08 this was a hand-maintained allowlist (SIMPLE_KEEP_ADVANCED)
// of the paths that were allowed to render their own page in Northstar; every
// path not on it fell through to <MasterBrainShell/>. Measured with
// python -m tools.vision.ux_audit --run: 3 of 29 service routes rendered. The
// list only ever grew when someone remembered, so every room added afterwards
// (listings, socialpulse, the whole legacy catalogue) opened the chat shell
// instead of itself.
//
// The rule is inverted: only these chat-first paths keep the chat surface. Every
// other path renders the page its <Route> declares — so a new room cannot be
// swallowed by forgetting to add it here, and an unknown path gets the honest
// NotFound page rather than a chat surface that pretends to be it.
//
// The chrome does NOT change with the mode any more: the chat-first frame and
// every room both render inside <ShellLayout> (top nav + side nav + outlet).
const CHAT_FIRST_PATHS = [/^\/$/, /^\/home(\/|$)/]

function ModeGate({ children }) {
  const shell = useShell()
  // null while the shell context is still loading — the gate is enforced the
  // moment the real answer lands, never against an unknown.
  const advancedAllowed = shell.ready ? shell.advancedAllowed : null
  return <ModeProvider advancedAllowed={advancedAllowed}>{children}</ModeProvider>
}

// The Northstar view replaces the internal rooms, so it must carry the SAME auth
// gate GuardedRoutes enforces — a signed-out visitor hitting /golden-goose is
// redirected to sign-in, never shown the shell. The chat sits in the shell's
// outlet with the chat-first frame, so the top nav and side nav stay put.
function SimpleShellRoutes({ role, authenticated, loaded }) {
  const location = useLocation()
  const path = location.pathname
  const isPublic = isPublicPath(path)
  if (!loaded) return null
  if (LOCAL_DEV && path === '/sign-in') {
    return <Navigate to="/home" replace />
  }
  if (!authenticated && !isPublic) {
    return <Navigate to="/sign-in" replace />
  }
  const adminOnly = path === '/beta-ops' || path.startsWith('/beta-ops/') || path === '/admin'
  if (adminOnly && role !== 'platform_admin') {
    return (
      <ShellLayout role={role}>
        <AccessDenied needed="platform admin" />
      </ShellLayout>
    )
  }
  return (
    <ShellLayout role={role} mainClassName="main-content-simple">
      <MasterBrainShell />
    </ShellLayout>
  )
}

function Shell() {
  const session = useSession()
  const { mode } = useMode()
  const location = useLocation()

  const role = currentRole(session)
  const authenticated = !!session.authenticated
  const loaded = !!session.loaded
  const path = location.pathname
  // V3: Northstar is the main view; Advanced view is the room shell (tier-gated).
  const simpleMode = mode !== 'advanced'
  const chatFirst = CHAT_FIRST_PATHS.some(re => re.test(path))

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
      {/* Above the chrome, so it covers the routes that are deliberately outside
          the shell too (/sign-in, /beta, /recovery, /legal). */}
      <DevBanner authMethod={session.authMethod} />
      {session.suspended
        ? <ShellLayout role={role}><AccountSuspended /></ShellLayout>
        : simpleMode && chatFirst
          ? <SimpleShellRoutes role={role} authenticated={authenticated} loaded={loaded} />
          : <GuardedRoutes role={role} authenticated={authenticated} loaded={loaded} />}
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