// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — 3D RENDER EXPORT GATE (Phase 7 item 4)
//
// The 3D Product Scene composer renders REAL geometry, but a render is not a
// photograph. This gate puts every 3D export through the same mechanics the
// other sections use, plus the Brand Registry actual-photo rule:
//
//   actualPhoto  BLOCK  - a render cannot serve as an Amazon listing image
//   compliance   BLOCK  - the Amazon pre-flight runs on the rendered asset
//   disclosure   BLOCK  - same rules as every other section; an unanswered
//                         classification never passes
//   fidelity     BLOCK  - only when the operator locked a reference; the
//                         render is diffed against it (a render that diverges
//                         from the locked photograph is refused)
//   compare      BLOCK  - product accuracy: a human sign-off bound to the
//                         scene version, required when locked or listing-bound
//
// Every step reports pass / block / not-required / not-run; a step that did
// not run is never shown as passed. No provider is contacted anywhere here.
// ═══════════════════════════════════════════════════════════════════════════

import { SPEC_SOURCES } from './specRegistry.js'
import { classifyDisclosure } from './disclosure.js'
import { verifyFidelity } from './fidelity.js'
import { compareStepStatus } from './compose.js'
import { checkCompliance } from './compliance.js'

export const RENDER_PURPOSES = [
  {
    id: 'internal',
    label: 'Internal reference',
    note: 'Pack-art review, mockups for your own decisions, internal docs. Not a marketplace listing slot.',
  },
  {
    id: 'listing',
    label: 'Amazon listing image',
    note: 'Any gallery slot on an Amazon listing. Amazon requires an actual photograph of the product here.',
  },
]

// The Brand Registry actual-photo rule, as data with its source. The detail is
// an original paraphrase; the source id resolves in the spec registry.
export const ACTUAL_PHOTO_RULE = {
  id: 'render-actual-photo',
  tier: 'BLOCK',
  label: 'Actual photograph required',
  detail: 'Amazon product-image requirements call for an actual photograph of the product. A rendered or synthetic image - including a 3D render or a mockup render - does not qualify, so an export intended for a listing slot is refused. Export as an internal reference instead, or photograph the product.',
  source_id: 'img-guide',
}

export function actualPhotoSource() {
  const src = SPEC_SOURCES[ACTUAL_PHOTO_RULE.source_id]
  return src ? { id: src.id, label: src.label, pulled: src.pulled, confidence: src.confidence } : null
}

/** The doc adapter the shared engines (disclosure/fidelity/compare/compliance)
 * understand. The rendered pixels sit in a full-canvas product layer.
 *
 * Version binding: formatId is kind-agnostic ('render3d') and w/h are the
 * SCENE's canonical dimensions, so ONE compare sign-off covers every view of
 * the same scene state (scene / pack / mockup). The actual render size travels
 * in meta.renderW / meta.renderH. */
export function makeRenderDoc({ w, h, dataUrl, meta = {} }) {
  return {
    formatId: 'render3d',
    w, h,
    channel: meta.purpose === 'listing' ? 'Amazon listing' : 'Internal reference',
    layers: [{ kind: 'product', x: 0, y: 0, w: 1, h: 1, dataUrl }],
    meta,
  }
}

function disclosureStep(doc) {
  const meta = doc.meta || {}
  const cls = classifyDisclosure(doc)
  if (cls.status === 'exempt') return { status: 'pass', detail: cls.detail || 'A named exemption applies.' }
  if (cls.status === 'decided') {
    if (cls.tagRequired && !meta.syntheticPerformerTag) {
      return { status: 'block', detail: 'A synthetic performer is classified and the disclosure marker is not applied. Apply the marker or correct the classification.' }
    }
    return { status: 'pass', detail: cls.detail || 'Disclosure decided.' }
  }
  if (cls.status === 'needs-confirmation') {
    return { status: 'block', detail: 'The people classification is unanswered. An unanswered disclosure never passes.' }
  }
  if (cls.status === 'conflict') {
    return { status: 'block', detail: cls.detail || 'The disclosure answers conflict; resolve them before export.' }
  }
  if (cls.status === 'blocked-identifiable') {
    return { status: 'block', detail: cls.detail || 'The identifiability question blocks export; this is a consent matter, not a label.' }
  }
  return { status: 'block', detail: `Unknown disclosure status "${cls.status}" - blocked rather than assumed safe.` }
}

