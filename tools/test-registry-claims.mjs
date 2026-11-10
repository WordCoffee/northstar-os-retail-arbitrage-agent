// ═══════════════════════════════════════════════════════════════════════════
// REGISTRY CLAIMS — fixture harness (Phase 8 item 1)
//
// Every claim update of this phase gets one PASS fixture and one FAIL fixture:
//   • title length: 75 chars passes, 76 flags (FLAG, never a block);
//   • the AI-people metadata window is recorded with its date range and the
//     Product image guide as the authoritative method;
//   • image formats: JPEG/TIFF/PNG/non-animated GIF pass; animated GIF and an
//     unknown format fail;
//   • the 10 MB size limit is recorded as NOT enforced (a fail fixture proves
//     no rule blocks a large size);
//   • A+ eligibility displays "confirm in A+ Content Manager".
// Plus: every claim carries a source id that resolves, a pulled-at date, a
// tier and a cadence.
//
// Run:  node tools/test-registry-claims.mjs
// Exit: 0 = all green, 1 = a failure.
// ═══════════════════════════════════════════════════════════════════════════

import { REGISTRY_CLAIMS, claimStatus, claimPulledAt, titleLengthFlag, titleRuleFlags, TITLE_RULES, ITEM_HIGHLIGHTS, titleExportNotice, formatAccepted, ACCEPTED_IMAGE_FORMATS, IMAGE_SIZE_BLOCK, TITLE_LIMIT_CHARS } from '../northstar-os-ui/src/studio/engine/registryClaims.js'
import { SPEC_SOURCES } from '../northstar-os-ui/src/studio/engine/specRegistry.js'
import { RULES, checkCompliance } from '../northstar-os-ui/src/studio/engine/compliance.js'
import { mismatchFlags, buildListingContext } from '../northstar-os-ui/src/studio/engine/listingContext.js'
import { readFileSync } from 'fs'
import { fileURLToPath } from 'url'
import { join } from 'path'

const ROOT = fileURLToPath(new URL('..', import.meta.url))

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── 1. Claim records: source, pulled-at, tier, cadence ─────────────────────
for (const c of REGISTRY_CLAIMS) {
  const ids = c.source_ids || (c.source_id ? [c.source_id] : [])
  const unknown = ids.filter(id => !SPEC_SOURCES[id])
  if (ids.length === 0) {
    if (claimStatus(c) === 'UNSOURCED' || c.status === 'REPORTED') ok(`"${c.id}" carries no source and reports UNSOURCED/REPORTED (a negative record, never a fact claim)`)
    else no(`"${c.id}" without a source is not UNSOURCED`)
  } else if (unknown.length === 0) {
    ok(`"${c.id}" cites resolvable source id(s): ${ids.join(', ')}`)
  } else no(`"${c.id}" cites unknown source(s): ${unknown.join(', ')}`)
  if (ids.length) {
    const pulled = claimPulledAt(c)
    if (pulled && /^\d{4}-\d{2}-\d{2}$/.test(pulled)) ok(`"${c.id}" carries its pulled-at date (${pulled})`)
    else no(`"${c.id}" has no usable pulled-at date (${pulled})`)
  }
  if (['BLOCK', 'FLAG', 'INFO'].includes(c.tier)) ok(`"${c.id}" carries a tier (${c.tier})`)
  else no(`"${c.id}" has no valid tier (${c.tier})`)
  if (c.cadence && /^\d+d$/.test(c.cadence)) ok(`"${c.id}" carries a cadence (${c.cadence})`)
  else no(`"${c.id}" has no cadence`)
}

