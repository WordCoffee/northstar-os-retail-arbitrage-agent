// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — GENERIC SECTION WORKSPACE
//
// Every remaining section (A+ / Brand Story, Storefront, Ads, Video & UGC,
// Social, Packaging) is a CONFIGURATION of this component, so a spec can only
// ever come from the registry and a compliance rule can only ever come from the
// engine. A section file declares: which spec groups it offers, which extra
// fields it collects, and which rule notes it shows.
//
// HONESTY CONTRACT
//   • Specs render from the registry with a VERIFIED / REPORTED / UNSOURCED
//     confidence label, a source id and a pulled-at date.
//   • Export is disabled whenever the pre-flight blocks.
//   • An unsourced format (e.g. the SP video row) cannot be exported at all.
//   • Fields never make an SEO claim. Alt text is described as a required
//     field that must describe the image for screen readers.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useMemo, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import {
  StudioTopBar, StudioLeftRail, StudioCanvas, StudioInspector, InspectorSection,
  StudioBottomStrip, CompliancePanel, StudioEmpty, VerdictPill, useStudioZoom,
} from '../../../studio/components/StudioShell.jsx'
import { SPEC_GROUPS, specById, SPEC_SOURCES, confidenceOf, AMAZON_CAPS, AI_POLICY } from '../../../studio/engine/specRegistry.js'
import { checkCompliance } from '../../../studio/engine/compliance.js'
import { createDoc } from '../../../studio/engine/doc.js'

const CONFIDENCE_PILL = {
  VERIFIED: { cls: 'pill-ok', label: 'VERIFIED', title: 'Sourced from an Amazon-owned page (Seller Central / Ads help / Amazon PDF).' },
  REPORTED: { cls: 'pill-warn', label: 'REPORTED', title: 'Third-party source. Not confirmed against an Amazon page — verify before relying on it.' },
  UNSOURCED: { cls: 'pill-error', label: 'UNSOURCED', title: 'No source recorded. Export is refused.' },
}

function SourceLine({ spec }) {
  const src = SPEC_SOURCES[spec.source]
  return (
    <div className="ss-rule-source">
      {spec.source || 'registry'} · pulled {src?.pulled || '2026-10-10'}
      {spec.dateSensitive ? ' · date-sensitive' : ''}
      {src?.url ? <> · <a href={src.url} target="_blank" rel="noreferrer noopener">source</a></> : null}
    </div>
  )
}

// ── Spec picker with confidence tagging ─────────────────────────────────────
export function ConfidenceTag({ spec }) {
  const c = CONFIDENCE_PILL[confidenceOf(spec)] || CONFIDENCE_PILL.REPORTED
  return (
    <span className="pill ${c.cls}" title={c.title} style={{ fontSize: 9 }}>{c.label}</span>
  )
}

