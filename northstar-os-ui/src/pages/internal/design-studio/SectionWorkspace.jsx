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
import CompositingSurface from './CompositingSurface.jsx'
import { PEOPLE_CLASSES, DISCLOSURE_KEYWORD } from '../../../studio/engine/disclosure.js'
import { FIDELITY_MODES } from '../../../studio/engine/fidelity.js'
import { packToMarkdown } from '../../../studio/engine/outputPacks.js'

// -- Fields EVERY section gets ---------------------------------------------
// The disclosure classification, the fidelity mode and the technical rules are
// not optional extras on one page: they apply to every asset the studio can
// produce, so they are appended to every section's own field list.
export const SHARED_FIELDS = [
  {
    id: 'fidelityMode', kind: 'select', label: 'Product fidelity',
    options: FIDELITY_MODES.map(m => ({ value: m.id, label: m.label })),
    note: 'How the product itself was produced. "Product region generated" blocks export: the product is never generated, only the scene around it.',
  },
  {
    id: 'peopleClass', kind: 'select', label: 'People in this asset',
    options: [{ value: '', label: '- not answered -' }].concat(PEOPLE_CLASSES.map(c => ({ value: c.id, label: c.label }))),
    note: 'There is NO default. Export stays blocked until this is answered. The studio CANNOT detect AI-generated people from pixels; this is your declaration, and the studio only knows what it generated itself.',
    source: 'img-guide / ai-announce', pulled: '2026-10-10',
  },
  {
    id: 'studioGeneratedPerson', kind: 'toggle',
    label: 'The studio generated a person for this asset',
    note: 'If this is on, an answer of "no people" is a CONFLICT and export is blocked: the studio knows it drew a person.',
  },
  { id: 'syntheticPerformerTag', kind: 'toggle', label: 'Write the XMP marker (contains-synthetic-performer)', note: 'Written to dc:subject, then re-read from the exported file to prove it survived the export path.' },
  {
    id: 'identifiableIndividual', kind: 'toggle',
    label: 'Intended to look like a real, identifiable individual',
    note: 'NOT a disclosure question and NEVER a tag. A likeness of a real person is a consent and right-of-publicity matter; a marker does not cure it. Turning this on BLOCKS export.',
    source: 'ny-statute', pulled: '2026-10-10',
  },
  {
    id: 'expressiveWorkAd', kind: 'toggle',
    label: 'Exemption: ad for a film, TV programme, streaming content or video game',
    note: 'Documented carve-out. The synthetic performer appears in the expressive work itself, so the tagging rule does not apply.',
    source: 'ny-statute / ai-announce', pulled: '2026-10-10',
  },
  {
    id: 'translationOnly', kind: 'toggle',
    label: 'Exemption: AI used only for language translation',
    note: 'Documented carve-out. Dubbing or translating an existing advertisement is not creating a synthetic performer.',
    source: 'ny-statute', pulled: '2026-10-10',
  },
  {
    id: 'audioOnly', kind: 'toggle',
    label: 'Exemption: audio-only advertisement',
    note: 'Documented carve-out. The New York statute expressly does not apply to audio advertisements, so this rule set must not fire. An audio asset must NOT be asked for the marker.',
    source: 'ny-statute', pulled: '2026-10-10',
  },
  { id: 'filename', kind: 'text', label: 'Export filename', placeholder: 'B01ABCDEFG.main.jpg', note: 'Amazon documents the pattern ID.VARIANT.ext.', source: 'img-guide', pulled: '2026-10-10' },
  { id: 'dpi', kind: 'number', min: 1, max: 1200, label: 'Density (dpi)', note: 'At least 72 dpi.' },
  { id: 'colorSpace', kind: 'select', label: 'Colour space', options: [{ value: 'sRGB', label: 'sRGB' }, { value: 'CMYK', label: 'CMYK (converted, may shift)' }] },
  { id: 'units', kind: 'number', min: 1, max: 99, label: 'Units shown', note: 'Main image: one unit plus included accessories.' },
  { id: 'mannequin', kind: 'toggle', label: 'A mannequin is shown', note: 'Prohibited on the main image.' },
  { id: 'packagingShown', kind: 'toggle', label: 'Packaging is shown', note: 'Allowed only when the packaging itself is a product feature.' },
]

