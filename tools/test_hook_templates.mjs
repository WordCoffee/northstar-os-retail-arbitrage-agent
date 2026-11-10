// V3 contract test — hook templates as data (node, no bundler).
//   node tools/test_hook_templates.mjs
// Exits non-zero on any failure so tools/rea_regress.py can gate it.

import {
  HOOK_TEMPLATES, HOOK_SOURCES, DURATION_WINDOWS,
  hookTemplate, storyboardFromTemplate,
} from '../northstar-os-ui/src/studio/engine/hookTemplates.js'

let failures = 0
const check = (name, cond, detail = '') => {
  if (cond) console.log(`  ok   ${name}`)
  else { failures += 1; console.log(`  FAIL ${name} ${detail}`) }
}

console.log('V3 — hook templates')

// 1. every template is traceable to published sources, and thin evidence is
//    declared rather than padded with a citation that does not show it.
for (const t of HOOK_TEMPLATES) {
  const strong = (t.evidence || 'strong') === 'strong'
  check(`${t.id} evidence tier is honest`,
    strong ? t.sources.length >= 3 : (t.sources.length === 2 && !!t.evidence_gap),
    `${t.sources.length} sources, tier ${t.evidence || 'strong'}`)
  check(`${t.id} sources all resolve`, t.sources.every(s => HOOK_SOURCES[s]),
    t.sources.filter(s => !HOOK_SOURCES[s]).join(','))
}

// 2. every source carries a URL, a pull date and a confidence label
for (const [id, s] of Object.entries(HOOK_SOURCES)) {
  check(`source ${id} is dated and labelled`, !!s.url && !!s.pulled && !!s.confidence)
}

// 3. beats are contiguous, ordered, and cover the whole clip
for (const t of HOOK_TEMPLATES) {
  let cursor = 0
  let contiguous = true
  for (const b of t.beats) {
    if (Math.abs(b.from - cursor) > 1e-9) contiguous = false
    cursor = b.to
  }
  check(`${t.id} beats are contiguous`, contiguous)
  check(`${t.id} beats cover 0..1`, Math.abs(cursor - 1) < 1e-9, String(cursor))
}

// 4. no template promises performance lift
for (const t of HOOK_TEMPLATES) {
  check(`${t.id} makes no lift claim`,
    !/lift|increase|boost|convert better|guarantee/i.test(t.name))
}

// 5. a valid storyboard is timed against the Amazon window
const sb = storyboardFromTemplate('H1', { hook: 'The label nobody reads', product: 'Mogra' },
  { durationSeconds: 12, platform: 'amazonSbVideo' })
check('storyboard ok', sb.ok === true, sb.errors.join('; '))
check('four beats', sb.beats.length === 4)
check('beats are seconds inside the clip',
  sb.beats[0].start_s === 0 && sb.beats[sb.beats.length - 1].end_s === 12)
check('captions are declared mandatory', sb.captions_required === true)

// 6. the Amazon window is enforced from the published range, not invented
const tooShort = storyboardFromTemplate('H1', { hook: 'x', product: 'y' },
  { durationSeconds: 3, platform: 'amazonSbVideo' })
check('3s is refused for Amazon SB', tooShort.ok === false
  && tooShort.errors.some(e => /outside the amazonSbVideo window/.test(e)))

// 7. missing / oversized slots are refused, not padded
const missing = storyboardFromTemplate('H1', { product: 'Mogra' })
check('missing hook is refused', missing.ok === false
  && missing.errors.some(e => /'hook' is required/.test(e)))

const long = storyboardFromTemplate('H1', { hook: 'h'.repeat(61), product: 'Mogra' })
check('over-budget hook is refused', long.ok === false
  && long.errors.some(e => /cap is 60/.test(e)))

// 8. an unknown template says what is known
let threw = null
try { hookTemplate('H9') } catch (e) { threw = e.message }
check('unknown template throws with the known ids',
  !!threw && /known: H1, H2, H3, H4, H5/.test(threw), threw || '')

// 9. the published windows are the ones the sources state
check('amazon SB window is 6-45 s', DURATION_WINDOWS.amazonSbVideo.min === 6
  && DURATION_WINDOWS.amazonSbVideo.max === 45)
check('amazon store window is 2-20 s', DURATION_WINDOWS.amazonStore.min === 2
  && DURATION_WINDOWS.amazonStore.max === 20)

console.log(failures === 0 ? '\nPASS: hook templates' : `\nFAIL: ${failures} check(s)`)
process.exit(failures === 0 ? 0 : 1)
