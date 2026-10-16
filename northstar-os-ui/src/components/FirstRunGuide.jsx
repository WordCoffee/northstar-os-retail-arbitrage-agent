// ═══════════════════════════════════════════════════════════════════════════
// FIRST-RUN GUIDE (2026-10-16, Phase 2)
//
// A three-step guided start for a new user (the operator and their partner):
//   1. Bring a file from Amazon   2. Make something   3. Get it to Amazon
// Shown once per browser; dismissible; every step deep-links to the real room.
// Nothing here calls a provider and nothing is fabricated — the copy mirrors
// the product's file-only architecture.
// ═══════════════════════════════════════════════════════════════════════════

import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

const KEY = 'ns-first-run-done'

export default function FirstRunGuide() {
  const navigate = useNavigate()
  const [done, setDone] = useState(() => {
    try { return localStorage.getItem(KEY) === '1' } catch { return true }
  })
  const [step, setStep] = useState(0)

  if (done) return null

  const finish = (goTo) => {
    try { localStorage.setItem(KEY, '1') } catch { /* storage unavailable */ }
    setDone(true)
    if (goTo) navigate(goTo)
  }

  const STEPS = [
    {
      title: 'Bring a file from Amazon',
      body: 'Download a bulksheet, a listing template or a search-term report from your Amazon console, then upload it in Design Studio → Ads → Amazon files. No Amazon sign-in, no API — your files, your machine.',
      action: 'Open Amazon files',
      goTo: '/design-studio?section=ads&view=amazon-files',
    },
    {
      title: 'Make something',
      body: 'In the Design Studio, start from your own photo: main images, A+ sets, print dielines and social assets all render locally. Every compliance check runs before export.',
      action: 'Open Design Studio',
      goTo: '/design-studio',
    },
    {
      title: 'Get it to Amazon',
      body: 'Northstar writes a change file with only your approved changes. Download it and upload it to Amazon yourself — nothing is ever submitted for you.',
      action: 'See how it works',
      goTo: '/design-studio?section=ads&view=amazon-files',
    },
  ]

  const s = STEPS[step]

  return (
    <div
      data-testid="first-run-guide"
      style={{
        position: 'fixed', inset: 0, zIndex: 60,
        background: 'rgba(24, 32, 24, 0.45)', display: 'flex',
        alignItems: 'center', justifyContent: 'center', padding: 20,
      }}
    >
      <div className="card" style={{ maxWidth: 560, width: '100%', padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span className="pill pill-muted">step {step + 1} of {STEPS.length}</span>
          <button className="btn btn-sm btn-ghost" onClick={() => finish(null)} data-testid="first-run-skip">
            Skip — I know my way around
          </button>
        </div>
        <h2 style={{ fontFamily: 'var(--font-serif)', fontSize: 24, color: 'var(--pine-deep)', margin: '14px 0 8px' }}>
          {s.title}
        </h2>
        <p style={{ fontSize: 14, color: 'var(--ink-mid)', lineHeight: 1.55 }}>{s.body}</p>
        <div style={{ display: 'flex', gap: 8, marginTop: 20, flexWrap: 'wrap' }}>
          {step < STEPS.length - 1 ? (
            <button className="btn btn-sm btn-primary" onClick={() => setStep(step + 1)} data-testid="first-run-next">
              Next
            </button>
          ) : (
            <button className="btn btn-sm btn-primary" onClick={() => finish(s.goTo)} data-testid="first-run-finish">
              {s.action}
            </button>
          )}
          {step > 0 && (
            <button className="btn btn-sm" onClick={() => setStep(step - 1)}>Back</button>
          )}
          <button className="btn btn-sm btn-ghost" onClick={() => finish(s.goTo)}>
            Take me there now
          </button>
        </div>
        <div className="text-low" style={{ fontSize: 11, marginTop: 14 }}>
          This guide shows once. Everything it points at works offline on your own files.
        </div>
      </div>
    </div>
  )
}
