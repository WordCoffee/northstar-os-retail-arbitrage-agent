// ═══════════════════════════════════════════════════════════════════════════
// INDEXING HONESTY REGISTER — fixture + static-scan harness (Phase 6 item 7)
//
// 1. Every claim carries a source id, confidence and the pulled-at date.
// 2. Unofficial claims are REPORTED; a claim with no registry source is
//    UNSOURCED; nothing is silently upgraded.
// 3. No entry claims that alt text or on-image text improves ranking, and no
//    UI source in the studio says so either (the static scan proves it, with a
//    positive control so the scan cannot pass vacuously).
//
// Run:  node tools/test-indexing-register.mjs
// Exit: 0 = all green, 1 = a failure.
// ═══════════════════════════════════════════════════════════════════════════

import { readdirSync, readFileSync, statSync } from 'fs'
import { join, relative } from 'path'
import { fileURLToPath } from 'url'
import {
  INDEXING_CLAIMS, CONFIDENCE, SUBJECT, claimConfidence, claimPulledAt,
  claimsSupportingRanking, rankingAdviceFor,
} from '../northstar-os-ui/src/studio/engine/indexing.js'
import { SPEC_SOURCES } from '../northstar-os-ui/src/studio/engine/specRegistry.js'

const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(ROOT, 'northstar-os-ui', 'src')

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++; console.log('PASS  ' + m) }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── 1. Register shape ──────────────────────────────────────────────────────
for (const c of INDEXING_CLAIMS) {
  const missing = ['id', 'surface', 'subject', 'claim', 'official', 'supports_ranking', 'note']
    .filter(k => c[k] === undefined || c[k] === null || c[k] === '')
  if (missing.length === 0) ok(`claim "${c.id}" carries its full record`)
  else no(`claim "${c.id}" is missing: ${missing.join(', ')}`)
}

// ── 2. Confidence + pulled-at ──────────────────────────────────────────────
const sourced = INDEXING_CLAIMS.filter(c => c.source_id)
const unknownSource = sourced.filter(c => !SPEC_SOURCES[c.source_id])
if (unknownSource.length === 0) ok(`every source id resolves in the registry (${sourced.length} sourced claims)`)
else no(`claims cite unknown source ids: ${unknownSource.map(c => `${c.id}:${c.source_id}`).join(', ')}`)

for (const c of sourced) {
  const conf = claimConfidence(c)
  const want = c.official ? CONFIDENCE.VERIFIED : CONFIDENCE.REPORTED
  if (conf === want) ok(`"${c.id}" -> ${conf} (official=${c.official})`)
  else no(`"${c.id}" -> ${conf}, expected ${want}`)
  const pulled = claimPulledAt(c)
  if (pulled && /^\d{4}-\d{2}-\d{2}$/.test(pulled)) ok(`"${c.id}" carries its pulled-at date (${pulled})`)
  else no(`"${c.id}" has no usable pulled-at date (${pulled})`)
}
const unsourced = INDEXING_CLAIMS.filter(c => !c.source_id)
for (const c of unsourced) {
  if (claimConfidence(c) === CONFIDENCE.UNSOURCED) ok(`"${c.id}" with no source is UNSOURCED, not plausible`)
  else no(`"${c.id}" without a source reported as ${claimConfidence(c)}`)
}

// The exact string the requirement calls out: unofficial -> REPORTED.
const folklore = INDEXING_CLAIMS.find(c => c.id === 'image-text-folklore')
if (folklore && claimConfidence(folklore) === CONFIDENCE.UNSOURCED && folklore.official === false) {
  ok('the "on-image text lifts ranking" folklore is UNSOURCED + unofficial (never advice)')
} else no('the folklore claim is not marked unofficial/UNSOURCED')

// ── 3. Imagery never supports ranking, and ranking support stays text-only ──
const imagery = INDEXING_CLAIMS.filter(c => c.subject === SUBJECT.ALT_TEXT || c.subject === SUBJECT.IMAGE_TEXT)
if (imagery.length >= 3 && imagery.every(c => c.supports_ranking === false)) {
  ok(`no imagery/alt-text claim claims a ranking effect (${imagery.length} checked)`)
} else no('an imagery or alt-text claim claims a ranking effect')

const ranking = claimsSupportingRanking()
if (ranking.length > 0 && ranking.every(c => c.subject === SUBJECT.TEXT || c.subject === SUBJECT.BACKEND_TERMS)) {
  ok(`rank-supporting claims are text-only (${ranking.map(c => c.id).join(', ')})`)
} else no(`rank-supporting set is empty or includes imagery: ${ranking.map(c => c.id).join(', ')}`)

// ── 4. The advice guard ────────────────────────────────────────────────────
for (const subject of [SUBJECT.ALT_TEXT, SUBJECT.IMAGE_TEXT]) {
  const a = rankingAdviceFor(subject)
  if (a.adviceable === false && /no recorded Amazon source/i.test(a.statement)) {
    ok(`rankingAdviceFor(${subject}) refuses with a stated reason`)
  } else no(`rankingAdviceFor(${subject}) did not refuse honestly`)
}
if (rankingAdviceFor(SUBJECT.TEXT).adviceable === true) ok('text claims remain adviseable (they have a documented source)')
else no('text claims were wrongly blocked')

// ── 5. Static scan: the studio never ASSERTS imagery ranking gains ─────────
const NEGATION = /(not\b|never\b|no recorded|no amazon|isn't|is not|doesn't|does not|cannot|can.t|won.t|will not|nor\b)/i
const MENTION = /(alt[- ]?text|image text|on-image text|file ?name|exif)/gi
// The promise shape we forbid: ranking/seo GAINS. "indexed" alone is a purpose
// statement (text is indexed) and is allowed; the register's own identifiers
// (INDEXING_CLAIMS) must not trip the scan.
const GAIN = /\b(ranks?|ranking|boosts?|seo)\b/i

function walk(dir) {
  const out = []
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    const st = statSync(p)
    if (st.isDirectory()) out.push(...walk(p))
    else if (/\.(js|jsx)$/.test(name)) out.push(p)
  }
  return out
}

let scanned = 0
let negatedHits = 0
const violations = []
for (const file of walk(SRC)) {
  scanned++
  const text = readFileSync(file, 'utf8')
  const lineOf = (idx) => text.slice(0, idx).split('\n').length
  // Global iteration so a mention and its negation can sit on different lines
  // (prose wraps, and so do comments). The window is generous on purpose: a
  // FALSE POSITIVE here costs a look, a FALSE NEGATIVE ships dishonest advice.
  const mention = /(alt[- ]?text|image text|on-image text|file ?name|exif)/gi
  let m
  while ((m = mention.exec(text)) !== null) {
    const window = text.slice(Math.max(0, m.index - 220), Math.min(text.length, m.index + 260))
    if (GAIN.test(window)) {
      if (NEGATION.test(window)) negatedHits++
      else violations.push(`${relative(ROOT, file)}:${lineOf(m.index)}: ${window.replace(/\s+/g, ' ').trim().slice(0, 150)}`)
    }
  }
}
if (violations.length === 0) ok(`static scan: ${scanned} source files, no positive imagery-ranking claim`)
else no(`static scan found ${violations.length} positive imagery-ranking claim(s):\n      ` + violations.slice(0, 6).join('\n      '))
if (negatedHits >= 2) ok(`positive control: ${negatedHits} negated mentions exist, so the scan is not vacuous`)
else no(`positive control failed: only ${negatedHits} negated mentions - the scan may be searching nothing`)

console.log(`\nINDEXING REGISTER: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
