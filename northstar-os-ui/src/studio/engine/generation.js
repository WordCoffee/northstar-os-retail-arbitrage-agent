// ═══════════════════════════════════════════════════════════════════════════
// STUDIO ENGINE — GENERATION PATH (UNARMED)
//
// Generated output does not get its own rules. It enters the SAME gates as
// imported art: the disclosure classifier, the fidelity check, the marker, and
// the compare step. This module is the adapter that turns a router response
// into a document the existing pipeline already understands.
//
// HARD RULES
//   • A GENERATED PRODUCT REGION stays export-blocked. Generation is for the
//     background and the scene around the product, never the product.
//   • A generated person AUTO-FLAGS as AI-generated and AUTO-APPLIES the
//     marker. The seller's answer cannot turn that off.
//   • Seller attestation is still required even when the marker is automatic.
//   • Nothing here calls a provider. It maps a response that already exists.
//
// The router is UNARMED in this build, so every path below is exercised with
// mocked responses only (see tools/test-generation.mjs).
// ═══════════════════════════════════════════════════════════════════════════

import { classifyDisclosure, ATTESTATION_STATEMENTS } from './disclosure.js'

// What a router response is allowed to say. Anything else is UNKNOWN and the
// asset is blocked rather than guessed.
export const GEN_KINDS = [
  { id: 'background', label: 'Background / scene only', productRegionGenerated: false, mayContainPerson: true },
  { id: 'lifestyle', label: 'Lifestyle scene around the product', productRegionGenerated: false, mayContainPerson: true },
  { id: 'product-cleanup', label: 'Product cleanup / background removal', productRegionGenerated: false, mayContainPerson: false },
  { id: 'product-region', label: 'Product region itself', productRegionGenerated: true, mayContainPerson: false, blocking: true },
]

export const GEN_KIND_BY_ID = Object.fromEntries(GEN_KINDS.map(k => [k.id, k]))

/**
 * Map a router response into document metadata.
 *
 * @param {object} response  a router response, real or mocked
 * @returns {{ok:boolean, meta:object, blockers:string[], reason?:string}}
 */
export function metaFromGeneration(response) {
  if (!response || typeof response !== 'object') {
    return { ok: false, meta: {}, blockers: [], reason: 'empty-response' }
  }
  const kind = response.kind || response.generation_kind
  const spec = GEN_KIND_BY_ID[kind]
  if (!spec) {
    return {
      ok: false, meta: {}, blockers: [],
      reason: `unknown-generation-kind:${String(kind)}`,
      detail: 'An unrecognised generation kind is UNKNOWN, so the asset is blocked rather than guessed.',
    }
  }

  const blockers = []
  if (spec.blocking || spec.productRegionGenerated) {
    // Not a metadata problem: the PRODUCT ITSELF was generated.
    blockers.push(
      'The product region was generated. The product must be the operator\'s real photograph; only the background and the scene may be generated.'
    )
  }

  const meta = {
    generated: true,
    generationKind: spec.id,
    generationProvider: response.provider || 'unknown',
    generationModel: response.model || 'unknown',
    generatedAt: response.finished_at || response.at || null,
    // FIDELITY: a generated product region is a blocking fidelity mode.
    fidelityMode: spec.productRegionGenerated ? 'generated' : 'locked',
  }

  // A generated person: auto-flag and auto-apply the marker. The seller cannot
  // switch this off; they can only correct it by saying the person is real.
  const sawPerson = response.contains_person === true || response.containsPerson === true
  if (spec.mayContainPerson && sawPerson) {
    meta.studioGeneratedPerson = true
    meta.peopleClass = 'ai-photoreal'
    meta.syntheticPerformerTag = true            // AUTOMATIC
    meta.attestationRequired = true              // STILL REQUIRED
    meta.attestationStatement = ATTESTATION_STATEMENTS['ai-photoreal']
  }

  // A definitive "no person" answer lets the seller classify as no-people.
  if (response.contains_person === false && !meta.studioGeneratedPerson) {
    meta.peopleClass = meta.peopleClass || 'no-people'
  }

  return { ok: blockers.length === 0, meta, blockers, kind: spec }
}

/**
 * Validate that a generated asset actually clears the gates. This is the same
 * classifier the imported-art path uses, so a generated asset cannot have a
 * weaker standard applied to it.
 */
export function auditGeneratedAsset(doc) {
  const c = classifyDisclosure(doc)
  const problems = []
  if (c.status === 'conflict') problems.push(...c.conflicts)
  if (c.status === 'needs-confirmation') problems.push('A generated asset with people still needs the seller classification.')
  if (doc?.meta?.studioGeneratedPerson && doc?.meta?.syntheticPerformerTag !== true) {
    problems.push('A generated person requires the marker; it cannot be switched off.')
  }
  if (doc?.meta?.studioGeneratedPerson && !doc?.meta?.attestation) {
    problems.push('A generated person requires a seller attestation even though the marker is automatic.')
  }
  if (doc?.meta?.generationKind && GEN_KIND_BY_ID[doc.meta.generationKind]?.blocking) {
    problems.push('The product region was generated, so export is blocked.')
  }
  return { ok: problems.length === 0, problems, disclosure: c }
}

// ── The arming state ───────────────────────────────────────────────────────
// The router is UNARMED in this build. The UI must say so rather than imply
// that generation is available.
export const UNARMED_NOTICE = {
  title: 'Generation is UNARMED',
  detail:
    'No image or video model is connected. Nothing on this surface calls a provider, and nothing is generated. ' +
    'Every generate action is a real request recorder whose honest terminal state is "Blocked - provider required". ' +
    'Arming requires the owner checklist in docs/GENERATION_ARMING_CHECKLIST.md.',
}

/** Read the arming state from a status payload. Unknown is NOT armed. */
export function armingState(status) {
  if (!status || typeof status !== 'object') {
    return { armed: false, known: false, detail: 'The arming state could not be read, so generation is treated as UNARMED.' }
  }
  const armed = status.media_live_armed === true
  return {
    armed,
    known: true,
    gates: status.gates || null,
    detail: armed
      ? 'The media router reports ARMED.'
      : 'The media router reports UNARMED. Generation cannot run.',
  }
}

/** Block a generate action while unarmed, with a real reason. */
export function gateGenerate(status) {
  const a = armingState(status)
  if (!a.armed) {
    return { allowed: false, reason: a.known ? 'unarmed' : 'unknown', detail: a.detail }
  }
  return { allowed: false, reason: 'no-cost-preview', detail: 'Even when armed, a generate action requires an explicit cost preview and confirmation.' }
}
