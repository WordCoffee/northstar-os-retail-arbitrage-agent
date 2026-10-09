// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENTS — SHARED CHROME
// Mode toggle, tool rail, provider boundary, asset thumbnails.
// ═══════════════════════════════════════════════════════════════════════════

import Icon from '../../components/Icon.jsx'
import { PROVIDER_BOUNDARY } from '../engine/presets.js'

// ── Simple / Advanced mode ────────────────────────────────────────────────────
// Simple exposes only the fields that matter for a fast, safe edit. Advanced
// unlocks the full inspector (layer geometry, guides, export scale, raw
// prompts). The switch is honest about what it hides.
export function ModeToggle({ mode, onChange }) {
  return (
    <div className="sp-mode" role="tablist" aria-label="Editing mode">
      {[
        { id: 'simple', label: 'Simple', note: 'Curated controls — fast, safe edits.' },
        { id: 'advanced', label: 'Advanced', note: 'Full inspector, layer geometry, guides and raw prompt fields.' },
      ].map(m => (
        <button key={m.id} role="tab" aria-selected={mode === m.id}
          className={`sp-mode-btn ${mode === m.id ? 'active' : ''}`}
          onClick={() => onChange(m.id)} title={m.note}>
          {m.id === 'simple' ? <Icon name="target" size={13} /> : <Icon name="settings" size={13} />}
          <span>{m.label}</span>
        </button>
      ))}
    </div>
  )
}

// ── Left tool rail ────────────────────────────────────────────────────────────
export function ToolRail({ tools, active, onSelect, vertical = true }) {
  return (
    <div className={`sp-rail ${vertical ? '' : 'sp-rail-h'}`} role="tablist">
      {tools.map(t => (
        <button key={t.id} role="tab" aria-selected={active === t.id}
          className={`sp-rail-btn ${active === t.id ? 'active' : ''}`}
          onClick={() => onSelect(t.id)} title={t.note || t.label}>
          <Icon name={t.icon} size={16} />
          <span className="sp-rail-label">{t.label}</span>
          {t.count !== undefined && <span className="sp-rail-count">{t.count}</span>}
        </button>
      ))}
    </div>
  )
}

// ── Provider boundary (honest) ────────────────────────────────────────────────
export function ProviderBoundary({ kind = 'image', children }) {
  const p = PROVIDER_BOUNDARY[kind] || PROVIDER_BOUNDARY.image
  return (
    <div className="alert" data-testid="provider-boundary">
      <div className="alert-title">
        <span className="pill pill-unknown">PROVIDER REQUIRED</span> {p.label} is not connected
      </div>
      <div className="alert-text">
        Expected engine <strong>{p.engine}</strong> · env <span className="text-mono">{p.env}</span> ·
        gate <span className="text-mono">{p.gate}=1</span>. {p.models}. Nothing is generated until
        this boundary is satisfied — no placeholder image is shown in its place.
        {children}
      </div>
    </div>
  )
}

// ── Asset thumbnail ───────────────────────────────────────────────────────────
export function AssetThumb({ asset, height = 64, onClick, selected, actions }) {
  if (!asset) return null
  return (
    <div className={`sp-thumb ${selected ? 'selected' : ''}`} onClick={onClick} title={asset.name}>
      <div className="sp-thumb-img" style={{ height, backgroundImage: `url(${asset.dataUrl})` }} />
      <div className="sp-thumb-meta">
        <span className="sp-thumb-name">{asset.name}</span>
        <span className="text-mono sp-thumb-dims">{asset.w}×{asset.h}</span>
      </div>
      {actions && <div className="sp-thumb-actions">{actions}</div>}
    </div>
  )
}

export function ThumbPlaceholder({ height = 64, label = 'no preview' }) {
  return (
    <div className="sp-thumb-ph" style={{ height }}>
      <span>{label}</span>
    </div>
  )
}

// ── Format picker grid ────────────────────────────────────────────────────────
export function FormatGrid({ groups, value, onChange }) {
  return (
    <div className="sp-formats">
      {groups.map(g => (
        <div key={g.id} className="sp-format-group">
          <div className="sp-format-group-label">{g.label}</div>
          <div className="sp-format-list">
            {g.formats.map(f => (
              <button key={f.id} className={`sp-format ${value === f.id ? 'active' : ''}`}
                onClick={() => onChange(f)} title={`${f.w}×${f.h} px · ${f.channel}`}>
                <span className={`sp-format-box ar-${f.w >= f.h ? 'wide' : 'tall'}`}
                  style={{ aspectRatio: `${f.w} / ${f.h}` }} />
                <span className="sp-format-label">{f.label}</span>
                <span className="text-mono sp-format-dims">{f.w}×{f.h}</span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
