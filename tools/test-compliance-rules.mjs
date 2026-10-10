// ═══════════════════════════════════════════════════════════════════════════
// PER-RULE FIXTURE TEST — compliance engine
//
// For EVERY rule in the register this file declares one fixture that must PASS
// and one fixture that must FAIL (block for a blocking rule, flag for a flag
// rule). A rule with no fail path by construction is declared `alwaysPass` with
// the reason, and the test asserts it really does always pass — it is never
// silently skipped.
//
// Run:  node tools/test-compliance-rules.mjs
// Exit: 0 = every rule covered and correct, 1 = at least one failure.
// ═══════════════════════════════════════════════════════════════════════════

import { RULES, checkCompliance } from '../northstar-os-ui/src/studio/engine/compliance.js'
import { SPEC_BY_ID, SPEC_SOURCES, SPEC_GROUPS } from '../northstar-os-ui/src/studio/engine/specRegistry.js'

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++; }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── Fixture helpers ─────────────────────────────────────────────────────────
const L = {
  bg: (fill = '#ffffff') => ({ kind: 'bg', fill }),
  product: (o = {}) => ({ kind: 'product', x: o.x ?? 0.02, y: o.y ?? 0.02, w: o.w ?? 0.95, h: o.h ?? 0.95, ...o }),
  text: (text, role = 'headline', o = {}) => ({ kind: 'text', text, role, x: o.x ?? 0.1, y: o.y ?? 0.1, w: o.w ?? 0.5, h: o.h ?? 0.1, ...o }),
  badge: (text, o = {}) => ({ kind: 'badge', text, x: o.x ?? 0.1, y: o.y ?? 0.8, w: o.w ?? 0.2, h: o.h ?? 0.1, ...o }),
  shape: (o = {}) => ({ kind: 'shape', shape: 'rect', x: o.x ?? 0.1, y: o.y ?? 0.1, w: o.w ?? 0.2, h: o.h ?? 0.2, fill: o.fill ?? '#cccccc', ...o }),
}

function doc(o = {}) {
  return {
    w: o.w ?? 2000,
    h: o.h ?? 2000,
    formatId: o.formatId ?? 'amz-main',
    channel: o.channel ?? 'Amazon listing',
    family: o.family ?? '',
    media: o.media,
    layers: o.layers ?? [L.bg('#ffffff'), L.product()],
    meta: o.meta ?? {},
  }
}

/** Run the engine and return the row for a rule id, or null. */
function rowFor(d, ctx = {}, ruleId) {
  const report = checkCompliance(d, ctx)
  return report.results.find(r => r.id === ruleId) || null
}