/**
 * Run the full 3D export gate.
 *
 * @param {object} o
 * @param {'internal'|'listing'} o.purpose
 * @param {'scene'|'pack'|'mockup'} o.renderKind
 * @param {number} o.w @param {number} o.h   the SCENE's canonical dims (version binding)
 * @param {string} o.dataUrl                 the rendered PNG (a real canvas export)
 * @param {object} o.meta                    scene metadata (peopleClass, fidelityMode,
 *                                           referenceDataUrl, compareConfirmed, lastEditAt,
 *                                           renderW/renderH for the actual size, ...)
 * @returns {{ok:boolean, steps:object, blocked:Array, summary:string}}
 */
export async function gateRender3d({ purpose, renderKind, w, h, dataUrl, meta = {} }) {
  const doc = makeRenderDoc({ w, h, dataUrl, meta: { ...meta, purpose, renderKind } })
  const steps = {}
  const blocked = []

  // 1. Actual photograph (listing slots only).
  if (purpose === 'listing') {
    const src = actualPhotoSource()
    steps.actualPhoto = {
      status: 'block',
      detail: ACTUAL_PHOTO_RULE.detail,
      rule: { id: ACTUAL_PHOTO_RULE.id, tier: ACTUAL_PHOTO_RULE.tier, label: ACTUAL_PHOTO_RULE.label },
      source: src,
    }
    blocked.push(`${ACTUAL_PHOTO_RULE.label} (${ACTUAL_PHOTO_RULE.id}, source ${ACTUAL_PHOTO_RULE.source_id}${src ? `, pulled ${src.pulled}` : ''})`)
  } else {
    steps.actualPhoto = {
      status: 'not-required',
      detail: 'Internal reference: the actual-photo requirement applies to listing images only.',
    }
  }

  // 2. Amazon pre-flight on the rendered asset (listing purpose only; an
  //    internal reference is not a listing placement). A step that cannot run
  //    is reported as not-run and blocks - never as a pass.
  if (purpose === 'listing') {
    try {
      const pf = checkCompliance(doc, meta.complianceContext || {})
      steps.compliance = pf.verdict === 'block'
        ? { status: 'block', detail: `${pf.blocked.length} blocking rule(s): ${pf.blocked.map(r => r.id).join(', ')}` }
        : { status: 'pass', detail: `${pf.total - pf.blocked.length} of ${pf.total} checks pass` }
      if (pf.verdict === 'block') blocked.push('Amazon pre-flight: blocking rule(s)')
    } catch (e) {
      steps.compliance = { status: 'not-run', detail: `The pre-flight could not run: ${String(e && e.message || e)}` }
      blocked.push('Amazon pre-flight did not run')
    }
  } else {
    steps.compliance = { status: 'not-required', detail: 'Internal reference: the listing pre-flight is not applied.' }
  }

  // 3. Disclosure (same rules as every other section).
  steps.disclosure = disclosureStep(doc)
  if (steps.disclosure.status === 'block') blocked.push('Disclosure')

  // 4. Fidelity, only when a reference is locked (same semantics as elsewhere:
  //    no lock -> nothing to diff; a lock -> a real diff that can block).
  if (meta.fidelityMode === 'locked') {
    try {
      const fid = await verifyFidelity({ ...doc, meta: { ...doc.meta, compositeDataUrl: dataUrl } })
      steps.fidelity = { status: fid.status, detail: fid.detail }
      if (fid.status !== 'pass') blocked.push('Fidelity')
    } catch (e) {
      steps.fidelity = { status: 'not-run', detail: `The fidelity diff could not run: ${String(e && e.message || e)}` }
      blocked.push('Fidelity diff did not run')
    }
  } else {
    steps.fidelity = { status: 'not-required', detail: 'No locked reference: there is nothing to diff. Lock the product photograph to turn the diff on.' }
  }

  // 5. Product accuracy: a human compare sign-off, required when locked or
  //    when the export claims a listing slot.
  if (meta.fidelityMode === 'locked' || purpose === 'listing') {
    const cmp = compareStepStatus(doc)
    steps.compare = cmp.satisfied
      ? { status: 'pass', detail: cmp.detail }
      : { status: 'block', detail: cmp.detail }
    if (!cmp.satisfied) blocked.push('Product-accuracy sign-off')
  } else {
    steps.compare = { status: 'not-required', detail: 'Internal reference without a locked reference: no product-accuracy sign-off is required.' }
  }

  const ok = Object.values(steps).every(s => s.status !== 'block')
  const summary = Object.entries(steps).map(([k, v]) => `${k}: ${v.status}`).join(' | ')
  return { ok, steps, blocked, summary }
}
