import { useState } from 'react'
import { MetricTiles } from '../../components/Shared.jsx'

export default function BetaLanding() {
  return (
    <div className="fade-in">
      <div className="page-header" style={{ textAlign: 'center', paddingTop: 60 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10, marginBottom: 16 }}>
          <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.5"><path d="M12 2L3 7 12 12 21 7 21 17 12 22 3 17" fill="none"/><circle cx="12" cy="12" r="2" fill="var(--forest)"/></svg>
          <h1 style={{ fontSize: 36 }}>NorthstarOS</h1>
        </div>
        <p className="lead" style={{ maxWidth: 520, margin: '0 auto 8px' }}>Retail Arbitrage Intelligence Suite</p>
        <p className="text-mid" style={{ maxWidth: 440, margin: '0 auto 32px' }}>An invite-only operating environment for Amazon FBA commerce intelligence and operations.</p>
      </div>
      <div className="grid-3" style={{ maxWidth: 900, margin: '0 auto' }}>
        {[
          { title: 'Product Finder', desc: 'Systematic discovery and evidence-driven evaluation across retail markets.' },
          { title: 'Golden Goose Finder', desc: 'Opportunity surfacing with supporting and contradicting signal analysis.' },
          { title: 'Portfolio & Finance', desc: 'Capital tracking, profitability analysis, and reinvestment planning.' },
        ].map((item, i) => (
          <div key={i} className="card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--forest)" strokeWidth="1.8"><rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M3 9h18M9 3v18" stroke="currentColor" stroke-width="1.8"/></svg>
              <h3 style={{ margin: 0, fontSize: 16 }}>{item.title}</h3>
            </div>
            <p className="text-mid" style={{ fontSize: 13, margin: 0 }}>{item.desc}</p>
          </div>
        ))}
      </div>
      <div className="card" style={{ maxWidth: 500, margin: '32px auto 0' }}>
        <div className="alert-warn" style={{ marginBottom: 16 }}>
          <div className="alert-title">Invite-Only Access</div>
          <div className="alert-text">NorthstarOS operates on an invitation basis. You cannot register directly.</div>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          <p className="text-mid" style={{ fontSize: 13 }}>If you have received an invitation, accept it through the link provided to you.</p>
          <div className="inline-flex" style={{ gap: 10 }}>
            <button className="btn btn-primary btn-block" onClick={() => window.location.href = '/beta/accept'}>Accept Invitation</button>
            <button className="btn btn-block" onClick={() => window.location.href = '/sign-in'}>Sign In</button>
          </div>
          <p className="text-low" style={{ fontSize: 12, textAlign: 'center' }}>Need access? Contact your organization operator.</p>
        </div>
      </div>
    </div>
  )
}