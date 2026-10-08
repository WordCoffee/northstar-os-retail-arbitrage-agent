import { useEffect, useState } from 'react'
import foundationApi from '../foundation/api.js'

const STORAGE_KEY = 'ns-reasoning-model'

const ROLE_LABEL = {
  default: 'Default',
  alternative: 'Alternative',
  budget: 'Budget',
}

const ROLE_TONE = {
  default: 'forest',
  alternative: 'ochre',
  budget: 'muted',
}

function formatCost(c) {
  if (c === undefined || c === null) return '—'
  return `$${c.toFixed(2)}`
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
      const defaultModel = models.find(m => m.role === 'default') || models[0]
      const initial = models.find(m => m.id === stored || m.short_id === stored) || defaultModel
      setCatalog(cat || { models: [], armed: false, available: false })
      setSelected(initial ? initial.id : null)
      setPhase('loaded')
    })
    return () => { alive = false }
  }, [])

  const persist = (modelId) => {
    setSelected(modelId)
    try { localStorage.setItem(STORAGE_KEY, modelId) } catch { /* storage unavailable */ }
  }

  const selectedModel = catalog?.models?.find(m => m.id === selected) || catalog?.models?.[0]

  return { selected, selectedModel, catalog, phase, persist }
}

export default function ReasoningModelSelector({ value, onChange, showPricing = true, showArmed = true }) {
  const { catalog, phase } = useReasoningModel()
  const models = catalog?.models || []
  const armed = catalog?.armed
  const available = catalog?.available

  return (
    <div className="reasoning-model-selector" style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
      <label htmlFor="reasoning-model" className="text-low" style={{ fontSize: 12 }}>Hosted reasoning model</label>
      <select
        id="reasoning-model"
        className="field"
        style={{ minWidth: 220 }}
        value={value || ''}
        onChange={e => onChange && onChange(e.target.value)}
        disabled={phase === 'loading' || models.length === 0}
      >
        {phase === 'loading' && <option value="">Loading…</option>}
        {phase !== 'loading' && models.length === 0 && <option value="">No models</option>}
        {models.map(m => (
          <option key={m.id} value={m.id}>
            {m.name} · {ROLE_LABEL[m.role] || m.role}
          </option>
        ))}
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
            const m = models.find(x => x.id === value)
            if (!m) return null
            return `${formatCost(m.cost_per_1m_input)} / 1M in · ${formatCost(m.cost_per_1m_output)} / 1M out · ${m.pricing_source}`
          })()}
        </span>
      )}
    </div>
  )
}

export { STORAGE_KEY }
