import { useState, useEffect } from 'react'
import { HashRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Header from './components/Header.jsx'
import Sidebar from './components/Sidebar.jsx'
import RightRail from './components/RightRail.jsx'
import Dock from './components/Dock.jsx'
import Icon from './components/Icon.jsx'

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

function Shell() {
  const navigate = useNavigate()
  const location = useLocation()

  const [theme, setTheme] = useState(() => localStorage.getItem('northstar-theme') || 'dark')
  const [toasts, setToasts] = useState([])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('northstar-theme', theme)
  }, [theme])

  const toast = (msg, tone = 'ok') => {
    const id = Date.now() + Math.random()
    setToasts((prev) => [...prev.slice(-3), { id, msg, tone }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200)
  }

  return (
    <div className="app">
      <Header theme={theme} onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} toast={toast} />

      <div className="body">
        <Sidebar />
        <main className="main" key={location.pathname}>
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
            <Route path="*" element={<NotFound navigate={navigate} />} />
          </Routes>
        </main>
        <RightRail toast={toast} />
      </div>

      <Dock />

      <button className="assistant" onClick={() => toast('Paperclip: I can route you — try the sidebar or dock.', 'ok')} aria-label="Paperclip assistant">
        <Icon name="paperclip" size={22} />
        <span>How can I help?</span>
      </button>

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

export default function App() {
  return (
    <HashRouter>
      <Shell />
    </HashRouter>
  )
}