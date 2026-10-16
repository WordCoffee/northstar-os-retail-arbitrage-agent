// ═══════════════════════════════════════════════════════════════════════════
// STUDIO COMPONENT — MASTER-BRAIN EVIDENCE STRIP (Phase 9 item 2; v2 2026-10-16)
//
// A READ-ONLY view of the Studio's imported evidence, rendered inside other
// rooms (ListingForge, AdPilot, SocialPulse, and five more).
//
// v2 layout: a compact four-cell strip answers "what evidence do I actually
// have?" above the fold; the full detail — sources, freshness, limits and
// rows — expands on demand behind the Details button. Every missing section
// still reads UNKNOWN, never zero. No provider is contacted by this component
// or the endpoint behind it.
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

function Cell({ label, ok, value, title }) {
  return (
    <div className={`mbp-cell${ok ? '' : ' is-unknown'}`} title={title || ''}>
      <div className="mbp-label">
        <span className={`nav-dot ${ok ? 'nav-dot-ok' : 'nav-dot-ochre'}`} />
        {label}
      </div>
      <div className="mbp-value" title={value}>{value}</div>
    </div>
  )
}

export default function MasterBrainPanel({ title = 'Studio evidence (read-only)' }) {
  const [state, setState] = useState({ state: 'loading' })
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let alive = true
    fetchMasterBrainContext().then(r => { if (alive) setState(r) })
    return () => { alive = false }
  }, [])

  const bv = state.state === 'ready' ? (state.brand_voice || {}) : {}
  const kw = state.state === 'ready' ? (state.keywords || {}) : {}
  const st = state.state === 'ready' ? (state.search_terms || {}) : {}
  const lr = state.state === 'ready' ? (state.listing_records || {}) : {}

  return (
    <div className="card" style={{ padding: '12px 14px' }} data-testid="master-brain-panel">
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 13 }}>{title}</strong>
        <span className="pill pill-muted">read-only</span>
        <span className="pill pill-muted">no provider calls</span>
        {state.state === 'ready' && (
          <button
            className="btn btn-sm btn-ghost"
            style={{ marginLeft: 'auto' }}
            onClick={() => setOpen(o => !o)}
          >
            {open ? 'Hide details' : 'Details'}
          </button>
        )}
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
          <div className="mbp-grid">
            <Cell
              label="Brand voice"
              ok={!!bv.available}
              value={bv.available ? `${Object.keys(bv.fields || {}).length} fields` : 'UNKNOWN — no file imported'}
              title={bv.available
                ? 'Imported brand-voice file; open Details for the fields.'
                : 'No brand-voice file has been imported in the Studio; the field set is UNKNOWN.'}
            />
            <Cell
              label="Keywords"
              ok={!!kw.available}
              value={kw.available ? `${(kw.items || []).length} terms` : 'UNKNOWN — no list imported'}
              title={kw.available
                ? 'Imported keyword list; open Details for terms and volumes.'
                : 'No keyword list has been imported in the Studio; UNKNOWN, not empty.'}
            />
            <Cell
              label="Search terms"
              ok={!!st.available}
              value={st.available ? `${(st.items || []).length} rows` : 'UNKNOWN — no reports imported'}
              title={st.available
                ? 'Imported search-term reports; the click-only bias caveat travels with the rows.'
                : 'No search-term reports have been imported in the Studio; the evidence is UNKNOWN.'}
            />
            <Cell
              label="Listings"
              ok={!!lr.available}
              value={lr.available ? `${(lr.items || []).length} records` : 'UNKNOWN — tenant store empty'}
              title={lr.available
                ? 'Listing records in the tenant store.'
                : 'No listing records exist in the tenant store yet; UNKNOWN.'}
            />
          </div>

          {!open && (
            <div className="text-low" style={{ fontSize: 10.5, marginTop: 8 }}>
              Read-only Studio evidence · missing sections read UNKNOWN, never zero. Import files in the Design Studio to fill these cells.
            </div>
          )}

          {open && (
            <div>
              <Section
                title="Brand voice"
                available={!!bv.available}
                source={bv.source_label ? `${bv.source} (${bv.source_label})` : bv.source}
                observedAt={bv.observed_at}
                limits={bv.limits}
                empty="No brand-voice file has been imported in the Studio; the field set is UNKNOWN."
              >
                <div className="text-low" style={{ fontSize: 11 }}>
                  {Object.entries(bv.fields || {}).map(([k, v]) => (
                    <div key={k}><strong>{k}</strong>: {v}</div>
                  ))}
                </div>
              </Section>

              <Section
                title="Imported keywords"
                available={!!kw.available}
                source={kw.source_label ? `${kw.source} (${kw.source_label})` : kw.source}
                observedAt={kw.observed_at}
                limits={kw.limits}
                empty="No keyword list has been imported in the Studio; UNKNOWN, not empty."
              >
                <div className="text-low" style={{ fontSize: 11 }}>
                  {(kw.items || []).slice(0, 12).map((k, i) => (
                    <div key={i}>{k.term}{k.volume === null || k.volume === undefined ? ' · volume UNKNOWN' : ` · volume ${k.volume}`}</div>
                  ))}
                  {(kw.items || []).length > 12 && <div>… {kw.items.length - 12} more</div>}
                </div>
              </Section>

              <Section
                title="Search-term evidence"
                available={!!st.available}
                source={st.source}
                observedAt={null}
                limits={st.limits}
                empty="No search-term reports have been imported in the Studio; the evidence is UNKNOWN."
              >
                <div className="text-low" style={{ fontSize: 11 }}>
                  {(st.items || []).slice(0, 8).map((t, i) => (
                    <div key={i}>{t.term} · clicks {t.clicks} · impressions {t.impressions} · {t.kind === 'brand_analytics_sqp' ? 'BA SQP' : 'SP terms'}</div>
                  ))}
                  <div style={{ marginTop: 2 }}>{st.bias}</div>
                </div>
              </Section>

              <Section
                title="Listing records"
                available={!!lr.available}
                source={lr.source}
                observedAt={(lr.items || [])[0] && lr.items[0].observed_at}
                limits={lr.limits}
                empty="No listing records exist in the tenant store yet; UNKNOWN."
              >
                <div className="text-low" style={{ fontSize: 11 }}>
                  {(lr.items || []).slice(0, 8).map((r, i) => (
                    <div key={i}>{r.asin} — {r.title || '(untitled)'}</div>
                  ))}
                </div>
              </Section>

              <div className="text-low" style={{ fontSize: 10, marginTop: 10 }}>{state.note}</div>
            </div>
          )}
        </>
      )}
    </div>
  )
}
