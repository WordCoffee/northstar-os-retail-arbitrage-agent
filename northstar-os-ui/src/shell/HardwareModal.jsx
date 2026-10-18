// ═══════════════════════════════════════════════════════════════════════════
// HARDWARE MONITOR (V3 S6) — the RTX 5080 performance modal.
//
// Opened from the shell's hardware chip. Real readings only:
//   • GPU name, utilization, temperature, VRAM bar with the 1.8 GB canvas
//     reserve marked on it (the 14.2 GB model budget is total minus reserve)
//   • RAM bar
//   • the governor's verdict: reserve intact? canvas DPR full or lowered?
//   • auto-refreshes every 3 s while open; unavailable hardware reports
//     UNKNOWN, never a fabricated number.
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useState } from 'react'
import { shellApi } from './api.js'

function gb(mb) {
  return (mb / 1024).toFixed(1)
}

function Gauge({ label, usedMb, totalMb, reserveMb, detail }) {
  const pct = totalMb ? Math.min(100, Math.round((usedMb / totalMb) * 100)) : null
  const reservePct = totalMb && reserveMb ? Math.max(0, (reserveMb / totalMb) * 100) : null
  return (
    <div className="hw-gauge-block">
      <div className="hw-gauge-head">
        <span>{label}</span>
        <span className="hw-gauge-val">{detail || 'UNKNOWN'}</span>
      </div>
      <div className="hw-gauge" aria-hidden="true">
        {pct != null && <i style={{ width: `${pct}%` }} />}
        {reservePct != null && (
          <span className="hw-reserve" style={{ left: `${100 - reservePct}%` }}
            title={`Canvas reserve: ${gb(reserveMb)} GB must stay free`} />
        )}
      </div>
      {pct != null && totalMb != null && (
        <div className="hw-gauge-sub">
          {gb(usedMb)} / {gb(totalMb)} GB used · {pct}%
          {reserveMb != null && ` · ${gb(reserveMb)} GB reserved for the canvas`}
        </div>
      )}
    </div>
  )
}

export default function HardwareModal({ onClose }) {
  const [hw, setHw] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const h = await shellApi.hardware()
        if (!cancelled) setHw(h)
      } catch (e) {
        if (!cancelled) setError(e.message || 'telemetry unavailable')
      }
    }
    tick()
    const t = setInterval(tick, 3000)
    return () => { cancelled = true; clearInterval(t) }
  }, [])

  const gpu = hw?.gpu || {}
  const g0 = (gpu.gpus || [])[0] || null
  const ram = hw?.ram || {}
  const gov = hw?.governor || {}

  return (
    <div className="hw-overlay" onClick={onClose} role="dialog" aria-modal="true"
      aria-label="Hardware performance monitor" data-theme-scope="media"
      data-testid="hw-modal">
      <div className="hw-modal" onClick={(e) => e.stopPropagation()}>
        <div className="hw-head">
          <h3>Hardware performance</h3>
          <span className="hw-sub">
            Local telemetry · {hw ? `sampled ${String(hw.sampled_at || '').slice(11, 19)} UTC` : 'sampling…'}
          </span>
          <span style={{ flex: 1 }} />
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>Close</button>
        </div>

        {error && <div className="hw-note">Telemetry error: {error}</div>}

        <div className="hw-grid">
          <div className="hw-card">
            <div className="hw-card-title">GPU</div>
            <div className="hw-card-name">{g0 ? g0.name : (gpu.reason || 'UNKNOWN — no GPU reading')}</div>
            {g0 && (
              <>
                <div className="hw-stats">
                  {g0.util_pct != null && <span className="hw-chip">{Math.round(g0.util_pct)}% util</span>}
                  {g0.temp_c != null && <span className="hw-chip">{Math.round(g0.temp_c)}°C</span>}
                </div>
                <Gauge
                  label="VRAM"
                  usedMb={g0.vram_used_mb}
                  totalMb={g0.vram_total_mb}
                  reserveMb={gov.reserve_target_mb}
                />
              </>
            )}
            {!g0 && gpu.ok === false && (
              <div className="hw-note">{gpu.reason}</div>
            )}
          </div>

          <div className="hw-card">
            <div className="hw-card-title">RAM</div>
            {ram.ok ? (
              <Gauge
                label="System memory"
                usedMb={ram.used_mb}
                totalMb={ram.total_mb}
                detail={`${gb(ram.used_mb)} / ${gb(ram.total_mb)} GB · ${ram.percent}%`}
              />
            ) : (
              <div className="hw-note">{ram.reason || 'UNKNOWN — no RAM reading'}</div>
            )}
          </div>

          <div className="hw-card hw-governor">
            <div className="hw-card-title">Canvas governor</div>
            {gov.recommended_dpr ? (
              <>
                <div className="hw-verdict" data-ok={gov.reserve_ok ? '1' : '0'}>
                  {gov.reserve_ok
                    ? 'Reserve intact — canvas at full quality'
                    : 'Reserve LOW — canvas quality lowered'}
                </div>
                <div className="hw-note">
                  {gov.free_mb != null && `${gb(gov.free_mb)} GB VRAM free · `}
                  target: ≥ {gb(gov.reserve_target_mb)} GB stays free for the
                  WebGL canvas + compositor (the 14.2 GB model budget is the
                  rest of the 16 GB card). Canvas DPR: {gov.recommended_dpr}.
                </div>
              </>
            ) : (
              <div className="hw-note">UNKNOWN — no governor verdict without a GPU reading.</div>
            )}
          </div>
        </div>

        <div className="hw-foot">
          Auto-refreshes every 3 s while open · renders evict the local brain
          before using the card · nothing here is estimated from anything but
          nvidia-smi and the OS memory counters.
        </div>
      </div>
    </div>
  )
}
