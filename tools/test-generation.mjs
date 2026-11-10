// ═══════════════════════════════════════════════════════════════════════════
// GENERATION PATH — fixture-tested, UNARMED
//
// Phase 5 item 9. Generated output must enter the SAME gates as imported art.
// The router is unarmed, so every case here is a MOCKED router response. No
// provider is called, no model is loaded, no credits move.
//
// Run:  node tools/test-generation.mjs
// Exit: 0 = all green, 1 = a failure.
// ═══════════════════════════════════════════════════════════════════════════

import {
  GEN_KINDS, GEN_KIND_BY_ID, metaFromGeneration, auditGeneratedAsset,
  armingState, gateGenerate, UNARMED_NOTICE,
} from '../northstar-os-ui/src/studio/engine/generation.js'
import { classifyDisclosure } from '../northstar-os-ui/src/studio/engine/disclosure.js'
import { checkCompliance } from '../northstar-os-ui/src/studio/engine/compliance.js'

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++ }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

const doc = (meta, extra = {}) => ({
  formatId: 'amz-main', w: 1200, h: 1200, channel: 'Amazon listing',
  layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.05, y: 0.05, w: 0.9, h: 0.9, dataUrl: 'data:image/png;base64,AA' }],
  meta, ...extra,
})

console.log('router is UNARMED: every case below is a mocked response\n')

// ── A background-only generation is allowed to proceed ────────────────────
{
  const r = metaFromGeneration({ kind: 'background', provider: 'mock', model: 'mock-bg', contains_person: false })
  if (r.ok && r.meta.generated && r.meta.fidelityMode === 'locked') ok('a background-only generation is accepted and keeps fidelity locked')
  else no(`background-only rejected: ${JSON.stringify(r).slice(0, 120)}`)
  if (r.meta.peopleClass === 'no-people') ok('a definitive no-person response classifies as no-people')
  else no(`no-person response classified as ${r.meta.peopleClass}`)
}

// ── A generated PRODUCT REGION is blocked ─────────────────────────────────
{
  const r = metaFromGeneration({ kind: 'product-region', provider: 'mock' })
  if (!r.ok && r.blockers.length) ok('a generated PRODUCT REGION is blocked')
  else no('a generated product region was accepted')
  if (r.meta.fidelityMode === 'generated') ok('it is marked with the BLOCKING fidelity mode')
  else no(`fidelity mode was ${r.meta.fidelityMode}`)

  const audit = auditGeneratedAsset(doc({ ...r.meta, peopleClass: 'no-people' }))
  if (!audit.ok && audit.problems.some(p => /product region was generated/i.test(p))) {
    ok('the audit independently blocks a generated product region')
  } else no(`audit did not block: ${JSON.stringify(audit.problems)}`)

  const comp = checkCompliance(doc({ ...r.meta, peopleClass: 'no-people', fidelityMode: 'generated' }))
  if (comp.verdict === 'block' && comp.blocked.some(b => b.id === 'product-fidelity')) {
    ok('the PRE-FLIGHT blocks a generated product region (product-fidelity)')
  } else no(`pre-flight verdict was ${comp.verdict}`)
}

// ── A generated PERSON auto-flags and auto-applies the marker ─────────────
{
  const r = metaFromGeneration({ kind: 'lifestyle', provider: 'mock', contains_person: true })
  if (r.meta.studioGeneratedPerson === true) ok('a generated person AUTO-FLAGS as studio-generated')
  else no('a generated person was not flagged')
  if (r.meta.peopleClass === 'ai-photoreal') ok('a generated person is classified ai-photoreal, not left to the seller')
  else no(`generated person classified as ${r.meta.peopleClass}`)
  if (r.meta.syntheticPerformerTag === true) ok('the marker is AUTO-APPLIED for a generated person')
  else no('the marker was not auto-applied')
  if (r.meta.attestationRequired === true && r.meta.attestationStatement) {
    ok('seller attestation is STILL REQUIRED alongside the automatic marker')
  } else no('attestation was not required for a generated person')

  const c = classifyDisclosure(doc(r.meta))
  if (c.status === 'decided' && c.tagRequired) ok('the classifier requires the tag for the generated person')
  else no(`classifier said ${c.status} tagRequired=${c.tagRequired}`)

  // The seller cannot switch the marker off on a generated person.
  const off = doc({ ...r.meta, syntheticPerformerTag: false })
  const cOff = classifyDisclosure(off)
  if (cOff.status === 'conflict') ok('switching the marker off on a generated person is a CONFLICT')
  else no(`marker-off reported ${cOff.status}`)

  // Attestation still missing -> the audit says so.
  const audit = auditGeneratedAsset(off)
  if (!audit.ok) ok('the audit refuses a generated person without a valid attestation')
  else no('the audit accepted a generated person with no attestation')

  const withAtt = auditGeneratedAsset(doc({ ...r.meta, attestation: { user: 't2', at: 'x', statement: r.meta.attestationStatement } }))
  const attestProblem = withAtt.problems.some(p => /attestation/i.test(p))
  if (!attestProblem) ok('a valid attestation clears the attestation problem')
  else no('a valid attestation did not clear the problem')
}

