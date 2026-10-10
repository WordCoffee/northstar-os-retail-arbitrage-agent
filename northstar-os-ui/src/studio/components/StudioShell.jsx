// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENTS — EDITOR SHELL
//
// Phase 2: one editor-grade shell used by every Design Studio section.
//
//   ┌──────────────────────────── TopBar ─────────────────────────────┐
//   │ project · undo/redo · zoom · safe-zone toggle · export          │
//   ├──────────┬──────────────────────────────────────┬───────────────┤
//   │ LeftRail │              Canvas                  │  Inspector    │
//   │ templates│        (zoom / pan / guides)         │  properties   │
//   │ assets   │                                      │  AI actions   │
//   │ layers   │                                      │  compliance   │
//   ├──────────┴──────────────────────────────────────┴───────────────┤
//   │ BottomStrip — pages / variants / timeline                       │
//   └─────────────────────────────────────────────────────────────────┘
//
// The shell is presentation only: sections supply the rails and the canvas.
// Safe-zone overlays render from specRegistry SAFE_ZONES so a crop rule can
// never drift from its source.
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { SAFE_ZONES } from '../engine/specRegistry.js'

// ── Top bar ──────────────────────────────────────────────────────────────────
export function StudioTopBar({
  title, subtitle, onUndo, onRedo, canUndo, canRedo,
  zoom, onZoom, onFit, showSafeZones, onToggleSafeZones,
  safeZoneNote, actions, status,
}) {
  return (
    <div className="ss-topbar">
      <div className="ss-topbar-left">
        <div className="ss-topbar-title">{title}</div>
        {subtitle && <div className="ss-topbar-sub">{subtitle}</div>}
      </div>
      <div className="ss-topbar-mid">
        <button className="ss-iconbtn" onClick={onUndo} disabled={!canUndo} title="Undo (Ctrl+Z)"><Icon name="rotate" size={14} /></button>
        <button className="ss-iconbtn" onClick={onRedo} disabled={!canRedo} title="Redo (Ctrl+Shift+Z)"><Icon name="rotate" size={14} /></button>
        <span className="ss-sep" />
        <button className="ss-iconbtn" onClick={() => onZoom(Math.max(0.1, zoom - 0.1))} title="Zoom out"><Icon name="zoomOut" size={14} /></button>
        <button className="ss-zoomlabel" onClick={onFit} title="Fit to view">{Math.round(zoom * 100)}%</button>
        <button className="ss-iconbtn" onClick={() => onZoom(Math.min(4, zoom + 0.1))} title="Zoom in"><Icon name="zoomIn" size={14} /></button>
        <span className="ss-sep" />
        <button
          className={`ss-iconbtn ${showSafeZones ? 'active' : ''}`}
          onClick={() => onToggleSafeZones(!showSafeZones)}
          title={safeZoneNote || 'Show the Amazon safe zones for this format'}
        ><Icon name="grid" size={14} /></button>
      </div>
      <div className="ss-topbar-right">
        {status}
        {actions}
      </div>
    </div>
  )
}

// ── Left rail ────────────────────────────────────────────────────────────────
export function StudioLeftRail({ tabs, active, onSelect, children }) {
  return (
    <div className="ss-leftrail">
      <div className="ss-leftrail-tabs">
        {tabs.map(t => (
          <button key={t.id} className={`ss-leftrail-tab ${active === t.id ? 'active' : ''}`}
            onClick={() => onSelect(t.id)} title={t.note || t.label}>
            <Icon name={t.icon} size={15} />
            <span>{t.label}</span>
          </button>
        ))}
      </div>
      <div className="ss-leftrail-body">{children}</div>
    </div>
  )
}

