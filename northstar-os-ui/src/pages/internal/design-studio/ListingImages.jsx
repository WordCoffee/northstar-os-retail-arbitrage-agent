// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — SECTION: LISTING IMAGES
//
// The reference Phase 2 workspace. Built on the editor shell:
//   left rail   — specs (from the spec registry) + gallery slots
//   canvas      — the format at its real aspect ratio with Amazon safe zones
//   inspector   — properties + the compliance pre-flight (blocks/warns/passes)
//   bottom strip— the gallery slots (main + secondaries), add/remove
//
// HONESTY CONTRACT
//   • Sizes come from the spec registry, which cites a source URL per row.
//   • The pre-flight is deterministic: it reads the document, never a model.
//   • A format with no safe-zone data says so instead of inventing one.
//   • Nothing claims image text improves ranking; Amazon documents the
//     opposite for external search and screen readers.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useToast } from '../../../components/ToastContext.jsx'
import Icon from '../../../components/Icon.jsx'
import {
  StudioTopBar, StudioLeftRail, StudioBottomStrip, StudioEmpty, VerdictPill,
  useStudioZoom,
} from '../../../studio/components/StudioShell.jsx'
import { SPEC_GROUPS, specById, AMAZON_CAPS } from '../../../studio/engine/specRegistry.js'
import { checkCompliance } from '../../../studio/engine/compliance.js'
import { createDoc } from '../../../studio/engine/doc.js'
import { RegistrySpecPicker, ConfidenceTag } from './SectionWorkspace.jsx'
import CompositingSurface from './CompositingSurface.jsx'

const GALLERY_IMAGE_SPECS = SPEC_GROUPS.filter(g => g.id === 'Gallery')

const LEFT_TABS = [
  { id: 'specs', label: 'Format', icon: 'grid', note: 'Every Amazon listing format, from the spec registry.' },
  { id: 'product', label: 'Product', icon: 'product', note: 'Attach a live catalogue row. No demo rows are shown.' },
  { id: 'slots', label: 'Slots', icon: 'layers', note: 'Main + secondary slots from the flat-file schema.' },
  { id: 'rules', label: 'Rules', icon: 'shield', note: 'What Amazon documents for this format.' },
]

// Load live products only. The finder route already filters data_kind='live',
// so a demo row can never appear here.
function useLiveProducts() {
  const [products, setProducts] = useState([])
  const [state, setState] = useState('idle') // idle | loading | error | ready
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setState('loading'); setError('')
    try {
      const res = await fetch('/api/products/finder?limit=24', { credentials: 'include' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      const rows = data.candidates || data.products || data.rows || []
      setProducts(rows)
      setState('ready')
    } catch (e) {
      setError(String(e.message || e))
      setState('error')
    }
  }, [])
  return { products, state, error, load }
}

// The gallery slot plan, straight from the flat-file column schema.
const SLOT_PLAN = [
  { col: 'main_image_url', label: 'Main', role: 'main', specId: 'amz-main' },
  { col: 'other_image_url1', label: 'Secondary 1', role: 'secondary', specId: 'amz-secondary' },
  { col: 'other_image_url2', label: 'Secondary 2', role: 'secondary', specId: 'amz-secondary' },
  { col: 'other_image_url3', label: 'Secondary 3', role: 'secondary', specId: 'amz-secondary' },
  { col: 'other_image_url4', label: 'Secondary 4', role: 'secondary', specId: 'amz-secondary' },
  { col: 'swatch_image_url', label: 'Swatch', role: 'swatch', specId: 'amz-secondary' },
]

function SlotLabel({ slot }) {
  return (
    <>
      <Icon name={slot.role === 'main' ? 'star' : 'image'} size={12} />
      {slot.label}
    </>
  )
}