// ── The seller's "no people" answer cannot override a generated person ────
{
  const r = metaFromGeneration({ kind: 'lifestyle', provider: 'mock', contains_person: true })
  const c = classifyDisclosure(doc({ ...r.meta, peopleClass: 'no-people' }))
  if (c.status === 'conflict') ok('a seller answer of "no people" on a generated person is a CONFLICT')
  else no(`override attempt reported ${c.status}`)
}

// ── An unknown generation kind is UNKNOWN, and blocked ────────────────────
{
  const r = metaFromGeneration({ kind: 'something-new', provider: 'mock' })
  if (!r.ok && /unknown-generation-kind/.test(r.reason || '')) ok('an unrecognised generation kind is refused, not guessed')
  else no(`unknown kind gave ${JSON.stringify(r).slice(0, 100)}`)
  const empty = metaFromGeneration(null)
  if (!empty.ok && empty.reason === 'empty-response') ok('an empty router response is refused')
  else no('an empty response was accepted')
}

// ── Every declared kind behaves as declared ──────────────────────────────
{
  let checked = 0
  for (const k of GEN_KINDS) {
    const r = metaFromGeneration({ kind: k.id, provider: 'mock', contains_person: false })
    const expectBlocked = !!(k.blocking || k.productRegionGenerated)
    if (r.ok !== !expectBlocked) { no(`kind ${k.id} ok=${r.ok}, expected ${!expectBlocked}`); continue }
    if (r.meta.fidelityMode !== (k.productRegionGenerated ? 'generated' : 'locked')) {
      no(`kind ${k.id} fidelityMode=${r.meta.fidelityMode}`); continue
    }
    checked++
  }
  ok(`all ${GEN_KINDS.length} declared generation kinds behave as declared (${checked} verified)`)
}

// ── The arming gate ──────────────────────────────────────────────────────
{
  const unarmed = armingState({ media_live_armed: false })
  if (!unarmed.armed) ok('an explicit false reads as UNARMED')
  else no('false read as armed')
  const unknown = armingState(null)
  if (!unknown.armed && !unknown.known) ok('an UNREADABLE arming state is treated as UNARMED')
  else no('an unreadable state read as armed')
  const armed = armingState({ media_live_armed: true })
  if (armed.armed && armed.known) ok('a true value reads as armed (the gate can be satisfied)')
  else no('a true value did not read as armed')

  // Even armed, a generate action needs a cost preview.
  const g = gateGenerate({ media_live_armed: true })
  if (!g.allowed && g.reason === 'no-cost-preview') ok('even when ARMED, a generate action requires a cost preview')
  else no(`armed gate gave ${JSON.stringify(g)}`)
  const u = gateGenerate({ media_live_armed: false })
  if (!u.allowed && u.reason === 'unarmed') ok('an unarmed router refuses a generate action with a real reason')
  else no(`unarmed gate gave ${JSON.stringify(u)}`)

  if (/UNARMED/.test(UNARMED_NOTICE.title) && /provider required/i.test(UNARMED_NOTICE.detail)) {
    ok('the unarmed notice says the honest terminal state is "provider required"')
  } else no('the unarmed notice is not honest about the terminal state')
}

// ── Nothing in the generation module reaches the network ─────────────────
{
  const fs = await import('node:fs')
  const src = fs.readFileSync(new URL('../northstar-os-ui/src/studio/engine/generation.js', import.meta.url), 'utf8')
  const netCalls = ['fetch(', 'XMLHttpRequest', 'WebSocket', 'EventSource', 'navigator.sendBeacon']
  const found = netCalls.filter(n => src.includes(n))
  if (found.length === 0) ok('the generation module contains NO network call of any kind')
  else no(`the generation module contains network calls: ${found.join(', ')}`)
}

console.log(`\nGENERATION PATH (unarmed, mocked): ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
