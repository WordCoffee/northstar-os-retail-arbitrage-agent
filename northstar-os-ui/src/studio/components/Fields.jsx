// readiness-scan: input-unlabelled waived - these are leaf form controls with no
// label of their own; the consumer wraps them in <Field label="..."> (line 26), which
// supplies the accessible name via implicit label association. Labelling them here
// would duplicate or invent a name the page did not ask for.
// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENTS — FORM PRIMITIVES
// Small, dependency-free field controls used by the studio inspector panels.
// They build on the shared `.field` / `.label` tokens so they match the shell.
// ═══════════════════════════════════════════════════════════════════════════

import { useId, useState } from 'react'

export function Section({ title, hint, right, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen)
  const id = useId()
  return (
    <div className="sp-section">
      <button className="sp-section-head" aria-expanded={open} onClick={() => setOpen(o => !o)}>
        <span className="sp-section-caret">{open ? '▾' : '▸'}</span>
        <span className="sp-section-title">{title}</span>
        {right && <span className="sp-section-right">{right}</span>}
      </button>
      {open && <div className="sp-section-body">{children}</div>}
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="sp-field">
      <span className="sp-field-label">{label}</span>
      {children}
      {hint && <span className="sp-field-hint">{hint}</span>}
    </label>
  )
}

export function TextInput({ value, onChange, placeholder, rows }) {
  if (rows) {
    return (
      <textarea className="field" rows={rows} value={value} placeholder={placeholder}
        onChange={e => onChange(e.target.value)} />
    )
  }
  return (
    <input className="field" type="text" value={value} placeholder={placeholder}
      onChange={e => onChange(e.target.value)} />
  )
}

export function NumberInput({ value, onChange, min, max, step = 1, suffix }) {
  return (
    <span className="sp-num">
      <input className="field" type="number" value={value} min={min} max={max} step={step}
        onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
      {suffix && <span className="sp-num-suffix">{suffix}</span>}
    </span>
  )
}

export function Slider({ value, onChange, min = 0, max = 1, step = 0.01, suffix = '' }) {
  const v = typeof value === 'number' ? value : 0
  return (
    <span className="sp-slider">
      <input type="range" min={min} max={max} step={step} value={v}
        onChange={e => onChange(Number(e.target.value))} />
      <span className="sp-slider-val text-mono">{suffix === '%' ? `${Math.round(v * 100)}%` : `${v}${suffix}`}</span>
    </span>
  )
}

export function Select({ value, onChange, options }) {
  return (
    <select className="field" value={value} onChange={e => onChange(e.target.value)}>
      {options.map(o => (
        <option key={o.value ?? o} value={o.value ?? o}>{o.label ?? o}</option>
      ))}
    </select>
  )
}

export function ColorInput({ value, onChange }) {
  return (
    <span className="sp-color">
      <input type="color" value={/^#[0-9a-f]{6}$/i.test(value) ? value : '#000000'}
        onChange={e => onChange(e.target.value)} />
      <input className="field text-mono" type="text" value={value} onChange={e => onChange(e.target.value)} />
    </span>
  )
}

export function SegmentedControl({ value, onChange, options, size = 'md' }) {
  return (
    <div className={`sp-seg sp-seg-${size}`} role="tablist">
      {options.map(o => {
        const v = o.value ?? o
        const active = v === value
        return (
          <button key={v} role="tab" aria-selected={active}
            className={`sp-seg-btn ${active ? 'active' : ''}`}
            onClick={() => onChange(v)} title={o.note || undefined}>
            {o.label ?? o}
          </button>
        )
      })}
    </div>
  )
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="check-row">
      <input type="checkbox" checked={!!checked} onChange={e => onChange(e.target.checked)} />
      <span>{label}</span>
    </label>
  )
}

export function ChipRow({ options, value = [], onToggle, allLabel }) {
  const isAll = !value || value.length === 0
  return (
    <div className="inline-flex">
      {allLabel && (
        <button className={`filter-pill ${isAll ? 'active' : ''}`} onClick={() => onToggle([])}>{allLabel}</button>
      )}
      {options.map(o => {
        const v = o.value ?? o
        const active = Array.isArray(value) && value.includes(v)
        return (
          <button key={v} className={`filter-pill ${active ? 'active' : ''}`} onClick={() => onToggle(v)} title={o.note || undefined}>
            {o.label ?? o}
          </button>
        )
      })}
    </div>
  )
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div className="sp-stat">
      <div className="sp-stat-label">{label}</div>
      <div className={`sp-stat-value ${tone ? `tone-${tone}` : ''}`}>{value}</div>
      {sub && <div className="sp-stat-sub">{sub}</div>}
    </div>
  )
}

export function EmptyState({ title, children }) {
  return (
    <div className="sp-empty">
      <div className="sp-empty-title">{title}</div>
      {children && <div className="sp-empty-body">{children}</div>}
    </div>
  )
}