export function RegistrySpecPicker({ groups, value, onChange }) {
  return (
    <div className="ss-specs" data-testid="spec-picker">
      {groups.map(g => (
        <div key={g.id} className="ss-spec-group">
          <div className="ss-spec-group-label">{g.label}</div>
          {g.specs.map(s => (
            <button key={s.id} className={`ss-spec ${value === s.id ? 'active' : ''}`}
              onClick={() => onChange(s)} title={s.note || `${s.w}×${s.h}`}>
              <span className="ss-spec-top">
                <span className="ss-spec-name">{s.label}</span>
                <ConfidenceTag spec={s} />
              </span>
              <span className="text-mono ss-spec-dims">{s.w}×{s.h}
                {s.media === 'video' ? ` · ${s.durationMin}-${s.durationMax}s` : ''}
                {s.maxBytes ? ` · ${Math.round(s.maxBytes / 1024)} KB` : ''}
              </span>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Field renderer ──────────────────────────────────────────────────────────
function Field({ f, value, onChange }) {
  if (f.kind === 'toggle') {
    return (
      <label className="ss-field ss-field-toggle">
        <input type="checkbox" checked={!!value} onChange={e => onChange(e.target.checked)} />
        <span>{f.label}</span>
        {f.note && <span className="ss-field-note">{f.note}</span>}
      </label>
    )
  }
  if (f.kind === 'number') {
    return (
      <label className="ss-field">
        <span className="ss-field-label">{f.label}{f.required && <span className="ss-req"> required</span>}</span>
        <input type="number" value={value ?? ''} min={f.min} max={f.max}
          onChange={e => onChange(e.target.value === '' ? '' : Number(e.target.value))} />
        {f.note && <span className="ss-field-note">{f.note}</span>}
        {f.source && <span className="ss-field-src">{f.source} · {f.pulled || '2026-10-10'}</span>}
      </label>
    )
  }
  if (f.kind === 'textarea') {
    return (
      <label className="ss-field">
        <span className="ss-field-label">{f.label}{f.required && <span className="ss-req"> required</span>}</span>
        <textarea rows={f.rows || 3} value={value ?? ''} placeholder={f.placeholder || ''}
          onChange={e => onChange(e.target.value)} maxLength={f.maxLength} />
        {f.note && <span className="ss-field-note">{f.note}</span>}
        {f.source && <span className="ss-field-src">{f.source} · {f.pulled || '2026-10-10'}</span>}
        {f.maxLength && <span className="ss-field-count">{(value || '').length}/{f.maxLength}</span>}
      </label>
    )
  }
  return (
    <label className="ss-field">
      <span className="ss-field-label">{f.label}{f.required && <span className="ss-req"> required</span>}</span>
      <input type="text" value={value ?? ''} placeholder={f.placeholder || ''} maxLength={f.maxLength}
        onChange={e => onChange(e.target.value)} />
      {f.note && <span className="ss-field-note">{f.note}</span>}
      {f.source && <span className="ss-field-src">{f.source} · {f.pulled || '2026-10-10'}</span>}
      {f.maxLength && <span className="ss-field-count">{(value || '').length}/{f.maxLength}</span>}
    </label>
  )
}

export default function SectionWorkspace({
  title, subtitle, groups, defaultSpecId, fields = [], ruleNotes = [], slots = null,
  canvasFitWidth = 560, children, testId,
}) {
  const [specId, setSpecId] = useState(defaultSpecId)
  const [showSafeZones, setShowSafeZones] = useState(true)
  const [zoom, setZoom] = useStudioZoom(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [tab, setTab] = useState('specs')
  const [meta, setMeta] = useState({})
  const [slot, setSlot] = useState(slots ? slots[0].id : null)

  const spec = specById(specId) || specById(defaultSpecId)
  const conf = confidenceOf(spec)

  const [doc] = useState(() => createDoc({ w: 1000, h: 1000, name: 'Untitled' }))

  const docForCheck = useMemo(() => ({
    ...doc,
    w: spec.w, h: spec.h,
    formatId: spec.id,
    channel: spec.channel,
    family: spec.group,
    media: spec.media,
    meta: {
      altText: meta['altText'] || '',
      syntheticPeople: !!meta['syntheticPeople'],
      syntheticPerformerTag: !!meta['syntheticPerformerTag'],
      durationSeconds: meta['durationSeconds'] ?? (spec.media === 'video' ? spec.durationRecommended || 0 : undefined),
    },
  }), [doc, spec, meta])

  const report = useMemo(() => checkCompliance(docForCheck, {
    durationSeconds: spec.media === 'video' ? Number(docForCheck.meta.durationSeconds || 0) : undefined,
  }), [docForCheck, spec])

  const pickSpec = useCallback((s) => { setSpecId(s.id) }, [])

  const setField = (id) => (v) => setMeta(m => ({ ...m, [id]: v }))

  const tabs = [
    { id: 'specs', label: 'Format', icon: 'grid', note: 'Formats from the spec registry, labelled VERIFIED / REPORTED.' },
    ...(fields.length ? [{ id: 'fields', label: 'Fields', icon: 'edit', note: 'Section fields. Required fields are enforced by the pre-flight.' }] : []),
    { id: 'rules', label: 'Rules', icon: 'shield', note: 'What Amazon documents for these formats.' },
  ]

  const exportDisabled = report.verdict === 'block'

  return (
    <div className="ss-shell" data-testid={testId || 'section-workspace'}>
      <StudioTopBar
        title={title}
        subtitle={subtitle}
        zoom={zoom} onZoom={setZoom} onFit={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}
        showSafeZones={showSafeZones} onToggleSafeZones={setShowSafeZones}
        safeZoneNote={spec.safe ? undefined : 'No safe zone is recorded for this format'}
        status={<><VerdictPill verdict={report.verdict} /> <ConfidenceTag spec={spec} /></>}
        actions={
          <button className="btn btn-sm btn-primary" disabled={exportDisabled}
            title={exportDisabled
              ? (conf === 'UNSOURCED' ? 'This format has no recorded Amazon source, so export is refused.' : 'The pre-flight blocks export until every blocking rule passes.')
              : 'Export becomes available when the pre-flight does not block.'}>
            <Icon name="download" size={13} /> Export
          </button>
        }
      />

      <div className="ss-shell-mid">
        <StudioLeftRail tabs={tabs} active={tab} onSelect={setTab}>
          {tab === 'specs' && <RegistrySpecPicker groups={groups} value={specId} onChange={pickSpec} />}
          {tab === 'fields' && (
            <div className="stack" style={{ gap: 10 }}>
              {fields.map(f => (
                <Field key={f.id} f={f} value={meta[f.id]} onChange={setField(f.id)} />
              ))}
            </div>
          )}
          {tab === 'rules' && (
            <div className="stack" style={{ gap: 8 }}>
              {ruleNotes.map((r, i) => (
                <div key={i} className={`ss-rule ss-rule-${r.tone || 'flag'}`}>
                  <div className="ss-rule-label">{r.label}</div>
                  <div className="ss-rule-detail">{r.detail}</div>
                  <div className="ss-rule-source">{r.source}</div>
                </div>
              ))}
            </div>
          )}
        </StudioLeftRail>

        <StudioCanvas
          zoom={zoom} pan={pan} onPan={setPan} canvasAspect={spec.w / spec.h}
          safeZoneId={spec.safe} showSafeZones={showSafeZones} fitWidth={canvasFitWidth}
          onWheelZoom={(d) => setZoom(z => Math.max(0.1, Math.min(4, z + d)))}
        >
          {children || (
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff' }}>
              <StudioEmpty
                title={`${spec.label} — nothing placed yet`}
                what={`${spec.w}×${spec.h} px. Add artwork to this module to begin. Nothing is generated until the local engine is armed; this workspace arranges your own assets only.`}
                actionLabel={conf === 'UNSOURCED' ? undefined : 'Add artwork from the asset library'}
                onAction={conf === 'UNSOURCED' ? undefined : undefined}
                connect={conf === 'UNSOURCED'}
              />
            </div>
          )}
        </StudioCanvas>

        <StudioInspector>
          <InspectorSection title="Compliance pre-flight">
            <CompliancePanel report={report} />
          </InspectorSection>

          <InspectorSection title="Format">
            <div className="ss-rule">
              <div className="ss-rule-label">{spec.label} <ConfidenceTag spec={spec} /></div>
              <div className="ss-rule-detail">
                {spec.w}×{spec.h} px
                {spec.minW ? ` · min ${spec.minW} px` : ''}
                {spec.maxBytes ? ` · ${Math.round(spec.maxBytes / 1024)} KB cap` : ''}
                {spec.media === 'video' ? ` · ${spec.durationMin}-${spec.durationMax}s (${spec.durationRecommended}s recommended)` : ''}
                {spec.aspectDefault === false ? ' · NOT the default aspect' : ''}
              </div>
              {spec.note && <div className="ss-rule-detail">{spec.note}</div>}
              <SourceLine spec={spec} />
            </div>
          </InspectorSection>

          {spec.media === 'video' && (
            <InspectorSection title="Video spec (from the registry)">
              <div className="ss-rule">
                <div className="ss-rule-detail">
                  {AMAZON_CAPS.video.formats.join(' / ')} · {AMAZON_CAPS.video.codecs.join(' / ')} · Main or Baseline ·
                  {' '}{AMAZON_CAPS.video.videoBitrateMinMbps} Mbps+ video · audio {AMAZON_CAPS.video.audioBitrateMinKbps} kbps
                  {' '}at {(AMAZON_CAPS.video.audioSampleMinHz / 1000).toFixed(1)} kHz · fps {AMAZON_CAPS.video.fpsAllowed.join(', ')} ·
                  {' '}{Math.round(AMAZON_CAPS.video.maxBytes / 1048576)} MB cap.
                </div>
                <div className="ss-rule-source">sbv spec · 2026-10-10</div>
              </div>
            </InspectorSection>
          )}

          <InspectorSection title="Policy" defaultOpen={false}>
            <div className="ss-rule ss-rule-flag">
              <div className="ss-rule-label">AI people disclosure</div>
              <div className="ss-rule-detail">{AI_POLICY.syntheticPersonIptc.keyword} in {AI_POLICY.syntheticPersonIptc.field} when the image contains photorealistic AI-generated people.</div>
              <div className="ss-rule-source">A+ guidelines · 2026-10-10</div>
            </div>
            <div className="ss-rule ss-rule-flag" style={{ marginTop: 8 }}>
              <div className="ss-rule-label">Never Brand Registry proof</div>
              <div className="ss-rule-detail">{AI_POLICY.brandRegistryEnrollment.rule}</div>
              <div className="ss-rule-source">Brand Registry Application Guide · 2026-10-10</div>
            </div>
          </InspectorSection>
        </StudioInspector>
      </div>

      <StudioBottomStrip
        items={slots || [{ id: spec.id, label: spec.label }]}
        active={slot}
        onSelect={(s) => { setSlot(s.id); if (s.specId) setSpecId(s.specId) }}
        renderItem={(s) => (<><Icon name={s.icon || 'image'} size={12} />{s.label}</>)}
        actions={<span className="text-low" style={{ fontSize: 11 }}>{title} - {report.checked ?? report.ready}/{report.total} rules decided</span>}
      />
    </div>
  )
}