// ── Canvas with zoom / pan / safe zones ─────────────────────────────────────
export function StudioCanvas({ children, zoom = 1, fitWidth = 900, safeZoneId, showSafeZones, pan = { x: 0, y: 0 }, onPan, canvasAspect = 1, onWheelZoom }) {
  const ref = useRef(null)
  const drag = useRef(null)
  const zones = safeZoneId ? SAFE_ZONES[safeZoneId] : null

  const startPan = (e) => {
    if (!onPan) return
    drag.current = { x: e.clientX - pan.x, y: e.clientY - pan.y }
  }
  const movePan = (e) => {
    if (!drag.current || !onPan) return
    onPan({ x: e.clientX - drag.current.x, y: e.clientY - drag.current.y })
  }
  const endPan = () => { drag.current = null }

  useEffect(() => {
    const el = ref.current
    if (!el || !onWheelZoom) return
    const handler = (e) => {
      if (!e.ctrlKey && !e.metaKey) return
      e.preventDefault()
      onWheelZoom(e.deltaY > 0 ? -0.05 : 0.05)
    }
    el.addEventListener('wheel', handler, { passive: false })
    return () => el.removeEventListener('wheel', handler)
  }, [onWheelZoom])

  return (
    <div
      ref={ref}
      className="ss-canvas"
      onMouseDown={startPan}
      onMouseMove={movePan}
      onMouseUp={endPan}
      onMouseLeave={endPan}
      style={{ cursor: onPan ? (drag.current ? 'grabbing' : 'grab') : 'default' }}
    >
      <div
        className="ss-canvas-inner"
        style={{
          width: Math.round(fitWidth * zoom),
          height: Math.round(fitWidth * zoom / (canvasAspect || 1)),
          transform: `translate(${pan.x}px, ${pan.y}px)`,
        }}
      >
        {children}
        {showSafeZones && zones && (
          <div className="ss-safezones" aria-hidden="true">
            {(zones.keepOut || []).map((z, i) => (
              <div key={i} className="ss-zone ss-zone-keepout" title={z.label}
                style={{ left: `${z.x * 100}%`, top: `${z.y * 100}%`, width: `${z.w * 100}%`, height: `${z.h * 100}%` }}>
                <span className="ss-zone-label">{z.label}</span>
              </div>
            ))}
            {zones.keepIn && (
              <div className="ss-zone ss-zone-keepin" title={zones.keepIn.label}
                style={{ left: `${zones.keepIn.x * 100}%`, top: `${zones.keepIn.y * 100}%`, width: `${zones.keepIn.w * 100}%`, height: `${zones.keepIn.h * 100}%` }} />
            )}
          </div>
        )}
      </div>
      {showSafeZones && !zones && (
        <div className="ss-safezones-note">No safe zone recorded for this format.</div>
      )}
      {zones && <div className="ss-canvas-caption">{zones.note} · {zones.source}</div>}
    </div>
  )
}

// ── Right inspector ──────────────────────────────────────────────────────────
export function StudioInspector({ children }) {
  return <div className="ss-inspector">{children}</div>
}

export function InspectorSection({ title, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className={`ss-insp ${open ? 'open' : ''}`}>
      <button className="ss-insp-head" onClick={() => setOpen(o => !o)}>
        <span>{title}</span>
        <Icon name={open ? 'chevronDown' : 'chevronRight'} size={13} />
      </button>
      {open && <div className="ss-insp-body">{children}</div>}
    </div>
  )
}

// ── Bottom strip ─────────────────────────────────────────────────────────────
export function StudioBottomStrip({ items, active, onSelect, renderItem, actions }) {
  return (
    <div className="ss-bottomstrip">
      <div className="ss-bottomstrip-items">
        {items.map((it, i) => (
          <button key={it.id || i} className={`ss-bottomstrip-item ${active === (it.id || i) ? 'active' : ''}`}
            onClick={() => onSelect(it)} title={it.label}>
            {renderItem ? renderItem(it) : it.label}
          </button>
        ))}
        {!items.length && <span className="ss-bottomstrip-empty">Nothing here yet.</span>}
      </div>
      {actions && <div className="ss-bottomstrip-actions">{actions}</div>}
    </div>
  )
}

// ── Compliance verdict pill (shared by every section) ───────────────────────
export function VerdictPill({ verdict }) {
  const map = {
    pass: { cls: 'pill-ok', label: 'Pre-flight pass' },
    flag: { cls: 'pill-warn', label: 'Pre-flight warns' },
    block: { cls: 'pill-error', label: 'Pre-flight blocks' },
    unknown: { cls: 'pill-muted', label: 'Not checked' },
  }
  const v = map[verdict] || map.unknown
  return <span className={`pill ${v.cls}`} data-testid="verdict-pill">{v.label}</span>
}

