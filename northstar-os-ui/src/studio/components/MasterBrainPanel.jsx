// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENT — MASTER-BRAIN PANEL (Phase 9 item 2)
//
// A READ-ONLY view of the Studio's imported evidence, rendered inside other
// rooms (ListingForge, AdPilot, SocialPulse). It reads one tenant-scoped
// endpoint; every section states its source, observed time, freshness and
// limits, and a missing section reads UNKNOWN - never zero. No provider is
// contacted by this component or the endpoint behind it.
// ═══════════════════════════════════════════════════════════════════════════

import { useEffect, useState } from 'react'
import { fetchMasterBrainContext } from '../engine/imports.js'

const FRESH_DAYS = 90 // the same stated engineering window the listing context uses

function freshnessOf(iso) {
  if (!iso) return { label: 'unknown', note: 'no usable date on the record' }
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return { label: 'unknown', note: 'no usable date on the record' }
  const days = Math.max(0, Math.round((Date.now() - t) / 86400000))
  return days <= FRESH_DAYS
    ? { label: 'current', note: `observed ${days} day(s) ago (window ${FRESH_DAYS} days - an engineering choice)` }
    : { label: 'stale', note: `observed ${days} day(s) ago - beyond the ${FRESH_DAYS}-day window` }
}

function Section({ title, available, source, observedAt, limits, children, empty }) {
  const f = freshnessOf(observedAt)
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 12 }}>{title}</strong>
        {available
          ? <span className="pill pill-muted">{source}</span>
          : <span className="pill pill-warn">UNKNOWN</span>}
        {available && <span className="text-low" style={{ fontSize: 11 }}>observed {observedAt ? String(observedAt).slice(0, 10) : 'UNKNOWN'} · {f.label} — {f.note}</span>}
      </div>
      {available ? children : <div className="text-low" style={{ fontSize: 11 }}>{empty}</div>}
      {limits && limits.length > 0 && (
        <div className="text-low" style={{ fontSize: 10, marginTop: 2 }}>{limits.join(' ')}</div>
      )}
    </div>
  )
}

export default function MasterBrainPanel({ title = 'Studio evidence (read-only)' }) {
  const [state, setState] = useState({ state: 'loading' })

  useEffect(() => {
    let alive = true
    fetchMasterBrainContext().then(r => { if (alive) setState(r) })
    return () => { alive = false }
  }, [])

  return (
    <div className="card" style={{ padding: 14 }} data-testid="master-brain-panel">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{title}</strong>
        <span className="pill pill-muted">read-only</span>
        <span className="pill pill-muted">no provider calls</span>
      </div>

      {state.state === 'loading' && <div className="text-low" style={{ fontSize: 11, marginTop: 8 }}>Loading the Studio evidence…</div>}
      {state.state === 'error' && (
        <div className="alert alert-warn" style={{ marginTop: 8 }}>
          <div className="alert-title">Studio evidence is UNKNOWN</div>
          <div className="alert-text" style={{ fontSize: 11 }}>Reason: {state.reason}. This is not an empty dataset.</div>
        </div>
      )}

      {state.state === 'ready' && (
        <>
          <Section
            title="Brand voice"
            available={!!(state.brand_voice && state.brand_voice.available)}
            source={state.brand_voice && state.brand_voice.source_label ? `${state.brand_voice.source} (${state.brand_voice.source_label})` : state.brand_voice && state.brand_voice.source}
            observedAt={state.brand_voice && state.brand_voice.observed_at}
            limits={state.brand_voice && state.brand_voice.limits}
            empty="No brand-voice file has been imported in the Studio; the field set is UNKNOWN."
          >
            <div className="text-low" style={{ fontSize: 11 }}>
              {Object.entries(state.brand_voice.fields).map(([k, v]) => (
                <div key={k}><strong>{k}</strong>: {v}</div>
              ))}
            </div>
          </Section>

          <Section
            title="Imported keywords"
            available={!!(state.keywords && state.keywords.available)}
            source={state.keywords && state.keywords.source_label ? `${state.keywords.source} (${state.keywords.source_label})` : state.keywords && state.keywords.source}
            observedAt={state.keywords && state.keywords.observed_at}
            limits={state.keywords && state.keywords.limits}
            empty="No keyword list has been imported in the Studio; UNKNOWN, not empty."
          >
            <div className="text-low" style={{ fontSize: 11 }}>
              {state.keywords.items.slice(0, 12).map((k, i) => (
                <div key={i}>{k.term}{k.volume === null || k.volume === undefined ? ' · volume UNKNOWN' : ` · volume ${k.volume}`}</div>
              ))}
              {state.keywords.items.length > 12 && <div>… {state.keywords.items.length - 12} more</div>}
            </div>
          </Section>

          <Section
            title="Search-term evidence"
            available={!!(state.search_terms && state.search_terms.available)}
            source={state.search_terms && state.search_terms.source}
            observedAt={null}
            limits={state.search_terms && state.search_terms.limits}
            empty="No search-term reports have been imported in the Studio; the evidence is UNKNOWN."
          >
            <div className="text-low" style={{ fontSize: 11 }}>
              {state.search_terms.items.slice(0, 8).map((t, i) => (
                <div key={i}>{t.term} · clicks {t.clicks} · impressions {t.impressions} · {t.kind === 'brand_analytics_sqp' ? 'BA SQP' : 'SP terms'}</div>
              ))}
              <div style={{ marginTop: 2 }}>{state.search_terms.bias}</div>
            </div>
          </Section>

          <Section
            title="Listing records"
            available={!!(state.listing_records && state.listing_records.available)}
            source={state.listing_records && state.listing_records.source}
            observedAt={state.listing_records && state.listing_records.items[0] && state.listing_records.items[0].observed_at}
            limits={state.listing_records && state.listing_records.limits}
            empty="No listing records exist in the tenant store yet; UNKNOWN."
          >
            <div className="text-low" style={{ fontSize: 11 }}>
              {state.listing_records.items.slice(0, 8).map((r, i) => (
                <div key={i}>{r.asin} — {r.title || '(untitled)'}</div>
              ))}
            </div>
          </Section>

          <div className="text-low" style={{ fontSize: 10, marginTop: 10 }}>{state.note}</div>
        </>
      )}
    </div>
  )
}
