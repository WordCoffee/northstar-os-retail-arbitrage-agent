// ═══════════════════════════════════════════════════════════════════════════
// DESIGN STUDIO — COMPOSITING SURFACE
//
// The real canvas. Layers, a locked reference, the safe-zone overlay, undo/redo
// and a human compare step, ending in the export pipeline.
//
// HONESTY CONTRACT
//   • The product is the operator's own photograph. Nothing is generated.
//   • Every layer is a real, editable object with a box you can see.
//   • Text is drawn as canvas vector text, never as generated pixels.
//   • Export runs the pipeline and reports each step's real status; a step that
//     did not run is never shown as passed.
//   • An unverified fidelity blocks export. We do not ship what we cannot check.
// ═══════════════════════════════════════════════════════════════════════════

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import { useToast } from '../../../components/ToastContext.jsx'
import {
  StudioCanvas, StudioLeftRail, StudioInspector, InspectorSection,
  StudioBottomStrip, VerdictPill, useUndo,
} from '../../../studio/components/StudioShell.jsx'
import { SAFE_ZONES, specById } from '../../../studio/engine/specRegistry.js'
import { renderDoc, exportComposite, summariseExport, compareStepStatus } from '../../../studio/engine/compose.js'
import { DEFAULT_THRESHOLD } from '../../../studio/engine/fidelity.js'
import { checkCompliance } from '../../../studio/engine/compliance.js'
import {
  verifyUploadedAsset, recheckEntry, recheckSummary, cureWindow, NOTICE_AND_CURE_DAYS,
  DISCLOSURE_KEYWORD, classifyDisclosure,
} from '../../../studio/engine/disclosure.js'

const LEFT_TABS = [
  { id: 'layers', label: 'Layers', icon: 'layers', note: 'Every layer is a real, editable object.' },
  { id: 'reference', label: 'Reference', icon: 'lock', note: 'Lock the real product photograph. Without a lock there is nothing to diff.' },
  { id: 'add', label: 'Add', icon: 'plus', note: 'Add the product photograph, a shape, or vector text.' },
  { id: 'library', label: 'Library', icon: 'stack', note: 'Export history, the upload check and the re-check log.' },
]

const uid = (p) => `${p}-${Math.random().toString(36).slice(2, 8)}`

// Local persistence for the re-check log. It is the operator's own record of
// when they verified a live asset, so it survives a reload.
const LOG_KEY = 'ns-ds-recheck-log'
const NOTICE_KEY = 'ns-ds-notices'

function readJson(key, fallback) {
  try { const raw = localStorage.getItem(key); return raw ? JSON.parse(raw) : fallback } catch { return fallback }
}
function writeJson(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* storage unavailable */ }
}