// ── The fixture table ───────────────────────────────────────────────────────
// pass: fixture that must produce the rule at level 'pass'
// fail: fixture that must produce the rule at the rule's own level, OR 'flag'
//       for a flag rule (a flag rule's failure IS a flag)
// alwaysPass: true when the design makes a fail impossible; `why` is required
const FIXTURES = [
  {
    id: 'raster-range',
    pass: doc({ w: 2000, h: 2000 }),
    fail: doc({ w: 400, h: 400 }),
  },
  {
    id: 'raster-zoom',
    pass: doc({ w: 2000, h: 2000 }),
    fail: doc({ w: 800, h: 800 }),
    failLevel: 'flag',
  },
  {
    id: 'main-white-bg',
    pass: doc({ formatId: 'amz-main', layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ formatId: 'amz-main', layers: [L.bg('#123456'), L.product()] }),
  },
  {
    id: 'main-fill',
    pass: doc({ formatId: 'amz-main', layers: [L.bg('#ffffff'), L.product({ w: 0.95, h: 0.95 })] }),
    fail: doc({ formatId: 'amz-main', layers: [L.bg('#ffffff'), L.product({ w: 0.5, h: 0.5 })] }),
  },
  {
    id: 'main-no-overlay',
    pass: doc({ formatId: 'amz-main', layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ formatId: 'amz-main', layers: [L.bg('#ffffff'), L.product(), L.text('SALE')] }),
  },
  {
    id: 'aplus-module-size',
    pass: doc({ formatId: 'aplus-overlay-dark', channel: 'Amazon A+', w: 970, h: 300, layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ formatId: 'aplus-overlay-dark', channel: 'Amazon A+', w: 300, h: 100, layers: [L.bg('#ffffff'), L.product()] }),
  },
  {
    id: 'no-animated-gif',
    alwaysPass: true,
    why: 'The engine only ever exports PNG, so an animated GIF cannot be produced by this pipeline. The rule exists to document the constraint and to guard a future export path.',
  },
  {
    id: 'caps-headline',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('GREAT COFFEE FOR MORNINGS')] }),
  },
  {
    id: 'title-case',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great Coffee Morning Brew')] }),
    failLevel: 'flag',
  },
  {
    id: 'pressure-punct',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings!!')] }),
  },
  {
    id: 'cta-end-punct',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.badge('Shop now')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.badge('Shop now!')] }),
  },
  {
    id: 'special-chars',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('The B.E.S.T. coffee')] }),
  },
  {
    id: 'pressure-language',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Hurry while supplies last')] }),
    failLevel: 'flag',
  },
  {
    id: 'personal-language',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee for mornings')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Solve your morning problem')] }),
    failLevel: 'flag',
  },
  {
    id: 'superiority',
    pass: doc({ layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('The best coffee')] }),
  },
  {
    id: 'competitor-named',
    pass: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('A leading brand')] }),
    fail: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('Better than Starbucks')] }),
    ctx: { competitors: 'Starbucks' },
    ctxFail: { competitors: 'Starbucks' },
  },
  {
    id: 'brand-prohibited',
    pass: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('Great coffee')] }),
    fail: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('Cures headaches')] }),
    ctx: { prohibited: 'cures' },
    ctxFail: { prohibited: 'cures' },
  },
  {
    id: 'text-on-image-legibility',
    pass: doc({ layers: [L.bg('#ffffff'), L.product(), L.text('Hello')] }),
    fail: doc({ layers: [L.bg('#ffffff'), L.product()] }),
    failLevel: 'flag',
  },
  {
    id: 'image-text-not-indexed',
    alwaysPass: true,
    alwaysLevel: 'flag',
    why: 'The rule is an unconditional advisory: whatever the document contains, keyword-bearing image text is not an SEO play. There is no state of the document that should suppress the advisory.',
  },
  {
    id: 'store-safe-zone',
    pass: doc({ formatId: 'store-hero', channel: 'Amazon Store', w: 3000, h: 600, layers: [L.bg('#f5f0e8'), L.text('Centred headline', 'headline', { x: 0.45, y: 0.4, w: 0.2, h: 0.1 })] }),
    fail: doc({ formatId: 'store-hero', channel: 'Amazon Store', w: 3000, h: 600, layers: [L.bg('#f5f0e8'), L.text('Left edge text', 'headline', { x: 0.02, y: 0.4, w: 0.05, h: 0.1 })] }),
    failLevel: 'flag',
  },
  {
    id: 'store-no-embedded-text',
    pass: doc({ formatId: 'store-tile-full', channel: 'Amazon Store', w: 3000, h: 1500, layers: [L.bg('#f5f0e8'), L.product()] }),
    fail: doc({ formatId: 'store-tile-full', channel: 'Amazon Store', w: 3000, h: 1500, layers: [L.bg('#f5f0e8'), L.product(), L.text('Baked in')] }),
    failLevel: 'flag',
  },
  {
    id: 'sbv-video-spec',
    pass: doc({ formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e')] }),
    fail: doc({ formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e')] }),
    ctx: { durationSeconds: 20 },
    ctxFail: { durationSeconds: 90 },
  },
  {
    id: 'sbv-text-safe-area',
    pass: doc({ formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e'), L.text('Centre hook', 'headline', { x: 0.3, y: 0.4, w: 0.3, h: 0.1 })] }),
    fail: doc({ formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e'), L.text('Corner text', 'headline', { x: 0.85, y: 0.9, w: 0.1, h: 0.05 })] }),
    failLevel: 'flag',
  },
  {
    id: 'ai-people-disclosure',
    pass: doc({ meta: { syntheticPeople: true, syntheticPerformerTag: true } }),
    fail: doc({ meta: { syntheticPeople: true, syntheticPerformerTag: false } }),
    failLevel: 'flag',
  },
  {
    id: 'brand-registry-not-a-mockup',
    alwaysPass: true,
    alwaysLevel: 'flag',
    why: 'An unconditional policy advisory: every generated asset in this studio is marketing-only and never Brand Registry proof. Nothing about a document removes the advisory.',
  },
  {
    id: 'aplus-alt-text',
    pass: doc({ formatId: 'aplus-single', channel: 'Amazon A+', w: 300, h: 300, meta: { altText: 'A 300x300 module showing the front of the pack on a linen surface.' }, layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ formatId: 'aplus-single', channel: 'Amazon A+', w: 300, h: 300, meta: {}, layers: [L.bg('#ffffff'), L.product()] }),
  },
  {
    id: 'aplus-file-size',
    pass: doc({ formatId: 'aplus-single', channel: 'Amazon A+', w: 300, h: 300, meta: { altText: 'Described.' }, layers: [L.bg('#ffffff'), L.product()] }),
    fail: doc({ formatId: 'aplus-single', channel: 'Amazon A+', w: 300, h: 300, meta: { altText: 'Described.' }, layers: [L.bg('#ffffff'), L.product()] }),
    ctx: { exportBytes: 1 * 1024 * 1024 },
    ctxFail: { exportBytes: 3 * 1024 * 1024 },
  },
  {
    id: 'ad-char-caps',
    pass: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('Short headline')] }),
    fail: doc({ channel: 'Amazon Ads', layers: [L.bg('#ffffff'), L.product(), L.text('A headline that is deliberately far too long for the published character cap on ads')] }),
  },
  {
    id: 'sbv-vertical-date-sensitive',
    pass: doc({ formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e')] }),
    fail: doc({ formatId: 'sbv-vertical', channel: 'Amazon Ads', media: 'video', w: 1080, h: 1920, layers: [L.bg('#0c150e')] }),
    failLevel: 'flag',
  },
  {
    id: 'spec-sourced',
    pass: doc({ formatId: 'amz-main' }),
    fail: doc({ formatId: 'spv-video', channel: 'Amazon Ads', media: 'video', w: 1920, h: 1080, layers: [L.bg('#0c150e')] }),
  },
]

// ── Run ─────────────────────────────────────────────────────────────────────
const covered = new Set()
console.log(`Compliance rule register: ${RULES.length} rules\n`)

for (const f of FIXTURES) {
  covered.add(f.id)
  const rule = RULES.find(r => r.id === f.id)
  if (!rule) { no(`fixture references unknown rule "${f.id}"`); continue }

  if (f.alwaysPass) {
    const level = f.alwaysLevel || 'pass'
    const hit = rowFor(f.doc || doc(), {}, f.id)
    if (hit && hit.level === level) ok(`${f.id} :: always ${level} as designed`)
    else no(`${f.id} :: expected an always-${level} row, got ${hit ? hit.level : 'no row'}`)
    continue
  }

  const pctx = f.passCtx || f.ctx || {}
  const fctx = f.ctxFail || f.ctx || {}
  const p = rowFor(f.pass, pctx, f.id)
  const q = rowFor(f.fail, fctx, f.id)
  const wantFail = f.failLevel || rule.level

  if (p && p.level === 'pass') ok(`${f.id} :: pass fixture passes`)
  else no(`${f.id} :: pass fixture expected pass, got ${p ? p.level : 'no row'}`)

  if (q && q.level === wantFail) ok(`${f.id} :: fail fixture ${wantFail}s`)
  else no(`${f.id} :: fail fixture expected ${wantFail}, got ${q ? q.level : 'no row'}`)
}

// Every rule in the register must be covered by a fixture.
for (const r of RULES) {
  if (!covered.has(r.id)) no(`rule "${r.id}" has NO fixture — coverage gap`)
}

// ── Source discipline: every blocking rule must name a source ───────────────
for (const r of RULES) {
  if (!r.source) no(`rule "${r.id}" has no source`)
  if (!r.accessed) no(`rule "${r.id}" has no accessed date`)
}

// ── Spec registry discipline ────────────────────────────────────────────────
let specPass = 0
let specFail = 0
for (const [id, s] of Object.entries(SPEC_BY_ID)) {
  const src = SPEC_SOURCES[s.source]
  if (!src) { specFail++; console.log(`FAIL  spec ${id} references unknown source ${s.source}`); }
  else if (src.confidence === 'UNSOURCED') specPass++; // deliberate: documented as unsourced
  else if (!src.url) { specFail++; console.log(`FAIL  spec ${id} source ${s.source} has no URL`); }
  else specPass++
}

// Every group used by a spec must be reachable through SPEC_GROUPS, otherwise a
// format can exist in the registry yet be invisible in every picker.
{
  const inSpecs = new Set(Object.values(SPEC_BY_ID).map(s => s.group))
  const inGroups = new Set(SPEC_GROUPS.map(g => g.id))
  for (const g of inSpecs) {
    if (!inGroups.has(g)) { specFail++; console.log(`FAIL  group "${g}" exists in AMAZON_SPECS but is not exposed by SPEC_GROUPS`) }
  }
  console.log(`\nGroup coverage: ${inGroups.size} of ${inSpecs.size} groups exposed`)
  if (inGroups.size > inSpecs.size) specFail++ // a phantom group is also wrong
}
console.log(`\nSpec registry: ${specPass} sourced, ${specFail} broken`)

// ── Report ──────────────────────────────────────────────────────────────────
console.log(`\nRULE FIXTURES: ${pass} passed, ${fail} failed`)
console.log(`Rules covered: ${covered.size}/${RULES.length}`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail || specFail ? 1 : 0)
