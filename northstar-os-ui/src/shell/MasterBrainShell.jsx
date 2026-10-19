// ═══════════════════════════════════════════════════════════════════════════
// MASTER BRAIN SHELL (V3 S4/S6) — the Simple view that is now the main
// NorthstarOS surface: full-bleed procedural cosmic canvas, the focus rail
// (Auto · Create · Grow · Research · Operate · AutothinK), real hardware
// telemetry, and the universal chat surface underneath.
//
// Rooms become FOCUSES: navigating to a room route in Simple mode selects the
// matching focus instead of rendering the room (the room itself lives in the
// Advanced view, which qualifying tiers can open from here).
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import ChatSurface from '../chat/ChatSurface.jsx'
import CosmicCanvas from './CosmicCanvas.jsx'
import HardwareModal from './HardwareModal.jsx'
import { useShell } from './ShellContext.jsx'
import { useMode } from '../context/ModeContext.jsx'

// Route → focus: deep links land on the right brain context.
const PATH_FOCUS = [
  [/^\/autothink/, 'autothink'],
  [/^\/(design-studio|creative-studio|product-designer)/, 'create'],
  [/^\/(listings|listingforge|keyword-tracker|adpilot|socialpulse)/, 'grow'],
  [/^\/(product-finder|golden-goose|competitor-monitor|routing)/, 'research'],
  [/^\/(profitability|commerce-ops|monitoring|spreadsheet-lab|memory-bank|shared-data|provider-adapters|master-brain|customer-workspace)/, 'operate'],
]

function hardwareLine(hw) {
  if (!hw) return { text: 'HW …', title: 'Hardware telemetry loading' }
  const g = hw.gpu || {}
  if (g.ok && Array.isArray(g.gpus) && g.gpus.length) {
    const g0 = g.gpus[0]
    const parts = []
    if (g0.util_pct != null) parts.push(`${Math.round(g0.util_pct)}% GPU`)
    let vramTitle = ''
    if (g0.vram_total_mb) {
      const usedGb = (g0.vram_used_mb || 0) / 1024
      const totalGb = g0.vram_total_mb / 1024
      parts.push(`${usedGb.toFixed(1)}/${totalGb.toFixed(1)} GB VRAM`)
      const free = g0.vram_total_mb - (g0.vram_used_mb || 0)
      vramTitle = free < 1800
        ? `VRAM reserve low (${Math.round(free)} MB free) — the 1.8 GB canvas reserve target is not met`
        : `Free VRAM: ${Math.round(free)} MB (1.8 GB reserved for the UI canvas)`
    }
    if (g0.temp_c != null) parts.push(`${Math.round(g0.temp_c)}°C`)
    return { text: parts.join(' · ') || g0.name || 'GPU', title: vramTitle || g0.name || 'GPU' }
  }
  if (hw.ram && hw.ram.ok) {
    return { text: `${hw.ram.percent}% RAM · GPU unknown`, title: g.reason || 'nvidia-smi unavailable' }
  }
  return { text: 'HW unavailable', title: g.reason || 'no readable hardware telemetry' }
}

export default function MasterBrainShell() {
  const shell = useShell()
  const { advancedAllowed, setMode } = useMode()
  const navigate = useNavigate()
  const location = useLocation()
  const [busy, setBusy] = useState(false)
  const [hwOpen, setHwOpen] = useState(false)

  // Deep links select the matching focus (rooms are focuses in Simple mode).
  useEffect(() => {
    const hit = PATH_FOCUS.find(([re]) => re.test(location.pathname))
    if (hit && hit[1] !== shell.focusId && !shell.focuses.find((f) => f.id === hit[1])?.locked) {
      shell.setFocus(hit[1])
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname])

  // Mark the document while the Simple shell is mounted so the shared chrome
  // (the top bar) can follow it into the dark without touching Advanced rooms.
  useEffect(() => {
    const root = document.documentElement
    root.dataset.shellMode = 'simple'
    return () => { delete root.dataset.shellMode }
  }, [])

  const hw = useMemo(() => hardwareLine(shell.hardware), [shell.hardware])
  const planLabel = shell.planName || (shell.plan ? String(shell.plan) : 'Foundation')
  const canvasDpr = shell.hardware?.governor?.recommended_dpr ?? 1.5
  const reserveOk = shell.hardware?.governor?.reserve_ok

  return (
    <div className="mb-shell" data-testid="mb-shell">
      <CosmicCanvas active={busy} maxDpr={canvasDpr} themeId={shell.focusId} />
      <div className="mb-scrim" aria-hidden="true" />
      <div className="mb-content" data-theme-scope="media">
        <div className="mb-header">
          <div className="mb-focus" role="tablist" aria-label="Master Brain focus"
            data-testid="mb-focus">
            {shell.focuses.map((f) => (
              <button
                key={f.id}
                type="button"
                role="tab"
                aria-selected={f.id === shell.focusId}
                className={`mb-focus-chip ${f.id === shell.focusId ? 'active' : ''} ${f.locked ? 'locked' : ''}`}
                onClick={() => { if (!f.locked) shell.setFocus(f.id) }}
                title={f.locked
                  ? `${f.label} — needs a qualifying plan (AutothinK workspace)`
                  : (f.blurb || f.label)}
                data-testid={`mb-focus-${f.id}`}
              >
                {f.label}{f.locked ? ' 🔒' : ''}
              </button>
            ))}
          </div>
          <div className="mb-status">
            <button
              type="button"
              className={`mb-chip mb-chip-btn ${reserveOk === false ? 'warn' : ''}`}
              title={`${hw.title} — open the hardware monitor`}
              onClick={() => setHwOpen(true)}
              data-testid="mb-hardware"
            >
              {hw.text}
            </button>
            <span className="mb-chip" title={`Plan: ${planLabel}`}>{planLabel}</span>
            {shell.offline && <span className="mb-chip warn" title={shell.offlineReason}>Shell context offline</span>}
            {advancedAllowed && (
              <button type="button" className="btn btn-sm btn-ghost"
                onClick={() => setMode('advanced')} data-testid="mb-to-advanced">
                Advanced view
              </button>
            )}
          </div>
        </div>
        <ChatSurface
          focus={shell.focus}
          heading="Bojo"
          sub="Northstar creative assistant"
          onBusyChange={setBusy}
          onOpenAdvanced={advancedAllowed
            ? (path) => { setMode('advanced'); navigate(path || '/home') }
            : null}
        />
      </div>
      {hwOpen && <HardwareModal onClose={() => setHwOpen(false)} />}
    </div>
  )
}
