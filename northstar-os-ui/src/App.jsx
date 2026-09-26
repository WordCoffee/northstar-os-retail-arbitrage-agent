import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Header from './components/Header.jsx'
import Sidebar from './components/Sidebar.jsx'
import Dock from './components/Dock.jsx'
import Icon from './components/Icon.jsx'
import { PageHead } from './ui.jsx'

import Hub from './pages/Hub.jsx'
import Ledger from './pages/Ledger.jsx'
import Prospector from './pages/Prospector.jsx'
import GoldenGoose from './pages/GoldenGoose.jsx'
import OfferChisel from './pages/OfferChisel.jsx'
import TownCrier from './pages/TownCrier.jsx'
import Auctioneer from './pages/Auctioneer.jsx'
import Autothink from './pages/Autothink.jsx'
import TheWatch from './pages/TheWatch.jsx'
import RankLedger from './pages/RankLedger.jsx'
import RivalBoard from './pages/RivalBoard.jsx'
import Account from './pages/Account.jsx'

import { SessionProvider, useSession } from './foundation/session.jsx'
import EnvBadge from './foundation/components/EnvBadge.jsx'
import PreviewBanner from './foundation/components/PreviewBanner.jsx'
import OrgSelector from './foundation/components/OrgSelector.jsx'
import Notifications from './foundation/components/Notifications.jsx'
import PinnedDrawer from './foundation/components/PinnedDrawer.jsx'
import CommandPalette from './foundation/components/CommandPalette.jsx'
import RouteGuard from './foundation/components/RouteGuard.jsx'
import FoundationStatus from './foundation/pages/FoundationStatus.jsx'
import Jobs from './foundation/pages/Jobs.jsx'
import Keywords from './foundation/pages/Keywords.jsx'
import BetaTester from './foundation/pages/BetaTester.jsx'
import BetaOps from './foundation/pages/BetaOps.jsx'
import BetaSignup from './foundation/pages/BetaSignup.jsx'
import { useTour, TourOverlay } from './foundation/HelpTour.jsx'
import { routeToId } from './data/services.js'