// A rule note every section shows, so the disclosure obligation is visible on
// the surface where the asset is made rather than buried in a policy page.
export const SHARED_RULES = [
  { label: 'AI-generated people must be declared', tone: 'block', detail: `Amazon requires the keyword "${DISCLOSURE_KEYWORD}" in the dc:subject (XMP) field for media containing photorealistic AI-generated people, before upload, in all worldwide stores. The string is exact.`, source: 'ai-announce / img-guide - 2026-10-10' },
  { label: 'The tag is not the New York disclosure', tone: 'flag', detail: 'The XMP marker is invisible to shoppers and does NOT satisfy the New York conspicuous-disclosure duty. Tagging the file is the Amazon workflow; the statutory legend is separate.', source: 'ny-statute - 2026-10-10' },
  { label: 'A reported export hazard', tone: 'flag', detail: 'Sellers report that live listing copies lose the tag after Amazon reprocesses the image. Keep tagged originals and a record of which files contain AI people.', source: 'ai-live-loss - 2026-10-10' },
]

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
  if (f.kind === 'select') {
    return (
      <label className="ss-field">
        <span className="ss-field-label">{f.label}{f.required && <span className="ss-req"> required</span>}</span>
        <select value={value ?? ''} onChange={e => onChange(e.target.value)}>
          {(f.options || []).map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        {f.note && <span className="ss-field-note">{f.note}</span>}
        {f.source && <span className="ss-field-src">{f.source} - {f.pulled || '2026-10-10'}</span>}
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
  canvasFitWidth = 560, children, testId, storyboardOnly = false, packBuilder = null, packLabel = 'Pack',
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
    // The WHOLE collected field set flows into the document, so a rule can read
    // any field a section declares without this component knowing the rule.
    // Enumerating keys here is how the disclosure and fidelity fields would
    // silently never reach the pre-flight.
    meta: {
      ...meta,
      altText: meta['altText'] || '',
      syntheticPeople: !!meta['syntheticPeople'],
      syntheticPerformerTag: !!meta['syntheticPerformerTag'],
      studioGeneratedPerson: !!meta['studioGeneratedPerson'],
      durationSeconds: meta['durationSeconds'] ?? (spec.media === 'video' ? spec.durationRecommended || 0 : undefined),
    },
  }), [doc, spec, meta])

  const report = useMemo(() => checkCompliance(docForCheck, {
    durationSeconds: spec.media === 'video' ? Number(docForCheck.meta.durationSeconds || 0) : undefined,
  }), [docForCheck, spec])

  const pickSpec = useCallback((s) => { setSpecId(s.id) }, [])
  void canvasFitWidth

  const setField = (id) => (v) => setMeta(m => ({ ...m, [id]: v }))

  const tabs = [
    { id: 'specs', label: 'Format', icon: 'grid', note: 'Formats from the spec registry, labelled VERIFIED / REPORTED.' },
    { id: 'fields', label: 'Fields', icon: 'edit', note: 'Section fields plus the shared disclosure, fidelity and technical fields. Required fields are enforced by the pre-flight.' },
    { id: 'rules', label: 'Rules', icon: 'shield', note: 'What Amazon documents for these formats.' },
  ]

  const allFields = [...fields, ...SHARED_FIELDS]
  const allRules = [...ruleNotes, ...SHARED_RULES]

  const exportDisabled = report.verdict === 'block'

  // A section may attach an output-pack builder (storyboard / asset pack /
  // spec sheet). The pack is a document built from the operator's own fields
  // and this pre-flight report; nothing is rendered or generated.
  const downloadPack = useCallback(() => {
    if (!packBuilder) return
    try {
      const pack = packBuilder({ spec, meta, report })
      const md = packToMarkdown(pack)
      const blob = new Blob([md], { type: 'text/markdown' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${pack.kind || 'pack'}-${spec.id}.md`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('pack build failed', e)
    }
  }, [packBuilder, spec, meta, report])

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
          <>
            {packBuilder && (
              <button className="btn btn-sm" disabled={exportDisabled} onClick={downloadPack}
                data-testid="pack-download"
                title={exportDisabled
                  ? 'The pre-flight blocks: the pack would be a checklist, not an upload-ready document.'
                  : 'Download the section output pack (a plan; nothing is rendered).'}>
                <Icon name="file" size={13} /> {packLabel}
              </button>
            )}
            <button className="btn btn-sm btn-primary" disabled={exportDisabled}
              title={exportDisabled
                ? (conf === 'UNSOURCED' ? 'This format has no recorded Amazon source, so export is refused.' : 'The pre-flight blocks export until every blocking rule passes.')
                : 'Export becomes available when the pre-flight does not block.'}>
              <Icon name="download" size={13} /> Export
            </button>
          </>
        }
      />

      <div className="ss-shell-mid">
        <StudioLeftRail tabs={tabs} active={tab} onSelect={setTab}>
          {tab === 'specs' && <RegistrySpecPicker groups={groups} value={specId} onChange={pickSpec} />}
          {tab === 'fields' && (
            <div className="stack" style={{ gap: 10 }}>
              {allFields.map(f => (
                <Field key={f.id} f={f} value={meta[f.id]} onChange={setField(f.id)} />
              ))}
            </div>
          )}
          {tab === 'rules' && (
            <div className="stack" style={{ gap: 8 }}>
              {allRules.map((r, i) => (
                <div key={i} className={`ss-rule ss-rule-${r.tone || 'flag'}`}>
                  <div className="ss-rule-label">{r.label}</div>
                  <div className="ss-rule-detail">{r.detail}</div>
                  <div className="ss-rule-source">{r.source}</div>
                </div>
              ))}
            </div>
          )}
        </StudioLeftRail>

        {/* The real compositing surface owns the canvas, the inspector and the
            export pipeline for every section it drives: layers, a locked
            reference, the safe-zone overlay, undo/redo, the compare step and
            the six-step export. It reads THIS section's registry spec. */}
        <div className="cs-embed" style={{ gridColumn: '2 / -1', minWidth: 0 }}>
          {children || <CompositingSurface specId={specId} storyboardOnly={storyboardOnly} />}
        </div>

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
