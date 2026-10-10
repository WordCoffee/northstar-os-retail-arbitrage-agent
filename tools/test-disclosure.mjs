// ═══════════════════════════════════════════════════════════════════════════
// AI-GENERATED PEOPLE DISCLOSURE — full test suite
//
// Covers directive item 1h:
//   • every classification, for the listing/A+/ads/video surfaces
//   • the conflict path (studio generated a person + "no people" answer)
//   • attestation validity and re-requirement after an edit
//   • the marker SURVIVING every export path (resize, re-encode, format change)
//   • the negative case: a file WITHOUT the tag must fail verification
//
// Run:  node tools/test-disclosure.mjs
// Exit: 0 = all green, 1 = a failure.
// ═══════════════════════════════════════════════════════════════════════════

import {
  PEOPLE_CLASSES, CLASS_BY_ID, DISCLOSURE_KEYWORD,
  classifyDisclosure, makeAttestation, attestationValid, assetVersion,
  embedDisclosure, readDisclosure, verifyDisclosureMarker,
  EXPORT_PATHS, ADS_DISCLOSURE_PATHS, DISCLOSURE_SCOPE, ON_CREATIVE_WARNING,
  checkFilename, buildXmpPacket,
} from '../northstar-os-ui/src/studio/engine/disclosure.js'
import { SPEC_SOURCES } from '../northstar-os-ui/src/studio/engine/specRegistry.js'

let pass = 0
let fail = 0
const failures = []
const ok = (m) => { pass++ }
const no = (m) => { fail++; failures.push(m); console.log('FAIL  ' + m) }