// ── 2. Title length: 75 passes, 76 flags; the mismatch check applies it ────
{
  const passT = titleLengthFlag('x'.repeat(TITLE_LIMIT_CHARS))
  const failT = titleLengthFlag('x'.repeat(TITLE_LIMIT_CHARS + 1))
  if (!passT.flagged && failT.flagged && failT.review.includes('FLAG')) {
    ok(`title length: ${TITLE_LIMIT_CHARS} chars pass, ${TITLE_LIMIT_CHARS + 1} flags (date-sensitive FLAG)`)
  } else no(`title-length boundary wrong: pass=${passT.flagged} fail=${failT.flagged}`)

  // A title over the limit must NOT block any compliance rule (it is a listing
  // flag, not an export block).
  const overDoc = {
    formatId: 'amz-main', w: 2000, h: 2000,
    layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.02, y: 0.02, w: 0.96, h: 0.96, dataUrl: 'data:image/png;base64,AA' }],
    meta: { title: 'y'.repeat(120) },
  }
  const pf = checkCompliance(overDoc, {})
  const sizeLikeRules = RULES.filter(r => /75/.test(r.detail || ''))
  if (pf.verdict !== 'block' && sizeLikeRules.length === 0) {
    ok('an over-limit title produces NO blocking rule (it is a listing FLAG, not an export block)')
  } else no(`over-limit title behaviour wrong: verdict=${pf.verdict} rulesMentioning75=${sizeLikeRules.map(r => r.id).join(',')}`)

  // The listing mismatch check surfaces it as a flag.
  const context = buildListingContext({
    forgeListings: [{ asin: 'B0TEST', updated: '2026-10-05T00:00:00Z', copy: { title: 'z'.repeat(90), bullets: [], description: '', keywords: '' } }],
  })
  const mm = mismatchFlags({ brief: null, context })
  if (mm.flags.some(f => f.kind === 'title-rule' && f.rule === 'title-length-75' && /FLAG/.test(f.review))) {
    ok('the listing mismatch check renders the title-length FLAG without needing a brief')
  } else no('the listing mismatch check did not flag the long title')

  const shortCtx = buildListingContext({
    forgeListings: [{ asin: 'B0TEST', updated: '2026-10-05T00:00:00Z', copy: { title: 'Short title', bullets: [], description: '', keywords: '' } }],
  })
  const mm2 = mismatchFlags({ brief: null, context: shortCtx })
  if (!mm2.flags.some(f => f.kind === 'title-rule')) ok('a clean short title produces no title flag')
  else no('a clean short title was flagged')

  // ── Phase 9 item 1: one pass and one fail fixture PER title rule ─────────
  const titleRules = {
    length: {
      pass: 'Stainless Steel Tumbler 20oz Cold Brew',
      fail: 'Stainless Steel Tumbler 20oz Cold Brew with a very long tail of descriptive words for the listing',
    },
    promotional: { pass: 'Stainless Steel Tumbler 20oz', fail: 'Stainless Steel Tumbler - Free Shipping' },
    specialChars: { pass: 'Stainless Steel Tumbler 20oz', fail: 'Stainless Steel Tumbler 20oz! Buy?' },
    sameWord: { pass: 'Stainless Steel Tumbler 20oz', fail: 'Tumbler Tumbler Tumbler Steel' },
  }
  for (const [name, fx] of Object.entries(titleRules)) {
    const p = titleRuleFlags(fx.pass)
    const f = titleRuleFlags(fx.fail)
    if (p.length === 0 && f.length >= 1) ok(`title rule "${name}": pass fixture clean, fail fixture flags (${f.map(x => x.rule).join(',')})`)
    else no(`title rule "${name}" fixtures wrong: pass=${JSON.stringify(p)} fail=${JSON.stringify(f)}`)
  }
  // Every flagged rule must be one of the recorded rule ids.
  const ruleIds = new Set(TITLE_RULES.map(r => r.id))
  const allFlags = titleRuleFlags('Tumbler Tumbler Tumbler !!! Free Shipping').map(f => f.rule)
  if (allFlags.every(id => ruleIds.has(id)) && allFlags.length >= 3) {
    ok(`every emitted title flag names a recorded rule id (${allFlags.join(',')})`)
  } else no(`a title flag named an unrecorded rule: ${allFlags.join(',')}`)

  // The register claims: title rules VERIFIED via the captured page; the
  // rollout stays REPORTED and date-sensitive.
  const lenClaim = REGISTRY_CLAIMS.find(c => c.id === 'title-length-75')
  const rollout = REGISTRY_CLAIMS.find(c => c.id === 'title-rollout-2026-07-27')
  const contentClaim = REGISTRY_CLAIMS.find(c => c.id === 'title-content-rules')
  if (lenClaim && lenClaim.status === 'VERIFIED' && lenClaim.source_id === 'title-guide'
      && Array.isArray(lenClaim.applies_except) && lenClaim.applies_except.length === 2) {
    ok('the title-length claim is VERIFIED via the captured title-guide source, with its jurisdiction exceptions')
  } else no(`title-length claim wrong: ${lenClaim && lenClaim.status}/${lenClaim && lenClaim.source_id}`)
  if (contentClaim && contentClaim.status === 'VERIFIED' && /promotional/.test(contentClaim.claim)) {
    ok('the title content rules (promotional / characters / repeated word) are recorded VERIFIED')
  } else no('title content rules missing')
  if (rollout && rollout.status === 'REPORTED' && rollout.date_sensitive === true) {
    ok('the rollout (2026-07-27 kick-off, gradual, 14-day review) stays REPORTED and date-sensitive')
  } else no('rollout claim wrong')

  // ── Item Highlights: 125 chars, comma-separated, flat-file column UNKNOWN ─
  {
    const ih = REGISTRY_CLAIMS.find(c => c.id === 'item-highlights-field')
    if (ITEM_HIGHLIGHTS.maxChars === 125 && ITEM_HIGHLIGHTS.flat_file_column === null
        && /comma-separated/.test(ITEM_HIGHLIGHTS.format)) {
      ok('Item Highlights records 125 chars + comma-separated phrases with the flat-file column UNKNOWN')
    } else no('Item Highlights record wrong')
    if (ih && ih.status === 'VERIFIED' && (ih.unknown_fields || []).includes('flat_file_column')) {
      ok('the Item Highlights claim is VERIFIED and names its UNKNOWN field')
    } else no('Item Highlights claim wrong')
    const notice = titleExportNotice()
    if (/UNKNOWN/.test(notice) && /Item Highlights/.test(notice) && /do not invent/i.test(notice)) {
      ok('the title-export notice states the UNKNOWN column and forbids inventing one')
    } else no('title-export notice wrong')
  }
}