// ── Compliance panel body (shared) ───────────────────────────────────────────
export function CompliancePanel({ report, onOverride }) {
  if (!report) return <div className="text-low" style={{ fontSize: 12 }}>Nothing to check yet.</div>
  return (
    <div className="ss-compliance" data-testid="compliance-panel">
      <div className="ss-compliance-head">
        <VerdictPill verdict={report.verdict} />
        <span className="text-low" style={{ fontSize: 11 }}>{report.ready}/{report.total} rules pass</span>
      </div>
      {report.blocked.length > 0 && (
        <div className="ss-compliance-group">
          <div className="ss-compliance-group-label ss-block">Blocks export ({report.blocked.length})</div>
          {report.blocked.map((r, i) => (
            <div key={i} className="ss-rule ss-rule-block">
              <div className="ss-rule-label">{r.label}</div>
              <div className="ss-rule-detail">{r.detail}</div>
              <div className="ss-rule-source">{r.source} · {r.accessed}</div>
            </div>
          ))}
        </div>
      )}
      {report.flagged.length > 0 && (
        <div className="ss-compliance-group">
          <div className="ss-compliance-group-label ss-flag">Needs review ({report.flagged.length})</div>
          {report.flagged.map((r, i) => (
            <div key={i} className="ss-rule ss-rule-flag">
              <div className="ss-rule-label">{r.label}</div>
              <div className="ss-rule-detail">{r.detail}</div>
              <div className="ss-rule-source">{r.source} · {r.accessed}</div>
            </div>
          ))}
        </div>
      )}
      {report.passed.length > 0 && (
        <details className="ss-passed">
          <summary>Passed ({report.passed.length})</summary>
          {report.passed.map((r, i) => (
            <div key={i} className="ss-rule ss-rule-pass">
              <div className="ss-rule-label">{r.label}</div>
              <div className="ss-rule-detail">{r.detail}</div>
            </div>
          ))}
        </details>
      )}
      {onOverride && report.verdict === 'block' && (
        <button className="btn btn-sm" onClick={onOverride} title="Record an explicit override on the document. It is never silent.">
          Override with a recorded reason
        </button>
      )}
    </div>
  )
}

// ── Spec picker (reads the registry, groups by channel) ─────────────────────
export function SpecPicker({ groups, value, onChange }) {
  return (
    <div className="ss-specs" data-testid="spec-picker">
      {groups.map(g => (
        <div key={g.id} className="ss-spec-group">
          <div className="ss-spec-group-label">{g.label} <span className="text-low">· {g.channel}</span></div>
          {g.specs.map(s => (
            <button key={s.id} className={`ss-spec ${value === s.id ? 'active' : ''}`}
              onClick={() => onChange(s)} title={s.note || `${s.w}×${s.h}`}>
              <span className="ss-spec-name">{s.label}</span>
              <span className="text-mono ss-spec-dims">{s.w}×{s.h}</span>
              {s.maxBytes && <span className="ss-spec-cap">{Math.round(s.maxBytes / 1024)} KB cap</span>}
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Empty state with a Run action (the studio-wide honest pattern) ──────────
export function StudioEmpty({ title, what, actionLabel, onAction, connect, children }) {
  return (
    <div className="ss-empty" data-testid="studio-empty">
      <div className="ss-empty-title">{title}</div>
      <div className="ss-empty-what">{what}</div>
      {actionLabel && onAction && <button className="btn btn-sm btn-primary" onClick={onAction}>{actionLabel}</button>}
      {connect && (
        <div className="ss-empty-connect">
          Not connected: add the key in <strong>Settings › Integrations</strong>.
        </div>
      )}
      {children}
    </div>
  )
}

// ── useStudioZoom — shared zoom state with keyboard shortcuts ───────────────
export function useStudioZoom(initial = 1) {
  const [zoom, setZoom] = useState(initial)
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey)) return
      if (e.key === '=' || e.key === '+') { e.preventDefault(); setZoom(z => Math.min(4, z + 0.1)) }
      if (e.key === '-') { e.preventDefault(); setZoom(z => Math.max(0.1, z - 0.1)) }
      if (e.key === '0') { e.preventDefault(); setZoom(1) }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])
  return [zoom, setZoom]
}

// ── useUndo — a tiny shared history for section documents ───────────────────
export function useUndo(initial) {
  const [stack, setStack] = useState([initial])
  const [index, setIndex] = useState(0)
  const value = stack[index]
  const push = (next) => {
    setStack(prev => [...prev.slice(0, index + 1), next].slice(-50))
    setIndex(i => Math.min(i + 1, 49))
  }
  const undo = () => setIndex(i => Math.max(0, i - 1))
  const redo = () => setIndex(i => Math.min(stack.length - 1, i + 1))
  const reset = (v) => { setStack([v]); setIndex(0) }
  return { value, push, undo, redo, reset, canUndo: index > 0, canRedo: index < stack.length - 1, depth: stack.length }
}