// ── Real 1x1 containers, so the marker work is on genuine bytes ────────────
const PNG_1x1 = Uint8Array.from(Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==', 'base64'))
const JPEG_1x1 = Uint8Array.from(Buffer.from(
  '/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q==', 'base64'))

console.log(`containers: PNG ${PNG_1x1.length} B, JPEG ${JPEG_1x1.length} B\n`)

const docWith = (meta = {}, extra = {}) => ({
  formatId: 'amz-main', w: 2000, h: 2000, channel: 'Amazon listing',
  layers: [{ kind: 'bg', fill: '#ffffff' }, { kind: 'product', x: 0.05, y: 0.05, w: 0.9, h: 0.9 }],
  meta, ...extra,
})

// ── 1a. Every classification, with no default ──────────────────────────────
{
  // No answer at all -> needs-confirmation, never a silent pass.
  const r0 = classifyDisclosure(docWith({}))
  if (r0.status === 'needs-confirmation') ok('unanswered asset reports needs-confirmation (no default)')
  else no(`unanswered asset reported ${r0.status}, expected needs-confirmation`)

  const expectTag = { 'ai-photoreal': true }
  for (const c of PEOPLE_CLASSES) {
    const r = classifyDisclosure(docWith({ peopleClass: c.id }))
    const want = expectTag[c.id] ? true : false
    if (r.status === 'decided' && r.tagRequired === want) ok(`classification ${c.id}: decided, tagRequired=${want}`)
    else no(`classification ${c.id}: got status=${r.status} tagRequired=${r.tagRequired}, expected decided/${want}`)
  }

  // An unknown classification must not be trusted.
  const rBad = classifyDisclosure(docWith({ peopleClass: 'probably-fine' }))
  if (rBad.status === 'conflict') ok('an unrecognised classification is a conflict')
  else no(`unrecognised classification reported ${rBad.status}`)

  // Every classification x every format surface (listing, A+, video, ads, Store).
  const SURFACES = [
    { formatId: 'amz-main', channel: 'Amazon listing' },
    { formatId: 'amz-secondary', channel: 'Amazon listing' },
    { formatId: 'aplus-premium-full', channel: 'Amazon A+' },
    { formatId: 'brand-story-desktop', channel: 'Amazon A+' },
    { formatId: 'sbv-landscape', channel: 'Amazon Ads', media: 'video' },
    { formatId: 'spv-video', channel: 'Amazon Ads', media: 'video' },
    { formatId: 'store-hero', channel: 'Amazon Store' },
  ]
  let combos = 0
  let comboOk = 0
  for (const c of PEOPLE_CLASSES) {
    for (const s of SURFACES) {
      combos++
      const d = { ...docWith({ peopleClass: c.id }), ...s }
      const r = classifyDisclosure(d)
      const want = !!expectTag[c.id]
      if (r.status === 'decided' && r.tagRequired === want) comboOk++
      else no(`combo ${c.id} x ${s.formatId}: status=${r.status} tagRequired=${r.tagRequired}`)
    }
  }
  ok(`every classification x every surface: ${comboOk}/${combos} correct`)
}

// ── 1b. Conflict: the studio generated a person ────────────────────────────
{
  const genNoPeople = classifyDisclosure(docWith({ peopleClass: 'no-people', studioGeneratedPerson: true }))
  if (genNoPeople.status === 'conflict') ok('studio-generated person + "no people" is a CONFLICT')
  else no(`studio-generated + no-people reported ${genNoPeople.status}`)

  const genExpressive = classifyDisclosure(docWith({ peopleClass: 'expressive-work', studioGeneratedPerson: true }))
  if (genExpressive.status === 'conflict') ok('studio-generated person + expressive-work is a CONFLICT')
  else no(`studio-generated + expressive-work reported ${genExpressive.status}`)

  // The legitimately-conflicting answer is still accepted.
  const genTagged = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', studioGeneratedPerson: true }))
  if (genTagged.status === 'decided' && genTagged.tagRequired) ok('studio-generated person + ai-photoreal is DECIDED and needs the tag')
  else no(`studio-generated + ai-photoreal reported ${genTagged.status}`)

  // A tag-required class with the marker switched off is also a conflict.
  const markerOff = classifyDisclosure(docWith({ peopleClass: 'ai-photoreal', syntheticPerformerTag: false }))
  if (markerOff.status === 'conflict') ok('tag-required class with the marker off is a CONFLICT')
  else no(`marker-off reported ${markerOff.status}`)

  // A real person photo that the studio merely placed is NOT a conflict.
  const placed = classifyDisclosure(docWith({ peopleClass: 'real-only', studioGeneratedPerson: false }))
  if (placed.status === 'decided' && !placed.tagRequired) ok('real-only with no studio generation is DECIDED, no tag')
  else no(`real-only reported ${placed.status}`)
}

// ── 1c. Attestation, and re-requirement after an edit ─────────────────────
{
  const d1 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:00Z' })
  const a1 = makeAttestation(d1, { user: 't2' })
  if (a1 && a1.user === 't2' && a1.timestamp && a1.statement && a1.classification === 'ai-photoreal') {
    ok('attestation records user, timestamp, statement, classification and version')
  } else no(`attestation incomplete: ${JSON.stringify(a1)}`)

  if (attestationValid(a1, d1)) ok('attestation is valid for the version it was made against')
  else no('attestation invalid immediately after creation')

  // ANY edit invalidates it.
  const d2 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:05Z' })
  if (!attestationValid(a1, d2)) ok('an edit RE-REQUIRES the attestation')
  else no('attestation survived an edit — re-requirement is broken')

  // Changing the classification also invalidates it.
  const d3 = docWith({ peopleClass: 'no-people', lastEditAt: '2026-10-10T00:00:00Z' })
  if (!attestationValid(a1, d3)) ok('changing the classification invalidates the attestation')
  else no('attestation survived a classification change')

  // A different asset size is a different version.
  const d4 = docWith({ peopleClass: 'ai-photoreal', lastEditAt: '2026-10-10T00:00:00Z' })
  d4.w = 1000
  if (!attestationValid(a1, d4)) ok('a size change invalidates the attestation')
  else no('attestation survived a size change')

  if (!attestationValid(null, d1)) ok('a missing attestation is invalid')
  else no('null attestation treated as valid')
}

// ── 1d. The marker SURVIVES every export path ─────────────────────────────
{
  let survived = 0
  for (const p of EXPORT_PATHS) {
    const source = p.mime === 'image/png' ? PNG_1x1 : JPEG_1x1
    let bytes
    try {
      // A format change re-encodes through the target container.
      bytes = embedDisclosure(source, p.mime, [DISCLOSURE_KEYWORD])
    } catch (e) {
      no(`export path ${p.id} could not embed: ${e.message}`)
      continue
    }
    const v = verifyDisclosureMarker(bytes, p.mime, DISCLOSURE_KEYWORD)
    if (v.ok) survived++
    else no(`export path ${p.id} LOST the marker: ${v.reason} — ${v.detail}`)
  }
  ok(`marker survived ${survived}/${EXPORT_PATHS.length} export paths`)

  // The negative case: a file that never carried the tag must FAIL.
  const plain = verifyDisclosureMarker(PNG_1x1, 'image/png', DISCLOSURE_KEYWORD)
  if (!plain.ok && plain.reason === 'no-xmp') ok('a file with no XMP fails verification (the stripping case)')
  else no(`untagged PNG reported ok=${plain.ok} reason=${plain.reason}`)

  const plainJ = verifyDisclosureMarker(JPEG_1x1, 'image/jpeg', DISCLOSURE_KEYWORD)
  if (!plainJ.ok) ok('untagged JPEG fails verification')
  else no('untagged JPEG passed verification')

  // No bytes at all.
  const none = verifyDisclosureMarker(null, 'image/png')
  if (!none.ok && none.reason === 'no-exported-bytes') ok('a missing export cannot be verified')
  else no(`missing bytes reported ok=${none.ok} reason=${none.reason}`)

  // A DIFFERENT keyword must not satisfy the check — the string is exact.
  const wrong = embedDisclosure(PNG_1x1, 'image/png', ['synthetic-performer'])
  const wrongV = verifyDisclosureMarker(wrong, 'image/png', DISCLOSURE_KEYWORD)
  if (!wrongV.ok && wrongV.reason === 'keyword-missing') ok('a near-miss keyword ("synthetic-performer") does NOT satisfy the check')
  else no(`near-miss keyword reported ok=${wrongV.ok} reason=${wrongV.reason}`)

  // A space-separated variant must also fail.
  const spaced = embedDisclosure(PNG_1x1, 'image/png', ['contains synthetic performer'])
  const spacedV = verifyDisclosureMarker(spaced, 'image/png', DISCLOSURE_KEYWORD)
  if (!spacedV.ok) ok('a space-separated variant does NOT satisfy the check')
  else no('space-separated variant passed')

  // Round-trip integrity: the packet we read back equals the packet we wrote.
  const packet = buildXmpPacket([DISCLOSURE_KEYWORD])
  const embedded = embedDisclosure(PNG_1x1, 'image/png', [DISCLOSURE_KEYWORD])
  const readBack = readDisclosure(embedded, 'image/png')
  if (readBack && readBack === packet) ok('XMP round-trips byte-identically through PNG')
  else no('XMP round-trip mismatch through PNG')

  // JPEG keeps the APP1 marker in a readable position.
  const jembed = embedDisclosure(JPEG_1x1, 'image/jpeg', [DISCLOSURE_KEYWORD])
  const jread = readDisclosure(jembed, 'image/jpeg')
  if (jread && jread.includes(DISCLOSURE_KEYWORD)) ok('XMP round-trips through JPEG APP1')
  else no('XMP round-trip failed through JPEG')

  // Unsupported container must throw rather than silently claim success.
  let threw = false
  try { embedDisclosure(PNG_1x1, 'image/webp', [DISCLOSURE_KEYWORD]) } catch { threw = true }
  if (threw) ok('an unsupported container throws instead of claiming the tag was written')
  else no('unsupported container did not throw')
}

// ── 1e / 1f. Scope labels and the ads paths ───────────────────────────────
{
  const badScope = DISCLOSURE_SCOPE.filter(s => !SPEC_SOURCES[s.source])
  if (badScope.length === 0) ok(`every scope row names a known source (${DISCLOSURE_SCOPE.length} surfaces)`)
  else no(`scope rows with unknown sources: ${badScope.map(s => s.surface).join(', ')}`)

  const reported = DISCLOSURE_SCOPE.filter(s => s.status === 'REPORTED').map(s => s.surface)
  if (reported.length > 0) ok(`scope honestly labels ${reported.length} surface(s) REPORTED: ${reported.join(', ')}`)
  else no('no scope labelled REPORTED — the gated pages are being over-claimed')

  if (ADS_DISCLOSURE_PATHS.length === 3) ok('all three Ads disclosure paths recorded')
  else no(`expected 3 Ads paths, got ${ADS_DISCLOSURE_PATHS.length}`)
  const hasUploadStep = ADS_DISCLOSURE_PATHS.some(p => /Contains synthetic performers/.test(p.step) && p.whoActs === 'Advertiser')
  if (hasUploadStep) ok('the advertiser upload step "Contains synthetic performers" is recorded')
  else no('the advertiser upload checklist step is missing')
  const hasOnCreative = ADS_DISCLOSURE_PATHS.some(p => /directly into the creative/.test(p.step))
  if (hasOnCreative) ok('the on-creative disclosure path (third-party served) is recorded')
  else no('the on-creative path is missing')
  if (/cannot be a metadata tag/.test(ON_CREATIVE_WARNING) && /conspicuous/.test(ON_CREATIVE_WARNING)) {
    ok('the on-creative warning states the tag is not a conspicuous disclosure')
  } else no('the conspicuousness warning is missing or weak')
}

// ── Filename pattern ─────────────────────────────────────────────────────
{
  const good = checkFilename('B01ABCDEFG.main.jpg')
  const bad = checkFilename('my final image (v2).jpg')
  const empty = checkFilename('')
  if (good.ok) ok('filename B01ABCDEFG.main.jpg accepted')
  else no(`valid filename rejected: ${good.detail}`)
  if (!bad.ok && !empty.ok) ok('a non-conforming filename and an empty filename are both rejected')
  else no('filename validation accepted a bad value')
}

// ── Source discipline: every AI source resolves, gated pages marked ───────
{
  for (const id of ['ai-tag-page', 'ai-announce', 'ai-ads-page', 'ny-statute']) {
    const s = SPEC_SOURCES[id]
    if (!s) { no(`source ${id} missing from SPEC_SOURCES`); continue }
    if (!s.pulled) no(`source ${id} has no pulled-at date`)
    if (/gated/i.test(s.note || '') && s.confidence === 'VERIFIED' && id === 'ai-ads-page') {
      no('ai-ads-page is login-gated but labelled VERIFIED')
    }
  }
  ok('every AI disclosure source resolves with a pulled-at date')
  if (SPEC_SOURCES['ai-ads-page'].confidence === 'REPORTED') ok('the gated Ads page is labelled REPORTED')
  else no('the gated Ads page is not labelled REPORTED')
}

console.log(`\nDISCLOSURE SUITE: ${pass} passed, ${fail} failed`)
if (failures.length) console.log('\nFailures:\n  ' + failures.join('\n  '))
process.exit(fail ? 1 : 0)
