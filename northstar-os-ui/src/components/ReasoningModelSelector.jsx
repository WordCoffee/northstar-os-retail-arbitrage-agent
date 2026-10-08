import { useEffect, useState } from 'react'
import foundationApi from '../foundation/api.js'

const STORAGE_KEY = 'ns-reasoning-model-v2'

const ROLE_LABEL = {
  default: 'Default (non-creative policy)',
  standard: 'Standard (low-cost fallback)',
  alternative: 'Alternative',
  budget: 'Budget',
  escalation: 'Escalation (explicit only)',
}

const ROLE_TONE = {
  default: 'forest',
  standard: 'ochre',
  alternative: 'ochre',
  budget: 'muted',
  escalation: 'warn',
}

function formatCost(c) {
  if (c === undefined || c === null) return '—'
  if (c === 0) return 'free'
  return `$${c.toFixed(2)}`
}

function modelTitle(m) {
  if (!m) return ''
  const bits = [`${m.provider}/${m.id}`]
  if (m.availability_note) bits.push(m.availability_note)
  if (m.notes) bits.push(m.notes)
  return bits.join(' — ')
}

export function useReasoningModel() {
  const [selected, setSelected] = useState(null)
  const [catalog, setCatalog] = useState(null)
  const [phase, setPhase] = useState('loading')

  useEffect(() => {
    let alive = true
    Promise.all([
      foundationApi.reasoningModels().catch(() => null),
      Promise.resolve().then(() => {
        try { return localStorage.getItem(STORAGE_KEY) || null } catch { return null }
      }),
    ]).then(([cat, stored]) => {
      if (!alive) return
      const models = cat && Array.isArray(cat.models) ? cat.models : []
      const escalation = cat && Array.isArray(cat.escalation_models) ? cat.escalation_models : []
      const allModels = [...models, ...escalation]
      const defaultModel = models.find(m => m.role === 'default') || models[0]
      const initial = allModels.find(m => m.id === stored || m.short_id === stored) || defaultModel
      setCatalog(cat || { models: [], escalation_models: [], armed: false, available: false })
      setSelected(initial ? initial.id : null)
      setPhase('loaded')
    })
    return () => { alive = false }
  }, [])

  const persist = (modelId) => {
    setSelected(modelId)
    try { localStorage.setItem(STORAGE_KEY, modelId) } catch { /* storage unavailable */ }
  }

  const models = catalog?.models || []
  const escalation = catalog?.escalation_models || []
  const selectedModel = [...models, ...escalation].find(m => m.id === selected) || models[0]

  return { selected, selectedModel, catalog, phase, persist, models, escalation }
}

export default function ReasoningModelSelector({ value, onChange, showPricing = true, showArmed = true, showEscalation = true }) {
  const { models, escalation, catalog, phase } = useReasoningModel()
  const armed = catalog?.armed
  const available = catalog?.available

  return (
    <div className="reasoning-model-selector" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <label htmlFor="reasoning-model" className="text-low" style={{ fontSize: 12 }}>Hosted reasoning model</label>
      <select
        id="reasoning-model"
        className="field"
        style={{ minWidth: 260 }}
        value={value || ''}
        onChange={e => onChange && onChange(e.target.value)}
        disabled={phase === 'loading' || (models.length + escalation.length) === 0}
      >
        {phase === 'loading' && <option value="">Loading…</option>}
        {phase !== 'loading' && (models.length + escalation.length) === 0 && <option value="">No models</option>}
        {models.length > 0 && (
          <optgroup label="Selectable (non-creative)">
            {models.map(m => (
              <option key={m.id} value={m.id} title={modelTitle(m)}>
                {m.name} · {ROLE_LABEL[m.role] || m.role}{m.provider_blocked ? ' · provider-blocked' : ''}
              </option>
            ))}
          </optgroup>
        )}
        {showEscalation && escalation.length > 0 && (
          <optgroup label="Escalation — explicit selection only, never auto-selected">
            {escalation.map(m => (
              <option key={m.id} value={m.id} title={modelTitle(m)}>
                {m.name} · {ROLE_LABEL[m.role] || m.role}
              </option>
            ))}
          </optgroup>
        )}
      </select>
      {showArmed && (
        <span
          className={`pill ${armed ? 'pill-ok' : available ? 'pill-ochre' : 'pill-muted'}`}
          title={armed ? 'OpenCode Go armed and ready' : available ? 'Key present but not armed' : 'Not configured'}
        >
          {armed ? 'armed' : available ? 'not armed' : 'not configured'}
        </span>
      )}
      {showPricing && value && (
        <span className="text-low" style={{ fontSize: 11 }}>
          {(() => {
            const m = [...models, ...escalation].find(x => x.id === value)
            if (!m) return null
            return `${formatCost(m.cost_per_1m_input)} / 1M in · ${formatCost(m.cost_per_1m_output)} / 1M out · ${m.pricing_source}`
          })()}
        </span>
      )}
      {value && (() => {
        const m = [...models, ...escalation].find(x => x.id === value)
        if (!m) return null
        return m.provider_blocked ? (
          <span className="pill pill-warn" title={modelTitle(m)}>
            provider-blocked
          </span>
        ) : (
          <span className="pill pill-muted" title={modelTitle(m)}>
            selectable
          </span>
        )
      })()}
    </div>
  )
}

export { STORAGE_KEY }