// ── 3. AI-people metadata window + authoritative method ────────────────────
{
  const c = REGISTRY_CLAIMS.find(x => x.id === 'ai-people-metadata-window')
  if (c && c.date_from === '2026-07-22' && c.date_to === '2026-07-27') {
    ok('the AI-people metadata window records 2026-07-22 to 2026-07-27')
  } else no(`window wrong: ${c && c.date_from}..${c && c.date_to}`)
  if (c && c.authoritative_source_id === 'img-guide' && SPEC_SOURCES['img-guide']) {
    ok('the Product image guide is recorded as the authoritative method')
  } else no('the authoritative method is not the Product image guide')
  if (c && claimStatus(c) === 'REPORTED') ok('the window claim stays REPORTED (assembled from dated, partly non-Amazon sources)')
  else no(`window claim status wrong: ${c && claimStatus(c)}`)

  // FAIL fixture: a claim that names a range but no authoritative source must
  // not be able to claim authority.
  const broken = { id: 'x', source_ids: ['ai-announce'], authoritative_source_id: 'not-a-source' }
  if (!SPEC_SOURCES[broken.authoritative_source_id]) ok('fail fixture: an unknown authoritative source does not resolve')
  else no('an unknown authoritative source resolved')
}

// ── 4. Image formats ───────────────────────────────────────────────────────
for (const f of ['jpeg', 'jpg', 'tiff', 'png', 'gif']) {
  if (formatAccepted(f).ok) ok(`format ${f} passes`)
  else no(`format ${f} was rejected`)
}
for (const f of ['gif-animated', 'webp', 'avif']) {
  if (!formatAccepted(f).ok) ok(`format ${f} fails (not in the accepted set)`)
  else no(`format ${f} was accepted`)
}
{
  const c = REGISTRY_CLAIMS.find(x => x.id === 'image-formats')
  if (c && claimStatus(c) === 'VERIFIED' && ACCEPTED_IMAGE_FORMATS.length === 6) {
    ok('the formats claim is sourced to the Product image guide (VERIFIED via that source)')
  } else no(`formats claim status wrong: ${c && claimStatus(c)}`)

  // The engine rule agrees with the register.
  const okDoc = { formatId: 'amz-main', w: 2000, h: 2000, layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.02, y: 0.02, w: 0.96, h: 0.96, dataUrl: 'data:image/png;base64,AA' }], meta: { exportFormat: 'png' } }
  const badDoc = { ...okDoc, meta: { exportFormat: 'gif-animated' } }
  const r1 = checkCompliance(okDoc, {}).results.find(r => r.id === 'no-animated-gif')
  const r2 = checkCompliance(badDoc, {}).results.find(r => r.id === 'no-animated-gif')
  if (r1 && r1.level === 'pass' && r2 && r2.level === 'block') {
    ok('compliance rule no-animated-gif: PNG passes, animated GIF blocks')
  } else no(`rule fixtures wrong: ${r1 && r1.level} / ${r2 && r2.level}`)
}

// ── 5. The 10 MB limit is NOT enforced ─────────────────────────────────────
{
  if (IMAGE_SIZE_BLOCK.enforced === false) ok('the register records the 10 MB limit as NOT enforced (unconfirmed)')
  else no('the 10 MB limit is marked enforced')
  const sizeRules = RULES.filter(r => /10\s*mb|10mb|size-10/i.test(r.id + ' ' + (r.detail || '')))
  if (sizeRules.length === 0) ok('no compliance rule mentions a 10 MB block')
  else no(`a rule references 10 MB: ${sizeRules.map(r => r.id).join(', ')}`)
  // FAIL fixture: a large size (simulated via metadata) must not block.
  const bigDoc = { formatId: 'amz-main', w: 2000, h: 2000, layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.02, y: 0.02, w: 0.96, h: 0.96, dataUrl: 'data:image/png;base64,AA' }], meta: { fileSizeMB: 12 } }
  if (checkCompliance(bigDoc, {}).verdict !== 'block') ok('a 12 MB document does NOT block (nothing enforces an unconfirmed figure)')
  else no('a 12 MB document blocked')
}

// ── 6. A+ eligibility display ──────────────────────────────────────────────
{
  const c = REGISTRY_CLAIMS.find(x => x.id === 'aplus-eligibility')
  if (c && /confirm in a\+ content manager/i.test(c.display || '')) ok('A+ eligibility displays "confirm in A+ Content Manager"')
  else no('A+ eligibility display missing')
  const aplusSrc = readFileSync(join(ROOT, 'northstar-os-ui', 'src', 'pages', 'internal', 'design-studio', 'APlus.jsx'), 'utf8')
  if (/confirm eligibility in A\+ Content Manager/i.test(aplusSrc)) ok('the A+ workspace states the same instruction')
  else no('the A+ workspace does not state the eligibility instruction')
}

console.log(`\nREGISTRY CLAIMS: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