export default function CompositingSurface({ specId = 'amz-main', initialLayers = [], onExported }) {
  const { toast } = useToast()
  const spec = specById(specId) || specById('amz-main')
  const [tab, setTab] = useState('layers')
  const [selected, setSelected] = useState('')
  const [showZones, setShowZones] = useState(true)
  const [compareOpen, setCompareOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [lastExport, setLastExport] = useState(null)
  const canvasRef = useRef(null)

  const doc = useMemo(() => ({
    formatId: spec.id, w: spec.w, h: spec.h,
    channel: spec.channel, family: spec.group, media: spec.media,
    meta: {},
  }), [spec])

  const [layers, setLayers] = useState(() => (initialLayers.length ? initialLayers : [
    { id: uid('bg'), kind: 'bg', fill: spec.id === 'amz-main' ? '#ffffff' : '#f5f0e8' },
  ]))

  const history = useUndo(layers)
  const pushLayers = useCallback((next) => {
    setLayers(next)
    history.push(next)
  }, [history])

  const [reference, setReference] = useState(null)   // { dataUrl, name }
  const [confirm, setConfirm] = useState(null)        // { at, by }
  const [log, setLog] = useState(() => readJson(LOG_KEY, []))
  const [notices, setNotices] = useState(() => readJson(NOTICE_KEY, {}))
  const [uploadResult, setUploadResult] = useState(null)
  const [uploadName, setUploadName] = useState('')
  // The surface is where the asset is MADE, so it owns the disclosure fields
  // for that asset. Without them the upload check could only ever answer
  // "not-required", which is a false pass on an asset that needs the marker.
  const [dm, setDm] = useState({
    peopleClass: '', studioGeneratedPerson: false, syntheticPerformerTag: true,
    identifiableIndividual: false, filename: '',
  })

  const appendLog = useCallback((entry) => {
    setLog(prev => {
      const next = [entry, ...prev].slice(0, 200)
      writeJson(LOG_KEY, next)
      return next
    })
  }, [])

  const setNotice = useCallback((key, iso) => {
    setNotices(prev => {
      const next = { ...prev, [key]: iso || null }
      writeJson(NOTICE_KEY, next)
      return next
    })
  }, [])

  const workingDoc = useMemo(() => ({
    ...doc,
    layers,
    meta: {
      fidelityMode: reference ? 'locked' : 'placed',
      referenceDataUrl: reference ? reference.dataUrl : undefined,
      compareConfirmed: confirm || undefined,
      ...dm,
      ...(doc.meta || {}),
    },
  }), [doc, layers, reference, confirm, dm])

  const report = useMemo(() => checkCompliance(workingDoc), [workingDoc])

  // ── Render into the real canvas whenever the layers change ──────────────
  useEffect(() => {
    let cancelled = false
    const el = canvasRef.current
    if (!el) return
    renderDoc(workingDoc, (id) => layers.find(l => l.id === id)?.dataUrl)
      .then((src) => {
        if (cancelled) return
        el.width = src.width
        el.height = src.height
        const ctx = el.getContext('2d')
        ctx.clearRect(0, 0, el.width, el.height)
        ctx.drawImage(src, 0, 0)
      })
      .catch((e) => { if (!cancelled) toast(`Canvas render failed: ${e.message}`, 'warn') })
    return () => { cancelled = true }
  }, [workingDoc, layers, toast])

  // ── Layer operations ────────────────────────────────────────────────────
  const patch = useCallback((id, next) => {
    pushLayers(layers.map(l => (l.id === id ? { ...l, ...next } : l)))
  }, [layers, pushLayers])

  const remove = useCallback((id) => {
    pushLayers(layers.filter(l => l.id !== id))
    if (selected === id) setSelected('')
  }, [layers, pushLayers, selected])

  const move = useCallback((id, dir) => {
    const i = layers.findIndex(l => l.id === id)
    const j = i + dir
    if (i < 0 || j < 0 || j >= layers.length) return
    const next = [...layers]
    ;[next[i], next[j]] = [next[j], next[i]]
    pushLayers(next)
  }, [layers, pushLayers])

  const addProduct = useCallback((file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      const id = uid('prod')
      pushLayers([...layers, { id, kind: 'product', assetId: id, dataUrl: String(reader.result), name: file.name, x: 0.05, y: 0.05, w: 0.9, h: 0.9, fit: 'contain' }])
      setSelected(id)
      setTab('layers')
      toast('Product photograph placed. If you have not locked a reference yet, lock one so the fidelity check has something to diff.', 'info')
    }
    reader.readAsDataURL(file)
  }, [layers, pushLayers, toast])

  const addText = useCallback(() => {
    const id = uid('txt')
    pushLayers([...layers, { id, kind: 'text', text: 'Headline', role: 'headline', x: 0.1, y: 0.12, w: 0.5, h: 0.1, size: 0.06, weight: 700, color: '#1a1a1a', align: 'left' }])
    setSelected(id)
    toast('Text added as an editable vector layer. It is drawn by the canvas, never generated.', 'info')
  }, [layers, pushLayers, toast])

  const addShape = useCallback(() => {
    const id = uid('shp')
    pushLayers([...layers, { id, kind: 'shape', shape: 'rect', x: 0.55, y: 0, w: 0.45, h: 1, fill: '#e8e2d8' }])
    setSelected(id)
  }, [layers, pushLayers])

  const lockReference = useCallback((file) => {
    if (!file) return
    const reader = new FileReader()
    reader.onload = () => {
      setReference({ dataUrl: String(reader.result), name: file.name })
      setConfirm(null)  // a new reference invalidates any prior sign-off
      toast('Reference locked. A new reference invalidates any previous compare sign-off; you will be asked to compare again.', 'info')
    }
    reader.readAsDataURL(file)
  }, [toast])

  const selectedLayer = layers.find(l => l.id === selected)

  // ── Export ──────────────────────────────────────────────────────────────
  const doExport = useCallback(async () => {
    setExporting(true)
    try {
      const result = await exportComposite(workingDoc, {
        resolveAsset: (id) => layers.find(l => l.id === id)?.dataUrl,
        mime: 'image/png',
      })
      setLastExport({ ...result, summary: summariseExport(result), at: new Date().toISOString() })
      if (result.ok && result.bytes) {
        // Record the export in the library so the "re-check exported ad" action
        // has a real asset to act on, with the marker requirement it shipped under.
        const assetKey = workingDoc.meta.filename || `export-${Date.now()}`
        appendLog({
          assetId: assetKey,
          checkedAt: new Date().toISOString(),
          user: 'operator',
          verdict: 'exported',
          passed: true,
          tagRequired: result.steps['marker-embed']?.status === 'pass',
          surface: 'export',
          detail: `Exported ${result.mime}, ${result.bytes.length} bytes. ${result.steps['marker-verify']?.detail || ''}`,
        })
        const url = URL.createObjectURL(new Blob([result.bytes], { type: result.mime }))
        const a = document.createElement('a')
        a.href = url
        a.download = (workingDoc.meta.filename || 'northstar-export') .replace(/\.(jpg|jpeg|png|tif|tiff|gif)$/i, '') + '.png'
        a.click()
        URL.revokeObjectURL(url)
        toast('Export complete. Every pipeline step passed.', 'info')
        onExported?.(result)
      } else {
        toast(`Export blocked: ${result.report[0] || 'a pipeline step did not pass'}. Nothing was written.`, 'warn')
      }
    } catch (e) {
      toast(`Export failed: ${e.message}`, 'warn')
    } finally {
      setExporting(false)
    }
  }, [workingDoc, layers, toast, onExported, appendLog])

  const cmp = compareStepStatus(workingDoc)
  const exportBlocked = report.verdict === 'block' || !cmp.satisfied

  // ── Upload check: load the LIVE image back and read the marker ──────────
  // Amazon reprocesses uploaded media and the tag can be lost, so the only
  // honest check is to read what is actually serving. The verdict is logged
  // with its date; a check that did not run is never logged.
  const runUploadCheck = useCallback(async (file) => {
    if (!file) return
    const buf = new Uint8Array(await file.arrayBuffer())
    const mime = file.type || 'image/png'
    // Derive the requirement from THIS asset's own disclosure state, not from a
    // hard-coded assumption. `not-required` is a real answer only when the asset
    // genuinely does not need the marker.
    const cls = classifyDisclosure(workingDoc)
    const requires = cls.tagRequired === true
    const result = verifyUploadedAsset(buf, { mime, tagRequired: requires, label: file.name })
    setUploadResult({ ...result, classification: cls.status, tagRequired: requires })
    setUploadName(file.name)
    const entryRes = recheckEntry({
      assetId: workingDoc.meta.filename || file.name,
      result,
      user: 'operator',
      at: new Date().toISOString(),
    })
    if (entryRes.ok) {
      appendLog({ ...entryRes.entry, tagRequired: requires, classification: cls.status, surface: 'upload-check' })
    }
    toast(result.ok ? `Upload check passed: ${result.detail}` : `Upload check WARNING: ${result.detail}`, result.ok ? 'info' : 'warn')
  }, [workingDoc, appendLog, toast])

  // ── Re-check an exported asset, from the library ────────────────────────
  const runRecheck = useCallback(async (file, assetKey) => {
    if (!file) return
    const buf = new Uint8Array(await file.arrayBuffer())
    const result = verifyUploadedAsset(buf, { mime: file.type || 'image/png', tagRequired: true, label: file.name })
    setUploadResult(result)
    setUploadName(file.name)
    const entryRes = recheckEntry({ assetId: assetKey || file.name, result, user: 'operator', at: new Date().toISOString() })
    if (entryRes.ok) appendLog({ ...entryRes.entry, tagRequired: true, surface: 'library-recheck' })
    toast(result.ok ? 'Re-check passed.' : `Re-check WARNING: ${result.detail}`, result.ok ? 'info' : 'warn')
  }, [appendLog, toast])

  const logSummary = useMemo(() => recheckSummary(log), [log])

  return (
    <div className="cs-surface" data-testid="compositing-surface">
      <div className="ss-shell-mid" style={{ minHeight: 520 }}>
        <StudioLeftRail tabs={LEFT_TABS} active={tab} onSelect={setTab}>
          {tab === 'layers' && (
            <div className="stack" style={{ gap: 6 }}>
              {layers.length === 0 && <div className="text-low" style={{ fontSize: 12 }}>No layers.</div>}
              {[...layers].reverse().map(l => (
                <div key={l.id} className={`cs-layer ${selected === l.id ? 'active' : ''}`} onClick={() => setSelected(l.id)}>
                  <Icon name={l.kind === 'text' ? 'type' : l.kind === 'product' ? 'image' : l.kind === 'bg' ? 'shapes' : 'grid'} size={13} />
                  <span className="cs-layer-name">{l.kind === 'text' ? `"${String(l.text).slice(0, 16)}"` : (l.name || l.kind)}</span>
                  <button className="cs-mini" title="Move up" onClick={(e) => { e.stopPropagation(); move(l.id, -1) }}>^</button>
                  <button className="cs-mini" title="Move down" onClick={(e) => { e.stopPropagation(); move(l.id, 1) }}>v</button>
                  <button className="cs-mini" title="Delete" onClick={(e) => { e.stopPropagation(); remove(l.id) }}>x</button>
                </div>
              ))}
              <div className="inline-flex" style={{ gap: 6, marginTop: 8 }}>
                <button className="btn btn-sm" disabled={!history.canUndo} onClick={history.undo}>Undo</button>
                <button className="btn btn-sm" disabled={!history.canRedo} onClick={history.redo}>Redo</button>
              </div>
              <div className="text-low" style={{ fontSize: 10 }}>{history.depth} history step(s)</div>
            </div>
          )}

          {tab === 'reference' && (
            <div className="stack" style={{ gap: 10 }}>
              {reference ? (
                <div className="ss-rule ss-rule-pass">
                  <div className="ss-rule-label">Reference locked</div>
                  <div className="ss-rule-detail">{reference.name}. The rendered product region is diffed against this before export.</div>
                  <div className="ss-rule-source">mean threshold {(DEFAULT_THRESHOLD * 100).toFixed(0)}%</div>
                </div>
              ) : (
                <div className="ss-rule ss-rule-incomplete">
                  <div className="ss-rule-label">No reference locked</div>
                  <div className="ss-rule-detail">Without a locked reference nothing can be diffed, so fidelity stays UNVERIFIED and export is blocked.</div>
                </div>
              )}
              <label className="ss-field">
                <span className="ss-field-label">Lock the real product photograph</span>
                <input type="file" accept="image/*" onChange={e => lockReference(e.target.files?.[0])} />
              </label>
            </div>
          )}

          {tab === 'add' && (
            <div className="stack" style={{ gap: 10 }}>
              <label className="ss-field">
                <span className="ss-field-label">Product photograph</span>
                <input type="file" accept="image/*" onChange={e => addProduct(e.target.files?.[0])} />
                <span className="ss-field-note">Your own pixels. The product is never generated.</span>
              </label>
              <button className="btn btn-sm" onClick={addText}><Icon name="type" size={12} /> Add vector text</button>
              <button className="btn btn-sm" onClick={addShape}><Icon name="shapes" size={12} /> Add shape</button>
            </div>
          )}

          {tab === 'library' && (
            <div className="stack" style={{ gap: 12 }} data-testid="recheck-library">
              {/* 3. UPLOAD CHECK */}
              <div className="ss-rule">
                <div className="ss-rule-label">Upload check</div>
                <div className="ss-rule-detail">
                  Load the image that is actually live on Amazon and read it back. Amazon reprocesses
                  uploaded media and the marker can be lost, so reading the served file is the only check
                  that means anything.
                </div>
                <label className="ss-field" style={{ marginTop: 6 }}>
                  <input type="file" accept="image/*" data-testid="upload-check-input"
                    onChange={e => runUploadCheck(e.target.files?.[0])} />
                </label>
                {uploadResult && (
                  <div className={`ss-rule ss-rule-${uploadResult.ok ? 'pass' : 'flag'}`} data-testid="upload-check-result" style={{ marginTop: 6 }}>
                    <div className="ss-rule-label">{uploadName || 'file'} - {uploadResult.verdict}</div>
                    <div className="ss-rule-detail">{uploadResult.detail}</div>
                  </div>
                )}
              </div>

              {/* 4. RE-CHECK LIBRARY + NOTICE-AND-CURE */}
              <div className="ss-rule">
                <div className="ss-rule-label">Re-check log</div>
                <div className="ss-rule-detail">
                  {logSummary.checks === 0
                    ? 'No checks recorded yet. Every check is logged with its date.'
                    : `${logSummary.checks} check(s). Last ${new Date(logSummary.lastCheckedAt).toLocaleString()} - ${logSummary.lastVerdict}${logSummary.everFailed ? ' (has failed at least once)' : ''}.`}
                </div>
              </div>

              <label className="ss-field">
                <span className="ss-field-label">Date a notice was received (optional)</span>
                <input type="date" data-testid="notice-date"
                  onChange={e => setNotice(workingDoc.meta.filename || 'current', e.target.value ? new Date(e.target.value).toISOString() : null)} />
                <span className="ss-field-note">
                  A publisher or distributor put on notice of an undisclosed synthetic performer has {NOTICE_AND_CURE_DAYS} days to remove the ad or comply.
                </span>
              </label>
              {notices[workingDoc.meta.filename || 'current'] && (
                <div className="ss-rule ss-rule-flag" data-testid="cure-window">
                  <div className="ss-rule-detail">{cureWindow(notices[workingDoc.meta.filename || 'current']).detail}</div>
                </div>
              )}

              {/* Per-entry actions: re-check an exported ad */}
              <div className="stack" style={{ gap: 6 }}>
                {log.length === 0 && <div className="text-low" style={{ fontSize: 11 }}>Nothing to re-check yet.</div>}
                {log.slice(0, 12).map((e, i) => (
                  <div key={i} className={`ss-rule ss-rule-${e.passed ? 'pass' : 'flag'}`}>
                    <div className="ss-rule-label">{e.assetId || 'unnamed'} - {e.verdict}</div>
                    <div className="ss-rule-source">{new Date(e.checkedAt).toLocaleString()} - {e.surface || 'check'}</div>
                    <label className="btn btn-sm" style={{ marginTop: 6, display: 'inline-block' }}>
                      Re-check exported ad
                      <input type="file" accept="image/*" style={{ display: 'none' }}
                        data-testid={`recheck-${i}`}
                        onChange={ev => runRecheck(ev.target.files?.[0], e.assetId)} />
                    </label>
                  </div>
                ))}
              </div>
            </div>
          )}
        </StudioLeftRail>

        <StudioCanvas
          zoom={1} pan={{ x: 0, y: 0 }} canvasAspect={spec.w / spec.h}
          safeZoneId={showZones ? spec.safe : null} showSafeZones={showZones}
          fitWidth={spec.w >= 2000 ? 520 : 560}
        >
          <canvas ref={canvasRef} style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
        </StudioCanvas>

        <StudioInspector>
          <InspectorSection title="Pre-flight">
            <div className="ss-compliance" data-testid="compliance-panel">
              <div className="ss-compliance-head">
                <VerdictPill verdict={report.verdict} />
                <span className="text-low" style={{ fontSize: 11 }}>{report.checked}/{report.total} decided</span>
              </div>
            </div>
          </InspectorSection>

          <InspectorSection title="AI-generated people disclosure">
            <label className="ss-field">
              <span className="ss-field-label">People in this asset</span>
              <select value={dm.peopleClass} data-testid="surface-people-class"
                onChange={e => setDm(v => ({ ...v, peopleClass: e.target.value }))}>
                <option value="">- not answered -</option>
                <option value="no-people">No people in this asset</option>
                <option value="real-only">Real people only</option>
                <option value="real-ai-altered">Real people, altered with AI tools</option>
                <option value="ai-photoreal">Entirely AI-generated photorealistic people</option>
                <option value="non-photoreal">Non-photorealistic or illustrated people</option>
                <option value="expressive-work">Character from a film, TV, game or other expressive work</option>
              </select>
            </label>
            <label className="ss-field ss-field-toggle" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={dm.syntheticPerformerTag}
                onChange={e => setDm(v => ({ ...v, syntheticPerformerTag: e.target.checked }))} />
              <span>Write the XMP marker ({DISCLOSURE_KEYWORD})</span>
            </label>
            <label className="ss-field ss-field-toggle">
              <input type="checkbox" checked={dm.studioGeneratedPerson}
                onChange={e => setDm(v => ({ ...v, studioGeneratedPerson: e.target.checked }))} />
              <span>The studio generated a person here</span>
            </label>
            <label className="ss-field ss-field-toggle">
              <input type="checkbox" checked={dm.identifiableIndividual} data-testid="surface-identifiable"
                onChange={e => setDm(v => ({ ...v, identifiableIndividual: e.target.checked }))} />
              <span>Intended to look like a real, identifiable individual</span>
            </label>
            <label className="ss-field" style={{ marginTop: 8 }}>
              <span className="ss-field-label">Export filename</span>
              <input type="text" value={dm.filename} placeholder="B01ABCDEFG.main.png"
                onChange={e => setDm(v => ({ ...v, filename: e.target.value }))} />
            </label>
            <div className="ss-field-note" style={{ marginTop: 6 }} data-testid="disclosure-status">
              {classifyDisclosure(workingDoc).note}
            </div>
          </InspectorSection>

          <InspectorSection title="Compare to reference">            <div className={`ss-rule ss-rule-${cmp.satisfied ? 'pass' : 'incomplete'}`}>
              <div className="ss-rule-label">{cmp.required ? (cmp.satisfied ? 'Compared' : 'Required before export') : 'Not required'}</div>
              <div className="ss-rule-detail">{cmp.detail}</div>
            </div>
            {cmp.required && (
              <button className="btn btn-sm" style={{ marginTop: 8 }} onClick={() => setCompareOpen(true)} disabled={!reference}>
                {cmp.satisfied ? 'Compare again' : 'Compare to reference'}
              </button>
            )}
          </InspectorSection>

          {selectedLayer && (
            <InspectorSection title={`Layer: ${selectedLayer.kind}`}>
              {selectedLayer.kind === 'text' && (
                <>
                  <label className="ss-field">
                    <span className="ss-field-label">Text</span>
                    <input type="text" value={selectedLayer.text || ''} onChange={e => patch(selectedLayer.id, { text: e.target.value })} />
                  </label>
                  <label className="ss-field">
                    <span className="ss-field-label">Size ({(selectedLayer.size * 100).toFixed(1)}% of height = {Math.round((selectedLayer.size || 0) * spec.h)}px)</span>
                    <input type="range" min="0.01" max="0.2" step="0.002" value={selectedLayer.size || 0.03} onChange={e => patch(selectedLayer.id, { size: Number(e.target.value) })} />
                  </label>
                </>
              )}
              <div className="cs-boxrow">
                {['x', 'y', 'w', 'h'].map(k => (
                  <label key={k} className="ss-field">
                    <span className="ss-field-label">{k.toUpperCase()}</span>
                    <input type="number" min="-0.5" max="1.5" step="0.01" value={Number(selectedLayer[k] ?? 0).toFixed(2)}
                      onChange={e => patch(selectedLayer.id, { [k]: Number(e.target.value) })} />
                  </label>
                ))}
              </div>
            </InspectorSection>
          )}

          <InspectorSection title="Export" defaultOpen>
            <label className="ss-field ss-field-toggle">
              <input type="checkbox" checked={showZones} onChange={e => setShowZones(e.target.checked)} />
              <span>Show safe zones</span>
            </label>
            <button className="btn btn-sm btn-primary" style={{ marginTop: 8 }} disabled={exportBlocked || exporting} onClick={doExport}>
              <Icon name="download" size={12} /> {exporting ? 'Exporting...' : 'Run export pipeline'}
            </button>
            {exportBlocked && (
              <div className="ss-field-note" style={{ marginTop: 6 }}>
                {!cmp.satisfied ? 'Blocked: the compare step is not signed off.' : 'Blocked by the pre-flight.'}
              </div>
            )}
            {lastExport && (
              <div className="ss-rule" style={{ marginTop: 10 }}>
                <div className="ss-rule-label">{lastExport.ok ? 'Export passed' : 'Export blocked'}</div>
                <div className="ss-rule-detail">{lastExport.summary}</div>
              </div>
            )}
          </InspectorSection>
        </StudioInspector>
      </div>

      <StudioBottomStrip
        items={layers.map(l => ({ id: l.id, label: l.kind, icon: l.kind === 'text' ? 'type' : 'image' }))}
        active={selected}
        onSelect={(s) => setSelected(s.id)}
        actions={<span className="text-low" style={{ fontSize: 11 }}>{layers.length} layer(s)</span>}
      />

      {compareOpen && (
        <div className="cs-modal" data-testid="compare-modal" onClick={() => setCompareOpen(false)}>
          <div className="cs-modal-body" onClick={e => e.stopPropagation()}>
            <div className="cs-modal-head">
              <strong>Compare to reference</strong>
              <button className="btn btn-sm" onClick={() => setCompareOpen(false)}>Close</button>
            </div>
            <div className="cs-compare">
              <div>
                <div className="cs-compare-cap">Locked reference</div>
                {reference ? <img src={reference.dataUrl} alt="locked reference" /> : <div className="text-low">No reference.</div>}
              </div>
              <div>
                <div className="cs-compare-cap">Current composite</div>
                <canvas ref={el => {
                  if (!el || !canvasRef.current) return
                  el.width = canvasRef.current.width
                  el.height = canvasRef.current.height
                  el.getContext('2d').drawImage(canvasRef.current, 0, 0)
                }} className="cs-compare-canvas" />
              </div>
            </div>
            <div className="ss-field-note" style={{ margin: '10px 0' }}>
              Look at the label, the edges and the proportions. The pixel diff is a tripwire; this is the sign-off. Confirming records who
              compared and when, and a new reference invalidates it.
            </div>
            <button className="btn btn-sm btn-primary" onClick={() => {
              setConfirm({ at: new Date().toISOString(), by: 'operator' })
              setCompareOpen(false)
              toast('Compared and signed off.', 'info')
            }}>I compared these and the product matches</button>
          </div>
        </div>
      )}
    </div>
  )
}