export default function ListingImages({ product: initialProduct, asin: initialAsin }) {
  const { toast } = useToast()
  const [tab, setTab] = useState('specs')
  const [specId, setSpecId] = useState('amz-main')
  const [showSafeZones, setShowSafeZones] = useState(true)
  const [slotId, setSlotId] = useState('main_image_url')
  const [zoom, setZoom] = useStudioZoom(1)
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [product, setProduct] = useState(initialProduct || null)
  const asin = product?.asin || initialAsin
  const live = useLiveProducts()
  useEffect(() => { if (!initialProduct) live.load() }, [initialProduct, live.load])

  const spec = specById(specId) || specById('amz-main')

  // A real document for the chosen format. Text/badge layers stay empty until
  // the operator adds them — the workspace never seeds content.
  const [doc, setDoc] = useState(() => createDoc({ w: 2000, h: 2000, name: 'Listing main image' }))
  const docForCompliance = useMemo(() => ({
    ...doc,
    w: spec.w, h: spec.h,
    formatId: spec.id,
    channel: spec.channel,
    family: spec.group,
    media: spec.media,
    meta: {
      ...(doc.meta || {}),
      altText: doc.meta?.altText || '',
      syntheticPeople: !!doc.meta?.syntheticPeople,
      syntheticPerformerTag: !!doc.meta?.syntheticPerformerTag,
    },
  }), [doc, spec])

  const report = useMemo(() => checkCompliance(docForCompliance, {
    listingCopy: product?.title || '',
    durationSeconds: spec.media === 'video' ? (doc.meta?.durationSeconds || 0) : undefined,
  }), [docForCompliance, product, spec])

  const pickSpec = useCallback((s) => {
    setSpecId(s.id)
    setDoc(d => ({ ...d, w: s.w, h: s.h, name: s.label }))
    toast(`${s.label} — ${s.w}×${s.h}. Specs loaded from ${s.source || 'the registry'}.`, 'info')
  }, [toast])

  const aspect = spec.w / spec.h

  return (
    <div className="ss-shell" data-testid="listing-images-workspace">
      <StudioTopBar
        title="Listing Images"
        subtitle={product ? `${product.title || asin} · ${asin || ''}` : 'No product attached'}
        zoom={zoom} onZoom={setZoom} onFit={() => { setZoom(1); setPan({ x: 0, y: 0 }) }}
        showSafeZones={showSafeZones} onToggleSafeZones={setShowSafeZones}
        safeZoneNote={spec.safe ? undefined : 'No safe zone is recorded for this format'}
        status={<><VerdictPill verdict={report.verdict} /> <ConfidenceTag spec={spec} /></>}
        actions={
          <button className="btn btn-sm btn-primary" disabled={report.verdict === 'block'}
            title={report.verdict === 'block' ? 'The pre-flight blocks export until every blocking rule passes.' : 'Export is available when the pre-flight does not block.'}>
            <Icon name="download" size={13} /> Export
          </button>
        }
      />

      <div className="ss-shell-mid">
        <StudioLeftRail tabs={LEFT_TABS} active={tab} onSelect={setTab}>
          {tab === 'specs' && (
            <RegistrySpecPicker groups={GALLERY_IMAGE_SPECS} value={specId} onChange={pickSpec} />
          )}
          {tab === 'product' && (
            <div className="stack" style={{ gap: 8 }}>
              {live.state === 'loading' && <div className="text-low" style={{ fontSize: 12 }}>Loading live products...</div>}
              {live.state === 'error' && (
                <div className="ss-rule ss-rule-flag">
                  <div className="ss-rule-label">Could not load the catalogue</div>
                  <div className="ss-rule-detail">{live.error}. The workspace stays empty rather than showing demo rows.</div>
                </div>
              )}
              {live.state === 'ready' && live.products.length === 0 && (
                <StudioEmpty
                  title="No live products yet"
                  what="The catalogue has no data_kind = live rows for this finder. Run a SourceScout pull to populate it - demo rows are never shown here."
                  actionLabel="Go to SourceScout"
                  onAction={() => toast('Open SourceScout from the rail to run a catalogue pull.', 'info')}
                />
              )}
              {live.state === 'ready' && live.products.map(p => (
                <button key={p.asin}
                  className={`ss-spec ${asin === p.asin ? 'active' : ''}`}
                  onClick={() => { setProduct(p); toast(`Attached ${p.asin}.`, 'info') }}>
                  <span className="ss-spec-name">{p.name || p.title || p.asin}</span>
                  <span className="text-mono ss-spec-dims">{p.asin}</span>
                </button>
              ))}
            </div>
          )}
          {tab === 'slots' && (
            <div className="stack" style={{ gap: 6 }}>
              {SLOT_PLAN.map(s => (
                <button key={s.col}
                  className={`ss-spec ${slotId === s.col ? 'active' : ''}`}
                  onClick={() => { setSlotId(s.col); pickSpec(specById(s.specId)) }}>
                  <span className="ss-spec-name">{s.label}</span>
                  <span className="text-mono ss-spec-dims">{s.col}</span>
                </button>
              ))}
            </div>
          )}
          {tab === 'rules' && (
            <div className="stack" style={{ gap: 8 }}>
              <div className="ss-rule ss-rule-block">
                <div className="ss-rule-label">Main image and search</div>
                <div className="ss-rule-detail">Amazon suppresses a listing from search and browse until the main image meets every category rule.</div>
                <div className="ss-rule-source">suppression help page · 2026-10-10</div>
              </div>
              <div className="ss-rule ss-rule-flag">
                <div className="ss-rule-label">Lifestyle main images are the exception, not the rule</div>
                <div className="ss-rule-detail">A lifestyle main image is allowed only for BED, BED_FRAME, MATTRESS, RUG, RUG_PAD and SOFA. Every other category needs pure white.</div>
                <div className="ss-rule-source">style guides · 2026-10-10</div>
              </div>
              <div className="ss-rule ss-rule-flag">
                <div className="ss-rule-label">Each child ASIN needs its own main image</div>
                <div className="ss-rule-detail">A variation family is suppressed per child. Fixing the parent leaves non-compliant children invisible in search.</div>
                <div className="ss-rule-source">Seller Labs analysis · 2026-10-10</div>
              </div>
            </div>
          )}
        </StudioLeftRail>

        {/* The real compositing surface owns the canvas, the inspector and the
            export pipeline from here: layers, a locked reference, the
            safe-zone overlay, undo/redo and the human compare step. */}
        <div className="cs-embed" style={{ gridColumn: '2 / -1', minWidth: 0 }}>
          <CompositingSurface specId={specId} />
        </div>
      </div>

      <StudioBottomStrip
        items={SLOT_PLAN}
        active={slotId}
        onSelect={(s) => { setSlotId(s.col); pickSpec(specById(s.specId)) }}
        renderItem={(s) => (<><Icon name={s.role === 'main' ? 'star' : 'image'} size={12} />{s.label}</>)}
        actions={<span className="text-low" style={{ fontSize: 11 }}>{SLOT_PLAN.length} slots · {report.checked ?? report.ready}/{report.total} rules decided</span>}
      />
    </div>
  )
}