function Shell() {
  const navigate = useNavigate()
  const location = useLocation()
  const session = useSession()

  const [theme, setTheme] = useState(() => localStorage.getItem('northstar-theme') || 'dark')
  const [toasts, setToasts] = useState([])
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [tourOpen, setTourOpen] = useState(false)
  const tour = useTour(routeToId(location.pathname) || 'hub')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('northstar-theme', theme)
  }, [theme])

  // First-entry tour: show once per service unless dismissed.
  useEffect(() => {
    if (!tour.available || tourOpen) return
    tour.isDone().then((done) => { if (!done) setTourOpen(true) })
  }, [location.pathname])

  const finishTour = () => {
    setTourOpen(false)
    tour.markDone()
  }

  const toast = (msg, tone = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev.slice(-3), { id, msg, tone }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200)
  }

  return session.suspended ? (
    <div className="app">
      <div className="page" style={{ maxWidth: 560, margin: '60px auto' }}>
        <PageHead title="Account suspended"
          sub="Your organization cannot use product features right now" />
        <div className="stack">
          <div className="alert warn">
            <div className="k">Status</div>
            <div style={{ flex: 1 }}>{session.suspensionState || 'suspended'}</div>
          </div>
          <p className="text-low">
            {session.suspensionMessage || 'Feature use is currently blocked for this account.'}
          </p>
          <p className="text-low">
            To resolve this, contact the beta operator through the support channel
            you were given at onboarding.
          </p>
          <a className="btn" href="/api/v1/foundation/legal/filesets/support_contact" target="_blank"
             rel="noreferrer">Support &amp; contact</a>
        </div>
      </div>
    </div>
  ) : (
    <div className="app">
      <Header theme={theme} onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
              toast={toast}
              rightSlot={
                <div className="fs-topbar-extra">
                  <EnvBadge />
                  <OrgSelector />
                  <Notifications />
                  <button className="btn btn-ghost" onClick={() => setTourOpen(true)} title="Replay tour">Help</button>
                  <button className="btn btn-ghost" onClick={() => setPaletteOpen(true)} title="Command palette (Ctrl+K)">⌘K</button>
                </div>
              } />

      <PreviewBanner />

      <div className="body">
        <Sidebar betaOnly={session.uiMode === 'private_beta'} />
        <main className="main" key={location.pathname}>
          {session.uiMode === 'private_beta' ? (
            <Routes>
              <Route path="/" element={<BetaDefault />} />
              <Route path="/beta" element={
                <RouteGuard permission="view"><BetaTester toast={toast} /></RouteGuard>
              } />
              <Route path="/beta-signup" element={<BetaSignup toast={toast} />} />
              <Route path="/beta-ops" element={
                <RouteGuard permission="platform_admin"><BetaOps toast={toast} /></RouteGuard>
              } />
              {/* any legacy route in the local private-beta stack -> tombstone */}
              <Route path="*" element={<LegacyDisabled />} />
            </Routes>
          ) : (
            <Routes>
              <Route path="/" element={<Hub toast={toast} navigate={navigate} />} />
              <Route path="/hub" element={<Hub toast={toast} navigate={navigate} />} />
              <Route path="/ledger" element={<Ledger toast={toast} />} />
              <Route path="/prospector" element={<Prospector toast={toast} />} />
              <Route path="/goldengoose" element={<GoldenGoose toast={toast} />} />
              <Route path="/offerchisel" element={<OfferChisel toast={toast} />} />
              <Route path="/towncrier" element={<TownCrier toast={toast} />} />
              <Route path="/auctioneer" element={<Auctioneer toast={toast} />} />
              <Route path="/autothink" element={<Autothink toast={toast} />} />
              <Route path="/thewatch" element={<TheWatch toast={toast} />} />
              <Route path="/rankledger" element={<RankLedger toast={toast} />} />
              <Route path="/rivalboard" element={<RivalBoard toast={toast} />} />
              <Route path="/account" element={<Account toast={toast} />} />
              <Route path="/foundation" element={
                <RouteGuard permission="request_refresh"><FoundationStatus toast={toast} /></RouteGuard>
              } />
              <Route path="/jobs" element={
                <RouteGuard permission="request_refresh"><Jobs toast={toast} /></RouteGuard>
              } />
              <Route path="/keywords" element={
                <RouteGuard permission="request_refresh"><Keywords toast={toast} /></RouteGuard>
              } />
              <Route path="/beta" element={
                <RouteGuard permission="view"><BetaTester toast={toast} /></RouteGuard>
              } />
              <Route path="/beta-signup" element={<BetaSignup toast={toast} />} />
              <Route path="/beta-ops" element={
                <RouteGuard permission="platform_admin"><BetaOps toast={toast} /></RouteGuard>
              } />
              <Route path="*" element={<NotFound navigate={navigate} />} />
            </Routes>
          )}
        </main>
      </div>

      {session.uiMode !== 'private_beta' && <><PinnedDrawer toast={toast} /><Dock /></>}

      <TourOverlay steps={tour.steps} onClose={finishTour} />

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)}
                      onToggle={() => setPaletteOpen((v) => !v)} />

      <div className="toast-wrap">
        {toasts.map((t) => (
          <div key={t.id} className={`toast ${t.tone}`}>{t.msg}</div>
        ))}
      </div>
    </div>
  )
}

function NotFound({ navigate }) {
  return (
    <div className="page">
      <div className="card">
        <h1 className="text-glow" style={{ fontSize: 20 }}>Route not found</h1>
        <p className="text-mid">The service you requested doesn’t exist in this shell.</p>
        <button className="btn btn-primary" onClick={() => navigate('/hub')}>Back to Operations Hub</button>
      </div>
    </div>
  )
}

// Role-aware default landing for the private-beta UI mode.
function BetaDefault() {
  const session = useSession()
  const navigate = useNavigate()
  useEffect(() => {
    if (!session.authenticated) { navigate('/beta-signup', { replace: true }); return }
    if (session.hasPerm && session.hasPerm('platform_admin')) { navigate('/beta-ops', { replace: true }); return }
    navigate('/beta', { replace: true })
  }, [session.authenticated, session.role])
  return <div className="page"><div className="text-low">Loading beta…</div></div>
}

// Explicit tombstone for legacy UI routes in the local private-beta mode.
function LegacyDisabled() {
  return (
    <div className="page">
      <PageHead title="Legacy UI disabled"
        sub="The legacy Operations Hub shell is disabled in the local private-beta environment" />
      <div className="card">
        <p className="text-low">
          This area is not part of the private beta. The legacy analyst shell
          (Operations Hub, Ledger, Sourcing, Prospecting, Golden Goose, Listings,
          and similar) is intentionally unavailable here.
        </p>
        <p className="text-low">
          Use the <strong>Private Beta</strong> (tester) or <strong>Beta Operations</strong>
          (platform admin) areas instead.
        </p>
      </div>
    </div>
  )
}

export default function App() {
  return (
    <HashRouter>
      <SessionProvider>
        <Shell />
      </SessionProvider>
    </HashRouter>
  )
}